"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useState } from "react";

import { SECONDARY_INTERACTIONS } from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

import { ERROR_ICONS } from "./constants";
import type { ChatMessage } from "./types";

/**
 * ErrorBubble — rik error-presentation med kategori-ikon, tip-text,
 * expanderbar tekniska detaljer och retry-knapp.
 *
 * Designval: en separat komponent istället för att svälla MessageBubble
 * med fler conditionals. Egen state för detail-expand (öppnar inte
 * automatiskt vid mount för att hålla bubblan kompakt).
 */
export function ErrorBubble({
  message,
  onRetry,
}: {
  message: ChatMessage;
  onRetry: (prompt: string) => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const Icon = message.errorKind
    ? ERROR_ICONS[message.errorKind]
    : AlertTriangle;
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
