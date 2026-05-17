"use client";

import { useEffect, useRef, useState } from "react";

type ViewerPanelProps = {
  runId: string | null;
};

type FilesPayload = {
  runId: string;
  files: Record<string, string>;
  error?: string;
};

function formatViewerError(caught: unknown): string {
  if (caught instanceof Error) {
    const details = [
      `name: ${caught.name || "Error"}`,
      `message: ${caught.message || "(empty message)"}`,
    ];
    if (caught.stack) {
      details.push(`stack:\n${caught.stack.split("\n").slice(0, 20).join("\n")}`);
    }
    return details.join("\n");
  }

  try {
    return `non-Error rejection:\n${JSON.stringify(caught, null, 2)}`;
  } catch {
    return `non-Error rejection:\n${String(caught)}`;
  }
}

export function ViewerPanel({ runId }: ViewerPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState("Beskriv en sajt nedan så bygger vi den åt dig.");
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(false);

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
      return;
    }

    const node = containerRef.current;
    let cancelled = false;
    setStatus(`Laddar filer för ${runId}…`);
    setError(null);
    setUnavailable(false);
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
            setStatus(
              "Förhandsvisning saknas för denna run. Mock-runs skriver inte en faktisk Next.js-app — skicka en prompt i chat-rutan för att köra en riktig builder-run.",
            );
            return;
          }
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        if (cancelled || !containerRef.current) return;
        setStatus("Startar StackBlitz…");

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

        await sdk.embedProject(
          mountTarget,
          {
            title: `Sajtbyggaren preview ${runId}`,
            description: "Generated site snapshot",
            template: "node",
            files: payload.files,
          },
          {
            openFile: "app/page.tsx",
            view: "preview",
            height: 1200,
          },
        );

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

        setStatus(`Förhandsvisning aktiv för ${runId}`);
        setLoading(false);
      } catch (caught) {
        if (!cancelled) {
          setError(formatViewerError(caught));
          setStatus("Förhandsvisning kunde inte startas.");
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

  return (
    <div className="viewer-canvas relative flex h-full w-full overflow-hidden bg-background">
      {/* Thin top progress strip while building/loading. */}
      {loading ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-20 h-[2px] overflow-hidden bg-transparent"
        >
          <div className="h-full w-1/3 animate-[viewer-progress_1.6s_ease-in-out_infinite] rounded-full bg-foreground/70" />
        </div>
      ) : null}

      {/* Empty hero — visible only when no run is selected. */}
      {showEmpty ? (
        <div className="flex h-full w-full items-center justify-center px-6">
          <div className="flex max-w-xl flex-col items-center gap-3 text-center">
            <span className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground/70">
              Sajtbyggaren · localhost
            </span>
            <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
              Beskriv din sajt så bygger vi den.
            </h1>
            <p className="text-balance text-sm text-muted-foreground sm:text-base">
              Skriv vad sajten ska göra. Vi genererar Project Input, kör Quality
              Gate och paketerar en preview du kan inspektera direkt här.
            </p>
          </div>
        </div>
      ) : null}

      {/* Inline status (only while loading a real run). */}
      {!showEmpty && (status || loading) ? (
        <div className="pointer-events-none absolute left-4 top-4 z-20 flex items-center gap-2 rounded-full border border-border/60 bg-card/85 px-3 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
          {loading ? (
            <span className="inline-block size-1.5 animate-pulse rounded-full bg-foreground/70" />
          ) : (
            <span className="inline-block size-1.5 rounded-full bg-emerald-500" />
          )}
          <span className="max-w-[44ch] truncate">{status}</span>
        </div>
      ) : null}

      {/* Unavailable banner. */}
      {showUnavailable ? (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="max-w-md rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-4 text-sm text-amber-800 dark:text-amber-300">
            Förhandsvisning saknas för denna run. Mock-runs skriver inte en
            faktisk Next.js-app — skicka en prompt i chat-rutan för att köra
            en riktig builder-run.
          </div>
        </div>
      ) : null}

      {/* StackBlitz SDK error pre — kept as readable diagnostic. */}
      {error ? (
        <pre className="absolute bottom-24 left-1/2 z-20 max-h-48 w-[min(90vw,640px)] -translate-x-1/2 overflow-auto whitespace-pre-wrap rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-[11px] text-destructive shadow-lg">
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
        className={`h-full w-full ${unavailable || showEmpty ? "invisible" : ""}`}
      />
    </div>
  );
}
