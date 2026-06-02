import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StarterCta } from "@/components/marketing/starter-cta";
import { PROFESSIONS, getProfession } from "@/lib/professions";

// Endast de 20 kända yrkena prerenderas; okända slugs → 404 (ingen on-demand
// rendering av godtyckliga slugs).
export const dynamicParams = false;

export function generateStaticParams() {
  return PROFESSIONS.map((p) => ({ yrke: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ yrke: string }>;
}): Promise<Metadata> {
  const { yrke } = await params;
  const profession = getProfession(yrke);
  if (!profession) return {};
  const title = `Hemsida för ${profession.displayName.toLowerCase()}`;
  return {
    title,
    description: profession.pitch,
    alternates: { canonical: `/for/${profession.slug}` },
    openGraph: {
      title: `${title} · Sajtbyggaren`,
      description: profession.pitch,
      images: [
        {
          url: profession.image,
          width: 1280,
          height: 960,
          alt: profession.displayName,
        },
      ],
    },
  };
}

const BENEFITS: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "Färdig på minuter",
    body: "Beskriv din verksamhet — AI:n bygger en komplett sida åt dig.",
  },
  {
    title: "Förfina med ord",
    body: "Be om ändringar i vanlig svenska, så bygger vi om.",
  },
  {
    title: "Snabb & mobilanpassad",
    body: "Redo för kunderna direkt, på alla skärmar.",
  },
];

export default async function ProfessionLandingPage({
  params,
}: {
  params: Promise<{ yrke: string }>;
}) {
  const { yrke } = await params;
  const profession = getProfession(yrke);
  if (!profession) notFound();

  return (
    <>
      {/* Bild-led hero. */}
      <section className="mx-auto w-full max-w-[1200px] px-5 pt-12 sm:px-8 sm:pt-20">
        <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
          Sajtbyggaren för {profession.displayName.toLowerCase()}
        </p>
        <div className="mt-6 grid items-center gap-8 lg:grid-cols-2 lg:gap-12">
          <div>
            <h1 className="text-foreground text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
              {profession.headline}
            </h1>
            <p className="text-muted-foreground mt-5 max-w-[52ch] text-[16px] leading-relaxed sm:text-[18px]">
              {profession.pitch}
            </p>
            <div className="mt-7">
              <StarterCta
                promptSeed={profession.promptSeed}
                family={profession.family}
                category={profession.category}
              />
            </div>
          </div>
          <div className="border-border/60 relative aspect-[4/3] w-full overflow-hidden rounded-3xl border">
            <Image
              src={profession.image}
              alt={profession.displayName}
              fill
              sizes="(max-width: 1024px) 100vw, 600px"
              className="object-cover"
              priority
            />
          </div>
        </div>
      </section>

      {/* Tre mikrofördelar. */}
      <section className="mx-auto w-full max-w-[1200px] px-5 py-24 sm:px-8 sm:py-32">
        <ul className="grid gap-px overflow-hidden rounded-3xl border border-border/60 bg-border/60 sm:grid-cols-3">
          {BENEFITS.map((b) => (
            <li key={b.title} className="bg-background flex flex-col gap-2 p-6">
              <span className="text-foreground text-[17px] font-semibold tracking-tight">
                {b.title}
              </span>
              <span className="text-muted-foreground text-[14px] leading-relaxed">
                {b.body}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* Slut-CTA. */}
      <section className="bg-foreground text-background">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col items-center gap-6 px-5 py-24 text-center sm:px-8 sm:py-32">
          <h2 className="max-w-[22ch] text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Redo att ge din {profession.displayName.toLowerCase()} en hemsida
            som känns rätt?
          </h2>
          <StarterCta
            promptSeed={profession.promptSeed}
            family={profession.family}
            category={profession.category}
            tone="light"
          />
          <Link
            href="/"
            className="text-background/70 hover:text-background focus-visible:ring-background/50 rounded text-[14px] underline-offset-4 transition-colors hover:underline focus-visible:ring-2 focus-visible:outline-none"
          >
            ← Tillbaka till startsidan
          </Link>
        </div>
      </section>
    </>
  );
}
