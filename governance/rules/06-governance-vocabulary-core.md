---
description: Governance-JSON är sanningskälla; inga nya domänbegrepp, alias, scheman eller owner-mappar utan naming-dictionary (och ibland ADR). Ett begrepp = ett kanoniskt namn + en ägarmapp.
alwaysApply: true
---

# Governance och vokabulär

Konsoliderar governance-först, term-disciplin, vocabulary-disciplin och no-duplicate-terms. Bakgrund: i gamla `sajtmaskin` växte begreppen okontrollerat tills `brief`, `scaffold`, `context`, `quality gate`, `preview`, `template-library` och `dossier` betydde olika saker i olika filer. Vi tvingar **deklaration före användning**.

## Sanningskällor

- Policies: [`governance/policies/`](../policies/) — JSON är sanning, allt annat (kod, docs, `.cursor/rules`) härleds från dem.
- Schemas: [`governance/schemas/`](../schemas/)
- Reglernas källa: `governance/rules/`
- Cursor-regler: `.cursor/rules/*.mdc` är genererade speglar. Redigera ALDRIG spegeln direkt om ändringen ska committas. Uppdatera `governance/rules/*.md` och kör:

  ```powershell
  python scripts/rules_sync.py
  python scripts/rules_sync.py --check
  ```

## Hård regel: deklaration före användning

Att (a) införa ett nytt domänbegrepp (klass/typ/JSON-fält/mapp/dokumentationsterm), (b) återanvända ett befintligt begrepp i ett nytt område, eller (c) skapa ny policy/schema/paket — kräver att begreppet finns i [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json) **innan** det skrivs någon annanstans. Saknas det: stoppa, lägg till termen i samma PR, sen får den användas.

- Ett begrepp har exakt **ett** kanoniskt namn och **en** ägarmapp (`ownerPackage`, måste matcha [`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json)). Inga namnskuggor.
- Begrepp i `aliasesAllowed` får dyka upp i kommentarer/docs, men koden använder alltid det kanoniska namnet.
- Termer i `globallyForbidden` (`v0`, `tier1`, `tier2`, `tier3`, `preview-host`, m.fl.) får aldrig återinföras. `sandbox` får bara användas som registrerat alias för `Preview Runtime`/Vercel Sandbox, inte som fri produktterm. Återanvändning kräver att termen tas bort från forbidden-listan i en explicit policy-bump.
- Alla policies måste valideras mot sina JSON Schema innan ändring committas: `python scripts/governance_validate.py`.

### Vad som räknas som domänbegrepp

Räknas: produktsubstantiv (`Site Brief`, `Scaffold`, `Dossier`, `Generation Package`, `Preview Runtime`, `Quality Gate`, `Selection Profile`), mapp-/paketnamn, produktbärande klass-/typnamn (`StructuredSiteBrief`, `ScaffoldDefinition`), filnamnssuffix med betydelse (`*.scaffold.json`, `*.dossier.json`, `*.policy.json`).

Räknas inte: vanliga programmeringsord (`function`, `class`, `array`), bibliotekstermer från externa SDK:er, lokala variabelnamn, samt UI-komponentnamn som bara bor i en enda app (`PromptBuilder`, `RunHistory`, `TokenMeter`).

## Vocabulary-disciplin (ADR krävs)

Efter ADR 0012 är operator-vokabulären låst. Det enda flödet:

```text
Init Prompt -> Project Input (Deep Brief) -> Starter -> Scaffold -> Variant
  -> Dossier (soft eller hard) -> Generation Package -> Build
```

- Inga nya arkitekturtermer, och inga nya `*-dossier`/`*-input`/`*-project`/`*-brief`/`*-package`-suffix, utan en ADR som motiverar varför ett befintligt begrepp inte räcker.
- Finns redan två namn för samma sak: stoppa, gör en cleanup-PR (välj canonical, förbjud det andra via `globallyForbidden`, döp om på disk). Driv inte cleanup-PR och feature-PR samtidigt.

| Operator får säga | Kod/policies använder |
|---|---|
| `repo` (om starter-bas) | `Starter` |
| `sajt` / `site` | `Project Input` (operator-data) / `Build Result` (genererad output) |
| `legokloss` | `Dossier` |
| `mall` | `Scaffold` (inte `Template`) |
| `tema` / `look` | `Variant` |

## Procedur när ett begrepp saknas

1. Föreslå termen i `naming-dictionary.v1.json` med `id` (camelCase), `canonical`, `definition` (1-3 konkreta meningar), `ownerPackage`, `aliasesAllowed`/`aliasesForbidden`. Vid ny arkitekturterm: skriv även ADR under `governance/decisions/00XX-<slug>.md` och vänta på godkännande.
2. Bump `version` i naming-dictionary om förändringen är substantiell.
3. Kör `python scripts/governance_validate.py` (krock med globally-forbidden) och `python scripts/check_term_coverage.py` (nya användningar plockas upp).
4. Implementera först därefter koden/dokumentationen.

## Vanliga stopp

Stoppa och fråga/planera om ändringen ändrar runtime-kontrakt över flera lager, skapar nytt schema/policy/paketbegrepp, flyttar ansvar mellan `scripts/`/`packages/`/`apps/`/`governance/`, eller kräver ny dependency.
