import { ArrowRight, Clock, Mail, MapPin, Phone, Quote, ShieldCheck, Sparkles } from "lucide-react";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="relative overflow-hidden bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/30">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">
          <div className="flex items-center gap-2 text-sm uppercase tracking-widest text-[color:var(--muted)]">
            <MapPin className="size-4" />
            <span>{"Sverige"}</span>
          </div>
          <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">{"En hemsida för en ishockeyspelare som nått hall of fame. jak"}</h1>
          <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{"Svenskspråkig webbplats med 2 sidor för ishockeyspelaren Jakob Eberg, med fokus på hans hall of fame-meriter."}</p>
          <div className="flex flex-wrap gap-3">
            <a href={"/kontakt"} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">Begär offert<ArrowRight className="size-4" /></a>
            <a href={"tel:+4680000000"} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {"+46 8 000 00 00"}</a>
          </div>
        </div>
      </section>

      <section className="border-t border-[color:var(--border)]">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">
          <div className="flex flex-col gap-3">
            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Tjänster</p>
            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Vad vi tar oss an</h2>
          </div>
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <li key={"konsultation"} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--card,var(--background))] p-6 transition-all hover:border-[color:var(--primary)] hover:shadow-sm">
              <span className="mb-4 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Sparkles className="size-5" /></span>
              <h3 className="text-lg font-semibold">{"Konsultation"}</h3>
              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{"Inledande konsultation - platshållare som genererats från din prompt. Justera Project Input för att förbättra texten."}</p>
            </li>
          </ul>
          <a href={"/tjanster"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se alla tjänster<ArrowRight className="size-4" /></a>
        </div>
      </section>

      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/20">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Varför oss</h2>
          <ul className="grid gap-4 md:grid-cols-2">

          </ul>
        </div>
      </section>

      <section className="border-t border-[color:var(--border)] bg-[color:var(--primary)] text-[color:var(--primary-foreground)]">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Hör av dig idag</h2>
          <p className="max-w-2xl text-base opacity-90 md:text-lg">Beskriv kort vad du behöver så återkommer vi inom en arbetsdag.</p>
          <a href={"/kontakt"} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary-foreground)] px-5 py-3 text-sm font-medium text-[color:var(--primary)] hover:opacity-90 transition-opacity">Kontakta oss<ArrowRight className="size-4" /></a>
        </div>
      </section>
    </main>
  );
}
