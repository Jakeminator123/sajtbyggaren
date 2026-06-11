# When to use

Use this dossier when the operator or user explicitly asks for a real server-side contact form flow (for example "Resend", "API-based contact form", "send without mail client", or "track delivery failures"). It is the hard alternative to `mailto-contact-form`.

Best fit:

- The business wants backend delivery instead of relying on the visitor's mail client.
- The contact page should keep a complete form UI even before secrets are configured.
- The team accepts hard-dossier constraints (env contract + server route + honest design mode).

Do not use for:

- Week-1 quick launches that should run without any runtime env (use `mailto-contact-form`).
- Cases where the user did not explicitly ask for an API-backed contact integration.
- Flows that need file uploads, CRM sync, or advanced anti-spam logic (separate hard dossier).

# How this dossier ships

The dossier mounts a client form component plus a local server route (`/api/contact/resend`).

- Integration mode (env present): the route validates payload server-side and forwards the email request to Resend with `RESEND_API_KEY`.
- Design mode (env missing): the same route responds with an honest design-mode message and does not call Resend.

This keeps the form visually complete in preview while preserving honesty: no fake "message sent" state when integration is not active.

# Required contract points

1. Form submission must target the generated local server route `/api/contact/resend` (never direct provider calls from browser code).
2. Name, email, and message must be validated server-side before any integration call.
3. Missing `RESEND_API_KEY` must activate design mode automatically and return an honest no-op response.
4. Client-side code must never expose provider secrets or build-time secret values.
5. User-facing feedback must distinguish design mode from real integration mode.

# Implementation skeleton

```tsx
"use client";

import { useState, type FormEvent } from "react";

export function ResendContactForm() {
  const [message, setMessage] = useState<string>("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/contact/resend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: String(form.get("name") || ""),
        email: String(form.get("email") || ""),
        phone: String(form.get("phone") || ""),
        message: String(form.get("message") || ""),
      }),
    });
    const payload = await response.json().catch(() => ({}));
    setMessage(typeof payload.message === "string" ? payload.message : "Unexpected response.");
  }

  return (
    <form onSubmit={onSubmit}>
      {/* native fields + honest status message */}
    </form>
  );
}
```

# Forbidden anti-patterns

- Client fetches directly to `https://api.resend.com/*`.
- Any hardcoded token, fake API key, or "example secret" in source.
- Returning success UI in design mode when no provider call happened.
- Hiding missing-env state from operator/user-facing feedback.
- Replacing server validation with client-only checks.
