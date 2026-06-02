"use client";

import { useState } from "react";

// Öppnar Stripe Customer Portal (hantera/avsluta abonnemang, byt kort).
// Hämtar en portal-url från /api/checkout/portal och redirectar.
export function ManageSubscriptionButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function openPortal() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/checkout/portal", { method: "POST" });
      const data = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (data.url) {
        window.location.href = data.url;
        return;
      }
      setError(data.error ?? "Kunde inte öppna kundportalen.");
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
        onClick={openPortal}
        disabled={busy}
        className="border-border text-foreground hover:bg-muted focus-visible:ring-ring/50 inline-flex h-10 items-center justify-center rounded-full border px-5 text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:opacity-60"
      >
        {busy ? "Öppnar…" : "Hantera abonnemang"}
      </button>
      {error && <p className="text-destructive text-[13px]">{error}</p>}
    </div>
  );
}
