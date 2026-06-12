/**
 * hosted-answer-only — svara en REN FRÅGA hostat utan att starta en sandbox
 * (G1, prod-incidenten 2026-06-12 site-3e7d71ad).
 *
 * Problemet: hostat kör VARJE följdprompt hela sandbox-pipelinen
 * (pip install → OpenClaw-konduktorbeslut → ev. build) bara för att få veta
 * att "Vad tycker du om sajten?" var en ren fråga — minuter och stream-budget
 * för ett svar som tar sekunder att generera. Den här modulen är en
 * LÄTTVIKTIG PRE-KLASSIFICERING som körs i prompt-routen FÖRE
 * ``startHostedBuild`` och kortsluter till answer-only ENBART vid hög
 * konfidens "ren fråga".
 *
 * GRÄNSDRAGNING mot konduktorn (duplicera aldrig konduktorlogiken):
 *   - Pre-klassificeraren är en GROV grind med exakt två utfall: "ren fråga"
 *     (hög konfidens) eller "möjlig ändring" (allt annat). Den fattar ALDRIG
 *     ändringsbeslut, väljer aldrig roll/editKind och producerar aldrig ett
 *     OpenClaw-beslut — konduktorn äger fortsatt alla ändringsbeslut i
 *     byggvägen (run_openclaw_followup.py i sandboxen).
 *   - Vid MINSTA tvekan (låg/medel konfidens, parse-fel, timeout, LLM-fel,
 *     verktygs-intent/markeringar/baseRunId i payloaden) → byggvägen, exakt
 *     som idag. Hellre långsam än felklassad.
 *   - Utan OPENAI_API_KEY är ingen klassificering möjlig → alltid byggvägen
 *     (oförändrat beteende).
 *
 * ÄRLIGHETSKONTRAKT (bryter aldrig #313):
 *   - Den här modulen LÄSER bara (KV GET + blob GET via befintliga hostade
 *     läsare). Den bumpar aldrig version, skriver aldrig KV-pekare, triggar
 *     aldrig preview-refresh och skriver aldrig artefakter.
 *   - Svaret grundas i sajtens FAKTISKA hostade kontext: composition-bilden
 *     (readHostedSiteComposition: project-input + run-artefakter via KV +
 *     blob) plus site-brief ur artefakt-tarballen. Saknas kontexten helt →
 *     ingen kortslutning (byggvägen ger då sitt vanliga ärliga fel/utfall).
 *   - Svarstexten genereras med samma SOUL-bas + dynamiska ärlighetsrader
 *     som den lokala conversation-gaten (generateConversationAnswer i
 *     route.ts): den påstår aldrig att något ändrats i denna tur.
 */

import {
  fetchHostedRunArtefactsTar,
  hostedRunArtefactBundle,
  listHostedRunsForSite,
} from "./hosted-run-history";
import { chatWithOpenAi, openaiEnv } from "./openai";
import { readHostedSiteComposition } from "./site-composition";
import { loadSoulBaseLines } from "./soul";

/**
 * Tidsbudget för pre-klassificeringen. Vid timeout vinner byggvägen — grinden
 * får aldrig bli en ny hängpunkt framför sandbox-starten (samma race-mönster
 * som APPLIED_CONFIRMATION_TIMEOUT_MS i route.ts).
 */
const PRECLASSIFY_TIMEOUT_MS = 8_000;

/** Tak för det serialiserade kontext-snittet (under openai.ts 8000-taket). */
const CONTEXT_SNIPPET_MAX_CHARS = 5_000;

/** Säkerhetstak för den sammansatta systemprompten (spegel av route.ts). */
const SYSTEM_SAFE_CHARS = 7_800;

/** Fallback-personan när SOUL.md saknas (samma rader som route.ts). */
const SOUL_FALLBACK_LINES: ReadonlyArray<string> = [
  "Du är OpenClaw, dirigenten i Sajtbyggaren — operatörens chattassistent.",
  "Svara kort, vänligt och ärligt på svenska.",
];

/** Ärlig felrad när svars-anropet misslyckas (sajten är orörd). */
const ANSWER_ERROR_TEXT =
  "Jag kunde inte ta fram ett svar just nu (chat-anropet misslyckades). " +
  "Sajten är oförändrad — prova igen om en stund.";

/**
 * Pre-klassificeringens utfall. ``pure_question`` ges BARA vid hög konfidens;
 * ``build`` är default för allt annat (inklusive alla felvägar).
 */
export type HostedFollowupPreclassification = "pure_question" | "build";

/** Resultatet av en lyckad kortslutning (route.ts bygger svars-payloaden). */
export interface HostedAnswerOnlyOutcome {
  answerText: string;
  conversation: {
    conversationKind: "question";
    role: null;
    expectsAnswer: true;
  };
  timings: { classifyMs: number; contextMs: number; answerMs: number };
}

/**
 * Tolka klassificerar-LLM:ens råsvar. Ren funktion (source-lockad +
 * enhetstestbar): ENDAST ett parsebart JSON-objekt med
 * ``classification === "pure_question"`` OCH ``confidence === "high"`` ger
 * kortslutning — allt annat (parse-fel, andra etiketter, medium/low) → build.
 */
export function parsePreclassificationReply(
  raw: string,
): HostedFollowupPreclassification {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start === -1 || end <= start) return "build";
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw.slice(start, end + 1));
  } catch {
    return "build";
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return "build";
  }
  const obj = parsed as Record<string, unknown>;
  if (obj.classification === "pure_question" && obj.confidence === "high") {
    return "pure_question";
  }
  return "build";
}

/**
 * Klassificera följdprompten: ren fråga (hög konfidens) eller möjlig ändring.
 * Kastar aldrig; alla felvägar (no-key, timeout, LLM-fel, parse-fel) → build.
 */
async function preclassifyHostedFollowup(
  prompt: string,
): Promise<HostedFollowupPreclassification> {
  if (!openaiEnv("OPENAI_API_KEY")) return "build";
  const systemContent = [
    "Du är en strikt klassificerare i Sajtbyggaren (verktyget som bygger",
    "operatörens företagshemsida). Operatören skriver följdmeddelanden i en",
    "chatt som BÅDE kan svara på frågor och bygga om sajten. Avgör om",
    "meddelandet är en REN FRÅGA/KONVERSATION (förväntar enbart ett svar i",
    "chatten) eller om det KAN uttrycka en önskan att ändra/bygga något.",
    'Svara med ENDAST en JSON-rad: {"classification":"pure_question"|',
    '"possible_change","confidence":"high"|"medium"|"low"}.',
    'Regler: "pure_question" kräver att meddelandet inte innehåller någon',
    "ändringsönskan alls — bara fråga/åsikt/småprat (t.ex. \"Vad tycker du",
    'om sajten?", "Vilka sidor finns?", "Hur funkar previewen?").',
    "ALLT som kan tolkas som en instruktion, önskan eller ett behov av",
    'ändring — även vagt eller formulerat som fråga ("kan vi göra den lite',
    'varmare?", "borde rubriken vara större?") — är "possible_change".',
    "Är du det minsta osäker: välj \"possible_change\" eller sänk",
    "confidence. En felklassad \"pure_question\" är dyr; \"possible_change\"",
    "är alltid säkert (byggvägen svarar också på frågor).",
  ].join("\n");
  try {
    const timeout = new Promise<null>((resolve) => {
      const timer = setTimeout(() => resolve(null), PRECLASSIFY_TIMEOUT_MS);
      if (typeof timer.unref === "function") timer.unref();
    });
    const completion = chatWithOpenAi([
      { role: "system", content: systemContent },
      { role: "user", content: prompt.slice(0, 8000) },
    ])
      .then(({ message }) => message.content)
      .catch(() => null);
    const reply = await Promise.race([completion, timeout]);
    if (reply === null) return "build";
    return parsePreclassificationReply(reply);
  } catch {
    return "build";
  }
}

interface HostedAnswerContext {
  /** Bounded JSON-snitt med composition + site-brief (grundningen). */
  contextSnippet: string;
  /** Faktarad om senaste byggda version, eller null när okänd. */
  versionLine: string | null;
}

/**
 * Sätt ihop den hostade sajtkontexten ur BEFINTLIGA read-only-källor:
 * composition-bilden (KV-index + run-artefakt-tarball + project-input via
 * run-state-pekaren) plus site-brief ur samma tarball (cache:ad per URL).
 * Returnerar null när sajten saknar hostad kontext — då kortsluter vi INTE
 * (byggvägen ger sitt vanliga ärliga utfall, t.ex. run-state-preflight-felet).
 */
async function assembleHostedAnswerContext(
  siteId: string,
): Promise<HostedAnswerContext | null> {
  let composition: Awaited<ReturnType<typeof readHostedSiteComposition>>;
  try {
    composition = await readHostedSiteComposition(siteId);
  } catch {
    return null;
  }
  if (!composition) return null;

  // site-brief ur senaste versionens artefakt-tarball (best-effort — tar- och
  // list-cacharna i hosted-run-history gör detta billigt direkt efter
  // composition-läsningen ovan).
  let siteBrief: Record<string, unknown> | null = null;
  try {
    const { entries } = await listHostedRunsForSite(siteId, 1);
    const entry = entries[0];
    if (entry) {
      const files = await fetchHostedRunArtefactsTar(entry);
      if (files) {
        siteBrief = hostedRunArtefactBundle(entry, files).siteBrief;
      }
    }
  } catch {
    siteBrief = null;
  }

  const contextPayload = {
    composition: {
      siteId: composition.siteId,
      version: composition.version,
      companyName: composition.companyName,
      language: composition.language,
      scaffoldId: composition.scaffoldId,
      variantId: composition.variantId,
      routes: composition.routes,
      components: composition.components,
      dependencies: composition.dependencies,
      lastBuild: composition.lastBuild,
    },
    siteBrief,
  };
  let contextSnippet: string;
  try {
    contextSnippet = JSON.stringify(contextPayload).slice(
      0,
      CONTEXT_SNIPPET_MAX_CHARS,
    );
  } catch {
    return null;
  }
  const versionLine =
    typeof composition.version === "number"
      ? `Senaste byggda version av sajten är v${composition.version}.`
      : null;
  return { contextSnippet, versionLine };
}

/**
 * Generera det grundade chat-svaret. Samma ärlighetsordning som den lokala
 * conversation-gaten: SOUL-basen FÖRST, de dynamiska ärlighetsraderna EFTER
 * (de vinner alltid; vid teckenöverskott släpps SOUL-basen, aldrig
 * ärlighetsraderna). Kastar aldrig — fel ger den ärliga felraden.
 */
async function generateGroundedHostedAnswer(
  prompt: string,
  context: HostedAnswerContext,
): Promise<string> {
  const soulBaseLines = loadSoulBaseLines() ?? SOUL_FALLBACK_LINES;
  const dynamicLines = [
    "Du har INTE ändrat sajten i DENNA tur: påstå aldrig att något byggts " +
      "eller ändrats nu.",
    context.versionLine
      ? "Byggrollernas historik (FAKTA du får referera): " +
        context.versionLine +
        " Om operatören frågar vad som ändrats: referera historiken i " +
        "stället för att säga att inget hänt."
      : "Du har ingen bygghistorik i den här turen — säg det ärligt om " +
        "operatören frågar vad som ändrats.",
    "Frågan gäller operatörens sajt. Grunda svaret ENBART i sajtkontexten " +
      `nedan — hitta aldrig på detaljer som inte står där:\n${context.contextSnippet}`,
    "Om frågan gäller något som inte står i sajtkontexten: säg det ärligt " +
      "i stället för att gissa.",
    "Svara kort, vänligt och ärligt på svenska. Ställ ingen fråga tillbaka " +
      "om det inte behövs.",
  ];
  const combined = [...soulBaseLines, ...dynamicLines].join("\n");
  const systemContent =
    combined.length > SYSTEM_SAFE_CHARS ? dynamicLines.join("\n") : combined;
  try {
    const { message } = await chatWithOpenAi([
      { role: "system", content: systemContent },
      { role: "user", content: prompt.slice(0, 8000) },
    ]);
    return message.content;
  } catch {
    return ANSWER_ERROR_TEXT;
  }
}

/**
 * Hela kortslutnings-grinden. Returnerar ett färdigt answer-only-utfall
 * ELLER null = "ta byggvägen" (default för varje tveksamhet/felväg).
 *
 * Grindordning (varje steg kan bara släppa igenom, aldrig tvinga fram):
 *   1. Strukturella byggsignaler (toolIntent/markedSections/baseRunId) →
 *      byggvägen. Ett verktygs-intent ÄR en ändringsintention per definition.
 *   2. Utan OPENAI_API_KEY → byggvägen (ingen klassificering möjlig).
 *   3. LLM-pre-klassificering: ENDAST "pure_question" med hög konfidens
 *      fortsätter; timeout/fel/medium/low → byggvägen.
 *   4. Hostad sajtkontext måste finnas (composition) — annars byggvägen så
 *      preflight-felen/utfallen förblir exakt dagens.
 */
export async function maybeAnswerHostedFollowupWithoutSandbox(options: {
  prompt: string;
  siteId: string;
  hasToolIntent: boolean;
  hasMarkedSections: boolean;
  hasBaseRunId: boolean;
}): Promise<HostedAnswerOnlyOutcome | null> {
  if (options.hasToolIntent || options.hasMarkedSections || options.hasBaseRunId) {
    return null;
  }
  if (!openaiEnv("OPENAI_API_KEY")) return null;

  const tClassify = Date.now();
  const classification = await preclassifyHostedFollowup(options.prompt);
  const classifyMs = Date.now() - tClassify;
  if (classification !== "pure_question") return null;

  const tContext = Date.now();
  const context = await assembleHostedAnswerContext(options.siteId);
  const contextMs = Date.now() - tContext;
  if (!context) return null;

  const tAnswer = Date.now();
  const answerText = await generateGroundedHostedAnswer(options.prompt, context);
  const answerMs = Date.now() - tAnswer;

  return {
    answerText,
    // Grov, ärlig etikett från pre-klassificeraren (kind "question" +
    // expectsAnswer) — konduktorns finare conversationKind-vokabulär ägs av
    // byggvägen. role är null: ingen byggroll agerade.
    conversation: { conversationKind: "question", role: null, expectsAnswer: true },
    timings: { classifyMs, contextMs, answerMs },
  };
}
