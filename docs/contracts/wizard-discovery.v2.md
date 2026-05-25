# wizard-discovery.v2

Status: draft contract — föreslås av frontend (`christopher-ui`) 2026-05-22.

## Syfte

`v1` (nuvarande) skickar all wizard-data som **fri text** via `composeMasterPrompt`.
`briefModel` tvingas sedan gissa struktur som wizarden redan har explicit.
Resultatet är fuzzy matchningar och dead-data (`vibe.vibeId`, `selectedFunctions`,
`mustHave`, `primaryCta` etc) som backend inte kan använda deterministiskt.

`v2` lägger till ett **`directives`-block** med direkt strukturerad data.
Backend kan använda det utan LLM-extraktion när det finns och faller tillbaka
till v1-flödet när det saknas.

## Ägare

- Frontend (wizard + payload-serialisering): `christopher-ui`-medutvecklare.
- Backend (`briefModel`, `planningModel`, scaffold/variant-val): Jakob.
- Contract-review: båda.

## Bakåtkompatibilitet

`v1`-clients fortsätter fungera oförändrat (`schemaVersion: 1`, ingen
`directives`). Servern måste behandla v1 som idag (LLM-extraktion via
`briefModel` på `rawPrompt` + `composeMasterPrompt`-text).

`v2` introducerar **inga breaking changes** — `directives` är `optional` på
client-sidan, och backend måste tolerera både närvaro och frånvaro av det.

### Roll-out-ordning

1. **Pass 1 (klart i `christopher-ui`):** frontend skickar `schemaVersion: 1`
   och **inkluderar `directives` som additivt fält**. Backend
   `_load_discovery_file` ignorerar okända fält (`payload.get("schemaVersion")`
   är fortfarande `1`). Detta körs i produktion utan backend-ändringar.
2. **Pass 2 (Jakob):** Backend implementerar v2-pathen — läser `directives`,
   hoppar `briefModel` när data finns, bumpar `_load_discovery_file` att
   tillåta `schemaVersion in {1, 2}`.
3. **Pass 3 (frontend):** Bump `schemaVersion: 2` i koordinerad PR. Frontend-
   ändringen är en enrad-fix i `buildDiscoveryPayload`.

## Input (request payload till `/api/prompt`)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schemaVersion` | `1 \| 2` | Ja | `1` används idag (additive directives). `2` aktiveras när backend stödjer pathen — koordinerad PR i Pass 3. |
| `rawPrompt` | `string` | Ja | Operatörens råa pitch. Bevaras för `SiteBrief.raw_prompt` + tone-detection som backup. |
| `contentBranch` | `"services" \| "products" \| "menu" \| "team" \| "projects" \| "general"` | Ja | Computed från `answers.siteType` via discovery-options. |
| `scaffoldHint` | `string` | Ja | Generic runtime-safe hint. Backend gör slutligt scaffold-val. |
| `answers` | `WizardAnswers` | Ja | Hela wizard-staten (befintlig shape, oförändrad). |
| `directives` | `WizardDirectives` | Nej (`v2`) | Strukturerad direktiv-block. Beskrivs nedan. |

## WizardDirectives-shape

```ts
type WizardDirectives = {
  language: "sv" | "en";
  scaffoldHint: string;            // exempel: "local-service-business"
  variantHint?: string;            // exempel: "warm-craft" (från VIBE_OPTIONS)
  layoutHint?: "gradient" | "centered" | "split"; // hero-layout-override (ADR 0027)
  pageCount?: number;              // 1..12, derived från mustHave.length + 1 (start)
  businessType?: string;           // kebab-case slug, från businessFamily.id
  requestedCapabilities?: string[]; // slugs, från selectedFunctions[].capability
  conversionGoals?: string[];      // slugs som "booking", "quote-request", "call"
  tone?: {
    primary?: string;              // första brand.toneTags[]
    secondary?: string[];          // brand.toneTags[1..]
    avoid?: string[];              // brand.wordsToAvoid split:ad på komma
  };
  brand?: {
    primaryColorHex?: string;      // direct från answers.brand.primaryColorHex
    accentColorHex?: string;
    designStyle?: string;
  };
  uniqueSellingPoints?: string[];  // strukturerad lista (max 4)
  media?: {                        // tombstones för borttagna assets (null = clear)
    favicon?: AssetRef | null;
    ogImage?: AssetRef | null;
    backgroundVideo?: AssetRef | null;
  };
  /**
   * Phase 3 (ADR 0031): operator-pin per section för design-treatments.
   * Map<sectionId, treatmentId> där varje sectionId är registrerad i
   * `_SECTION_RENDERERS` och varje treatmentId finns i schema-enum för
   * den sectionen. Backend resolve-ordning: operator-pin (denna map) >
   * variant-default (`_SECTION_TREATMENTS_BY_VARIANT`) > section-default.
   * UI:t filtrerar bort pins för sections som inte hör till aktiv
   * scaffold; tomt = inga overrides.
   */
  sectionTreatments?: Record<string, string>;
  notesForPlanner?: string;        // specialRequests + uniqueSellingPoints concat:ade
};
```

## Field-mapping (wizard → directives)

| Wizard field | Directives field | Mapping-regel |
| --- | --- | --- |
| `rawPrompt` (auto-detect) | `language` | `detect_language(rawPrompt)` mirror, default `sv` |
| `businessFamily` (id) | `scaffoldHint` | `BUSINESS_FAMILIES.find(id).scaffoldHint` |
| `businessFamily` (id) | `businessType` | Samma id — backend slug-mappar internt |
| `vibe.vibeId` | `variantHint` | **Nytt kanal** — deterministisk variant-routning |
| `vibe.layoutHint` | `layoutHint` | Hero-layout-override (ADR 0027). Tom sträng = "auto" hopps över. |
| `vibe.sectionTreatments` | `sectionTreatments` | Phase 3 / ADR 0031. Filtreras per scaffold + trim:as innan emit. |
| `uniqueSellingPoints[]` | `uniqueSellingPoints` | Max 4 — fler skulle göra hero-blocket otydligt. |
| `media.{favicon,ogImage,backgroundVideo}` | `media.*` | Tombstone `null` = explicit borttaget; `stripEmpty` bevarar `null` för dessa nycklar. |
| `mustHave.length + 1` | `pageCount` | Inkluderar startsida som inte ligger i `mustHave` |
| `selectedFunctions[]` | `requestedCapabilities` | Via `FUNCTION_CHOICE.capability`-lookup; tomma hopps över |
| `primaryCta` (free text) | `conversionGoals` | Mapas till slugs via simpel keyword-matchning ("boka" → `"booking"`, "ring" → `"call"`, "offert" → `"quote-request"`) |
| `brand.toneTags[0]` | `tone.primary` | Första tag:en |
| `brand.toneTags[1..]` | `tone.secondary` | Resten |
| `brand.wordsToAvoid` | `tone.avoid` | Split:as på komma → trimmas |
| `brand.primaryColorHex` | `brand.primaryColorHex` | Direct (när `vibe.useCustomColors === true` ELLER non-empty) |
| `brand.accentColorHex` | `brand.accentColorHex` | Samma regel |
| `brand.designStyle` | `brand.designStyle` | Direct |
| `specialRequests` + `uniqueSellingPoints[]` | `notesForPlanner` | Concat:eras med `" — "` |

Tomma fält strippas (samma `stripEmpty`-mekanism som v1).

## Backend-konsumtion (beskrivning, inte implementation)

`scripts/prompt_to_project_input.py` (eller `/api/prompt`-handlern) bör:

1. Läs `schemaVersion`. Om `>= 2` och `directives` finns: använd `directives`-pathen.
2. Bygg `SiteBrief` direkt från `directives` utan att kalla `briefModel`. `rawPrompt`
   placeras i `SiteBrief.raw_prompt`. Backend-källa flaggas
   `briefSource = "directives-v2"` (ny enum-värde).
3. Om `directives.scaffoldHint` finns: använd den **deterministiskt** i
   scaffold-resolutionen (skippa heuristik som idag bygger på `business_type`-gissning).
4. Om `directives.variantHint` finns: mappa till `variantId` via en ny
   governance-policy `governance/policies/vibe-to-variant.v1.json` (kandidat-tabell
   levereras tillsammans med detta contract — se nästa sektion).
5. Om `directives.brand.primaryColorHex` finns: använd den som token-override
   (B140 är redan implementerat — detta är samma path men direkt struktur istället
   för indirekt via `composeMasterPrompt`-text).
6. Om något saknas eller `schemaVersion < 2`: kör nuvarande v1-flöde
   oförändrat.

## Variant-mapping (kandidat-tabell)

`VIBE_OPTIONS` i `apps/viewser/components/discovery-wizard/wizard-constants.ts`
äger den semantiska vibe-listan. För deterministisk variant-routning föreslås
en ny governance-policy:

```json
{
  "version": 1,
  "description": "Mappar wizard vibeId till variantId. Skapad i contract wizard-discovery.v2.",
  "mappings": {
    "minimalist-trust": "variant-nordic-trust",
    "warm-craft": "variant-warm-craft",
    "premium-dark": "variant-premium-dark",
    "modern-tech": "variant-modern-tech",
    "organic-natural": "variant-organic-natural",
    "playful-bold": "variant-playful-bold",
    "elegant-editorial": "variant-elegant-editorial",
    "sport-energy": "variant-sport-energy",
    "calm-spa": "variant-calm-spa",
    "tech-saas": "variant-tech-saas"
  }
}
```

**Note:** target-variantId:n behöver bekräftas mot `data/variants/*`. Backend
kan välja att initialt mappa alla vibes till befintliga variants (1:1 inte
nödvändigt — flera vibes kan dela samma variant medan biblioteket växer).

## Mock success-payload (v2)

```json
{
  "schemaVersion": 2,
  "rawPrompt": "Vi är en målerifirma i Palma med 25 års erfarenhet. Vi vill ha en sida som ser lugn och förtroendeingivande ut. Boka tid via sajten.",
  "contentBranch": "services",
  "scaffoldHint": "local-service-business",
  "answers": {
    "companyName": "Palma Måleri AB",
    "offer": "Måleri och tapetsering på Mallorca",
    "businessFamily": "local-service-business",
    "siteType": ["construction"],
    "vibe": {
      "vibeId": "warm-craft",
      "useCustomColors": true,
      "typographyFeel": "serif-classic",
      "references": ""
    },
    "brand": {
      "toneTags": ["lugn", "lokal", "professionell"],
      "designStyle": "minimalistisk",
      "primaryColorHex": "#16a34a",
      "accentColorHex": "#cdb98a",
      "wordsToAvoid": "startup-svada, billig, snabb"
    },
    "selectedFunctions": ["fn-booking", "fn-contact"],
    "mustHave": ["Tjänster", "Om oss", "Kontakt"],
    "primaryCta": "Boka tid",
    "specialRequests": "Bokning ska vara framträdande på startsidan",
    "uniqueSellingPoints": ["25 års erfarenhet", "Svensktalande personal"]
  },
  "directives": {
    "language": "sv",
    "scaffoldHint": "local-service-business",
    "variantHint": "warm-craft",
    "pageCount": 4,
    "businessType": "local-service-business",
    "requestedCapabilities": ["booking-flow", "contact-form"],
    "conversionGoals": ["booking"],
    "tone": {
      "primary": "lugn",
      "secondary": ["lokal", "professionell"],
      "avoid": ["startup-svada", "billig", "snabb"]
    },
    "brand": {
      "primaryColorHex": "#16a34a",
      "accentColorHex": "#cdb98a",
      "designStyle": "minimalistisk"
    },
    "notesForPlanner": "Bokning ska vara framträdande på startsidan — 25 års erfarenhet, Svensktalande personal"
  }
}
```

## Mock loading

Inte applicerbart — wizard-payload skickas synkront i ett enda HTTP-anrop.
Loading-state hör till `generation-run.v1`-kontraktet.

## Mock error (server-side validation)

Server returnerar HTTP `422 Unprocessable Entity`:

```json
{
  "error": "invalid wizard-discovery payload",
  "schemaVersion": 2,
  "details": [
    {
      "path": "directives.brand.primaryColorHex",
      "message": "Must be a valid #rrggbb hex color string."
    }
  ]
}
```

## Empty state

`directives` får vara `undefined` (inte tom-objekt) när inga directives kunde
härledas. Backend måste tolerera båda fallen som "kör v1-flödet".

## Test-idéer

- **Frontend unit:** `buildDiscoveryPayload v2` producerar `directives.requestedCapabilities`
  med alla `capability`-värden från valda `selectedFunctions[]`, i ordningsbevarande sätt,
  utan duplicates.
- **Frontend unit:** `directives.brand.primaryColorHex` inkluderas när
  `vibe.useCustomColors === true` ELLER när fältet är non-empty.
  Annars hoppas det över så variantens default `--primary` används.
- **Frontend unit:** `directives.pageCount` = `answers.mustHave.length + 1` när
  `mustHave[]` inte inkluderar "Startsida"-likes, annars `mustHave.length` direkt.
- **Frontend unit:** `conversionGoals` mapping är deterministisk: `"Boka tid"` → `["booking"]`,
  `"Ring oss nu"` → `["call"]`, `"Begär offert"` → `["quote-request"]`. Multi-CTA:s splittas.
- **Backend contract:** payload med `schemaVersion: 2` och giltig `directives` skapar
  en `SiteBrief` utan att `briefModel` ropas (mock OpenAI-clienten och verifiera 0 anrop).
- **Backend contract:** payload utan `directives` (`schemaVersion: 1` ELLER `directives: undefined`)
  följer exakt nuvarande v1-flöde — output är byte-för-byte identisk med pre-v2-output.
- **Regression:** `vibe.vibeId === ""` ⇒ `directives.variantHint === undefined` (inte tom sträng).

## Open questions (för Jakob)

1. Ska `briefSource` för `directives`-pathen heta `"directives-v2"` eller `"wizard-directives-v2"`?
   Föreslår första — kortare och konsistent med befintliga enum-värden (`"real"`, `"mock-no-key"`).
2. När `directives.variantHint` är satt men `vibe-to-variant.v1.json` inte har en mapping för
   det specifika ID:t — ska backend (a) faila, (b) logga warning och fall tillbaka till
   heuristik, eller (c) tyst ignorera? Föreslår (b) — `qualityResult` får en `findings`-post.
3. När både `directives.tone.primary` och `directives.brand.primaryColorHex` finns,
   ska `directives.brand.primaryColorHex` övertrumfa tone-keyword-mappingen (B139)?
   Föreslår ja — explicit hex är alltid en operator-override.

## Status

Draft. Awaiting backend review (Jakob). Frontend börjar implementera
`buildDiscoveryPayload v2` mot detta kontrakt med UI-preview i wizardens sista
steg så operatören ser exakt vad backend tar emot.
