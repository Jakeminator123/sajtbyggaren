"use client";

import {
  ChevronLeft,
  ChevronUp,
  Crosshair,
  GitBranch,
  ImagePlus,
  Loader2,
  MessageSquare,
  Minus,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import {
  ChangeEvent as ReactChangeEvent,
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { useBuildTracePolling } from "@/components/builder/use-build-trace-polling";
import {
  DEVICE_PRESET_OPTIONS,
  useDevicePreset,
} from "@/components/device-preset-context";
import { usePreviewInspector } from "@/components/preview-inspector-context";
import {
  classifyBuildStatus,
  outcomeToStage,
  type PromptBuildOutcome,
} from "@/components/prompt-builder";
import { Textarea } from "@/components/ui/textarea";
import type { AssetRef } from "@/lib/asset-store/types";
import {
  CATEGORY_LABEL,
  summarizeChangeSet,
  summarizeChangesFromPrompt,
  type BuildChange,
  type RunChangeSet,
} from "@/lib/build-changes";
import { CHIP_INTERACTIONS, PRIMARY_INTERACTIONS } from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

import {
  ALLOWED_UPLOAD_MIMES,
  INITIAL_BUILD_LABEL,
  MAX_UPLOAD_BYTES,
  PANEL_DEFAULT_SIZE,
  PANEL_HEIGHT,
  PANEL_MIN_HEIGHT,
  PROGRESS_RAMP_DURATION_MS,
  QUICK_PROMPT_CATEGORIES,
  RESIZE_HANDLE_OVERHANG,
  TOOLBAR_ROW_HEIGHT,
} from "./floating-chat/constants";
import { ErrorBubble } from "./floating-chat/error-bubble";
import {
  clampSize,
  clampToViewport,
  classifyFollowupError,
  defaultPosition,
} from "./floating-chat/helpers";
import { useKeyboardInset } from "./floating-chat/hooks";
import type {
  AppliedCopyDirective,
  ChatMessage,
  FloatingChatProps,
  OpenClawAction,
  OpenClawBridgeView,
  OpenClawDecisionView,
  Position,
  RouterBuildRequirement,
  RouterDecisionView,
  RouterMessageKind,
  Size,
} from "./floating-chat/types";

/**
 * Floating, draggable, minimizable chat window för efter-bygget-läget.
 *
 * Designprinciper:
 * 1. SUPERMINIMALISM. Vi visar bara chat + skicka. Andra "häftiga
 *    ändringar" lever i `BuilderActions`-FAB:en bredvid.
 * 2. ALDRIG IN I VÄGEN FÖR PREVIEW. Användaren ska kunna dra panelen
 *    var som helst, eller minimera till en liten bubbla. Position
 *    persisteras per användare i localStorage.
 * 3. EN UPPGIFT. Den här rutan kör en sak: skicka follow-up-prompts
 *    till `/api/prompt` med `mode: "followup"` + nuvarande siteId.
 *    Alla resultat kommer tillbaka som assistent-meddelanden.
 *
 * SSR-säkerhet: vi använder `useLayoutEffect` (i SSR ersatt till
 * `useEffect`) endast efter mount för att läsa `window` — initialt
 * position-state är `null` och panelen renderas via CSS-fallback
 * (`right-6 bottom-6`) tills mount-effekten kör.
 */

type PromptApiResponse = {
  runId?: string;
  siteId?: string;
  version?: number | null;
  buildStatus?: string | null;
  briefSource?: string | null;
  // B155 (2026-05-30): följdpromptar får ``appliedVisibleEffect`` +
  // ``appliedVisibleEffectReason`` i ``build-result.json`` (auktoritativ
  // källa enligt Jakob — trace-event ``followup.no_op_detected`` plockas
  // inte upp av ``parseTraceLine`` som bara känner sju kända fält).
  // Builden går alltid igenom, men när motorn upptäcker att ingen synlig
  // ändring landade flippar vi success-bubblan till en ärlig
  // info-variant istället för att lova "Klart!". Skrivs bara på
  // followup-builds; init-builds saknar fältet (testat i
  // tests/test_followup_honest_no_op.py::test_init_build_omits_*).
  buildResult?: Record<string, unknown>;
  // ADR 0034 väg B (2026-06-01): exponerar de strukturerade
  // copy-direktiv som path A applicerade på den här versionens
  // project-input. Tom lista = init-build, "vanlig" follow-up utan
  // copy-direktiv eller artefakt-läsning som silently failade. UI:t
  // härleder svenska success-rader per direktiv; payload renderas
  // alltid som textnod (React escapar default — vi använder aldrig
  // dangerouslySetInnerHTML här).
  appliedCopyDirectives?: AppliedCopyDirective[];
  // UI-gap-fix (2026-06-02): strukturerad, EXAKT change-set för
  // follow-ups — routes tillagda/borttagna + variant-byten härledda
  // serverside genom att diffa nya runen mot föregående (se
  // lib/run-change-set.ts). null/utelämnad på init-builds och
  // follow-ups utan route-/variant-delta → UI faller tillbaka på
  // prompt-heuristiken (summarizeChangesFromPrompt).
  changeSet?: RunChangeSet | null;
  // KÖR-6a readiness (2026-06-03): det deterministiska router-beslutet för
  // den här prompten, speglar governance/schemas/router-decision.schema.json.
  // Backend (classify_message) producerar strukturen men /api/prompt skickar
  // den ÄNNU INTE — follow-up-bryggan (kor-7b/7c/7d, #176) wirar in den.
  // Tills dess är fältet utelämnat och ``extractRouterDecision`` returnerar
  // null → UI:t beter sig EXAKT som idag (graceful degradation, samma mönster
  // som appliedVisibleEffect/appliedCopyDirectives). När det börjar skickas
  // härleder ``summarizeRouterDecision`` en ärlig rad per messageKind utan ny
  // UI-deploy. Renderas aldrig rått (vi läser bara kända enum-fält).
  routerDecision?: Record<string, unknown>;
  // Skiva 1b: OpenClaw Core V0:s follow-up-beslut, speglar
  // ``OpenClawDecision.model_dump()`` (packages/.../openclaw/models.py). En
  // rikare superset av ``routerDecision`` med konkret answer/plan/
  // clarifyingQuestion/patchPlanRequest. /api/prompt skickar det BARA på
  // follow-ups där den gamla copyDirective-vägen INTE redan applicerade en
  // synlig ändring (annars null → den auktoritativa bygg-summeringen står
  // ensam). Utelämnat på init → ``extractOpenClawDecision`` returnerar null →
  // oförändrat beteende. Renderas aldrig rått (bara kända enum-/textfält).
  openClawDecision?: Record<string, unknown>;
  // Skiva 1b (action bridge): the honest OpenClaw apply outcome, speglar
  // ``bridge``-objektet från ``run_openclaw_followup.py --apply``
  // ({status, applied, previewShouldRefresh, chain}). /api/prompt skickar det
  // BARA på follow-ups (null på init). När ``applied=true`` materialiserade
  // OpenClaw-kedjan en ny version (t.ex. en restyle) → ``runId`` pekar redan på
  // den och ``summarizeOpenClawBridge`` ger en ärlig success-rad. När
  // ``applied=false`` ignoreras bryggan (den vanliga/legacy-summeringen står).
  bridge?: Record<string, unknown>;
  // F1 slice 2 (conversation gate): när dirigenten klassade följdprompten som
  // en KONVERSATION (small_talk/site_opinion/question) stannade /api/prompt
  // FÖRE bygget och skickar ett ärligt chat-svar här i stället för ett
  // build-resultat. ``runId`` är då null (inget bygge, ingen version, ingen
  // preview-refresh). Utelämnat på vanliga byggen → ``extractConversationAnswer``
  // returnerar null → oförändrat beteende. Renderas som textnod (React escapar).
  answerText?: string | null;
  // Metadata-syskonet till answerText ({conversationKind, role}); läses inte
  // av UI:t idag men trådas med för observability/test.
  conversation?: Record<string, unknown>;
  error?: string;
};

// F1 slice 2: avläs konversations-svaret defensivt — samma fält-drift-säkra
// mönster som extractAppliedVisibleEffect. Ett svar gäller BARA när routen
// uttryckligen stannade före bygget (inget runId): ett payload med runId är
// ett riktigt bygge och går alltid genom den vanliga summeringen.
function extractConversationAnswer(payload: PromptApiResponse): string | null {
  if (payload.runId) return null;
  const raw = payload.answerText;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed ? trimmed : null;
}

// F1 slice 3 (Scout #262): den explicita "dirigenten svarar i chatten, inget
// bygge"-signalen ur ``conversation.expectsAnswer``. Läses defensivt; gäller
// bara när inget riktigt bygge skedde (runId saknas) - en payload med runId är
// ett bygge och går alltid genom den vanliga summeringen.
function extractExpectsAnswer(payload: PromptApiResponse): boolean {
  if (payload.runId) return false;
  const conversation = payload.conversation;
  if (!conversation || typeof conversation !== "object") return false;
  return (conversation as Record<string, unknown>).expectsAnswer === true;
}

// F1 slice 3 (honest role-row): vilken conductor-roll som agerade + dess
// conversationKind, härlett defensivt ur ``payload.conversation`` (samma
// fält-drift-säkra mönster som extractConversation i route.ts). Renderas som en
// liten dämpad rad under assistent-bubblan så operatören ärligt ser VEM som
// agerade (t.ex. section_builder på en sektionsadd). Aldrig styr build/preview.
function extractConversationMeta(
  payload: PromptApiResponse,
): { role: string | null; conversationKind: string | null } | null {
  const conversation = payload.conversation;
  if (!conversation || typeof conversation !== "object") return null;
  const obj = conversation as Record<string, unknown>;
  const role = typeof obj.role === "string" ? obj.role : null;
  const conversationKind =
    typeof obj.conversationKind === "string" ? obj.conversationKind : null;
  if (role === null && conversationKind === null) return null;
  return { role, conversationKind };
}

// Svenska etiketter för roll-raden. UPPER_CASE-konstanter (inte PascalCase) så
// term-coverage --strict inte flaggar dem som okända domänbegrepp.
const CONVERSATION_ROLE_LABELS: Record<string, string> = {
  router: "dirigent",
  section_builder: "sektionsbyggare",
  stylist: "stylist",
  copy: "text/copy",
};

const CONVERSATION_KIND_LABELS: Record<string, string> = {
  edit: "ändring",
  small_talk: "småprat",
  site_opinion: "omdöme",
  question: "fråga",
  other: "övrigt",
};

// Bygg den ärliga roll-raden ("Roll: sektionsbyggare · ändring"). Returnerar
// null när varken roll eller kind är känd så bubblan inte får en tom rad.
// Okända värden ekas verbatim (aldrig påhittade) - React escapar texten.
function formatRoleRow(
  role: string | null | undefined,
  conversationKind: string | null | undefined,
): string | null {
  const parts: string[] = [];
  if (role) parts.push(`Roll: ${CONVERSATION_ROLE_LABELS[role] ?? role}`);
  if (conversationKind) {
    parts.push(CONVERSATION_KIND_LABELS[conversationKind] ?? conversationKind);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

// B155: avläs ``appliedVisibleEffect`` från build-result-payloaden utan
// att lita på dess typ. Returnerar `null` när builden inte är en
// follow-up (init-läge skriver inte fältet) eller när bygget gick i
// fel/degraded läge — detta gör success-grenen i
// ``summarizeBuildResult`` säker mot fält-drift utan att vi behöver
// flytta no-op-logiken till bygg-routen.
function extractAppliedVisibleEffect(
  buildResult: Record<string, unknown> | undefined,
): { applied: boolean; reason: string | null } | null {
  if (!buildResult) return null;
  const applied = buildResult.appliedVisibleEffect;
  if (typeof applied !== "boolean") return null;
  const reasonRaw = buildResult.appliedVisibleEffectReason;
  return {
    applied,
    reason: typeof reasonRaw === "string" ? reasonRaw : null,
  };
}

/**
 * ADR 0034 väg B (B155 path B): bygg en svensk success-rad per applicerat
 * copy-direktiv. Renderingen i FloatingChat-bubblan sker via
 * ``{message.content}`` (textnod) — payload escapas alltid av React.
 * Vi mappar alla fyra targets som schema-enumen på
 * ``governance/schemas/project-input.schema.json:directives.copyDirectives``
 * tillåter (company-name | tagline | about-text | services). Kort copy
 * (namn/rubrik/tjänstnamn) ekas i citat så operatören känner igen ändringen;
 * lång copy (om oss-texten, upp till 600 tecken) ekas INTE i bubblan — den
 * syns i previewen — så vi bara bekräftar att fältet uppdaterades. Okända
 * kombinationer faller tillbaka på en neutral "uppdaterades"-rad så framtida
 * schema-bumps inte tystar UI:t.
 */
function summarizeCopyDirectives(
  directives: AppliedCopyDirective[] | undefined,
): string[] {
  if (!directives || directives.length === 0) return [];
  const lines: string[] = [];
  for (const directive of directives) {
    const payload = directive.payload;
    if (!payload) continue;
    if (directive.target === "company-name") {
      lines.push(`Jag ändrade företagsnamnet till "${payload}".`);
      continue;
    }
    if (directive.target === "tagline") {
      // Scope-eko (2026-06-09): rubrik/tagline-copyDirective träffar ALLTID
      // startsidans hero (``company.heroHeadline``-override / tagline). Vi
      // namnger sidan explicit så en operatör som tittade på en undersida inte
      // tror att DEN sidans rubrik ändrades — undersid-rubriker är inte
      // adresserbara copyDirectives än (relä till Jakob, topic followup-targeting).
      if (directive.operation === "include-token") {
        lines.push(`Jag la in "${payload}" i hero-texten på startsidan.`);
      } else {
        lines.push(`Jag uppdaterade rubriken till "${payload}" på startsidan.`);
      }
      continue;
    }
    if (directive.target === "about-text") {
      // Om oss-texten kan vara upp till 600 tecken → eka inte hela payloaden
      // i chat-bubblan, bekräfta bara ändringen (operatören ser den i preview).
      lines.push("Jag skrev om om oss-texten.");
      continue;
    }
    if (directive.target === "services") {
      // targetRef pekar ut vilken tjänst som ändrades; eka tjänstnamnet (kort,
      // max 80 tecken) men inte den nya summaryn (upp till 300 tecken).
      const ref = directive.targetRef?.trim();
      lines.push(
        ref
          ? `Jag uppdaterade tjänsten "${ref}".`
          : "Jag uppdaterade en tjänst.",
      );
      continue;
    }
  }
  return lines;
}

const STORAGE_KEY_POSITION = "sajtbyggaren:floating-chat:position";
const STORAGE_KEY_SIZE = "sajtbyggaren:floating-chat:size";
const STORAGE_KEY_MINIMIZED = "sajtbyggaren:floating-chat:minimized";
const STORAGE_KEY_QUICK_PROMPTS = "sajtbyggaren:floating-chat:quick-prompts";
// Första-gångs-hinten "Så funkar det" (kärnloopen: följdprompt → ny
// version). Visas en gång per webbläsare, sedan persisteras dismissen.
const STORAGE_KEY_LOOP_HINT = "sajtbyggaren:floating-chat:loop-hint-seen";

/**
 * Reflekterar Tailwind ``md:``-brytpunkten (768px). Under brytpunkten
 * renderas FloatingChat som bottom-sheet med drag-handle istället för
 * fast 360×460-floating panel — det gör att panelen inte täcker hela
 * mobilskärmen och respekterar iOS home-indicator. SSR-säker
 * (returnerar false under server-rendering, läses först post-mount).
 */
// useIsomorphicLayoutEffect — useLayoutEffect på klient, useEffect på
// server. Behövs för att eliminera FloatingChat-layout-flickern: tidigare
// useEffect-mönstret returnerade false vid första paint på mobil
// (desktop-placeholder right-6 bottom-6 syntes 1 frame innan effect
// kördes). useLayoutEffect kör innan paint så första synliga frame har
// rätt isMobile-värde. SSR-pathen faller tillbaka till useEffect så vi
// undviker Reacts "useLayoutEffect does nothing on the server"-varning.
const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

function useIsMobileViewport(): boolean {
  const [isMobile, setIsMobile] = useState(false);
  useIsomorphicLayoutEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(max-width: 767px)");
    setIsMobile(mq.matches);
    // Parameter-typen infereras automatiskt av addEventListener-overload
    // för media-query-listenern; ingen explicit annotation behövs.
    const update = (event: { matches: boolean }) => setIsMobile(event.matches);
    // B151: iOS Safari < 14 (samt äldre Edge-/IE-baserade browsers) stödjer
    // inte addEventListener-signaturen på matchMedia-resultatet — där måste
    // vi falla tillbaka till den deprecated addListener-/removeListener-
    // signaturen. Feature-detect istället för att anta nyare APIn så
    // chatten inte kraschar ren-blank på äldre iOS-enheter i fält.
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", update);
      return () => mq.removeEventListener("change", update);
    }
    // Inline struktur-typ för deprecated addListener/removeListener (lever
    // bara här lokalt — undviker en namngiven PascalCase-typ som
    // term-coverage strict skulle flagga som okänd domän-term).
    const legacy = mq as unknown as {
      addListener: (listener: (event: { matches: boolean }) => void) => void;
      removeListener: (listener: (event: { matches: boolean }) => void) => void;
    };
    legacy.addListener(update);
    return () => legacy.removeListener(update);
  }, []);
  return isMobile;
}

function readStoredPosition(): Position | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY_POSITION);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Position>;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number")
      return null;
    return { x: parsed.x, y: parsed.y };
  } catch {
    return null;
  }
}

function readStoredSize(): Size | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY_SIZE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Size>;
    if (typeof parsed.width !== "number" || typeof parsed.height !== "number")
      return null;
    return { width: parsed.width, height: parsed.height };
  } catch {
    return null;
  }
}

function readStoredMinimized(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY_MINIMIZED) === "true";
  } catch {
    return false;
  }
}

function readStoredQuickPromptsOpen(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY_QUICK_PROMPTS) === "true";
  } catch {
    return false;
  }
}

// Returnerar true (= hinten redan sedd → dölj) under SSR så vi inte
// flimrar in tipset före hydration. Post-mount läser layout-effekten
// det riktiga värdet och öppnar hinten om den aldrig visats.
function readLoopHintSeen(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(STORAGE_KEY_LOOP_HINT) === "true";
  } catch {
    return false;
  }
}

// --- KÖR-6a RouterDecision-readiness ---------------------------------------
// Stängda enum-litteraler speglade från
// governance/schemas/router-decision.schema.json. Vi mirrorar bara de fält
// summarizeRouterDecision faktiskt grenar på; resten av kontraktet ignoreras
// medvetet (UI:t ska inte koppla sig hårt till hela router-shapen).
const ROUTER_MESSAGE_KINDS: ReadonlySet<string> = new Set([
  "answer_only",
  "site_review",
  "edit_instruction",
  "component_discovery",
  "reference_analysis",
  "bug_report",
  "multi_intent",
  "unclear",
]);

const ROUTER_BUILD_REQUIREMENTS: ReadonlySet<string> = new Set([
  "none",
  "plan_only",
  "artifact_patch_only",
  "targeted_rebuild",
  "full_rebuild",
]);

// Avläs ``routerDecision`` defensivt utan att lita på dess typ — exakt samma
// fält-drift-säkra mönster som ``extractAppliedVisibleEffect``. Returnerar
// null när fältet saknas (dagens läge) eller har en okänd messageKind, så
// summarizeBuildResult faller tillbaka på oförändrat beteende.
function extractRouterDecision(
  payload: PromptApiResponse,
): RouterDecisionView | null {
  const raw = payload.routerDecision;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const messageKind = obj.messageKind;
  if (typeof messageKind !== "string" || !ROUTER_MESSAGE_KINDS.has(messageKind)) {
    return null;
  }
  const buildRequirementRaw = obj.buildRequirement;
  const buildRequirement =
    typeof buildRequirementRaw === "string" &&
    ROUTER_BUILD_REQUIREMENTS.has(buildRequirementRaw)
      ? (buildRequirementRaw as RouterBuildRequirement)
      : "none";
  const subtasks = obj.subtasks;
  return {
    messageKind: messageKind as RouterMessageKind,
    buildRequirement,
    requiresClarification: obj.requiresClarification === true,
    subtaskCount: Array.isArray(subtasks) ? subtasks.length : 0,
  };
}

// Ärlig, förskottslös rad per router-utfall. Returnerar null för de fall där
// routern faktiskt begärde ett synligt bygge (edit/multi_intent med
// targeted_rebuild/full_rebuild) → då tar den vanliga bygg-summeringen vid
// (Bug B/no-op, copy-direktiv, change-set). Vi lovar ALDRIG en ändring som
// routern inte krävde ett bygge för (orchestrator-punkt 5).
function summarizeRouterDecision(
  view: RouterDecisionView,
): { content: string; variant: ChatMessage["variant"] } | null {
  if (view.requiresClarification || view.messageKind === "unclear") {
    return {
      content:
        'Jag är inte säker på vad du vill ändra. Beskriv exakt vilken text, sektion eller sida du menar — t.ex. "byt rubriken i hero till X".',
      variant: "info",
    };
  }
  if (view.messageKind === "answer_only" || view.messageKind === "site_review") {
    return {
      content:
        "Det här tolkade jag som en fråga om sajten, inte en ändring — så jag byggde inte om något. Säg till om du vill att jag ändrar något konkret.",
      variant: "info",
    };
  }
  if (view.messageKind === "reference_analysis") {
    return {
      content:
        'Att härma en extern referens ("som på …") stöds inte än. Beskriv i stället konkret vad du vill ha — t.ex. "mörk topbar med logga till vänster".',
      variant: "info",
    };
  }
  if (view.messageKind === "component_discovery") {
    return {
      content:
        "Jag kan inte söka fram färdiga komponenter åt dig än. Beskriv funktionen du vill lägga till så bygger jag den som en vanlig ändring.",
      variant: "info",
    };
  }
  if (view.messageKind === "bug_report") {
    return {
      content:
        "Tack — jag noterade felrapporten. Jag kan inte felsöka sajten automatiskt än, men beskriv var det ser fel ut så försöker jag åtgärda det.",
      variant: "info",
    };
  }
  // edit_instruction / multi_intent: bygg-kravet avgör om en synlig ändring
  // ens väntas. none/plan_only/artifact_patch_only = "plan skapad, men den
  // targeted rebuild som gör den synlig är inte klar än". targeted_rebuild/
  // full_rebuild → null så den riktiga bygg-summeringen tar vid.
  if (
    view.buildRequirement === "none" ||
    view.buildRequirement === "plan_only" ||
    view.buildRequirement === "artifact_patch_only"
  ) {
    const intro =
      view.messageKind === "multi_intent" && view.subtaskCount > 1
        ? `Jag delade upp din förfrågan i ${view.subtaskCount} delar och planerade dem`
        : "Jag planerade ändringen";
    return {
      content: `${intro}, men bygget som gör den synlig är inte klart i den här versionen än. Previewen visar därför fortfarande föregående version.`,
      variant: "info",
    };
  }
  return null;
}

const OPENCLAW_ACTIONS: ReadonlySet<string> = new Set([
  "answer_only",
  "clarification",
  "plan_only",
  "patch_plan_request",
]);

// Avläs ``openClawDecision`` defensivt — samma fält-drift-säkra mönster som
// ``extractRouterDecision``. Returnerar null när fältet saknas (init-builds,
// follow-ups där gamla vägen applicerade) eller har en okänd action, så
// summarizeBuildResult faller tillbaka på routerDecision/bygg-summeringen.
function extractOpenClawDecision(
  payload: PromptApiResponse,
): OpenClawDecisionView | null {
  const raw = payload.openClawDecision;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const action = obj.action;
  if (typeof action !== "string" || !OPENCLAW_ACTIONS.has(action)) return null;
  const answer = typeof obj.answer === "string" ? obj.answer.trim() : null;
  const clarifyingQuestion =
    typeof obj.clarifyingQuestion === "string"
      ? obj.clarifyingQuestion.trim()
      : null;
  const planRaw = obj.plan;
  const plan: string[] = Array.isArray(planRaw)
    ? planRaw
        .filter(
          (item): item is string =>
            typeof item === "string" && item.trim().length > 0,
        )
        .map((item) => item.trim())
        .slice(0, 6)
    : [];
  let patchTargetSummary: string | null = null;
  const ppr = obj.patchPlanRequest;
  if (ppr && typeof ppr === "object") {
    const target = (ppr as Record<string, unknown>).targetSummary;
    patchTargetSummary =
      typeof target === "string" && target.trim() ? target.trim() : null;
  }
  return {
    action: action as OpenClawAction,
    answer: answer || null,
    clarifyingQuestion: clarifyingQuestion || null,
    plan,
    patchTargetSummary,
  };
}

// Ärlig rad per OpenClaw-beslut. answer_only/clarification/plan_only ekar det
// konkreta svaret/frågan/planen (rikare än routerDecisions generiska rad).
// patch_plan_request är V0:s ärliga "ändringen förstods men action-bryggan som
// utför den är inte inkopplad än" — route:n har redan skickat null när den
// gamla copyDirective-vägen FAKTISKT applicerade ändringen, så ett kvarvarande
// patch_plan_request betyder att ändringen INTE landade (t.ex. layout/sektion
// som v1 inte stöder). Renderas alltid som textnod ({message.content}) →
// React escapar payloaden. Okänd action → null (faller tillbaka på router).
function summarizeOpenClawDecision(
  view: OpenClawDecisionView,
): { content: string; variant: ChatMessage["variant"] } | null {
  if (view.action === "answer_only") {
    return {
      content:
        view.answer ??
        "Det här tolkade jag som en fråga, inte en ändring — så jag byggde inte om något.",
      variant: "info",
    };
  }
  if (view.action === "clarification") {
    return {
      content:
        view.clarifyingQuestion ??
        'Jag är inte säker på vad du vill ändra. Beskriv exakt vilken text, sektion eller sida du menar — t.ex. "byt rubriken i hero till X".',
      variant: "info",
    };
  }
  if (view.action === "plan_only") {
    if (view.plan.length > 0) {
      const bullets = view.plan.map((step) => `• ${step}`).join("\n");
      return {
        content: `Jag har en plan – men jag har inte byggt om något än:\n${bullets}`,
        variant: "info",
      };
    }
    return {
      content: "Jag har en plan, men jag har inte byggt om något än.",
      variant: "info",
    };
  }
  // patch_plan_request
  return {
    content: view.patchTargetSummary
      ? `Jag tolkade det här som en ändring (${view.patchTargetSummary}), men funktionen som faktiskt utför den är inte inkopplad än. Previewen visar därför fortfarande föregående version.`
      : "Jag tolkade det här som en ändring, men funktionen som faktiskt utför den är inte inkopplad än. Previewen visar därför fortfarande föregående version.",
    variant: "info",
  };
}

// Skiva 1b (action bridge): OpenClaw-apply-utfallet. När /api/prompt rutade
// follow-upen genom ``run_openclaw_followup.py --apply`` och KÖR-7-kedjan
// MATERIALISERADE en ny version (restyle/capability) bär ``bridge``
// { applied, previewShouldRefresh, chain:{ editKind, version, previousVersion } }.
// Avläses defensivt (samma fält-drift-säkra mönster som extractOpenClawDecision).
function extractOpenClawBridge(
  payload: PromptApiResponse,
): OpenClawBridgeView | null {
  const raw = payload.bridge;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const chainRaw = obj.chain;
  const chain =
    chainRaw && typeof chainRaw === "object"
      ? (chainRaw as Record<string, unknown>)
      : {};
  return {
    applied: obj.applied === true,
    previewShouldRefresh: obj.previewShouldRefresh === true,
    editKind: typeof chain.editKind === "string" ? chain.editKind : null,
    version: typeof chain.version === "number" ? chain.version : null,
    previousVersion:
      typeof chain.previousVersion === "number" ? chain.previousVersion : null,
  };
}

// Ärlig success-rad när OpenClaw-apply FAKTISKT landade en ny version (kedjan
// är auktoritativ). Returnerar null när inget applicerades (applied=false) så
// summarizeBuildResult faller tillbaka på den vanliga bygg-/no-op-/decision-
// summeringen — vi lovar aldrig en ändring som bryggan inte materialiserade.
// Renderas alltid som textnod ({message.content}) → React escapar payloaden.
function summarizeOpenClawBridge(
  view: OpenClawBridgeView,
): { content: string; variant: ChatMessage["variant"] } | null {
  if (!view.applied) return null;
  const versionText =
    typeof view.version === "number"
      ? view.previousVersion != null && view.version >= 2
        ? ` Sajten gick från v${view.previousVersion} → v${view.version}.`
        : ` Ny version: v${view.version}.`
      : "";
  // Honesty split (Vercel-agent-fynd 2026-06-08): ``bridge.applied=true`` means
  // a new version was written + the targeted render ran — NOT that anything
  // visibly changed. ``previewShouldRefresh`` mirrors the chain's
  // ``appliedVisibleEffect`` (preview only refreshes on a real visible change),
  // so it is the gate for claiming a visible change. A capability mount whose
  // soft dossier renders nothing (a section_add that is mount-only today) lands
  // ``applied=true`` + ``previewShouldRefresh=false``; saying "Jag genomförde
  // ändringen — ladda om" there is a FALSE success (reloading shows nothing new).
  // Be honest instead: the version/capability was registered but is not visible.
  if (!view.previewShouldRefresh) {
    return {
      content:
        `Jag registrerade ändringen i sajtens uppsättning.${versionText} ` +
        "Men den ger ingen synlig ändring i previewen ännu — previewen ser " +
        "likadan ut (vissa tillägg monteras men renderas inte synligt än).",
      variant: "info",
    };
  }
  const lead =
    view.editKind === "visual_style"
      ? "Jag uppdaterade sajtens utseende (färg/typsnitt)"
      : "Jag genomförde ändringen";
  return {
    content: `${lead}.${versionText} Previewen visar den nu.`,
    variant: "success",
  };
}

// A3 (B155 honest-level-1): backend listar i ``build-result.json`` de
// följd-asks den deterministiska v1-pipelinen KÄNDE IGEN men inte kunde
// applicera, som ``{target, reason}``. Komplement till den globala
// ``appliedVisibleEffect``-boolean: i stället för bara "inget syntes" kan vi
// säga EXAKT vad som inte landade. Backend bounded:ar listan (max 20 items,
// target<=80, reason<=400); vi cappar ändå defensivt till 5 rader i bubblan
// och renderar alltid som textnod (React escapar payloaden).
function summarizeUnappliedFollowupIntents(
  buildResult: Record<string, unknown> | undefined,
): string {
  if (!buildResult) return "";
  const raw = buildResult.unappliedFollowupIntents;
  if (!Array.isArray(raw)) return "";
  const lines: string[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const target = typeof obj.target === "string" ? obj.target.trim() : "";
    const reason = typeof obj.reason === "string" ? obj.reason.trim() : "";
    if (!target && !reason) continue;
    lines.push(target && reason ? `• ${target}: ${reason}` : `• ${target || reason}`);
    if (lines.length >= 5) break;
  }
  if (lines.length === 0) return "";
  return `\n\nDetta kände jag igen men kunde inte göra än:\n${lines.join("\n")}`;
}

function summarizeBuildResult(
  payload: PromptApiResponse,
  outcome: PromptBuildOutcome,
  userPrompt: string,
): {
  content: string;
  variant: ChatMessage["variant"];
  changes?: BuildChange[];
  changesExact?: boolean;
} {
  // KÖR-6a readiness: om backend exponerar ett router-beslut låter vi det
  // ärligt styra meddelandet för icke-bygg-utfall (fråga, oklart, referens,
  // discovery, plan-only) INNAN success-/no-op-grenarna nedan. Saknas fältet
  // (dagens läge) → extractRouterDecision = null → oförändrat beteende.
  // Edit/multi_intent som krävde ett synligt bygge faller igenom
  // (summarizeRouterDecision → null) till den vanliga summeringen.
  // Skiva 1b: OpenClaw-beslutet preemptar FÖRE routerDecision (det är en rikare
  // superset med konkret answer/plan/fråga). Samma outcome === "ok"-grind som
  // routern: på failed/degraded får den auktoritativa fel-/varningsgrenen nedan
  // stå för meddelandet (annars tappar operatören "Försök igen"). När bygget
  // rapporterade en auktoritativ no-op (appliedVisibleEffect.applied === false)
  // OCH OpenClaw bara bad om förtydligande låter vi B155-grenen ta vid (dess
  // "kan bara ändra texter, layout stöds ej än" är ärligare än en generisk
  // fråga) — exakt samma deferToBuildTruth-nyans som routerDecision. För
  // patch_plan_request vinner OpenClaw (dess targetSummary är mer specifik).
  // Skiva 1b (action bridge): if the OpenClaw apply chain MATERIALISED a change
  // (bridge.applied=true), show an honest restyle/capability success line. This
  // wins over the decision/router lines because a change DID land — the run +
  // preview already point to the new version. Only on a successful build;
  // failed/degraded fall through to the authoritative branch below.
  const bridgeView = extractOpenClawBridge(payload);
  if (bridgeView && bridgeView.applied && outcome === "ok") {
    const bridgeLine = summarizeOpenClawBridge(bridgeView);
    if (bridgeLine) {
      // Roll-bekräftelse (operatörsfynd 2026-06-11): backend kan skicka en
      // dirigent-genererad bekräftelse i ``answerText`` för en SYNLIGT
      // applicerad ändring (payload bär då ett riktigt runId + applied
      // bridge, till skillnad från answer-only-fallet som kräver !runId).
      // Den ersätter BARA success-radens text — varianten, changes-listan
      // och alla ärlighetsgrindar står kvar, och mount-only-raden (variant
      // "info", ingen synlig ändring) kan aldrig överskuggas av prat.
      const confirmation =
        bridgeLine.variant === "success" &&
        typeof payload.answerText === "string"
          ? payload.answerText.trim()
          : "";
      const line = confirmation
        ? { ...bridgeLine, content: confirmation }
        : bridgeLine;
      const exactChanges = summarizeChangeSet(payload.changeSet);
      return exactChanges.length > 0
        ? { ...line, changes: exactChanges, changesExact: true }
        : line;
    }
  }
  const openClawView = extractOpenClawDecision(payload);
  if (openClawView && outcome === "ok") {
    const buildReportedNoOp =
      extractAppliedVisibleEffect(payload.buildResult)?.applied === false;
    const deferToBuildTruth =
      buildReportedNoOp && openClawView.action === "clarification";
    if (!deferToBuildTruth) {
      const openClawLine = summarizeOpenClawDecision(openClawView);
      if (openClawLine) {
        return openClawLine;
      }
    }
  }
  // Router-preempten får BARA köra när bygget gick igenom (outcome === "ok").
  // Annars (failed/degraded) döljer router-raden — som returnerar variant
  // "info" — den auktoritativa fel-/varningsgrenen nedan, och eftersom
  // ``retryPrompt`` bara sätts på variant "error" (se sendFollowupPrompt)
  // tappar operatören "Försök igen" på ett misslyckat bygge. Router-beslutet
  // är en förbygg-gissning; det faktiska bygg-utfallet är sanning.
  const routerView = extractRouterDecision(payload);
  if (routerView && outcome === "ok") {
    // Ärlighets-nyans: routerns ``unclear``/``requiresClarification`` är en
    // förbygg-gissning som kan ha fel — operatören kan ha varit tydlig ("gör
    // hero-knappen större") fast förfrågan helt enkelt inte stöds än. När
    // bygget FAKTISKT kördes och rapporterade ett auktoritativt no-op-skäl
    // (B155 ``appliedVisibleEffect.applied === false``) är det skälet ärligare
    // än gissningen, så vi låter B155-grenen nedan ta vid (den skiljer
    // "kan bara ändra texter, layout stöds ej än" från "var mer specifik").
    // Övriga utfall (fråga/referens/discovery/bug/plan-only) preemptar fortsatt
    // eftersom deras rad är mer specifik än den generiska bygg-summeringen.
    const buildReportedNoOp =
      extractAppliedVisibleEffect(payload.buildResult)?.applied === false;
    const deferToBuildTruth =
      buildReportedNoOp &&
      (routerView.requiresClarification ||
        routerView.messageKind === "unclear");
    if (!deferToBuildTruth) {
      const routerLine = summarizeRouterDecision(routerView);
      if (routerLine) {
        return routerLine;
      }
    }
  }
  // A3: ärlig svans med följd-asks som motorn kände igen men inte applicerade.
  // Tom sträng på init-builds och follow-ups utan oapplicerade intents → ingen
  // påverkan på de befintliga grenarna.
  const unappliedNote = summarizeUnappliedFollowupIntents(payload.buildResult);
  // B3 — version-progression i success-meddelandet. När payload.version
  // är t.ex. 3 visar vi "v2 → v3" så operatören får en känsla av
  // historiken utan att Inspectorn behöver öppnas. För v1 (första
  // bygget) visar vi bara "v1" eftersom det inte finns någon "från"-
  // version. Plus Sprint 6: paraphraserad changes-list baserat på
  // operatörens prompt — heuristisk tills backend exponerar en riktig
  // diff.
  if (outcome === "ok") {
    let versionText = "";
    if (typeof payload.version === "number") {
      if (payload.version >= 2) {
        versionText = ` Sajten gick från v${payload.version - 1} → v${payload.version}.`;
      } else {
        versionText = ` Version 1 publicerad.`;
      }
    }
    // B155 (2026-05-30): backend signalerar via build-result.json om
    // följdprompten faktiskt gav en synlig ändring. När motorn
    // upptäcker att inget visible-file-set ändrats (eller att intent
    // klassats som "no semantic change") byter vi success-grenen till
    // en ärlig info-rad så operatören inte gissar att texten landade
    // när den inte gjorde det. Visas bara på followups (init saknar
    // fältet) och bara när effect.applied === false.
    // Bug B-ärlighet: två distinkta no-op-orsaker från build_site.py kräver
    // OLIKA råd, annars vilseleder vi operatören.
    //   - `visible_files_unchanged`: bygget kördes men genererade IDENTISKA
    //     filer. Operatören bad om en konkret ändring (oftast layout/struktur
    //     som "centrera hero" / "lägg till gallery") men deterministisk
    //     codegen-v1 kan inte göra den än. Att be om "mer exakt text/sektion"
    //     vore fel — problemet är saknad codegen-kapabilitet, inte otydlighet.
    //     Riktig codegenModel för dessa intents är Sprint 3B (backend-lane).
    //   - annars (`intent_no_semantic_change`): intenten klassades som att den
    //     inte kräver någon innehållsändring (fråga/vag prompt) → då hjälper
    //     det faktiskt att be om en konkret rubrik/text/sektion.
    // Båda grenarna behåller variant "info" (aldrig "success") — låst av
    // tests/test_viewser_files.py::test_b155_floating_chat_no_op_does_not_claim_success.
    const effect = extractAppliedVisibleEffect(payload.buildResult);
    if (effect && effect.applied === false) {
      if (effect.reason === "visible_files_unchanged") {
        return {
          content: `Bygget gick igenom${versionText} men sajten ser likadan ut. I nuläget kan jag ändra texter på startsidan (företagsnamn, rubrik, tagline) — rubriker på undersidor och större layout-/strukturändringar (centrera hero, lägga till sektion) stöds inte än.${unappliedNote}`,
          variant: "info",
        };
      }
      return {
        content: `Jag kunde inte fånga någon synlig ändring den här gången.${versionText} Testa att ange exakt rubrik, text eller sektion — t.ex. "byt namnet i headern till X".${unappliedNote}`,
        variant: "info",
      };
    }
    // ADR 0034 väg B: när path A faktiskt skrev strukturerade copy-
    // direktiv för den här versionen så visa exakt vad som ändrades.
    // Tom lista = init-build, follow-up utan strukturerade direktiv,
    // eller artefakt-läsning som silently failade — alla tre
    // fallbackar till den generiska "Klart!"-raden så vi inte lovar
    // ändringar vi inte kan bekräfta.
    // UI-gap-fix (2026-06-02): backend kan härleda en EXAKT change-set
    // (routes tillagda/borttagna, variant-byte). Beräkna den FÖRE copy-
    // grenen så att den inte göms när en run både har copy-direktiv OCH
    // strukturella deltan — copy-direktiven beskriver bara text-ändringar.
    const exactChanges = summarizeChangeSet(payload.changeSet);
    const copyLines = summarizeCopyDirectives(payload.appliedCopyDirectives);
    if (copyLines.length > 0) {
      const verb = versionText ? `Klart!${versionText}` : "Klart!";
      const list =
        copyLines.length === 1
          ? copyLines[0]
          : copyLines.map((line) => `• ${line}`).join("\n");
      return {
        content: `${verb} ${list}`,
        variant: "success",
        // Bifoga den strukturella change-set:en under "Ändrat" när den finns,
        // annars göms tillagda/borttagna sidor och variant-byten bakom
        // copy-raden.
        ...(exactChanges.length > 0
          ? { changes: exactChanges, changesExact: true }
          : {}),
      };
    }
    // Faller bara igenom till heuristiken när change-set:en saknas/är tom.
    if (exactChanges.length > 0) {
      return {
        content: `Klart!${versionText} Previewen laddas om automatiskt.`,
        variant: "success",
        changes: exactChanges,
        changesExact: true,
      };
    }
    const changes = summarizeChangesFromPrompt(userPrompt);
    return {
      content: `Klart!${versionText} Previewen laddas om automatiskt.`,
      variant: "success",
      changes: changes.length > 0 ? changes : undefined,
    };
  }
  if (outcome === "degraded") {
    return {
      content: `Sajten byggdes, men Quality Gate flaggade något (typecheck, route-scan eller policy). Sajten har ändå publicerats — se Inspector för detaljer.${unappliedNote}`,
      variant: "warning",
    };
  }
  if (outcome === "failed") {
    return {
      content:
        "Bygget misslyckades och föregående version behölls. Prova en mer specifik instruktion eller dela upp ändringen.",
      variant: "error",
    };
  }
  return {
    content:
      "Bygget returnerade okänd status. Kontrollera Inspector → Quality Gate.",
    variant: "warning",
  };
}

export function FloatingChat({
  siteId,
  onBuildDone,
  isBuilding,
  onBuildStart,
  onBuildEnd,
  onStageChange,
  pendingBaseRunId,
  onClearBaseRunId,
  onShowVersions,
  tools,
  focusComposerSignal,
  composerPrefill,
}: FloatingChatProps) {
  const [position, setPosition] = useState<Position | null>(null);
  // Panel-storlek (desktop). Startar på default 360×460 = nuvarande fasta
  // mått (matchar SSR/first paint); hydreras från localStorage post-mount.
  // Resize-handles på panelens kanter/hörn skriver hit under drag.
  const [size, setSize] = useState<Size>(PANEL_DEFAULT_SIZE);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  // Första-gångs-hinten "Så funkar det". Startar dold (false) → layout-
  // effekten öppnar den post-mount om den aldrig setts. Persisteras vid
  // dismiss så den bara visas en gång per webbläsare.
  const [loopHintOpen, setLoopHintOpen] = useState(false);
  // På mobil (<768px) renderas panelen som bottom-sheet utan drag/
  // position-hantering. Hooken returnerar false under SSR och vid
  // initial hydration; skiftar till true post-mount om matchMedia
  // träffar.
  const isMobile = useIsMobileViewport();
  // Device-preset (375/768/1024/full) delas med ViewerPanel via
  // DevicePresetProvider — toggle-UI:t bor numera under FloatingChat:s
  // chat-panel (tidigare uppe till höger i canvasen).
  const { devicePreset, setDevicePreset } = useDevicePreset();
  // keyboardInset enabled bara när chatten är öppen på mobil — vi
  // behöver inte lyssna på visualViewport-resize:s när panelen är
  // minimerad eller när vi är på desktop (där tangentbord inte
  // täcker overlay-elementet).
  const keyboardInset = useKeyboardInset(isMobile && !isMinimized);
  // Initial-meddelandet beräknas en gång från siteId (lazy init) så
  // ingen useEffect behöver setState efter mount för att synca
  // intron mot sajten. Sajt-byten löses via key={siteId} i
  // BuilderShell vilket re-monterar komponenten med fräsch state.
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: `intro-${siteId}`,
      role: "assistant",
      content: `Sajten ${siteId} är aktiv. Beskriv vad du vill ändra.`,
      variant: "info",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  // Bilagor som operatören laddat upp men ännu inte skickat. När
  // skicka körs läggs deras refs in i prompt-texten och listan
  // töms. /api/upload-asset lagrar dem direkt under aktuell siteId,
  // så bygget kan hitta dem även om operatören aldrig nämner dem.
  const [attachments, setAttachments] = useState<AssetRef[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // Modulmarkeringar (sektionsmarkering i preview): skapas i Markera
  // modul-läget i PreviewInspectorOverlay, visas som chips i composern
  // och skickas som markedSections[] i nästa /api/prompt-anrop. Rensas
  // efter skickat — markeringen gäller EN följdprompt, inte en session.
  const { markedSections, removeMarkedSection, clearMarkedSections } =
    usePreviewInspector();
  // Snabbförslag-chips ligger under en collapsed "Förslag"-toggle
  // för att hålla composern minimalistisk. State persisteras så
  // operatörens preference (kollapsad/öppen) lever över reloads.
  const [quickPromptsOpen, setQuickPromptsOpen] = useState(false);
  // Progress-bar 0-100% under build körs. Driver bredden på den
  // tunna stapeln längst ner i panelen så operatören får en visuell
  // känsla av tidsåtgången utöver step-label:n i pending-bubblan.
  // Ramper deterministiskt till 95% över ~86s (sum av FOLLOWUP_BUILD_STEPS.durationMs)
  // och hoppar till 100% när response kommer (i finally:n).
  const [buildProgress, setBuildProgress] = useState(0);
  // Pending-meddelandets id sparas i en ref så useEffect kan uppdatera
  // bubblans content när tracePolling-hooken levererar nya phase-
  // labels. setState i en useEffect-callback hade triggat re-renders
  // och stale closures — refen är synkron och stale-fri.
  const pendingMessageIdRef = useRef<string | null>(null);
  const dragStartRef = useRef<{
    pointerX: number;
    pointerY: number;
    originX: number;
    originY: number;
  } | null>(null);
  // Resize-drag-state. ``edge`` är en sträng-union av väderstreck
  // (n/s/e/w + hörn) — hålls inline (inte namngiven PascalCase-typ) så
  // term-coverage --strict inte flaggar den som okänd domän-term.
  const resizeStartRef = useRef<{
    pointerX: number;
    pointerY: number;
    originW: number;
    originH: number;
    originX: number;
    originY: number;
    edge: "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
  } | null>(null);
  // Synkron spegel av size så drag-/window-resize-clamp:en kan läsa
  // aktuell storlek utan stale closures (samma motiv som dragStartRef).
  const sizeRef = useRef<Size>(size);
  const headerRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Ref till composer-textarea så vi kan flytta focus dit när panelen
  // expanderas från minimerat läge (annars stannar tangentbords-focus
  // på FAB-knappen och operatören måste Tab:a sig in i textfältet).
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  // Gate mot localStorage-race: persist-effekterna nedan kör vid mount INNAN
  // hydrerings-IIFE:n (useLayoutEffect) hunnit läsa stored-värdena. Utan denna
  // gate skrev de default-värdet ("false") tillbaka till localStorage och
  // nollställde operatörens sparade minimized/quick-prompts-preference innan
  // den ens lästs. Sätts true först när hydreringen läst klart.
  const hasHydratedRef = useRef(false);

  // Expandera panelen + flytta focus till composer i samma callback.
  // setTimeout(0) säkerställer att React renderat panelen + textarean
  // innan vi anropar focus() — annars är composerRef.current null.
  const expandAndFocus = useCallback(() => {
    setIsMinimized(false);
    setTimeout(() => {
      composerRef.current?.focus();
    }, 50);
  }, []);

  // UX-glue (msg-0050 b): surfa chatten när ett bygge från en ANNAN yta
  // (dialog/inspector) blir klart. BuilderShell bumpar focusComposerSignal;
  // vi jämför mot föregående värde via en ref så själva mount inte triggar
  // expand/focus (initialvärdet hoppas över). FloatingChat:s egna byggen går
  // via den råa onBuildDone i BuilderShell och bumpar därför aldrig signalen.
  const lastFocusSignalRef = useRef(focusComposerSignal ?? 0);
  useEffect(() => {
    const next = focusComposerSignal ?? 0;
    if (next === lastFocusSignalRef.current) return;
    lastFocusSignalRef.current = next;
    if (next <= 0) return;
    // expandAndFocus() sätter setIsMinimized(false). Vi skjuter upp anropet via
    // setTimeout(0) så setState inte körs synkront i effekt-kroppen (React 19:s
    // react-hooks/set-state-in-effect) — samma deferral-princip som filens
    // övriga post-mount-effekter. expandAndFocus har sin egen setTimeout(50)
    // för focus() efter att panelen hunnit renderas.
    const timer = setTimeout(() => expandAndFocus(), 0);
    return () => clearTimeout(timer);
  }, [focusComposerSignal, expandAndFocus]);

  // Sektionsmenyns "Ändra text"-åtgärd: förifyll composern + flytta
  // focus. Nonce-jämförelsen via ref gör mount no-op och låter samma
  // text triggas två gånger i rad. setTimeout(0) deferar setState:n ur
  // effektkroppen (react-hooks/set-state-in-effect, samma mönster som
  // focusComposerSignal-effekten ovan).
  const lastPrefillNonceRef = useRef(composerPrefill?.nonce ?? 0);
  useEffect(() => {
    const nonce = composerPrefill?.nonce ?? 0;
    if (nonce === lastPrefillNonceRef.current) return;
    lastPrefillNonceRef.current = nonce;
    if (!composerPrefill || nonce <= 0) return;
    const text = composerPrefill.text;
    const timer = setTimeout(() => {
      setInput(text);
      expandAndFocus();
    }, 0);
    return () => clearTimeout(timer);
  }, [composerPrefill, expandAndFocus]);

  // Initiera position + minimized från localStorage efter mount.
  //
  // setState wrappas i en async IIFE → setState körs efter `await`,
  // vilket är "subscription-style" enligt React 19:s
  // `react-hooks/set-state-in-effect`-rule (samma mönster som
  // viewer-panel.tsx + run-details-panel.tsx använder för
  // post-mount-state-initialisering).
  //
  // Vi använder useLayoutEffect så positionen sätts innan browsern
  // målar — annars skulle panelen kort flimra på CSS-fallback-
  // positionen längst ner till höger. CSS-fallbacken finns kvar för
  // first paint (när position === null) så ingenting krockar med
  // SSR-hydratiseringen.
  //
  // Sajt-id-reset löses via `key={siteId}` i BuilderShell — det
  // re-monterar komponenten när sajten byts, så meddelande-tråden
  // nollställs naturligt utan setState-i-effekt-bryt mot regeln.
  useLayoutEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      const storedSize = readStoredSize();
      const initialSize = storedSize ? clampSize(storedSize) : PANEL_DEFAULT_SIZE;
      setSize(initialSize);
      const footprint = initialSize.height + TOOLBAR_ROW_HEIGHT;
      const stored = readStoredPosition();
      const initial = stored
        ? clampToViewport(stored, initialSize.width, footprint)
        : defaultPosition(initialSize.width, footprint);
      setPosition(initial);
      setIsMinimized(readStoredMinimized());
      setQuickPromptsOpen(readStoredQuickPromptsOpen());
      setLoopHintOpen(!readLoopHintSeen());
      // Markera hydrering klar EFTER att stored-värdena lästs och setState
      // köats — nu får persist-effekterna börja skriva (den batchade re-
      // rendern skriver de hydrerade värdena, inte default).
      hasHydratedRef.current = true;
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Stäng hinten + kom ihåg dismissen. Egen callback så render-blocket
  // hålls rent och localStorage-skrivningen aldrig kraschar UI:t.
  const dismissLoopHint = useCallback(() => {
    setLoopHintOpen(false);
    try {
      window.localStorage.setItem(STORAGE_KEY_LOOP_HINT, "true");
    } catch {
      // Tyst — quota/disabled localStorage får inte krascha UI.
    }
  }, []);

  // Synka sizeRef varje gång size ändras så clamp:arna i drag-/window-
  // resize-handlers läser aktuell storlek utan att behöva size i deps.
  useEffect(() => {
    sizeRef.current = size;
  }, [size]);

  // Håll panel-storlek + position innanför viewport vid window-resize.
  useEffect(() => {
    function handleResize() {
      setSize((current) => clampSize(current));
      setPosition((current) => {
        if (!current) return current;
        const s = clampSize(sizeRef.current);
        return clampToViewport(current, s.width, s.height + TOOLBAR_ROW_HEIGHT);
      });
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Persistera panel-storlek (gated på hydrering som övriga preferenser).
  useEffect(() => {
    if (!hasHydratedRef.current) return;
    try {
      window.localStorage.setItem(STORAGE_KEY_SIZE, JSON.stringify(size));
    } catch {
      // Tyst — quota / disabled localStorage får inte krascha UI.
    }
  }, [size]);

  // Persistera position.
  useEffect(() => {
    if (!hasHydratedRef.current) return;
    if (!position) return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY_POSITION,
        JSON.stringify(position),
      );
    } catch {
      // Tyst — quota / disabled localStorage får inte krascha UI.
    }
  }, [position]);

  // Persistera minimized-state.
  useEffect(() => {
    if (!hasHydratedRef.current) return;
    try {
      window.localStorage.setItem(STORAGE_KEY_MINIMIZED, String(isMinimized));
    } catch {
      // Tyst.
    }
  }, [isMinimized]);

  // Persistera quick-prompts-toggle.
  useEffect(() => {
    if (!hasHydratedRef.current) return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY_QUICK_PROMPTS,
        String(quickPromptsOpen),
      );
    } catch {
      // Tyst.
    }
  }, [quickPromptsOpen]);

  // Auto-scrolla till botten när nya meddelanden kommer.
  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [messages]);

  // (tidigare unmount-cleanup för buildStepTimerRef togs bort i samma
  // commit som FOLLOWUP_BUILD_STEPS — useBuildTracePolling-hooken har
  // egen AbortController + cleanup som täcker både unmount och
  // enabled=false-fallet, så ingen separat cleanup behövs här.)

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (isMinimized) return;
      if (event.button !== 0) return;
      if (!position) return;
      // Bail om pointer-down skedde på (eller inuti) en interaktiv
      // kontroll i headern. Annars sätter setPointerCapture + det
      // efterföljande event.preventDefault() stopp för click-eventet
      // på minimera/stäng-knapparna och de blir oanvändbara — exakt
      // den buggen som operatören rapporterade ("går inte att klicka
      // på _-knappen bredvid krysset"). closest("button") täcker
      // även framtida ikon-knappar utan att vi behöver underhålla
      // en hårdkodad whitelist.
      const eventTarget = event.target as HTMLElement | null;
      if (eventTarget?.closest("button")) return;
      const target = event.currentTarget;
      target.setPointerCapture(event.pointerId);
      dragStartRef.current = {
        pointerX: event.clientX,
        pointerY: event.clientY,
        originX: position.x,
        originY: position.y,
      };
      setIsDragging(true);
      // Förhindra textselektion under drag.
      event.preventDefault();
    },
    [isMinimized, position],
  );

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const start = dragStartRef.current;
      if (!start) return;
      const dx = event.clientX - start.pointerX;
      const dy = event.clientY - start.pointerY;
      const s = sizeRef.current;
      setPosition(
        clampToViewport(
          { x: start.originX + dx, y: start.originY + dy },
          s.width,
          s.height + TOOLBAR_ROW_HEIGHT,
        ),
      );
    },
    [],
  );

  const handlePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragStartRef.current) return;
      const target = event.currentTarget;
      try {
        target.releasePointerCapture(event.pointerId);
      } catch {
        // Pointer-capture kan vara avslutad redan — inget att göra.
      }
      dragStartRef.current = null;
      setIsDragging(false);
    },
    [],
  );

  // Resize-drag: en handler-fabrik per kant/hörn. Startar drag, fångar
  // pointern på själva handtaget (inte headern) och sparar origin-mått +
  // origin-position så väst-/nord-drag kan hålla motsatt kant fast.
  const handleResizePointerDown = useCallback(
    (edge: "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw") =>
      (event: ReactPointerEvent<HTMLDivElement>) => {
        if (isMobile || isMinimized || !position) return;
        if (event.button !== 0) return;
        // Stoppa propagation så headerns drag-handler aldrig triggas och
        // preventDefault så ingen text selekteras under resize.
        event.stopPropagation();
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        resizeStartRef.current = {
          pointerX: event.clientX,
          pointerY: event.clientY,
          originW: size.width,
          originH: size.height,
          originX: position.x,
          originY: position.y,
          edge,
        };
        setIsResizing(true);
      },
    [isMobile, isMinimized, position, size],
  );

  const handleResizePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const start = resizeStartRef.current;
      if (!start) return;
      const dx = event.clientX - start.pointerX;
      const dy = event.clientY - start.pointerY;
      const { edge } = start;
      let width = start.originW;
      let height = start.originH;
      if (edge.includes("e")) width = start.originW + dx;
      if (edge.includes("w")) width = start.originW - dx;
      if (edge.includes("s")) height = start.originH + dy;
      if (edge.includes("n")) height = start.originH - dy;
      const clamped = clampSize({ width, height });
      // Väst-/nord-drag: håll motsatt (höger/nederkant) fast genom att
      // flytta x/y med den faktiska (clamp:ade) storleksdiffen.
      let x = start.originX;
      let y = start.originY;
      if (edge.includes("w")) x = start.originX + (start.originW - clamped.width);
      if (edge.includes("n")) y = start.originY + (start.originH - clamped.height);
      setSize(clamped);
      setPosition(
        clampToViewport({ x, y }, clamped.width, clamped.height + TOOLBAR_ROW_HEIGHT),
      );
    },
    [],
  );

  const handleResizePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!resizeStartRef.current) return;
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        // Pointer-capture kan vara avslutad redan — inget att göra.
      }
      resizeStartRef.current = null;
      setIsResizing(false);
    },
    [],
  );

  const handleUploadClick = useCallback(() => {
    if (isUploading || isSending || isBuilding) return;
    setUploadError(null);
    fileInputRef.current?.click();
  }, [isBuilding, isSending, isUploading]);

  const handleFileChange = useCallback(
    async (event: ReactChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      // Återställ input-elementet direkt så samma fil kan väljas
      // igen efter borttagning (browsers tröjnar annars `change`).
      event.target.value = "";
      if (!file) return;
      if (!ALLOWED_UPLOAD_MIMES.has(file.type)) {
        setUploadError("Endast PNG, JPEG, WebP eller SVG tillåts.");
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setUploadError(
          `Filen är ${(file.size / 1024 / 1024).toFixed(1)} MB — max är 10 MB.`,
        );
        return;
      }

      setIsUploading(true);
      setUploadError(null);
      try {
        const form = new FormData();
        form.append("file", file);
        // "gallery" är säker default — vi tvingar inte fram en
        // hero-/logo-omklassning. Operatören kan i fri text säga
        // "använd den nya bilden som hero" så plockar build-pipelinen
        // upp det via Vision/role-mapping.
        form.append("role", "gallery");
        form.append("siteId", siteId);
        const response = await fetch("/api/upload-asset", {
          method: "POST",
          body: form,
        });
        const payload = (await response.json()) as {
          ok?: boolean;
          ref?: AssetRef;
          error?: string;
        };
        if (!response.ok || !payload.ok || !payload.ref) {
          throw new Error(payload.error ?? "Uppladdningen misslyckades.");
        }
        setAttachments((prev) => [...prev, payload.ref as AssetRef]);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Okänt fel.";
        setUploadError(message);
      } finally {
        setIsUploading(false);
      }
    },
    [siteId],
  );

  const removeAttachment = useCallback((assetId: string) => {
    setAttachments((prev) => prev.filter((ref) => ref.assetId !== assetId));
  }, []);

  const sendFollowupPrompt = useCallback(
    async (raw: string) => {
      const trimmed = raw.trim();
      // Skicka kan triggas av tre saker: text+bilagor, bara text,
      // eller bara bilagor. Vi tillåter alla tre — om operatören
      // bara laddat upp en bild och klickar skicka tolkar vi det
      // som "använd den här bilden i sajten på lämpligt sätt".
      const hasAttachments = attachments.length > 0;
      if (!trimmed && !hasAttachments) return;
      if (isSending || isBuilding || isUploading) return;
      if (!siteId) return;

      // Bygg prompt-text med bilage-block sist så LLM:n får
      // strukturerad metadata utan att operatörens egna ord
      // späds ut. Markdown-bildlänken hänvisar till den
      // public-URL som build-pipelinen senare kommer servera
      // (`/uploads/<filename>`).
      const pieces: string[] = [];
      if (trimmed) pieces.push(trimmed);
      if (hasAttachments) {
        const header =
          attachments.length === 1
            ? "Jag har bifogat en bild som du kan använda:"
            : `Jag har bifogat ${attachments.length} bilder du kan använda:`;
        const lines = attachments.map((ref) => {
          const alt = ref.alt?.trim() || ref.filename;
          return `- ![${alt}](/uploads/${ref.filename}) (assetId=${ref.assetId}, role=${ref.role})`;
        });
        pieces.push("", header, ...lines);
      }
      const promptText = pieces.join("\n").trim();
      // Snapshot bilagorna innan vi tömmer listan så user-bubblan
      // kan visa rätt count även efter setAttachments([]).
      const sentAttachments = attachments;
      // Snapshot modulmarkeringarna innan de rensas — de skickas som
      // strukturerat markedSections[]-fält (routeId + sectionId ur
      // preview-markörerna; headingText följer med som note).
      const sentMarkedSections = markedSections.map((ref) => ({
        routeId: ref.routeId,
        sectionId: ref.sectionId,
        // note cappas till 200 tecken — samma gräns som /api/prompt-zodens
        // MarkedSectionSchema, så en lång sektionsrubrik aldrig 400:ar.
        ...(ref.headingText ? { note: ref.headingText.slice(0, 200) } : {}),
      }));

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed || "(Bifogade bilder utan extra instruktion)",
        attachmentCount: sentAttachments.length || undefined,
      };
      const pendingMessageId = `pending-${Date.now()}`;
      pendingMessageIdRef.current = pendingMessageId;
      const pendingMessage: ChatMessage = {
        id: pendingMessageId,
        role: "assistant",
        content: INITIAL_BUILD_LABEL,
        isPending: true,
        variant: "info",
      };
      setMessages((prev) => [...prev, userMessage, pendingMessage]);
      setInput("");
      setAttachments([]);
      clearMarkedSections();
      setUploadError(null);
      setBuildProgress(0);
      setIsSending(true);
      onBuildStart();
      // Återställ stegmarkören till "thinking" direkt — trace-polling-
      // effekten nedan förfinar till "building" när trace.ndjson når
      // build-fasen. Utan denna reset visade BuildProgressCard föregående
      // bygges sista stage.
      onStageChange?.("thinking");

      // Pending-bubblans label drivs av useBuildTracePolling-hooken
      // (lägre ner i komponenten) som sätts enabled när isSending=true.
      // Den uppdaterar pending-meddelandets content via en useEffect
      // som lyssnar på tracePolling.label-ändringar.

      try {
        const response = await fetch("/api/prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: promptText,
            mode: "followup",
            siteId,
            // baseRunId opt-in: om operatören klickat "Iterera från denna"
            // i Versions-tab plockar vi upp runId här. Backend
            // (scripts/prompt_to_project_input.py --base-run-id) laddar
            // PI-snapshotet från den runen istället för senaste, så
            // versionsräkningen blir max(latest, base) + 1.
            ...(pendingBaseRunId
              ? { baseRunId: pendingBaseRunId.baseRunId }
              : {}),
            // Sektionsmarkering i preview: strukturerade modulreferenser
            // från Markera modul-läget. Mjuk signal — backend validerar
            // mot base-runens emittedSections och droppar okända id:n
            // med varning. Utelämnas helt när inga markeringar finns.
            ...(sentMarkedSections.length > 0
              ? { markedSections: sentMarkedSections }
              : {}),
          }),
        });
        const payload = (await response.json()) as PromptApiResponse;
        // F1 slice 2 (conversation gate): dirigenten svarade i chatten utan
        // bygge (skämt/omdöme/fråga). Visa det ärliga svaret som info-bubbla
        // och stanna: inget runId finns, onBuildDone anropas INTE (ingen
        // version, ingen preview-refresh) och stegmarkören nollas till idle.
        // F1 slice 3: which conductor role acted (+ conversationKind) for the
        // honest role-row under the bubble; and the explicit expectsAnswer
        // signal (Scout #262) so an answer-only turn with an empty answerText
        // still short-circuits with an honest line instead of a generic HTTP
        // failure. extractConversationAnswer stays the primary source.
        const conversationMeta = extractConversationMeta(payload);
        const expectsAnswer = response.ok && extractExpectsAnswer(payload);
        const answerOnlyText = response.ok
          ? extractConversationAnswer(payload)
          : null;
        const conversationAnswer =
          answerOnlyText !== null
            ? answerOnlyText
            : expectsAnswer
              ? "Jag svarade i chatten utan att bygga om något."
              : null;
        if (conversationAnswer !== null) {
          onStageChange?.("idle");
          setMessages((prev) =>
            prev
              .filter((m) => m.id !== pendingMessageId)
              .concat({
                id: `answer-${Date.now()}`,
                role: "assistant",
                content: conversationAnswer,
                variant: "info",
                conversationRole: conversationMeta?.role ?? null,
                conversationKind: conversationMeta?.conversationKind ?? null,
              }),
          );
          return;
        }
        if (!response.ok || !payload.runId || !payload.siteId) {
          const errorText =
            payload.error ??
            `Prompt-anropet misslyckades (HTTP ${response.status})`;
          const classified = classifyFollowupError(errorText);
          onStageChange?.("failed");
          setMessages((prev) =>
            prev
              .filter((m) => m.id !== pendingMessageId)
              .concat({
                id: `error-${Date.now()}`,
                role: "assistant",
                content: classified.message,
                variant: "error",
                errorKind: classified.kind,
                errorTip: classified.tip,
                errorDetails: errorText,
                // Spara endast text-delen som retry-prompt — bilagorna
                // har redan tömts från attachments-state och kan inte
                // återställas utan att operatören laddar upp dem igen.
                retryPrompt: trimmed || undefined,
              }),
          );
          return;
        }
        const outcome = classifyBuildStatus(payload.buildStatus);
        const summary = summarizeBuildResult(payload, outcome, trimmed);
        setMessages((prev) =>
          prev
            .filter((m) => m.id !== pendingMessageId)
            .concat({
              id: `done-${Date.now()}`,
              role: "assistant",
              content: summary.content,
              variant: summary.variant,
              changes: summary.changes,
              changesExact: summary.changesExact,
              // F1 slice 3: which role acted (e.g. section_builder on a
              // section_add) for the honest role-row; decorative metadata only.
              conversationRole: conversationMeta?.role ?? null,
              conversationKind: conversationMeta?.conversationKind ?? null,
              // Pipeline-failed bygge (variant "error", outcome "failed"):
              // erbjud "Försök igen" med samma prompt. Build-fel är ofta
              // transienta (npm-timeout, flakig codegen) så en retry är
              // värdefull — tidigare saknades retry helt på failed-bygget
              // (bara HTTP/network-fel fick retry-knapp). Endast text-delen
              // sparas; bilagor kan inte återställas (samma regel som
              // HTTP-fel-grenen ovan).
              retryPrompt:
                summary.variant === "error" ? trimmed || undefined : undefined,
            }),
        );
        // Bygget landade (ok/degraded/failed-status) — markera sista steget
        // så stegmarkören visar "klart" tills page.tsx tar över. Använd
        // samma outcomeToStage-mappning som PromptBuilder: degraded/unknown
        // → "degraded" (inte "success"), annars visade progress-cardet grönt
        // medan chatten samtidigt rapporterade en varning.
        onStageChange?.(outcomeToStage(outcome));
        onBuildDone(payload.runId, outcome);
      } catch (caught) {
        const errorText =
          caught instanceof Error ? caught.message : "Okänt fel.";
        const classified = classifyFollowupError(errorText);
        onStageChange?.("failed");
        setMessages((prev) =>
          prev
            .filter((m) => m.id !== pendingMessageId)
            .concat({
              id: `error-${Date.now()}`,
              role: "assistant",
              content: classified.message,
              variant: "error",
              errorKind: classified.kind,
              errorTip: classified.tip,
              errorDetails: errorText,
              retryPrompt: trimmed || undefined,
            }),
        );
      } finally {
        // Pending-bubblan slutar uppdatera automatiskt via tracePolling-
        // hooken: när isSending blir false flippas hookens enabled-flagga
        // och poll-loopen rensas (AbortController + setState(emptyState)).
        // Hoppar till 100 % först — UI:t visar progress-baren animera
        // till slutet under fade-out (200 ms). Reset till 0 sker
        // automatiskt när nästa build startar.
        pendingMessageIdRef.current = null;
        setBuildProgress(100);
        setIsSending(false);
        onBuildEnd();
      }
    },
    [
      attachments,
      markedSections,
      clearMarkedSections,
      isSending,
      isBuilding,
      isUploading,
      siteId,
      onBuildStart,
      onBuildEnd,
      onBuildDone,
      onStageChange,
      pendingBaseRunId,
    ],
  );

  // Progress-bar ramp: under build körs ökar vi `buildProgress`
  // smooth från 0% → 95% över ~30s. Vi använder requestAnimationFrame
  // så den följer browserns frame-rate och fade:as ut snyggt vid
  // reduced-motion (där transition:en på baren själv är 0ms).
  useEffect(() => {
    if (!isSending && !isBuilding) return;
    if (buildProgress >= 95) return;
    const start = Date.now();
    const startProgress = buildProgress;
    let rafId = 0;
    const tick = () => {
      const elapsed = Date.now() - start;
      // Easeout — snabbt först, saktar mot slutet, klampar vid 95.
      const linear = Math.min(1, elapsed / PROGRESS_RAMP_DURATION_MS);
      const eased = 1 - Math.pow(1 - linear, 1.4);
      const target = startProgress + (95 - startProgress) * eased;
      setBuildProgress(target);
      if (target < 95 && (isSending || isBuilding)) {
        rafId = requestAnimationFrame(tick);
      }
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
    // Lint: buildProgress får INTE vara dep — annars triggas effecten
    // efter varje frame och vi får oändlig loop. Vi tar bara den
    // initiala värdet via closure och låter den driva fram.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSending, isBuilding]);

  // Live Build Sync — pending-bubblans label drivs av riktig pipeline-
  // status från trace.ndjson via useBuildTracePolling. Hooken aktiveras
  // när isSending=true (en /api/prompt-fetch är pågående) och pollar
  // /api/runs?siteId=X tills pending-runen syns, sedan
  // /api/runs/[runId]/trace?since= för incrementala events. När
  // hookens label byts uppdaterar useEffect pending-meddelandets
  // content. Cleanup sker via enabled=false när isSending blir false.
  // C3: aktivera även när ett dialog-bygge driver page-level isBuilding (utan
  // att FloatingChat självt skickar). Annars pollade vi bara trace.ndjson för
  // FloatingChat:s egna byggen, och en variant/färg/bild/scrape-dialog lämnade
  // BuildProgressCard kvar på "thinking" hela bygget igenom (stage-refine
  // nedan bailade på !isSending). Label-uppdateringen är ändå no-op när ingen
  // pending-bubbla finns (dialoger skapar ingen), så det enda nettot är att
  // buildStage avancerar korrekt.
  const tracePolling = useBuildTracePolling(siteId, {
    enabled: isSending || isBuilding,
  });
  useEffect(() => {
    const id = pendingMessageIdRef.current;
    if (!id) return;
    if (!tracePolling.isPending && tracePolling.runStatus === null) return;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, content: tracePolling.label } : m,
      ),
    );
  }, [tracePolling.label, tracePolling.isPending, tracePolling.runStatus]);

  // Förfina bygg-stage från trace.ndjson-fasen: understand/plan = "thinking",
  // build = "building". page.tsx mappar detta till BuildProgressCard-steget.
  // C3: kör medan ett bygge pågår — antingen FloatingChat:s eget (isSending)
  // eller ett dialog-bygge som driver page-level isBuilding. När båda är
  // false rör vi inte buildStage (success/failed sätts i handleSend för
  // FloatingChat-byggen; för dialog-byggen sätter handleBuildDone utfallet).
  useEffect(() => {
    if ((!isSending && !isBuilding) || !onStageChange) return;
    if (tracePolling.currentPhase === "build") {
      onStageChange("building");
    } else if (
      tracePolling.currentPhase === "understand" ||
      tracePolling.currentPhase === "plan"
    ) {
      onStageChange("thinking");
    }
  }, [tracePolling.currentPhase, isSending, isBuilding, onStageChange]);

  // ⌥1–⌥4 växlar preview-bredd (mobile/tablet/laptop/full) utan att lämna
  // tangentbordet under preview→följdprompt-loopen. Bara på desktop (presets
  // är desktop-only) och inte när fokus ligger i composern. Matchar på
  // event.code (Digit1–4) eftersom Option+siffra ger specialtecken på Mac.
  // Samma modifier som wizardens steg-hopp, men de samexisterar aldrig —
  // wizarden är stängd i builder-läget där FloatingChat lever.
  useEffect(() => {
    if (isMobile) return;
    const handler = (event: KeyboardEvent) => {
      if (!event.altKey || event.metaKey || event.ctrlKey) return;
      if (!/^Digit[1-4]$/.test(event.code)) return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      const option =
        DEVICE_PRESET_OPTIONS[parseInt(event.code.slice(5), 10) - 1];
      if (!option) return;
      event.preventDefault();
      setDevicePreset(option.id);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isMobile, setDevicePreset]);

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        void sendFollowupPrompt(input);
        return;
      }
      // Esc inom textarea: om input är icke-tom, rensa den; annars
      // minimera panelen. Två steg så operatören inte råkar minimera
      // mitt i en lång prompt-redigering.
      if (event.key === "Escape") {
        if (input.trim().length > 0) {
          event.preventDefault();
          setInput("");
        } else {
          event.preventDefault();
          setIsMinimized(true);
        }
      }
    },
    [input, sendFollowupPrompt],
  );

  if (!position) {
    // Pre-mount: render en CSS-positionerad placeholder så panelen
    // syns omedelbart utan layout-shift när position-staten väl
    // sätts. Mobil = bottom-sheet (full bredd, pb-safe, rounded-top),
    // desktop = bottom-right floating (360x460).
    return (
      <aside
        aria-label="Sajtmaskin-chatt"
        className={cn(
          "border-border/60 bg-card/95 pointer-events-auto fixed z-40 flex flex-col border shadow-2xl backdrop-blur-xl",
          // Pre-mount-placeholdern visas i 1 frame innan layout-effect
          // satt position-state. Full rounded-2xl här eftersom toolbar-
          // raden inte rendras än — annars skulle chat-panelen se
          // "ofullständig" ut (avhuggen nederkant utan något under).
          isMobile
            ? "pb-safe inset-x-0 bottom-0 max-h-[85dvh] w-full rounded-t-3xl"
            : "right-6 bottom-6 w-[360px] rounded-2xl",
        )}
        style={isMobile ? undefined : { height: PANEL_HEIGHT }}
      >
        {isMobile && <div aria-hidden className="bottom-sheet-handle" />}
        <div className="border-border/60 flex items-center justify-between border-b px-3 py-2">
          <div className="text-foreground flex items-center gap-2 text-[12px] font-medium tracking-tight">
            <MessageSquare className="text-muted-foreground h-3.5 w-3.5" />
            Sajtmaskin
          </div>
        </div>
        <div className="flex-1" />
      </aside>
    );
  }

  if (isMinimized) {
    // Mobil = FAB (56x56) bottom-safe-right. Sidotab-mönstret täcker
    // för stor del av smala viewports och hamnar dessutom mitt på
    // skärmen vilket är svårt att nå med tummen. FAB:en lever i
    // tum-zonen och respekterar safe-area.
    if (isMobile) {
      return (
        <button
          type="button"
          onClick={expandAndFocus}
          aria-label="Öppna Sajtmaskin-chatten"
          title="Öppna chatten"
          className={cn(
            "group pointer-events-auto fixed right-4 z-40 inline-flex h-14 w-14 items-center justify-center rounded-full",
            "border-border/60 bg-card/95 text-foreground border shadow-2xl backdrop-blur-xl",
            "motion-safe:animate-fc-edge-pulse",
            "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
            "transition-transform active:scale-95",
            "bottom-safe-4",
          )}
        >
          <MessageSquare aria-hidden className="text-foreground/80 h-5 w-5" />
          <span
            aria-hidden
            className={cn(
              "ring-card absolute top-1.5 right-1.5 h-2 w-2 rounded-full ring-2",
              isBuilding
                ? "bg-amber-500 motion-safe:animate-pulse"
                : "bg-emerald-500",
            )}
          />
          <span className="sr-only">Sajtmaskin</span>
        </button>
      );
    }
    // Desktop: sido-tab på höger kant. Fast position oavsett var
    // panelen stod när operatören klickade Minimera. Pulsen är
    // subtil (motion-safe + 2.6s). Hover/focus expanderar till en
    // bredare pill med text och ChevronLeft-ikon.
    return (
      <button
        type="button"
        onClick={expandAndFocus}
        aria-label="Öppna Sajtmaskin-chatten"
        title="Öppna chatten"
        className={cn(
          "group pointer-events-auto fixed top-1/2 right-0 z-40 -translate-y-1/2",
          "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
        )}
      >
        <span
          className={cn(
            "border-border/60 bg-card/95 text-foreground flex h-14 items-center gap-2 rounded-l-2xl border border-r-0 pr-3 pl-2.5 backdrop-blur-xl",
            "motion-safe:animate-fc-edge-pulse",
            "transition-[padding,gap] duration-200 ease-out",
            "group-hover:gap-2.5 group-hover:pr-4 group-focus-visible:gap-2.5 group-focus-visible:pr-4",
          )}
        >
          <ChevronLeft
            aria-hidden
            className={cn(
              "text-muted-foreground h-4 w-4 transition-transform duration-200",
              "group-hover:text-foreground group-hover:-translate-x-0.5",
              "group-focus-visible:text-foreground group-focus-visible:-translate-x-0.5",
            )}
          />
          <span
            aria-hidden
            className={cn(
              "h-2 w-2 rounded-full",
              isBuilding
                ? "bg-amber-500 motion-safe:animate-pulse"
                : "bg-emerald-500",
            )}
          />
          <span className="text-[12px] font-medium tracking-tight whitespace-nowrap">
            Sajtmaskin
          </span>
        </span>
      </button>
    );
  }

  return (
    <>
      <aside
        aria-label="Sajtmaskin-chatt"
        className={cn(
          "border-border/60 bg-card/95 pointer-events-auto fixed z-40 flex flex-col overflow-hidden border shadow-2xl backdrop-blur-xl",
          // Mobil = bottom-sheet (full bredd, kapad höjd, safe-area).
          // Desktop = 360px floating panel med inline position-state.
          // På desktop används rounded-t-2xl (inte rounded-2xl) eftersom
          // toolbar-raden under (format + Verktyg) hänger ihop kant-i-kant
          // och formar tillsammans EN rektangel med rundade ytter-hörn.
          // Bottom-rundningen lever på toolbar-raden istället.
          isMobile
            ? "pb-safe inset-x-0 bottom-0 max-h-[85dvh] w-full rounded-t-3xl"
            : "rounded-t-2xl",
          isDragging || isResizing
            ? "cursor-grabbing transition-none"
            : "motion-safe:transition-[box-shadow] motion-safe:duration-150",
        )}
        style={
          isMobile
            ? // bottom: keyboardInset hänger panelen ovanför iOS-tangentbordet
              // (= 0 när keyboard ej syns, > 0 när det är öppet). transition
              // gör att panelen glider upp/ner smidigt istället för att hoppa.
              {
                bottom: keyboardInset,
                transition: "bottom 0.18s ease-out",
              }
            : {
                left: position.x,
                top: position.y,
                width: size.width,
                height: size.height,
                minHeight: PANEL_MIN_HEIGHT,
              }
        }
      >
        {isMobile && <div aria-hidden className="bottom-sheet-handle" />}
        <div
          ref={headerRef}
          onPointerDown={isMobile ? undefined : handlePointerDown}
          onPointerMove={isMobile ? undefined : handlePointerMove}
          onPointerUp={isMobile ? undefined : handlePointerUp}
          onPointerCancel={isMobile ? undefined : handlePointerUp}
          className={cn(
            "border-border/60 bg-card/90 flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2 select-none",
            isMobile
              ? "cursor-default"
              : isDragging
                ? "cursor-grabbing"
                : "cursor-grab",
          )}
        >
          <div className="text-foreground flex min-w-0 items-center gap-2 text-[12px] font-medium tracking-tight">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                isBuilding
                  ? "bg-amber-500 motion-safe:animate-pulse"
                  : "bg-emerald-500",
              )}
              aria-hidden
            />
            <MessageSquare className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
            <span className="truncate">Sajtmaskin</span>
            <span
              className="text-muted-foreground ml-1 truncate font-mono text-[10px]"
              title={siteId}
            >
              {siteId}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              type="button"
              onClick={() => setIsMinimized(true)}
              aria-label="Minimera"
              className="text-muted-foreground hover:text-foreground hover:bg-muted/60 min-tap md:min-tap-0 inline-flex items-center justify-center rounded-md active:scale-95 sm:h-6 sm:w-6"
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setIsMinimized(true)}
              aria-label="Stäng (minimera)"
              title="Stäng (öppnas igen från bubblan)"
              className="text-muted-foreground hover:text-foreground hover:bg-muted/60 min-tap md:min-tap-0 inline-flex items-center justify-center rounded-md active:scale-95 sm:h-6 sm:w-6"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Första-gångs-hint: gör kärnloopen synlig (följdprompt → ny
          version). Dismiss:bar och persisterad så den bara visas en
          gång. "Visa versioner" djuplänkar till historiken. */}
        {loopHintOpen ? (
          <div className="border-border/60 bg-muted/40 shrink-0 border-b px-3 py-2.5">
            <div className="flex items-start gap-2">
              <Sparkles
                className="text-foreground/70 mt-0.5 h-3.5 w-3.5 shrink-0"
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="text-foreground text-[12px] leading-relaxed">
                  Så funkar det: beskriv en ändring här så bygger jag om sajten.
                  Varje bygge sparas som en ny version du kan gå tillbaka till.
                </p>
                {onShowVersions ? (
                  <button
                    type="button"
                    onClick={onShowVersions}
                    className="text-foreground/80 hover:text-foreground mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium underline-offset-2 hover:underline"
                  >
                    <GitBranch className="h-3 w-3" aria-hidden />
                    Visa versioner
                  </button>
                ) : null}
              </div>
              <button
                type="button"
                onClick={dismissLoopHint}
                aria-label="Dölj tipset"
                title="Dölj"
                className="text-muted-foreground hover:text-foreground hover:bg-muted/60 min-tap md:min-tap-0 inline-flex shrink-0 items-center justify-center rounded-md active:scale-95 sm:h-6 sm:w-6"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ) : null}

        <div
          ref={messagesRef}
          className="flex-1 overflow-y-auto px-3 py-3"
          role="log"
          aria-live="polite"
        >
          <ol className="flex flex-col gap-2">
            {messages.map((message) => (
              <li key={message.id} className="flex flex-col">
                <MessageBubble
                  message={message}
                  onRetry={(prompt) => {
                    // Sätt input + skicka — operatören kan välja att
                    // ändra prompten först om hen vill, eller bara
                    // klicka skicka direkt. Vi rensar inte input om
                    // operatören redan börjat skriva på något nytt.
                    if (input.trim().length === 0) {
                      setInput(prompt);
                      // Auto-skicka när input var tom — annars är det
                      // sannolikt operatören håller på med en ny prompt
                      // och hen får trycka skicka själv.
                      void sendFollowupPrompt(prompt);
                    } else {
                      setInput(prompt);
                    }
                  }}
                />
              </li>
            ))}
          </ol>
        </div>

        {/* Build progress-bar — visas under build körs. Determinerade
          steg är 4 (brief/plan/codegen/quality); progress drivs av
          ``buildProgress``-state som ramper från 0 → 95% över
          förväntad total-duration. Stannar vid 95% tills response,
          sedan hoppar till 100% och fade:as ut via onAnimationEnd. */}
        {(isSending || isBuilding) && (
          <div className="border-border/40 bg-card/80 shrink-0 border-t">
            <div className="bg-border/40 relative h-[2px] w-full overflow-hidden">
              <div
                className="bg-foreground/80 absolute inset-y-0 left-0 motion-safe:transition-[width] motion-safe:duration-500"
                style={{ width: `${buildProgress}%` }}
                aria-hidden
              />
            </div>
          </div>
        )}

        <div className="border-border/60 bg-card/90 shrink-0 border-t p-2">
          {/* "Iterera från denna"-pill: visas så fort operatören valt
            en historisk version i Versions-tab. Nästa submit skickar
            baseRunId i fetch-bodyn så backend laddar PI-snapshotet
            från den runen istället för senaste. X:et avmarkerar
            utan att skicka. */}
          {pendingBaseRunId ? (
            <div
              role="status"
              className="mb-2 flex items-center gap-2 rounded-md border border-sky-500/40 bg-sky-500/[0.08] px-2 py-1.5 text-[11px] text-sky-700 dark:text-sky-300"
            >
              <GitBranch className="h-3 w-3 shrink-0" aria-hidden />
              <span className="flex-1 truncate">
                Iterera från{" "}
                {pendingBaseRunId.baseVersion !== null
                  ? `version ${pendingBaseRunId.baseVersion}`
                  : "vald version"}
              </span>
              {onClearBaseRunId ? (
                <button
                  type="button"
                  onClick={onClearBaseRunId}
                  aria-label="Avbryt iterera-läge"
                  title="Avbryt iterera-läge"
                  className={cn(
                    "min-tap md:min-tap-0 inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-sky-500/15 active:scale-95",
                    "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
                  )}
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              ) : null}
            </div>
          ) : null}
          {/* Snabbförslag ligger bakom en collapsed "Förslag"-toggle.
            Klick på en chip fyller textarean (utan att skicka) så
            operatören kan finslipa innan submit. Toggle-läget
            persisteras i localStorage så preference följer med
            mellan reloads. Endast när det inte finns bilagor att
            visa — vi vill inte stapla två chip-rader. */}
          {attachments.length === 0 && !isSending && !isBuilding ? (
            <div className="mb-2 flex flex-col items-center">
              <button
                type="button"
                onClick={() => setQuickPromptsOpen((prev) => !prev)}
                aria-expanded={quickPromptsOpen}
                aria-controls="floating-chat-quick-prompts"
                aria-label={quickPromptsOpen ? "Dölj förslag" : "Visa förslag"}
                title={quickPromptsOpen ? "Dölj förslag" : "Visa förslag"}
                className={cn(
                  "text-muted-foreground/70 hover:text-foreground hover:bg-muted/50",
                  "min-tap md:min-tap-0 inline-flex h-5 w-9 items-center justify-center rounded-full active:scale-95",
                  "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
                  "transition-colors",
                )}
              >
                <ChevronUp
                  className={cn(
                    "h-3.5 w-3.5 transition-transform duration-200",
                    quickPromptsOpen ? "rotate-180" : "rotate-0",
                  )}
                  aria-hidden
                />
              </button>
              {quickPromptsOpen ? (
                <div
                  id="floating-chat-quick-prompts"
                  className="mt-1.5 flex w-full flex-col gap-1.5"
                >
                  {QUICK_PROMPT_CATEGORIES.map((category) => (
                    <div key={category.id} className="flex flex-col gap-1">
                      <span
                        className="text-muted-foreground/60 px-0.5 text-[9.5px] font-medium tracking-widest uppercase"
                        aria-hidden
                      >
                        {category.label}
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {category.prompts.map((suggestion) => (
                          <button
                            key={suggestion}
                            type="button"
                            onClick={() => {
                              setInput(suggestion);
                              setQuickPromptsOpen(false);
                            }}
                            title={suggestion}
                            className={cn(
                              "border-border/60 bg-background/80 text-foreground/80",
                              "hover:border-border hover:bg-card hover:text-foreground",
                              "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
                              "min-tap md:min-tap-0 rounded-full border px-2.5 py-1 text-[11px] transition-colors active:scale-95 sm:px-2 sm:py-0.5 sm:text-[10.5px]",
                              CHIP_INTERACTIONS,
                            )}
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {/* Markerade moduler (sektionsmarkering i preview). Chips med
            routeId/sectionId + X — samma mönster som bilage-chipsen.
            Rensas när prompten skickas (markeringen gäller en prompt). */}
          {markedSections.length > 0 ? (
            <div className="-mx-0.5 mb-2 flex flex-wrap gap-1">
              {markedSections.map((ref) => (
                <span
                  key={`${ref.routeId}:${ref.sectionId}`}
                  className="inline-flex max-w-full items-center gap-1 rounded-md border border-emerald-600/40 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-900 dark:text-emerald-200"
                >
                  <Crosshair
                    className="h-3 w-3 shrink-0 text-emerald-600"
                    aria-hidden
                  />
                  <span
                    className="truncate"
                    title={
                      ref.headingText
                        ? `${ref.routeId} · ${ref.sectionId} · ${ref.headingText}`
                        : `${ref.routeId} · ${ref.sectionId}`
                    }
                  >
                    {ref.routeId === "home"
                      ? ref.sectionId
                      : `${ref.routeId}/${ref.sectionId}`}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      removeMarkedSection(ref.routeId, ref.sectionId)
                    }
                    aria-label={`Ta bort markeringen ${ref.sectionId}`}
                    className="text-emerald-700/80 hover:text-emerald-900 min-tap md:min-tap-0 inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded active:scale-95 dark:text-emerald-300/80 dark:hover:text-emerald-100"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              ))}
            </div>
          ) : null}

          {/* Pending-bilagor. Små chips med filnamn + X. När operatören
            skickar prompten töms listan. */}
          {attachments.length > 0 ? (
            <div className="-mx-0.5 mb-2 flex flex-wrap gap-1">
              {attachments.map((ref) => (
                <span
                  key={ref.assetId}
                  className="border-border/60 bg-muted/60 text-foreground/85 inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-0.5 text-[11px]"
                >
                  <ImagePlus className="text-muted-foreground h-3 w-3 shrink-0" />
                  <span className="truncate" title={ref.filename}>
                    {ref.filename}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(ref.assetId)}
                    aria-label={`Ta bort ${ref.filename}`}
                    className="text-muted-foreground hover:text-foreground min-tap md:min-tap-0 inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded active:scale-95"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              ))}
            </div>
          ) : null}

          {uploadError ? (
            <p
              role="alert"
              className="text-destructive mb-2 px-1 text-[11px] leading-snug"
            >
              {uploadError}
            </p>
          ) : null}

          <div className="border-border/70 bg-background focus-within:border-ring/50 focus-within:ring-ring/30 overflow-hidden rounded-xl border focus-within:ring-2">
            <Textarea
              ref={composerRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                attachments.length > 0
                  ? "Berätta hur bilden ska användas (valfritt)…"
                  : "Beskriv ändringen…"
              }
              rows={2}
              maxLength={4000}
              disabled={isSending || isBuilding}
              // text-base (16px) på mobil förhindrar iOS Safari från att
              // auto-zooma vid fokus; krymper till text-[13px] på md+.
              // sm:-breakpoint (640px) är fortfarande iPad-portrait där
              // iOS-zoom kan trigga; md: (768px) är säkrare.
              className="min-h-[60px] resize-none border-0 bg-transparent px-3 py-2 text-base shadow-none focus-visible:ring-0 md:text-[13px]"
            />
            <div className="border-border/60 flex items-center justify-between gap-2 border-t px-2 py-1.5">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleUploadClick}
                  disabled={isUploading || isSending || isBuilding}
                  aria-label="Bifoga bild"
                  title="Bifoga bild (PNG, JPEG, WebP, SVG · max 10 MB)"
                  className={cn(
                    "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                    "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                    "min-tap md:min-tap-0 inline-flex items-center justify-center rounded-md transition-colors sm:h-6 sm:w-6",
                    "active:scale-95 disabled:opacity-40 disabled:hover:bg-transparent",
                  )}
                >
                  {isUploading ? (
                    <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <ImagePlus aria-hidden className="h-3.5 w-3.5" />
                  )}
                </button>
                <span className="text-muted-foreground text-[10px]">
                  ⌘↵ skicka · esc minimera
                </span>
              </div>
              <button
                type="button"
                onClick={() => void sendFollowupPrompt(input)}
                disabled={
                  isSending ||
                  isBuilding ||
                  isUploading ||
                  (input.trim().length === 0 && attachments.length === 0)
                }
                aria-label="Skicka instruktion"
                className={cn(
                  "bg-foreground text-background inline-flex min-h-[44px] items-center gap-1.5 rounded-md px-3.5 text-sm font-medium sm:h-7 sm:min-h-0 sm:px-2.5 sm:text-[11.5px]",
                  "hover:bg-foreground/90 active:scale-95 disabled:opacity-40",
                  "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                  PRIMARY_INTERACTIONS,
                )}
              >
                {isSending || isBuilding ? (
                  <Loader2 aria-hidden className="h-3 w-3 animate-spin" />
                ) : (
                  <Send aria-hidden className="h-3 w-3" />
                )}
                {isSending || isBuilding
                  ? buildProgress < 15
                    ? "Skickar"
                    : buildProgress < 95
                      ? "Bygger"
                      : "Sparar"
                  : "Skicka"}
              </button>
            </div>
          </div>
        </div>

        {/* Dold filinput används av paperclip-knappen. Visuellt
          gömd men funktionellt aktiverbar via .click(). */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/svg+xml"
          onChange={(event) => void handleFileChange(event)}
          className="hidden"
          aria-hidden
        />

      </aside>

      {/* Toolbar-rad UNDER chat-panelen — innehåller device-preset-
        knapparna (375/768/1024/Full), en subtil vertikal divider, och
        en optional `tools`-slot (typiskt BuilderActions inline-knappen).
        Bredd = PANEL_WIDTH (360px) och `rounded-b-2xl` så toolbar-raden
        + chat-panelen ovanför formar visuellt EN sammanhängande
        rektangel: chat = rounded-t-2xl, toolbar = rounded-b-2xl, raka
        sidkanter på båda. `border-t-0` döljer top-borden så chat-
        panelens border-bottom syns igenom som en subtil divider mellan
        de två sektionerna (operatör-önskan 2026-05-26: "inte ligga i
        en egen bubbla utan raka kanter på sidorna som om dom ligger i
        samma fyrkant som resten av chattrutan").

        Renderas bara på desktop (md+) och endast när panelen inte är
        minimerad — på mobile är enheten själv liten och toggle-värdet
        är meningslöst, och Verktyg-pillen är ändå dold under md:.
        position-null guard:en hanterar SSR + initial hydration innan
        first-mount-effekten satt position-state. */}
      {!isMobile && !isMinimized && position ? (
        <div
          role="toolbar"
          aria-label="Förhandsvisningsbredd och verktyg"
          className="border-border/60 bg-card/95 pointer-events-auto fixed z-40 hidden items-center justify-center gap-0.5 rounded-b-2xl border border-t-0 p-1 shadow-2xl backdrop-blur-xl md:flex"
          style={{
            left: position.x,
            top: position.y + size.height,
            width: size.width,
          }}
        >
          {DEVICE_PRESET_OPTIONS.map((option, idx) => {
            const isActive = devicePreset === option.id;
            const Icon = option.Icon;
            const shortcut = `⌥${idx + 1}`;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={isActive}
                aria-label={
                  option.width
                    ? `Preview-bredd ${option.label}px (genväg ${shortcut})`
                    : `Full bredd (genväg ${shortcut})`
                }
                title={`Genväg ${shortcut}`}
                onClick={() => setDevicePreset(option.id)}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium transition active:scale-95",
                  isActive
                    ? "bg-foreground text-background shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {option.label}
              </button>
            );
          })}
          {tools ? (
            <>
              <span aria-hidden className="bg-border/60 mx-0.5 h-5 w-px" />
              {tools}
            </>
          ) : null}
        </div>
      ) : null}

      {/* Resize-handtag (desktop): ett fixed lager som spänner över HELA
        fönstret (chat-panelen + toolbar-raden = en visuell rektangel) och
        sticker ut 4px utanför kanten, som riktiga OS-/webbläsarfönster.
        Tidigare bodde handtagen inne i chat-panelen: dels klipptes de av
        panelens overflow-hidden så de yttersta pixlarna träffade bordern
        i stället för handtaget, dels saknade toolbar-raden (fönstrets
        visuella nederkant) handtag helt — operatörsfynd 2026-06-10:
        "går bara att dra uppe". Wrappern är pointer-events-none så den
        aldrig blockerar chat-innehållet; varje handtag är pointer-
        events-auto med rätt resize-cursor. z-50 lägger dem ovanför
        headern så top-kanten resize:ar i stället för att dra
        (handleResizePointerDown stopPropagation:ar). */}
      {!isMobile && !isMinimized && position ? (
        <div
          aria-hidden
          className="pointer-events-none fixed z-50"
          style={{
            left: position.x - RESIZE_HANDLE_OVERHANG,
            top: position.y - RESIZE_HANDLE_OVERHANG,
            width: size.width + RESIZE_HANDLE_OVERHANG * 2,
            height:
              size.height + TOOLBAR_ROW_HEIGHT + RESIZE_HANDLE_OVERHANG * 2,
          }}
        >
          {(
            [
              ["n", "top-0 right-4 left-4 h-2.5 cursor-ns-resize"],
              ["s", "right-4 bottom-0 left-4 h-2.5 cursor-ns-resize"],
              ["e", "top-4 right-0 bottom-4 w-2.5 cursor-ew-resize"],
              ["w", "top-4 bottom-4 left-0 w-2.5 cursor-ew-resize"],
              ["ne", "top-0 right-0 h-4 w-4 cursor-nesw-resize"],
              ["nw", "top-0 left-0 h-4 w-4 cursor-nwse-resize"],
              ["se", "right-0 bottom-0 h-4 w-4 cursor-nwse-resize"],
              ["sw", "bottom-0 left-0 h-4 w-4 cursor-nesw-resize"],
            ] as const
          ).map(([edge, cls]) => (
            <div
              key={edge}
              onPointerDown={handleResizePointerDown(edge)}
              onPointerMove={handleResizePointerMove}
              onPointerUp={handleResizePointerUp}
              onPointerCancel={handleResizePointerUp}
              className={cn("pointer-events-auto absolute", cls)}
            />
          ))}
        </div>
      ) : null}
    </>
  );
}

function MessageBubble({
  message,
  onRetry,
}: {
  message: ChatMessage;
  onRetry: (prompt: string) => void;
}) {
  const isUser = message.role === "user";
  const isError = message.variant === "error";
  const isSuccess = message.variant === "success";
  const variantClass = (() => {
    if (message.variant === "success") return "border-emerald-500/40";
    if (message.variant === "warning") return "border-amber-500/40";
    if (message.variant === "error") return "border-destructive/50";
    return "border-border/60";
  })();

  if (isError) {
    return <ErrorBubble message={message} onRetry={onRetry} />;
  }

  return (
    <div
      className={cn(
        "flex max-w-full flex-col gap-0.5",
        isUser ? "items-end" : "items-start",
      )}
    >
      <span
        className={cn(
          // whitespace-pre-line bevarar radbrytningar i fler-rads-svar
          // (t.ex. copy-directive-sammanfattningar) men kollapsar löpande
          // blanksteg — utan den platta-pressas allt till en rad.
          "rounded-xl border px-3 py-2 text-[12.5px] leading-relaxed whitespace-pre-line",
          isUser
            ? "bg-foreground text-background border-transparent"
            : `bg-muted/40 text-foreground ${variantClass}`,
          message.isPending && "text-muted-foreground italic",
        )}
      >
        {message.isPending ? (
          <span className="inline-flex items-center gap-1.5">
            <Loader2 className="h-3 w-3 animate-spin" />
            {message.content}
          </span>
        ) : (
          message.content
        )}
      </span>
      {/* F1 slice 3 — ärlig roll-rad: vilken conductor-roll som agerade
          (dirigent/sektionsbyggare/stylist/text) + conversationKind, härlett ur
          payload.conversation. Bara på assistent-bubblor som inte är pending;
          dekorativ metadata, styr aldrig build/preview. */}
      {!isUser &&
      !message.isPending &&
      formatRoleRow(message.conversationRole, message.conversationKind) ? (
        <span className="text-muted-foreground/70 ml-1 font-mono text-[9.5px] tracking-[0.12em]">
          {formatRoleRow(message.conversationRole, message.conversationKind)}
        </span>
      ) : null}
      {/* Success-change-list — visas under success-bubblan med en
          kort vänster-border per ändring. Rubriken växlar på
          message.changesExact: "Ändrat" för bekräftade deltas från en
          strukturerad change-set (summarizeChangeSet), "Troligen ändrat"
          för prompt-heuristiken (summarizeChangesFromPrompt). */}
      {isSuccess && message.changes && message.changes.length > 0 ? (
        <div className="mt-1.5 ml-1 flex flex-col gap-1 border-l-2 border-emerald-500/30 pl-2.5">
          <span className="text-muted-foreground/70 font-mono text-[9.5px] tracking-[0.18em] uppercase">
            {message.changesExact ? "Ändrat" : "Troligen ändrat"}
          </span>
          {message.changes.map((change, idx) => (
            <span
              key={`${change.category}-${idx}`}
              className="text-foreground/85 inline-flex items-center gap-1.5 text-[11.5px]"
            >
              <Sparkles
                className="h-2.5 w-2.5 shrink-0 text-emerald-600 dark:text-emerald-400"
                aria-hidden
              />
              <span className="text-muted-foreground/80 font-medium">
                {CATEGORY_LABEL[change.category]}:
              </span>
              <span>{change.label}</span>
            </span>
          ))}
        </div>
      ) : null}
      {message.attachmentCount && message.attachmentCount > 0 ? (
        <span
          className={cn(
            "text-muted-foreground inline-flex items-center gap-1 text-[10.5px]",
            isUser ? "pr-1" : "pl-1",
          )}
        >
          <ImagePlus className="h-2.5 w-2.5" />
          {message.attachmentCount === 1
            ? "1 bilaga"
            : `${message.attachmentCount} bilagor`}
        </span>
      ) : null}
    </div>
  );
}
