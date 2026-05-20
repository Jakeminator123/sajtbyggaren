"use client";

import { ExternalLink, Check, Loader2 } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { PromptStage } from "@/components/prompt-builder";

type ViewerPanelProps = {
  runId: string | null;
  /**
   * Sätts till true av page.tsx under hela request-cykeln mot
   * /api/prompt. Triggar BuildProgressCard i mitten av canvasen i
   * stället för hero-texten så operatören ser en dedikerad bygg-vy.
   */
  isBuilding?: boolean;
  /**
   * Aktuell PromptStage från PromptBuilder. Styr vilken rad som är
   * aktiv i BuildProgressCard-stegmarkören.
   */
  buildStage?: PromptStage;
};

type FilesPayload = {
  runId: string;
  files: Record<string, string>;
  error?: string;
};

type BrowserKind = "chromium" | "safari" | "firefox" | "unknown";

/**
 * Heuristik för "kan denna webbläsare köra en embeddad WebContainer-
 * iframe?". StackBlitz embed kräver `COEP: credentialless` på host-
 * dokumentet plus stöd för credentialless-iframes i browsern. Per
 * StackBlitz egen browser-support-tabell:
 *   - Chromium-baserade (Chrome, Edge, Brave, Opera, Vivaldi): JA
 *   - Safari (desktop + iOS, inkl. CriOS/FxiOS som är WebKit under huven):
 *     NEJ — Safari saknar credentialless och kan därför inte ladda embeds
 *   - Firefox: NEJ — beta-stöd för WebContainers men inte för embeds
 *
 * Detta dokumenteras i `docs/integrations/webcontainers-notes.md` och
 * `docs/integrations/stackblitz-research.md`. När browsern inte stödjer
 * embed visar ViewerPanel ett fallback-kort med en "Öppna i nytt fönster"-
 * knapp som anropar `sdk.openProject()` (top-level navigation till
 * stackblitz.com, fungerar i alla browsers eftersom det inte är embeddat).
 */
function getBrowserKind(): BrowserKind {
  if (typeof navigator === "undefined") return "chromium";
  const ua = navigator.userAgent;
  if (/Firefox\/\d+/.test(ua)) return "firefox";
  // iOS-browsers är alla WebKit oavsett etikett (CriOS = Chrome iOS,
  // FxiOS = Firefox iOS, EdgiOS = Edge iOS) — räkna som Safari.
  if (/iPhone|iPad|iPod|CriOS|FxiOS|EdgiOS/.test(ua)) return "safari";
  // Desktop Safari: "Safari/" finns men "Chrome/"/"Chromium/" saknas.
  if (/Safari\/\d+/.test(ua) && !/Chrom(e|ium)\/\d+/.test(ua)) return "safari";
  if (/Chrom(e|ium)\/\d+/.test(ua)) return "chromium";
  return "unknown";
}

function supportsStackBlitzEmbed(kind: BrowserKind): boolean {
  // SSR och okänd browser: vi optimistiskt försöker embeda. Worst case
  // får operatören error-pre + kan klicka "Öppna i nytt fönster".
  if (kind === "unknown") return true;
  return kind === "chromium";
}

function formatViewerError(caught: unknown): string {
  if (caught instanceof Error) {
    const details = [
      `name: ${caught.name || "Error"}`,
      `message: ${caught.message || "(empty message)"}`,
    ];
    if (caught.stack) {
      details.push(
        `stack:\n${caught.stack.split("\n").slice(0, 20).join("\n")}`,
      );
    }
    return details.join("\n");
  }

  try {
    return `non-Error rejection:\n${JSON.stringify(caught, null, 2)}`;
  } catch {
    return `non-Error rejection:\n${String(caught)}`;
  }
}

export function ViewerPanel({
  runId,
  isBuilding = false,
  buildStage = "idle",
}: ViewerPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(false);
  // När browsern inte stödjer embed sparar vi hämtade filer + den
  // detekterade browser-kinden i ett gemensamt state-objekt.
  // Knappen anropar `sdk.openProject()` med samma payload (utan att
  // fetcha igen) och fallback-kortets text personifieras via
  // `fallback.kind`. Browser-detekteringen sker synkront inuti
  // run-id-effekten (navigator är tillgänglig där eftersom effekten
  // kör efter mount) — ingen separat detect-effect behövs, och
  // useEffect-deps-arrayen förblir konstant så HMR inte klagar.
  const [fallback, setFallback] = useState<{
    files: Record<string, string>;
    kind: BrowserKind;
  } | null>(null);
  const [openingExternal, setOpeningExternal] = useState(false);

  // Öppna sajten i en ny flik på stackblitz.com (top-level navigation,
  // ingen embed = ingen credentialless-iframe = funkar i Safari/Firefox).
  // Använder samma SDK + samma files-payload som embed-vägen.
  const handleOpenExternal = useCallback(async () => {
    if (!fallback || !runId || openingExternal) return;
    setOpeningExternal(true);
    setError(null);
    try {
      const sdk = (await import("@stackblitz/sdk")).default;
      sdk.openProject(
        {
          title: `Sajtbyggaren preview ${runId}`,
          description: "Generated site snapshot",
          template: "node",
          files: fallback.files,
        },
        {
          openFile: "app/page.tsx",
          newWindow: true,
        },
      );
    } catch (caught) {
      setError(formatViewerError(caught));
    } finally {
      setOpeningExternal(false);
    }
  }, [fallback, openingExternal, runId]);

  useEffect(() => {
    // containerRef-div is now mounted unconditionally (see render
    // below) so containerRef.current is bound on every runId change,
    // including transitions out of unavailable=true. The remaining
    // null-check covers the very first render before React has
    // attached the ref (effect runs after commit, but we still keep
    // the guard for defense in depth).
    if (!runId || !containerRef.current) {
      setUnavailable(false);
      setLoading(false);
      setFallback(null);
      return;
    }

    const node = containerRef.current;
    let cancelled = false;
    setError(null);
    setUnavailable(false);
    setFallback(null);
    setLoading(true);
    node.replaceChildren();

    void (async () => {
      try {
        const response = await fetch(`/api/runs/${runId}/files`);
        const payload = (await response.json()) as FilesPayload;
        if (!response.ok || payload.error) {
          // 404 = run-dir saknar generated-files / .generated/<siteId>/.
          // Det är förväntat för dev_generate-mock-runs (placeholder-pipeline).
          // Visa pedagogisk fallback istället för stack trace.
          if (response.status === 404) {
            // Cancelled-guard: a stale 404 from a previous runId must
            // not overwrite UI state for the run that is currently
            // selected (race condition when runId changes faster than
            // the in-flight fetch resolves). Mirrors the guard on the
            // success / catch paths below.
            if (cancelled) return;
            setUnavailable(true);
            setLoading(false);
            return;
          }
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        if (cancelled || !containerRef.current) return;

        // Browser-kind-check: Safari, Firefox och iOS-browsers kan
        // inte rendera embeddade WebContainer-iframes (saknar stöd
        // för credentialless cross-origin isolation). Visa
        // fallback-kort med "Öppna i nytt fönster" istället för
        // StackBlitz' kryptiska "Unable to run Embedded Project"-
        // fel som annars dyker upp inuti iframen. Vi detekterar
        // synkront här eftersom navigator är tillgänglig efter mount
        // — separat detect-effect behövs inte.
        const kind = getBrowserKind();
        if (!supportsStackBlitzEmbed(kind)) {
          setFallback({ files: payload.files, kind });
          setLoading(false);
          return;
        }

        // B43 (post-review-2): the dynamic import + embedProject have
        // their own awaits. If the operator switches runId between
        // them, cleanup sets cancelled=true but the in-flight
        // embedProject still mounts the stale preview into the
        // always-mounted ref-div. Re-check cancelled after BOTH
        // awaits and explicitly clear the node if we mounted into
        // a stale tree.
        const sdk = (await import("@stackblitz/sdk")).default;
        if (cancelled || !containerRef.current) return;

        // StackBlitz SDK replaces the target element with an iframe
        // (`target.replaceWith(frame)`). Never pass it the React-owned
        // shell div itself; create an unmanaged child and let the SDK
        // replace that child. React then keeps owning a stable shell,
        // avoiding DOM placement crashes when sibling status/error UI
        // re-renders while StackBlitz mutates the preview DOM.
        const mountTarget = document.createElement("div");
        mountTarget.className = "h-full w-full";
        containerRef.current.replaceChildren(mountTarget);

        // Patch document.createElement so the <iframe> StackBlitz SDK
        // creates inside embedProject is tagged with the
        // `credentialless` HTML attribute BEFORE the browser starts
        // loading its src. Our host page sends
        // `Cross-Origin-Embedder-Policy: credentialless` (see
        // apps/viewser/next.config.ts), which is required for the
        // WebContainer inside the iframe to access SharedArrayBuffer.
        // But Chrome additionally requires that EACH embedded iframe
        // either responds with its own COEP header or carries the
        // credentialless attribute on the <iframe> element — and
        // StackBlitz's embed response does not send a COEP header.
        // Without the attribute Chrome shows "Specify a Cross-Origin
        // Embedder Policy to prevent this frame from being blocked"
        // in DevTools and refuses to load the embed. The attribute
        // must be set before insertion because the browser begins
        // fetching the iframe's document as soon as it enters the DOM
        // with src already populated. See
        // https://developer.chrome.com/blog/iframe-credentialless for
        // the credentialless-iframe model and why parent COEP alone
        // is insufficient.
        //
        // The patch is scoped via try/finally so we never leave the
        // global API mutated past the SDK's internal iframe creation.
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
              description: "Generated site snapshot",
              template: "node",
              files: payload.files,
              settings: {
                compile: {
                  // Auto-rebuild when files ändras (StackBlitz default = on,
                  // men vi sätter explicit så det aldrig avbryts av framtida
                  // SDK-versionsändringar).
                  trigger: "auto",
                },
              },
            },
            {
              openFile: "app/page.tsx",
              view: "preview",
              // Ljust tema för att matcha Sajtbyggarens egen UI istället för
              // StackBlitz default-mörkblå. Möjliga värden: "default" (mörk),
              // "light", "dark". `terminalHeight: 0` döljer den lilla
              // terminal-panelen som annars syns nere i preview-läget och
              // gör helhetsintrycket mörkare.
              theme: "light",
              terminalHeight: 0,
              // Göm sidebar med fil-listan eftersom vi visar bara preview
              // (operatören inspekterar koden via Run History-drawern i
              // Sajtbyggaren-UI:t, inte via StackBlitz-sidebaren).
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
          // Stale embed mounted while we were unmounting. Tear it
          // down so the next runId starts from an empty node.
          if (containerRef.current) {
            containerRef.current.replaceChildren();
          }
          return;
        }

        // Fullscreen preview canvas: StackBlitz SDK sets a fixed
        // height attribute on the iframe (from the `height` option
        // above). Override it via inline style so the iframe expands
        // to fill the canvas container. The container itself owns
        // sizing via flex/CSS — the iframe should always be 100%
        // height/width inside it.
        const iframe = containerRef.current?.querySelector("iframe");
        if (iframe) {
          iframe.style.height = "100%";
          iframe.style.width = "100%";
          iframe.style.border = "0";
        }

        setLoading(false);
      } catch (caught) {
        if (!cancelled) {
          setError(formatViewerError(caught));
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (node) node.replaceChildren();
    };
  }, [runId]);

  const showEmpty = !runId;
  const showUnavailable = unavailable && !!runId;
  const showFallback = !!fallback && !!runId && !isBuilding;
  // "Finalize"-fasen efter build_site.py är klart: backend har skrivit
  // build-result.json (status=ok), frontend har satt stage="success" och
  // building=false, men ViewerPanel hämtar nu manifest från
  // /api/runs/X/files och bootar StackBlitz-SDK:n. Utan denna flagga
  // försvann BuildProgressCard direkt vid success — operatören tappade
  // den visuella kontinuiteten från "Bygger sajt" → "Startar preview".
  const isFinalizing =
    buildStage === "success" && loading && !!runId && !unavailable;
  // Visa hero-videon så länge ingen riktig iframe har mountats. Det
  // täcker: ingen run vald (empty), 404 på files (unavailable),
  // pågående fetch (loading), SDK-error, pågående bygge OCH
  // browser-fallback (Safari/Firefox). `loading` räcker —
  // `isFinalizing` är en delmängd av `loading`.
  const showHero =
    showEmpty ||
    showUnavailable ||
    showFallback ||
    loading ||
    !!error ||
    isBuilding;
  // BuildProgressCard tar över mittenytan när vi aktivt bygger ELLER
  // när bygget precis blivit klart men preview-iframen fortfarande
  // bootas. Hero-texten ska INTE visas i någondera fas — det skulle
  // vara dubbel information med två konkurrerande UI:n. Inte heller
  // när vi visar browser-fallback-kortet (det äger mittenytan).
  const showHeroText =
    (showEmpty || showUnavailable || !!error) &&
    !isBuilding &&
    !isFinalizing &&
    !showFallback;
  const showBuildCard = isBuilding || isFinalizing;

  return (
    <div className="viewer-canvas bg-background relative flex h-full w-full overflow-hidden">
      {/* Hero-bakgrundsvideo. Autoplay + muted + loop + playsInline så
          den startar i alla browsers utan användarinteraktion. Videons
          centrum förskjuts mot höger via object-position så 3D-objektet
          inte krockar med hero-texten i vänsterspalten. */}
      {showHero ? (
        <>
          <video
            key="sm-hero"
            className="pointer-events-none absolute inset-0 h-full w-full object-cover [object-position:78%_center]"
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            aria-hidden
          >
            <source src="/SM_hero.mp4" type="video/mp4" />
          </video>
          {/* Två gradienter: en horisontell som mörknar vänsterkanten
              så hero-texten alltid har kontrast, plus en vertikal som
              fadar mot botten där prompt-rutan lever. */}
          <div
            aria-hidden
            className="from-background/85 via-background/40 dark:from-background/90 dark:via-background/50 pointer-events-none absolute inset-0 bg-gradient-to-r to-transparent"
          />
          <div
            aria-hidden
            className="to-background/80 dark:to-background/90 pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent"
          />
        </>
      ) : null}

      {/* Thin top progress strip while building/loading. */}
      {loading ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-20 h-[2px] overflow-hidden bg-transparent"
        >
          <div className="bg-foreground/70 h-full w-1/3 animate-[viewer-progress_1.6s_ease-in-out_infinite] rounded-full" />
        </div>
      ) : null}

      {/* BuildProgressCard — dominant central laddningsmodul när
          bygget pågår. Absolut positionerad så cardet är garanterat
          centrerat på canvasen oavsett vad andra siblings gör i
          flex-layouten. */}
      {showBuildCard ? (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-6">
          <div className="pointer-events-auto">
            {/* key={buildStage} forces a full remount on every stage
                transition so elapsedSec restarts at 0 via useState(0)
                without needing a setState call inside the effect
                body (react-hooks/set-state-in-effect). */}
            <BuildProgressCard key={buildStage} stage={buildStage} />
          </div>
        </div>
      ) : null}

      {/* Hero-text — visas alltid när StackBlitz inte aktivt visar en
          sajt (empty, unavailable, error). Vänsterställd så den inte
          krockar med videons 3D-objekt till höger. */}
      {showHeroText ? (
        <div className="relative z-10 flex h-full w-full items-center px-8 sm:px-12 lg:px-20">
          <div className="flex max-w-lg flex-col items-start gap-4 text-left">
            <span className="border-border/40 bg-background/70 text-foreground/70 rounded-full border px-3 py-1 font-mono text-[10px] tracking-[0.22em] uppercase shadow-sm backdrop-blur">
              Sajtbyggaren · localhost
            </span>
            <h1 className="text-foreground text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-5xl">
              Beskriv din sajt
              <br />
              <span className="text-foreground/60">så bygger vi den.</span>
            </h1>
            <p className="text-foreground/75 max-w-md text-[14px] leading-relaxed text-balance sm:text-[15px]">
              Skriv vad sajten ska göra. Vi genererar Project Input, kör Quality
              Gate och paketerar en preview du kan inspektera direkt här.
            </p>
          </div>
        </div>
      ) : null}

      {/* Tidigare bodde en status-pill här (top-4 left-4) som visade
          "Förhandsvisning aktiv för {runId}". Den krockade visuellt
          med SiteHeader-logon och läckte rå run-ID-text in i UI:t
          utan att tillföra något: FloatingChat-headern säger redan
          "Sajten {siteId} är aktiv", och loading-pulsen längst upp
          (showLoading-stripen) räcker för att signalera arbete.
          Hela status-state togs bort när pillan gick. */}

      {/* Unavailable banner. */}
      {showUnavailable ? (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="max-w-md rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-4 text-sm text-amber-800 dark:text-amber-300">
            Förhandsvisning saknas för denna run. Mock-runs skriver inte en
            faktisk Next.js-app — skicka en prompt i chat-rutan för att köra en
            riktig builder-run.
          </div>
        </div>
      ) : null}

      {/* Browser-fallback för Safari/Firefox/iOS. Sajten är byggd men
          inbäddad preview funkar inte (browsern stödjer inte
          credentialless cross-origin isolation). Knappen öppnar samma
          projekt i nytt fönster på stackblitz.com via sdk.openProject
          — top-level navigation som funkar i alla browsers. */}
      {showFallback ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="border-border/60 bg-background/95 pointer-events-auto w-full max-w-[460px] rounded-3xl border p-7 shadow-[0_32px_80px_-16px_rgba(0,0,0,0.25)] backdrop-blur-xl">
            <div className="mb-5 flex items-center gap-3">
              <span className="bg-muted/60 inline-flex h-10 w-10 items-center justify-center rounded-xl p-1.5">
                <Image
                  src="/LOGO_SM2.0.png"
                  alt="Sajtmaskin"
                  width={28}
                  height={28}
                  className="h-full w-full object-contain"
                />
              </span>
              <div className="flex flex-1 flex-col leading-tight">
                <span className="text-muted-foreground font-mono text-[9.5px] tracking-[0.22em] uppercase">
                  Sajtbyggaren · preview
                </span>
                <span className="text-foreground text-[15px] font-semibold tracking-tight">
                  Sajten är klar
                </span>
              </div>
            </div>

            <p className="text-foreground/85 mb-3 text-[13px] leading-relaxed">
              {fallback?.kind === "firefox"
                ? "Firefox stödjer inte ännu inbäddad preview från WebContainers."
                : "Safari stödjer inte inbäddad preview från WebContainers."}{" "}
              Sajten är byggd och redo — öppna den i ett nytt fönster på
              stackblitz.com där den fungerar direkt.
            </p>

            <Button
              type="button"
              onClick={handleOpenExternal}
              disabled={openingExternal}
              className="w-full justify-center gap-2"
            >
              {openingExternal ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Öppnar…
                </>
              ) : (
                <>
                  <ExternalLink className="h-4 w-4" />
                  Öppna preview i nytt fönster
                </>
              )}
            </Button>

            <p className="text-muted-foreground mt-3 text-[11.5px] leading-relaxed">
              Tips: öppna Sajtbyggaren i Chrome, Edge eller Brave för inbäddad
              live-preview direkt i denna vy.
            </p>
          </div>
        </div>
      ) : null}

      {/* StackBlitz SDK error pre — kept as readable diagnostic. */}
      {error ? (
        <pre className="border-destructive/40 bg-destructive/10 text-destructive absolute bottom-24 left-1/2 z-20 max-h-48 w-[min(90vw,640px)] -translate-x-1/2 overflow-auto rounded-lg border px-3 py-2 text-[11px] whitespace-pre-wrap shadow-lg">
          {error}
        </pre>
      ) : null}

      {/*
        containerRef-div hålls mounted oavsett `unavailable` så
        containerRef.current är bunden över transitions. Tidigare
        satt den i else-grenen av en `unavailable ? tips : <div ref>`
        ternary, vilket avmonterade ref när 404 satte
        unavailable=true - det låste UI:t i stuck state när nästa
        runId valdes (effekten har bara `[runId]` som dep och kör
        inte om vid unavailable-flip). Hidden via Tailwind när
        empty/unavailable äger ytan.
      */}
      <div
        ref={containerRef}
        className={`h-full w-full ${unavailable || showEmpty || isBuilding || isFinalizing || showFallback ? "invisible" : ""}`}
      />
    </div>
  );
}

/**
 * Central laddningskort som visas i mitten av canvasen under hela
 * /api/prompt-cykeln. Stegmarkören visar var vi är i pipelinen:
 *
 *   1. Förbereder brief
 *   2. Genererar Project Input
 *   3. Bygger sajt
 *   4. Startar preview
 *
 * Mappas från PromptStage så vi kan visa rätt aktivt steg medan
 * `executeBuild()` jobbar.
 */
const BUILD_STEPS: ReadonlyArray<{
  id: "prepare" | "generate" | "build" | "preview";
  title: string;
  hint: string;
}> = [
  {
    id: "prepare",
    title: "Förbereder brief",
    hint: "Vi paketerar dina svar till en master-prompt.",
  },
  {
    id: "generate",
    title: "Genererar Project Input",
    hint: "briefModel extraherar mål, ton och kapabiliteter.",
  },
  {
    id: "build",
    title: "Bygger sajt",
    hint: "npm install + Next.js-bygge i en ren sandbox. Första bygget tar 1–3 minuter eftersom node_modules behöver installeras från noll.",
  },
  {
    id: "preview",
    title: "Startar preview",
    hint: "Förbereder StackBlitz-iframen.",
  },
];

function stageToStepIndex(stage: PromptStage): number {
  switch (stage) {
    case "idle":
      return 0;
    case "thinking":
      return 1;
    case "building":
      return 2;
    case "success":
    case "degraded":
    case "failed":
      return 3;
    default:
      return 0;
  }
}

function BuildProgressCard({ stage }: { stage: PromptStage }) {
  const activeIdx = stageToStepIndex(stage);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const minutes = Math.floor(elapsedSec / 60);
  const seconds = (elapsedSec % 60).toString().padStart(2, "0");

  return (
    <div className="border-border/60 bg-background/95 w-full max-w-[560px] rounded-3xl border p-9 shadow-[0_32px_80px_-16px_rgba(0,0,0,0.25)] backdrop-blur-xl">
      <div className="mb-6 flex items-center gap-3">
        <span className="bg-muted/60 inline-flex h-10 w-10 items-center justify-center rounded-xl p-1.5">
          <Image
            src="/LOGO_SM2.0.png"
            alt="Sajtmaskin"
            width={28}
            height={28}
            className="h-full w-full object-contain"
          />
        </span>
        <div className="flex flex-1 flex-col leading-tight">
          <span className="text-muted-foreground font-mono text-[9.5px] tracking-[0.22em] uppercase">
            Sajtbyggaren · build
          </span>
          <span className="text-foreground text-[15px] font-semibold tracking-tight">
            Bygger din sajt
          </span>
        </div>
        <span className="bg-muted/50 text-foreground rounded-full px-2.5 py-1 font-mono text-[11px] tracking-tight tabular-nums">
          {minutes}:{seconds}
        </span>
      </div>

      <ol className="flex flex-col gap-0.5">
        {BUILD_STEPS.map((step, idx) => {
          const isActive = idx === activeIdx;
          const isPast = idx < activeIdx;
          const isFuture = idx > activeIdx;
          return (
            <li
              key={step.id}
              className={[
                "flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors",
                isActive ? "bg-foreground/[0.04]" : "",
              ].join(" ")}
            >
              <span
                className={[
                  "mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] transition-colors",
                  isPast
                    ? "bg-foreground text-background"
                    : isActive
                      ? "bg-foreground text-background"
                      : "border-border/70 bg-background text-muted-foreground/70 border",
                ].join(" ")}
              >
                {isPast ? (
                  <Check className="h-3 w-3" strokeWidth={2.5} />
                ) : isActive ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <span className="font-mono text-[9.5px] tracking-tight">
                    {idx + 1}
                  </span>
                )}
              </span>
              <div className="flex flex-1 flex-col leading-snug">
                <span
                  className={[
                    "text-[13px] font-medium tracking-tight",
                    isFuture ? "text-muted-foreground" : "text-foreground",
                  ].join(" ")}
                >
                  {step.title}
                </span>
                <span
                  className={[
                    "text-[11.5px] leading-relaxed",
                    isActive
                      ? "text-muted-foreground"
                      : "text-muted-foreground/70",
                  ].join(" ")}
                >
                  {step.hint}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="bg-border/50 mt-6 h-[2px] w-full overflow-hidden rounded-full">
        <div
          className="bg-foreground/80 h-full animate-pulse rounded-full transition-[width] duration-500 ease-out"
          style={{
            width: `${((activeIdx + 1) / BUILD_STEPS.length) * 100}%`,
          }}
        />
      </div>
    </div>
  );
}
