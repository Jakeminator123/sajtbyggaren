"use client";

import { useState, type FormEvent } from "react";

type notice_kind = "idle" | "success" | "error" | "design";

type notice_state = {
  kind: notice_kind;
  message: string;
};

type resend_contact_form_props = {
  submitPath: string;
  designModeAtBuild?: boolean;
  designModeMessage: string;
};

function _notice_classes(kind: notice_kind): string {
  if (kind === "success") {
    return "text-emerald-700";
  }
  if (kind === "design") {
    return "text-amber-700";
  }
  return "text-red-700";
}

function _safe_string(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function ResendContactForm({
  submitPath,
  designModeAtBuild = false,
  designModeMessage,
}: resend_contact_form_props) {
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<notice_state>({ kind: "idle", message: "" });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }

    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = {
      name: _safe_string(formData.get("name")),
      email: _safe_string(formData.get("email")),
      phone: _safe_string(formData.get("phone")),
      message: _safe_string(formData.get("message")),
    };

    setPending(true);
    setNotice({ kind: "idle", message: "" });

    try {
      const response = await fetch(submitPath, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({} as Record<string, unknown>));
      const message =
        typeof body.message === "string" && body.message.trim()
          ? body.message
          : "Kunde inte tolka svaret från servern.";

      if (!response.ok) {
        const mode = body.mode === "design" ? "design" : "error";
        setNotice({ kind: mode, message });
        return;
      }

      setNotice({ kind: "success", message });
      form.reset();
    } catch {
      setNotice({
        kind: "error",
        message: "Något gick fel vid skickning. Försök igen.",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Namn</span>
          <input
            name="name"
            required
            className="w-full rounded-md border border-[color:var(--border)] bg-[color:var(--background)] px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">E-post</span>
          <input
            name="email"
            type="email"
            required
            className="w-full rounded-md border border-[color:var(--border)] bg-[color:var(--background)] px-3 py-2"
          />
        </label>
      </div>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Telefon (valfritt)</span>
        <input
          name="phone"
          type="tel"
          inputMode="tel"
          className="w-full rounded-md border border-[color:var(--border)] bg-[color:var(--background)] px-3 py-2"
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Meddelande</span>
        <textarea
          name="message"
          required
          rows={6}
          className="w-full rounded-md border border-[color:var(--border)] bg-[color:var(--background)] px-3 py-2"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="inline-flex items-center rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? "Skickar..." : "Skicka meddelande"}
      </button>
      {designModeAtBuild ? (
        <p className="text-sm text-amber-700" role="status" aria-live="polite">
          {designModeMessage}
        </p>
      ) : null}
      {notice.kind !== "idle" ? (
        <p className={`text-sm ${_notice_classes(notice.kind)}`} role="status" aria-live="polite">
          {notice.message}
        </p>
      ) : null}
    </form>
  );
}
