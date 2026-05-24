# When to use

Use this dossier when the brief implies recurring customer questions that deserve a dedicated answer surface: "Hur fungerar bokningen?", "Kan jag avboka?", "Vad ingår i priset?", "Har ni parkering?", "Behöver jag boka i förväg?". Triggers include `FAQ`, `vanliga frågor`, `frågor och svar`, `Q&A`, `customer questions`, `hur fungerar`, `kan man`.

Best fit:

- A `/faq` route with 8-15 question/answer pairs.
- An FAQ section on `/tjanster`, `/boka` or `/priser` covering tier-specific concerns.
- A pre-booking FAQ on the contact page covering "när får jag svar?", "vad kostar konsultationen?".
- An after-the-fact "Vanligaste frågor" strip directly above the contact form.

Do not use for:

- Marketing claims dressed as questions ("Varför är vi bäst? — För att vi är passionerade.") — those are testimonial-grade self-praise, not real customer questions. Use a value-prop section.
- A blog post in disguise — if any answer is >300 characters, it belongs in a `/insikter`-style article.
- Legal disclaimers — those belong in `/villkor`, not in an FAQ.

# How to integrate

A faq-accordion output MUST deliver these five contract points:

1. **Native `<details>`/`<summary>` semantics.** Use the browser-native disclosure widget — zero JS, full keyboard accessibility out of the box, works without hydration, indexable by Google. NEVER recreate this with `useState` + `<button>` + manual ARIA; you reinvent broken behaviour.
2. **One question, one answer, no chatter.** Each Q is a `<summary>` (the visible toggle label) and each A is the `<details>` body. Answers are 1-3 short paragraphs (under 300 chars). Longer = needs its own article.
3. **schema.org FAQPage JSON-LD.** Emit `FAQPage` with `mainEntity` array of `Question`/`Answer` objects. Google renders these as expanding-FAQ-snippets in SERPs — significant CTR lift for service-business queries.
4. **Optional categorical grouping.** If the brief supplies 12+ FAQ items, group them under `<h2>` category headings ("Bokning & avbokning", "Pris & betalning", "Tillgänglighet"). Each group is a `<section>` with its own `<details>` items. With <8 items, skip groupings entirely.
5. **No "open all" button.** That defeats the point of progressive disclosure; visitors scan questions, not answers. If they want all answers visible they `Ctrl+F`.

# Implementation skeleton

```tsx
// components/faq/faq-accordion.tsx — Server Component, no "use client"

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqGroup {
  heading?: string;
  items: ReadonlyArray<FaqItem>;
}

interface FaqAccordionProps {
  groups: ReadonlyArray<FaqGroup>;
}

export function FaqAccordion({ groups }: FaqAccordionProps) {
  const allItems = groups.flatMap((g) => g.items);
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: allItems.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  return (
    <section aria-label="Vanliga frågor">
      {groups.map((group, gi) => (
        <div key={group.heading ?? `g-${gi}`} className="mb-10">
          {group.heading ? (
            <h2 className="mb-4 text-xl font-semibold">{group.heading}</h2>
          ) : null}
          <ul role="list" className="divide-y divide-border">
            {group.items.map((item) => (
              <li key={item.question} className="py-2">
                <details className="group">
                  <summary className="flex cursor-pointer items-center justify-between gap-4 py-3 font-medium [&::-webkit-details-marker]:hidden">
                    <span>{item.question}</span>
                    <span
                      aria-hidden="true"
                      className="text-muted-foreground transition group-open:rotate-180"
                    >
                      ▾
                    </span>
                  </summary>
                  <div className="pb-4 pr-8 text-sm text-muted-foreground">
                    {item.answer}
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </section>
  );
}
```

Adapt to the variant tokens: `nordic-fine-dining` may use a thin divider and serif question face, `pulse-fit` may use a saturated chevron color, `family-warmth` may use larger pad and softer chevron. Keep the five contract points intact.

# Forbidden anti-patterns

- Building a custom accordion with `useState` + manually-managed `aria-expanded` — the native `<details>` already does this correctly. Hand-rolled versions almost always break Esc-to-close or focus-trap behaviour.
- 30+ FAQ items on one page — split into category pages or move to a knowledge base.
- Same Q rephrased in 4 different ways — bad SEO (Google deduplicates) and visually noisy. Pick the most natural phrasing.
- Q without a question mark — reads as a heading, breaks visitor expectation.
- Emoji chevrons (▼ vs the rotated ▾ shown) without a `transition` — feels broken on slow devices.
