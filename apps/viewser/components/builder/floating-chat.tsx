"use client";

import {
  ChevronUp,
  ImagePlus,
  Loader2,
  MessageSquare,
  Minus,
  Send,
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

import {
  classifyBuildStatus,
  type PromptBuildOutcome,
} from "@/components/prompt-builder";
import { Textarea } from "@/components/ui/textarea";
import type { AssetRef } from "@/lib/asset-store/types";
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

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  isPending?: boolean;
  variant?: "info" | "success" | "warning" | "error";
  /** Antal bilagor som skickades tillsammans med användarens prompt. */
  attachmentCount?: number;
};

/**
 * Snabbförslag-chips. Visas ovanför textarean när input är tomt och
 * inga bilagor är pending — tanken är att operatören får tydliga,
 * vanliga "ändra-en-byggd-sajt"-avsikter inom räckhåll utan att
 * behöva tänka från noll. Klick fyller textarean (operatören kan
 * finslipa innan skicka).
 */
const QUICK_PROMPTS: ReadonlyArray<string> = [
  "Ändra färgschemat",
  "Lägg till en sida",
  "Byt hero-bild",
  "Mer innehåll på startsidan",
  "Starkare CTA",
];

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
): { content: string; variant: ChatMessage["variant"] } {
  if (outcome === "ok") {
    const versionText =
      typeof payload.version === "number" ? ` (v${payload.version})` : "";
    return {
      content: `Klart${versionText}. Previewen uppdateras automatiskt.`,
      variant: "success",
    };
  }
  if (outcome === "degraded") {
    return {
      content:
        "Sajten byggdes, men något beteende avvek från Quality Gate. Kolla konsolen för detaljer.",
      variant: "warning",
    };
  }
  if (outcome === "failed") {
    return {
      content: "Bygget misslyckades. Prova en mer specifik instruktion.",
      variant: "error",
    };
  }
  return {
    content: "Bygget returnerade okänd status. Kontrollera konsolen.",
    variant: "warning",
  };
}

export function FloatingChat({
  siteId,
  onBuildDone,
  isBuilding,
  onBuildStart,
  onBuildEnd,
}: FloatingChatProps) {
  const [position, setPosition] = useState<Position | null>(null);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
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
  const dragStartRef = useRef<{
    pointerX: number;
    pointerY: number;
    originX: number;
    originY: number;
  } | null>(null);
  const headerRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (isMinimized) return;
      if (event.button !== 0) return;
      if (!position) return;
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
      const pendingMessage: ChatMessage = {
        id: `pending-${Date.now()}`,
        role: "assistant",
        content: "Bygger om sajten…",
        isPending: true,
        variant: "info",
      };
      setMessages((prev) => [...prev, userMessage, pendingMessage]);
      setInput("");
      setAttachments([]);
      setUploadError(null);
      setIsSending(true);
      onBuildStart();

      try {
        const response = await fetch("/api/prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: promptText,
            mode: "followup",
            siteId,
          }),
        });
        const payload = (await response.json()) as PromptApiResponse;
        if (!response.ok || !payload.runId || !payload.siteId) {
          const errorText =
            payload.error ??
            `Prompt-anropet misslyckades (HTTP ${response.status})`;
          setMessages((prev) =>
            prev
              .filter((m) => m.id !== pendingMessage.id)
              .concat({
                id: `error-${Date.now()}`,
                role: "assistant",
                content: errorText,
                variant: "error",
              }),
          );
          return;
        }
        const outcome = classifyBuildStatus(payload.buildStatus);
        const summary = summarizeBuildResult(payload, outcome);
        setMessages((prev) =>
          prev
            .filter((m) => m.id !== pendingMessage.id)
            .concat({
              id: `done-${Date.now()}`,
              role: "assistant",
              content: summary.content,
              variant: summary.variant,
            }),
        );
        onBuildDone(payload.runId, outcome);
      } catch (caught) {
        const errorText =
          caught instanceof Error ? caught.message : "Okänt fel.";
        setMessages((prev) =>
          prev
            .filter((m) => m.id !== pendingMessage.id)
            .concat({
              id: `error-${Date.now()}`,
              role: "assistant",
              content: errorText,
              variant: "error",
            }),
        );
      } finally {
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
    ],
  );

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
    // sätts. Använder bottom-right som default-position.
    return (
      <aside
        aria-label="Sajtmaskin-chatt"
        className="border-border/60 bg-card/95 pointer-events-auto fixed right-6 bottom-6 z-40 flex w-[360px] flex-col rounded-2xl border shadow-2xl backdrop-blur-xl"
        style={{ height: PANEL_HEIGHT }}
      >
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
    return (
      <button
        type="button"
        onClick={() => setIsMinimized(false)}
        aria-label="Återställ chatten"
        className={cn(
          "border-border/60 bg-card/95 text-foreground pointer-events-auto fixed z-40 flex h-11 items-center gap-2 rounded-full border px-3.5 text-[12px] font-medium shadow-2xl backdrop-blur-xl",
          "hover:bg-card focus-visible:ring-ring/50 transition-colors focus-visible:ring-2 focus-visible:outline-none",
        )}
        style={{
          left: position.x,
          top: position.y + PANEL_HEIGHT - 44,
        }}
      >
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            isBuilding
              ? "bg-amber-500 motion-safe:animate-pulse"
              : "bg-emerald-500",
          )}
          aria-hidden
        />
        <MessageSquare className="text-muted-foreground h-3.5 w-3.5" />
        Sajtmaskin
      </button>
    );
  }

  return (
    <aside
      aria-label="Sajtmaskin-chatt"
      className={cn(
        "border-border/60 bg-card/95 pointer-events-auto fixed z-40 flex w-[360px] flex-col overflow-hidden rounded-2xl border shadow-2xl backdrop-blur-xl",
        isDragging
          ? "cursor-grabbing transition-none"
          : "motion-safe:transition-[box-shadow] motion-safe:duration-150",
      )}
      style={{
        left: position.x,
        top: position.y,
        height: PANEL_HEIGHT,
        minHeight: PANEL_MIN_HEIGHT,
      }}
    >
      <div
        ref={headerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        className={cn(
          "border-border/60 bg-card/90 flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2 select-none",
          isDragging ? "cursor-grabbing" : "cursor-grab",
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
            className="text-muted-foreground hover:text-foreground hover:bg-muted/60 inline-flex h-6 w-6 items-center justify-center rounded-md"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setIsMinimized(true)}
            aria-label="Stäng (minimera)"
            title="Stäng (öppnas igen från bubblan)"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/60 inline-flex h-6 w-6 items-center justify-center rounded-md"
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
              <MessageBubble message={message} />
            </li>
          ))}
        </ol>
      </div>

      <div className="border-border/60 bg-card/90 shrink-0 border-t p-2">
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
                "inline-flex h-5 w-9 items-center justify-center rounded-full",
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
                className="mt-1.5 flex w-full flex-wrap justify-center gap-1"
              >
                {QUICK_PROMPTS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => {
                      setInput(suggestion);
                      setQuickPromptsOpen(false);
                    }}
                    className={cn(
                      "border-border/60 bg-background/80 text-foreground/80",
                      "hover:border-border hover:bg-card hover:text-foreground",
                      "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
                      "rounded-full border px-2 py-0.5 text-[10.5px] transition-colors",
                    )}
                  >
                    {suggestion}
                  </button>
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
                  className="text-muted-foreground hover:text-foreground inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded"
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
            className="min-h-[60px] resize-none border-0 bg-transparent px-3 py-2 text-[13px] shadow-none focus-visible:ring-0"
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
                  "inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors",
                  "disabled:opacity-40 disabled:hover:bg-transparent",
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
                "bg-foreground text-background inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11.5px] font-medium",
                "hover:bg-foreground/90 disabled:opacity-40",
                "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
              )}
            >
              {isSending || isBuilding ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" />
              )}
              {isSending || isBuilding ? "Bygger" : "Skicka"}
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

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const variantClass = (() => {
    if (message.variant === "success") return "border-emerald-500/40";
    if (message.variant === "warning") return "border-amber-500/40";
    if (message.variant === "error") return "border-destructive/50";
    return "border-border/60";
  })();
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
