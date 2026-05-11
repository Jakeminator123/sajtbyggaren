import type { Metadata } from "next";
import Link from "next/link";
import { MinimalFooter } from "@/components/layout";

export const metadata: Metadata = {
  title: "Om oss",
  description: "Om Sajtmaskin — AI-driven webbplattform för svenska företag.",
};

export default function OmPage() {
  return (
    <>
      <main className="min-h-screen bg-background text-foreground">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <Link
            href="/"
            className="mb-8 inline-block text-sm text-muted-foreground hover:text-foreground"
          >
            &larr; Tillbaka
          </Link>

          <h1 className="mb-2 text-2xl font-semibold tracking-tight">Om Sajtmaskin</h1>
          <p className="mb-10 text-sm text-muted-foreground">
            AI-driven webbplattform av Pretty Good AB. React, Next.js, TypeScript.
          </p>

          <div className="space-y-6 text-sm leading-relaxed text-muted-foreground">
            <p>
              Vi hjälper företag att gå från idé till publicerad sajt — med bra prestanda och
              verktyg anpassade för svensk kontext.
            </p>

            <div>
              <h2 className="mb-1 text-sm font-medium text-foreground">Kontakt</h2>
              <a
                href="mailto:support@sajtmaskin.se"
                className="text-primary hover:underline underline-offset-4"
              >
                support@sajtmaskin.se
              </a>
            </div>

            <div className="flex gap-4 text-xs">
              <Link href="/faq" className="text-primary hover:underline underline-offset-4">
                FAQ
              </Link>
              <Link href="/privacy" className="text-primary hover:underline underline-offset-4">
                Integritetspolicy
              </Link>
            </div>
          </div>
        </div>
      </main>
      <MinimalFooter />
    </>
  );
}
