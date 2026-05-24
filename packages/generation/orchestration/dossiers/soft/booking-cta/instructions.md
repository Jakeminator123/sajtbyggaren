# When to use

Use this dossier when the visitor's primary conversion is to **book a slot** — a table reservation at a restaurant, an appointment at a clinic, a chair at a hair salon, a personal-training session, a guided tour. Triggers include `boka`, `boka bord`, `reservation`, `appointment`, `tidsbokning`, `boka tid`, `tabellreservation`, `book a table`, `book now`, `Caspeco`, `Bokadirekt`, `Resmio`, `BookEden`, `Calendly`.

Best fit:

- A `/bokning` (restaurant) or `/boka-tid` (clinic) or `/boka` (salon) page that is the single dedicated conversion route.
- A repeated home-page CTA strip that always drives to the same booking destination.
- A sticky mobile bar that anchors a "Boka bord"-style action even when scrolling.

Do not use for:

- Generic newsletter signup or contact form (those are `newsletter-subscribe` and `contact-form`).
- Self-serve ecommerce checkout (that is `checkout`).
- Calendar availability querying with real-time slot retrieval — that requires a *hard* dossier (Caspeco-api, Bokadirekt-api) which is planned, not built.

# How to integrate

A booking CTA MUST deliver these five contract points:

1. **Primary action surface.** A clearly-labelled button or link is the largest interactive element on the page above the fold. Label uses concrete domain language: "Boka bord", "Boka tid", "Boka behandling" — never generic "Boka nu" without object.
2. **Destination clarity.** The CTA's `href` is exactly one of: `tel:+46...` (phone), `https://...` (external booking provider URL the operator supplied), or `mailto:...` (last-resort fallback only). The destination is visible to the user before they click: phone number printed below the button, or "Öppnas hos {provider}" label for external URLs. Never a fake JS `onClick` that does nothing in SSR.
3. **Hours adjacency.** Opening hours (or appointment availability summary like "Mån-Fre 09-17") MUST render on the same page within 1-2 sections of the CTA. A booking CTA without visible hours is broken UX — visitors abandon when they can't tell if anyone will pick up.
4. **Large-party / out-of-scope fallback.** Below the primary CTA, render a small notice: "För grupper >8 personer, ring oss direkt" (restaurant), "För akuta ärenden, ring {phone}" (clinic), or equivalent per scaffold. This prevents the "I can't fit my use case" abandonment.
5. **Server-rendered.** No `"use client"`, no state, no fetch. The destination URL is a prop passed in from the server reading `project-input.json` (or scaffold-supplied content). Keep the markup SSG-friendly for SEO.

# Implementation skeleton

```tsx
// components/booking/booking-cta.tsx — Server Component

type BookingDestination =
  | { kind: "phone"; phone: string; displayPhone: string }
  | { kind: "external"; url: string; providerLabel: string }
  | { kind: "mailto"; email: string };

interface BookingHours {
  summary: string;
  weeklyBreakdown?: ReadonlyArray<{ days: string; hours: string }>;
}

interface BookingCtaProps {
  primaryAction: string;
  destination: BookingDestination;
  hours: BookingHours;
  largePartyNote?: string;
}

export function BookingCta({ primaryAction, destination, hours, largePartyNote }: BookingCtaProps) {
  const href =
    destination.kind === "phone"
      ? `tel:${destination.phone}`
      : destination.kind === "external"
        ? destination.url
        : `mailto:${destination.email}`;
  const subline =
    destination.kind === "phone"
      ? destination.displayPhone
      : destination.kind === "external"
        ? `Öppnas hos ${destination.providerLabel}`
        : destination.email;
  return (
    <section aria-label="Boka" className="py-16 text-center">
      <a
        href={href}
        className="inline-flex items-center justify-center rounded-md bg-primary px-8 py-4 text-lg font-medium text-primary-foreground transition hover:opacity-90"
      >
        {primaryAction}
      </a>
      <p className="mt-3 text-sm text-muted-foreground">{subline}</p>
      <p className="mt-8 text-sm font-medium">{hours.summary}</p>
      {hours.weeklyBreakdown ? (
        <ul className="mt-2 text-sm text-muted-foreground">
          {hours.weeklyBreakdown.map((row) => (
            <li key={row.days}>
              <span className="mr-2">{row.days}</span>
              <span className="tabular-nums">{row.hours}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {largePartyNote ? (
        <p className="mt-6 text-xs text-muted-foreground">{largePartyNote}</p>
      ) : null}
    </section>
  );
}
```

The skeleton is a pattern. Adapt button size, label wording and hours layout per scaffold and variant. Keep the five contract points intact.

# Forbidden anti-patterns

- A `<button>` with `onClick` doing nothing in SSR — must be `<a href>` so it works without JS.
- A booking page with no visible opening hours.
- Generic CTA copy ("Boka nu") without a domain object.
- Embedding a third-party `<iframe>` from an unknown booking provider without operator-supplied URL — that turns into a build crash or empty box.
- Adding `useState`, fetch or local state — bookings happen on the provider's site, never inside this component.
