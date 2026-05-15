import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Mail, MapPin, Phone } from "lucide-react";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "En hemsida för en ishockeyspelare som nått hall of fame. jak",
  description: "Svenskspråkig webbplats med 2 sidor för ishockeyspelaren Jakob Eberg, med fokus på hans hall of fame-meriter.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="sv"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">
        <header className="sticky top-0 z-40 border-b border-[color:var(--border)] bg-[color:var(--background)]/80 backdrop-blur supports-[backdrop-filter]:bg-[color:var(--background)]/60">
          <div className="mx-auto flex w-[var(--container-width)] items-center justify-between gap-6 py-4">
            <a href="/" className="flex items-center gap-2 text-base font-semibold">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-[color:var(--primary)] text-[color:var(--primary-foreground)] text-xs font-bold uppercase">{"En"}</span>
              <span className="hidden sm:inline">{"En hemsida för en ishockeyspelare som nått hall of fame. jak"}</span>
            </a>
            <nav className="flex items-center gap-5 text-sm font-medium">
            <a href={"/"} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">Hem</a>
            <a href={"/tjanster"} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">Tjänster</a>
            <a href={"/om-oss"} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">Om oss</a>
            <a href={"/kontakt"} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">Kontakt</a>
            </nav>
            <a href={"/kontakt"} className="hidden md:inline-flex items-center gap-1 rounded-md bg-[color:var(--primary)] px-4 py-2 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">Kontakta oss</a>
          </div>
        </header>
        <div className="flex-1">{children}</div>
        <footer className="border-t border-[color:var(--border)] bg-[color:var(--background)]">
          <div className="mx-auto grid w-[var(--container-width)] gap-8 py-12 md:grid-cols-3">
            <div className="flex flex-col gap-3">
              <p className="text-base font-semibold">{"En hemsida för en ishockeyspelare som nått hall of fame. jak"}</p>
              <p className="text-sm text-[color:var(--muted)]">{"Svenskspråkig webbplats med 2 sidor för ishockeyspelaren Jakob Eberg, med fokus på hans hall of fame-meriter."}</p>
            </div>
            <div className="flex flex-col gap-2 text-sm">
              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>
              <a href={"tel:+4680000000"} className="inline-flex items-center gap-2 hover:underline"><Phone className="size-4" />{"+46 8 000 00 00"}</a>
              <a href={"mailto:kontakt@example.se"} className="inline-flex items-center gap-2 hover:underline"><Mail className="size-4" />{"kontakt@example.se"}</a>
              <p className="inline-flex items-start gap-2 text-[color:var(--muted)]"><MapPin className="size-4 mt-0.5" />{"Adress saknas - uppdatera Project Input"}</p>
            </div>
            <div className="flex flex-col gap-2 text-sm text-[color:var(--muted)]">
              <p className="text-xs uppercase tracking-widest">Sajt</p>
              <a href={"/"} className="hover:underline">Hem</a>
              <a href={"/tjanster"} className="hover:underline">Tjänster</a>
              <a href={"/om-oss"} className="hover:underline">Om oss</a>
              <a href={"/kontakt"} className="hover:underline">Kontakt</a>
            </div>
          </div>
          <div className="border-t border-[color:var(--border)] py-4">
            <p className="mx-auto w-[var(--container-width)] text-xs text-[color:var(--muted)]">© {new Date().getFullYear()} {"En hemsida för en ishockeyspelare som nått hall of fame. jak"}. Alla rättigheter förbehållna.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
