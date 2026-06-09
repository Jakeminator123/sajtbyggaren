"use client";

import { ExternalLink, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * StackblitzPreview — LEGACY / PAUSED WebContainer-preview-väg (ADR 0033).
 *
 * Detta är den ENDA modulen i Viewsers preview-canvas som når
 * ``await import("@stackblitz/sdk")``. Den laddas via en runtime ``import()``
 * (klient-only, ingen SSR) från ``ViewerPanel`` och RENDERAS bara när
 * preview-läget är ``stackblitz``/``auto`` (descriptorns
 * ``canFallbackToStackblitz === true``). Eftersom hela StackBlitz-modulgrafen
 * ligger bakom den lazy komponentgränsen ingår den INTE i ViewerPanel:s
 * eager-laddade chunk — en
 * normal ``vercel-sandbox``/``local-next``-studioladdning hämtar därför
 * aldrig stackblitz-chunken över nätet (det var bundle-bloat:en före denna
 * split: ``await import`` i ViewerPanel självt prefetchades via sidans
 * modulgraf trots att SDK:n aldrig instantierades i sandbox-läge).
 *
 * Komponenten äger HELA StackBlitz-flödet:
 *   1. Hämtar filuppsättningen via ``/api/runs/<runId>/files``.
 *   2. Embeddar en WebContainer-iframe i Chromium (credentialless +
 *      cross-origin-isolated).
 *   3. Faller tillbaka till ett "öppna i nytt fönster"-kort i
 *      Safari/Firefox/iOS (top-level ``openProject``-navigation, ingen embed).
 *
 * Browser-stöd: StackBlitz-embed kräver ``COEP: credentialless`` + stöd för
 * credentialless-iframes:
 *   - Chromium (Chrome/Edge/Brave/Opera/Vivaldi): JA
 *   - Safari (desktop + iOS, inkl. CriOS/FxiOS): NEJ
 *   - Firefox: NEJ
 * Se ``docs/integrations/webcontainers-notes.md`` och
 * ``docs/integrations/stackblitz-research.md``.
 */

type BrowserKind = "chromium" | "safari" | "firefox" | "unknown";

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

type FilesPayload = {
  runId: string;
  files: Record<string, string>;
  error?: string;
};

/**
 * Status för StackBlitz-panelen. Ersätter ViewerPanel:s tidigare
 * intvinnade ``loading``/``fallback``/``error``-flaggor med en sluten
 * state-maskin lokal till denna paus-väg.
 */
type StackblitzStatus =
  | { kind: "loading" }
  | { kind: "embedded" }
  | { kind: "fallback"; files: Record<string, string>; browser: BrowserKind }
  | { kind: "unavailable"; title: string; message: string; hint?: string }
  | { kind: "error"; message: string };

export type StackblitzPreviewProps = {
  runId: string;
  /**
   * Sätts av ViewerPanel under bygge/finalize. Döljer fallback-kortet så
   * det inte konkurrerar med BuildProgressCard-overlayn under en rebuild.
   */
  isBuilding?: boolean;
};

export function StackblitzPreview({
  runId,
  isBuilding = false,
}: StackblitzPreviewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<StackblitzStatus>({ kind: "loading" });
  const [openingExternal, setOpeningExternal] = useState(false);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;

    let cancelled = false;
    setStatus({ kind: "loading" });
    node.replaceChildren();

    void (async () => {
      try {
        const response = await fetch(`/api/runs/${runId}/files`);
        const payload = (await response.json()) as FilesPayload;
        if (!response.ok || payload.error) {
          // 404 = run-dir saknar generated-files / .generated/<siteId>/.
          // Förväntat för dev_generate-mock-runs (placeholder-pipeline).
          // Visa pedagogisk fallback istället för stack trace.
          if (response.status === 404) {
            // Cancelled-guard: en stale 404 från en tidigare runId får
            // inte skriva över UI-state för den nu valda runen (race när
            // runId byts snabbare än in-flight-fetchen hinner resolva).
            if (cancelled) return;
            setStatus({
              kind: "unavailable",
              title: "Mock-run utan generated-files",
              message:
                "Förhandsvisning saknas för denna run. Mock-runs skriver inte en faktisk Next.js-app.",
              hint: "Skicka en prompt i chat-rutan för att köra en riktig builder-run.",
            });
            return;
          }
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        if (cancelled || !containerRef.current) return;

        // Browser-kind-check: Safari, Firefox och iOS-browsers kan inte
        // rendera embeddade WebContainer-iframes (saknar stöd för
        // credentialless cross-origin isolation). Visa fallback-kort med
        // "Öppna i nytt fönster" istället för StackBlitz' kryptiska
        // "Unable to run Embedded Project"-fel.
        const kind = getBrowserKind();
        if (!supportsStackBlitzEmbed(kind)) {
          setStatus({ kind: "fallback", files: payload.files, browser: kind });
          return;
        }

        // B43 (post-review-2): dynamiska importen + embedProject har egna
        // awaits. Om operatören byter runId mellan dem sätter cleanup
        // cancelled=true men in-flight embedProject mountar ändå den stale
        // previewn i den always-mounted ref-divden. Re-check cancelled
        // EFTER BÅDA awaits och rensa noden om vi mountade i ett stale träd.
        const sdk = (await import("@stackblitz/sdk")).default;
        if (cancelled || !containerRef.current) return;

        // StackBlitz SDK ersätter target-elementet med en iframe
        // (`target.replaceWith(frame)`). Skicka aldrig in den React-ägda
        // shell-divden själv; skapa ett omanagerat barn och låt SDK:n byta
        // ut det. React behåller då en stabil shell.
        const mountTarget = document.createElement("div");
        mountTarget.className = "h-full w-full";
        containerRef.current.replaceChildren(mountTarget);

        // Patcha document.createElement så <iframe> som StackBlitz SDK
        // skapar taggas med `credentialless`-attributet INNAN browsern
        // börjar ladda dess src. Vår host skickar
        // `Cross-Origin-Embedder-Policy: credentialless` (se
        // apps/viewser/next.config.ts), och Chrome kräver att VARJE
        // embeddad iframe antingen svarar med egen COEP-header eller bär
        // `credentialless`-attributet — StackBlitz embed-svar saknar COEP.
        // Utan attributet visar Chrome "Specify a Cross-Origin Embedder
        // Policy ...". Attributet måste sättas före insertion eftersom
        // browsern börjar hämta iframens dokument så snart den hamnar i
        // DOM med src ifylld. Se
        // https://developer.chrome.com/blog/iframe-credentialless.
        //
        // Patchen är scopa:d via try/finally så vi aldrig lämnar global-
        // API:t muterat förbi SDK:ns interna iframe-skapande.
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
                  // Auto-rebuild när filer ändras (StackBlitz default = on,
                  // men vi sätter explicit så det aldrig avbryts av framtida
                  // SDK-versionsändringar).
                  trigger: "auto",
                },
              },
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
              // Säg åt SDK:n att lägga till `cross-origin-isolated` i
              // iframens `allow`-lista (Permissions Policy-delegering).
              // Krävs för att `window.crossOriginIsolated` ska bli `true`
              // inuti iframen — annars bootar WebContainern inte och visar
              // "Unable to run Embedded Project" trots korrekt host-COEP/COOP.
              // Tillsammans med `credentialless`-attributet ovan ger detta
              // full cross-origin isolation åt embedden. Se EmbedOptions i
              // @stackblitz/sdk/types/interfaces.d.ts och
              // https://blog.stackblitz.com/posts/cross-browser-with-coop-coep/.
              crossOriginIsolated: true,
            },
          );
        } finally {
          document.createElement = originalCreateElement;
        }

        if (cancelled) {
          // Stale embed mountad medan vi avmonterade. Riv ner den så nästa
          // runId startar från en tom nod.
          if (containerRef.current) {
            containerRef.current.replaceChildren();
          }
          return;
        }

        // Fullscreen preview-canvas: SDK sätter en fast height på iframen
        // (från `height`-optionen). Override via inline-style så iframen
        // fyller container:n.
        const iframe = containerRef.current?.querySelector("iframe");
        if (iframe) {
          iframe.style.height = "100%";
          iframe.style.width = "100%";
          iframe.style.border = "0";
        }

        setStatus({ kind: "embedded" });
      } catch (caught) {
        if (!cancelled) {
          setStatus({ kind: "error", message: formatViewerError(caught) });
        }
      }
    })();

    return () => {
      cancelled = true;
      if (node) node.replaceChildren();
    };
  }, [runId]);

  // Öppna sajten i en ny flik på stackblitz.com (top-level navigation, ingen
  // embed = ingen credentialless-iframe = funkar i Safari/Firefox). Använder
  // samma SDK + samma files-payload som embed-vägen.
  const handleOpenExternal = useCallback(async () => {
    if (status.kind !== "fallback" || openingExternal) return;
    setOpeningExternal(true);
    try {
      const sdk = (await import("@stackblitz/sdk")).default;
      sdk.openProject(
        {
          title: `Sajtbyggaren preview ${runId}`,
          description: "Generated site snapshot",
          template: "node",
          files: status.files,
        },
        {
          openFile: "app/page.tsx",
          newWindow: true,
        },
      );
    } catch (caught) {
      setStatus({ kind: "error", message: formatViewerError(caught) });
    } finally {
      setOpeningExternal(false);
    }
  }, [openingExternal, runId, status]);

  const showFallback = status.kind === "fallback" && !isBuilding;

  return (
    <div className="relative h-full w-full bg-white">
      {/*
        containerRef-div hålls ALLTID mounted så containerRef.current är
        bunden över runId-byten (effekten har bara `[runId]` som dep). Gjordes
        den conditional skulle ref:en falla till null och låsa panelen i ett
        stuck state. Visibility styrs via Tailwind utifrån `status` i stället
        för att avmontera noden.
      */}
      <div
        ref={containerRef}
        className={`h-full w-full ${status.kind === "embedded" ? "" : "invisible"}`}
      />

      {status.kind === "loading" ? (
        <div
          className="pointer-events-none absolute inset-0 z-[6] flex items-center justify-center bg-white"
          role="status"
          aria-live="polite"
        >
          <div className="flex flex-col items-center gap-2 text-center">
            <Loader2
              aria-hidden
              className="text-muted-foreground/50 h-6 w-6 motion-safe:animate-spin"
            />
            <span className="text-muted-foreground text-[12px]">
              Bootar förhandsvisning…
            </span>
            <span className="text-muted-foreground/70 text-[11px]">
              StackBlitz cold-start kan ta 30–60 sekunder första gången.
            </span>
          </div>
        </div>
      ) : null}

      {/* Pedagogiskt kort när run-dir saknar generated-files (mock-run). */}
      {status.kind === "unavailable" ? (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="pointer-events-auto max-w-md rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-4 text-sm text-amber-800 dark:text-amber-300">
            <div className="mb-1 font-medium">{status.title}</div>
            <div>{status.message}</div>
            {status.hint ? (
              <div className="mt-2 text-[12px] text-amber-700/80 dark:text-amber-300/80">
                {status.hint}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Browser-fallback för Safari/Firefox/iOS. Sajten är byggd men inbäddad
          preview funkar inte (browsern stödjer inte credentialless cross-origin
          isolation). Knappen öppnar samma projekt i nytt fönster på
          stackblitz.com via sdk.openProject — top-level navigation som funkar
          i alla browsers. */}
      {showFallback && status.kind === "fallback" ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="border-border/60 bg-background/95 pointer-events-auto w-full max-w-[460px] rounded-3xl border p-7 shadow-[0_32px_80px_-16px_rgba(0,0,0,0.25)] backdrop-blur-xl">
            <h2 className="text-foreground mb-4 text-[17px] font-semibold tracking-tight">
              Sajten är klar
            </h2>

            <p className="text-foreground/85 mb-3 text-[13px] leading-relaxed">
              {status.browser === "firefox"
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
              Tips: kör{" "}
              <code className="font-mono">python scripts/build_site.py</code>{" "}
              och sätt{" "}
              <code className="font-mono">VIEWSER_PREVIEW_MODE=local-next</code>{" "}
              för en inbäddad preview som fungerar i alla browsers — eller öppna
              Sajtbyggaren i Chrome/Edge/Brave om du vill stanna i
              StackBlitz-läget.
            </p>
          </div>
        </div>
      ) : null}

      {/* StackBlitz SDK error pre — kept as readable diagnostic. */}
      {status.kind === "error" ? (
        <pre className="border-destructive/40 bg-destructive/10 text-destructive absolute bottom-24 left-1/2 z-20 max-h-48 w-[min(90vw,640px)] -translate-x-1/2 overflow-auto rounded-lg border px-3 py-2 text-[11px] whitespace-pre-wrap shadow-lg">
          {status.message}
        </pre>
      ) : null}
    </div>
  );
}
