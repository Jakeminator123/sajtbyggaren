# ADR 0012: Vocabulary compression

## Status

Accepted (2026-05-08).

## Kontext

Operator-facing vokabulären växte i v6-v9 med flera Dossier-typer
(`Site Dossier`, `Feature Dossier`, `Integration Dossier`, `Data Dossier`)
ovanpå Dossier-klasserna (`soft`, `hybrid`, `hard`). Det skapade samma
namnskugga vi rensade ut i sajtmaskin: ett konkret kundprojekt (t.ex.
`painter-palma`) kallades både "Site Dossier" och "Project Input" i olika
docs och UI-pickers. Operatören ska inte behöva lära sig fyra parallella
Dossier-axlar för att förstå vad ett projekt är.

## Beslut

### Lås operator-flödet i exakt åtta steg

```
Init Prompt
  ↓
Project Input (Deep Brief)
  ↓
Starter selection
  ↓
Scaffold selection
  ↓
Variant selection
  ↓
Dossier selection
  ↓
Generation Package
  ↓
Build
```

Det här är den enda pedagogiska modellen. Allt annat operator-facing språk
mappar mot de här åtta termerna.

### Definitioner

| Term | Definition |
|---|---|
| `Init Prompt` | Den första promptens råtext från operatören. |
| `Project Input` | Strukturerad tolkning av init-promptens kund-/site-data. Tidigare kallat "Site Dossier" eller "site-dossier" i filnamn. Filer: `examples/<siteId>.project-input.json`. Alias i docs: `Deep Brief`. |
| `Starter` | Nedladdad/körbar Next.js-bas under `data/starters/<starterId>/`. Operatören får säga "repo" i UI; kod och policies använder `Starter`. Aldrig samma sak som Sajtbyggarens egen repo. |
| `Scaffold` | Sajtens route- och sektionsgrammatik. Inte en sida. Definierar vilka `Route`/`Page` som finns och vilka sektioner som tillåts. |
| `Route` / `Page` | En faktisk sida i den genererade sajten (t.ex. `/`, `/kontakt`). Bestäms av `Scaffold`. |
| `Variant` | Site-wide visuellt uttryck (typografi, färg, motif). En sajt har normalt en variant. Tidigare alias: `Scaffold Variant`. |
| `Dossier` | Återanvändbar capability/legokloss som monteras på `Route`/section/slot. Default-kompatibel med alla `Scaffolds` om inget annat sägs. |
| `Generation Package` | Den enda nyttolasten till codegen-LLM. |
| `Build` | Körningen som producerar `Generated Files` och artefakter under `data/runs/<runId>/`. |

### Dossier-klasser: bara `soft` och `hard`

| Klass | Innebörd | Exempel |
|---|---|---|
| `soft` | Återanvändbar frontend/content capability. Inga secrets eller externa API:er. | `pacman-game`, `mouse-reactive-background`, `pricing-calculator`. |
| `hard` | Kräver env, secrets, backend, auth, databas, betalning eller extern API. | `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart`. |

`hybrid` tas bort som klass. En dossier som behöver mockas i designläge men
integration i live-läge är fortfarande `hard` - den har bara en
`mockMode`-konfiguration. Det räcker.

### Termer som tas bort som canonical i naming-dictionary v10

Borttagna (de var dossier-typer som stod ovanpå dossier-klasserna och dubblade
modellen):

- `siteDossier` → ersätts av `projectInput`
- `featureDossier` → räknas bara som `Dossier` med klass `soft`
- `integrationDossier` → räknas bara som `Dossier` med klass `hard`
- `dataDossier` → räknas bara som `Dossier` med klass `soft` om det är data, eller landar i `Project Input` om det är site-specifikt innehåll
- `hybridDossier` → ersätts av `mockMode`-konfiguration på `hard` Dossier

Termerna läggs till i `naming-dictionary.v1.json:globallyForbidden` så
återinförande blockeras automatiskt av regression-testet.

### Termer som läggs till

- `projectInput` → canonical "Project Input". Alias: "Deep Brief", "Example Project".

### Filer på disk

`examples/<siteId>.site-dossier.json` döps om till
`examples/<siteId>.project-input.json` så filnamnet matchar språket. Ingen
adapter eller bakåtkompatibilitet - vi har bara `painter-palma` att migrera.

## Konsekvenser

- `naming-dictionary.v1.json` bumpar `version: 9` → `10`. Net -4 termer, +1 ny.
- `examples/painter-palma.site-dossier.json` döps om.
- `scripts/build_site.py`, `apps/viewser/lib/*` och tester refererar nya
  filnamnet och nya termen `Project Input`.
- `docs/glossary.md`, `docs/architecture/*`, `data/starters/README.md`,
  `governance/rules/build-chain-discipline.md` saneras.
- Två nya rules under `governance/rules/`:
  - `vocabulary-discipline.md` - inga nya arkitekturtermer utan ADR.
  - `dossier-vs-project-input.md` - hård regel om vad Dossier är vs Project Input.

## Vad detta INTE är

- Inte en feature-runda. Vi rör inte selector, embeddings, Pacman, StackBlitz,
  fler starters eller Anthropic.
- Inte en omformulering av `Engine Run`, fas 1/2/3 eller artefaktkontraktet
  (det ligger i `engine-run.v1.json` och rör vi inte här).
- Inte en omdöpning av `siteId`-fältet i kod - det är fortfarande siteId
  eftersom det identifierar en site-instans.

## Mätbart efter PR

- `python scripts/governance_validate.py` grön
- `python scripts/rules_sync.py --check` grön
- `python scripts/check_term_coverage.py --strict` grön
- `python -m pytest -q` grön
- `cd apps/viewser && npm run build` grön
- Search efter `Site Dossier|Feature Dossier|Integration Dossier|Data Dossier|Hybrid Dossier`
  i produktfiler returnerar 0 träffar (utom i ADR och `governance/policies/naming-dictionary.v1.json:globallyForbidden`).
