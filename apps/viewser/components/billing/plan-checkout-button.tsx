"use client";

import { useState } from "react";

import type { PlanId } from "@/lib/billing/plans";

// Startar Stripe Checkout för ett paket. Om användaren inte är inloggad
// (401) skickas hen till /login med retur till /priser. Annars redirectar vi
// till den Stripe-hostade checkout-sidan.
export function PlanCheckoutButton({
  planId,
  highlighted,
}: {
  planId: PlanId;
  highlighted?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/checkout", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ planId }),
      });
      if (response.status === 401) {
        window.location.href = "/login?next=/priser";
        return;
      }
      const data = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (data.url) {
        window.location.href = data.url;
        return;
      }
      setError(data.error ?? "Kunde inte starta köpet.");
      setBusy(false);
    } catch {
      setError("Kunde inte nå servern.");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={startCheckout}
        disabled={busy}
        className={`focus-visible:ring-ring/50 inline-flex h-11 items-center justify-center rounded-full px-6 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${
          highlighted
            ? "bg-foreground text-background hover:bg-foreground/90"
            : "border-border text-foreground hover:bg-muted border"
        }`}
      >
        {busy ? "Ett ögonblick…" : "Kom igång"}
      </button>
      {error && <p className="text-destructive text-[13px]">{error}</p>}
    </div>
  );
}
