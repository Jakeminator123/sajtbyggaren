# Import-logg från sajtmaskin

Den här loggen håller spår av varje **manuell port** av en idé eller modul från `Jakeminator123/sajtmaskin` till Sajtbyggaren. Vi använder inte `git cherry-pick`. Vi portar medvetet och döper om enligt [`naming-dictionary.v1.json`](../../governance/policies/naming-dictionary.v1.json).

## Varför manual port?

Sajtmaskin har historisk komplexitet (namnskuggor, F2/F3-tier, spridda begrepp) som vi inte vill ärva mekaniskt. Cherry-pick riskerar att dra in beroende-grafer och termer som bryter mot Sajtbyggarens governance.

**Regel:** Inga commits från sajtmaskin landar i Sajtbyggarens git-historik. Vi ser sajtmaskin som extern referens; portar är våra egna commits.

## Procedur per import

1. Identifiera idén/modulen som ska porteras.
2. Hitta källcommit eller källfil i sajtmaskin (för spårbarhet).
3. Verifiera att inga begrepp som ska ärvas saknas i `naming-dictionary.v1.json`. Om de saknas: registrera dem **innan** du portar.
4. Skriv om koden i Sajtbyggarens stil (engelska identifierare, kanoniska namn, `repo-boundaries`-respekterande imports).
5. Lägg till en regression-test om porten är icke-trivial.
6. Lägg till en post i den här loggen enligt mallen nedan.
7. Kör hela kontroll-sviten (`scripts/governance_validate.py`, `scripts/rules_sync.py --check`, `scripts/check_term_coverage.py --strict`, `pytest`).

## Mall

```markdown
## Import NNN — <Kort namn>

- **Source:** `Jakeminator123/sajtmaskin@<commit-eller-tag>`, sökväg `<path/to/file>`
- **Target:** `<sajtbyggaren-path>`
- **Reason:** <varför vi vill ha detta>
- **Renamed:**
  - `<gammalt namn>` → `<nytt kanoniskt namn>`
  - ...
- **New terms registered:** <id> (om några)
- **Tests added:** `<test-fil>`
- **Status:** ported | tested | accepted
- **Notes:** <eventuella avvikelser från sajtmaskin-implementationen>
```

## Imports

(Inga imports gjorda än. Första importen sker när fas 1 LLM-flödet börjar implementeras.)

## Kandidater att titta på senare

Från [`docs/migration-plan.md`](../migration-plan.md):

| Källa | Område | Varför intressant |
|-------|--------|-------------------|
| `1f4e869` | LLM-pipeline | "Simpler pipeline, richer prompts" - arkitekturmässigt nära det vi vill ha. |
| `ba33b28` | Generation-bas | Före Design Priority-komplexiteten introducerades. |
| `04b3215` | Quality-baseline | Tagg "best generation quality so far"; behöver verifieras med eval. |
| `29971fb`, `9eccc75` | Streaming | Stream/builder-respons (kommer porteras under fas 3). |
| `3e7ca17`, `a5b4fb2` | Builder/auth | Builder-livscykel-mönster (kommer först när `apps/` byggs). |

Inga av dessa porteras automatiskt. Varje kandidat utvärderas när motsvarande fas i Sajtbyggaren börjar.
