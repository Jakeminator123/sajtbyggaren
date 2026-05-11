import type { Metadata } from "next";
import Link from "next/link";
import { MinimalFooter } from "@/components/layout";

export const metadata: Metadata = {
  title: "Blogg",
  description: "Artiklar om Sajtmaskin — kommer snart.",
};

export default function BloggPage() {
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

          <h1 className="mb-2 text-2xl font-semibold tracking-tight">Blogg</h1>
          <p className="mb-8 text-sm text-muted-foreground">Kommer snart.</p>

          <Link
            href="/builder"
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Öppna builder
          </Link>
        </div>
      </main>
      <MinimalFooter />
    </>
  );
}
