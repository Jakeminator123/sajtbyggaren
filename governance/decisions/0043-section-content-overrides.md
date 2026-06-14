# ADR 0043 — ändringsbar sektionstext via följdprompt (`directives.sectionContentOverrides`)

**Status:** Accepted
**Datum:** 2026-06-10
**Beroenden:** ADR 0027 (semantic follow-up merge — additiv directive-precedent),
ADR 0032 (section-treatments som additiv directive), ADR 0034 (follow-up prompt
content passthrough — `directives.copyDirectives`), ADR 0036 (blueprint-/router-
vokabulär), ADR 0038 (synlig section_add-render — `directives.mountedSections`).
Referens: [`docs/gaps/GAP-followup-prompt-content-passthrough.md`](../../docs/gaps/GAP-followup-prompt-content-passthrough.md)
(B155-resten: "funktionen som faktiskt utför den är inte inkopplad än").

## Kontext

En copy-följdprompt mot en specifik sektion ("ändra texten i hero-sektionen till
X", "gör om texten i om-oss-sektionen så den nämner Y") klassas av routern
(`editKind=copy_change`) och patch-planeraren
(`packages/generation/orchestration/patch/`) föreslår redan ett korrekt mål på
formen `contentBlocks.<routeId>.<sectionId>.<field>`. Men apply-steget
(`packages/generation/orchestration/apply/`) fick bara skriva sanktionerade
Project Input-fält (`requestedCapabilities`, `selectedDossiers.required`,
`directives.mountedSections`, brand/tone). En `copy_change` mappade därför mot
ingenting och blev en ärlig `unmapped`-no-op — `applied=false`, ingen ny version,
previewen stod kvar. Det bröt kärnflödets förtroende
(`prompt -> företagshemsida -> preview -> följdprompt -> ny version`).

`copyDirectives` (ADR 0034) täcker bara de fyra globala copy-fälten
(company-name / tagline / about-text / services) och den enda sektionsöverstyrning
som fanns var hero-H1 via `company.heroHeadline`-pinnen (B173). Det fanns ingen
generell, sanktionerad väg från ett `contentBlocks`-sektionmål till synlig text.

`appliedVisibleEffect` mäts som en byte-diff av `app/**`+`public/**`-snapshots
mellan versioner (`scripts/build_site.py:_detect_followup_applied_visible_effect`),
så en sektion blir "synlig" först när den faktiskt skriver TSX-bytes.

## Beslut

Inför ett additivt valfritt Project Input-fält
`directives.sectionContentOverrides`: en map där nyckeln är ett sektionsmål
`"<routeId>.<sectionId>.<field>"` (field = `headline` | `subheadline` | `body`)
och värdet är den nya, redan validerade texten.

1. **Schema (additiv bump).** `project-input.schema.json` får fältet under
   `directives`, slutet via `patternProperties` + `additionalProperties: false`
   så bara de tre vitlistade textfälten accepteras (typos failar validering).
   `maxLength` 600 i schemat; koden cappar snävare per fält (headline/subheadline
   200, body 600). Fältet är optional — saknad map bryter inga befintliga
   PI-snapshots.

2. **Apply (KÖR-7c).** Apply mappar patch-planerarens `contentBlocks`-mål hit i
   nästa immutabla version — **aldrig fri filpatch, bara de vitlistade
   textfälten**. Den nya copyn härleds deterministiskt ur följdprompten (samma
   public-copy-guards som `copyDirectives` via
   `packages/generation/followup/copy_directives._safe_copy_payload`):
   `headline`/`subheadline` tar ett explicit replace-värde (`... till "X"`,
   citat, kolon); `body` tar ett explicit replace-värde eller en
   `...så den nämner X`-markör som **lägger till** X i den befintliga texten. Ett
   vitlistat mål vars copy inte kan härledas förblir en ärlig no-op (planeraren
   uppfinner aldrig copy). Mål utanför vitlistan (inline-komponent, okänt fält)
   förblir `unmapped` precis som idag.

3. **Renderern.** En override vinner över blueprint-copyn (samma mönster som
   `company.heroHeadline`-pinnen) i hero (headline/subheadline), home-story
   (body) och about-story (headline/body). Utan override är render-utdata
   byte-identisk med idag (fältet är optional och matchas på adress-suffix
   `.<sectionId>.<field>`, deterministiskt; >1 träff = ingen override).

4. **Ärligheten.** När en override faktiskt skrivs ändras TSX-bytes, så
   `appliedVisibleEffect=true` blir ÄKTA via den befintliga fil-diffen. ROW-3-
   guarden behöver ingen ändring — pilotprompterna bär ingen demonstrativ
   citat-replace-signal — men `_has_copy_directives` räknar nu även
   `sectionContentOverrides` som en applicerad copy-ändring så en override-driven
   diff aldrig felrapporteras som `copy_directive_not_applied`.

5. **Carry-forward.** Mappen lever i Project Input och bärs vidare av
   `merge_followup_project_input`s deep-copy, så den överlever brief-reuse (B180)
   och hero-pinnen (B173). En senare följdprompt lägger bara till/uppdaterar sina
   egna nycklar; ingen tidigare sektionsändring nollas.

Lokationsval (samma resonemang som ADR 0032 / 0038):

- **Valt — additivt directive under `directives.sectionContentOverrides`.**
  Samma precedent som `directives.copyDirectives` / `mountedSections`. Renderaren
  får redan hela Project Input som `dossier`, så ingen ny plumbing genom
  `build()` / `write_pages` behövs.
- Avvisat — fri filpatch i `.generated/` (ADR 0034 väg C, fortsatt parkerad):
  bryter immutabiliteten och codegen-kontraktet.
- Avvisat — utöka `copyDirectives` med sektionsmål: dess targets är globala
  copy-fält, inte adresserade sektioner.

## Konsekvenser

- Rå följdprompt renderas aldrig okontrollerat som kundcopy; varje värde går
  genom samma guards som `copyDirectives`, och `sectionId`/`routeId`/`field` är
  slutna referenser.
- Beteendebevarande: utan `sectionContentOverrides` är render-utdata
  byte-identisk med idag (låst av befintliga renderer-golden + nya tester).
- Schema-bumpen är additiv och bryter inga befintliga PI-snapshots.
- Canonical term registrerad i `naming-dictionary.v1.json` (v31): Section Content
  Override.

## Utanför scope (kommande slices, registrerade i `docs/known-issues.md`)

- Generativ omskrivning utan explicit värde ("gör om texten så den låter mer
  premium" utan citat) kräver copyModel — den deterministiska vägen förblir en
  ärlig no-op tills copyModel-passet kopplas in i apply.
- Compound-prompter ("gör den coolare och lägg till ett skämt") rapporterar ännu
  inte otillämpade delar via `unappliedFollowupIntents` på apply-vägen.
- Fler sektioner/routes än hero + story/about-story och fler scaffolds.

## Tillägg 2026-06-14 (#318) — citerad om-oss-text landar och förblir synlig

Operatörsfynd (`olkultur-ab-e9594d`): en följdprompt som citerade den RENDERADE
om-oss-/story-texten landade inte och chatten antydde ändå framgång. Två
medvetna beslut, på den **prompt-drivna** följdprompt-vägen
(`scripts/prompt_to_project_input.py:merge_followup_project_input`), inte bara
apply-/patch-vägen ovan:

1. **Story-pin på copy-vägen.** När `_apply_copy_directives` applicerar ett
   `about-text`-direktiv (`company.story`) pinnas samma text nu även till
   `directives.sectionContentOverrides` för båda story-ytorna
   (`home.story.body` + `about.about-story.body`) — exakt mönstret denna ADR
   redan etablerade för apply-vägen, och en spegling av
   `company.heroHeadline`-pinnen. Skälet är samma render-skuggning som punkt 3
   ovan: `derive_story(brief)` (planning-blueprinten) regenereras varje bygge
   och skuggar `company.story` vid render (`apply_blueprint_to_dossier`), så en
   ren `company.story`-ändring syns inte. Override:n vinner och överlever
   ombygget.

2. **Utökad matchkälla.** `_extract_literal_replace_directives` matchar nu OLD
   även mot den FÖREGÅENDE byggets renderade/härledda story
   (`previous_rendered_story`, läst ur run-direns `generation-package.json`
   `contentBlocks` via `run_blueprint_story`, samma facit som
   `RenderBlueprint.story()`), inte bara den lagrade `company.story`. Operatören
   citerar det hen SER — vilket är den härledda storyn, inte det lagrade fältet
   — så utan detta fanns ingen träff. En träff blir ett `about-text`-direktiv
   som punkt 1 pinnar.

Ärlighet (kompletterar punkt 4 ovan): en citerad copy-replace vars OLD inte
matchar någon redigerbar copy (varken lagrad eller renderad) ger en ärlig
`unappliedFollowupIntents`-post (`target: copy-replace`), och både den posten
och `_followup_requested_copy_replace`-grinden nycklar på det citerade
OLD/NEW-paret i stället för verb-nyckelordet — så #313-kontraktet håller även
när chatt→CLI-gränsen manglar ett inledande "Ä" till "*" (encoding-roten
B204, bokförd separat, EJ blind-fixad här).
