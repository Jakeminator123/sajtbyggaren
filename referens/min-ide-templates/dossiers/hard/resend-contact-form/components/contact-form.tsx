"use client";

import { useState, type FormEvent } from "react";

interface ContactFormProps {
  subjectPrefix?: string;
  className?: string;
}

type SubmitState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; email: string }
  | { kind: "error"; message: string; degraded: boolean };

export function ContactForm({ subjectPrefix, className }: ContactFormProps) {
  const [state, setState] = useState<SubmitState>({ kind: "idle" });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const name = String(formData.get("name") ?? "").trim();
    const email = String(formData.get("email") ?? "").trim();
    const subject = String(formData.get("subject") ?? "").trim();
    const message = String(formData.get("message") ?? "").trim();

    if (!name || !email || !message) {
      setState({ kind: "error", message: "Fill in name, email, and message.", degraded: false });
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setState({ kind: "error", message: "That email address looks invalid.", degraded: false });
      return;
    }

    setState({ kind: "submitting" });
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          subject: subjectPrefix ? `${subjectPrefix}: ${subject || "(no subject)"}` : subject,
          message,
        }),
      });
      const body = (await res.json().catch(() => ({}))) as { ok?: boolean; error?: string };
      if (res.status === 503) {
        setState({
          kind: "error",
          message: "The contact form is not yet configured. Please email us directly.",
          degraded: true,
        });
        return;
      }
      if (!res.ok || !body.ok) {
        setState({
          kind: "error",
          message: body.error ?? `Request failed (${res.status})`,
          degraded: false,
        });
        return;
      }
      setState({ kind: "success", email });
      form.reset();
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Network error.",
        degraded: false,
      });
    }
  }

  if (state.kind === "success") {
    return (
      <div className={className}>
        <div className="rounded-lg border border-border bg-card p-6 text-card-foreground">
          <h3 className="text-lg font-semibold">Thanks — your message is on its way.</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            We&apos;ll reply to <span className="font-medium">{state.email}</span> as soon as we can.
          </p>
        </div>
      </div>
    );
  }

  const submitting = state.kind === "submitting";

  return (
    <form className={className} onSubmit={handleSubmit} noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-foreground">Name</span>
          <input
            name="name"
            required
            autoComplete="name"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-foreground">Email</span>
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
      </div>
      <label className="mt-4 block text-sm">
        <span className="mb-1 block font-medium text-foreground">Subject (optional)</span>
        <input
          name="subject"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </label>
      <label className="mt-4 block text-sm">
        <span className="mb-1 block font-medium text-foreground">Message</span>
        <textarea
          name="message"
          required
          rows={6}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </label>
      {state.kind === "error" && (
        <p
          className={`mt-3 text-sm ${state.degraded ? "text-muted-foreground" : "text-destructive"}`}
        >
          {state.message}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="mt-6 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 disabled:opacity-50"
      >
        {submitting ? "Sending…" : "Send message"}
      </button>
    </form>
  );
}
