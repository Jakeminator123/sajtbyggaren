import { ArrowRight, Sparkles } from "lucide-react";

export default function ServicesPage() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">
          <header className="flex flex-col gap-3">
            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Tjänster</p>
            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vad vi gör</h1>
            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Allt vi erbjuder, samlat på ett ställe. Klicka på en tjänst eller hör av dig direkt.</p>
          </header>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <article key={"konsultation"} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all hover:border-[color:var(--primary)] hover:shadow-sm">
            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Sparkles className="size-6" /></span>
            <h2 className="text-xl font-semibold">{"Konsultation"}</h2>
            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{"Inledande konsultation - platshållare som genererats från din prompt. Justera Project Input för att förbättra texten."}</p>
          </article>
          </div>
          <a href={"/kontakt"} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">Begär offert<ArrowRight className="size-4" /></a>
        </div>
      </section>
    </main>
  );
}
