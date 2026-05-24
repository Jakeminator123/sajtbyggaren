# When to use

Use this dossier whenever the brief implies a physical location with public visiting hours: restaurants, cafés, salons, clinics, gyms, retail shops, workshops, museums, libraries. Triggers include `öppettider`, `opening hours`, `besökstider`, `mottagning`, `när har ni öppet`, `lunchtider`, `dropin`.

Best fit:

- A hours block on `/kontakt`, `/hitta-hit` or the home-page contact section.
- A condensed weekly summary in the site footer.
- A staffing-style "Vi har öppet just nu" block (static fallback only — live "open now" status requires the planned `real-time-status` hard dossier).
- A holiday/exception list above the regular schedule for restaurants near major holidays.

Do not use for:

- Pure service-time data ("vi svarar inom 24h") — that is `response-time`, not opening hours.
- Online-only businesses with no physical location — they have no opening hours.
- Booking availability ("lediga tider") — that is `booking` capability with real slot data.

# How to integrate

An opening-hours output MUST deliver these five contract points:

1. **Semantic structure.** Use a `<dl>` (definition list) with `<dt>` for weekday and `<dd>` for hours. Screen readers announce day/time as paired data. NEVER a flat `<table>` or `<ul>` of strings.
2. **Localised weekday names.** Use full Swedish weekday names by default (`Måndag`, `Tisdag`, …). Operator can override with English. NEVER abbreviations (`Mån`, `Tis`) unless the variant explicitly asks for them — abbreviations make screen-readers announce "muhn" and look unprofessional.
3. **Closed-day handling.** Days with no hours render as `Stängt` (Swedish) or `Closed`, never as empty `<dd>` or `—`. A blank `<dd>` reads as a broken hours block.
4. **Split-shift support.** A day with lunch + dinner (e.g. `11:00-14:00, 17:00-22:00`) renders as two `<span>` ranges separated by a thin separator (` · ` or `,`), not as a single string `11-14, 17-22`.
5. **schema.org JSON-LD.** Emit `OpeningHoursSpecification` for every day with hours. Google uses this for the "Hours" panel in the Knowledge Card. Server-side only — no client-side hydration needed.

# Implementation skeleton

```tsx
// components/hours/opening-hours.tsx — Server Component

interface OpeningHoursSpan {
  open: string;
  close: string;
}

interface OpeningHoursDay {
  weekday: "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | "saturday" | "sunday";
  spans: ReadonlyArray<OpeningHoursSpan>;
}

interface OpeningHoursProps {
  hours: ReadonlyArray<OpeningHoursDay>;
  locale?: "sv" | "en";
  closedLabel?: string;
}

const WEEKDAY_LABELS_SV: Record<OpeningHoursDay["weekday"], string> = {
  monday: "Måndag",
  tuesday: "Tisdag",
  wednesday: "Onsdag",
  thursday: "Torsdag",
  friday: "Fredag",
  saturday: "Lördag",
  sunday: "Söndag",
};

const SCHEMA_DAY: Record<OpeningHoursDay["weekday"], string> = {
  monday: "Mo",
  tuesday: "Tu",
  wednesday: "We",
  thursday: "Th",
  friday: "Fr",
  saturday: "Sa",
  sunday: "Su",
};

export function OpeningHours({
  hours,
  locale = "sv",
  closedLabel = "Stängt",
}: OpeningHoursProps) {
  const jsonLd = hours
    .filter((day) => day.spans.length > 0)
    .map((day) => ({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: SCHEMA_DAY[day.weekday],
      opens: day.spans[0].open,
      closes: day.spans[day.spans.length - 1].close,
    }));

  return (
    <section aria-label="Öppettider">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
        {hours.map((day) => (
          <Fragment key={day.weekday}>
            <dt className="font-medium">{WEEKDAY_LABELS_SV[day.weekday]}</dt>
            <dd className="tabular-nums">
              {day.spans.length === 0
                ? closedLabel
                : day.spans
                    .map((s) => `${s.open}–${s.close}`)
                    .join(" · ")}
            </dd>
          </Fragment>
        ))}
      </dl>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </section>
  );
}
```

The skeleton is a pattern, not a template. Adapt the visual shape to the variant: `nordic-fine-dining` may right-align the times, `casual-cafe` may use a horizontal pill row instead of a definition list. Keep the five contract points intact.

# Forbidden anti-patterns

- Free-text "Måndag-Fredag 10-18, Lördag 11-15, Söndag stängt" in a single `<p>` — kills both screen reader and SEO.
- Rendering "Open now" / "Closed now" without server-side timezone awareness — produces wrong status for visitors in other regions.
- Using emoji clocks (🕐🕑🕒) as time markers — pure noise for screen readers.
- Embedding a date-picker JS widget — opening hours are static schedule, not a booking calendar.
- Generating `OpeningHoursSpecification` with fictional times when the brief did not supply them — schema.org lies hurt SEO trust.
