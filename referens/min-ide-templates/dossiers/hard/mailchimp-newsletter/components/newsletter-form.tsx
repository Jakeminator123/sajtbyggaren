"use client";

import { useState, type FormEvent } from "react";

type FormState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; message: string }
  | { kind: "already"; message: string }
  | { kind: "unconfigured" }
  | { kind: "error"; message: string };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface NewsletterFormProps {
  className?: string;
  placeholder?: string;
  submitLabel?: string;
  submittingLabel?: string;
  successMessage?: string;
  alreadyMessage?: string;
  consentNote?: string;
}

export function NewsletterForm({
  className,
  placeholder = "you@example.com",
  submitLabel = "Subscribe",
  submittingLabel = "Subscribing…",
  successMessage = "Thanks! Check your inbox to confirm.",
  alreadyMessage = "You are already subscribed — thanks!",
  consentNote,
}: NewsletterFormProps) {
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const [state, setState] = useState<FormState>({ kind: "idle" });

  const isInvalid = touched && email.length > 0 && !EMAIL_RE.test(email);
  const isBusy = state.kind === "submitting";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!EMAIL_RE.test(email)) {
      setTouched(true);
      return;
    }
    setState({ kind: "submitting" });
    try {
      const res = await fetch("/api/newsletter-subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        status?: "subscribed" | "already";
        error?: string;
      };
      if (res.status === 503) {
        setState({ kind: "unconfigured" });
        return;
      }
      if (!res.ok || !data.ok) {
        setState({
          kind: "error",
          message: data.error === "invalid-email" ? "That email looks off." : "Something went wrong. Try again?",
        });
        return;
      }
      if (data.status === "already") {
        setState({ kind: "already", message: alreadyMessage });
      } else {
        setState({ kind: "success", message: successMessage });
        setEmail("");
      }
    } catch {
      setState({ kind: "error", message: "Network error. Try again?" });
    }
  }

  if (state.kind === "unconfigured") {
    return (
      <div
        className={className ?? "rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"}
        role="status"
      >
        Newsletter is not configured yet. Set <code>MAILCHIMP_API_KEY</code> and{" "}
        <code>MAILCHIMP_AUDIENCE_ID</code> to enable signups.
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={className ?? "flex w-full max-w-md flex-col gap-2"}>
      <div className="flex w-full gap-2">
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => setTouched(true)}
          placeholder={placeholder}
          aria-invalid={isInvalid || state.kind === "error"}
          aria-describedby="newsletter-feedback"
          disabled={isBusy}
          className="flex-1 rounded-md border bg-background px-3 py-2 text-sm aria-[invalid=true]:border-destructive"
        />
        <button
          type="submit"
          disabled={isBusy}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {isBusy ? submittingLabel : submitLabel}
        </button>
      </div>
      {consentNote && <p className="text-xs text-muted-foreground">{consentNote}</p>}
      <p
        id="newsletter-feedback"
        aria-live="polite"
        className="min-h-[1.25rem] text-xs"
      >
        {isInvalid && <span className="text-destructive">Enter a valid email address.</span>}
        {state.kind === "success" && <span className="text-emerald-600">{state.message}</span>}
        {state.kind === "already" && <span className="text-emerald-600">{state.message}</span>}
        {state.kind === "error" && <span className="text-destructive">{state.message}</span>}
      </p>
    </form>
  );
}
