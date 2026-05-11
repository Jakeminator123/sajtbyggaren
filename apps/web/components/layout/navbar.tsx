import Link from "next/link";
import Image from "next/image";
import { HeaderActions } from "./header-actions";

/**
 * Navbar för apps/web.
 *
 * Logon består av SVG-symbol (raket från /icon.svg) + textlogotyp
 * "Sajtbyggaren" i ett heading-typsnitt. PNG-logon från Sajtmaskin
 * (LOGO_SM2.0.png) sade "SAJTMASKIN" och kan inte bytas ut utan att
 * regenerera bildfilen.
 */
export function Navbar() {
  return (
    <nav className="fixed top-0 right-0 left-0 z-50 h-14 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-4">
        <Link
          href="/"
          className="flex items-center gap-2 transition-opacity hover:opacity-80"
          aria-label="Sajtbyggaren – startsida"
        >
          <Image
            src="/icon.svg"
            alt=""
            aria-hidden="true"
            width={28}
            height={28}
            className="h-6 w-6 md:h-7 md:w-7"
            priority
          />
          <span className="font-heading text-base font-semibold tracking-tight text-foreground md:text-lg">
            Sajtbyggaren
          </span>
        </Link>

        <HeaderActions />
      </div>
    </nav>
  );
}
