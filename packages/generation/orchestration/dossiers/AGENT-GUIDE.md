# Dossier-kit: agentguide (läs detta INNAN du författar eller konsumerar en dossier)

Den här guiden finns för att en agent som ska hantera en "specialförmåga"
(t.ex. ett kontaktformulär, en prislista, ett 5-i-rad-spel som soft dossier,
eller Stripe-betalning som hard dossier) ska få så mycket förpackad hjälp att
implementationen blir *plocka in + anpassa*, inte *uppfinn från noll*.

**80%-principen:** en dossier-mapp ska bära ~80 % av implementationen som
användaren förväntas vilja ha — färdiga kontraktspunkter, ett kodskelett som
följer husets mönster, anti-mönster att undvika och (när trohetsgraden kräver det)
verbatim komponentfiler. Agentens jobb är de sista 20 %: anpassa fältnamn,
copy och scaffold-specifika detaljer.

## Var saker bor (låst av governance)

| Yta | Roll |
|---|---|
| `packages/generation/orchestration/dossiers/<class>/<dossierId>/` | Själva dossiern (denna mapp är ägar-path) |
| `governance/schemas/dossier.schema.json` | Manifest-schemat — varje `manifest.json` MÅSTE validera |
| `governance/policies/dossier-contract.v1.json` | Klasser, obligatoriska filer, aktiveringsregler |
| `governance/policies/capability-map.v1.json` | capability-slug → dossiers-mappningen (tom lista = gap, inte feature) |
| `data/dossier-candidates/` | Kandidat-utflöde från generator/intake (aldrig direkt till ägar-pathen) |

## Formatet per dossier (det här ÄR kitet)

```text
<class>/<dossierId>/
  manifest.json      OBLIGATORISK - maskinläsbar deklaration (schema-validerad)
  instructions.md    OBLIGATORISK - 80%-kitet i text (struktur nedan)
  components/        VALFRI - verbatim TSX när trohetsgraden kräver exakt kod
  code-contract.json / env-contract.json / integration-contract.json /
  examples.md / evals.json   VALFRIA - hard-extras (planerade, ännu oanvända)
```

### manifest.json — fält och betydelse

| Fält | Betydelse för konsumerande agent |
|---|---|
| `id` | dossierId; mappnamnet måste matcha |
| `enabled` | av/på utan att radera (Underhåll-vyn togglar) |
| `label` | operatörsläsbar etikett |
| `capability` | EXAKT en capability-slug ur capability-map (t.ex. `contact-form`, `payments`) |
| `class` | `soft` (ingen env/secrets/backend) eller `hard` (kräver env/extern API; får ha mockMode) |
| `codeFidelity` | `rewritable` = skelettet är ett mönster som får anpassas; högre trohetsgrad = följ koden närmare |
| `complexity` | grov implementationskostnad (low/medium/high) |
| `defaultForCapability` | true = väljs när capabilityn efterfrågas utan specifik dossier |
| `summary` | en ärlig mening om vad den gör OCH inte gör |
| `envVars` | tom för soft; hard listar exakta env-namn (aldrig värden!) |
| `dependencies` | npm-paket utöver starterns bas (helst tom — zero-deps är default) |
| `files` | verbatim-filer i `components/` (tom = instructions-only) |
| `exposes` | komponentnamn som dossiern erbjuder (t.ex. `MailtoContactForm`) |
| `lastVerified` | YYYY-MM-DD; bumpa när du verifierat mot motorn |

### instructions.md — de fem obligatoriska sektionerna

Alla 13 befintliga dossiers följer samma de-facto-struktur. Författa ALLTID i
denna ordning (engelska rubriker, det är konventionen i befintliga filer):

1. "When to use" — triggers (svenska + engelska fraser), best fit,
   "Do not use for" med pekare till rätt alternativ.
2. "How this dossier ships" — den tekniska leveransmodellen, inklusive
   tradeoff-tabell mot alternativa dossiers när relevant.
3. "Required contract points" — numrerade, testbara krav (semantik, a11y,
   synlighet, fallbacks). Detta är dossierns kvalitetskontrakt.
4. "Implementation skeleton" — körbar TSX/kod som följer husets mönster
   (native element, Tailwind-klasser, inga extra libs). Skelettet är ett
   mönster vid `codeFidelity: rewritable` — anpassa fält/copy per scaffold,
   men bryt aldrig kontraktspunkterna.
5. "Forbidden anti-patterns" — konkreta saker som INTE får skeppas
   (t.ex. `<form action="/api/...">` mot en route som inte finns).

## Soft vs hard — reglerna som styr dig

| | soft | hard |
|---|---|---|
| Env/secrets/backend | förbjudet | krävs (deklareras i `envVars`) |
| Aktivering | semantisk (brief räcker) | explicit eller stark semantisk signal — användaren måste ha bett om det |
| Designläge | n/a | får ha mockMode-konfiguration |
| Exempel | faq-accordion, pricing-table, interactive-game-loop | stripe-checkout, resend-contact-form, supabase-auth |

**Ärlighetsläge för hard (viktigt):** ingen hard dossier är implementerad än
och hard-monteringsflödet (server-route i genererad sajt, env-injektion i
hostat bygge, mockMode-rendering) är INTE byggt. Den första hard-dossiern
etablerar det flödet — det är ett infraprojekt, inte bara en manifest-fil.
Lova aldrig i copy/UI att en hard-förmåga fungerar innan env finns.

## Konsumtionsvägen (hur dossiern når användarsajten)

```text
capability-map (slug -> dossiers) -> Site Plan selectedDossiers
  -> codegen mount (source="dossier-mount" i CodegenResult)
  -> ev. synlig render via section_add-vägen (se skills/section-add/SKILL.md)
```

- Montering är inte detsamma som synlighet: flera sektionstyper är ärligt
  *mount-only* (`applied=true` men `appliedVisibleEffect=false`) tills en
  renderare ytar dem. Hitta aldrig på en synlig effekt.
- En okänd/ostödd typ är en ärlig no-op med anledning — aldrig en påhittad
  sektion.
- Dossiers injiceras aldrig automatiskt i alla scaffolds; valet ligger i
  per-sajt `Project Input`/plan.

## Författa en NY dossier — arbetsgång

1. **Kolla gapet:** finns capability-slugen i capability-map? Tom
   `dossiers`-lista = dokumenterat gap som din dossier kan stänga.
2. **Utgå från en granne:** kopiera strukturen från närmast liknande
   befintlig dossier (t.ex. `mailto-contact-form` för formulär).
3. **Kandidat-väg för externt källmaterial:** använd
   `scripts/dossier_candidate_intake.py` (read-only analys av lokal källa)
   och `scripts/generate_dossier_candidate.py` (dossierModel) — utflödet
   landar i `data/dossier-candidates/`, ALDRIG direkt i ägar-pathen.
   Operatören granskar innan något flyttas in hit.
4. **Skriv manifest + instructions** enligt formatet ovan. Validera:
   `python scripts/governance_validate.py`.
5. **Uppdatera README:** lägg din dossierId i Status-listan i
   `dossiers/README.md` — `tests/test_docs_freshness.py` rödflaggar annars.
6. **Registrera i capability-map** (policy-bump) så selektorn hittar den.
7. **Guards innan PR:** ruff + governance_validate + rules_sync --check +
   check_term_coverage --strict + pytest (minst tooling/governance-markers).

## Fallgropar (kostar timmar om du missar dem)

- **`--dossier`-flaggan i build_site.py är INTE en dossier** — den pekar på
  ett `Project Input`. Två olika saker delar ordet (se begreppskartan).
- **Förbjudna alias:** klassen `hybrid` är borttagen (ADR 0012); package/
  plugin/feature som synonym till dossier är förbjudet i naming-dictionary.
- **Inga hemligheter i dossier-filer** — inte ens exempel-API-nycklar.
- **Zero-deps är default:** varje rad i `dependencies` kräver policy +
  operatörsgodkännande.
- **Skelett-koden måste matcha starterns mönster** (native element + Tailwind,
  server components där möjligt, `"use client"` bara när handlers krävs).
