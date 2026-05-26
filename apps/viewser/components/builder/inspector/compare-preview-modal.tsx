"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import {
  AlertTriangle,
  ExternalLink,
  Loader2,
  X as XIcon,
} from "lucide-react";
import { forwardRef, useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * ComparePreviewModal — sida-vid-sida visuell jämförelse av två historiska
 * runs. Renderar två StackBlitz-iframer i en 50/50-grid på desktop (stackad
 * på smal viewport) så operatören ser strukturella, layout- och variant-
 * skillnader i en blick i stället för att klicka mellan runs i ConsoleDrawer.
 *
 * Återanvänder samma /api/runs/[runId]/files-payload som ViewerPanel —
 * ingen ny backend behövs. Browser-fallback identisk med ViewerPanel:
 * Safari/Firefox/iOS får ett kort med "Öppna i nytt fönster" eftersom
 * embeddade WebContainers kräver Chromium-credentialless.
 *
 * Path B (GAP-backend-path-b-section-renderer) ökar VÄRDET av denna
 * feature kraftigt — när 12 inaktiva scaffolds aktiveras blir det
 * möjligt att jämföra strukturellt olika sajter, inte bara variant-
 * varianter på samma scaffold. Modalen i sig är dock helt oberoende.
 */

type BrowserKind = "chromium" | "safari" | "firefox" | "unknown";

function getBrowserKind(): BrowserKind {
  if (typeof navigator === "undefined") return "chromium";
  const ua = navigator.userAgent;
  if (/Firefox\/\d+/.test(ua)) return "firefox";
  if (/iPhone|iPad|iPod|CriOS|FxiOS|EdgiOS/.test(ua)) return "safari";
  if (/Safari\/\d+/.test(ua) && !/Chrom(e|ium)\/\d+/.test(ua)) return "safari";
  if (/Chrom(e|ium)\/\d+/.test(ua)) return "chromium";
  return "unknown";
}

function supportsEmbed(kind: BrowserKind): boolean {
  if (kind === "unknown") return true;
  return kind === "chromium";
}

function shortRunId(runId: string): string {
  return runId.length > 18 ? `${runId.slice(0, 18)}…` : runId;
}

type FilesPayload = {
  runId: string;
  files: Record<string, string>;
  error?: string;
};

type PaneStatus =
  | { kind: "loading" }
  | { kind: "embedded" }
  | { kind: "fallback"; files: Record<string, string>; browser: BrowserKind }
  | { kind: "unavailable" }
  | { kind: "error"; message: string };

export type ComparePreviewModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  runIdA: string;
  runIdB: string;
  versionA: number | null | undefined;
  versionB: number | null | undefined;
};

export function ComparePreviewModal({
  open,
  onOpenChange,
  runIdA,
  runIdB,
  versionA,
  versionB,
}: ComparePreviewModalProps) {
  // Mobile swipe-state: vilken pane är centrerad i snap-scroll-viewporten.
  // Uppdateras via scroll-position-mätning så vi vet vilken pill (A/B) som
  // ska markeras som aktiv när användaren swipar. På desktop (lg:) syns
  // båda panes samtidigt i 50/50-grid och pillarna är ren visuell etikett.
  const [activePane, setActivePane] = useState<"A" | "B">("A");
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const paneARef = useRef<HTMLElement | null>(null);
  const paneBRef = useRef<HTMLElement | null>(null);

  // Smooth-scroll till efterfrågad pane när användaren klickar på pill.
  // Lg-breakpoint (1024px) använder grid istället för snap-scroll så
  // scrollIntoView är inget no-op där — vi väljer ändå att alltid scrolla,
  // eftersom desktop-flex-grid har båda panes i view oavsett.
  const goToPane = useCallback((target: "A" | "B") => {
    const ref = target === "A" ? paneARef.current : paneBRef.current;
    ref?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "start",
    });
  }, []);

  // Scroll-position-baserad active-pane-tracking på mobil. Vi mäter
  // scrollLeft mot scrollWidth - clientWidth → 0% = A vinner, 100% = B
  // vinner. Threshold 0.5 betyder att vi växlar exakt halvvägs igenom
  // svepet, vilket matchar `snap-mandatory` som ändå snappar fullt
  // till en pane vid release. Snabbare och simplare än observers när
  // vi bara har två snap-targets.
  useEffect(() => {
    if (!open) return;
    const scroller = scrollerRef.current;
    if (!scroller) return;
    const handleScroll = () => {
      const maxScroll = scroller.scrollWidth - scroller.clientWidth;
      if (maxScroll <= 0) return;
      const ratio = scroller.scrollLeft / maxScroll;
      setActivePane(ratio < 0.5 ? "A" : "B");
    };
    handleScroll();
    scroller.addEventListener("scroll", handleScroll, { passive: true });
    return () => scroller.removeEventListener("scroll", handleScroll);
  }, [open]);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop
          className={cn(
            "fixed inset-0 z-40 bg-black/40 backdrop-blur-sm",
            "data-open:animate-in data-open:fade-in-0",
            "data-closed:animate-out data-closed:fade-out-0",
          )}
        />
        <DialogPrimitive.Popup
          className={cn(
            "bg-background fixed inset-2 z-50 flex flex-col overflow-hidden rounded-2xl shadow-2xl ring-1 ring-foreground/10 outline-none sm:inset-4",
            "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
            "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
          )}
        >
          <ModalHeader
            runIdA={runIdA}
            runIdB={runIdB}
            versionA={versionA}
            versionB={versionB}
            activePane={activePane}
            onPaneSelect={goToPane}
          />

          {/* Mobile: snap-x horizontal scroll mellan A och B, en pane
              per swipe. Desktop (lg:): 50/50-grid som tidigare så båda
              syns samtidigt. Refen behövs på lg också eftersom scroll-
              listener bara fästs när modalen är öppen men inte bryr sig
              om viewport-bredd. */}
          <div
            ref={scrollerRef}
            className={cn(
              "min-h-0 flex-1 bg-muted/30 p-2",
              "flex snap-x snap-mandatory gap-2 overflow-x-auto scrollbar-hidden",
              "lg:grid lg:grid-cols-2 lg:overflow-hidden",
            )}
          >
            <PreviewPane
              key={`A:${runIdA}`}
              ref={paneARef}
              runId={runIdA}
              version={versionA}
              tone="rose"
              active={open}
            />
            <PreviewPane
              key={`B:${runIdB}`}
              ref={paneBRef}
              runId={runIdB}
              version={versionB}
              tone="emerald"
              active={open}
            />
          </div>
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function ModalHeader({
  runIdA,
  runIdB,
  versionA,
  versionB,
  activePane,
  onPaneSelect,
}: {
  runIdA: string;
  runIdB: string;
  versionA: number | null | undefined;
  versionB: number | null | undefined;
  activePane: "A" | "B";
  onPaneSelect: (pane: "A" | "B") => void;
}) {
  return (
    <header className="border-border/60 bg-background/95 flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3 pt-safe">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <DialogPrimitive.Title className="text-foreground text-[14px] font-semibold tracking-tight">
          Visuell jämförelse
        </DialogPrimitive.Title>
        <span className="text-muted-foreground hidden text-[12px] sm:inline">
          ·
        </span>
        <span className="text-muted-foreground hidden truncate text-[12px] sm:inline">
          v{versionA ?? "?"} ({shortRunId(runIdA)}) vs v{versionB ?? "?"} (
          {shortRunId(runIdB)})
        </span>
      </div>

      {/* A/B-pills: agerar både som visuell aktiv-indikator (när
          scroll-listener i parent uppdaterar activePane) och som
          direkt-navigering vid tap. Bara meningsfull på mobil
          där snap-scroll separerar panes; på lg+ syns båda
          samtidigt så pillarna fungerar som etiketter. */}
      <div
        role="tablist"
        aria-label="Välj jämförelse-pane"
        className="bg-muted/60 inline-flex shrink-0 rounded-full p-0.5 text-[11px] lg:hidden"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activePane === "A"}
          onClick={() => onPaneSelect("A")}
          className={cn(
            "min-tap sm:min-tap-0 rounded-full px-3 py-1 font-medium transition active:scale-95 sm:px-2.5",
            activePane === "A"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
        >
          v{versionA ?? "?"} · A
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activePane === "B"}
          onClick={() => onPaneSelect("B")}
          className={cn(
            "min-tap sm:min-tap-0 rounded-full px-3 py-1 font-medium transition active:scale-95 sm:px-2.5",
            activePane === "B"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
        >
          v{versionB ?? "?"} · B
        </button>
      </div>

      <DialogPrimitive.Close
        render={
          <Button variant="ghost" size="icon-sm" aria-label="Stäng">
            <XIcon className="h-4 w-4" />
          </Button>
        }
      />
    </header>
  );
}

const PreviewPane = forwardRef<
  HTMLElement,
  {
    runId: string;
    version: number | null | undefined;
    tone: "rose" | "emerald";
    active: boolean;
  }
>(function PreviewPane({ runId, version, tone, active }, ref) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<PaneStatus>({ kind: "loading" });
  const [openingExternal, setOpeningExternal] = useState(false);

  useEffect(() => {
    if (!active) return;
    const node = containerRef.current;
    if (!node) return;

    let cancelled = false;
    setStatus({ kind: "loading" });
    node.replaceChildren();

    void (async () => {
      try {
        const response = await fetch(`/api/runs/${runId}/files`);
        const payload = (await response.json()) as FilesPayload;

        if (cancelled) return;

        if (response.status === 404) {
          setStatus({ kind: "unavailable" });
          return;
        }

        if (!response.ok || payload.error) {
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        const browser = getBrowserKind();
        if (!supportsEmbed(browser)) {
          setStatus({ kind: "fallback", files: payload.files, browser });
          return;
        }

        const sdk = (await import("@stackblitz/sdk")).default;
        if (cancelled || !containerRef.current) return;

        const mountTarget = document.createElement("div");
        mountTarget.className = "h-full w-full";
        containerRef.current.replaceChildren(mountTarget);

        // Patcha document.createElement så <iframe> som StackBlitz SDK
        // skapar får `credentialless`-attributet innan browser börjar
        // ladda src — samma trick som viewer-panel.tsx, krävs av
        // Chromes COEP-credentialless-modell när embedded resource
        // saknar egen COEP-header. try/finally så patchen aldrig läcker.
        const originalCreateElement = document.createElement.bind(document);
        const patchedCreateElement = ((
          tagName: string,
          options?: ElementCreationOptions,
        ) => {
          const elem = originalCreateElement(tagName, options);
          if (
            typeof tagName === "string" &&
            tagName.toLowerCase() === "iframe"
          ) {
            elem.setAttribute("credentialless", "");
          }
          return elem;
        }) as typeof document.createElement;
        document.createElement = patchedCreateElement;

        try {
          await sdk.embedProject(
            mountTarget,
            {
              title: `Sajtbyggaren preview ${runId}`,
              description: "Generated site snapshot — comparison view",
              template: "node",
              files: payload.files,
              settings: { compile: { trigger: "auto" } },
            },
            {
              openFile: "app/page.tsx",
              view: "preview",
              theme: "light",
              terminalHeight: 0,
              hideExplorer: true,
              hideNavigation: true,
              hideDevTools: true,
              clickToLoad: false,
              height: 1200,
            },
          );
        } finally {
          document.createElement = originalCreateElement;
        }

        if (cancelled) {
          if (containerRef.current) containerRef.current.replaceChildren();
          return;
        }

        const iframe = containerRef.current?.querySelector("iframe");
        if (iframe) {
          iframe.style.height = "100%";
          iframe.style.width = "100%";
          iframe.style.border = "0";
        }

        setStatus({ kind: "embedded" });
      } catch (caught) {
        if (cancelled) return;
        const message =
          caught instanceof Error
            ? caught.message
            : "Okänt fel vid laddning av preview.";
        setStatus({ kind: "error", message });
      }
    })();

    return () => {
      cancelled = true;
      if (node) node.replaceChildren();
    };
  }, [active, runId]);

  const handleOpenExternal = useCallback(async () => {
    if (status.kind !== "fallback" || openingExternal) return;
    setOpeningExternal(true);
    try {
      const sdk = (await import("@stackblitz/sdk")).default;
      sdk.openProject(
        {
          title: `Sajtbyggaren preview ${runId}`,
          description: "Generated site snapshot — comparison view",
          template: "node",
          files: status.files,
        },
        { openFile: "app/page.tsx", newWindow: true },
      );
    } finally {
      setOpeningExternal(false);
    }
  }, [openingExternal, runId, status]);

  const toneClasses =
    tone === "rose"
      ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";

  return (
    <section
      ref={ref}
      className="border-border/40 bg-background relative flex min-h-0 w-full shrink-0 snap-start flex-col overflow-hidden rounded-xl border lg:w-auto lg:shrink"
    >
      <header className="border-border/40 bg-background/95 flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2">
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10.5px]",
            toneClasses,
          )}
          title={runId}
        >
          <span className="text-[9px] tracking-[0.18em] uppercase opacity-80">
            {tone === "rose" ? "A" : "B"}
          </span>
          <span>v{version ?? "?"}</span>
        </span>
        <span
          className="text-muted-foreground truncate font-mono text-[10.5px]"
          title={runId}
        >
          {shortRunId(runId)}
        </span>
      </header>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-white">
        <div ref={containerRef} className="h-full w-full" />

        {status.kind === "loading" ? (
          <PaneOverlay>
            <div className="flex flex-col items-center gap-2 text-center">
              <Loader2 className="text-muted-foreground h-5 w-5 animate-spin" />
              <span className="text-muted-foreground text-[11.5px]">
                Bootar preview…
              </span>
              <span className="text-muted-foreground/70 text-[10.5px]">
                StackBlitz cold-start kan ta 30–60 sekunder första gången.
              </span>
            </div>
          </PaneOverlay>
        ) : null}

        {status.kind === "unavailable" ? (
          <PaneOverlay>
            <div className="border-amber-500/40 bg-amber-500/10 max-w-xs rounded-lg border px-3 py-2 text-center text-[11.5px] text-amber-800 dark:text-amber-300">
              Preview saknas för denna run (mock-runs eller misslyckade builds
              skriver inte filer).
            </div>
          </PaneOverlay>
        ) : null}

        {status.kind === "fallback" ? (
          <PaneOverlay>
            <div className="border-border/60 bg-background w-full max-w-xs rounded-xl border p-4 shadow-sm">
              <p className="text-foreground/85 mb-3 text-[12px] leading-relaxed">
                {status.browser === "firefox"
                  ? "Firefox stödjer inte ännu inbäddad preview från WebContainers."
                  : "Safari stödjer inte inbäddad preview från WebContainers."}{" "}
                Öppna sajten i en ny flik på stackblitz.com.
              </p>
              <Button
                type="button"
                size="sm"
                onClick={handleOpenExternal}
                disabled={openingExternal}
                className="w-full justify-center gap-2"
              >
                {openingExternal ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Öppnar…
                  </>
                ) : (
                  <>
                    <ExternalLink className="h-3.5 w-3.5" />
                    Öppna i nytt fönster
                  </>
                )}
              </Button>
            </div>
          </PaneOverlay>
        ) : null}

        {status.kind === "error" ? (
          <PaneOverlay>
            <div className="border-destructive/40 bg-destructive/10 text-destructive max-w-xs rounded-lg border px-3 py-2 text-center text-[11.5px]">
              <AlertTriangle aria-hidden className="mx-auto mb-1 h-4 w-4" />
              <div className="font-mono text-[10.5px] break-all whitespace-pre-wrap">
                {status.message}
              </div>
            </div>
          </PaneOverlay>
        ) : null}
      </div>
    </section>
  );
});

function PaneOverlay({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background/80 pointer-events-auto absolute inset-0 z-10 flex items-center justify-center px-3 backdrop-blur-sm">
      {children}
    </div>
  );
}
