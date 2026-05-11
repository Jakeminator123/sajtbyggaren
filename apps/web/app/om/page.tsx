import type { Metadata } from "next";
import Link from "next/link";
import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Om oss",
  description:
    "Om Sajtbyggaren — AI-driven webbplattform för svenska företag.",
};

export default function OmPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Navbar />

      <main className="flex-1 pt-14">
        <section className="mx-auto max-w-3xl px-6 py-20 sm:py-24">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            En tjänst från Pretty Good AB
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            Om Sajtbyggaren
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
            Vi hjälper svenska företag att gå från idé till publicerad sajt —
            med bra prestanda, korrekt SEO och verktyg anpassade för svensk
            kontext.
          </p>

          <div className="mt-12 grid gap-10 sm:grid-cols-2">
            <div>
              <h2 className="text-base font-semibold text-foreground">
                Bakom plattformen
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Sajtbyggaren drivs av Pretty Good AB (org.nr DG97), ett svenskt
                bolag med fokus på AI-driven produktutveckling. Plattformen är
                byggd med React 19, Next.js 16 och TypeScript.
              </p>
            </div>

            <div>
              <h2 className="text-base font-semibold text-foreground">
                Kontakt
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Maila oss på{" "}
                <a
                  href="mailto:hej@sajtbyggaren.se"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  hej@sajtbyggaren.se
                </a>
                {" "}så hör vi av oss inom en arbetsdag.
              </p>
            </div>
          </div>

          <div className="mt-12 flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/priser">Se priser</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/faq">Vanliga frågor</Link>
            </Button>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
