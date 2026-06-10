import {
  AlertTriangle,
  Clock,
  ServerCrash,
  ShieldAlert,
  WifiOff,
} from "lucide-react";

import type { ErrorKind, QuickPromptCategory, Size } from "./types";

export const QUICK_PROMPT_CATEGORIES: ReadonlyArray<QuickPromptCategory> = [
  {
    id: "design",
    label: "Design",
    prompts: [
      "Använd en varmare färgpalett",
      "Mer luftig typografi och vitytor",
      "Mörkare bakgrund med ljusare accenter",
    ],
  },
  {
    id: "content",
    label: "Innehåll",
    prompts: [
      "Skriv om hero-rubriken så den är mer säljande",
      "Lägg till en sektion om vårt team",
      "Mer specifika beskrivningar i tjänsteblocken",
    ],
  },
  {
    id: "layout",
    label: "Layout",
    prompts: [
      "Centrera hero-sektionen",
      "Hero med bild bredvid (split-layout)",
      "Lägg till en gallery-sektion på startsidan",
    ],
  },
];

/**
 * Pending-bubblans label drivs nu av `useBuildTracePolling`-hooken
 * (GAP-viewser-pipeline-status-polling). Hooken pollar
 * /api/runs?siteId=X för att hitta pending-runen och switchar sedan
 * till /api/runs/[runId]/trace?since= för incrementala events. Phase
 * från trace.ndjson ("understand"/"plan"/"build") översätts till svenska
 * labels så operatören ser exakt vad pipen gör — inte en simulerad
 * tidskedja.
 *
 * Total-duration är hårdkodad till 30 s för progress-barens easing-ramp
 * (95 % på ~30 s, hopp till 100 % när /api/prompt-fetchen returnerar).
 * Det är bara en visuell ledtråd — den verkliga progress-signalen är
 * `tracePolling.currentPhase`-uppdateringen i pending-bubblan.
 */
export const PROGRESS_RAMP_DURATION_MS = 30_000;
export const INITIAL_BUILD_LABEL = "Bygger om sajten…";

/**
 * Returnera en ikon (lucide-react-komponent) per error-kind. Hålls
 * separat från `classifyFollowupError` så klassificeringen kan testas
 * utan React-bundlare och bubblan kan lägga till nya ikoner utan att
 * röra klassificeringen.
 */
export const ERROR_ICONS: Record<ErrorKind, typeof AlertTriangle> = {
  "rate-limit": Clock,
  timeout: Clock,
  schema: AlertTriangle,
  auth: ShieldAlert,
  quality: ServerCrash,
  network: WifiOff,
  generic: AlertTriangle,
};

export const ALLOWED_UPLOAD_MIMES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/svg+xml",
]);
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export const PANEL_WIDTH = 360;
export const PANEL_HEIGHT = 460;
export const PANEL_MIN_HEIGHT = 220;
// Resize-gränser (operatör-önskan 2026-06-07: dra i hörnen som ett
// webbläsarfönster). Bredden får inte bli smalare än chip-raden tål
// (~320) och inte bredare än att den täcker hela previewen i onödan.
// Höjden delar PANEL_MIN_HEIGHT som golv; taket clamp:as mot viewporten
// i clampSize så panelen + toolbar-raden alltid får plats.
export const PANEL_MIN_WIDTH = 320;
export const PANEL_MAX_WIDTH = 720;
export const PANEL_MAX_HEIGHT = 900;
export const VIEWPORT_PADDING = 16;
/**
 * Toolbar-pillen (375/768/1024/Full + Verktyg) sitter kant-i-kant
 * UNDER chat-panelen via `top: position.y + PANEL_HEIGHT`. När vi
 * clamp:ar drag/resize-position måste vi räkna med pillens egen höjd
 * (h-8 button + p-0.5 padding ≈ 36px) plus lite andnings-padding så
 * raden inte klipps av viewportens nederkant. Används som höjd-argument
 * till clampToViewport där tidigare bara PANEL_HEIGHT användes
 * (scout-fynd 2026-05-26: toolbar hamnade utanför viewporten vid
 * default-position nederst till höger).
 */
export const TOOLBAR_ROW_HEIGHT = 40;
/**
 * Hur många pixlar resize-handtagen sticker ut UTANFÖR fönsterkanten.
 * Handtags-lagret är ett fixed syskon till panelen (inte ett barn) så
 * det varken klipps av panelens overflow-hidden eller stannar innanför
 * bordern — man ska kunna greppa exakt på/utanför kanten precis som i
 * ett OS-fönster (operatörsfynd 2026-06-10: östkant/nederkant gick
 * inte att greppa eftersom yttersta pixlarna träffade bordern).
 */
export const RESIZE_HANDLE_OVERHANG = 4;

export const PANEL_DEFAULT_SIZE: Size = {
  width: PANEL_WIDTH,
  height: PANEL_HEIGHT,
};
