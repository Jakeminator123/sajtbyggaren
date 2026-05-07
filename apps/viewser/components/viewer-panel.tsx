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
  const [status, setStatus] = useState("Välj eller skapa en run för preview.");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !containerRef.current) return;

    let cancelled = false;
    setStatus(`Laddar filer för ${runId}...`);
    setError(null);

    void (async () => {
      try {
        const response = await fetch(`/api/runs/${runId}/files`);
        const payload = (await response.json()) as FilesPayload;
        if (!response.ok || payload.error) {
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
            height: 560,
          },
        );
        if (!cancelled) {
          setStatus(`Preview aktiv för ${runId}`);
        }
      } catch (caught) {
        if (!cancelled) {
          const message = caught instanceof Error ? caught.message : "Okänt viewer-fel.";
          setError(message);
          setStatus("Preview kunde inte startas.");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId]);

  return (
    <Card className="h-full">
      <CardHeader className="border-b">
        <CardTitle className="text-base">Viewer Panel</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4">
        <p className="text-sm text-muted-foreground">{status}</p>
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
        <div ref={containerRef} className="h-[560px] overflow-hidden rounded-md border" />
      </CardContent>
    </Card>
  );
}
