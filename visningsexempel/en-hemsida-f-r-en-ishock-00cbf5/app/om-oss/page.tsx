import { MapPin, Quote } from "lucide-react";

export default function AboutPage() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">
        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">
          <header className="flex flex-col gap-3">
            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Om oss</p>
            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{"En hemsida för en ishockeyspelare som nått hall of fame. jak"}</h1>
          </header>
          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">
            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/20" />
            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{"En hemsida för en ishockeyspelare som nått hall of fame. jakob Eberg heter han och han vill ha två sidror!"}</p>
          </div>
          <div className="flex flex-col gap-4">
            <h2 className="text-2xl font-semibold tracking-tight">Teamet</h2>
            <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">

            </ul>
          </div>
          <div className="flex flex-col gap-2">
            <h2 className="inline-flex items-center gap-2 text-2xl font-semibold tracking-tight"><MapPin className="size-5" />Områden vi arbetar i</h2>
            <p className="text-[color:var(--muted)] leading-relaxed">{"Sverige"}</p>
          </div>
        </div>
      </section>
    </main>
  );
}
