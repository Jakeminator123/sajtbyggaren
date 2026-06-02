"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { LOGIN_HREF, REGISTER_HREF } from "@/lib/auth-config";

// Delat login-/registreringsformulär. Minimalistisk marknadsestetik (vita
// fält, svart pill-knapp, ljusgrå ramar). Postar mot /api/auth/* och navigerar
// vidare vid lyckat svar. Rör ingen bygg-logik.
type Mode = "login" | "register";

function safeNext(next: string | undefined, fallback: string): string {
  // Skydda mot open-redirect: tillåt bara interna sökvägar.
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return fallback;
}

export function AuthForm({
  mode,
  next,
}: {
  mode: Mode;
  next?: string;
}) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === "register";
  const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(
          isRegister
            ? { email, password, name: name || undefined }
            : { email, password },
        ),
      });
      const data = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) {
        setError(data.error ?? "Något gick fel. Försök igen.");
        setSubmitting(false);
        return;
      }
      // Server-komponenter (header, /konto) måste läsa om sessionen.
      router.push(safeNext(next, "/konto"));
      router.refresh();
    } catch {
      setError("Kunde inte nå servern. Kontrollera din anslutning.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      {isRegister && (
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="name"
            className="text-foreground text-[13px] font-medium"
          >
            Namn <span className="text-muted-foreground">(valfritt)</span>
          </label>
          <input
            id="name"
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="border-border bg-card text-foreground placeholder:text-muted-foreground focus-visible:ring-ring/50 h-12 w-full rounded-xl border px-4 text-[15px] outline-none transition focus-visible:ring-2"
            placeholder="Ditt namn"
          />
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="email"
          className="text-foreground text-[13px] font-medium"
        >
          E-post
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="border-border bg-card text-foreground placeholder:text-muted-foreground focus-visible:ring-ring/50 h-12 w-full rounded-xl border px-4 text-[15px] outline-none transition focus-visible:ring-2"
          placeholder="din@epost.se"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="password"
          className="text-foreground text-[13px] font-medium"
        >
          Lösenord
        </label>
        <input
          id="password"
          type="password"
          autoComplete={isRegister ? "new-password" : "current-password"}
          required
          minLength={isRegister ? 8 : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="border-border bg-card text-foreground placeholder:text-muted-foreground focus-visible:ring-ring/50 h-12 w-full rounded-xl border px-4 text-[15px] outline-none transition focus-visible:ring-2"
          placeholder={isRegister ? "Minst 8 tecken" : "Ditt lösenord"}
        />
      </div>

      {error && (
        <p
          role="alert"
          className="text-destructive bg-destructive/5 border-destructive/20 rounded-xl border px-4 py-3 text-[14px]"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 mt-1 inline-flex h-12 items-center justify-center rounded-full text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting
          ? "Ett ögonblick…"
          : isRegister
            ? "Skapa konto"
            : "Logga in"}
      </button>

      {!isRegister && (
        <Link
          href="/glomt-losenord"
          className="text-muted-foreground hover:text-foreground text-center text-[13px] transition-colors"
        >
          Glömt lösenordet?
        </Link>
      )}

      <p className="text-muted-foreground mt-2 text-center text-[14px]">
        {isRegister ? "Har du redan ett konto? " : "Inget konto än? "}
        <Link
          href={isRegister ? LOGIN_HREF : REGISTER_HREF}
          className="text-foreground font-medium underline-offset-4 hover:underline"
        >
          {isRegister ? "Logga in" : "Skapa konto"}
        </Link>
      </p>
    </form>
  );
}
