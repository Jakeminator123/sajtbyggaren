# When to use

Use this dossier as the **default** contact-form implementation when the operator has not provided a server-side email delivery service (Resend, SendGrid, Mailgun) or external form provider (Formspree, Tally, Typeform). Triggers include `kontakta oss`, `contact form`, `skicka meddelande`, `förfrågan`, `offertförfrågan`, `inquiry`, `get in touch`, `kontaktformulär` — and ANY brief that lists "kontaktformulär" as a wanted feature without specifying a delivery backend.

Best fit:

- A `/kontakt` (or `/hitta-hit` for restaurants, `/contact-us`) page where the form is one of several contact paths (phone, email, address, map).
- A short inquiry block on a service page that drives quote requests.
- Any site that does not want to handle env secrets in week 1 but still needs a usable form for visitors.

Do not use for:

- High-volume forms where the operator needs server-side persistence, spam protection or auto-reply (use the planned `resend-contact-form` hard dossier instead).
- Multi-step wizards or forms with conditional logic (out of scope; needs a form-builder dossier).
- Forms that must collect file uploads (mailto cannot carry attachments reliably).

# How this dossier ships

The form does NOT POST to a server. On submit it builds a `mailto:` URL with the visitor's input pre-populated into `subject` and `body`, then triggers `window.location.href = mailtoUrl`. The visitor's default mail client (Apple Mail, Gmail web, Outlook) opens with the message ready to send. The visitor presses Send themselves.

Tradeoffs vs server-side delivery:

| Aspect | mailto-contact-form (this dossier) | resend-contact-form (planned hard dossier) |
|---|---|---|
| Env / secrets required | None | RESEND_API_KEY |
| Works on first build | Yes | Only after secrets configured |
| Spam protection | None (visitor's mail client) | Server-side (Akismet, hCaptcha) |
| Auto-reply / receipts | No | Yes |
| Failure mode | Visitor without configured mail client sees a download dialog | Server timeout or 500 |
| Use case | Small business, low form volume, week-1 ship | High-volume site, post-launch |

# Required contract points

1. **Native form semantics.** A `<form>` element with proper `<label>` per field, `required` attributes for required fields, `type="email"` for email, `inputMode="tel"` for phone. NEVER a `<div>` pretending to be a form.
2. **Visible recipient.** The page MUST display the recipient email address near the form (e.g. "Skickas till: hello@example.se") so the visitor knows where their inquiry goes BEFORE submitting.
3. **Three fields minimum, six maximum.** Name, email, message are minimum. Phone, subject and one operator-defined extra field (e.g. "Antal personer" for restaurant, "Önskad behandling" for clinic) are optional. More fields kill conversion.
4. **Client-side validation only.** `required`, `type`, `pattern` attributes — no JS-driven validation library. The browser's native validation UI is sufficient and accessible.
5. **Graceful no-mailclient fallback.** If `mailto:` fails to open (rare but possible on locked-down kiosks), the form must show a fallback section with the recipient email as a clickable `mailto:` link and the visitor's typed message in a copy-paste-ready `<textarea>` so they can paste it into webmail.
6. **No analytics, no tracking, no third-party scripts.** This dossier ships zero external dependencies.

# Implementation skeleton

```tsx
// components/contact/mailto-contact-form.tsx — Client Component (needs onSubmit handler)
"use client";

import { useState, type FormEvent } from "react";

interface MailtoContactFormProps {
  recipient: string;
  subjectPrefix?: string;
  extraFieldLabel?: string;
  extraFieldName?: string;
}

export function MailtoContactForm({
  recipient,
  subjectPrefix = "Förfrågan från webbplatsen",
  extraFieldLabel,
  extraFieldName,
}: MailtoContactFormProps) {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") || "");
    const email = String(data.get("email") || "");
    const phone = String(data.get("phone") || "");
    const message = String(data.get("message") || "");
    const extra = extraFieldName ? String(data.get(extraFieldName) || "") : "";
    const subject = `${subjectPrefix} — ${name}`;
    const body = [
      `Namn: ${name}`,
      `E-post: ${email}`,
      phone && `Telefon: ${phone}`,
      extraFieldLabel && extra && `${extraFieldLabel}: ${extra}`,
      "",
      message,
    ]
      .filter(Boolean)
      .join("\n");
    const mailto = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.location.href = mailto;
    setSubmitted(true);
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-xl space-y-4">
      <p className="text-sm text-muted-foreground">
        Skickas till: <a href={`mailto:${recipient}`} className="underline">{recipient}</a>
      </p>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Namn</span>
        <input name="name" required className="w-full rounded-md border border-input bg-background px-3 py-2" />
      </label>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">E-post</span>
        <input name="email" type="email" required className="w-full rounded-md border border-input bg-background px-3 py-2" />
      </label>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Telefon (valfritt)</span>
        <input name="phone" type="tel" inputMode="tel" className="w-full rounded-md border border-input bg-background px-3 py-2" />
      </label>
      {extraFieldLabel && extraFieldName ? (
        <label className="block">
          <span className="mb-1 block text-sm font-medium">{extraFieldLabel}</span>
          <input name={extraFieldName} className="w-full rounded-md border border-input bg-background px-3 py-2" />
        </label>
      ) : null}
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Meddelande</span>
        <textarea name="message" required rows={6} className="w-full rounded-md border border-input bg-background px-3 py-2" />
      </label>
      <button
        type="submit"
        className="rounded-md bg-primary px-6 py-3 font-medium text-primary-foreground transition hover:opacity-90"
      >
        Skicka
      </button>
      {submitted ? (
        <p className="text-sm text-muted-foreground" role="status" aria-live="polite">
          Om din mailklient inte öppnades automatiskt — kopiera meddelandet ovan och skicka det till <a className="underline" href={`mailto:${recipient}`}>{recipient}</a>.
        </p>
      ) : null}
    </form>
  );
}
```

The skeleton is a pattern. Adapt labels and field set per scaffold (restaurant adds "Antal personer", clinic adds "Önskad behandling", real-estate adds "Objektsnummer"). Keep the six contract points intact.

# Forbidden anti-patterns

- A `<form action="/api/contact" method="POST">` when no such API route exists in the project — that ships a broken form.
- A `<div>`-based form that uses click handlers instead of native `<form>` submission — kills accessibility and `Enter`-to-submit.
- Hiding the recipient email so the visitor can't tell where their message goes.
- Adding a CAPTCHA, hCaptcha, reCAPTCHA or any third-party script — this dossier is zero-deps by design.
- Importing a UI library form component that drags in extra runtime weight; native `<input>` + Tailwind classes is sufficient.
