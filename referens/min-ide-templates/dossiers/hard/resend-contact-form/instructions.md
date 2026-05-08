# When to use

Use this dossier when the brief declares the `contact-form` capability — the site needs a working contact form that delivers messages somewhere (email inbox in this case).

Best fit:

- A "Contact us" page on a marketing site.
- A footer-form on a portfolio.
- A simple support-request form for a small SaaS.

Do not use it for:

- Booking or scheduling forms (different shape — date/time fields, calendar integration). Pair with a calendar dossier instead.
- Lead-capture forms that should sync to a CRM (HubSpot, Pipedrive). Use a CRM-targeted dossier when one exists.
- Heavy multi-step forms (use a wizard pattern + Zod validation instead — this dossier is single-step).

# How to integrate

1. Mount `<ContactForm />` on the contact route (typically `app/contact/page.tsx` or `app/(marketing)/contact/page.tsx`).
2. Wrap it in a section with sensible padding and a heading; the component itself does not own the surrounding layout.
3. Pass an optional `subjectPrefix` prop if you want server-side categorisation (e.g. `subjectPrefix="Hotel inquiry"` so the inbox sees `Hotel inquiry: <user subject>`).
4. The form POSTs to `/api/contact`, which validates the body, calls Resend, and returns `{ ok: true }` on success or `{ ok: false, error }` on failure.

If `RESEND_API_KEY`, `EMAIL_FROM`, or `CONTACT_EMAIL_TO` are missing in `process.env` the dossier is selected but **unconfigured**. The route returns HTTP 503 with `{ ok: false, error: "email-not-configured" }`. The bundled `ContactForm` component handles this gracefully — it surfaces a calm "the contact form is not yet configured, please email us directly" message after the user clicks Send (rather than blocking the form upfront, which would hide the existence of a contact path). If you want a stricter UX, add a server-side feature flag and render an alternative `<a href="mailto:…">` instead of `<ContactForm />` when the env is incomplete.

# UX rules

- Always include `name`, `email`, and `message` fields. `subject` is optional but improves inbox triage.
- Validate email format on the client *and* the server. The server is the source of truth.
- Show a loading spinner or `Submitting…` label while the request is in flight.
- After success, replace the form with a thank-you confirmation that includes the submitted email so the user knows where the reply will go.
- After failure, keep the form contents intact and show a non-destructive error message — never throw away what the user typed.
- Honour `prefers-reduced-motion` for any transitions.

# Avoid

- Do not call the Resend SDK directly from the client — the API key would leak.
- Do not paraphrase `components/api/contact/route.ts`. The Resend SDK init pattern, body validation order, and the "missing env returns 503"-guard must stay byte-exact.
- Do not store form submissions in a database without telling the user (privacy). Email-only delivery is the default contract.
- Do not auto-fill the message with marketing copy. Always start empty.
- Do not hide the contact email entirely when the form is unconfigured — give the user a fallback way to reach you.

# Verification

- Submit the form with valid data — the configured inbox receives an email within a few seconds.
- Submit with an invalid email — the form shows an inline error, no API call is made.
- Submit with `RESEND_API_KEY` empty — the route returns 503 and the UI shows the unconfigured state.
- Server logs show `[POST] /api/contact 200` on success or `[POST] /api/contact 503` when degraded.
- Reload the page — the form returns to its empty state cleanly.
