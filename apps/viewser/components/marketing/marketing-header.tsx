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
import { LOGIN_HINT, LOGIN_HREF, LOGIN_LABEL } from "@/lib/auth-config";

// Marknadssajtens header. Medvetet separat från components/layout/site-header.tsx
// (den är en pointer-events-none preview-overlay för konsolen). Minimal nav:
// Hem / Produkt / Om oss. "Logga in" ligger uppe till vänster (operatörens
// önskemål) bredvid logotypen och pekar in i studion via auth-config-seamen
// så Jakobs riktiga auth kan slottas in senare utan redesign.
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

  return (
    <header className="border-border/60 bg-background/80 sticky top-0 z-40 w-full border-b backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-[1200px] items-center justify-between gap-4 px-5 sm:px-8">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            aria-label="Sajtbyggaren — till startsidan"
            className="focus-visible:ring-ring/50 inline-flex items-center rounded-md focus-visible:ring-2 focus-visible:outline-none"
          >
            <Image
              src="/sajtbyggaren_logo.png"
              alt="Sajtbyggaren"
              width={132}
              height={28}
              style={{ width: "auto" }}
              priority
            />
          </Link>
          <Link
            href={LOGIN_HREF}
            title={LOGIN_HINT}
            className="text-muted-foreground hover:text-foreground hover:border-border focus-visible:ring-ring/50 hidden rounded-full border border-transparent px-3 py-1 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none sm:inline-flex"
          >
            {LOGIN_LABEL}
          </Link>
        </div>

        {/* Desktop-nav: inline pills med aktiv-state. */}
        <nav
          aria-label="Huvudmeny"
          className="hidden items-center gap-1 sm:flex"
        >
          {NAV_ITEMS.map((item) => {
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

        {/* Mobil: hamburgare → Sheet-meny (3 nav-länkar är få men en drawer
            ger fullstora tap-targets + plats för login + primär CTA utan att
            tränga ihop headern). */}
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
            <nav
              aria-label="Mobilmeny"
              className="flex flex-col gap-1 px-2"
            >
              {NAV_ITEMS.map((item) => {
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
                render={<Link href={LOGIN_HREF} />}
                title={LOGIN_HINT}
                className="border-border text-foreground hover:bg-muted focus-visible:ring-ring/50 inline-flex h-11 items-center justify-center rounded-full border text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
              >
                {LOGIN_LABEL}
              </SheetClose>
              <SheetClose
                render={<Link href={LOGIN_HREF} />}
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
