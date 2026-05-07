# ADR 0006: Term-disciplin (deklaration före användning)

- Status: accepterat
- Datum: 2026-05-07

## Kontext

I gamla `sajtmaskin` blev `brief`, `scaffold`, `context`, `quality gate`, `preview`, `template-library` och `dossier` namnskuggor: samma ord betydde olika saker i olika filer. När ordlistan väl fanns i `docs/architecture/glossary.md` upprätthölls den inte aktivt - termer fick krypa in i kod och dokumentation utan att registreras.

Användaren har uttryckligen krävt strikt kontroll på begreppsfloran. Förra repots passiva ordlista räckte inte.

## Beslut

Sajtbyggaren använder en **deklaration-före-användning**-regel för domänbegrepp, kodifierad i:

- [`governance/rules/term-discipline.md`](../rules/term-discipline.md) (alwaysApply, speglas till `.cursor/rules/`).
- [`governance/policies/naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json) som sanningskälla.
- [`scripts/check_term_coverage.py`](../../scripts/check_term_coverage.py) som diagnos-skript som hittar PascalCase- och citerade termer som inte finns i ordlistan.

Konkret innebär det:

1. Ett nytt domänbegrepp **måste** registreras i `naming-dictionary.v1.json` innan det används någon annanstans (kod, dokumentation, paketnamn).
2. Synonymer/alias accepteras endast i `aliasesAllowed`. Förbjudna alias återinförs inte utan policy-bump.
3. `python scripts/check_term_coverage.py` rapporterar kandidatord; operatören avgör om de är riktiga begrepp.
4. `python scripts/governance_validate.py` cross-checkar att inga policies aktivt använder `globallyForbidden`-termer (utöver i `forbiddenTerms`/`aliasesForbidden`-fält där det är poängen).
5. Code review blockerar PRs som inför nya begrepp utan motsvarande naming-dictionary-uppdatering.

## Vad som räknas som domänbegrepp

Räknas:

- Substantiv som beskriver produktens världsbild (`Site Brief`, `Scaffold`, `Dossier`, `Selection Profile`).
- Mapp- och paketnamn med produktbetydelse (`packages/generation`, `packages/preview-runtime`).
- Klass-/typ-/interfacenamn med produktbetydelse (`StructuredSiteBrief`, `PreviewRuntime`).
- Filnamnssuffix med betydelse (`*.scaffold.json`, `*.dossier.json`).

Räknas inte:

- Vanliga programmeringsord (`function`, `array`, `error`).
- Lokala variabelnamn (`i`, `count`).
- Bibliotekstermer från externa SDK:er (men dokumenteras om de blir produktnära).

## Konsekvenser

- Det går snabbare att lägga till en term i naming-dictionary än att fortsätta använda en oregistrerad. Det ger rätt incitament.
- `check_term_coverage.py` kan skapa brus i tidiga faser (många kandidater). Det är OK; vi filtrerar via `COMMON_WORDS`-listan iterativt.
- När runtime-koden börjar skrivas blir term-coverage-skriptet en pre-commit-hook (gate) i en kommande policy-bump.

## Förhållande till tidigare beslut

- Konkretiserar [ADR 0001](0001-policies-as-source-of-truth.md): policies som sanningskälla kräver att begreppen i policies inte muteras vild i kod.
- Underlag för [ADR 0005](0005-scaffold-dossier-model.md): scaffold/dossier-modellen utökade naming-dictionary till version 2.
