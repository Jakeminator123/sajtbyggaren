# ADR 0063 — Hard Starter-kontrakt: en Starter är ett layout-skal, aldrig en Python-operation

**Status:** Accepted
**Datum:** 2026-06-16
**Beroenden:** ADR 0005 (scaffold-/dossier-modell), ADR 0011 (scaffold-registret
är ärvt arbetsmaterial), ADR 0014 (`SCAFFOLD_TO_STARTER` som handhållen tabell),
ADR 0017 (real-codegen-scope = `marketing-base`), ADR 0019 (B20 step 2:
`ecommerce-lite -> commerce-base`-aktivering), ADR 0053 (hard-dossier-kontrakt)
och ADR 0026 (embeddings parkerade). Bygger på de redan existerande artefakterna
[`governance/policies/scaffold-contract.v1.json`](../policies/scaffold-contract.v1.json),
[`governance/policies/starter-registry.v1.json`](../policies/starter-registry.v1.json)
och den kanoniska mappningen + "Hårda krav per starter" i
[`data/starters/README.md`](../../data/starters/README.md). Konsekvensreglerna
bevakas av `tests/test_starter_scaffold_mapping.py` och
`tests/test_runtime_scaffold_smoke.py`.

## Kontext

Fem starters täcker de fjorton registrerade scaffolden (ADR 0011,
`data/starters/README.md`). De hårda kraven per starter finns redan informellt
listade i `data/starters/README.md` ("Hårda krav per starter"), men de är inte
formaliserade som ett *kontrakt*. Det saknas tre saker:

1. en uttalad regel att en ny Starter aldrig får tvinga fram ändringar i
   `scripts/build_site.py`,
2. en uttalad anslutningsregel mot section-dispatchern (Path B), och
3. en beslutsregel för agenter som frestas att lägga branschspecialfall i
   orkestreringen.

Symptomet idag: bara 6 av 14 scaffolds finns på disk och bara ~6 är
runtime-mappade (alla på `marketing-base`/`commerce-base`). När fler ska "i
spel" uppstår frågan "måste vi skripta startern?". Svaret ska vara nej — men
det är inte skrivet, så agenter och granskare saknar ankaret. Den verkliga
risken är att `build_site.py` växer tillbaka till branschspecialfall, vilket
går rakt emot målbilden (`docs/heavy-llm-flow/00-malbild-och-lager.md`, §1 och
§4) där `build_site.py` = orkestrering och Startern = körbart layout-skal.

Detta kontrakt ska **inte** förväxlas med "contract propagation" i ADR 0026
(embeddings). Det är två olika kontrakt: ADR 0026 parkerar embeddings tills
brief-signaler propagerar korrekt genom kedjan och utbudet passerar ~30
enheter; denna ADR låser gränssnittet för Starter-lagret. Denna ADR ändrar
inte embeddings-statusen.

## Beslut

### 1. Starter-kontraktet (hårda regler)

En Starter (`data/starters/<id>/`):

1. **Får inte kräva ändring i `scripts/build_site.py`.** `build_site.py` är
   orkestrering. Branschlogik hör hemma i scaffold-/section-/dossier-lagret.
2. **Måste ta emot sidor via `write_pages` / section-dispatchern (Path B).** En
   route renderas genom dispatchern, inte genom per-route `if/elif` i
   `build_site.py` (Path A är legacy och ska inte växa).
3. **Måste använda samma token/CSS-kontrakt** som övriga starters — variantens
   `tokens` (color/typography/radius/spacing/motion) injiceras; ingen hårdkodad
   färg eller typografi i startern.
4. **Får inte bära businesslogik** (auth, databas, betalning, CMS, analytics).
   Sådant hör hemma i en `hard` Dossier (ADR 0053), aldrig i startern.
5. **Får inte skapa fake content** — ingen hårdkodad copy, inga påhittade
   recensioner eller CTA-länkar. Innehåll kommer från Project Input + dossiers.
6. **Får bara vara layout/struktur/visuell bas** — ett körbart Next.js-skal som
   uppfyller de hårda kraven (Next.js 16, TypeScript strict, Tailwind 4,
   shadcn/ui, npm-lockfil, ESLint + Prettier).

Punkt 3–6 är formaliseringen av de befintliga "Hårda krav per starter" i
`data/starters/README.md`. Punkt 1–2 är de nya, uttalade gränssnittsreglerna.

### 2. Vad som faktiskt krävs för att sätta en Starter "i spel"

En Starter blir runtime först när ett Scaffold mappar till den. Den generiska,
konfig-drivna vägen för en ny Starter/Scaffold är:

1. **1 scaffold-katalog** under
   `packages/generation/orchestration/scaffolds/<id>/` med de sex obligatoriska
   filerna (`scaffold-contract.v1.json`) — författas via
   `tooling/scaffold-generator`, inte för hand.
2. **1 kanonisk mappnings-rad** `scaffold: starter` i `data/starters/README.md`
   (mellan `scaffold-starter-mapping`-markörerna) — målbilden.
3. **Runtime-aktivering = 2 rader:** en post i `SCAFFOLD_STARTER_MAP`
   (`packages/policies/component_catalog.py`, re-exporteras som
   `SCAFFOLD_TO_STARTER` av `plan.py`) och en `_RUNTIME_SCAFFOLD_HINTS`-post
   (`packages/generation/discovery/resolve.py`). Båda krävs
   (`tests/test_runtime_scaffold_smoke.py`).
4. Eventuellt **1 renderare** — endast om en section-typ är genuint ny (annars
   återanvänds dispatchern). En ny section-typ är en ny byggförmåga, inte
   starter-skräddarsöm.
5. Eventuellt **1 dossier** — om en ny capability behövs.
6. **Tester** — mapping-drift, runtime-smoke och ev. golden-path.

Krävs mer än så är det troligen inte en "ny Starter" utan en ny byggförmåga
som hör hemma i dispatcher-/dossier-/capability-lagret (jfr
`docs/scaffold-runtime-extension-needed.md` och B49 för `docs-base`).

### 3. Varningssignal (beslutsregel för agenter och granskare)

Om en agent säger "för den här startern måste vi lägga till N if-satser i
`build_site.py`" → **stoppa nästan alltid**. Rätt fråga är i stället: *"vilket
kontrakt saknas så att Startern kan ansluta generiskt?"* Detta speglar
`scaffold-contract.v1.json:forbiddenInScaffoldFiles` ("if-else word matching som
scaffold-väljare") och utvidgar förbudet till orkestreringslagret.

### 4. Lager-karta (målbild, här låst för Starter-lagret)

- `scripts/build_site.py` = orkestrering
- `packages/generation/build/*` = generiska byggprimitiver (renderers/dispatcher)
- `packages/generation/orchestration/scaffolds/*` = routes/sections (deklarativ JSON)
- `data/starters/*` = körbara layout-skal
- `packages/generation/orchestration/dossiers/*` = capability-paket

## Vad denna ADR inte beslutar

- Ingen kodändring i `packages/`, `scripts/`, `apps/` eller `backoffice/` —
  detta är ett docs/governance-beslut.
- Ingen aktivering av en specifik Starter/Scaffold (t.ex. `portfolio-creator`).
  Det är en egen slice som ska följa checklistan i avsnitt 2.
- Ingen ändring av embeddings-status — embeddings förblir parkerade per ADR
  0026.
- Ingen ändring av `scaffold-contract.v1.json` eller `starter-registry.v1.json`
  — denna ADR pekar på dem, inte ändrar dem. En framtida policy-bump kan koda
  kontraktet maskinläsbart (eget slice).

## Konsekvenser

Positiva:

- En agent som ska sätta en Starter i spel har nu ett uttalat ankare: konfig +
  ≤2 rader runtime, aldrig `build_site.py`-special. Granskare kan avvisa
  Python-sprawl med en regel i handen.
- Skyddar slimningen av `build_site.py` (den ska inte bli 5000 rader
  branschspecialfall).
- Formaliserar de redan existerande hårda kraven så de blir refererbara.

Negativa/neutrala:

- Reglerna fanns delvis redan (`data/starters/README.md`,
  `scaffold-contract.v1.json`) — denna ADR höjer dem till uttalat kontrakt
  snarare än uppfinner dem.
- Maskinläsbar validering (schema) är medvetet utanför scope; tills den finns
  gäller kontraktet via review + de befintliga drift-testerna.
