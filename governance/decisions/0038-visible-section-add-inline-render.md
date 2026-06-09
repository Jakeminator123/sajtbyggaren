# ADR 0038 — synlig section_add-render som additiv directive (`directives.mountedSections`)

**Status:** Accepted
**Datum:** 2026-06-09
**Beroenden:** ADR 0027 (semantic follow-up merge — additiv directive-precedent),
ADR 0032 (section-treatments som additiv directive), ADR 0034 (follow-up prompt
content passthrough), ADR 0036 (blueprint-/router-vokabulär). Referens:
[`docs/refactor/megafiles-plan.md`](../../docs/refactor/megafiles-plan.md)
(grind: synlig section_add), [`docs/gaps/GAP-followup-prompt-content-passthrough.md`](../../docs/gaps/GAP-followup-prompt-content-passthrough.md).

## Kontext

En `section_add`-följdprompt ("lägg till en sektion om garantier", "lägg en
FAQ-sektion överst på startsidan") klassas av routern (`editKind=section_add`,
`packages/generation/orchestration/router/classify.py`) och monteras av apply
(`packages/generation/orchestration/apply/apply.py`) som
`requestedCapabilities` + `selectedDossiers.required` på nästa versions Project
Input. Idag är resultatet **mount-only för 7 av 9 sanktionerade typer**:
`requestedCapabilities` läses aldrig vid render-tid, `render_home` har en
hårdkodad sektionsordning, och routerns positionsmål (`RouterTarget`)
konsumeras aldrig. Enda synliga vägen är `faq`/`team` på
`local-service-business`, som surfas som en **egen route** (`/faq`, `/team`) via
`meta.wizardMustHave` — inte som ett block i en befintlig sida.

Effekten: `applied=true` men `appliedVisibleEffect=false` — användaren får en ny
version utan synlig skillnad. Det bryter mot kärnflödets förtroende
(`prompt -> företagshemsida -> preview -> följdprompt -> ny version`).

`appliedVisibleEffect` mäts som en byte-diff av `app/**`+`public/**`-snapshots
mellan versioner (`scripts/build_site.py:_detect_followup_applied_visible_effect`),
så en sektion blir "synlig" först när den faktiskt skriver TSX-bytes.

## Beslut

Inför ett additivt directive-fält `directives.mountedSections[]` på Project
Input som säger att en monterad sektion ska renderas **inline** som ett block på
en befintlig route, vid en valfri position. Varje post är
`{sectionId, routeId, capability?, position?, ordinal?}`. Renderaren läser
fältet direkt ur Project Input (samma `dossier`-argument renderarna redan får)
och injicerar sektionen i route-ordningen.

Lokationsval (samma resonemang som ADR 0032):

- **Valt — additivt directive under `directives.mountedSections`.** Samma
  precedent som `directives.layoutHint` / `directives.sectionTreatments` /
  `directives.copyDirectives`. Renderaren får redan hela Project Input som
  `dossier`, så ingen ny plumbing genom `build()` / `write_pages` /
  `_rerender_after_repair`-closuren behövs (storleksvakten i
  `tests/test_build_site_size.py` rörs inte). Listan ersätts per version.
- Avvisat — meta-only (som `wizardMustHave`): meta är per-version-provenance och
  surfar bara dedikerade routes, inte inline-block; renderaren läser inte meta.
- Avvisat — nytt top-level-fält: mest invasivt mot befintliga PI-konsumenter.

## Ärlighetsgrindar (gate, render-tid)

En post injiceras ENDAST när alla grindar passerar — annars förblir sektionen
ärligt mount-only (rapporteras med skäl):

- (a) `sectionId` har en registrerad `render_section_*` i `_SECTION_RENDERERS`
  (`packages/generation/build/dispatcher.py`). Ett okänt id droppas tyst — aldrig
  ett `SystemExit`, aldrig en påhittad sektion.
- (b) sektionen finns inte redan i routens ordning (ingen dubblett).
- (c) grundat innehåll finns (sektionsrenderaren returnerar inte tom sträng) —
  en monterad sektion utan content syns aldrig (mounted-but-no-content).
- (d) scaffold stöds (slice 1: `local-service-business`).

## Konsekvenser

- Rå följdprompt renderas aldrig okontrollerat som kundcopy; `sectionId`/`routeId`
  är slutna referenser till befintliga sektioner och routes.
- `appliedVisibleEffect` blir ärligt `true` när en grundad sektion injiceras (ny
  byte i `app/page.tsx`), och fortsatt `false` när en grind faller.
- Beteendebevarande: utan `mountedSections` är render-utdata byte-identisk med
  idag (låst av `tests/test_home_section_inject.py` golden).
- Schema-bumpen är additiv och bryter inga befintliga PI-snapshots; `directives`
  förblir giltigt när fältet saknas.
- Canonical term registrerad i `naming-dictionary.v1.json` (v27): Mounted Section.

## Utanför scope (kommande slices)

- Finkornig positions-/ordinal-placering ("efter tjänster", ordinal-index)
  (slice 2; `position` stödjer top/bottom/before-contact i slice 1).
- Fler routes än `home` (slice 3) och fler scaffolds/typer (slice 4).
- Väg B (ärlig FloatingChat-feedback, UI) och väg C (filpatch i `.generated/`)
  per ADR 0034 — oförändrat parkerade.
