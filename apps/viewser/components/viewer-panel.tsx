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

export function ViewerPanel({ runId }: ViewerPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState("Välj en run i Run History för förhandsvisning.");
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!runId || !containerRef.current) {
      setUnavailable(false);
      return;
    }

    const node = containerRef.current;
    let cancelled = false;
    setStatus(`Laddar filer för ${runId}...`);
    setError(null);
    setUnavailable(false);
    node.innerHTML = "";

    void (async () => {
      try {
        const response = await fetch(`/api/runs/${runId}/files`);
        const payload = (await response.json()) as FilesPayload;
        if (!response.ok || payload.error) {
          // 404 = run-dir saknar generated-files / .generated/<siteId>/.
          // Det är förväntat för dev_generate-mock-runs (placeholder-pipeline).
          // Visa pedagogisk fallback istället för stack trace.
          if (response.status === 404) {
            setUnavailable(true);
            setStatus(
              "Förhandsvisning saknas för denna run. Mock-runs (scripts/dev_generate.py) skriver inte en faktisk Next.js-app. Kör Build via en Project Input istället.",
            );
            return;
          }
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        if (cancelled || !containerRef.current) return;
        setStatus("Startar StackBlitz...");

        const sdk = (await import("@stackblitz/sdk")).default;
        await sdk.embedProject(
          containerRef.current,
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
        if (!cancelled) {
          setStatus(`Förhandsvisning aktiv för ${runId}`);
        }
      } catch (caught) {
        if (!cancelled) {
          const message = caught instanceof Error ? caught.message : "Okänt viewer-fel.";
          setError(message);
          setStatus("Förhandsvisning kunde inte startas.");
        }
      }
    })();

    return () => {
      cancelled = true;
      if (node) node.innerHTML = "";
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
          <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        ) : null}
        {unavailable ? (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            Tips: välj en Project Input och klicka Build. Det kör
            scripts/build_site.py som producerar en riktig Next.js-app som
            embed:as via StackBlitz.
          </div>
        ) : (
          <div ref={containerRef} className="h-[480px] overflow-hidden rounded-md border" />
        )}
      </CardContent>
    </Card>
  );
}
