# 01 — Artefakt-kontrakt: "blueprintet"

Referensdokument. Den **viktigaste arkitekturförändringen** i hela mappen.

> **Princip:** Vi inför **inte** en ny artefakt som heter "Site Blueprint". Vi
> **utökar** de tre artefakter som redan finns. "Blueprint" är ett pedagogiskt
> samlingsnamn för de utökade fälten i Site Brief + Site Plan + Generation Package.
> Handoffen varnar uttryckligen mot att skapa nya canonical-typer ("request envelope",
> "patch plan") när befintliga artefakter redan täcker behovet.

Allt här är **schema-design**. Implementation sker i `kor-1a` (schema) → `kor-1b`
(brief) → `kor-1c` (generation package).

---

## 1. Bron mellan LLM och deterministisk renderer

```text
prompt / Project Input
   |
   v
[ Site Brief v2 ]            <- positioning, contentStrategy   (briefModel)
   |
   v
[ Site Plan v2 ]             <- sectionPlan                    (planningModel)
   |
   v
[ Generation Package v2 ]    <- contentBlocks, visualDirection, qualityRisks
   |                            ("the only payload that enters codegen")
   v
deterministisk renderer  ->  generated-files/
```

Generation Package är dokumenterat som "the only payload that enters codegen-LLM", men
är idag i praktiken bara refs + id:n. Det är **där** blueprintet ska bo så renderern
kan konsumera det.

---

## 2. Site Brief — idag vs v2

**Schema:** `governance/schemas/site-brief.schema.json`
**Producent:** `packages/generation/brief/extract.py` (`briefModel`)

### Finns idag (required + valfria)

`runId`, `language`, `rawPrompt`, `tone`, `targetAudience`, `requestedCapabilities`,
`conversionGoals`, `servicesMentioned`, `sourceModelRole`, `modelUsed`, `briefSource`,
`createdAt` · valfria: `businessTypeGuess`, `companyName`, `pageCount`, `locationHint`,
`contactPhone`, `contactEmail`, `contactAddress`, `contactOpeningHours`, `contentDepth`,
`notesForPlanner`, `scaffoldHint`.

Bra, men för tunt för "sajt med själ".

### Föreslagna v2-tillägg (additiva, valfria)

```jsonc
{
  // ... befintliga fält ...

  "businessFacts": {
    "facts": [],                       // bekräftade fakta (från prompt/wizard/scrape)
    "unknowns": ["telefon", "certifieringar"]  // medvetet okänt -> renderern visar inte
  },

  "positioning": {
    "oneLiner": "Elektriker i Malmö for trygga installationer och snabb hjalp.",
    "differentiator": "lokal, tydlig, trygg - utan krangliga offerter",
    "audienceNeed": "...",
    "localAngle": "...",
    "tone": "trygg, kunnig, rak",
    "avoid": ["overdrivet techig", "pahittade certifieringar", "generiska superlativ"]
  },

  "contentStrategy": {
    "heroAngle": "...",
    "trustStrategy": "arlig trust utan fake claims",
    "offerStrategy": "lyft 3-5 konkreta tjanster",
    "avoidGenericClaims": true
  },

  "conversion": {
    "primaryAction": "request_quote",
    "primaryCta": "Be om offert",
    "secondaryCta": "Se vara tjanster",
    "contactPriority": ["phone_if_real", "form", "email_if_real"],
    "ctaRules": ["Visa inte telefon om telefon saknas", "Anvand inte bokning om booking saknas"]
  }
}
```

**`unknowns` är ärlighetsmotorn.** Den binder LLM-intelligens till de deterministiska
kontakt-/trust-reglerna (`contact_placeholders.py`, B158/B159): ett fält i `unknowns`
får aldrig renderas som påhittad copy.

---

## 3. Site Plan — idag vs v2

**Schema:** `governance/schemas/site-plan.schema.json`
**Producent:** `packages/generation/planning/plan.py` (`produce_site_plan`, `PlanningChoice`)

### Finns idag

`runId`, `scaffoldId`, `variantId`, `starterId`, `routePlan[]` (`id`/`path`/`purpose`),
`selectedDossiers`, `buildSpec` (`qualityTarget`/`verificationPolicy`/`previewRuntime`),
`sourceModelRole`, `modelUsed`, `planSource`, valfria warnings.

> Notera: `sectionTreatments` ligger **inte** på Site Plan idag — det ligger på
> Project Input `directives.sectionTreatments` (ADR 0032) och konsumeras i fas 3.

### Föreslaget v2-tillägg: `sectionPlan` (section-level intent)

```jsonc
{
  // ... befintliga fält ...
  "sectionPlan": {
    "home.hero": {
      "goal": "position fast",
      "copyIntent": "trygg lokal elektriker",
      "visualTreatment": "split-proof",
      "ctaRole": "primary"
    },
    "home.trust-proof": {
      "goal": "build credibility without fake claims",
      "proofSources": ["prompt", "wizard"]
    }
  }
}
```

`sectionPlan`-nycklar ska mappa mot scaffoldens `sections.json` (route-id + section-id).
`PlanningChoice` får ett nytt fält `sectionPlan`; resolvern validerar att varje section
finns i scaffoldens tillåtna lista (samma rail som för dossiers).

---

## 4. Generation Package — idag vs v2 (kärnan)

**Schema:** `governance/schemas/generation-package.schema.json`

### Finns idag (mest refs + id:n)

`runId`, `policyVersions`, `siteBriefRef`, `sitePlanRef`, `scaffoldId`, `variantId`,
`starterId`, `language`, `engineMode`, `createdAt` (+ `projectId` på followup).

Inte tillräckligt för en tung LLM-kedja. Här bor blueprintet.

### Föreslagna v2-tillägg

```jsonc
{
  // ... befintliga fält ...

  "contentBlocks": {
    "home.hero": {
      "headline": "Trygg elektriker i Malmo nar jobbet maste bli ratt",
      "subheadline": "Vi hjalper privatpersoner, foreningar och mindre foretag ...",
      "proofLine": "Tydlig radgivning, sakra losningar och snabb aterkoppling.",
      "primaryCta": "Be om offert"
    },
    "services.service-list": [
      { "title": "Elinstallationer", "summary": "...", "bullets": ["...", "..."] }
    ]
  },

  "visualDirection": {
    "mood": "trygg, modern, lokal service",
    "density": "medium",
    "heroStyle": "split_with_image",
    "colorIntent": "warm_neutral_with_electric_accent",
    "sectionTreatments": { "service-list": "alternating-rows" },
    "imageBriefs": ["Elektriker i modern lagenhet i Malmo, naturligt ljus ..."],
    "layoutSignals": { "useTrustBandNearHero": true, "avoidOverlyPlayfulShapes": true }
  },

  "qualityRisks": [
    "No fake certifications",
    "Do not show phone if missing"
  ]
}
```

`contentBlocks`-nycklar = `<routeId>.<sectionId>` (samma adressering som `sectionPlan`).
`visualDirection.heroStyle`/`sectionTreatments` är **enums** som mappar mot befintliga
variant-tokens och `dispatcher.py`-treatments (se `kor-3b`).

---

## 5. Adresseringskontrakt (en sanning för "var sitter saker")

Allt blueprint-innehåll adresseras med samma nyckel-konvention så router, planner,
renderer och verifier pratar samma språk:

```text
<routeId>.<sectionId>          ex: "home.hero", "services.service-list"
<routeId>.<sectionId>.<field>  ex: "home.hero.headline"  (för patch-planer, se kor-7b)
```

- `routeId` kommer från Site Plan `routePlan[].id` (= scaffoldens `routes.json`).
- `sectionId` kommer från scaffoldens `sections.json`.
- Detta är samma adress i `sectionPlan` (Site Plan), `contentBlocks` +
  `visualDirection.sectionTreatments` (Generation Package) och i Artifact Patch Plans.

---

## 6. Nivåplan (coachens "blueprint före renderer")

Bygg i nivåer så grunden aldrig rivs:

| Nivå | Vad | Kördokument |
|------|-----|-------------|
| 1 | Definiera blueprint-fälten + spara som artefakt per run | `kor-1a` → `kor-1b` → `kor-1c` |
| 2 | Renderer konsumerar `contentBlocks`/`visualDirection` för de fält som märks direkt (hero/services/story/FAQ/CTA) | `kor-2` |
| 3 | Visual Direction → tokens/variants/section-treatments deklarativt | `kor-3a` → `kor-3b` |
| 4 | Quality verifier läser blueprint + render → reparerbara issues | `kor-4a` → `kor-4b` |
| 5 | Repair-pass ändrar blueprint-fält → re-render | `kor-5` |
| 6–7 | OpenClaw router + patch-planer mot dessa fält | `kor-6a/6b`, `kor-7a`–`kor-7d` |

Snabbast effekt: nivå 2 behöver bara använda
`hero.headline/subheadline/primaryCta`, `services[]`, `story`, `faq[]`,
`trustSignals[]`, `visualDirection.heroStyle/density`.

---

## 7. Hårda regler för blueprint-skivorna

- **Additivt och valfritt.** Alla v2-fält är `optional` i schemat med mock-fallback;
  inga befintliga tester får regreddera.
- **Flagga + mock.** När `OPENAI_API_KEY` saknas faller fälten tillbaka till mock (som
  `briefSource`/`planSource` redan gör) — kontraktet ska vara identiskt.
- **Ingen ny canonical-typ.** Registrera nya **fältnamn** vid behov i
  `naming-dictionary.v1.json`, men skapa ingen ny artefaktfil.
- **Ärlighet är schema-nivå.** `businessFacts.unknowns` + `qualityRisks` är inte
  dekoration — renderern och verifiern ska respektera dem (ingen placeholder-kontakt,
  ingen fake-cert).
- **Definition of done (nivå 1):** fyra baseline-prompter (elektriker Malmö, frisör
  Göteborg, naprapat Stockholm, keramik-e-handel) ger fyra **tydligt olika** blueprints;
  inga fake-certifieringar; ingen placeholder-kontakt i copy; blueprint sparas per run.
