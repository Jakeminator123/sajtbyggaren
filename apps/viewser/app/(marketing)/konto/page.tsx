import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ManageSubscriptionButton } from "@/components/account/manage-subscription-button";
import { LogoutButton } from "@/components/auth/logout-button";
import { AUTH_ENABLED, STUDIO_HREF } from "@/lib/auth-config";
import { getCreditBalance } from "@/lib/auth/credits";
import { listOwnedSiteIds } from "@/lib/auth/owned-sites";
import { getCurrentUser } from "@/lib/auth/session";
import {
  getSubscription,
  isSubscriptionActive,
} from "@/lib/auth/subscriptions";
import { getPlan } from "@/lib/billing/plans";

export const metadata: Metadata = {
  title: "Mitt konto",
  robots: { index: false, follow: false },
};

export default async function AccountPage() {
  // Auth-ytan är opt-in (NEXT_PUBLIC_AUTH_ENABLED). Avstängd → 404.
  if (!AUTH_ENABLED) notFound();
  const user = await getCurrentUser();
  // Middleware grindar redan, men dubbelkolla server-side.
  if (!user) redirect("/login?next=/konto");

  const credits = getCreditBalance(user.id);
  const subscription = getSubscription(user.id);
  const active = isSubscriptionActive(subscription);
  const plan = getPlan(subscription?.planId);
  const sites = listOwnedSiteIds(user.id);

  return (
    <div className="mx-auto w-full max-w-[760px] px-5 py-16 sm:px-8 sm:py-24">
      <div className="flex flex-col gap-2">
        <h1 className="text-foreground text-3xl font-semibold tracking-tight">
          Mitt konto
        </h1>
        <p className="text-muted-foreground text-[15px]">
          {user.name ? `${user.name} · ` : ""}
          {user.email}
        </p>
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {/* Krediter */}
        <section className="border-border/60 flex flex-col gap-3 rounded-3xl border p-6">
          <h2 className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
            Bygg-krediter
          </h2>
          <p className="text-foreground text-4xl font-semibold tracking-tight">
            {credits}
          </p>
          <p className="text-muted-foreground text-[14px]">
            Krediter dras när du bygger eller förfinar en sajt.
          </p>
          <Link
            href="/priser"
            className="text-foreground mt-1 text-[14px] font-medium underline-offset-4 hover:underline"
          >
            Fyll på med ett paket →
          </Link>
        </section>

        {/* Abonnemang */}
        <section className="border-border/60 flex flex-col gap-3 rounded-3xl border p-6">
          <h2 className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
            Abonnemang
          </h2>
          {active && plan ? (
            <>
              <p className="text-foreground text-2xl font-semibold tracking-tight">
                {plan.name}
              </p>
              <p className="text-muted-foreground text-[14px]">
                {plan.creditsPerMonth} krediter per månad.
              </p>
              <div className="mt-1">
                <ManageSubscriptionButton />
              </div>
            </>
          ) : (
            <>
              <p className="text-foreground text-2xl font-semibold tracking-tight">
                Inget aktivt
              </p>
              <p className="text-muted-foreground text-[14px]">
                Välj ett paket för att få krediter varje månad.
              </p>
              <Link
                href="/priser"
                className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 mt-1 inline-flex h-10 w-fit items-center rounded-full px-5 text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
              >
                Se paket
              </Link>
            </>
          )}
        </section>
      </div>

      {/* Mina sajter */}
      <section className="mt-4 flex flex-col gap-4 rounded-3xl border border-border/60 p-6">
        <h2 className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
          Mina sajter
        </h2>
        {sites.length === 0 ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-muted-foreground text-[14px]">
              Du har inte byggt någon sajt än.
            </p>
            <Link
              href={STUDIO_HREF}
              className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-10 items-center rounded-full px-5 text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
            >
              Bygg din första sajt
            </Link>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {sites.map((siteId) => (
              <li
                key={siteId}
                className="border-border/60 flex items-center justify-between rounded-2xl border px-4 py-3"
              >
                <span className="text-foreground font-mono text-[13px]">
                  {siteId}
                </span>
                <Link
                  href={STUDIO_HREF}
                  className="text-foreground text-[14px] font-medium underline-offset-4 hover:underline"
                >
                  Öppna →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="mt-10">
        <LogoutButton />
      </div>
    </div>
  );
}
