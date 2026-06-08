"use client";

import { Menu } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { STUDIO_HREF } from "@/lib/routes";

// Marknadssajtens header. Medvetet separat från components/layout/site-header.tsx
// (den är en pointer-events-none preview-overlay för konsolen). Minimal nav:
// Hem / Produkt / Om oss — centrerad. Logotypen ligger till vänster och primär
// bygg-CTA längst till höger (auth/billing är parkerat tills operatören slår
// på det i en egen PR).
const NAV_ITEMS: ReadonlyArray<{ href: string; label: string }> = [
  { href: "/", label: "Hem" },
  { href: "/produkt", label: "Produkt" },
  { href: "/om-oss", label: "Om oss" },
];

// Aktiv-länk: exakt match för "/" (annars vore allt "aktivt"), prefix-match
// för djupare sidor så ev. framtida undersidor markerar rätt toppnav.
function useIsActive() {
  const pathname = usePathname();
  return (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function MarketingHeader() {
  const isActive = useIsActive();
  const navItems = NAV_ITEMS;

  return (
    <header className="border-border/60 bg-background/80 sticky top-0 z-40 w-full border-b backdrop-blur-xl">
      <div className="relative mx-auto flex h-16 w-full max-w-[1200px] items-center justify-between gap-4 px-5 sm:px-8">
        {/* Vänster: logotyp. */}
        <Link
          href="/"
          aria-label="Sajtbyggaren — till startsidan"
          className="focus-visible:ring-ring/50 inline-flex items-center rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <Image
            src="/sajtbyggaren_logo.png"
            alt="Sajtbyggaren"
            width={90}
            height={22}
            priority
            // Höjd via ``h-[22px]``; ``w-auto`` + ``style.width:auto`` bevarar
            // aspect-ratio (intrinsisk 1750×426) och tystar Next:s
            // "width or height modified, but not the other"-varning.
            style={{ width: "auto" }}
            className="h-[22px] w-auto object-contain"
          />
        </Link>

        {/* Center: desktop-nav, absolut centrerad i headern oavsett logo-/
            entry-bredd (operatörens önskemål om centrerade menyval). */}
        <nav
          aria-label="Huvudmeny"
          className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-1 sm:flex"
        >
          {navItems.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`focus-visible:ring-ring/50 inline-flex items-center rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none ${
                  active
                    ? "text-foreground bg-foreground/[0.06]"
                    : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Höger (desktop): primär bygg-CTA. Mobilen får samma CTA längst ner
            i Sheet-menyn nedan, så headern hålls ren på små skärmar. */}
        <Link
          href={STUDIO_HREF}
          className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 hidden h-9 items-center justify-center rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98] sm:inline-flex"
        >
          Bygg din hemsida
        </Link>

        {/* Mobil: hamburgare → Sheet-meny (3 nav-länkar är få men en drawer
            ger fullstora tap-targets + primär CTA utan att tränga ihop
            headern). */}
        <Sheet>
          <SheetTrigger
            aria-label="Öppna meny"
            className="border-border/60 bg-card/80 text-foreground/80 hover:bg-card focus-visible:ring-ring/50 min-tap inline-flex items-center justify-center rounded-full border shadow-sm backdrop-blur-xl transition focus-visible:ring-2 focus-visible:outline-none active:scale-95 sm:hidden"
          >
            <Menu className="h-4 w-4" aria-hidden />
          </SheetTrigger>
          <SheetContent side="right" className="w-72">
            <SheetHeader>
              <SheetTitle>Meny</SheetTitle>
            </SheetHeader>
            <nav aria-label="Mobilmeny" className="flex flex-col gap-1 px-2">
              {navItems.map((item) => {
                const active = isActive(item.href);
                return (
                  <SheetClose
                    key={item.href}
                    render={<Link href={item.href} />}
                    aria-current={active ? "page" : undefined}
                    className={`focus-visible:ring-ring/50 rounded-xl px-3 py-3 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none ${
                      active
                        ? "text-foreground bg-foreground/[0.06]"
                        : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04]"
                    }`}
                  >
                    {item.label}
                  </SheetClose>
                );
              })}
            </nav>
            <div className="mt-auto flex flex-col gap-2 p-4">
              <SheetClose
                render={<Link href={STUDIO_HREF} />}
                className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-11 items-center justify-center rounded-full text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
              >
                Bygg din hemsida
              </SheetClose>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
