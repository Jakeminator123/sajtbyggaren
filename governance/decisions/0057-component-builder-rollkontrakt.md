# ADR 0057 — component_builder-rollkontrakt (äger component_add)

**Status:** Accepted
**Datum:** 2026-06-12
**Beroenden:** ADR 0040 (Component Catalog), ADR 0054 (kurerat komponentintag),
F1-rollkontrakten (`router`/`section_builder`/`stylist`/`copy` i
[`packages/generation/orchestration/openclaw/roles.py`](../../packages/generation/orchestration/openclaw/roles.py)).
Berörda filer:
[`roles.py`](../../packages/generation/orchestration/openclaw/roles.py),
[`docs/openclaw-workspace/action-registry.json`](../../docs/openclaw-workspace/action-registry.json),
[`docs/openclaw-workspace/TOOLS.md`](../../docs/openclaw-workspace/TOOLS.md),
[`docs/openclaw-workspace/skills/component-add/SKILL.md`](../../docs/openclaw-workspace/skills/component-add/SKILL.md),
korsvaliderade av
[`tests/test_openclaw_registry_consistency.py`](../../tests/test_openclaw_registry_consistency.py).

## Numrering (notis)

0055 (hostad-preview-standardisering) och 0056 (dossier-dependencies) är tagna i
basen. 0054 reserverades för intags-grinden (denna serie) och används av den.
Rollkontraktet får därför 0057.

## Kontext

`component_add` finns i routerns `EditKind`-enum men var **herrelöst** i
`_ROLE_BY_EDIT_KIND` — ingen konduktör-roll ägde det. `role_for_edit_kind(
"component_add")` och `skill_for_edit_kind("component_add")` returnerade `None`,
och en component_add-följdprompt rapporterades ärligt som ej-applicerad via
`unapplied.py` utan en namngiven ägare. ADR 0040 gav komponentmedvetenheten
(Component Catalog) och ADR 0054 gav intagsvägen; nu behöver `component_add` en
ärlig ägare som binder ihop dem.

## Beslut

### 1. Ny RoleContract `component_builder`

Läggs till i `ROLE_CONTRACTS`:

- `acceptsEditKinds = ("component_add",)`,
- `producesDirectives = ("component_add",)`,
- `contextLevel = "component_registry"` (nivån finns redan, 12k-budget),
- `status = "partial"`,
- `mountOnly = True`,
- `skill = "skills/component-add/SKILL.md"`,
- `visibleTypes = ()`.

`_ROLE_BY_EDIT_KIND` får `"component_add": "component_builder"` (fyller den
herrelösa mappningen). Typ-literalerna för roll-id och directive-kind utökas
med component_builder respektive component_add.

### 2. Kedjebeteende i denna slice (partial, mount-only)

En `component_add`-följdprompt ger ett **katalog-grundat svar** (vilka
komponenter som finns vendorerade enligt capability-map `components` + per-Starter
`component-manifest.json`) ELLER en **ärlig no-op** som pekar på det kurerade
intaget (`scripts/component_intake.py`, ADR 0054). Den **monterar inget och
skriver inga filer** — den befintliga kedjan rapporterar no-op:en via
`unappliedFollowupIntents` (ingen påhittad effekt). Att vendorera in en ny
komponent förblir en operatörs-PR (intag → granskning → Starter), aldrig en
runtime-montering. En generell mount-väg för component_add är en senare slice med
egen ADR.

### 3. Spegling + korsvalidering

Action `component_add` läggs i `action-registry.json` (`status: partial`,
`mountOnly: true`, samma skill), en sanktionsrad i `TOOLS.md`, och en ny
`skills/component-add/SKILL.md`. `tests/test_openclaw_registry_consistency.py`
korsvaliderar att registret och rollkontraktet är överens om skill/status/
mountOnly/visibleTypes och att varje producerad directive mappar till exakt en
action.

### 4. Termer registreras (ADR 0006)

`componentBuilder` (canonical "Component Builder") och `componentCandidate`
(canonical "Component Candidate") registreras i `naming-dictionary.v1.json`.

## Avsiktlig baseline-uppdatering (notis)

Att lägga till en femte roll är en **legitim semantisk ändring**, inte
test-fusk: `tests/test_openclaw_roles.py` och
`tests/test_eval_baseline_conductor.py` uppdaterades AVSIKTLIGT (4 → 5 roller,
`component_add` → `component_builder`). En genuint herrelös edit-kind (t.ex.
`component_remove`) behåller `role=None` så den ärliga ytan kvarstår.

## Vad ADR 0057 INTE beslutar

- Ingen mount/skriv-väg för component_add (fortsatt partial/mount-only).
- Ingen ändring av router-enumet `EditKind` (åtta kinds, oförändrat) eller
  router-decision-schemat.
- Ingen viewser-etikett för `component_builder` (apps/viewser ägs av annat pass;
  noteras i PR:en).

## Verifiering

- `tests/test_openclaw_roles.py`, `tests/test_eval_baseline_conductor.py`,
  `tests/test_openclaw_registry_consistency.py` — gröna med femte rollen.
- `python scripts/governance_validate.py`, `rules_sync --check`,
  `check_term_coverage --strict`, `ruff check .` — gröna.
