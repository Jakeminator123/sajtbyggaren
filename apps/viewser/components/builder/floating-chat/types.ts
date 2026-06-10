import type { ReactNode } from "react";

import type {
  PromptBuildOutcome,
  PromptStage,
} from "@/components/prompt-builder";
import type { BuildChange } from "@/lib/build-changes";

/**
 * Klassificering av error-meddelanden för rikare visuell + actionable
 * presentation. Mappar 1:1 mot ikon-paletten i ``ErrorBubble``.
 *
 * Klassificeringen sker en gång i ``classifyFollowupError`` när
 * meddelandet skapas, så MessageBubble kan vara dum presentations-
 * komponent utan att veta hur klassificering fungerar.
 */
export type ErrorKind =
  | "rate-limit"
  | "timeout"
  | "schema"
  | "auth"
  | "quality"
  | "network"
  | "generic";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  isPending?: boolean;
  variant?: "info" | "success" | "warning" | "error";
  /** Antal bilagor som skickades tillsammans med användarens prompt. */
  attachmentCount?: number;
  /**
   * För error-meddelanden: kort tip-text (visad mindre under huvud-
   * meddelandet) + den fulla error-strängen från servern (expanderbar
   * "Visa detaljer") + den ursprungliga prompten som operatören kan
   * retry:a med ett klick.
   */
  errorKind?: ErrorKind;
  errorTip?: string;
  errorDetails?: string;
  retryPrompt?: string;
  /**
   * För success-meddelanden: en kort lista över ändringar. Källan
   * avgörs av `changesExact`:
   *   - `true`  → bekräftade deltas från en strukturerad change-set
   *     (`summarizeChangeSet`), renderas under "Ändrat".
   *   - falsy   → prompt-heuristik (`summarizeChangesFromPrompt`),
   *     renderas under "Troligen ändrat".
   */
  changes?: BuildChange[];
  /** True när `changes` kommer från en exakt change-set, inte heuristik. */
  changesExact?: boolean;
  /**
   * F1 slice 3: vilken conductor-roll som agerade på följdprompten
   * (router/section_builder/stylist/copy) + dess conversationKind, härlett ur
   * `payload.conversation`. Renderas som en ärlig roll-rad under bubblan i
   * FloatingChat. Valfria → äldre/utelämnade payloads visar ingen rad.
   */
  conversationRole?: string | null;
  conversationKind?: string | null;
};

/**
 * Snabbförslag-chips, kategoriserade. Visas under en collapsed
 * "Förslag"-toggle ovanför textarean när input är tomt och inga
 * bilagor är pending.
 *
 * Designprinciper för formuleringen av prompts:
 * - Konkreta verb ("Centrera", "Lägg till", "Byt") — inte vaga
 *   substantiv ("Färgschema").
 * - Adresserar features som faktiskt finns i build_site.py
 *   (gradient/centered/split hero, gallery-sektion, FAQ-sektion,
 *   USP-chips, story-sektion). Operatören får inte föreslagna
 *   ändringar som pipelinen inte kan utföra deterministiskt.
 * - Kort nog att rymmas i panelens 360px-bredd som chip, men
 *   tillräckligt specifika för att brief-modellen ska kunna
 *   producera bra dossier-deltas.
 * - Tre kategorier: Design (visuell stil), Innehåll (nya/ändrade
 *   sektioner), Layout (struktur). Kategori-labels är medvetet
 *   svenska för att matcha hela operatör-UI:t.
 */
export type QuickPromptCategory = {
  id: "design" | "content" | "layout";
  label: string;
  prompts: ReadonlyArray<string>;
};

export type FloatingChatProps = {
  /** Sajten vi gör follow-ups på (måste vara prompt-genererad). */
  siteId: string;
  /** Anropas när en follow-up-build är klar — page.tsx väljer den nya runen. */
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
  /** Sätts under hela /api/prompt-cykeln av builder-shell så UI:t kan blockera dubbel-submit. */
  isBuilding: boolean;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  /**
   * Rapporterar bygg-stage (idle/thinking/building/success/failed) uppåt så
   * page.tsx kan driva ViewerPanel:s BuildProgressCard under follow-ups. Utan
   * den frös buildStage på föregående bygges sista värde (oftast "success")
   * och stegmarkören hoppade direkt till sista steget vid varje följdprompt.
   * Stegen drivs av den riktiga trace.ndjson-signalen (useBuildTracePolling),
   * inte av en setTimeout-flip (jfr B122).
   */
  onStageChange?: (stage: PromptStage) => void;
  /**
   * "Iterera från denna" — när satt skickar nästa /api/prompt-fetch med
   * `baseRunId` så backend laddar PI-snapshotet från den runen istället
   * för senaste. Operatören sätter via Versions-tab. Rensas via
   * `onClearBaseRunId` direkt efter en lyckad submit eller när operatören
   * klickar "Avbryt iterera"-pilllen i composern.
   */
  pendingBaseRunId?: { baseRunId: string; baseVersion: number | null } | null;
  onClearBaseRunId?: () => void;
  /**
   * Öppnar versionsvyn (ConsoleDrawer-historiken). Driver "Visa
   * versioner"-knappen i första-gångs-hinten så operatören direkt ser
   * var tidigare bygg bor. Valfri — utelämnas → knappen döljs.
   */
  onShowVersions?: () => void;
  /**
   * Slot för extra UI som rendras i samma centrerade toolbar-rad UNDER
   * chat-panelen (till höger om device-preset-toggle). Typiskt
   * `<BuilderActions variant="inline" ... />`. Renderas bara på desktop
   * när panelen inte är minimerad.
   */
  tools?: ReactNode;
  /**
   * UX-glue (msg-0050 b): en räknare som BuilderShell bumpar varje gång ETT
   * BYGGE FRÅN EN ANNAN YTA (en dialog eller inspector-snabbprompt) blir klart
   * (ok/degraded). När värdet ändras expanderar FloatingChat ur minimerat läge
   * och flyttar focus till composern så operatören kan skriva nästa följdprompt
   * direkt — utan att först leta upp/öppna chatten. FloatingChat:s EGNA byggen
   * bumpar den INTE (composern har redan focus där). Initialt 0 / utelämnad →
   * ingen effekt vid mount (vi jämför mot föregående värde via en ref).
   */
  focusComposerSignal?: number;
  /**
   * Sektionsmenyns "Ändra text"-åtgärd (klick på sektion i previewns
   * markläge): förifyll composern med en promptstart ('Ändra texten i
   * sektionen "…": ') och flytta focus dit. ``nonce`` bumpas per request
   * så två likadana prefills i rad ändå triggar (jämförs mot föregående
   * värde via en ref — mount har ingen effekt). Själva chippen läggs av
   * overlayn via markedSections; prefill:en rör bara input-texten och
   * skriver medvetet ÖVER ev. halvskriven text (operatören valde just
   * en ny åtgärd).
   */
  composerPrefill?: { text: string; nonce: number } | null;
};

/**
 * Strikt typad copy-direktiv-shape som speglar
 * ``governance/schemas/project-input.schema.json:directives.copyDirectives``.
 * Måste hållas i synk med ``AppliedCopyDirective`` i
 * ``apps/viewser/lib/runs.ts``. Den extra typen här finns så FloatingChat
 * inte tar ett direkt ``import`` på server-only path utan får sin
 * egen client-bundle-säkra typ.
 */
export type AppliedCopyDirective = {
  target: "company-name" | "tagline" | "about-text" | "services";
  operation: "replace-text" | "include-token";
  payload: string;
  // Pekar ut vilken tjänst (services[].id|label) ett services-direktiv träffar.
  // Krävs av schemat när target=services, utelämnas annars.
  targetRef?: string;
  source?: "prompt-rule" | "llm" | "explicit";
};

export type Position = { x: number; y: number };
export type Size = { width: number; height: number };

// --- KÖR-6a RouterDecision-readiness ---------------------------------------
// Stängda enum-litteraler speglade från
// governance/schemas/router-decision.schema.json. Vi mirrorar bara de fält
// summarizeRouterDecision faktiskt grenar på; resten av kontraktet ignoreras
// medvetet (UI:t ska inte koppla sig hårt till hela router-shapen).
export type RouterMessageKind =
  | "answer_only"
  | "site_review"
  | "edit_instruction"
  | "component_discovery"
  | "reference_analysis"
  | "bug_report"
  | "multi_intent"
  | "unclear";

export type RouterBuildRequirement =
  | "none"
  | "plan_only"
  | "artifact_patch_only"
  | "targeted_rebuild"
  | "full_rebuild";

export type RouterDecisionView = {
  messageKind: RouterMessageKind;
  buildRequirement: RouterBuildRequirement;
  requiresClarification: boolean;
  subtaskCount: number;
};

// Skiva 1b (UI half): OpenClaw Core V0:s action-enum, speglar
// ``OpenClawAction`` i packages/generation/orchestration/openclaw/models.py.
export type OpenClawAction =
  | "answer_only"
  | "clarification"
  | "plan_only"
  | "patch_plan_request";

export type OpenClawDecisionView = {
  action: OpenClawAction;
  answer: string | null;
  clarifyingQuestion: string | null;
  plan: string[];
  patchTargetSummary: string | null;
};

// Skiva 1b (action bridge): OpenClaw-apply-utfallet. När /api/prompt rutade
// follow-upen genom ``run_openclaw_followup.py --apply`` och KÖR-7-kedjan
// MATERIALISERADE en ny version (restyle/capability) bär ``bridge``
// { applied, previewShouldRefresh, chain:{ editKind, version, previousVersion } }.
// Avläses defensivt (samma fält-drift-säkra mönster som extractOpenClawDecision).
export type OpenClawBridgeView = {
  applied: boolean;
  previewShouldRefresh: boolean;
  editKind: string | null;
  version: number | null;
  previousVersion: number | null;
};
