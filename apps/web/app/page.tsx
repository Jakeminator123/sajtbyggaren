import Link from "next/link";
import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";

/**
 * Publik landningssida för Sajtbyggaren.
 *
 * apps/web är en UI-import från Sajtmaskin. Den fulla "skapa hemsida"-
 * pipelinen drivs i nya repot av `backend.py` + `packages/generation/` och
 * är inte ansluten till denna app än. Tills dess används en lugn,
 * informativ landning utan modaler eller builder-flöde.
 */
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Navbar har optional onLoginClick/onRegisterClick. apps/web är ren UI
          utan auth ännu (se apps/web/README.md) så vi låter Navbar:s
          interna defaults gälla. */}
      <Navbar />

      <main className="flex-1">
        <section className="mx-auto flex max-w-5xl flex-col items-center px-6 py-24 text-center sm:py-32">
          <p className="mb-4 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            En tjänst från Pretty Good AB
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
            Företagshemsidor på minuter — gjorda av AI.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Sajtbyggaren genererar professionella webbplatser med tydlig copy,
            korrekt struktur och Apple-inspirerad design. Beskriv ditt företag,
            så bygger vi första versionen åt dig.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild size="lg">
              <Link href="/priser">Se priser</Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/om">Läs mer om Sajtbyggaren</Link>
            </Button>
          </div>
        </section>

        <section className="border-t border-border bg-muted/30">
          <div className="mx-auto grid max-w-5xl gap-10 px-6 py-20 sm:grid-cols-3">
            <Highlight
              title="Snabbt."
              body="Beskriv ditt företag på en minut. AI:n bygger sidan, vi finputsar."
            />
            <Highlight
              title="Professionellt."
              body="Korrekt SEO, snabba bilder, mobilanpassat. Inte ett 'AI-mock'."
            />
            <Highlight
              title="Ditt företag."
              body="Egen domän, egen brand, egen ton. Vi anpassar tills det stämmer."
            />
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}

function Highlight({ title, body }: { title: string; body: string }) {
  return (
    <div className="text-left">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <p className="mt-3 text-base leading-relaxed text-muted-foreground">
        {body}
      </p>
    </div>
  );
}
