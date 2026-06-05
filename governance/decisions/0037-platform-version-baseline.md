# ADR 0037 — Plattforms-versionsbaslinje (en sanningskälla för versioner)

**Status:** Accepted
**Datum:** 2026-06-03
**Beroenden:** ADR 0030 (preview/deploy-providers är adapters, fristående output),
ADR 0028 (Runtime Ladder), ADR 0033 (vercel-sandbox primär preview),
`docs/agent-prompts/platform-version-baseline.md` (uppdrags-spec),
`docs/product-operating-context.md` (nordstjärna + "vänta med"-listan).

## Kontext

Sajtbyggaren pinnar idag samma kärnversioner för hand i sex separata
`package.json`: `apps/viewser/package.json` och de fem starters under
`data/starters/` (varav fyra har en `package.json` idag; saas-base saknar ännu
en). Verifierat 2026-06-03 delar de redan next 16.2.6, react / react-dom
19.2.4, lucide-react ^1.14.0, shadcn ^4.7.0, class-variance-authority ^0.7.1,
tailwind-merge ^3.5.0, clsx ^2.1.1 och Tailwind 4.

Lokal toolchain kör Node 24.15.0 (Volta global default) med npm 11,
Vercel-projektet sajtbyggaren-viewser kör Node 24.x, och sandbox-runnern
(`apps/viewser/lib/vercel-sandbox-runner.ts`) hårdkodar runtime node24. Allt
ligger alltså redan på Node 24 — men av sammanträffande, inte av kontrakt:

- Ingen fil har en `engines`- eller `volta`-pin för Node, så ingenting hindrar
  en host från att köra fel major.
- Versionerna är upprepade för hand i sex filer och inget larmar om de driftar
  isär. Faktisk drift finns redan: tailwindcss och `@tailwindcss/postcss` är
  ^4 i viewser/marketing men ^4.0.14 i commerce/portfolio/docs, och prettier /
  prettier-plugin-tailwindcss är exakt-pinnade i viewser men caret i starters.
- En liten latent miss: `@types/node` är ^20 fast runtime är Node 24.

När nya beroenden (lucide, shadcn, m.fl.) ska in skalar handpinnandet dåligt
och risken för drift mellan lokalt, Vercel, sandbox, starters och genererad
output växer.

## Beslut

**Node 24 LTS pinnas som standard, och en gemensam, maskinläsbar
versionsbaslinje införs som EN sanningskälla för runtime- och
beroende-versioner.** Baslinjen är operatör-/governance-ägd, inte ett
UI-beslut.

Konkret:

### Regel 1 — Baslinjen är en deklarativ källa, inte en workspace

Baslinjen bor i `governance/policies/platform-baseline.v1.json` (validerad mot
`governance/schemas/platform-baseline.schema.json`). Den listar pins för
runtime (node `24.x`, voltaNode `24.15.0`, npm `11.x`), framework (next, react,
react-dom, eslint-config-next), ui, styling och tooling.

Vi inför **inte** npm/pnpm workspaces eller catalog. Det skulle bryta ADR 0030:
varje genererad sajt och starter måste förbli fristående och byggbar med
`npm install && npm run build && npm run start` på vilken Node-host som helst
(operatörens dator, en container, Vercel, en sandbox). Baslinjen ger en
sanningskälla utan att offra den portabiliteten — `package.json` speglar
baslinjen, den äger den inte.

### Regel 2 — En grind larmar vid drift

`scripts/check_platform_baseline.py` (syskon till `governance_validate.py`,
`check_term_coverage.py`, `audit_starter_candidate.py`) läser baslinjen och
asserterar att `apps/viewser/package.json` och alla `data/starters/*/package.json`
konformar. `--check` (default i guard-sviten) failar deterministiskt vid drift
med en tydlig diff. `--fix` skriver in `engines` + `volta` och rättar pins
mekaniskt (samma mönster som `rules_sync.py`).

Eftersom en genererad sajt är en kopia av sin starter (`copy_starter()` kopierar
starterns `package.json`, `patch_package_json()` byter bara fältet `name`), ÄR
starters codegen-mallen — att grinda starters grindar den genererade sajtens
`package.json`.

### Regel 3 — Bara Vercel-stödda kombos

Varje pinnad version måste tillhöra en kombo som Vercel faktiskt kör. Node 24
är GA och Next 16 stöds, så baslinjen pinnar Node 24 LTS. En bump kräver en ny
Vercel-stödd kombo. Versioner som Vercel inte kör får aldrig pinnas.

### Regel 4 — Stegvis, granskad propagering

Steg 1–3 (ADR + baslinje + checker + tester) ligger helt i governance-/script-
lanen. Det faktiska propageringssteget — injicera `engines` + `volta`, bumpa
`@types/node` ^20 → ^24 och align:a de pins som idag varierar — körs via ett
granskat `--fix` och rör `apps/viewser/package.json` (Christophers lane) plus
`data/starters/*`. Det kräver operatörs-OK och koordinering via
`docs/agent-inbox.jsonl` innan det landar, så det inte blir merge-krock.

Tills propageringen körts är dessa mål markerade `pendingPropagation` i
policyn: `--check` rapporterar dem men failar inte på dem, medan den redan
uniforma kärnan (next, react, m.fl.) hard-grindas. När propageringen landat
flyttas målen till `enforced`.

## Vad ADR 0037 INTE beslutar

- Den propagerar inte själv pins eller `engines`/`volta` in i någon
  `package.json`. Det är steg 4, ett separat granskat `--fix`.
- Den byter inte Node-major. Baslinjen stannar på 24 LTS; en major-bump är en
  egen ADR.
- Den inför ingen ny canonical artefaktfil eller runtime-typ utöver själva
  policyn + dess schema. `package.json` förblir vanlig npm-metadata.
- Den rör inte hur beroenden faktiskt installeras (npm är fortsatt
  package manager per starter).

## Konsekvenser

Positiva:

- En sanningskälla i stället för sex handpinnade filer; drift mellan lokalt,
  Vercel, sandbox, starters och genererad output blir en grind-fail i stället
  för ett tyst fel långt senare.
- Skalar när nya bibliotek ska in: lägg en vettad, Vercel-stödd version i
  baslinjen en gång. Codegen får bara använda beroenden som finns i baslinjen,
  på baslinjens version. shadcn-komponenter är kopierad källkod (inte ett
  beroende) och behöver bara cva/tailwind-merge/lucide på baslinje-versionerna,
  vilket redan täcks.
- ADR 0030-portabiliteten behålls: ingen workspace/catalog, varje output är
  fortsatt fristående vanlig Next.js.

Negativa:

- Lite extra underhåll: en bump måste göras i baslinjen och propageras via
  `--fix` i stället för att redigeras direkt i en `package.json`. Det är priset
  för att slippa drift, och `--fix` gör propageringen mekanisk.
- Baslinjen måste hållas i synk med vad Vercel stödjer; en framtida
  Vercel-ändring av stödd Node-major kräver en baslinje-bump (med ny ADR vid
  major-byte).

## Referenser

- [ADR 0030 — Preview/deploy-providers är adapters](0030-preview-provider-portability.md)
- [ADR 0028 — Runtime Ladder](0028-runtime-ladder.md)
- [ADR 0033 — vercel-sandbox primär preview](0033-vercel-sandbox-primary-preview.md)
- [`governance/policies/platform-baseline.v1.json`](../policies/platform-baseline.v1.json)
- [`governance/schemas/platform-baseline.schema.json`](../schemas/platform-baseline.schema.json)
- [`docs/agent-prompts/platform-version-baseline.md`](../../docs/agent-prompts/platform-version-baseline.md)
