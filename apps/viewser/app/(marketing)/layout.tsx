import { CookieBanner } from "@/components/marketing/cookie-banner";
import { CookieConsentProvider } from "@/components/marketing/cookie-consent";
import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { getCurrentUser } from "@/lib/auth/session";

// Layout för (marketing)-route-gruppen: sticky header → scrollbart main →
// hårfin footer. Wrappar ALLA publika marknadssidor ("/", /produkt, /om-oss,
// /kontakt, legal-sidor, /for/[yrke]) men aldrig konsolen (egen route-grupp).
// Behåller konsolens varma tokens (bg-background/text-foreground) per
// operatörsbeslut D2 — ingen tema-override här.
export default async function MarketingLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Server-läs sessionen en gång och skicka in inloggningsstatusen till
  // headern (klientkomponent). Då växlar "Logga in" → "Mitt konto" utan
  // klient-flimmer och utan att headern importerar server-only-kod.
  const authed = (await getCurrentUser()) !== null;
  return (
    <CookieConsentProvider>
      <div className="flex min-h-dvh flex-col">
        {/* Skip-länk: syns bara vid tangentbordsfokus, hoppar förbi den stickiga
            headern direkt till innehållet (WCAG 2.4.1). */}
        <a
          href="#main-content"
          className="bg-foreground text-background focus-visible:ring-ring/60 sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:px-4 focus:py-2 focus:text-[13px] focus:font-medium focus-visible:ring-2 focus-visible:outline-none"
        >
          Hoppa till innehåll
        </a>
        <MarketingHeader authed={authed} />
        {/* scroll-mt så ankarlänkar inte hamnar bakom den 4rem höga headern. */}
        <main id="main-content" className="flex-1 scroll-mt-16">
          {children}
        </main>
        <MarketingFooter />
      </div>
      <CookieBanner />
    </CookieConsentProvider>
  );
}
