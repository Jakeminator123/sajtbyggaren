import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { runBuild } from "@/lib/build-runner";
import {
  hostedRunKey,
  startHostedBuild,
  type HostedBuildRunStatus,
  type HostedFollowupResult,
} from "@/lib/hosted-build-runner";
import {
  hostedPythonRuntimeUnavailable,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import { getKvStore, kvGetJson } from "@/lib/kv-store";
import { stopAndWaitPreviewServer } from "@/lib/local-preview-server";
import { assertLocalhost } from "@/lib/localhost-guard";
import { chatWithOpenAi, openaiEnv } from "@/lib/openai";
import { enforceRateLimit } from "@/lib/rate-limit";
import { runOpenClawFollowupApply } from "@/lib/openclaw-runner";
import { runPromptToProjectInput } from "@/lib/prompt-runner";
import { classifyMessage } from "@/lib/router-classify-runner";
import { readRunChangeSet } from "@/lib/run-change-set";
import { readAppliedCopyDirectives, readBuildResult, runsDir } from "@/lib/runs";
import { loadSoulBaseLines } from "@/lib/soul";

// Hostat: bygget kör detached i en sandbox men NDJSON-streamen poll:ar KV
// tills done/failed. 300 s är Fluid-taket på Hobby (Pro tillåter mer) — vid
// budget-slut avslutas streamen ärligt med runId så klienten kan polla
// GET /api/hosted-build/<runId> i stället. Lokalt påverkas inget (ingen
// maxDuration-enforcement i `next dev`).
export const runtime = "nodejs";
export const maxDuration = 300;

// Operator-prototype: keep the prompt small enough that an accidental
// 50 MB paste cannot wedge the build pipeline. The cap is generous for
// real prompts but blocks obvious abuse. Trim before length-checks so a
// whitespace-only payload fails at the API boundary with 400 instead of
// slipping through `.min(1)` and surfacing later as a 500 from the
// Python helper's own emptiness-check.
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/**
 * Discovery-wizardens payload. Schemat speglar `DiscoveryPayload` i
 * `apps/viewser/components/discovery-wizard/wizard-payload.ts`. Vi
 * validerar bara den yttersta strukturen — `answers`-objektet är
 * intentionellt löst (operator-prototyp) och kontrolleras djupare av
 * `_apply_discovery_overrides` på Python-sidan där fält som inte
 * känns igen helt enkelt ignoreras.
 */
const DiscoveryPayloadSchema = z
  .object({
    // Heter `schemaVersion` (inte version) avsiktligt: test_viewser_files
    // förbjuder en sidecar-meta-shape med "version:z" eller "projectId:z"
    // som client-payload — de tillhör Project Input-meta, inte API-
    // kontraktet. Discovery har sin egen schema-version som lever
    // oberoende av PI-schemat.
    //
    // Accepterar v1 (legacy, utan ``directives``-block) OCH v2
    // (2026-05-22, med strukturerade directives för att hoppa över
    // briefModel-extraktion när data finns). Frontend bumpar till v2
    // i ``buildDiscoveryPayload`` — backend (Python) tolererar båda
    // versioner via ``_apply_discovery_overrides``-stratifieringen.
    // Före detta union avvisade route:n v2-payloads med kryptiska
    // "Invalid input: expected 1" som operatören inte kunde tolka.
    schemaVersion: z.union([z.literal(1), z.literal(2)]),
    rawPrompt: z.string().trim().max(8000),
    contentBranch: z.string().trim().max(40).optional(),
    scaffoldHint: z.string().trim().max(60).optional(),
    answers: z.record(z.string(), z.unknown()),
    // Strukturerade wizard-directives introducerade i v2
    // (2026-05-22, se docs/contracts/wizard-discovery.v2.md). Vi
    // validerar bara att det är ett objekt — djupare schema-koll
    // ligger på Python-sidan (``_apply_discovery_overrides`` /
    // ``_normalise_wizard_directives``) eftersom directives är ett
    // växande kontrakt mellan rollout-passar (pass 1: backend
    // accepterar, pass 2: frontend skickar — där vi är nu, pass 3:
    // backend konsumerar fler fält). Att låsa schemat hårt här
    // skulle tvinga koordinerade deploys per pass — onödigt strikt
    // för ett internt API på localhost.
    directives: z.record(z.string(), z.unknown()).optional(),
  })
  .strict()
  .superRefine((payload, context) => {
    if (Object.prototype.hasOwnProperty.call(payload.answers, "starterId")) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["answers", "starterId"],
        message: "Discovery-payload får inte sätta starterId.",
      });
    }
  });

// Run-id-mönstret matchar `RUN_ID_PATTERN` i `lib/runs.ts` så vi avvisar
// path-traversal och whitespace-injektion redan vid 400-validering.
const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;

// ADR 0046: route-/sektions-id:n följer samma slug-grammatik som
// data-section-id-markörerna i codegen (gemener/siffror/bindestreck).
const SECTION_REF_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/**
 * En preview-markering från "Markera modul"-läget (ADR 0046).
 * `routeId`/`sectionId` valideras hårt här (slug-grammatik) och igen på
 * Python-sidan mot base-runens emittedSections-facit. `note` är fri
 * kontext (sektionens rubriktext) — aldrig en instruktion.
 */
const MarkedSectionSchema = z
  .object({
    routeId: z.string().trim().regex(SECTION_REF_PATTERN, "Ogiltigt routeId."),
    sectionId: z
      .string()
      .trim()
      .regex(SECTION_REF_PATTERN, "Ogiltigt sectionId."),
    note: z.string().trim().max(200).optional(),
  })
  .strict();

const PromptPayloadSchema = z.object({
  // Master-prompten från discovery-wizarden kan bli flera kilobyte
  // (operatörens originaltext + 8 sektioner med kategori, kontakt,
  // tjänster, story, sidor, ton). 16k är vältilltaget för worst-case
  // (alla wizard-fält maxade) utan att riskera att brytas vid en
  // ovanligt lång story-text.
  prompt: z
    .string()
    .trim()
    .min(1, "Prompt får inte vara tom.")
    .max(16000, "Prompt får vara max 16 000 tecken."),
  mode: z.enum(["init", "followup"]).default("init"),
  siteId: z
    .string()
    .trim()
    .regex(SITE_ID_PATTERN, "Ogiltigt siteId för följdprompt.")
    .optional(),
  // Iterera från en specifik historisk run istället för senaste. UI
  // sätter denna när operatören klickar "Iterera från denna" på en
  // versions-rad (se GAP-backend-build-trace-endpoint.md). Bakåt-
  // kompatibel: utan baseRunId fungerar follow-up exakt som idag
  // (prompt_to_project_input.py läser senaste PI-snapshotet för siteId).
  baseRunId: z
    .string()
    .trim()
    .regex(RUN_ID_PATTERN, "Ogiltigt baseRunId.")
    .optional(),
  discovery: DiscoveryPayloadSchema.optional(),
  // ADR 0046: operatörens preview-markeringar ("Markera modul"). Mjuk
  // prioriteringssignal — valideras mot base-runens facit på Python-sidan
  // och triggar aldrig ensam en build. Max 5 (speglar MAX_MARKED_SECTIONS
  // i preview-inspector-context.tsx).
  markedSections: z.array(MarkedSectionSchema).max(5).optional(),
  // Specialist-dispatch steg 2 (task A): strukturerat verktygs-intent från
  // builder-dialogerna ({tool, params}). Skalet hålls permissivt — params
  // djup-valideras per tool i sin konsument (asset_set re-valideras fält
  // för fält i prompt-runner.ts + Python-helpern). Bara asset_set forwardas
  // till CLI:t; övriga tools konsumeras i sina egna sömmar och ignoreras
  // här precis som när fältet strippades tyst av det icke-stricta schemat.
  toolIntent: z
    .object({
      tool: z.string().trim().min(1).max(40),
      params: z.record(z.string(), z.unknown()),
    })
    .optional(),
}).superRefine((payload, context) => {
  if (payload.mode === "followup" && !payload.siteId) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["siteId"],
      message: "Följdprompt kräver valt siteId.",
    });
  }
  if (payload.mode === "followup" && payload.discovery) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["discovery"],
      message: "Discovery-wizarden används bara i init-läge.",
    });
  }
  if (payload.baseRunId && payload.mode !== "followup") {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["baseRunId"],
      message: "baseRunId kan bara anges i follow-up-läge.",
    });
  }
  if (payload.markedSections?.length && payload.mode !== "followup") {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["markedSections"],
      message: "markedSections kan bara anges i follow-up-läge.",
    });
  }
  if (payload.toolIntent && payload.mode !== "followup") {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["toolIntent"],
      message: "toolIntent kan bara anges i follow-up-läge.",
    });
  }
});

// B169: per-siteId mutex för prompt-flödet. Tidigare en enda global
// ``let promptInFlight: Promise | null`` som serialiserade ALLA sajter i
// processen — ett segt/hängande bygge på site A blockerade init/follow-up på
// site B. Speglar build-runner.ts:s per-site Map-mönster (rad 23-40):
//
//   - Follow-ups keyas på ``siteId`` så två följdpromptar mot SAMMA sajt
//     fortfarande serialiseras (versionsrace-skyddet: Phase 1 läser/bumpar
//     ``meta.version`` + skriver PI-snapshot — det FÅR inte race:a).
//   - Init-läget har ingen siteId vid API-gränsen (den genereras i Phase 1
//     med en unik uuid-suffix, se ``prompt_to_project_input.slugify_site_id``),
//     så två inits kan ALDRIG kollidera på siteId. De får en unik nyckel per
//     request och kör därför parallellt i stället för att blockera varandra.
//
// ``finally``-grenen rensar entry:t bara om promise:n fortfarande är den
// aktiva — så en samtidig follow-up (som hunnit skriva en ny entry för samma
// siteId) inte oavsiktligt nukas. Samma försiktiga identity-guard som
// build-runner.ts.
const promptInFlight = new Map<string, Promise<unknown>>();

// ADR 0046: gruppera markeringarna till RouterContext.routeSections-formen
// ({routeId: [sectionId, ...]}) för den deterministiska klassificeringen.
// Tom/undefined input → undefined så classifyMessage-payloaden är oförändrad
// när inga markeringar finns.
function markedSectionsAsRouteSections(
  markedSections: { routeId: string; sectionId: string }[] | undefined,
): Record<string, string[]> | undefined {
  if (!markedSections?.length) return undefined;
  const grouped: Record<string, string[]> = {};
  for (const { routeId, sectionId } of markedSections) {
    const sections = (grouped[routeId] ??= []);
    if (!sections.includes(sectionId)) sections.push(sectionId);
  }
  return grouped;
}

// Read the raw `status` field from build-result.json without trusting
// its type. build_site.py writes "ok" / "degraded" / "failed" / "skipped";
// dev_generate.py writes "mock-complete". Anything else collapses to
// null so the client surface explicitly handles the unknown case
// instead of silently rendering a green "build klar" banner over a
// failed run (B44).
function extractBuildStatus(buildResult: Record<string, unknown>): string | null {
  const value = buildResult.status;
  return typeof value === "string" ? value : null;
}

// Read build-result.json's `appliedVisibleEffect` without trusting its type.
// build_site.py writes this boolean on follow-up builds (B155). It is the
// signal we use to decide whether the legacy copy/edit path already landed a
// visible change for this follow-up — see the routerDecision honesty gate in
// runPromptBuildOnce. Returns null on init builds / field-drift.
function extractAppliedVisibleEffect(
  buildResult: Record<string, unknown>,
): boolean | null {
  const value = buildResult.appliedVisibleEffect;
  return typeof value === "boolean" ? value : null;
}

// F1 slice 2 (conductor wiring): the conductor conversation kinds the
// dispatcher answers in chat WITHOUT a build. Mirrors
// _ANSWER_ONLY_CONVERSATION_KINDS in scripts/run_openclaw_followup.py.
// ConversationKind is a conductor-layer concept (slice 1) — the router's
// locked messageKind enum and router-decision.schema.json are untouched.
const CONVERSATION_ANSWER_KINDS: ReadonlySet<string> = new Set([
  "small_talk",
  "site_opinion",
  "question",
]);

type ConversationMetadata = {
  conversationKind: string;
  role: string | null;
  // F1 slice 3 (Scout #262): the conductor's explicit "this turn expects a chat
  // answer, not a build" signal (ConversationDecision.expectsAnswer). Read
  // defensively; the UI short-circuits answer-only on it instead of inferring
  // from "no runId".
  expectsAnswer: boolean;
};

// Read the additive ``conversation`` metadata block off the bridge's decision
// payload defensively (same field-drift-safe pattern as extractBuildStatus):
// a missing/malformed block degrades to null and the unchanged build flow runs.
function extractConversation(
  decision: Record<string, unknown> | null | undefined,
): ConversationMetadata | null {
  if (!decision) return null;
  const raw = decision.conversation;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const obj = raw as Record<string, unknown>;
  if (typeof obj.conversationKind !== "string") return null;
  return {
    conversationKind: obj.conversationKind,
    role: typeof obj.role === "string" ? obj.role : null,
    expectsAnswer: obj.expectsAnswer === true,
  };
}

// Honest no-key fallback: without OPENAI_API_KEY we never fake a conversation
// — the operator gets a plain Swedish line saying exactly why there is no
// answer. Mirrors briefModel's mock-no-key honesty (never a pretend chat).
const CONVERSATION_NO_KEY_ANSWER =
  "Jag kan inte svara utan API-nyckel (OPENAI_API_KEY saknas). Sajten är " +
  "oförändrad. Lägg till nyckeln i repo-rotens .env så kan jag chatta.";

const CONVERSATION_ERROR_ANSWER =
  "Jag kunde inte ta fram ett svar just nu (chat-anropet misslyckades). " +
  "Sajten är oförändrad — prova igen om en stund.";

// Bounded site context for the chat helper: the bridge's decision already
// carries the read-only AssembledContext payload (what the router asked for).
// We pass at most ~6000 chars so lib/openai.ts's 8000-char/message cap never
// trips; an empty payload yields null and the system prompt tells the model
// to be honest about not seeing the site.
function conversationContextSnippet(
  decision: Record<string, unknown>,
): string | null {
  const context = decision.context;
  if (!context || typeof context !== "object" || Array.isArray(context)) {
    return null;
  }
  const payload = (context as Record<string, unknown>).payload;
  if (!payload || typeof payload !== "object") return null;
  try {
    const json = JSON.stringify(payload);
    if (!json || json === "{}") return null;
    return json.slice(0, 6000);
  } catch {
    return null;
  }
}

/**
 * Roll-minne (operatörsfynd 2026-06-10): dirigenten svarade "jag ändrade
 * inget i den här turen" direkt EFTER att stylisten byggt v2 — tekniskt sant
 * men kontextlöst, så systemet såg ut att motsäga sig självt (rollerna delade
 * inget minne). Bygg en kompakt, faktabaserad historik-rad ur den senaste
 * KOMPLETTA runens artefakter (version + ändringsprompt ur ``input.json``)
 * så svars-rollen kan referera vad byggrollerna gjort — som historik, aldrig
 * som en ändring i denna tur. Defensiv: null på minsta läsfel.
 */
async function latestChangeSnippet(
  siteId: string | null | undefined,
): Promise<string | null> {
  if (!siteId) return null;
  const latest = await latestCompletedRunForSite(siteId);
  if (!latest) return null;
  let changePrompt: string | null = null;
  try {
    const raw = await fs.readFile(
      path.join(runsDir(), latest.runId, "input.json"),
      "utf-8",
    );
    const input = JSON.parse(raw) as Record<string, unknown>;
    for (const key of ["followUpPrompt", "originalPrompt", "rawPrompt"] as const) {
      const value = input[key];
      if (typeof value === "string" && value.trim()) {
        changePrompt = value.trim().slice(0, 300);
        break;
      }
    }
  } catch {
    // input.json saknas/oläsbar -> historiken får klara sig utan prompten.
  }
  const versionLabel = latest.version !== null ? `v${latest.version}` : "okänd version";
  const promptPart = changePrompt
    ? ` Senaste ändringsprompt: "${changePrompt}".`
    : "";
  return `Senaste byggda version av sajten är ${versionLabel}.${promptPart}`;
}

// ADR 0044: defensive fallback persona base, used when
// docs/openclaw-workspace/SOUL.md is missing/unreadable (loadSoulBaseLines
// returns null). These are exactly the hardcoded lines the chat persona used
// before SOUL became the single source of truth, so a missing/unreadable file
// degrades to today's behaviour rather than to an empty persona.
const CONVERSATION_SOUL_FALLBACK_LINES: ReadonlyArray<string> = [
  "Du är OpenClaw, dirigenten i Sajtbyggaren — operatörens chattassistent.",
  "Svara kort, vänligt och ärligt på svenska.",
];

// Safe ceiling for the assembled system message. lib/openai.ts throws over
// MAX_INPUT_CHARS_PER_MESSAGE (8000); we stay comfortably under it and, on
// overflow (e.g. a large site_opinion context snippet), drop the SOUL base —
// never the dynamic honesty lines.
const CONVERSATION_SYSTEM_SAFE_CHARS = 7800;

/**
 * F1 slice 2: generate the honest chat answer for a conversation kind via the
 * EXISTING lib/openai.ts chat helper. Never throws: no key → the honest
 * no-key line; any helper failure → an honest error line. The answer text is
 * plain chat copy — it never claims a site change THIS turn (the gate
 * guarantees no build ran), but it MAY reference the build history snippet as
 * facts so the dispatcher never contradicts what the build roles just did.
 *
 * ADR 0044: the persona base is loaded from docs/openclaw-workspace/SOUL.md and
 * the honest dynamic lines are appended AFTER it, so SOUL controls only the
 * chat persona/tone and can never override the honesty contract.
 */
async function generateConversationAnswer(
  prompt: string,
  conversation: ConversationMetadata,
  decision: Record<string, unknown>,
  siteId: string | null = null,
): Promise<string> {
  if (!openaiEnv("OPENAI_API_KEY")) {
    return CONVERSATION_NO_KEY_ANSWER;
  }
  const contextSnippet = conversationContextSnippet(decision);
  const historySnippet = await latestChangeSnippet(siteId);
  // ADR 0044: persona-basen kommer från docs/openclaw-workspace/SOUL.md
  // (server-side, cacheas per process, trunkeras). Vid läsfel/saknad fil
  // faller vi tillbaka på de hårdkodade raderna nedan. De DYNAMISKA
  // ärlighetsraderna byggs separat och läggs EFTER basen så de ALLTID vinner —
  // SOUL-texten kan aldrig redigera bort "inget ändrat i DENNA tur",
  // roll-minnet eller site_opinion-grundningen.
  const soulBaseLines = loadSoulBaseLines() ?? CONVERSATION_SOUL_FALLBACK_LINES;
  const dynamicLines = [
    "Du har INTE ändrat sajten i DENNA tur: påstå aldrig att något byggts " +
      "eller ändrats nu.",
    // Roll-minnet: historiken är fakta från artefakterna, inte ett påstående
    // om denna tur. Utan den motsade dirigenten stylistens nyss byggda v2.
    historySnippet
      ? "Byggrollernas historik (FAKTA du får referera): " +
        historySnippet +
        " Om operatören frågar vad som ändrats: referera historiken i " +
        "stället för att säga att inget hänt."
      : "Du har ingen bygghistorik i den här turen — säg det ärligt om " +
        "operatören frågar vad som ändrats.",
    conversation.conversationKind === "site_opinion"
      ? contextSnippet
        ? "Frågan gäller operatörens sajt. Grunda omdömet ENBART i " +
          `sajtkontexten nedan:\n${contextSnippet}`
        : "Frågan gäller operatörens sajt, men du har ingen sajtkontext i " +
          "den här turen — säg ärligt att du inte kan bedöma detaljerna."
      : "Om frågan gäller sajtens detaljer och du saknar kontext: säg det " +
        "ärligt i stället för att gissa.",
  ];
  // SOUL-basen FÖRST, de dynamiska ärlighetsraderna EFTER (de vinner). Skulle
  // den sammansatta systemprompten ändå spränga lib/openai.ts:s 8000-teckenstak
  // (t.ex. ett stort site_opinion-kontextsnitt) släpper vi SOUL-basen — aldrig
  // de dynamiska raderna — så anropet aldrig kastar och ärligheten finns kvar.
  const systemLines = [...soulBaseLines, ...dynamicLines];
  const combinedSystem = systemLines.join("\n");
  const systemContent =
    combinedSystem.length > CONVERSATION_SYSTEM_SAFE_CHARS
      ? dynamicLines.join("\n")
      : combinedSystem;
  try {
    const { message } = await chatWithOpenAi([
      { role: "system", content: systemContent },
      { role: "user", content: prompt.slice(0, 8000) },
    ]);
    return message.content;
  } catch {
    return CONVERSATION_ERROR_ANSWER;
  }
}

/**
 * Roll-bekräftelse efter en APPLICERAD ändring (operatörsfynd 2026-06-11):
 * dirigenten var stum efter ett lyckat bygge — edits bär ``expectsAnswer=false``
 * så ingen svarstext genererades och operatören fick bara den deterministiska
 * statusraden. Den här helpern låter dirigenten bekräfta kort i chatten vad
 * byggrollerna just gjorde, UTAN att rucka ärlighetskontraktet:
 *
 *   - Genereras BARA när kedjan rapporterade en SYNLIG ändring
 *     (``bridge.previewShouldRefresh === true``). Mount-only-utfall behåller
 *     den deterministiska "registrerad men syns inte än"-raden oförändrad.
 *   - Modellen får ENBART kedjans rapporterade fakta (editKind/version/
 *     routes) + operatörens prompt — aldrig något att "fylla i".
 *   - No-key / helper-fel / TIMEOUT → null, och FloatingChat faller tillbaka
 *     på den deterministiska success-raden. Fältet kan aldrig fejka en
 *     ändring: det skickas bara på svar som redan bär ett riktigt runId +
 *     bridge.
 *   - Tidsbudget (extern granskning 2026-06-11, fynd 2): OpenAI-klientens
 *     default-timeout är lång (minuter) — utan eget tak skulle ett hängande
 *     bekräftelse-anrop blockera HELA byggsvaret efter ett redan färdigt
 *     bygge. Promise.race med ett kort tak; vid timeout vinner den
 *     deterministiska raden (bekräftelsen är grädde, aldrig kritisk väg).
 */
const APPLIED_CONFIRMATION_TIMEOUT_MS = 8_000;

async function generateAppliedConfirmation(
  prompt: string,
  chain: Record<string, unknown>,
  role: string | null,
): Promise<string | null> {
  if (!openaiEnv("OPENAI_API_KEY")) return null;
  const facts: string[] = [];
  if (typeof chain.editKind === "string") {
    facts.push(`Ändringstyp: ${chain.editKind}`);
  }
  if (typeof chain.version === "number") {
    facts.push(`Ny version: v${chain.version}`);
  }
  if (
    Array.isArray(chain.changedRoutes) &&
    chain.changedRoutes.every((r) => typeof r === "string")
  ) {
    facts.push(`Ändrade sidor: ${(chain.changedRoutes as string[]).join(", ")}`);
  }
  if (role) facts.push(`Utförande roll: ${role}`);
  const systemContent = [
    "Du är OpenClaw, dirigenten i Sajtbyggaren — operatörens chattassistent.",
    "Byggrollerna har precis genomfört en ändring och previewen visar den " +
      "nya versionen.",
    "Bekräfta ändringen kort på svenska: 1–2 meningar, vänligt och konkret.",
    "Grunda dig ENBART i fakta nedan. Hitta aldrig på detaljer som inte " +
      "står där, lova inget mer än det som gjordes, och ställ ingen fråga.",
    // Extern granskning 2026-06-11 (fynd 4): operatörens prompt är en ÖNSKAN,
    // inte ett facit — en sammansatt önskan kan ha delar som inte landade.
    "Operatörens önskan nedan kan innehålla delar som INTE genomfördes — " +
      "bekräfta endast det som står i Fakta, aldrig önskan i sig.",
    "Nämn versionsnumret när det finns.",
    `Fakta:\n${facts.join("\n") || "(inga ytterligare fakta)"}`,
  ].join("\n");
  try {
    // Promise.race-tak: vid timeout faller vi till null (deterministisk rad)
    // i stället för att hålla det redan färdiga byggsvaret som gisslan.
    const timeout = new Promise<null>((resolve) => {
      const timer = setTimeout(
        () => resolve(null),
        APPLIED_CONFIRMATION_TIMEOUT_MS,
      );
      if (typeof timer.unref === "function") timer.unref();
    });
    // .catch på kedjan (inte bara try/catch): om timeouten vinner racet och
    // anropet FALLERAR senare får processen ingen unhandled rejection.
    const completion = chatWithOpenAi([
      { role: "system", content: systemContent },
      {
        role: "user",
        content: `Min ändringsönskan var: ${prompt.slice(0, 500)}`,
      },
    ])
      .then(({ message }) => message.content.trim() || null)
      .catch(() => null);
    return await Promise.race([completion, timeout]);
  } catch {
    return null;
  }
}

/**
 * B164 helper: the freshest COMPLETED run on disk for a siteId, or null.
 *
 * "Completed" = the run-dir has a ``build-result.json`` (so we only ever treat
 * a real, finished version as a recoverable one — never a half-written run-dir
 * that the targeted render abandoned). We read run-dirs in mtime order and
 * short-circuit at the first ``build-result.json`` whose ``siteId`` matches, so
 * the common case (the site's latest run is among the most recently modified
 * dirs) costs only a couple of reads. Unlike ``listRuns``' bounded global
 * window this never misses the site's run, which matters for the
 * before/after-bridge comparison in ``runPromptBuildOnce`` — a missed snapshot
 * there could either silently re-double-build OR re-surface a stale run.
 *
 * Only ever called on the FOLLOW-UP path (twice per follow-up: once for the
 * pre-bridge snapshot, once on the rare bridge-failure recovery), so the
 * worst-case full scan is bounded and off the hot init path.
 */
async function latestCompletedRunForSite(
  siteId: string,
): Promise<{ runId: string; version: number | null; mtimeMs: number } | null> {
  const root = runsDir();
  let entries;
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    // ENOENT (fresh env, no data/runs yet) or any read error → no run to find.
    return null;
  }
  const dirs = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
  if (!dirs.length) return null;

  const stats = await Promise.all(
    dirs.map(async (name) => {
      try {
        const stat = await fs.stat(path.join(root, name));
        return { name, mtimeMs: stat.mtimeMs };
      } catch {
        return null;
      }
    }),
  );
  const live = stats.filter(
    (entry): entry is { name: string; mtimeMs: number } => entry !== null,
  );
  if (!live.length) return null;
  live.sort((a, b) => b.mtimeMs - a.mtimeMs);

  for (const { name, mtimeMs } of live) {
    let buildResult: Record<string, unknown>;
    try {
      buildResult = await readBuildResult(name);
    } catch {
      // No build-result.json (partial/aborted run) → not a completed version
      // for any site; skip it and keep scanning older dirs.
      continue;
    }
    if (buildResult.siteId === siteId) {
      const rawVersion = buildResult.version;
      const version =
        typeof rawVersion === "number" && Number.isInteger(rawVersion)
          ? rawVersion
          : null;
      // mtimeMs follows along so the B164/B175 recovery can tell a run that
      // appeared DURING this request (chain landed it) from a stale one.
      return { runId: name, version, mtimeMs };
    }
  }
  return null;
}

/**
 * runPromptBuildOnce — kör Phase 1 (prompt → Project Input) och Phase 2
 * (build_site.py via runBuild) sekventiellt. Den frivilliga
 * `onPhase1Done`-callbacken bjuds in mellan faserna så stream-läget
 * kan emittera en riktig "building"-signal till klienten exakt när
 * Phase 1 är klar — istället för att klienten gissar via setTimeout
 * (B122). Synkrona callers (utan callback) får samma slutresultat
 * som tidigare utan beteendeskillnad.
 */
async function runPromptBuildOnce(
  payload: z.infer<typeof PromptPayloadSchema>,
  options?: { onPhase1Done?: () => void },
) {
  // Skiva 1b (action bridge): on FOLLOW-UPS, first try the OpenClaw apply
  // bridge. It runs the deterministic OpenClaw decision and — ONLY for an
  // edit_instruction (action=patch_plan_request) — the KÖR-7 chain
  // (router -> context -> patch -> apply -> targeted render). The chain stops
  // at an honest gate BEFORE any build for read-only kinds (answer/
  // clarification/plan_only) and for unmapped/no-op edits, so this NEVER
  // double-builds: when the bridge applied a visible change we re-surface its
  // run and skip the legacy build; otherwise we fall through to the unchanged
  // legacy copy/edit build path below. Init builds skip the bridge entirely so
  // init flow is byte-for-byte unchanged. Degrades to null on any failure.
  // B164: snapshot the latest COMPLETED run for this site BEFORE the bridge
  // runs. The KÖR-7 chain inside runOpenClawFollowupApply writes a new
  // immutable version (PI snapshot + targeted render) BEFORE build_site.py
  // finishes. If the bridge then fails LATE (timeout / exit!=0 / truncated
  // stdout / parse-fail) runOpenClawFollowupApply returns null — and the legacy
  // Phase 1+2 fallback below would silently build a SECOND version on top of
  // the one the chain already landed. We capture the pre-bridge runId here and
  // re-check after a null result (see the B164 recovery block below).
  // B175: also capture WHEN the request started — when the site has NO
  // completed run pre-bridge (first-run scenario: init's run pruned away or
  // never completed), runId-diffing has nothing to compare against, so the
  // recovery instead asks "did a completed run for this site appear DURING
  // this request?" via the run-dir mtime.
  const requestStartMs = Date.now();
  const preBridgeLatestRun =
    payload.mode === "followup" && payload.siteId
      ? await latestCompletedRunForSite(payload.siteId).catch(() => null)
      : null;

  const applyResult =
    payload.mode === "followup" && payload.siteId
      ? await runOpenClawFollowupApply(payload.prompt, {
          siteId: payload.siteId,
          baseRunId: payload.baseRunId,
        }).catch(() => null)
      : null;

  // F1 slice 3: the additive ``conversation`` metadata (which role acted +
  // conversationKind + expectsAnswer) extracted once from the bridge decision,
  // so every follow-up return path can thread it to the client for the honest
  // role-row in FloatingChat. Null on init / bridge failure (graceful).
  const conversationMeta = extractConversation(applyResult?.decision);

  if (applyResult && applyResult.bridge.applied) {
    const chain = applyResult.bridge.chain ?? {};
    const chainRunId = typeof chain.runId === "string" ? chain.runId : null;
    if (chainRunId) {
      // The OpenClaw chain materialised a new immutable version (e.g. a restyle
      // or capability add) and swapped current.json on ok/degraded. Re-surface
      // its run as the authoritative build so the EXISTING client flow (pick
      // runId -> refresh preview via onBuildDone) works unchanged — no legacy
      // build runs (the chain already built the targeted version).
      //
      // B163: the legacy path stops the local preview inside runBuild (see
      // build-runner.ts) so the NEXT preview start picks up the freshly
      // published current.json. This early-return path skipped that stop, and
      // startPreviewServer is idempotent (reuses a live `next start` whose cwd
      // is the OLD build dir) — so the iframe kept serving the previous
      // version after a successful OpenClaw apply. Stop the preview here too;
      // idempotent no-op when none is running, and never fails the response.
      // (vercel-sandbox previews restart per request and are unaffected.)
      if (payload.siteId) {
        try {
          await stopAndWaitPreviewServer(payload.siteId);
        } catch {
          // Preview-stop must never break a successful apply response.
        }
      }
      let bridgeBuildResult: Record<string, unknown> = {};
      try {
        bridgeBuildResult = await readBuildResult(chainRunId);
      } catch {
        bridgeBuildResult = {};
      }
      let bridgeCopyDirectives: Awaited<
        ReturnType<typeof readAppliedCopyDirectives>
      > = [];
      try {
        bridgeCopyDirectives = await readAppliedCopyDirectives(chainRunId);
      } catch {
        bridgeCopyDirectives = [];
      }
      let bridgeChangeSet: Awaited<ReturnType<typeof readRunChangeSet>> = null;
      try {
        bridgeChangeSet = await readRunChangeSet(
          chainRunId,
          payload.baseRunId ? { baseRunId: payload.baseRunId } : {},
        );
      } catch {
        bridgeChangeSet = null;
      }
      const chainBuildStatus =
        typeof chain.buildStatus === "string" ? chain.buildStatus : null;
      const chainVersion =
        typeof chain.version === "number" ? chain.version : null;
      // Roll-bekräftelse (operatörsfynd 2026-06-11): på en SYNLIGT applicerad
      // ändring genererar dirigenten en kort bekräftelse i chatten. Grindad på
      // previewShouldRefresh så en mount-only-montering ALDRIG får en
      // pratsam "klart!"-rad; null vid no-key/fel → deterministisk rad står.
      const appliedAnswerText =
        applyResult.bridge.previewShouldRefresh === true
          ? await generateAppliedConfirmation(
              payload.prompt,
              chain,
              conversationMeta?.role ?? null,
            )
          : null;
      return {
        runId: chainRunId,
        siteId: payload.siteId,
        projectId: null,
        version: chainVersion,
        briefSource: null,
        buildStatus: extractBuildStatus(bridgeBuildResult) ?? chainBuildStatus,
        buildResult: bridgeBuildResult,
        appliedCopyDirectives: bridgeCopyDirectives,
        changeSet: bridgeChangeSet,
        // A change DID apply, so we never show the "action bridge saknas" /
        // router no-build lines over it; the build summary + bridge line stand.
        routerDecision: null,
        openClawDecision: null,
        // Skiva 1b: the honest action-bridge outcome (applied /
        // previewShouldRefresh + chain) so FloatingChat shows a restyle /
        // capability success line and refreshes the preview.
        bridge: applyResult.bridge,
        // Roll-bekräftelsen (nullable). Skickas BARA tillsammans med ett
        // riktigt runId + applied bridge, så use-followup-build:s answer-only-
        // gren (som kräver !runId) aldrig kan misstolka den.
        answerText: appliedAnswerText,
        // F1 slice 3: which role acted (e.g. section_builder) for the honest
        // role-row; threaded but never controls build/preview.
        conversation: conversationMeta,
      };
    }
  }

  // F1 slice 2 (conversation gate): when the bridge classified the follow-up
  // as a CONVERSATION (small_talk / site_opinion / question) it already
  // stopped before any build (bridge.applied=false, decision=answer_only).
  // Return an honest chat answer instead of falling through to the legacy
  // Phase 1+2 build — a joke or an opinion question must never write a new
  // version. Guarantees: no build starts, no version is written,
  // appliedVisibleEffect is never true (buildResult stays empty and the
  // decision's validator forces it false) and previewShouldRefresh stays
  // false (the bridge said so). The answer text comes from the existing
  // lib/openai.ts chat helper with an honest no-key fallback.
  if (applyResult && !applyResult.bridge.applied) {
    // Reuse the conversation metadata extracted once above (extern granskning
    // 2026-06-10, F5: the duplicate extractConversation call invited drift).
    const conversation = conversationMeta;
    // F4 (same review): the gate honours BOTH the kind set AND the explicit
    // expectsAnswer signal, matching how use-followup-build + FloatingChat
    // already read the contract — if the conductor ever marks a kind outside
    // CONVERSATION_ANSWER_KINDS as answer-only, the server and the clients
    // must agree (answer, not a silent legacy build).
    if (
      conversation &&
      (CONVERSATION_ANSWER_KINDS.has(conversation.conversationKind) ||
        conversation.expectsAnswer === true)
    ) {
      const answerText = await generateConversationAnswer(
        payload.prompt,
        conversation,
        applyResult.decision,
        payload.siteId ?? null,
      );
      return {
        runId: null,
        siteId: payload.siteId ?? null,
        projectId: null,
        version: null,
        briefSource: null,
        buildStatus: null,
        buildResult: {},
        appliedCopyDirectives: [],
        changeSet: null,
        routerDecision: null,
        // The honest answer-only decision (+ conversation metadata) so the
        // client can see WHY no build ran; never rendered raw.
        openClawDecision: applyResult.decision,
        bridge: applyResult.bridge,
        // F1 slice 2: the honest chat answer FloatingChat renders instead of
        // a build summary. Never implies a site change.
        answerText,
        conversation,
      };
    }
  }

  // B164: the bridge returned null (timeout / exit!=0 / truncated stdout /
  // parse-fail). BEFORE falling through to the legacy Phase 1+2 build — which
  // would silently build a SECOND version on top of whatever the KÖR-7 chain
  // may have already written — re-check whether a NEW completed run for this
  // site appeared since the pre-bridge snapshot. If so, the chain DID land a
  // version; re-surface THAT run with an honest degraded status instead of
  // double-building. No retry and no second model call: a pure disk re-check.
  // (A non-null applyResult with bridge.applied===false is a real no-op — the
  // chain stopped at an honest gate BEFORE any build — so it is safe and we
  // intentionally do NOT trigger recovery for it.)
  //
  // B175: the recovery also covers the FIRST-run scenario. When the site had
  // no completed run pre-bridge (preBridgeLatestRun === null — e.g. the init
  // run was pruned by SAJTBYGGAREN_MAX_RUNS retention, or never completed)
  // there is no runId to diff against, so we instead require the post-bridge
  // run to have appeared DURING this request (run-dir mtime >= request start
  // FLOORED to the fs-timestamp granularity — see the floor rationale below).
  // That keeps the original safety: a pre-bridge snapshot that failed for a
  // transient reason can never make us re-surface a STALE run as if this
  // prompt produced it.
  if (applyResult === null && payload.mode === "followup" && payload.siteId) {
    const postBridgeLatestRun = await latestCompletedRunForSite(
      payload.siteId,
    ).catch(() => null);
    // A legitimately-new run is created by the bridge SECONDS into the request
    // (Python spawn + KÖR-7 chain + targeted build), so its run-dir mtime lands
    // at/after requestStartMs. The only reason any tolerance is needed is
    // filesystem timestamp coarseness: some filesystems floor mtime to whole
    // seconds (FAT/exFAT, older Unix), which can round a brand-new run's mtime
    // DOWN into the same clock-tick as requestStartMs. We therefore compare
    // against requestStartMs FLOORED to that granularity — never against a flat
    // window SUBTRACTED from it.
    //
    // B175-followup fix (review 2026-06-10): the previous flat 5 s subtraction
    // admitted runs whose mtime was up to 5 s BEFORE the request started, i.e.
    // genuinely STALE runs, which contradicts "appeared during this request"
    // and could re-surface a stale run as if this prompt produced it. The
    // earlier `<requestStart> minus window` shape is exactly what we drop.
    // Flooring only tolerates the sub-granularity
    // rounding of the request-start instant itself (< 1 tick), so a run created
    // in any earlier tick is correctly rejected. (NTFS/ext4/APFS are sub-ms, so
    // on the normal dev disk this is effectively `mtimeMs >= requestStartMs`.)
    const FS_TIMESTAMP_GRANULARITY_MS = 2_000;
    const requestStartFloorMs =
      Math.floor(requestStartMs / FS_TIMESTAMP_GRANULARITY_MS) *
      FS_TIMESTAMP_GRANULARITY_MS;
    const chainLandedNewRun =
      postBridgeLatestRun !== null &&
      (preBridgeLatestRun !== null
        ? postBridgeLatestRun.runId !== preBridgeLatestRun.runId
        : postBridgeLatestRun.mtimeMs >= requestStartFloorMs);
    if (postBridgeLatestRun && chainLandedNewRun) {
      const recoveredRunId = postBridgeLatestRun.runId;
      // Mirror B163: stop the preview so the next start picks up the chain's
      // freshly published current.json instead of serving the old build dir.
      // Idempotent + never fails the recovered response.
      try {
        await stopAndWaitPreviewServer(payload.siteId);
      } catch {
        // Preview-stop must never break the recovered response.
      }
      let recoveredBuildResult: Record<string, unknown> = {};
      try {
        recoveredBuildResult = await readBuildResult(recoveredRunId);
      } catch {
        recoveredBuildResult = {};
      }
      let recoveredCopyDirectives: Awaited<
        ReturnType<typeof readAppliedCopyDirectives>
      > = [];
      try {
        recoveredCopyDirectives = await readAppliedCopyDirectives(recoveredRunId);
      } catch {
        recoveredCopyDirectives = [];
      }
      let recoveredChangeSet: Awaited<ReturnType<typeof readRunChangeSet>> = null;
      try {
        recoveredChangeSet = await readRunChangeSet(
          recoveredRunId,
          payload.baseRunId ? { baseRunId: payload.baseRunId } : {},
        );
      } catch {
        recoveredChangeSet = null;
      }
      const recoveredStatus = extractBuildStatus(recoveredBuildResult);
      const recoveredLanded =
        recoveredStatus === "ok" || recoveredStatus === "degraded";
      return {
        runId: recoveredRunId,
        siteId: payload.siteId,
        projectId: null,
        version: postBridgeLatestRun.version,
        briefSource: null,
        // Honest degraded status: a version DID land but the apply bridge
        // failed to report it, so we never present this as a clean success.
        // A failed chain build stays "failed"; anything else is downgraded to
        // "degraded" so the operator sees "Build klar med varning", not green.
        buildStatus: recoveredStatus === "failed" ? "failed" : "degraded",
        buildResult: recoveredBuildResult,
        appliedCopyDirectives: recoveredCopyDirectives,
        changeSet: recoveredChangeSet,
        routerDecision: null,
        openClawDecision: null,
        // Distinct marker so FloatingChat/dialogs see the recovered apply: a
        // version landed (applied) and the preview should refresh when the
        // build completed, but the bridge itself degraded.
        bridge: {
          status: "degraded-recovered",
          applied: recoveredLanded,
          previewShouldRefresh: recoveredLanded,
          chain: null,
        },
        // F1 slice 3: role-row metadata (null here - the bridge failed before
        // reporting a decision, so we honestly carry no role).
        conversation: conversationMeta,
      };
    }
  }

  // KÖR-6a (skiva 1a): classify the incoming message with the DETERMINISTIC
  // router so the operator UI can honestly reframe a non-build outcome
  // (question/plan/unclear) on the legacy/fallback path. READ-ONLY metadata: it
  // runs concurrently with the build, never gates it, and never starts a
  // preview. Failures degrade to null. (The OpenClaw decision below comes from
  // the apply bridge above, which already classified the message — no second
  // spawn; on init or bridge failure it is simply null.)
  const routerDecisionPromise = classifyMessage(payload.prompt, {
    siteId: payload.siteId,
    // ADR 0046: preview-markeringarna som read-only RouterContext-
    // prioriteringssignal ({routeId: [sectionId]}). Aldrig build-styrande.
    routeSections: markedSectionsAsRouteSections(payload.markedSections),
  }).catch(() => null);

  // Phase 1: prompt -> Project Input on disk (data/prompt-inputs/<siteId>.*).
  const helper = await runPromptToProjectInput(payload.prompt, {
    mode: payload.mode,
    siteId: payload.siteId,
    baseRunId: payload.baseRunId,
    discovery: payload.discovery,
    markedSections: payload.markedSections,
    toolIntent: payload.toolIntent,
  });
  options?.onPhase1Done?.();

  // Phase 2: build_site.py with the absolute dossier path produced
  // above. runBuild's mutex serialises this against any concurrent
  // /api/build call so two builds do not race over .generated/.
  const build = await runBuild(helper.siteId, helper.dossierPath);

  // ADR 0034 path B (B155 UI): expose the validated copy-directives
  // that this version actually applied, härledda ur project-input-
  // snapshotet på dossierPath. Init-builds + builds utan directives
  // returnerar [] så UI:t kan särskilja "no-op" (appliedVisibleEffect
  // === false) från "applied without structured copy" (true men tom
  // lista). Aldrig en throw — felaktig artefakt landar som [] och
  // FloatingChat faller tillbaka på den generiska success-raden.
  let appliedCopyDirectives: Awaited<
    ReturnType<typeof readAppliedCopyDirectives>
  > = [];
  try {
    appliedCopyDirectives = await readAppliedCopyDirectives(build.runId);
  } catch {
    appliedCopyDirectives = [];
  }

  // UI-gap-fix (2026-06-02, Jakobs flagga): exponera en EXAKT change-set
  // för follow-ups så FloatingChat kan visa bekräftade deltas (routes
  // tillagda/borttagna, variant-byten) under "Ändrat" istället för
  // prompt-heuristiken under "Troligen ändrat". Härleds genom att diffa
  // den nya runen mot föregående run (eller baseRunId). Init-builds har
  // ingen föregående run → null. Aldrig en throw: artefakt-läsfel landar
  // som null och UI:t faller tillbaka på heuristiken.
  let changeSet: Awaited<ReturnType<typeof readRunChangeSet>> = null;
  if (payload.mode === "followup") {
    try {
      changeSet = await readRunChangeSet(
        build.runId,
        payload.baseRunId ? { baseRunId: payload.baseRunId } : {},
      );
    } catch {
      changeSet = null;
    }
  }

  // KÖR-6a honesty gate (skiva 1a): expose the router's read-only opinion
  // alongside runId/siteId/buildStatus, BUT never let it preempt a visible
  // change the (unchanged) legacy copy/edit path actually landed for this
  // follow-up. FloatingChat's summarizeRouterDecision (#177) honestly reframes
  // non-build outcomes (question/plan/unclear) but would, for the
  // artifact_patch_only / unclear classifications, wrongly say "not built yet"
  // over a copy change that DID apply. So when this follow-up applied copy
  // directives or reported a visible effect, we send routerDecision=null and
  // the existing authoritative build summary stands alone ("Ingen påhittad
  // effekt"). Init builds and genuine no-op follow-ups carry the full decision.
  const routerDecisionRaw = await routerDecisionPromise;
  const legacyPathAppliedVisibleChange =
    payload.mode === "followup" &&
    (appliedCopyDirectives.length > 0 ||
      extractAppliedVisibleEffect(build.buildResult) === true);
  const routerDecision = legacyPathAppliedVisibleChange
    ? null
    : routerDecisionRaw;

  // Same honesty gate for the OpenClaw decision. The decision comes from the
  // apply bridge above, which classified the message even on the fallback path
  // (read-only kind / unmapped edit / bridge failure -> null). V0 returns
  // patch_plan_request for an edit instruction, but the (unchanged) deterministic
  // copyDirective path may have ALREADY applied that edit (e.g. "byt rubriken
  // till X"). Rendering "action bridge saknas" over a change that DID land would
  // be dishonest, so when the legacy path applied a visible change we drop the
  // decision and the authoritative build summary stands alone.
  const openClawDecisionRaw = applyResult?.decision ?? null;
  const openClawDecision = legacyPathAppliedVisibleChange
    ? null
    : openClawDecisionRaw;

  return {
    runId: build.runId,
    siteId: helper.siteId,
    projectId: helper.projectId,
    version: helper.version,
    briefSource: helper.briefSource,
    // B44: surface the canonical build status so the operator UI can
    // distinguish ok / degraded / failed instead of treating any
    // returned runId as a successful build. build-runner.ts intentionally
    // returns the structured failure path with a runId so failed runs
    // still appear in Run History (B40 contract); without buildStatus
    // on the wire PromptBuilder used to flag those as "Build klar".
    buildStatus: extractBuildStatus(build.buildResult),
    buildResult: build.buildResult,
    appliedCopyDirectives,
    changeSet,
    // Read-only KÖR-6a router decision (deterministic classify_message).
    // Sibling of runId/siteId/buildStatus; never controls build/preview.
    routerDecision,
    // Read-only OpenClaw Core V0 follow-up decision (skiva 1b). Null on init
    // builds and on follow-ups where the legacy path applied a visible change.
    // Richer superset of routerDecision; never controls build/preview.
    openClawDecision,
    // Skiva 1b: the action-bridge outcome (applied=false on this fallback path)
    // for transparency; null on init. FloatingChat ignores a non-applied bridge.
    bridge: applyResult?.bridge ?? null,
    // F1 slice 3: which role acted (stylist/copy/section_builder or null) for
    // the honest role-row; threaded but never controls build/preview.
    conversation: conversationMeta,
  };
}

async function runPromptBuildSerially(
  payload: z.infer<typeof PromptPayloadSchema>,
  options?: { onPhase1Done?: () => void },
) {
  // B169: serialise per-siteId, not globally. Follow-ups key on the concrete
  // siteId so two follow-ups for the SAME site still queue (Phase 1 version-
  // bump race protection). Init has no siteId yet and generates a collision-
  // free one in Phase 1, so each init gets a unique key and runs in parallel
  // instead of blocking — and crucially never blocks a follow-up on another
  // site. Mirrors build-runner.ts's per-site Map.
  const queueKey = payload.siteId ?? `__init__:${randomUUID()}`;

  // Vänta på pending prompt-build för EXAKT denna queueKey — andra sajter
  // (och parallella inits) kör samtidigt. Läs om Map:en efter varje await så
  // en follow-up som skrivit en ny entry medan vi väntade inte missas.
  while (promptInFlight.has(queueKey)) {
    try {
      await promptInFlight.get(queueKey);
    } catch {
      // Previous prompt for this site failed; still allow the next one to run.
    }
  }

  const promise = runPromptBuildOnce(payload, options);
  promptInFlight.set(queueKey, promise);
  try {
    return await promise;
  } finally {
    // Rensa entry:t bara om promise:n FORTFARANDE är den aktiva — så en
    // samtidig follow-up (som hunnit skriva en ny entry för samma siteId)
    // inte oavsiktligt nukas. Speglar build-runner.ts:s identity-guard.
    if (promptInFlight.get(queueKey) === promise) {
      promptInFlight.delete(queueKey);
    }
  }
}

/** Poll-intervall mot KV under en hostad NDJSON-stream. */
const HOSTED_POLL_INTERVAL_MS = 3_000;
/** Stream-budget under route:ns maxDuration (300 s) med marginal för avslut. */
const HOSTED_STREAM_BUDGET_MS = 280_000;

/**
 * Polla KV-statusen för ett hostat bygge tills done/failed eller tills
 * svarsbudgeten är slut (``null``). Delas av NDJSON-streamen och den synkrona
 * JSON-vägen så båda svarslägen väntar in samma sanning. ``onBuilding``
 * anropas (en gång) när sandboxen nått bygg-/upload-fasen — streamen använder
 * den för sitt ``building``-event.
 */
async function pollHostedRunUntilSettled(
  runId: string,
  options?: { onBuilding?: () => void },
): Promise<HostedBuildRunStatus | null> {
  const store = getKvStore();
  const deadline = Date.now() + HOSTED_STREAM_BUDGET_MS;
  let buildingSignalled = false;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, HOSTED_POLL_INTERVAL_MS));
    const status = await kvGetJson<HostedBuildRunStatus>(
      store,
      hostedRunKey(runId),
    );
    if (!status) continue;
    if (
      !buildingSignalled &&
      (status.phase === "building" || status.phase === "uploading")
    ) {
      buildingSignalled = true;
      options?.onBuilding?.();
    }
    if (status.phase === "done" || status.phase === "failed") {
      return status;
    }
  }
  return null;
}

/** Ärlig budget-slut-text: bygget i sandboxen fortsätter, klienten kan följa
 * status via den siteId-bundna status-routen (B196). */
function hostedBudgetExhaustedMessage(runId: string, siteId: string): string {
  return (
    `Bygget pågår fortfarande (runId ${runId}) men svarsbudgeten är slut. ` +
    `Följ status via GET /api/hosted-build/${runId}?siteId=${siteId} — ` +
    "previewen funkar när bygget är klart."
  );
}

/**
 * Commit 3 (svars-paritet): bygg det rika hostade followup-svaret ur det
 * ``result``-block sandboxen POST:ade in i KV-statusdoken. Speglar den lokala
 * ``runPromptBuildOnce``-kontraktsformen (version/briefSource/buildResult/
 * appliedCopyDirectives/changeSet/openClawDecision/bridge/conversation/
 * answerText) så prompt-builder.tsx + use-followup-build.ts + floating-chat.tsx
 * får samma fält hostat som lokalt. ``answerText`` genereras HÄR (återvinner
 * generateConversationAnswer/generateAppliedConfirmation) eftersom det kräver
 * OpenAI-anrop som inte hör hemma i sandboxen. ``changeSet`` är null i v1
 * (kräver bägge PI-snapshots hydrerade — dokumenterad begränsning, speglar
 * artefakt-pekarens senaste-version-gräns).
 */
async function buildHostedFollowupResponse(
  result: HostedFollowupResult,
  prompt: string,
  siteId: string,
  fallbackRunId: string,
  buildId: string | null,
): Promise<Record<string, unknown>> {
  // conversation-metadatan coerceas via samma reader som lokalt (läser
  // ``conversation``-blocket defensivt; fält-drift → null).
  const conversation = extractConversation({ conversation: result.conversation });

  if (result.engine === "answer-only") {
    // Answer-only: inget bygge, inget runId. answerText från chat-hjälpen
    // (ärlig no-key-fallback inuti generateConversationAnswer).
    const answerText = conversation
      ? await generateConversationAnswer(
          prompt,
          conversation,
          result.openClawDecision ?? {},
          siteId,
        )
      : null;
    return {
      runId: null,
      siteId,
      projectId: null,
      version: null,
      briefSource: null,
      buildStatus: null,
      buildResult: {},
      appliedCopyDirectives: [],
      changeSet: null,
      routerDecision: null,
      openClawDecision: result.openClawDecision ?? null,
      bridge: result.bridge ?? null,
      answerText,
      conversation,
      hosted: true,
    };
  }

  // applied (openclaw) eller legacy: ett bygge landade.
  let answerText: string | null = null;
  const bridge = result.bridge;
  if (
    result.engine === "openclaw" &&
    bridge &&
    (bridge as Record<string, unknown>).previewShouldRefresh === true
  ) {
    // Roll-bekräftelse efter en SYNLIGT applicerad ändring (samma grind som
    // lokalt). chain-fakta kommer från bridgen; null vid no-key/timeout.
    const chain =
      ((bridge as Record<string, unknown>).chain as Record<string, unknown>) ??
      {};
    answerText = await generateAppliedConfirmation(
      prompt,
      chain,
      conversation?.role ?? null,
    );
  }
  return {
    runId: result.runId ?? fallbackRunId,
    siteId,
    projectId: null,
    version: result.version,
    briefSource: null,
    buildStatus: result.buildStatus,
    buildResult: result.buildResult,
    appliedCopyDirectives: result.appliedCopyDirectives,
    changeSet: null,
    routerDecision: null,
    openClawDecision: result.openClawDecision,
    bridge: result.bridge,
    answerText,
    conversation,
    hosted: true,
    buildId,
  };
}

/**
 * Hostad prompt-väg (P2): bygget kör detached i en sandbox via
 * ``startHostedBuild``; status landar i KV. Två svarslägen, samma kontrakt
 * som den lokala vägen så prompt-builder.tsx fungerar oförändrad:
 *
 *   - NDJSON (Accept: application/x-ndjson): emitterar ``accepted`` (ny rad,
 *     ignoreras av dagens klient men bär runId för curl/framtida UI), sedan
 *     ``building`` när sandboxen nått bygg-fasen, sist ``done``/``error``.
 *     Tar bygget längre än stream-budgeten avslutas streamen ärligt med ett
 *     error-event som pekar på GET /api/hosted-build/<runId>?siteId=<siteId>
 *     — bygget i sandboxen fortsätter och pekaren sätts när det blir klart.
 *   - Synkron JSON: väntar in done/failed server-side via samma KV-pollning
 *     som streamen och svarar med det gamla synkrona kontraktet
 *     (``{ runId, siteId, buildStatus, ... }`` eller ``{ error }``).
 *     Review-fynd #284 (fynd 2): det tidigare omedelbara 202-svaret
 *     ``{ accepted, runId, ... }`` tolkades av icke-streamande klienter
 *     (floating-chat.tsx, use-followup-build.ts) som ett FÄRDIGT bygge —
 *     de läste runId + HTTP ok och rapporterade "klart"/refreshade preview
 *     medan sandboxen fortfarande byggde (eller var på väg att faila, B194).
 *     Vid budget-slut: ärligt fel (504) med status-route-hänvisning.
 *
 * Följdprompter hostat failar ärligt i sandboxen tills run-historiken
 * persisteras (P3, B194) — statusen i KV förklarar varför.
 */
async function runHostedPromptFlow(
  payload: z.infer<typeof PromptPayloadSchema>,
  wantsStream: boolean,
): Promise<Response> {
  // Init-läge saknar siteId (lokalt deriverar Phase 1 det ur prompten) —
  // hostat genererar vi det här så sandbox, blob-prefix och KV-pekare delar
  // nyckel från start.
  const siteId = payload.siteId ?? `site-${randomUUID().slice(0, 8)}`;

  let runId: string;
  try {
    ({ runId } = await startHostedBuild({
      siteId,
      prompt: payload.prompt,
      followup: payload.mode === "followup",
      // asset_set-forwarding hostat (task A:s hostade halva): samma
      // Zod-validerade payload som den lokala vägen; runnern sanerar
      // med samma sanitizedAssetSetIntent före env-injektionen.
      ...(payload.toolIntent ? { toolIntent: payload.toolIntent } : {}),
      // Commit 3 (request-paritet): baseRunId + markedSections trädas in i
      // sandboxen (tidigare tappades de trots att schemat validerar dem).
      // Runnern re-validerar/sanerar dem före env-injektionen (samma
      // defense-in-depth + delade sanitizedMarkedSections som lokala vägen).
      ...(payload.baseRunId ? { baseRunId: payload.baseRunId } : {}),
      ...(payload.markedSections?.length
        ? { markedSections: payload.markedSections }
        : {}),
    }));
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Okänt fel när det hostade bygget skulle startas.";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  if (!wantsStream) {
    // Det synkrona kontraktet bevaras hostat: vänta in done/failed via samma
    // KV-pollning som streamen i stället för att svara 202 direkt (se JSDoc
    // ovan — det omedelbara accepted-svaret lästes som ett färdigt bygge).
    try {
      const settled = await pollHostedRunUntilSettled(runId);
      if (settled?.phase === "done") {
        // Commit 3: rikt followup-svar när sandboxen POST:ade ett result-block
        // (followups); annars det tunna init-svaret (oförändrat).
        if (settled.result) {
          return NextResponse.json(
            await buildHostedFollowupResponse(
              settled.result,
              payload.prompt,
              siteId,
              runId,
              settled.buildId ?? null,
            ),
          );
        }
        return NextResponse.json({
          runId,
          siteId,
          projectId: null,
          version: null,
          briefSource: null,
          buildStatus: "ok",
          hosted: true,
          buildId: settled.buildId ?? null,
        });
      }
      if (settled?.phase === "failed") {
        return NextResponse.json(
          {
            error: settled.error ?? "Det hostade bygget misslyckades.",
            runId,
            siteId,
            hosted: true,
          },
          { status: 500 },
        );
      }
      return NextResponse.json(
        {
          error: hostedBudgetExhaustedMessage(runId, siteId),
          runId,
          siteId,
          hosted: true,
        },
        { status: 504 },
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Okänt fel under status-pollningen av det hostade bygget.";
      return NextResponse.json(
        { error: message, runId, siteId, hosted: true },
        { status: 500 },
      );
    }
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const enqueueLine = (line: Record<string, unknown>) => {
        controller.enqueue(encoder.encode(`${JSON.stringify(line)}\n`));
      };
      enqueueLine({ stage: "accepted", runId, siteId, hosted: true });
      try {
        const settled = await pollHostedRunUntilSettled(runId, {
          onBuilding: () => enqueueLine({ stage: "building" }),
        });
        if (settled?.phase === "done") {
          // Commit 3: rikt followup-svar (samma fält som lokala done-payloaden)
          // när result finns; annars tunt init-svar (oförändrat).
          if (settled.result) {
            enqueueLine({
              stage: "done",
              ...(await buildHostedFollowupResponse(
                settled.result,
                payload.prompt,
                siteId,
                runId,
                settled.buildId ?? null,
              )),
            });
            return;
          }
          enqueueLine({
            stage: "done",
            runId,
            siteId,
            projectId: null,
            version: null,
            briefSource: null,
            buildStatus: "ok",
            hosted: true,
            buildId: settled.buildId ?? null,
          });
          return;
        }
        if (settled?.phase === "failed") {
          enqueueLine({
            stage: "error",
            error: settled.error ?? "Det hostade bygget misslyckades.",
          });
          return;
        }
        enqueueLine({
          stage: "error",
          error: hostedBudgetExhaustedMessage(runId, siteId),
        });
      } catch (error) {
        enqueueLine({
          stage: "error",
          error:
            error instanceof Error
              ? error.message
              : "Okänt fel under status-pollningen av det hostade bygget.",
        });
      } finally {
        controller.close();
      }
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;
  const hosted = isHostedVercelRuntime();
  if (hosted) {
    // P2 (hostad byggväg) är bakom explicit opt-in: utan flaggan degraderar
    // routen ärligt som tidigare i stället för att halvfungera.
    if (process.env.VIEWSER_ENABLE_HOSTED_BUILD !== "1") {
      return hostedPythonRuntimeUnavailable("prompt-build");
    }
    // Publik deploy utan auth (operatörsbeslut 2026-06-10): bygget är den
    // dyraste endpointen (sandbox + LLM + npm install) — strama kvoter per IP.
    const limited = await enforceRateLimit(request, "prompt-build", {
      limit: 3,
      windowSeconds: 300,
    });
    if (limited) return limited;
  }

  let payload: z.infer<typeof PromptPayloadSchema>;
  try {
    const json = await request.json().catch(() => ({}));
    payload = PromptPayloadSchema.parse(json);
  } catch (error) {
    if (error instanceof z.ZodError) {
      // Client-side validation errors must surface as 400, not 500.
      // Returning 500 for "missing field" / "too long" muddies the
      // API contract and makes operator-side debugging harder.
      //
      // Inkludera ``path`` i meddelandet så operatören ser vilket
      // fält som failade. Zod 4:s default-message-rendering ger
      // texter som ``"Invalid input: expected 1"`` utan att nämna
      // fältet — vilket är obegripligt när felet kommer från en
      // nästad payload (t.ex. ``discovery.schemaVersion``). Med
      // path-prefix blir det ``"discovery.schemaVersion: Invalid
      // input: expected 1"`` vilket är åtgärdsbart.
      const issue = error.issues[0];
      const message = issue
        ? `${issue.path.length > 0 ? `${issue.path.join(".")}: ` : ""}${issue.message}`
        : "Ogiltig prompt-payload.";
      return NextResponse.json({ error: message }, { status: 400 });
    }
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  // B122-fix: när klienten signalerar `Accept: application/x-ndjson`
  // emitterar vi två NDJSON-rader istället för en synkron JSON:
  //   1. `{stage:"building"}` exakt när Phase 1 (prompt → Project Input)
  //      är klar, så PromptBuilder kan flippa stage på en RIKTIG signal
  //      istället för en gissad `setTimeout(1500)`.
  //   2. `{stage:"done", runId, siteId, ...}` när Phase 2 är klar.
  // Vid fel skickas `{stage:"error", error:"..."}` och streamen stängs.
  // Klienter som inte sätter Accept-headern får oförändrad synkron JSON
  // (zero impact på floating-chat.tsx + use-followup-build.ts).
  const acceptHeader = request.headers.get("accept") ?? "";
  const wantsStream = acceptHeader.includes("application/x-ndjson");

  if (hosted) {
    return runHostedPromptFlow(payload, wantsStream);
  }

  if (wantsStream) {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const enqueueLine = (line: Record<string, unknown>) => {
          controller.enqueue(encoder.encode(`${JSON.stringify(line)}\n`));
        };
        try {
          const result = await runPromptBuildSerially(payload, {
            onPhase1Done: () => {
              enqueueLine({ stage: "building" });
            },
          });
          enqueueLine({ stage: "done", ...result });
        } catch (error) {
          const message =
            error instanceof Error
              ? error.message
              : "Okänt fel vid prompt-anropet.";
          enqueueLine({ stage: "error", error: message });
        } finally {
          controller.close();
        }
      },
    });
    return new Response(stream, {
      status: 200,
      headers: {
        "Content-Type": "application/x-ndjson; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        // X-Accel-Buffering=no hindrar reverse proxies (om någon
        // tillkommer framför Next.js) från att buffra streamen och
        // kollapsa den till en synkron response — vi vill att klienten
        // ska se {stage:"building"} omedelbart efter Phase 1.
        "X-Accel-Buffering": "no",
      },
    });
  }

  try {
    return NextResponse.json(await runPromptBuildSerially(payload));
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
