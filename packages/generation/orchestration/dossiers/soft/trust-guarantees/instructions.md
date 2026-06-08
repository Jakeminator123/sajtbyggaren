# when to use

Use this dossier when the brief or a follow-up asks for a trust/guarantees
block - the "varför oss", "garantier", "trygghet" or "fördelar" section that
reassures a visitor before they convert. Triggers include `garanti`,
`garantier`, `trygghet`, `förtroende`, `fördelar`, `trust`, `guarantees`.

Best fit:

- A short "varför oss"-list on the home page above the closing call to action.
- A guarantees strip that surfaces real promises (e.g. fixed-price quote,
  warranty length, response time) the operator actually offers.

Do not use for:

- Fabricated certificates, awards or guarantees the business has not stated.
- Customer quotes - those belong in the reviews/testimonials section, not here.

# how to integrate

The deterministic builder already renders this section via the existing
`render_section_trust_proof` helper. The content is grounded, in order, in:

1. `trustSignals` from the project-input when present, else
2. the operator's `uniqueSellingPoints`, else
3. confirmed `businessFacts.facts` from the blueprint (filtered against
   unknowns / quality risks so no ungrounded claim is rendered).

Mounting this dossier marks the guarantees capability as selected so the section
is treated as part of the site; it adds no new component and no new render path.

Contract points the rendered section keeps:

1. one icon bullet per grounded signal - semantic list markup, no client JS.
2. an empty grounding set renders nothing (no empty "varför oss" heading) -
   honesty over filler.
3. claims are the operator's own wording or confirmed facts, never invented
   certifications or numbers.

# forbidden anti-patterns

- Inventing a guarantee, award or certificate the business never claimed.
- Rendering a star rating or customer quote here (that is the reviews section).
- Padding the list with generic "vi är passionerade"-filler.
