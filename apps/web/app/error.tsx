"use client";

import { useEffect } from "react";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error("[app/error] Unhandled error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 text-center">
        <h2 className="mb-2 text-xl font-bold text-foreground">Något gick fel</h2>
        <p className="mb-6 text-muted-foreground">Ett oväntat fel inträffade. Försök att ladda om sidan.</p>
        <div className="space-y-3">
          <button
            onClick={() => reset()}
            className="w-full rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition-colors hover:opacity-90"
          >
            Försök igen
          </button>
          <button
            onClick={() => window.location.reload()}
            className="w-full rounded-lg bg-muted px-4 py-2 font-medium text-foreground transition-colors hover:bg-accent"
          >
            Ladda om sidan
          </button>
        </div>
        {process.env.NODE_ENV === "development" && (
          <details className="mt-6 text-left">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              Teknisk information
            </summary>
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-muted p-3 text-xs text-red-400">
              {error.message}
              {"\n\n"}
              {error.stack}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
