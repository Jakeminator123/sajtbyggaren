"use client";

import {
  AlertTriangle,
  ChevronLeft,
  ChevronUp,
  Clock,
  GitBranch,
  ImagePlus,
  Loader2,
  MessageSquare,
  Minus,
  RotateCcw,
  Send,
  ServerCrash,
  ShieldAlert,
  Sparkles,
  WifiOff,
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
  classifyBuildStatus,
  type PromptBuildOutcome,
} from "@/components/prompt-builder";
import { Textarea } from "@/components/ui/textarea";
import type { AssetRef } from "@/lib/asset-store/types";
import {
  CATEGORY_LABEL,
  summarizeChangesFromPrompt,
  type BuildChange,
} from "@/lib/build-changes";
import {
  CHIP_INTERACTIONS,
  PRIMARY_INTERACTIONS,
  SECONDARY_INTERACTIONS,
} from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

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

/**
 * Klassificering av error-meddelanden för rikare visuell + actionable
 * presentation. Mappar 1:1 mot ikon-paletten i ``ErrorBubble``.
 *
 * Klassificeringen sker en gång i ``classifyFollowupError`` när
 * meddelandet skapas, så MessageBubble kan vara dum presentations-
 * komponent utan att veta hur klassificering fungerar.
 */
type ErrorKind =
  | "rate-limit"
  | "timeout"
  | "schema"
  | "auth"
  | "quality"
  | "network"
  | "generic";

type ChatMessage = {
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
   * För success-meddelanden: en kort lista över ändringar som
   * troligen gjordes baserat på operatörens prompt. Heuristik från
   * `summarizeChangesFromPrompt` — backend exponerar ingen exakt
   * diff än, men detta ger operatören en känsla av vad som hänt
   * utan att öppna Inspectorn.
   */
  changes?: BuildChange[];
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
type QuickPromptCategory = {
  id: "design" | "content" | "layout";
  label: string;
  prompts: ReadonlyArray<string>;
};

const QUICK_PROMPT_CATEGORIES: ReadonlyArray<QuickPromptCategory> = [
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
const PROGRESS_RAMP_DURATION_MS = 30_000;
const INITIAL_BUILD_LABEL = "Bygger om sajten…";

/**
 * Tolka ett backend-felmeddelande och returnera en kort, åtgärdsbar
 * text + ett "tips" för operatören. Vi ser specifika fel oftast
 * (OpenAI/Anthropic rate-limits, schema-valideringar, timeout) och
 * vill ge användaren något konkret att göra istället för bara
 * generic "Bygget misslyckades".
 *
 * Mappningen bygger på faktiska error-strängar från
 * `apps/viewser/lib/build-runner.ts` och `scripts/build_site.py`.
 * När en sträng inte matchar någon känd kategori returneras en
 * generic-tip som ändå är bättre än "okänt fel".
 */
function classifyFollowupError(rawError: string): {
  kind: ErrorKind;
  message: string;
  tip: string;
} {
  const text = rawError.toLowerCase();
  if (text.includes("rate limit") || text.includes("429")) {
    return {
      kind: "rate-limit",
      message: "AI-tjänsten är överbelastad just nu.",
      tip: "Vänta 10–20 sekunder och försök igen.",
    };
  }
  if (text.includes("timeout") || text.includes("timed out")) {
    return {
      kind: "timeout",
      message: "Bygget tog för lång tid.",
      tip: "Prova en mindre, mer specifik ändring.",
    };
  }
  if (
    text.includes("schema") ||
    text.includes("validation") ||
    text.includes("invalid")
  ) {
    return {
      kind: "schema",
      message: "Sajtens struktur kunde inte uppdateras automatiskt.",
      tip: "Beskriv ändringen mer konkret (vilken sektion, vad ska ändras).",
    };
  }
  if (text.includes("openai") || text.includes("anthropic") || text.includes("api key")) {
    return {
      kind: "auth",
      message: "AI-tjänsten är otillgänglig.",
      tip: "Kontrollera att .env.local har giltig OPENAI_API_KEY.",
    };
  }
  if (text.includes("quality") || text.includes("typecheck") || text.includes("build failed")) {
    return {
      kind: "quality",
      message: "Den nya versionen klarade inte Quality Gate.",
      tip: "Pipelinen avbröt automatiskt — sajten är oförändrad. Prova en mer specifik instruktion.",
    };
  }
  if (text.includes("network") || text.includes("fetch") || text.includes("econnreset")) {
    return {
      kind: "network",
      message: "Nätverket avbröts.",
      tip: "Kontrollera anslutningen och försök igen.",
    };
  }
  return {
    kind: "generic",
    message: rawError.length > 200 ? rawError.slice(0, 200) + "…" : rawError,
    tip: "Prova en mer specifik instruktion eller dela upp ändringen i flera steg.",
  };
}

/**
 * Returnera en ikon (lucide-react-komponent) per error-kind. Hålls
 * separat från `classifyFollowupError` så klassificeringen kan testas
 * utan React-bundlare och bubblan kan lägga till nya ikoner utan att
 * röra klassificeringen.
 */
const ERROR_ICONS: Record<ErrorKind, typeof AlertTriangle> = {
  "rate-limit": Clock,
  timeout: Clock,
  schema: AlertTriangle,
  auth: ShieldAlert,
  quality: ServerCrash,
  network: WifiOff,
  generic: AlertTriangle,
};

const ALLOWED_UPLOAD_MIMES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/svg+xml",
]);
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

type FloatingChatProps = {
  /** Sajten vi gör follow-ups på (måste vara prompt-genererad). */
  siteId: string;
  /** Anropas när en follow-up-build är klar — page.tsx väljer den nya runen. */
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
  /** Sätts under hela /api/prompt-cykeln av builder-shell så UI:t kan blockera dubbel-submit. */
  isBuilding: boolean;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  /**
   * "Iterera från denna" — när satt skickar nästa /api/prompt-fetch med
   * `baseRunId` så backend laddar PI-snapshotet från den runen istället
   * för senaste. Operatören sätter via Versions-tab. Rensas via
   * `onClearBaseRunId` direkt efter en lyckad submit eller när operatören
   * klickar "Avbryt iterera"-pilllen i composern.
   */
  pendingBaseRunId?: { baseRunId: string; baseVersion: number | null } | null;
  onClearBaseRunId?: () => void;
};

type PromptApiResponse = {
  runId?: string;
  siteId?: string;
  version?: number | null;
  buildStatus?: string | null;
  briefSource?: string | null;
  error?: string;
};

type Position = { x: number; y: number };

const PANEL_WIDTH = 360;
const PANEL_HEIGHT = 460;
const PANEL_MIN_HEIGHT = 220;
const VIEWPORT_PADDING = 16;
const STORAGE_KEY_POSITION = "sajtbyggaren:floating-chat:position";
const STORAGE_KEY_MINIMIZED = "sajtbyggaren:floating-chat:minimized";
const STORAGE_KEY_QUICK_PROMPTS = "sajtbyggaren:floating-chat:quick-prompts";

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
    const update = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return isMobile;
}

/**
 * useKeyboardInset — returnerar antalet pixlar som virtuella tangent-
 * bordet täcker av viewporten på iOS Safari. Driver bottom-offset på
 * bottom-sheet-panelen så att composern aldrig hamnar under tangent-
 * bordet när operatören skriver.
 *
 * Implementation via `window.visualViewport`-API:t som specifikt rapporterar
 * sektionen som faktiskt är synlig för användaren (inte hela window).
 * Skillnaden `innerHeight - visualViewport.height - visualViewport.offsetTop`
 * = höjden av det som ligger nedanför synlig viewport, dvs keyboard.
 *
 * Disabled när `enabled` är false (vi vill inte lyssna på dessa events
 * när chatten är minimerad eller desktop-läge är aktivt).
 */
function useKeyboardInset(enabled: boolean): number {
  const [inset, setInset] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined") return;
    const vv = window.visualViewport;
    if (!vv) return;
    const update = () => {
      const offset = window.innerHeight - vv.height - vv.offsetTop;
      setInset(Math.max(0, Math.round(offset)));
    };
    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, [enabled]);
  return inset;
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

function clampToViewport(
  pos: Position,
  width: number,
  height: number,
): Position {
  if (typeof window === "undefined") return pos;
  const maxX = Math.max(
    VIEWPORT_PADDING,
    window.innerWidth - width - VIEWPORT_PADDING,
  );
  const maxY = Math.max(
    VIEWPORT_PADDING,
    window.innerHeight - height - VIEWPORT_PADDING,
  );
  return {
    x: Math.min(Math.max(VIEWPORT_PADDING, pos.x), maxX),
    y: Math.min(Math.max(VIEWPORT_PADDING, pos.y), maxY),
  };
}

function defaultPosition(width: number, height: number): Position {
  if (typeof window === "undefined") return { x: 0, y: 0 };
  return clampToViewport(
    {
      x: window.innerWidth - width - VIEWPORT_PADDING,
      y: window.innerHeight - height - VIEWPORT_PADDING,
    },
    width,
    height,
  );
}

function summarizeBuildResult(
  payload: PromptApiResponse,
  outcome: PromptBuildOutcome,
  userPrompt: string,
): {
  content: string;
  variant: ChatMessage["variant"];
  changes?: BuildChange[];
} {
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
    const changes = summarizeChangesFromPrompt(userPrompt);
    return {
      content: `Klart!${versionText} Previewen laddas om automatiskt.`,
      variant: "success",
      changes: changes.length > 0 ? changes : undefined,
    };
  }
  if (outcome === "degraded") {
    return {
      content:
        "Sajten byggdes, men Quality Gate flaggade något (typecheck, route-scan eller policy). Sajten har ändå publicerats — se Inspector för detaljer.",
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
    content: "Bygget returnerade okänd status. Kontrollera Inspector → Quality Gate.",
    variant: "warning",
  };
}

export function FloatingChat({
  siteId,
  onBuildDone,
  isBuilding,
  onBuildStart,
  onBuildEnd,
  pendingBaseRunId,
  onClearBaseRunId,
}: FloatingChatProps) {
  const [position, setPosition] = useState<Position | null>(null);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  // På mobil (<768px) renderas panelen som bottom-sheet utan drag/
  // position-hantering. Hooken returnerar false under SSR och vid
  // initial hydration; skiftar till true post-mount om matchMedia
  // träffar.
  const isMobile = useIsMobileViewport();
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
  const headerRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Ref till composer-textarea så vi kan flytta focus dit när panelen
  // expanderas från minimerat läge (annars stannar tangentbords-focus
  // på FAB-knappen och operatören måste Tab:a sig in i textfältet).
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  // Expandera panelen + flytta focus till composer i samma callback.
  // setTimeout(0) säkerställer att React renderat panelen + textarean
  // innan vi anropar focus() — annars är composerRef.current null.
  const expandAndFocus = useCallback(() => {
    setIsMinimized(false);
    setTimeout(() => {
      composerRef.current?.focus();
    }, 50);
  }, []);

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
      const stored = readStoredPosition();
      const initial = stored
        ? clampToViewport(stored, PANEL_WIDTH, PANEL_HEIGHT)
        : defaultPosition(PANEL_WIDTH, PANEL_HEIGHT);
      setPosition(initial);
      setIsMinimized(readStoredMinimized());
      setQuickPromptsOpen(readStoredQuickPromptsOpen());
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Håll position innanför viewport vid resize.
  useEffect(() => {
    function handleResize() {
      setPosition((current) => {
        if (!current) return current;
        return clampToViewport(current, PANEL_WIDTH, PANEL_HEIGHT);
      });
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Persistera position.
  useEffect(() => {
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
    try {
      window.localStorage.setItem(STORAGE_KEY_MINIMIZED, String(isMinimized));
    } catch {
      // Tyst.
    }
  }, [isMinimized]);

  // Persistera quick-prompts-toggle.
  useEffect(() => {
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
      setPosition(
        clampToViewport(
          { x: start.originX + dx, y: start.originY + dy },
          PANEL_WIDTH,
          PANEL_HEIGHT,
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
      setUploadError(null);
      setBuildProgress(0);
      setIsSending(true);
      onBuildStart();

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
          }),
        });
        const payload = (await response.json()) as PromptApiResponse;
        if (!response.ok || !payload.runId || !payload.siteId) {
          const errorText =
            payload.error ??
            `Prompt-anropet misslyckades (HTTP ${response.status})`;
          const classified = classifyFollowupError(errorText);
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
            }),
        );
        onBuildDone(payload.runId, outcome);
      } catch (caught) {
        const errorText =
          caught instanceof Error ? caught.message : "Okänt fel.";
        const classified = classifyFollowupError(errorText);
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
      isSending,
      isBuilding,
      isUploading,
      siteId,
      onBuildStart,
      onBuildEnd,
      onBuildDone,
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
  const tracePolling = useBuildTracePolling(siteId, { enabled: isSending });
  useEffect(() => {
    const id = pendingMessageIdRef.current;
    if (!id) return;
    if (!tracePolling.isPending && tracePolling.runStatus === null) return;
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: tracePolling.label } : m)),
    );
  }, [tracePolling.label, tracePolling.isPending, tracePolling.runStatus]);

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
          isMobile
            ? "inset-x-0 bottom-0 max-h-[85dvh] w-full rounded-t-3xl pb-safe"
            : "right-6 bottom-6 w-[360px] rounded-2xl",
        )}
        style={isMobile ? undefined : { height: PANEL_HEIGHT }}
      >
        {isMobile && (
          <div aria-hidden className="bottom-sheet-handle" />
        )}
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
            "active:scale-95 transition-transform",
            "bottom-safe-4",
          )}
        >
          <MessageSquare
            aria-hidden
            className="text-foreground/80 h-5 w-5"
          />
          <span
            aria-hidden
            className={cn(
              "absolute top-1.5 right-1.5 h-2 w-2 rounded-full ring-2 ring-card",
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
            "border-border/60 bg-card/95 text-foreground flex h-14 items-center gap-2 rounded-l-2xl border border-r-0 pl-2.5 pr-3 backdrop-blur-xl",
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
    <aside
      aria-label="Sajtmaskin-chatt"
      className={cn(
        "border-border/60 bg-card/95 pointer-events-auto fixed z-40 flex flex-col overflow-hidden border shadow-2xl backdrop-blur-xl",
        // Mobil = bottom-sheet (full bredd, kapad höjd, safe-area).
        // Desktop = 360px floating panel med inline position-state.
        isMobile
          ? "inset-x-0 bottom-0 w-full max-h-[85dvh] rounded-t-3xl pb-safe"
          : "w-[360px] rounded-2xl",
        isDragging
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
              height: PANEL_HEIGHT,
              minHeight: PANEL_MIN_HEIGHT,
            }
      }
    >
      {isMobile && (
        <div aria-hidden className="bottom-sheet-handle" />
      )}
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
            className="text-muted-foreground hover:text-foreground hover:bg-muted/60 inline-flex min-tap sm:min-tap-0 sm:h-6 sm:w-6 items-center justify-center rounded-md active:scale-95"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setIsMinimized(true)}
            aria-label="Stäng (minimera)"
            title="Stäng (öppnas igen från bubblan)"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/60 inline-flex min-tap sm:min-tap-0 sm:h-6 sm:w-6 items-center justify-center rounded-md active:scale-95"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

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
              className="bg-foreground/80 motion-safe:transition-[width] motion-safe:duration-500 absolute inset-y-0 left-0"
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
                  "hover:bg-sky-500/15 min-tap sm:min-tap-0 inline-flex h-5 w-5 items-center justify-center rounded-full active:scale-95",
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
                "min-tap sm:min-tap-0 inline-flex h-5 w-9 items-center justify-center rounded-full active:scale-95",
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
                      className="text-muted-foreground/60 px-0.5 text-[9.5px] font-medium uppercase tracking-widest"
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
                            "min-tap sm:min-tap-0 rounded-full border px-2.5 py-1 text-[11px] transition-colors active:scale-95 sm:px-2 sm:py-0.5 sm:text-[10.5px]",
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
                  className="text-muted-foreground hover:text-foreground min-tap sm:min-tap-0 inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded active:scale-95"
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
            className="min-h-[60px] resize-none border-0 bg-transparent px-3 py-2 text-base md:text-[13px] shadow-none focus-visible:ring-0"
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
                  "inline-flex min-tap sm:min-tap-0 sm:h-6 sm:w-6 items-center justify-center rounded-md transition-colors",
                  "disabled:opacity-40 disabled:hover:bg-transparent active:scale-95",
                )}
              >
                {isUploading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ImagePlus className="h-3.5 w-3.5" />
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
                "bg-foreground text-background inline-flex min-h-[44px] sm:min-h-0 sm:h-7 items-center gap-1.5 rounded-md px-3.5 sm:px-2.5 text-sm sm:text-[11.5px] font-medium",
                "hover:bg-foreground/90 disabled:opacity-40 active:scale-95",
                "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                PRIMARY_INTERACTIONS,
              )}
            >
              {isSending || isBuilding ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" />
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
    return (
      <ErrorBubble message={message} onRetry={onRetry} />
    );
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
          "rounded-xl border px-3 py-2 text-[12.5px] leading-relaxed",
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
      {/* Success-change-list — visas under success-bubblan med en
          kort vänster-border per ändring. Heuristik från
          summarizeChangesFromPrompt, tas bort den dag backend
          exponerar en strukturerad diff (då används payload-data
          istället för operatörens prompt). */}
      {isSuccess && message.changes && message.changes.length > 0 ? (
        <div className="border-emerald-500/30 mt-1.5 ml-1 flex flex-col gap-1 border-l-2 pl-2.5">
          <span className="text-muted-foreground/70 font-mono text-[9.5px] tracking-[0.18em] uppercase">
            Troligen ändrat
          </span>
          {message.changes.map((change, idx) => (
            <span
              key={`${change.category}-${idx}`}
              className="text-foreground/85 inline-flex items-center gap-1.5 text-[11.5px]"
            >
              <Sparkles
                className="text-emerald-600 dark:text-emerald-400 h-2.5 w-2.5 shrink-0"
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

/**
 * ErrorBubble — rik error-presentation med kategori-ikon, tip-text,
 * expanderbar tekniska detaljer och retry-knapp.
 *
 * Designval: en separat komponent istället för att svälla MessageBubble
 * med fler conditionals. Egen state för detail-expand (öppnar inte
 * automatiskt vid mount för att hålla bubblan kompakt).
 */
function ErrorBubble({
  message,
  onRetry,
}: {
  message: ChatMessage;
  onRetry: (prompt: string) => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const Icon = message.errorKind ? ERROR_ICONS[message.errorKind] : AlertTriangle;
  const canRetry =
    typeof message.retryPrompt === "string" && message.retryPrompt.length > 0;
  const hasDetails =
    typeof message.errorDetails === "string" &&
    message.errorDetails.length > 0 &&
    message.errorDetails !== message.content;
  return (
    <div className="flex max-w-full flex-col items-start gap-0.5">
      <div className="border-destructive/40 bg-destructive/[0.04] text-foreground flex flex-col gap-1.5 rounded-xl border px-3 py-2 text-[12.5px] leading-relaxed">
        <div className="flex items-start gap-2">
          <Icon
            className="text-destructive mt-0.5 h-3.5 w-3.5 shrink-0"
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <p className="text-foreground font-medium">{message.content}</p>
            {message.errorTip ? (
              <p className="text-muted-foreground mt-0.5 text-[11.5px] leading-snug">
                {message.errorTip}
              </p>
            ) : null}
          </div>
        </div>
        {(canRetry || hasDetails) && (
          <div className="border-destructive/20 mt-0.5 flex flex-wrap items-center gap-2 border-t pt-1.5">
            {canRetry ? (
              <button
                type="button"
                onClick={() => onRetry(message.retryPrompt as string)}
                className={cn(
                  "text-foreground/85 hover:text-foreground border-border/60 hover:border-foreground/40 hover:bg-muted/60",
                  "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors",
                  SECONDARY_INTERACTIONS,
                )}
                title="Skicka samma instruktion igen"
              >
                <RotateCcw className="h-3 w-3" aria-hidden />
                Försök igen
              </button>
            ) : null}
            {hasDetails ? (
              <button
                type="button"
                onClick={() => setDetailsOpen((prev) => !prev)}
                aria-expanded={detailsOpen}
                className={cn(
                  "text-muted-foreground hover:text-foreground",
                  "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
                  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium transition-colors",
                )}
              >
                {detailsOpen ? "Dölj detaljer" : "Visa detaljer"}
              </button>
            ) : null}
          </div>
        )}
        {detailsOpen && hasDetails ? (
          <pre className="bg-background/60 border-border/50 text-muted-foreground mt-1 max-h-32 overflow-auto rounded border px-2 py-1.5 font-mono text-[10.5px] whitespace-pre-wrap">
            {message.errorDetails}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
