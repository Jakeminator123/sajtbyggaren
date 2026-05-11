import type { Metadata } from "next";
import Link from "next/link";
import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Blogg",
  description: "Artiklar om Sajtbyggaren — kommer snart.",
};

export default function BloggPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Navbar />

      <main className="flex-1 pt-14">
        <section className="mx-auto max-w-3xl px-6 py-24 text-center sm:py-32">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Blogg
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            Artiklar kommer snart.
          </h1>
          <p className="mt-6 text-base leading-relaxed text-muted-foreground">
            Vi förbereder artiklar om hur AI-genererade sajter byggs i
            praktiken, vad som gör dem snabba, och hur du tar din digitala
            närvaro till nästa nivå.
          </p>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild>
              <Link href="/priser">Se priser</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/om">Läs mer om Sajtbyggaren</Link>
            </Button>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
