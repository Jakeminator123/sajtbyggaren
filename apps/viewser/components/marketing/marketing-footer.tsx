import Link from "next/link";

import { ManageCookiesButton } from "@/components/marketing/manage-cookies-button";

// Marknadssajtens footer. Hårfin, minimal, två nivåer: brand + tagline till
// vänster, länkar till höger; copyright på egen rad under en hårfin avdelare.
// Länkar till de juridiska/hjälpsidor som byggs ut i senare faser (P6) —
// sidorna finns som minimala platshållare redan i P0 så länkarna aldrig
// 404:ar. "Hantera cookies"-triggern kopplas in när CookieBanner/consent-
// providern landar (P6).
const FOOTER_LINKS: ReadonlyArray<{ href: string; label: string }> = [
  { href: "/produkt", label: "Produkt" },
  { href: "/om-oss", label: "Om oss" },
  { href: "/kontakt", label: "Kontakt" },
  { href: "/cookies", label: "Cookies" },
  { href: "/integritetspolicy", label: "Integritetspolicy" },
  { href: "/anvandarvillkor", label: "Användarvillkor" },
];

export function MarketingFooter() {
  return (
    <footer className="border-border/60 bg-background mt-24 w-full border-t">
      <div className="mx-auto w-full max-w-[1200px] px-5 py-12 sm:px-8">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-[34ch] space-y-2">
            <p className="text-foreground text-[15px] font-semibold tracking-tight">
              Sajtbyggaren
            </p>
            <p className="text-muted-foreground text-[13px] leading-relaxed">
              Vi lyfter huvudvärken att bygga och underhålla en hemsida från
              dem som bygger Sverige.
            </p>
          </div>
          <nav
            aria-label="Sidfot"
            className="grid grid-cols-2 gap-x-10 gap-y-1 sm:flex sm:flex-col sm:items-end"
          >
            {FOOTER_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 inline-flex rounded py-1 text-[13px] transition-colors focus-visible:ring-2 focus-visible:outline-none"
              >
                {link.label}
              </Link>
            ))}
            <ManageCookiesButton />
          </nav>
        </div>
        <div className="border-border/50 mt-10 border-t pt-6">
          <p className="text-muted-foreground text-[12.5px]">
            © {new Date().getFullYear()} Sajtbyggaren
          </p>
        </div>
      </div>
    </footer>
  );
}
