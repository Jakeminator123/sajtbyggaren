import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AUTH_ENABLED } from "@/lib/auth-config";

// Auth-route-gruppen ((auth)): /login, /registrera, /glomt-losenord. Egen,
// avskalad chrome — ingen marknads-nav/footer, bara logotyp + centrerat kort.
// noindex: inloggningssidor ska inte indexeras.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Auth-ytan är opt-in (NEXT_PUBLIC_AUTH_ENABLED). Avstängd → 404.
  if (!AUTH_ENABLED) notFound();
  return (
    <div className="bg-background flex min-h-dvh flex-col">
      <header className="flex h-16 w-full items-center px-5 sm:px-8">
        <Link
          href="/"
          aria-label="Sajtbyggaren — till startsidan"
          className="focus-visible:ring-ring/50 inline-flex items-center rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <Image
            src="/sajtbyggaren_logo.png"
            alt="Sajtbyggaren"
            width={106}
            height={22}
            style={{ width: "auto" }}
            priority
          />
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-[400px]">{children}</div>
      </main>
    </div>
  );
}
