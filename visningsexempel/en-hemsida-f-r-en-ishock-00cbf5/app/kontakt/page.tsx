import { Clock, Mail, MapPin, Phone } from "lucide-react";

export default function ContactPage() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">
          <header className="flex flex-col gap-3">
            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>
            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Hör av dig</h1>
            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Beskriv jobbet kort så återkommer vi inom en arbetsdag med tider och offert.</p>
          </header>
          <div className="grid gap-4 md:grid-cols-2">
            <article className="rounded-xl border border-[color:var(--border)] p-6">
              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Phone className="size-5" /></span>
              <h2 className="text-base font-semibold">Telefon</h2>
              <a href={"tel:+4680000000"} className="mt-2 block text-lg font-medium hover:underline">{"+46 8 000 00 00"}</a>
              <p className="mt-2 inline-flex items-center gap-2 text-sm text-[color:var(--muted)]">
                <Clock className="size-4" />
                <span>{"Mån-Fre 09:00-17:00"}</span>
              </p>
            </article>
            <article className="rounded-xl border border-[color:var(--border)] p-6">
              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Mail className="size-5" /></span>
              <h2 className="text-base font-semibold">E-post</h2>
              <a href={"mailto:kontakt@example.se"} className="mt-2 block text-lg font-medium hover:underline">{"kontakt@example.se"}</a>
            </article>
            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">
              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>
              <h2 className="text-base font-semibold">Adress</h2>
              <address className="mt-2 not-italic">
                <span className="block">{"Adress saknas - uppdatera Project Input"}</span>
              </address>
            </article>
          </div>
        </div>
      </section>
    </main>
  );
}
