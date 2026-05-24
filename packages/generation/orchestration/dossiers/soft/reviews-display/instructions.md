# When to use

Use this dossier when the brief supplies real customer reviews, testimonials or quotes that can be attributed to a named person or verified source (Google, TripAdvisor, Yelp, Trustpilot, own site collected via a form). Triggers include `recensioner`, `omdömen`, `kundröster`, `testimonials`, `vad våra kunder säger`, `omdömen från Google`.

Best fit:

- A `/recensioner` route on restaurants, clinics, salons, contractors.
- A 3-6 review strip on the home page directly above the final CTA (the high-trust position).
- A testimonial sidebar on `/tjanster` or `/portfolio` pages.

Do not use for:

- Fictional or fabricated quotes — the dossier is named "reviews-display" specifically because the data must be real. Fake reviews are an FTC-violation in the US and ARN-grund in Sweden.
- Generic claim strings ("Vi lovar kvalitet") — those go in a value-prop section, not in a reviews component. Use `_render_home_testimonials_section` "Det här lovar vi" pattern instead (per W1-10).
- Internal staff "testimonials" written by the founder — that is About Story copy, not customer reviews.

# How to integrate

A reviews output MUST deliver these five contract points:

1. **Real attribution.** Every review card declares an author name. If the source is anonymous (`"En nöjd gäst"`), the planner must explicitly approve — default behaviour is to drop the review rather than ship "Anonymous" cards. NEVER invent author names.
2. **Source provenance.** Each review declares its source: `google`, `tripadvisor`, `yelp`, `trustpilot`, `facebook` or `own-site`. Render as a small icon or badge near the author name so visitors can verify trust level.
3. **Star rating opt-in.** If the source provides a numeric rating (1-5), render filled/empty stars. If not, omit the stars entirely — never render "no rating" as 0 stars (visually identical to "1-star review").
4. **schema.org JSON-LD.** Emit `Review` schema for every card with author, reviewBody, datePublished (if known) and reviewRating (if known). Wrap the parent business in `AggregateRating` if 3+ reviews with numeric ratings exist. This is what produces rich SERP star snippets — significant CTR lift.
5. **Quote length cap.** Cards show at most 280 characters; longer reviews are truncated with `…` and optionally expand via `<details>` (no JS needed). Wall-of-text reviews kill conversion.

# Implementation skeleton

```tsx
// components/reviews/reviews-display.tsx — Server Component

type ReviewSource = "google" | "tripadvisor" | "yelp" | "trustpilot" | "facebook" | "own-site";

interface ReviewItem {
  author: string;
  source: ReviewSource;
  body: string;
  rating?: 1 | 2 | 3 | 4 | 5;
  datePublished?: string;
}

interface ReviewsDisplayProps {
  reviews: ReadonlyArray<ReviewItem>;
  businessName: string;
  truncateAt?: number;
}

const SOURCE_LABEL: Record<ReviewSource, string> = {
  google: "Google",
  tripadvisor: "TripAdvisor",
  yelp: "Yelp",
  trustpilot: "Trustpilot",
  facebook: "Facebook",
  "own-site": "Egen sajt",
};

export function ReviewsDisplay({
  reviews,
  businessName,
  truncateAt = 280,
}: ReviewsDisplayProps) {
  const numeric = reviews.filter((r) => typeof r.rating === "number");
  const avg =
    numeric.length >= 3
      ? numeric.reduce((acc, r) => acc + (r.rating ?? 0), 0) / numeric.length
      : null;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    name: businessName,
    ...(avg
      ? {
          aggregateRating: {
            "@type": "AggregateRating",
            ratingValue: avg.toFixed(1),
            reviewCount: numeric.length,
          },
        }
      : {}),
    review: reviews.map((r) => ({
      "@type": "Review",
      author: { "@type": "Person", name: r.author },
      reviewBody: r.body,
      ...(r.rating
        ? {
            reviewRating: {
              "@type": "Rating",
              ratingValue: r.rating,
              bestRating: 5,
            },
          }
        : {}),
      ...(r.datePublished ? { datePublished: r.datePublished } : {}),
    })),
  };

  return (
    <section aria-label="Kundrecensioner">
      <ul role="list" className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {reviews.map((r) => {
          const truncated = r.body.length > truncateAt;
          const head = truncated ? r.body.slice(0, truncateAt).trimEnd() + "…" : r.body;
          return (
            <li
              key={`${r.author}-${r.body.slice(0, 24)}`}
              className="rounded-lg border bg-card p-6"
            >
              {r.rating ? (
                <p aria-label={`${r.rating} av 5 stjärnor`} className="mb-3 text-primary">
                  {"★".repeat(r.rating)}
                  <span className="text-muted-foreground">{"★".repeat(5 - r.rating)}</span>
                </p>
              ) : null}
              <blockquote className="text-pretty">
                {truncated ? (
                  <details>
                    <summary className="cursor-pointer list-none">{head}</summary>
                    <span>{r.body.slice(truncateAt)}</span>
                  </details>
                ) : (
                  head
                )}
              </blockquote>
              <p className="mt-4 text-sm text-muted-foreground">
                — {r.author} <span aria-hidden="true">·</span>{" "}
                <span className="uppercase tracking-wide">{SOURCE_LABEL[r.source]}</span>
              </p>
            </li>
          );
        })}
      </ul>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </section>
  );
}
```

Adapt the JSX to the variant: `nordic-fine-dining` may strip the stars and rely on hushed grey quotes, `casual-cafe` may use rounded card backgrounds with photo avatars. Keep the five contract points intact.

# Forbidden anti-patterns

- Generating reviews from a template — if the brief gave 0 real reviews, render the W1-10 "Det här lovar vi" claims section instead.
- Carousel-only reviews that hide 80% of the proof behind interaction (kills SEO, fails screen readers).
- Showing only the source logo without an author name — reads as fake.
- Generating an `AggregateRating` with < 3 reviews — Google may flag as spam.
- Mixing customer reviews with "press quotes" in the same component — those are separate trust signals.
