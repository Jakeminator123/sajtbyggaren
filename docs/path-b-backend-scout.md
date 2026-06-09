---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

# Path B backend Scout (post-PR #68 + PR #70 + V1.1 + V1.2)

> **Arkivnot (lane A, 2026-06):** Historisk scout-rapport. Behålls *på plats*
> eftersom sökvägen är inbäddad i flera runtime-kommentarer
> (`scripts/check_term_coverage.py`, `packages/generation/planning/plan.py`,
> `packages/generation/build/renderers.py`). Sanningskälla för nuläget:
> `docs/current-focus.md` + `docs/handoff.md`. Se `docs/archive/README.md`.

**Scope:** Verifiering av Christophers ursprungliga Path B-plan
([`docs/scaffold-runtime-extension-needed.md`](scaffold-runtime-extension-needed.md))
från backend-perspektiv. Inga kodändringar — endast Scout-utdata.

**Branch när Scout kördes:** `jakob-be` på HEAD `1ed702b` (= `cb5c837` PR #70
mergecommit + 14 commits).

**Slutsats:** Christophers plan håller efter granskning. En **revision av
ordningen** ger lägre risk + möjlighet att stänga arbetet i fler men mindre
commits. Estimat reviderat till **~22-28h** med 9 commits istället för 7 steg.

---

## 1. TL;DR

- **Christophers plan stämmer.** `write_pages` if/elif-kedjan är fortfarande
  oförändrad (`scripts/build_site.py` rad 4658-4685) och `_RUNTIME_SCAFFOLD_HINTS`
  (`packages/generation/discovery/resolve.py` rad 670-676) saknar
  `restaurant-hospitality` (avsiktligt deferred enligt PR #68).
- **PR #68:s scope-leak landade som planerat.** `SCAFFOLD_TO_STARTER` har nu
  `restaurant-hospitality` på rad 78, `_PAGE_TO_CAPABILITY`-mismatchen är
  fixad, `_CAPABILITY_ALIASES` rad 119-124 har `faq`/`map`/`testimonials`-
  legacy. **Det Christophers plan kallar Gap 1 + 2 är redan stängda.**
- **Bara Gap 3 (write_pages section-renderer) återstår** — exakt det Path B
  handlar om.
- **Existerande registry-mönster är precedent.** `_WIZARD_ROUTE_RENDERERS`
  på rad 4701 är ALREADY en renderer-registry (per route-id) för wizard extra
  routes. Att utöka samma pattern till default-routes är en CONSISTENT
  refaktorering, inte en arkitekturändring.
- **Snapshot-test-risken är lägre än Christopher antog.** Endast 2
  test-filer (`tests/test_builder_audit_post_3b_next.py`,
  `tests/test_builder_route_emission.py`) anropar `render_home/services/about/
  contact/products` direkt. Backward-compat-shimmen Christopher föreslog
  isolerar risken till just dessa.

---

## 2. Verifierad state på jakob-be

### `scripts/build_site.py`

| Funktion / struktur | Rad | Status |
| --- | ---: | --- |
| `_hero_cta_variant` | 1913 | Oförändrad sedan PR #68 |
| `_hero_cta_label` | 1943 | Hero-CTA-helper (shop / booking / quote) |
| `_hero_cta_target_path` | 1988 | CTA-mål-resolver |
| `_pick_contact_route` | 2101 | Contact-route-picker, used by alla render_* |
| `render_home` | 2518-~2770 | Heavyweight, ~250 rader, många sektioner: hero, services-grid, USPs, story, testimonials, contact-cta |
| `render_services` | 2773-~2815 | Service-list-page |
| `render_about` | 2818-~2905 | About-page med story + team-grid |
| `render_contact` | 2910-~2955 | Contact-page med adress + kontaktinfo |
| `render_products` | 2960-~3070 | Products-grid för ecommerce-lite |
| `_HERO_STYLE_BY_VARIANT` | 3372 | Variant → hero-stil (gradient/photo/...) |
| `_WIZARD_ROUTE_RENDERERS` | 4701 | **Redan registry-monster for wizard extra routes** - precedent |
| `write_pages` | 4629-4685 | if/elif-kedjan Christopher beskrev |

### `packages/generation/discovery/resolve.py`

| Struktur | Rad | Status |
| --- | ---: | --- |
| `_PAGE_TO_CAPABILITY` | 96 | Wizard-page-label → capability, post-PR #68 |
| `_CAPABILITY_ALIASES` | 119 | Legacy-slug-mapping (faq, map, testimonials) |
| `_RUNTIME_SCAFFOLD_HINTS` | 670 | LSB + ecommerce-lite, INTE restaurant-hospitality |

### `packages/generation/planning/plan.py`

| Struktur | Rad | Status |
| --- | ---: | --- |
| `SCAFFOLD_TO_STARTER` | 64 | LSB → marketing-base, ecommerce-lite → commerce-base, **restaurant-hospitality → marketing-base** (PR #68:s scope-leak) |

### Snapshot-tester som kallar `render_*` direkt

| Fil | Funktioner som kallas | Risk för regression |
| --- | --- | --- |
| `tests/test_builder_audit_post_3b_next.py` | `render_home(dossier, dossier_routes=...)` | **Medel** — kommer brytas om hero-rendering ger annan output |
| `tests/test_builder_route_emission.py` | `write_pages(...)` end-to-end | **Hög** — hela routings-kontraktet — backward-compat-shim mitigerar |

Övriga test-filer (`test_builder_smoke`, `test_builder_brief`,
`test_builder_hardening`) går genom `build()`-funktionen, inte direkta
renderer-anrop — lägre regression-risk för dem.

---

## 3. Vad Christophers plan inte täckte

Saker backend-Builder måste tänka på som UI-Scoutens plan inte nämnde:

### 3.1 `_WIZARD_ROUTE_RENDERERS` finns redan

Pattern Christopher föreslog (`_SECTION_RENDERERS` registry) existerar redan
för wizard-extra-routes. Path B kan **återanvända samma kontrakt-design** för
default-routes utan att introducera ny terminologi.

### 3.2 `render_home` är inte en clean per-route-renderer

Den gör 5-7 saker idag (hero, services-grid, USPs, story-section,
testimonials-section, trust-signal-strip, contact-cta). Refaktoreringen
till per-sektion-renderers behöver bryta ut varje del. **Detta är största
delen av effort-estimatet.**

### 3.3 `_collect_icons_for_pages` är cross-sektion

Lucide-React-ikon-imports samlas i `render_home` baserat på alla sektioner
som råkar finnas (services-grid, USPs, story, testimonials). Efter
section-driven render måste **ikon-collection ske via en post-pass över
alla rendered sektioner**, inte inline per sektion. Det är inte trivialt.

### 3.4 Variant → hero-style behöver utökas

`_HERO_STYLE_BY_VARIANT` är en dict på rad 3372. Tre nya restaurant-variants
(`warm-bistro`, `nordic-fine-dining`, `casual-cafe`) behöver entries.
Christopher noterade detta som "valfritt" (fallback-chain täcker) men
mini-eval kommer flagga generiska gradients för restaurang-prompter.
**Rekommendera: lägg in entries i samma commit som section-renderers.**

### 3.5 `_pick_listing_route` är hårt knuten till `services` + `products`

Funktionen heter "pick listing route" och returnerar service-route för LSB
eller products-route för ecommerce. Restaurant har ingen "listing route" i
samma mening — `menu` skulle vara det närmaste. Behöver utökas att hantera
`menu`-route eller bytas mot en mer generisk helper.

### 3.6 `extra_routes` (wizard) blandar in sig

`write_pages` accepterar `extra_routes` (wizard-tillagda) som körs via
`_WIZARD_ROUTE_RENDERERS` efter default-routes. Path B-section-renderer-
registret måste **inte krocka med wizard-registret**. Antingen
- Två separata registries (`_DEFAULT_SECTION_RENDERERS` +
  `_WIZARD_ROUTE_RENDERERS`), eller
- En enad `_SECTION_RENDERERS` som wizard också konsumerar (renar
  arkitekturen men kräver wizard-route-redefinition i sections.json-stil).

**Rekommendation:** Hålla isär dem i Sprint A (mindre risk). Sammanslagning
är en valbar V2-cleanup.

---

## 4. Reviderad migration-sekvens (9 commits)

| # | Commit-titel | Diff-storlek | Snapshot-risk | Estimat |
| ---: | --- | ---: | --- | ---: |
| 1 | `refactor(builder): extract render_section_hero from render_home` | ~150-200 rader | Låg (output byte-identisk via shim) | 2-3h |
| 2 | `refactor(builder): extract render_section_services_summary + service_list` | ~120 rader | Låg | 1.5-2h |
| 3 | `refactor(builder): extract render_section_about_story + team + trust_proof` | ~150 rader | Låg | 2h |
| 4 | `refactor(builder): extract render_section_contact_info + contact_cta` | ~100 rader | Låg | 1-1.5h |
| 5 | `refactor(builder): extract render_section_product_grid + product_spotlight` | ~150 rader | Låg | 2h |
| 6 | `feat(builder): add _SECTION_RENDERERS registry + render_route_generic` | ~80 rader | **Hög** — wires up new dispatcher | 2-3h |
| 7 | `refactor(builder): convert render_home/services/about/contact/products to shims over render_route_generic` | ~60 rader | **Hög** — flips dispatcher, snapshots verifieras byte-identiska | 2-3h |
| 8 | `feat(builder): add 9 restaurant section renderers (menu, booking, hours, atmosphere)` | ~400-500 rader | Ingen (nya filer/sektioner) | 5-7h |
| 9 | `feat(builder): activate restaurant-hospitality runtime (whitelist + variant→hero-style + tests)` | ~50 rader | Låg | 1.5-2h |

**Totalt: 22-28h, 9 commits.** Christophers ursprungliga estimat (20-26h)
underskattade lite men inte mycket.

### Kritiska guards per commit

Varje commit ska köra:
- `python -m ruff check scripts/build_site.py`
- `python -m pytest tests/test_builder_route_emission.py tests/test_builder_audit_post_3b_next.py -q`
- För commits 1-5: **byte-diff snapshot-check** av output (build LSB +
  ecommerce-fixtures, jämför med pre-refaktor-output)

För commit 6-7 (dispatcher swap): **byte-identisk LSB-output** är acceptans.
För commit 8-9: **nya restaurant-fixture (`examples/restaurant-bistro.project-input.json`)
emitterar `/`, `/meny`, `/bokning`, `/om-oss`, `/kontakt` utan SystemExit**.

---

## 5. Risk-register

| Risk | Sannolikhet | Impact | Mitigation |
| --- | --- | ---: | --- |
| Byte-diff på LSB-snapshot efter dispatcher swap (commit 7) | Medel | Hög | Whitespace-normalize-helper innan commit; om byte-diff: dokumentera exakt char-diff och sign off |
| `_collect_icons_for_pages` ger fel ikon-set efter section-extraction | Hög | Medel | Implementera ikon-collection som post-pass över rendered sections; lock med ny test som verifierar att Quote-glyph dyker upp närhälst story/testimonials renderas |
| `extra_routes`-mekanismen kraschar när två register försöker hantera samma id | Låg | Hög | Validera vid module-load: `set(_SECTION_RENDERERS) & set(_WIZARD_ROUTE_RENDERERS) == set()` med tydlig felmeddelande |
| Restaurant-fixture aldrig genererad → commit 9 kan inte verifieras | Medel | Medel | Operatör eller Scout skapar `examples/restaurant-bistro.project-input.json` parallellt med commit 1 så den finns innan commit 9 |
| `render_home`-shim ger annan ordning på sections än sections.json deklarerar | Medel | Hög | Sections.json `requiredSections`-listan är källan; shim ska iterera den ordningen ENDAST, inte original render_home-ordningen |
| Real codegen-model på `marketing-base` förväntar specifik output-shape som ändras | Låg | Hög | Real codegen är scope för `marketing-base` (LSB) — om LSB-output är byte-identisk är realmodell oförändrad |

---

## 6. Föreslagen Builder-prompt (för senare session)

En framtida Builder-agent som ska genomföra Path B kan få denna prompt:

```text
Du är Builder-agent för Sajtbyggaren på Windows. Workspace:
C:\Users\jakem\Desktop\sajtbyggaren. Branch: jakob-be (synked mot main först).
Aktivera venv: & .venv\Scripts\Activate.ps1.

Uppgift: Implementera Path B (section-driven renderer) enligt
docs/path-b-backend-scout.md sekvensen (9 commits). Läs hela Scout-doc:en
först.

Scope ENDAST:
- scripts/build_site.py (huvudfil)
- tests/test_builder_route_emission.py (utöka med restaurant)
- tests/test_builder_audit_post_3b_next.py (verify shim-kompatibilitet)
- tests/test_builder_sections_dispatch.py (NY testfil)
- packages/generation/discovery/resolve.py (BARA _RUNTIME_SCAFFOLD_HINTS i sista commit)
- examples/restaurant-bistro.project-input.json (NY fixture)
- governance/decisions/0030-path-b-section-renderers.md (NY ADR)

Off-limits: apps/viewser/**, packages/generation/planning/, packages/generation/build/,
governance/policies/, data/starters/, övriga docs.

Flow: en commit per migrationssteg (9 totalt), guards mellan, ingen amend.
Push till jakob-be efter commit 9. Operatören beslutar PR till main.

Stoppregler: stoppa och rapportera om:
- LSB byte-diff efter dispatcher-swap inte är 0 efter whitespace-normalize
- Snapshot-test fails på trivial extraction (commit 1-5) — duger sannolikt en
  helper, men bör flaggas
- Restaurant-fixture emitterar fel route-set
```

---

## 7. Öppna frågor för operatör innan Builder spawnar

1. **Restaurant-fixture (`examples/restaurant-bistro.project-input.json`)** —
   kan skapas av Scout/operatör innan Builder börjar, eller låter vi Builder
   improvisera en. Christophers förslag var realistisk bistro med
   3-course-menu + öppettider. Min rekommendation: **operatör skissar i
   ~10 min innan Builder spawnas** — det undviker att Builder gissar
   småföretagardomän.

2. **Sequential eller parallell uppdelning?** 9 commits i en single Builder-
   session (22-28h) är för långt för en agent-kontextfönster. Förslag:
   **3 Builder-sessions:**
   - Session 1: commits 1-5 (refaktorering av befintliga renderers, ~9h)
   - Session 2: commits 6-7 (dispatcher swap, ~5h)
   - Session 3: commits 8-9 (restaurant + activation, ~7-9h)
   
   Mellan sessioner: Steward-pass + operator-review.

3. **Real-codegen-model på marketing-base** — Path B ska INTE påverka
   `_REAL_CODEGEN_STARTERS = {"marketing-base"}` (ADR 0017). Bekräfta att
   LSB-output är byte-identisk innan commit 7 mergeas till main.

4. **ADR-nummer** — `0030-path-b-section-renderers.md` är nästa lediga. OK
   med det numret?

5. **Backward-compat-shim livslängd** — när alla LSB/ecommerce-snapshot-tester
   är byte-identiska, kan `render_home`/`render_services`/etc. shimmas
   bort i V3 eller behållas som API-yta? Mitt råd: behåll som API-yta — de
   är trots allt en gångbar way att rendra en route från andra moduler om
   det behövs (t.ex. Quality Gate).

---

## 8. Vad Scout INTE undersökte

- **Quality Gate-impact:** route-scan-checken kollar bara att route-paths
  finns på disk. Section-shift påverkar inte den. Men typecheck-checken
  kan reagera på ändrade `dossier`-shapes om någon section-renderer
  introducerar nya field-access. Behöver verifieras i commit 8.
- **Real LLM-prompter via briefModel/planningModel:** dessa producerar
  `selectedDossiers`-listor utan att veta om sections.json. Path B
  påverkar inte deras kontrakt. Lågrisk.
- **Builder MVP CLI:n (`scripts/build_site.py --skip-build`):** den anropar
  `write_pages` direkt — om Path B håller `write_pages`-signaturen
  oförändrad (vilket är planen) påverkas inte CLI:n.

---

## 9. Sammanfattning för operatör

Christophers plan är solid. Path B är **fortfarande nästa stora backend-spår**
och har inte blivit billigare eller dyrare efter PR #68/#70-spåren. Nio
commits över **2-3 dedikerade Builder-sessioner** är realistiskt. Operatör
bör besluta om:

- Restaurant-fixture-skissen (10 min, inför session 1)
- Session-uppdelning (parallell efter session 1 om byte-stabilitet
  konfirmeras)
- ADR-nummer (0030 föreslås)

Tills dess: **inget att göra på Path B från Sprintvakt-perspektiv.** Gapet
`GAP-path-b-section-renderers` (Gap/Runtime, yellow) kan skapas i
`docs/workboard.json::queuedGaps` när operatören vill formellt schemalägga.

— Scout, 2026-05-25 (jakob-be HEAD `1ed702b`)
