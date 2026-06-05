# Builder-uppdrag: plattforms-versionsbaslinje (en sanningskälla för versioner)

> Klistra in detta i en Cursor-agent (lokal eller cloud-grind). Prompten är
> self-contained. Uppdraget inför EN styrd baslinje för runtime- och
> beroende-versioner som lokalt, Vercel, sandboxen, starters och genererad
> output alla läser från — i stället för dagens duplicerade pins i 6 separata
> `package.json`. Beslutet är operatör-/governance-ägt (din lane), inte ett
> UI-beslut.

## Roll

Du är en governance/builder-agent som ska skapa en maskinläsbar
versionsbaslinje + en drift-kontroll, och (efter operatörs-OK) konforma
befintliga `package.json` mot den. Du duplicerar inte versioner — du gör en
sanningskälla och en grind som larmar vid drift.

## Branch-regel (HÅRD)

- Arbeta på `jakob-be`. Verifiera vid start:
  - `git rev-parse --abbrev-ref HEAD` → `jakob-be`
  - `git fetch origin && git status` → up to date med `origin/jakob-be`
- Ändra inte `main`. Använd `main` bara som referens.
- Steg 1–3 (baslinje + checker + ADR) ligger HELT i din lane (`governance/`,
  `scripts/`, `docs/`, `tests/`). Steg 4 (propagering) rör
  `apps/viewser/package.json` (Christophers lane) + `data/starters/*` — kräver
  operatörs-OK och koordinering via `docs/agent-inbox.jsonl` innan du rör dem.

## Bakgrund (nuläge, verifierat 2026-06-03)

- Lokal Node = `24.15.0` (via Volta global default), npm 11.
- Vercel-projektet `sajtbyggaren-viewser` kör Node `24.x` (projekt-inställning).
- Sandbox-runnern hårdkodar runtime `node24`
  (`apps/viewser/lib/vercel-sandbox-runner.ts`).
- `apps/viewser/package.json` och alla 5 starters
  (`data/starters/{marketing,commerce,portfolio,docs,saas}-base`) delar redan
  samma kärnversioner: `next 16.2.6`, `react`/`react-dom 19.2.4`,
  `lucide-react ^1.14.0`, `shadcn ^4.7.0`, `class-variance-authority ^0.7.1`,
  `tailwind-merge ^3.5.0`, `clsx ^2.1.1`, Tailwind 4.
- MEN: ingen fil har `engines`/`volta`-pin för Node, versionerna är upprepade
  för hand i 6 filer, och inget larmar om de driftar isär. Liten latent miss:
  `@types/node` är `^20` fast runtime är Node 24.

Allt ligger alltså redan på Node 24 — men av sammanträffande, inte av kontrakt.

## Mål

En sanningskälla + en grind som håller lokalt, Vercel, sandbox, starters och
genererad output i lås, och som skalar när nya beroenden (lucide, shadcn, m.fl.)
ska in.

### 1. ADR

Skriv `governance/decisions/00xx-platform-version-baseline.md` (nästa lediga
nummer). Beslut: Node 24 LTS som pinnad standard + en gemensam
versionsbaslinje som sanningskälla. Motivering: ta bort drift-risk mellan
lokal toolchain, Vercel-runtime, sandbox och genererad output; behåll ADR
0030-portabiliteten (varje genererad sajt och starter förblir fristående
vanlig Next.js). Referera ADR 0030.

### 2. Baslinje-policy (JSON)

Skapa `governance/policies/platform-baseline.v1.json` (+ schema under
`governance/schemas/`) som listar:

- `runtime`: node `24.x`, voltaNode `24.15.0`, npm `11.x`.
- `framework`: next `16.2.6`, react `19.2.4`, react-dom `19.2.4`,
  eslint-config-next `16.2.6`.
- `ui`: lucide-react `^1.14.0`, shadcn `^4.7.0`,
  class-variance-authority `^0.7.1`, tailwind-merge `^3.5.0`, clsx `^2.1.1`,
  tw-animate-css `^1.4.0`, base-ui-react `^1.4.1`.
- `styling`: tailwindcss `^4`, tailwindcss-postcss `^4`.
- `tooling`: typescript `^5`, types-node `^24`, eslint `^9`,
  prettier `^3.8.3`, prettier-plugin-tailwindcss `^0.8.0`.

Regel som dokumenteras i policyn: varje version måste vara en Vercel-stödd
kombo (Node 24 är GA, Next 16 stöds). Bump kräver en Vercel-stödd kombo.

### 3. Drift-checker

Skapa `scripts/check_platform_baseline.py` (syskon till `governance_validate`,
`check_term_coverage`, `audit_starter_candidate`):

- Läser baslinjen och asserterar att `apps/viewser/package.json`, alla
  `data/starters/*/package.json`, och codegen-mallen (det som blir den
  genererade sajtens `package.json`) konformar: samma pins + `engines.node`
  finns.
- `--check` (default i guard-sviten) failar vid drift med tydlig diff.
- `--fix` skriver in `engines` + `volta` + rättar pins mekaniskt (samma mönster
  som `rules_sync.py --check/--write`).
- Lägg testtäckning i `tests/test_platform_baseline.py`.

Wira `--check` in i guard-sviten + dokumentera kommandot i README:s Snabbstart.

### 4. Propagering (KRÄVER operatörs-OK + Christopher-koordinering)

Kör `--fix` så `engines` + `volta` (Node 24) injiceras och pins alignas i
viewser + alla 5 starters + codegen-mallen. Bump `@types/node` `^20` → `^24`.
Eftersom `apps/viewser/package.json` är Christophers lane: posta en notis i
`docs/agent-inbox.jsonl` till `christopher-ui` (eller låt operatören merga in
det) innan ändringen pushas, så det inte blir merge-krock.

## Hur det skalar (lucide/shadcn/"mkt annat")

Baslinjen blir samtidigt allowlist + pinnad version för vad codegen får lägga i
en genererad sajt. `codegenModel` ska bara få använda beroenden som finns i
baslinjen, på baslinjens version → sajt, starter, viewser, sandbox och Vercel
hålls i lås. Nytt bibliotek = lägg i baslinjen en gång, med en vettad version.
shadcn-komponenter är kopierad källkod (inte ett beroende) → de behöver bara
cva/tailwind-merge/lucide på baslinje-versionerna, vilket redan täcks.

## Out of scope (rör inte)

- INTE npm/pnpm workspaces eller catalog — det bryter ADR 0030 (varje
  genererad sajt och starter måste vara fristående och byggbar på vilken host
  som helst, inkl. Vercel + sandbox). Baslinje-JSON ger en sanningskälla utan
  att offra det.
- INTE byta Node-major (stanna på 24 LTS).
- INTE röra `docs/heavy-llm-flow/` (annan agents mapp).
- INTE öppna PR mot `main` — pusha till `jakob-be`.
- Steg 4-propagering utan operatörs-OK.

## Validering (alla MÅSTE vara gröna före push)

```powershell
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python scripts/check_platform_baseline.py --check
python -m ruff check .
python -m pytest tests/test_platform_baseline.py -q
python scripts/focus_check.py
```

## Acceptanskriterier

- ADR + `platform-baseline.v1.json` + schema + `check_platform_baseline.py`
  (`--check`/`--fix`) + tester finns och guards är gröna.
- `--check` failar deterministiskt om en `package.json` driftar från baslinjen.
- Steg 4 (engines/volta/pin-alignment) körd ENDAST efter operatörs-OK och
  inbox-notis till `christopher-ui`.
- Inga workspaces/catalog införda.
- Bumpa senast-verifierad-SHA i `docs/current-focus.md` per Standard loop.

## Commit-stil

Engelska titel, svensk body, backtick-quoted identifiers, ADR-referens. T.ex.:

1. `feat(governance): platform version baseline + drift check (ADR 00xx)`
2. `test(governance): platform-baseline conformance`
3. (efter OK) `chore(platform): conform viewser + starters to Node 24 baseline`
