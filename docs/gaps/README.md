# Gaps och path-reservation

Sprintvakt använder gaps för att ge Jakob och Christopher små, tydliga
arbetsytor utan att två agenter råkar ändra samma filer samtidigt.

## Så används gaps

1. Läs `docs/workboard.json`.
2. Välj eller skapa ett gap med owner, paths, doNotTouch, acceptance och checks.
3. Kör collision-check innan arbete startar.
4. Reservera path scopes om gapet ska bli aktivt.
5. Generera agentprompt och arbeta bara inom scope.
6. Efter merge till `main`: synka `jakob-be` och `christopher-ui` från
   `origin/main` i stället för att öppna separata PR:er mot arbetsbrancherna.

## Ägargränser

- Jakob äger backend, generation, governance, scripts, runtime och
  merge/review.
- Christopher får som default smala UI/frontend-gaps i Viewser och
  presentationslagret.
- API-shape, run-shape, preview-runtime och generator-contract är Jakob-owned.
- Om ett UI-gap kräver backend-kontrakt ska gapet stoppas eller delas upp i ett
  separat Jakob-owned contract-gap.

## Path-reservation

En path-reservation är ett anspråk på filer eller globbar medan gapet är aktivt.
Ingen får reservera samma scope utan explicit handoff.

Exempel:

```json
{
  "owner": "christopher",
  "gapId": "GAP-viewser-empty-state",
  "paths": ["apps/viewser/components/**"],
  "reason": "UI polish in viewer components"
}
```

## Collision-risk

- `green`: inga överlapp och inga lane-brott. Docs-only Sprintvakt-ändringar är
  normalt gröna när de görs av Sprintvakt/Steward.
- `yellow`: möjligt delat ansvar eller contract-risk. Exempel: Jakob rör
  Viewser-komponenter samtidigt som Christopher har aktivt UI-gap, eller
  Christopher föreslår `apps/viewser/lib/**` där server-/run-shape kan påverkas.
- `red`: blocker. Exempel: två aktiva gaps rör samma fil/glob, Christopher rör
  `scripts/**`, `packages/generation/**`, `governance/policies/**` eller
  `tests/test_*.py`, eller någon försöker skriva utanför tillåtna Sprintvakt-
  filer via MCP.

## Green innan arbete

Ett gap är redo att starta när:

- `python scripts/sprintvakt_check.py` är grön.
- `detect_collisions` ger `green` eller en dokumenterad och godkänd `yellow`.
- Gapet har owner, paths, doNotTouch, acceptance och checks.
- Agentprompten upprepar exakt scope och stoppregler.
