"use client";

import { useEffect, useRef, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
  const [status, setStatus] = useState("Välj en run i Run History för förhandsvisning.");
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    // containerRef-div is now mounted unconditionally (see render
    // below) so containerRef.current is bound on every runId change,
    // including transitions out of unavailable=true. The remaining
    // null-check covers the very first render before React has
    // attached the ref (effect runs after commit, but we still keep
    // the guard for defense in depth).
    if (!runId || !containerRef.current) {
      setUnavailable(false);
      return;
    }

    const node = containerRef.current;
    let cancelled = false;
    setStatus(`Laddar filer för ${runId}...`);
    setError(null);
    setUnavailable(false);
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
            setStatus(
              "Förhandsvisning saknas för denna run. Mock-runs (scripts/dev_generate.py) skriver inte en faktisk Next.js-app. Skicka en prompt i promptfältet ovan för att köra en riktig builder-run.",
            );
            return;
          }
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        if (cancelled || !containerRef.current) return;
        setStatus("Startar StackBlitz...");

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
            title: `Viewser Preview ${runId}`,
            description: "Generated site snapshot",
            template: "node",
            files: payload.files,
          },
          {
            openFile: "app/page.tsx",
            view: "preview",
            height: 480,
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
        setStatus(`Förhandsvisning aktiv för ${runId}`);
      } catch (caught) {
        if (!cancelled) {
          setError(formatViewerError(caught));
          setStatus("Förhandsvisning kunde inte startas.");
        }
      }
    })();

    return () => {
      cancelled = true;
      if (node) node.replaceChildren();
    };
  }, [runId]);

  return (
    <Card className="h-full">
      <CardHeader className="border-b">
        <CardTitle className="text-base">Förhandsvisning</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4">
        <p className="text-sm text-muted-foreground">{status}</p>
        {error ? (
          <pre className="whitespace-pre-wrap rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-700 dark:text-red-300">
            {error}
          </pre>
        ) : null}
        {unavailable ? (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            Tips: skicka en prompt i promptfältet ovan. Det kör
            scripts/prompt_to_project_input.py + scripts/build_site.py
            och producerar en riktig Next.js-app som embed:as via
            StackBlitz.
          </div>
        ) : null}
        {/*
          containerRef-div hålls mounted oavsett `unavailable` så
          containerRef.current är bunden över transitions. Tidigare
          satt den i else-grenen av en `unavailable ? tips : <div ref>`
          ternary, vilket avmonterade ref när 404 satte
          unavailable=true - det låste UI:t i stuck state när nästa
          runId valdes (effekten har bara `[runId]` som dep och kör
          inte om vid unavailable-flip). Hidden via Tailwind när
          tips-blocket äger ytan.
        */}
        <div
          ref={containerRef}
          className={`h-[480px] overflow-hidden rounded-md border ${
            unavailable ? "hidden" : ""
          }`}
        />
      </CardContent>
    </Card>
  );
}
