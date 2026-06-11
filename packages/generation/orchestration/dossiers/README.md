# `packages/generation/orchestration/dossiers/`

Den här mappen är ägar-pathen för alla **Dossier**-definitioner enligt
[`repo-boundaries.v1.json`](../../../../governance/policies/repo-boundaries.v1.json)
och [`naming-dictionary.v1.json`](../../../../governance/policies/naming-dictionary.v1.json).

> **Agent som ska författa eller konsumera en dossier?** Läs
> [`AGENT-GUIDE.md`](AGENT-GUIDE.md) först — den låser formatet
> (manifest-fälten, instructions-strukturens fem sektioner, soft/hard-reglerna,
> konsumtionsvägen och arbetsgången för nya dossiers) enligt 80%-principen:
> dossiern bär merparten av implementationen, agenten anpassar resten.

## Dossier i en mening

En Dossier är en återanvändbar capability/legokloss som kan kopplas på vilken
sajt som helst om den är kompatibel. Default-kompatibel med alla Scaffolds.
En Dossier är inte ett konkret kundprojekt - det är `Project Input`, som bor
under `examples/<siteId>.project-input.json`.

## Klasser (ADR 0012)

Bara två klasser:

- **`soft`** - återanvändbar frontend/content capability utan secrets eller
  externa API:er. Exempel: `pacman-game`, `mouse-reactive-background`,
  `pricing-calculator`, `before-after-slider`.
- **`hard`** - kräver env, secrets, backend, auth, databas, betalning eller
  extern API. Får ha `mockMode`-konfiguration för designläge. Exempel:
  `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart`.

Tidigare versioner hade också `hybrid` som klass och en separat typ-axel.
Båda är borttagna - se ADR 0012 för detaljer och de termer som nu ligger i
`naming-dictionary.v1.json:globallyForbidden`.

## Mappstruktur

```text
packages/generation/orchestration/dossiers/
  soft/
    <dossierId>/
      manifest.json
      instructions.md
      components/                    (optional, soft-only)
        <componentName>.tsx
  hard/
    <dossierId>/
      manifest.json
      instructions.md
      components/                    (optional, soft-only ideal)
      code-contract.json             (optional, planerad Sprint 3+)
      env-contract.json              (optional, planerad Sprint 3+)
      integration-contract.json      (optional, planerad Sprint 3+)
      examples.md                    (optional)
      evals.json                     (optional)
  README.md  (this file)
```

`manifest.json` validerar mot
[`governance/schemas/dossier.schema.json`](../../../../governance/schemas/dossier.schema.json)
och deklarerar `class` (`soft` eller `hard`), `capability`, `codeFidelity`,
`complexity`, `defaultForCapability`, `summary`, `envVars`, `dependencies`,
`files`, `exposes` och `lastVerified`. Obligatoriska filer per
[`dossier-contract.v1.json:dossierDirectoryLayout.requiredFilesAllClasses`](../../../../governance/policies/dossier-contract.v1.json)
är idag bara `manifest.json` och `instructions.md`. Övriga filer i listan
ovan är optional och fylls när hard Dossiers importeras i Sprint 3+.

## Status

Tretton (13) soft Dossiers är implementerade idag (alla instructions-only,
inga verbatim TSX-filer):

**Pre-Week-1 (basbygglock):**

- [`soft/interactive-game-loop/`](soft/interactive-game-loop/) — capability
  `interactive-game`, `defaultForCapability=true`. Definierar state/loop/
  controls/collision/score/restart-kontraktet för spelbara mini-spel.

**Week 1 batch 1 (restaurant-grundpaket, 2026-05-24):**

- [`soft/menu-display/`](soft/menu-display/) — capability `menu`,
  `defaultForCapability=true`. Course-grouping + per-item price + dietary
  markers för restaurang/café-menyer.
- [`soft/booking-cta/`](soft/booking-cta/) — capability `booking`,
  `defaultForCapability=true`. Phone/external/mailto-CTA med adjacent
  hours, för restaurang/klinik/frisör-bokning.
- [`soft/mailto-contact-form/`](soft/mailto-contact-form/) — capability
  `contact-form`, `defaultForCapability=true`. Mailto-baserat kontaktformulär
  (zero env, zero backend) som default tills den planerade hard
  `resend-contact-form` importeras från MIN_IDE.

**Week 1 batch 2 (universella brick-and-mortar-byggstenar, 2026-05-24):**

- [`soft/image-gallery/`](soft/image-gallery/) — capability `gallery`,
  `defaultForCapability=true`. Responsiv CSS-grid med semantisk alt, lazy
  loading och aspect-ratio-reservation. Återanvänds av restaurant +
  framtida portfolio/clinic/real-estate-scaffolds.
- [`soft/opening-hours/`](soft/opening-hours/) — capability `hours`,
  `defaultForCapability=true`. Semantisk definition-list med closed-day,
  split-shift och schema.org OpeningHoursSpecification JSON-LD.
- [`soft/reviews-display/`](soft/reviews-display/) — capability `reviews`,
  `defaultForCapability=true`. Customer review-cards med source-provenance,
  optional star-rating och schema.org Review JSON-LD som ger rich
  SERP-snippets.
- [`soft/map-embed/`](soft/map-embed/) — capability `location`,
  `defaultForCapability=true`. OpenStreetMap-iframe (no API-key, GDPR-vänlig)
  med semantiskt address-block och native-app directions-deeplinks.

**Week 1 batch 3 (universella conversion-byggstenar, 2026-05-24):**

- [`soft/pricing-table/`](soft/pricing-table/) — capability `pricing`,
  `defaultForCapability=true`. 2-4 tier-cards med feature-checklist,
  optional 'mest populärt'-badge och en CTA per tier. Server-rendered,
  ingen klient-toggle (årlig/månadsbil reserverad för planerad hard
  pricing-table-toggle-dossier).
- [`soft/faq-accordion/`](soft/faq-accordion/) — capability `faq-section`,
  `defaultForCapability=true`. Native HTML `<details>`/`<summary>` (zero JS,
  full keyboard a11y, Google-indexerbart) plus schema.org FAQPage JSON-LD
  för rich SERP-snippets. Stänger den tidigare faq-section-gap.
- [`soft/video-hero/`](soft/video-hero/) — capability `hero-video`,
  `defaultForCapability=true`. Native `<video>` med poster-fallback,
  preload=metadata, prefers-reduced-motion-hantering och text-overlay
  med kontrast-gradient. Ingen YouTube/Vimeo-embed.

**section_builder-slice (section_add follow-up-roll, 2026-06-08):**

- [`soft/team-roster/`](soft/team-roster/) — capability `team-section`,
  `defaultForCapability=true`. Responsivt grid av monogram-kort (namn + roll)
  som återanvänder den befintliga `render_section_team`-renderaren. Data-drivet
  på `company.team`; tom lista renderar ingenting (ingen påhittad personal).
  Monteras av section_add-följdprompten ("lägg till en team-sektion").
- [`soft/trust-guarantees/`](soft/trust-guarantees/) — capability `guarantees`,
  `defaultForCapability=true`. Trust/garanti-block ('Varför oss' som ikon-
  punktlista) som återanvänder den befintliga `render_section_trust_proof`-
  renderaren. Grundat i `trustSignals` / `uniqueSellingPoints` / bekräftade
  `businessFacts` (aldrig påhittade certifikat/garantier). Monteras av
  section_add-följdprompten ("lägg till en sektion om garantier").

Övriga capability-slugs i [`governance/policies/capability-map.v1.json`](../../../../governance/policies/capability-map.v1.json)
har fortfarande tomma `dossiers`-listor och är dokumenterade gap
(`empty list = gap, not feature`): `newsletter-subscribe`, `payments`,
`auth`, `analytics`, `ai-chat`, `error-tracking`, `carousel`, `marquee`,
`command-search`. De väntar på MIN_IDE-import i kommande sprintar.
Ingen hard Dossier (stripe-checkout, supabase-auth, clerk-auth,
shopify-cart, resend-contact-form) är implementerad än.

Builder MVP läser primärt ett `Project Input` under
`examples/<siteId>.project-input.json` (t.ex. `painter-palma`) och patchar
startern (`site_plan["starterId"]`) med dess content. Det är inte en formell
Dossier-realisering — den första riktiga Dossier-mountingen ligger i Sprint 3
tillsammans med `codegenModel`.

## Kompatibilitet är default-allow

En Dossier är kompatibel med alla Scaffolds tills den explicit deklarerar
motsatsen via en `incompatibleScaffolds`-lista i `dossier.json`. Detta är
omvänt mot tidigare modell där Scaffolds opt-in:ade Dossiers via
`compatible-dossiers.json` (den blir framöver bara en hint, inte ett filter).

## Inte autoinjektion

En Dossier får användas av många Scaffolds, men injiceras aldrig automatiskt
i alla. Operator (eller Selector i framtida runda) avgör vilka Dossiers som
aktiveras per Project Input.
