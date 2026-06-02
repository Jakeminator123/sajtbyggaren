"use client";

import { useCookieConsent } from "@/components/marketing/cookie-consent";

// Footer-trigger som öppnar cookie-managern igen. Egen klientkomponent så
// MarketingFooter kan förbli en serverkomponent.
export function ManageCookiesButton() {
  const { openManager } = useCookieConsent();
  return (
    <button
      type="button"
      onClick={openManager}
      className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 inline-flex rounded py-1 text-left text-[13px] transition-colors focus-visible:ring-2 focus-visible:outline-none"
    >
      Hantera cookies
    </button>
  );
}
