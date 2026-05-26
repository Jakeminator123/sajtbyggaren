# Cloud-grind-prompt 4 — Gap 9 (moodImages-isolering + Vision → notesForPlanner)

> **Copy-paste hela detta block som första prompt i en ny Cursor Cloud Agent-session.**
> Agenten ska kunna jobba self-contained utan att läsa andra docs.
>
> **VÄNTA — starta INTE förrän Prompt 1 (Gap 6+7) är mergad till `origin/jakob-be`.**
> Båda prompter rör `scripts/build_site.py` `copy_operator_uploads`-flödet och vill inte krocka.

---

Du är Builder-agent som kör i en cloud-agent-VM (Ubuntu). Repo: `Jakeminator123/sajtbyggaren`. Arbets-branch: **`jakob-be`** (Jakob-lane). Du touchar bara GitHub-remoten.

## Mission

Stäng **backend-Gap 9** (`moodImages[]`-isolering). Idag laddar UI upp 1-5 referensbilder via `AssetDropzone role="gallery"` i `apps/viewser/components/discovery-wizard/steps/visual-step.tsx`, och `composeMasterPrompt()` skriver en text-sammanfattning per mood-bild i prompten. Men:

- Mood-bilder ska **inte** kopieras till `public/uploads/` på den genererade sajten (de är inspiration, inte sajt-assets). Idag iter_asset_refs hittar dem inte explicit som "mood" — verifiera och säkerställ.
- Mood-bilderna ska isoleras till `data/uploads/<runId>/__mood/` för intern bevarande och eventuell Vision-pipeline.
- Vision-resultat (om backend kör Vision separat på dem för att extrahera färgpalett/stil) ska mappas in i `site-brief.notes_for_planner`.

Acceptanskriterium från `docs/backend-handoff.md` Gap 9: *"Mood-bilder ska finnas i `data/uploads/<runId>/__mood/` men inte i `public/uploads/` på den färdiga sajten."*

## Branch + förutsättningar

```bash
git fetch origin --prune
git switch jakob-be
git pull --ff-only origin jakob-be
git status                                                  # ska vara clean
git log --oneline -10
git rev-list --left-right --count origin/main...origin/jakob-be
```

Verifiera att Prompt 1:s favicon/og-image-konvertering är inne (kolla `git log` efter `feat(build): close Gap 6 + 7`). Om inte: stoppa och rapportera "Prompt 1 inte mergad än — väntar".

Stoppa om `git pull --ff-only` failar.

## Tillåtna paths (write-set)

- `scripts/build_site.py` — utöka `iter_asset_refs` och `copy_operator_uploads` så `moodImages` filtreras bort från `public/uploads/`-flödet och istället skrivs till `data/uploads/<siteId>/__mood/`.
- `scripts/prompt_to_project_input.py` — om moodImages-mapping behöver kompletteras i Project Input-strukturen.
- `packages/generation/discovery/resolve.py` — om Vision-resultatet ska mappas in i `notesForPlanner` här.
- `packages/generation/brief/extract.py` — om `notesForPlanner`-fältet i SiteBrief behöver utökas med mood-sammanfattning.
- `governance/schemas/project-input.schema.json` — verifiera att `moodImages` finns som array av AssetRef. Om saknas: lägg till som additiv property under `additionalProperties: false`-regimen.
- `tests/test_builder_smoke.py` eller ny `tests/test_mood_isolation.py` — regression-tester.

## Off-limits paths (do not touch)

- `apps/viewser/components/**` (Christopher-lane).
- `apps/viewser/app/**/*.tsx`.
- `apps/viewser/app/api/upload-asset/route.ts` — Upload-API:t accepterar redan favicon/ogImage/backgroundVideo. Mood-bilder laddas upp som `role: "gallery"` enligt visual-step.tsx — verifiera men ändra inte upload-route:t.
- `governance/policies/**`.
- `packages/generation/orchestration/scaffolds/**`.

## Acceptanskriterier

1. När `project_input.moodImages` är en icke-tom lista av AssetRef, **filtreras** de bort från `iter_asset_refs()`-resultatet (så `copy_operator_uploads` inte kopierar dem till `public/uploads/`).
2. Mood-bildernas bytes kopieras istället till `data/uploads/<siteId>/__mood/<assetId>.<ext>` så att de bevaras för intern användning. Använd samma disk-/sourceUrl-lookup-logik som `copy_operator_uploads` har för andra refs (disk-first, sourceUrl-fallback).
3. Ny hjälpfunktion `copy_mood_assets(site_id, project_input) -> int` (eller motsvarande namn) som hanterar mood-pipelinen separat. Den kallas från samma plats i `build_site.py`-flödet som `copy_operator_uploads`, men returnerar antal mood-bilder isolerade.
4. Om backend redan har Vision-output för mood-bilder (kolla `apps/viewser/lib/asset-store/vision.ts` för shape — varje AssetRef har `visionConfidence`-fält och eventuell mood-sammanfattning), mappas den in i `site-brief.notes_for_planner` med ett prefix typ `"Visual mood: <sammanfattning>"`. Om Vision-output saknas: hoppa över utan att fela.
5. `_apply_directives_fields` (eller motsvarande i `packages/generation/discovery/resolve.py`) bevarar `moodImages`-referenserna i `project_input` så framtida pipeline-steg kan hitta dem. Inga AssetRef-objekt droppas tyst.
6. Schema-bumpning i `governance/schemas/project-input.schema.json`: om `moodImages` inte redan finns som `array` of `$defs.assetRef`, lägg till som **additiv** property (alltså inte kräver fält). Skriv ADR-tillägg under `governance/decisions/` bara om schema-ändringen kräver det per `docs/agent-handbook.md`-regeln "nya canonical termer kräver ADR" — `moodImages` är inte en ny canonical term så ADR är troligen inte nödvändig.
7. Nya tester (minst 3): (a) mood-bilder hamnar inte i `public/uploads/`, (b) mood-bilder hamnar i `data/uploads/<siteId>/__mood/`, (c) AssetRef utan disk-bytes och utan sourceUrl skippas snyggt utan att avbryta build:en.
8. `python -m pytest tests/ -q` grön. Existerande tester ska inte regressera.

## Tekniska tips

- `iter_asset_refs` (rad ~769 i `scripts/build_site.py`) iterar `brand.logo`, `brand.heroImage`, `gallery[]`, samt `media.favicon/ogImage/backgroundVideo`. Mood-bilder ligger i `project_input.moodImages` på top-nivå. Lägg till en explicit filter: om en ref kommer från `moodImages`-listan, hoppa över i `iter_asset_refs`.
- Alternativt: lägg till en parameter `include_mood: bool = False` på `iter_asset_refs` så `copy_operator_uploads` (utan flagga) inte tar med dem, men `copy_mood_assets` (med flagga) gör.
- Pass-through-lösning: lägg till en `_iter_mood_refs(project_input)` som specifikt returnerar `moodImages[]`-listan, så två separata loop:ar i två separata funktioner. Föredra renaste arkitekturen.
- `data/uploads/<siteId>/__mood/` skapas via `Path(...).mkdir(parents=True, exist_ok=True)`.
- För Vision → notesForPlanner: kolla om `apps/viewser/lib/asset-store/vision.ts` har en output-shape som lagras i AssetRef. Om Vision körs UI-side och resultatet skickas in i Project Input redan, kan backend bara läsa det. Om Vision körs backend-side via en annan path, är scope för Gap 9 inte detsamma — då bara isolera mood-bilderna och lämna Vision-mappningen till en framtida prompt (notera det i commit-body).

## Final guards (alla ska vara gröna före push)

```bash
python -m ruff check .
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python scripts/sprintvakt_check.py
python -m pytest tests/ -q
```

## Stoppvillkor

Stoppa och rapportera om:

- Prompt 1 inte mergad än (rebase-konflikt vid `copy_operator_uploads`).
- Schema-bumpning kräver ADR och du är osäker — bättre att fråga operatören.
- Vision-pipelinen visar sig vara mer komplex än prompten antar — då stäng bara mood-isoleringen och flagga Vision-delen som "future scope".

## Commit-format

En eller två atomiska commits:

```
1. feat(build): close Gap 9 — isolate moodImages to data/uploads/<siteId>/__mood/
2. feat(brief): map moodImages Vision output to notes_for_planner   (om relevant)
```

Engelska commit-body med kort förklaring av varför + filer som rörts.

## Push

```bash
git push origin jakob-be
```

Ingen PR. Operatörens beslut.

## Rapport tillbaka till operatör

```
Pushed <SHA> till origin/jakob-be.
Gap 9 stängd: moodImages-bilder isoleras till data/uploads/<siteId>/__mood/
istället för public/uploads/. <Eventuellt: Vision-sammanfattning mappas till
notes_for_planner.>
<N> nya tester. Alla guards gröna.

Backend-Gap-tabellen efter denna fix:
  Stängda: <antal>
  Delvis: <antal>
  Öppen: <antal>
```

## Parallellitet

- **Måste vänta på:** Prompt 1 (Gap 6+7) — båda rör `scripts/build_site.py` `copy_operator_uploads`-flödet.
- **OK parallellt med:** Prompt 2 (B147), Prompt 3 (doc-städ). Inga gemensamma write-paths.
- **Måste klar innan:** Prompt 5 (Gap 10) — båda rör `scripts/build_site.py` + `governance/schemas/project-input.schema.json`. Sekventiellt är säkrare.
