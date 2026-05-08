# When to use

Use this dossier when the brief declares the `faq-section` capability — the site needs a list of frequently asked questions with collapsible answers.

Best fit:

- A pre-purchase objection-handling section near the bottom of a marketing page (5–10 questions).
- A help section on a SaaS dashboard.
- A support sub-page on a documentation site.

Do not use it for:

- Long-form documentation (use a search-first docs layout instead).
- Conversational support flows (use a contact form or chat dossier).
- More than ~20 questions in one block (split into categories or move to a dedicated `/faq` route with anchors).

# How to integrate

Import the component and pass an `items` array. Each item has a `question` and an `answer`. The answer can be a string or any React node, so you can include links, lists, or short paragraphs.

```tsx
import { FaqAccordion } from "@/components/faq-accordion";

export default function FaqSection() {
  return (
    <FaqAccordion
      title="Frequently asked questions"
      items={[
        {
          question: "How long does delivery take?",
          answer: "Standard delivery is 2-3 business days within the EU.",
        },
        {
          question: "Can I cancel my subscription anytime?",
          answer: (
            <p>
              Yes — cancel from your account settings. You keep access until the end of the
              billing period.
            </p>
          ),
        },
      ]}
    />
  );
}
```

The component uses `<details>`/`<summary>` so it works without JavaScript. No external icon library is needed — the chevron is a CSS-only triangle that flips when the item opens.

# UX rules

- Group related questions; do not mix billing, technical, and policy questions in one list without separators.
- Order from most-likely to least-likely question. Put hard objections (price, cancellation, refund) first.
- Answers should be 1-3 short sentences. Link out to detailed docs for the rest.
- Provide a fallback CTA below the list ("Still have questions? Contact us") for cases the FAQ does not cover.
- Allow only one item to be open at a time when the section is short (≤5 questions); allow multiple when it is long. The component supports both via the `singleOpen` prop.

# Avoid

- Do not include questions the page already answers prominently elsewhere — it dilutes the trust signal.
- Do not invent stats or guarantees in answers. Pull copy from the brief or leave a TODO comment for the operator to fill in.
- Do not hide critical information (return policy, GDPR, pricing) only inside an accordion. Surface it where it must legally be visible.
- Do not animate the open/close so it slows down — `prefers-reduced-motion` users should see an instant toggle.

# Verification

- Click each question — the answer expands inline.
- Open one, then another, with `singleOpen={false}` — both stay open. With `singleOpen={true}` — the first closes when the second opens.
- Disable JavaScript in the browser — the accordion still works (because of native `<details>`).
- Tab through the questions — focus order matches DOM order, focus ring is visible.
- Screen reader announces "Question, expanded/collapsed" when toggling.
