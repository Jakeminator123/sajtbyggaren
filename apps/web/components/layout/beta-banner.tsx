"use client";

import { useState } from "react";
import { X } from "lucide-react";

export function BetaBanner() {
  const enabled = process.env.NEXT_PUBLIC_BETA_BANNER === "1";
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return sessionStorage.getItem("beta_banner_dismissed") === "1";
  });

  if (!enabled || dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem("beta_banner_dismissed", "1");
    } catch {
      /* noop */
    }
  };

  return (
    <div className="relative z-50 border-b border-primary/20 bg-primary/5">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-2">
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Beta</span> — Vi bygger Sveriges
          smartaste sajtbyggare.
        </p>
        <button
          onClick={handleDismiss}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Stäng banner"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
