# When to use

Use this dossier when the brief implies the operator sells a small set of named packages, tiers or plans with a clear price difference: salon services (basic / signature / VIP), consulting retainers (advisor / strategist / partner), gym memberships (drop-in / monthly / annual), SaaS-like service tiers, photographer packages, web-design packages. Triggers include `priser`, `paket`, `tjänsterna kostar`, `vad ingår`, `medlemskap`, `tier`, `plan`, `prislista` (när listan har 2-5 paket, inte en flat menu — då används menu-display istället).

Best fit:

- A `/priser` route with 2-4 side-by-side pricing cards.
- A pricing strip near the bottom of the home page above the final CTA.
- A pricing comparison block on a `/tjanster` page.

Do not use for:

- Restaurant menus (use `menu-display` — different structure, no tiers).
- Single-price products (use a regular product card, not a pricing table).
- Continuous-quote services where pricing depends on scope ("från X kr" pricing — use a `quote-cta` instead, planned).
- Pricing for >5 packages — that's a price list, not a comparison table; render as `<dl>`.

# How to integrate

A pricing-table output MUST deliver these five contract points:

1. **Tier card structure.** Each tier renders as a self-contained `<article>` with: tier name, headline price + cadence (e.g. "1 990 kr / mån"), one-sentence description, feature checklist, CTA. Tiers are siblings inside a CSS grid that re-flows from 1 column (mobile) → N columns (desktop).
2. **One CTA per tier, never zero.** Every tier ends with a clear next-step button or link. The CTA action depends on what the brief supplies: `tel:`, `mailto:`, external booking URL, anchor to contact form, or a `#kontakt` jump-link. NEVER render a tier without a CTA — that breaks the conversion model.
3. **"Most popular" badge.** Exactly one tier (the operator's recommended tier from the brief) MAY have a "Mest populärt" or "Rekommenderas" badge styled as a small pill. If the brief is silent, no badge — never guess which tier to highlight.
4. **Feature list with binary semantics.** Each feature row is either ✓ (included) or — (not included) or a count (e.g. "3 sessioner / mån"). NEVER conditional language like "tillgängligt vid behov" — that defeats the purpose of a comparison.
5. **Server-rendered, semantic.** No `"use client"`, no toggle state. Annual/monthly toggle would need state and is reserved for the planned `pricing-table-toggle` hard dossier. The static dossier supports a single billing cadence per render.

# Implementation skeleton

```tsx
// components/pricing/pricing-table.tsx — Server Component

interface PricingFeature {
  label: string;
  included: boolean | string;
}

interface PricingTier {
  id: string;
  name: string;
  price: string;
  cadence?: string;
  description: string;
  features: ReadonlyArray<PricingFeature>;
  cta: {
    label: string;
    href: string;
  };
  highlight?: boolean;
}

interface PricingTableProps {
  tiers: ReadonlyArray<PricingTier>;
  highlightLabel?: string;
}

export function PricingTable({
  tiers,
  highlightLabel = "Mest populärt",
}: PricingTableProps) {
  const cols = Math.min(tiers.length, 4);
  return (
    <ul
      role="list"
      className={`grid gap-6 md:grid-cols-2 lg:grid-cols-${cols}`}
    >
      {tiers.map((tier) => (
        <li key={tier.id}>
          <article
            className={`relative h-full rounded-lg border bg-card p-6 ${
              tier.highlight ? "ring-2 ring-primary" : ""
            }`}
          >
            {tier.highlight ? (
              <p className="absolute -top-3 left-6 inline-block rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
                {highlightLabel}
              </p>
            ) : null}
            <h3 className="text-lg font-semibold">{tier.name}</h3>
            <p className="mt-4 text-3xl font-semibold tabular-nums">
              {tier.price}
              {tier.cadence ? (
                <span className="text-sm font-normal text-muted-foreground">
                  {" / "}
                  {tier.cadence}
                </span>
              ) : null}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              {tier.description}
            </p>
            <ul role="list" className="mt-6 space-y-2 text-sm">
              {tier.features.map((f) => (
                <li key={f.label} className="flex items-start gap-2">
                  <span aria-hidden="true">
                    {f.included === true
                      ? "✓"
                      : f.included === false
                        ? "—"
                        : String(f.included)}
                  </span>
                  <span
                    className={
                      f.included === false ? "text-muted-foreground" : ""
                    }
                  >
                    {f.label}
                  </span>
                </li>
              ))}
            </ul>
            <a
              href={tier.cta.href}
              className="mt-6 inline-block w-full rounded-md bg-primary px-4 py-2 text-center font-medium text-primary-foreground"
            >
              {tier.cta.label}
            </a>
          </article>
        </li>
      ))}
    </ul>
  );
}
```

Adapt to the variant tokens: `nordic-fine-dining` may use a borderless flat-paper feel, `pulse-fit` may use the energetic-red primary CTA, `midnight-counsel` may use serif tier-names with metallic gold for the highlight. Keep the five contract points intact.

# Forbidden anti-patterns

- Generic "Kontakta oss" CTA on every tier — defeats the comparison narrative; each CTA should hint at the tier's action ("Boka basbehandling", "Hör av dig om VIP-pass").
- Hidden tier without a price ("Kontakta för pris") in the same table as priced tiers — visitors skip the unpriced tier; treat enterprise/quote-driven tiers as a separate "Custom" section.
- Per-tier "Spara X%" badges that compare to fictional list-prices — fake discounts violate ARN consumer-law guidance in Sweden.
- "Mest populärt" on more than one tier — undermines the signal.
- Toggle for "Månad / År" — that requires client state. Render two separate pricing tables (one per cadence) or wait for the planned `pricing-table-toggle` hard dossier.
