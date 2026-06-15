# Known issues + audit-derived bug log

> **Aktivt bug-scope:** 19 aktiva, 0 misplaced (av 24 öppna), 5 unknown, 15 stängda (kvar i filen; 159 äldre arkiverade i docs/archive/known-issues-closed-2026-06-15.md). Kör `python scripts/list_open_bugs.py` för full lista. Format-disciplin: se governance/rules/12-bug-and-pr-review.md.

Den här filen är vår **kanoniska bugg-/aning-lista**. Varje gång en bugg
hittas i en audit eller via en operatör läggs den in här med ett ID och en
tillhörande regressionstest. Innan ett ID stryks från listan måste testet
passera och en commit-referens länkas under "Fix".

Format per bugg:

> `<ID> - <Allvar>` - kort beskrivning. Källa: audit-rapport eller person.
> Fix: commit-sha eller "open". Test: filnamn::testnamn.

## Allvarsskala

- **Hög**: säkerhetshål, datakorruption, race conditions som kan korrumpera
  state.
- **Medel**: kontraktsbrott, namnskugga, dålig observability, men ingen
  korruption.
- **Låg**: kosmetiska, dokumentations-eftersläpningar, framtidsrisk.

## Öppna - inte fixade än

### Demo-baseline gap från verifierings-Scout 2026-05-15 (efter 1A)

Verifierings-Scout körde fyra skarpa prompts (`elektriker Malmö`,
`frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som
säljer keramik`) via `prompt_to_project_input.py` + `build_site.py`
och scorade totalsnitt 6.2 / 10. Tre fynd hamnade i 1A-hotfixen
(B61/B62/B63, stängda). Fyra ytterligare gap kvarstår som öppna
produkt-buggar:

- **`B67` Låg** - `scripts/build_site.py` hårdkodar `lang="sv"` på
  rad 786 och svensk UI-copy ("Begär offert", "Hör av dig idag",
  "Kontakta oss", "Se alla tjänster", "Spela direkt", "Beskriv kort
  vad du behöver så återkommer vi inom en arbetsdag.") på rad 605,
  799, 881, 908, 939-941, 982, 1054, 1132. README + brief stöder
  `language="en"` men renderer ignorerar det. Engelska sajter får
  svensk UI. Källa: verifierings-Scout 2026-05-15. Fix: i18n-
  arkitektur - parameterisera renderer-strings per language. Egen
  sprint, inte i 1B-scope. Fix: open. Test: open.

### Bug-sweep 2026-05-15 (tre parallella subagents efter 1A-hotfix)

Tre read-only subagents granskade (1) brief + prompt-helper pipeline,
(2) builder renderers + scaffolds + Quality Gate, (3) Viewser app +
run/follow-up-flöde. 21 fynd, sorterade på `Probability × Impact`:

- **`B86` Låg** - `scripts/build_site.py:1387-1388` hårdkodar
  `NPM_INSTALL_TIMEOUT_SECONDS = 600` och `NPM_BUILD_TIMEOUT_SECONDS
  = 300`. Långsamma Cloud Agent VMs överskrider regelbundet, ger
  flaky failures orelaterade till site-correctness. Källa: builder-
  renderer-bug-sweep 2026-05-15. Fix: CLI-flagga eller env-knapp.
  Fix: open. Test: open.

### Extern reviewer-triage 2026-05-15 (mot `d99f8ba` + `c273b1a`)

- **`B89` Medel** - `packages/generation/brief/extract.py:detect_language`
  defaultar till `sv` för korta engelska prompts utan träff i
  `ENGLISH_HINTS` (t.ex. `plumber stockholm`, `barber malmo`,
  `ceramic studio`). Kategoriöverlapp med B62 men annan edge-yta. Källa:
  extern reviewer + RO-verifierings-subagent 2026-05-15. Fix: open.
  Test: open.

### Re-Verifierings-Scout 2026-05-15 (post-Grind PR #28 mot `d0ded58`)

Re-Verifierings-Scout körde fyra demo-prompter mot fixad kod efter
Grind PR #28-mergen och rapporterade totalsnitt **5.54/10** (case-spann
3.9-6.25). Alla fyra builds var `status=ok`/`quality=ok`. Scout
flaggar själv att hen sannolikt är 0.3-0.5p strikare än Scout 1's
6.2-baseline, så jämförelsen mot baseline är osäker; det Scout är
säker på är att språk-/H1-buggar är borta och kvarvarande svagheter
är dev-jargong, generisk copy och scaffold-mismatch för e-handel.
Top kvarvarande demo-blockers: **B88** (kontakt-placeholder dev-
jargong synligt på alla fyra case), generisk service-copy ("X -
kontakta oss för mer information." återanvänds överallt), och hero-
CTA "Begär offert" hardcoded i `render_home` oavsett bransch
(bryter särskilt e-handel-trovärdighet). Audit-konfidence 7/10.

**Historisk B71-not:** Re-Verifierings-Scout kunde före Project DNA-
fixen inte verifiera follow-up-byte-stabilitet i ett första-
generationspass. B71 stängs först i Project DNA semantic follow-up
V1 nedan, där v1 → v2-tester låser både semantiska ändringar och
byte-stabila no-change-fall.

### Re-Verifierings-Scout 3 2026-05-18 (post-1C mot `b5ee710`/`6eaf222`)

Tredje pass-Scout körde samma fyra demo-prompter mot 1C-fixad kod
(`b5ee710`) efter Steward-bump (`6eaf222`). Totalsnitt **5.13/10 (rå) /
~5.9/10 (kalibrerat mot Scout-2-skalan)**, case-spann 4.88-5.75. Alla
fyra builds `status=ok`/`quality=ok`/`briefSource=real`. Verdict: 1C
lyfte snittet (mest case 4 där B95+B96 aktiveras), men under 7/10-
tröskeln och minst ett case under 6.5. Rekommendation: bug-sweep
round 2 / riktad fix innan Project DNA / semantic follow-up merge.
B88/B94/B95/B96 mekaniskt verifierade som stängda; B96 stängd men
levereras inte i case 2 + 3 eftersom briefModel returnerar
`conversionGoals=[]` för korta prompter (booking-bransch faller
tillbaka till quote-default). Audit-konfidence 7/10.

B101 + B102 stängda 2026-05-19 (keramik-/e-handel-pass, fix `d1fee90`);
se Stängda-sektionen längre ner.

### Extern reviewer-triage 2026-05-18 (mot post-1E/B108-baseline)

Reviewer-pass mot de fem senaste pusharna till `main` (`9f8bb2f`,
`bc43eb8`, `0fc9243`, `01c0cfb`, `6e0c82e`). Tre fynd, två öppna +
ett stängt (B112) i samma pass.

- **`B110` Låg-Medel** - `scripts/build_site.py:_normalize_business_type`
  (1E-fixen för B107) normaliserar `naprapath`/`naprapatklinik`/
  `webshop`-varianter till en kanonisk slug, men bara i CTA-flödet
  (`_hero_cta_variant`/`_hero_cta_label`). Mapparna i
  `scripts/prompt_to_project_input.py` (`_BUSINESS_TYPE_LABEL_SV`,
  `_TAGLINE_BY_BUSINESS_TYPE_SV`, `_SERVICE_LABEL_BY_BUSINESS_TYPE_SV`,
  `_SERVICE_SUMMARY_BY_BUSINESS_TYPE_SV` plus motsvarande `_EN`-mappar)
  nycklar direkt på rå briefModel-output. SV-mapparna är delvis
  redundant (har t.ex. `naprapath-clinic` + `naprapat-clinic` +
  `naprapatklinik`) men luckor finns ändå: `webshop`/`webbshop` saknas
  i tagline/service-label/service-summary-mapparna, så en briefModel-
  output som CTA-flödet normaliserar till `e-commerce` kan ändå ge
  generisk fallback i tagline/service-summary. EN-mapparna saknar
  `naprapatklinik` (svensk form). Effekten är inkonsekvent
  copy-kvalitet snarare än krash, men "split sanning" gör att samma
  input rendrar olika i olika rendering-steg. Riktig fix: flytta
  `_normalize_business_type` till en delad helper och kör alla
  business-type-lookups genom den. Kopplar mot B13a (arkitektur-flytt
  av `scripts/build_site.py` till `packages/`). Källa: extern reviewer
  2026-05-18. Fix: open. Test: open.
- **`B111` Låg** - `scripts/generate_variant_candidate.py:512-533`
  fångar alla `Exception` från `_call_variant_model` och faller
  tillbaka till `_mock_variant_candidate` med `source="mock-llm-error"`
  + stderr-print, sen returnerar `exit 0`. Det är inte tyst (operatör
  som kollar artefakten ser `source`, och stderr loggas), men för
  CI/automation som inte läser stderr kan en mock-fallback se ut som
  en lyckad real-modelloutput i exit-code. Design-fråga snarare än
  bugg: nuvarande beteende är medvetet "fortsätt även när modellen
  fallerar" för operatörsergonomi. Lågprio enhancement: lägg
  `--fail-on-llm-error` (eller `--strict`)-flagga som ger
  `exit != 0` när real-modellanrop failar, så CI kan skilja faktisk
  modellverifiering från mock-fallback. Källa: extern reviewer
  2026-05-18. Fix: open. Test: open.

### Extern reviewer-triage 2026-05-18 (post-PR-#31 christopher-ui-integration, runda 2)

Andra reviewer-passet mot post-PR-#31-baseline. Sex nya fynd:
B117 (SVG-XSS) och B118 (scrape-runner SIGKILL) stängda i samma
pass; B119-B122 öppna och listade nedan.

- **`B119` Låg** - `scripts/scrape_site.py:deterministic_fields`
  (rad 417-425) väljer kontaktuppgift via
  `next(iter(sorted(corpus.emails)))` — alfabetisk sortering, första
  träffen vinner. En sajt med både `info@foo.se` (huvudkontakt) och
  `aaa-removeme@foo.se` (gammal placeholder) skulle ge `aaa-removeme@`
  som vinnande email i discovery-payloaden. Samma mönster för phones
  och addresses. Ingen koppling till semantisk relevans (är emailen i
  header? footer? kontakt-sida?). Effekten är "plausibel men fel"
  kontaktinfo i Project Input, vilket är svårare att upptäcka än
  uppenbara fel. Fix-skiss: poängsätt kandidater på var i sajten de
  ses (mailto-länk i header > footer > body, `kontakt`/`contact`-sida
  > start), och välj högsta poäng. Källa: extern reviewer 2026-05-18
  (runda 2). Fix: open. Test: open.
- **`B120` Låg** - stad-extraktion ur kontakt-`addressLines` i
  `packages/generation/discovery/resolve.py` (`_apply_location_from_address` +
  `_SWEDISH_POSTCODE_RE`; B121 flyttade logiken hit från
  `prompt_to_project_input.py`). Effekten var tyst fallback till brief-extracted
  location, dvs halvfel platsdata utan signalering. Källa: extern reviewer
  2026-05-18 (runda 2).
  Delvis åtgärdad 2026-06-01 (`a90215e`): regexen läser nu ALLA adressrader
  (inte bara `addressLines[0]`, så `["Storgatan 5", "116 46 Stockholm"]` ger
  rätt stad) och tillåter flerordiga orter ("Västra Frölunda"); komma-separator
  och 5-siffrigt postnummer utan mellanslag matchar redan via `search()`.
  Regression: `tests/test_discovery_resolver.py::test_location_from_address_extracts_city`.
  Kvarstår (håller B120 öppen): internationella/engelska postnummerformat och
  "stad före postnummer" (US `City, ST 10001`) hanteras fortfarande inte —
  medvetet konservativt så fel utländsk stad aldrig sätts (säker fallback).
  Fix: open. Test: open.
<!-- B122 stängd 2026-05-27 (SHA `7b6fb6c`) — se Stängda-sektionen. -->


### Extern reviewer-triage 2026-05-18 (post-PR-#31 christopher-ui-integration)

Första reviewer-passet mot mainline efter att PR #31 (`feat(viewser):
integrate christopher-ui discovery and asset workflow`, merge
`3f4543d`, integration `0510146`) landade. Fyra fynd, två stängda
(B113, B114) + två öppna i samma pass.

- **`B115` Låg** - `SM_hero.mp4` (1.5 MB) och `LOGO_SM2.0.png`
  (162 KB) finns både under `apps/viewser/public/` och repo-roten
  `/public/` efter PR #31. Ingen `.gitattributes`/Git LFS — båda
  kopiorna är vanliga git-blobs. Totalt ~3.4 MB duplicerat i historiken.
  Inte runtime-bugg, men onödig repo-vikt och framtida driftkälla om
  kopiorna glider isär (operatör uppdaterar logon i en bara). Fixet
  kräver beslut om vilken plats som är kanonisk: `apps/viewser/public/`
  serveras direkt av Next.js dev-servern och är troligen den enda
  faktiskt använda; `/public/` på repo-roten har inget Next.js-app
  som monterar den. Källa: extern reviewer 2026-05-18.
  Status 2026-05-27: LOGO-halvan löst — `LOGO_SM2.0.png`-kopiorna är
  raderade ur git i båda mapparna efter logo-byte till
  `sajtbyggaren_logo.png` (commits `08f8515`, `f05dfe6`); kvarstår är
  `SM_hero.mp4`-duplikaten som fortfarande används aktivt i hero-
  videon på både mobil och desktop och därför kräver operatör-beslut
  om kanonisk plats innan entry kan stängas helt. Fix: open. Test: open.
### Övriga öppna

- **`B125` Låg-Medel** (var Hög; till stor del adresserad av vercel-sandbox, se Status nedan) - Embedded
  StackBlitz/WebContainer-preview i Viewser stöds officiellt bara i
  Chromium-browsers (Chrome 110+, Edge, Brave, Vivaldi). Safari och
  Firefox kan inte ladda embeddet eftersom WebContainer kräver
  `SharedArrayBuffer` -> cross-origin isolation -> iframe-attributet
  `credentialless`, vilket bara är implementerat i Chromium. Konsekvens:
  ~25-35% av svenska SMB-slutkunder (Safari på Mac/iPhone, Firefox)
  kommer inte kunna använda preview-fliken i Sajtbyggarens UI. Slut-
  publicerade kund-sajter är vanlig Next.js och funkar i alla browsers
  — det här är **bara** ett krav på preview-flödet inne i produkten.
  WebContainer valdes ändå som default-runtime eftersom kompute körs i
  kundens browser och det skalar kostnadseffektivt jämfört med en
  server-side container-park (sajtmaskin/Fly-erfarenhet visade att
  server-side preview blir dyrt linjärt med antal aktiva kunder). B59
  + B123 + B124 är förhistoria: B59 var det parkerade 2026-05-15-
  experimentet där tre header-lägen testades utan grön preview; B123
  satte korrekt host-COEP/COOP; B124 lade iframe-`credentialless`-
  attributet — tillsammans gör de att Chrome/Edge/Brave/Vivaldi-
  embed:en faktiskt funkar. Det som B125 nu kräver är **fallback-
  flöde för icke-Chromium-användare**.

  Kandidater i fallande ordning av oberoende från externa hostar (sätts
  i ADR innan implementation):
  1. **Server-byggd statisk preview**: `build_site.py` producerar redan
     ren Next.js. Bygg static export, deploy till egen VPS / Cloudflare
     R2 / valfri hosting, embed i iframe. Funkar överallt, ~30-60s per
     uppdatering, billigt.
  2. **Lokal `next dev`-process per kund** (parkerad B59-arkitektur):
     server spinner upp en levande dev-server per aktiv kund, iframe
     pekar dit. Snabb hot-reload men skalar dåligt — samma kostnads-
     problem som sajtmaskin hade på Fly.
  3. **"Öppna i StackBlitz"-fallback-knapp**: icke-Chromium-användare
     får en länk istället för embed, klick öppnar stackblitz.com i ny
     flik (där Safari/Firefox har beta-stöd för WebContainers). Sämst
     UX (kund lämnar varumärket) men minst kod.
  4. **Vercel preview-deployments**: bygg sajten en gång per ändring,
     få tillbaka en `*.vercel.app`-URL, embed i iframe. Snabbt och
     ingen egen infra, men kostnad per build och drar in
     Vercel-beroende som operatören explicit vill undvika där det går.

  Browser-detection ska göras client-side i Viewser:
  `feature-detection` av iframe-`credentialless`-attribut + UA-parse,
  visa fallback-vyn för icke-Chromium. Fallback-implementationen är
  scope för B125. Status idag: dokumenterad i README.md "Browser-stöd
  för preview-läge", `docs/product-operating-context.md` "Runtime och
  preview", och `docs/integrations/webcontainers-notes.md`. Källa:
  operatörrapport 2026-05-18 (post-B123/B124-diskussion).
  **Status 2026-06-08 (nedgraderad Hög->Låg-Medel):** vercel-sandbox (ADR 0033)
  serverar en publik https-`vercel.run`-iframe UTAN cross-origin-isolation, så
  den laddar i Safari/Firefox och löser i praktiken Chromium-only-begränsningen
  utan egen infra-park (kandidat 4 ovan, fast via Vercel Sandbox).
  **Status 2026-06-12:** default-flippen (ADR 0033) är GJORD — vercel-sandbox
  är kod-default (tomt env) och prod-default. B125 hålls öppen tills
  sandbox-previewen är E2E-verifierad i icke-Chromium (Safari/Firefox).
  Fix: open.
  Test: open.

- **`B155` Medel-Hög** - Följdpromptar som uttrycker fri copy- eller
  stiländring bevaras som metadata men passerar inte till renderer/codegen
  som applicerbara direktiv. Operatörsverifiering 2026-05-27 visade att
  "Allt sla vara mycket ljusare" inte gjorde en noir/editorial/mörk sajt
  ljusare, och att en prompt som bad om `TEST-JAKOB` i hero och övrig
  text inte gav någon förekomst i `app/page.tsx`. Audit visar att
  `scripts/prompt_to_project_input.py` bara mergar stödda strukturerade
  fält/intent, att `planSource="pinned"` skippar planningModel och att
  renderers/codegen saknar fält för fri copy-edit. Gap-spec:
  `docs/gaps/GAP-followup-prompt-content-passthrough.md`. ADR-utkast:
  `governance/decisions/0034-followup-prompt-content-passthrough.md`.
  Fix: open (ADR 0034 väg A nivå 1-3a är nu i `main` via PR #153 —
  copyDirective-modulutbrytning + P2 grounding + kontakt-ärlighet, llm-models
  v6): följdprompt -> validerade `directives.copyDirectives[]` (targets
  company-name | tagline | about-text | services, operation replace-text |
  include-token) appliceras före render. Deterministisk extraktor + dedikerad
  `copyDirectiveModel`-roll för fri text + editPlan-generering (nivå 3a) för
  about-text/services vid rewrite utan angivet värde; rå prompt läcker aldrig
  (samma public-copy-guards). "byt namnet i headern till X" och "inkludera
  TEST-JAKOB i hero" ger synlig ändring + `appliedVisibleEffect=true`. Förblir
  öppen tills resten landar: bredare/multi-target editPlan, ärligare
  nivå-1-avvisning (i stället för tyst tagline-remap), separat verifierModel
  och väg C (modell-patch av `.generated/`). Väg B FloatingChat-feedback är i
  `main` (PR #139).
  Test: `tests/test_followup_copy_directives.py` +
  `tests/test_followup_honest_no_op.py`.
  Live-test 2026-06-01 (operatör, hamburgare-ab): en följdprompt som bad om
  ändring av en *tjänstetext* ("Tydlig hjälp med cheeseburgers…") remappades
  av `copyDirectiveModel` till `tagline` (närmaste tillåtna target) och
  FloatingChat svarade "Klart! uppdaterade rubriken till …". `appliedVisibleEffect`
  blev true men fel yta ändrades. Reinforcerar: (a) nivå 2 (bredare targets:
  services/hero-body/about) behövs för att träffa rätt text, (b) nivå 1 bör
  hellre vara ärligt avvisande ("kan bara byta namn/tagline nu") än att tyst
  remappa till tagline och påstå full framgång.
  Hardening 2026-06-01 (`2e0c55f`): tre väg A-edge-cases stängda i
  `scripts/prompt_to_project_input.py` — generiskt "namn/namnet" byter inte
  längre `company.name` när prompten scopar till tjänst/produkt/sida; reject-
  verb matchas som ord, inte substring (så "byt företagsnamnet till Changemakers"
  applicerar i stället för att no-op:as); okvoterad trailing "till/to" fångar
  inte instruktioner ("change the hero to be more premium") som publik tagline.
  Kvarstår (håller B155 öppen): nivå 2 bredare targets, ärligare nivå-1-svar och
  väg B/C-presentation. Test: `tests/test_followup_copy_directives.py`.
  Slice 2026-06-10 (okvoterad literal replace): en okvoterad "ändra X till Y"
  matchar nu gammeltexten som exakt delsträng mot sparade copy-fält
  (`company.tagline`, `company.story`, `services[].summary`) och gör ett
  ordagrant byte vid exakt en träff; ingen träff = ärlig no-op; gammeltext i
  ≥2 fält = ärlig tvetydig no-op med reason i `unappliedFollowupIntents`. Citerade vägen oförändrad; ingen
  schema-/LLM-roll-ändring. Håller B155 öppen tills resten av targets är täckta —
  kvarvarande: byte av tjänst-namn/label (schemat har bara `services[].summary`),
  bredare/multi-target replace och väg B/C. Test: `tests/test_followup_copy_directives.py`
  (okvoterade fall + ärlig no-op + tvetydig reason + end-to-end).
  Operatörsfynd 2026-06-10 (bacon-ab, se B178): den okvoterade slicen ovan
  matchar bara "ändra X till Y" mot SPARADE copy-fält. En prompt som citerar
  hela gammeltexten i en lång mening utan citattecken ("Denna text: <hela
  hero-meningen> … vill jag bara ska bli JAKOB") träffar varken den citerade
  vägen (`_QUOTED_SPAN_RE` kräver citattecken) eller exakt-delsträngs-vägen
  (hero-H1 lagras inte som ett matchbart copy-fält), så ändringen no-op:ar
  TYST och full-rebuilden rapporterar ändå `appliedVisibleEffect=true`. Detta
  är den konkreta repron bakom B178 — håll B155 + B178 ihopkopplade tills
  fri-text-replace + ärlig avvisning täcker fallet.
  Slice 2026-06-10 (ADR 0043, sektionscopy via apply — "funktionen som faktiskt
  utför den"): en `copy_change` mot en sektion mappas nu i apply
  (`packages/generation/orchestration/apply/`) till det nya valfria fältet
  `directives.sectionContentOverrides` ("<routeId>.<sectionId>.<field>" -> text,
  field = headline | subheadline | body) och renderaren låter overriden vinna
  över blueprint-copyn (samma mönster som `company.heroHeadline`-pinnen). Routern
  attar nu en named-section-target för `copy_change` ("hero-sektionen" -> hero,
  "om-oss-sektionen" -> home story) och "gör om <copy-noun>" klassas som
  copy_change i stället för visual_style. Den nya texten härleds deterministiskt
  ur följdprompten genom copyDirective-guarderna; `... till "X"`/citat/kolon
  ersätter, och `body` stödjer även `...så den nämner X` (lägg-till). Pilotacceptans
  verifierad deterministiskt: "ändra texten i hero-sektionen till X" och "gör om
  texten i om-oss-sektionen så den nämner Y" ger ny version + synlig ändring +
  `appliedVisibleEffect`/`previewShouldRefresh=true`. Test:
  `tests/test_section_content_overrides.py`,
  `tests/test_patch_apply.py::test_apply_copy_change_*`,
  `tests/test_renderer_blueprint.py::test_section_content_override_*`.
  Slice 2026-06-10 (ADR 0047, generativ sektionsomskrivning — uppföljning (a)
  löst): editPlan-läget i `copyDirectiveModel` breddades till de vitlistade
  sektionsfälten. När `derive_section_edit` inte hittar ett explicit värde och
  följdprompten är en omskrivnings-instruktion ("gör om-oss-texten varmare",
  "skriv om heron så den låter mer premium") läser apply sektionens aktuella
  copy (befintlig override eller blueprint-copy) + instruktionen och genererar
  ny text via samma public-copy-guard + grundnings-vakt som `copyDirectives`;
  name/tagline genereras aldrig. Applicering ENBART via
  `directives.sectionContentOverrides` (ingen ny skrivyta/renderer-/schema-
  ändring). Utan `OPENAI_API_KEY`: ärlig no-op (mock-paritet, byte-identisk med
  förr). Test: `tests/test_section_content_overrides.py` (mockad LLM +
  mock-paritet + guards), `tests/test_followup_copy_directives.py` (gate/guard-
  units).
  Kvarstår (egen uppföljning, håller B155 öppen):
  (b) **compound-prompter** ("gör den coolare och lägg till ett skämt") rapporterar
  ännu inte otillämpade delar via `unappliedFollowupIntents` på apply-vägen — de
  tappas tyst i dag. Icke-numeriska påhittade fakta hålls bara av systemprompten
  (samma begränsning som ADR 0034). Fler sektioner/routes/scaffolds är också
  utanför slicen.
  Slice 2026-06-12 (#313, `56dc754f`, del F+D — falska "Klart!"-ytan stängd):
  legacy-full-rebuild-vägen kan inte längre bevisa framgång med enbart
  byte-diff. `prompt_to_project_input` observerar vilka utförar-ägda direktiv
  som faktiskt applicerades (`appliedFollowupDirectiveKinds` i meta-sidecaren)
  och en okänd nytillkommen capability-slug namnges ärligt i
  `unappliedFollowupIntents`; `build_site` flippar `appliedVisibleEffect` till
  false med reason `intent_not_executable` när inga direktiv applicerades, och
  Viewsers honesty-gates (lokalt + hostat) nollar bara OpenClaws ärliga beslut
  när konkreta direktiv finns. Del D: `generateFollowupOutcomeSummary` ger en
  ärlig LLM-svarsrad grundad enbart i byggets fakta på varje följdprompt-svar
  (no-op får ett "landade inte"-svar; null utan nyckel). B155 förblir öppen som
  kapacitets-gap (fri copy-replace mot rubriker, multi-target, service-label)
  men falsk-framgångs-ytan från B178-repron är stängd. Test:
  `tests/test_followup_honest_no_op.py` +
  `tests/test_viewser_hosted_followup_parity.py`.

- **`BO4-followup-cancel` Låg** - `backoffice/views/playground.py` visar nu
  subprocess-status och loggutdrag medan körningen pågår, men riktig
  cancellation/background-jobb är fortfarande inte implementerat. Det bör tas
  som separat sprint om operatören behöver avbryta en redan startad körning.
- **`B13a` Låg** - `scripts/build_site.py` innehåller produktlogik vilket
  bryter mot `repo-boundaries.v1.json:39`. Naturlig flytt blir
  `packages/generation/build/` när ramverket växer. (Sprint 2B audit-fix
  uppdaterade importgränserna så planning/brief/artifacts-importer inte
  längre bryter policyn, men den större arkitektur-skulden kvarstår.)
  Tidigare kallad `B13`; splittad i `B13a` (arkitektur-flytt, denna post)
  och `B13b` (route-emission) den 2026-05-13 efter att
  `docs/current-focus.md` började använda namnet "B13" för bara den
  ena halvan.
- **`B47` Låg** - `commerce-base` Shopify-startsidan kräver Shopify-handles
  `hidden-homepage-featured-items` och `hidden-homepage-carousel`, och
  footern kräver `next-js-frontend-footer-menu`. Saknas de blir delar av
  ett färdigbyggt `commerce-base`-spår tomma. Spåra som separat
  e-commerce-sprint som antingen ger fallback-copy/produkter eller
  dokumenterar starter-kraven. Ej blocker för aktiva flöden idag (real
  codegen-scope är fortfarande `marketing-base`-only per ADR 0017).
- **`B49` Medel** - `data/starters/docs-base/src/app/layout.tsx` har en
  manuellt underhållen `<aside>`-sidebar med fyra fasta `/docs/...`-länkar
  istället för att läsa från Nextra-page-map / `_meta.ts`-filerna. Källan:
  Steward-Scout-pass på PR #24 (2026-05-14, coach + tre subagents).
  `_meta.ts`-filerna importeras inte någonstans i layouten. Fixupen i
  PR #24 (commit `3f93655`) skrev om `authoring.mdx`, `index.mdx` och
  starter-README så de tydligt säger att sidebar är manuellt
  underhållen och måste edit:as när scaffold injicerar nya MDX, men
  arkitektur-skulden står kvar. Innan `course-education -> docs-base`
  aktiveras i `SCAFFOLD_TO_STARTER` ska antingen Nextra-theme-docs
  `Layout` få fungera (PR #24-bodyn säger att den failade validering
  i miljön) eller en lokal page-map-driven sidebar bygga sig själv från
  `_meta.ts` + filsystemet. Test bör låsa relationen så framtida
  scaffold-injektion av MDX inte tyst kan saknas i nav. Ej blocker idag
  (docs-base är inte aktiverad i runtime).
- **`B53` Låg** - `governance/schemas/` saknar en `routes.schema.json` som
  validerar scaffold-routes-kontraktet som `scripts/build_site.py` redan
  hårdkräver. Buildern kräver att `routes.json` har en route med
  `id="contact"` (annars raisas `SystemExit` i `_pick_contact_route`), men
  ingen schemafil låser detta i governance-lagret. Risk: en framtida
  starter/scaffold kan tappa contact-route utan att fångas tidigt; felet
  fångas först när buildern kör. Spåra som dokumentations-/contract-
  schema-sprint som lägger till `routes.schema.json` + `validate_routes()`
  i `packages/generation/artifacts/validate.py` med auto-validering i
  `load_scaffold_registry()` (samma mönster som B22 löste för
  `scaffold.schema.json`). Ej blocker - byggtidsguarden täcker redan
  scenariot, men en schema-fil ger tidigare felfångst + IDE-stöd.
- **`B59` Medel** (status: parkerad → **förmodligen löst i B123/B124, kvar
  att operatörverifiera end-to-end**) - StackBlitz `template:"node"`-preview
  (WebContainer) i Viewser var blockerad eller instabil i moderna Chrome-
  runtimes som kräver cross-origin isolation. Tre header-lägen testades
  empiriskt 2026-05-15 (både Cursor in-app browser och lokal Chrome smoke):
  - inga isolation headers -> iframe-load blockeras med Chrome-meddelandet
    "Specify a Cross-Origin Embedder Policy to prevent this frame from being
    blocked";
  - `Cross-Origin-Embedder-Policy: require-corp` + `Cross-Origin-Opener-Policy:
    same-origin` -> iframe-load OK, men VM-handshake timeout:ar
    (`Timeout: Unable to establish a connection with the StackBlitz VM`);
  - `Cross-Origin-Embedder-Policy: credentialless` + samma COOP -> iframe-load
    OK, men StackBlitz interna `sign_in`-check faller utan credentials
    (`https://stackblitz.com/sign_in - Unsuccessful HTTP response`) och UI:t
    fastnar permanent i "Startar StackBlitz...".

  Header-experimentet 2026-05-15 committades inte. Hypotesen då var "ingen
  mer COOP/COEP-toggling, byt arkitektur till lokal `next dev`".

  **2026-05-18 superseder-pass (B123 + B124):** operatören rapporterade exakt
  samma "Unable to run Embedded Project — Looks like this project is being
  embedded without proper isolation headers" + "Specify a Cross-Origin
  Embedder Policy" som 2026-05-15-experimentet. Vi implementerade en kombi-
  nation som **inte** testades då:
  1. `Cross-Origin-Embedder-Policy: credentialless` + `Cross-Origin-Opener-
     Policy: same-origin` på Viewser-host (`apps/viewser/next.config.ts`,
     stängde B123 i `5f23d13`).
  2. **Plus** `credentialless`-attribut på själva `<iframe>`-elementet via
     `document.createElement`-patch runt `sdk.embedProject(...)` (stängde
     B124 i `5d05e0d`). Parent-COEP räcker inte för iframes — Chrome kräver
     att varje embedded iframe antingen själv svarar med en COEP-header
     eller bär `credentialless`-attributet, och StackBlitz embed-respons
     skickar ingen header. Iframe-attributet är vad 2026-05-15-experimentet
     missade.

  Header-konfigen är verifierad på server-sidan (`Invoke-WebRequest -Method
  Head http://localhost:3000/` returnerar båda headers). End-to-end-grön-
  preview-verifiering kvar för operatör i Chromium-browser (Chrome 110+,
  Edge, Brave, Vivaldi — `credentialless`-iframe-attributet stöds inte i
  Firefox/Safari, vilket matchar StackBlitz egen Chromium-only-baseline för
  embedded WebContainers). Om operatören ser en grön preview kan B59
  stängas formellt i en separat docs-commit; om embeddet fortfarande
  fastnar i "Startar StackBlitz..." eller VM-timeout är 2026-05-15-
  hypotesen (lokal `next dev`-process som same-origin iframe eller static
  StackBlitz-template) fortfarande den arkitekturella nöd-vägen. Källa
  för supersession: extern reviewer-pass 2026-05-18 (operatör + agent).
  Test: `tests/test_viewser_isolation_headers.py` (7 source-locks som
  fångar både host-headers och iframe-attribut). Fix: open formellt
  (väntar end-to-end-verifikation), kandidat-SHA `5d05e0d`.

### Notera (inte en bugg) - dev-preview-output utanför repo

`scripts/build_site.py` skriver dev-preview-builden till
`../sajtbyggaren-output/.generated/<siteId>` som default sedan
2026-05-14 (workspace-perf-pass). Override via `--generated-dir <path>`
eller env `SAJTBYGGAREN_GENERATED_DIR`. CI använder
`$RUNNER_TEMP/sajtbyggaren-output/.generated/`. Tester går genom
`resolve_generated_dir()` så de följer samma override. Anledningen är
att flytta tunga npm-install-/Next.js-build-output utanför Cursor-
indexerings- och file-watcher-banan så IDE:n hålls snabb. Äldre dokumen-
tation (README, builder-mvp.md, viewser-docs) nämner fortfarande
`.generated/` som om den låg i repo; uppdatera om/när det blir aktuellt
i en docs-cleanup. Ingen B-ID krävs - detta är en avsiktlig
arkitekturändring, inte en bugg.

- StackBlitz/WebContainer-preview kör tillfälligt en patchad payload
  (`next build --webpack`, `npm run build && npm run start`,
  `package-lock.json` inkluderad, `app/global-error.tsx`-override) på grund av
  kända Next 16 + WebContainer-kompatibilitetsfel. Se
  [ADR 0021](../governance/decisions/0021-stackblitz-preview-payload-workarounds.md).

(B20 stängd 2026-05-13 — se "Stängda - regression-test säkrar fixet" nedan.)

### Demo-baseline-fix 1B closure note (2026-05-15)

PR #28 / `885431b` stängde 15 buggar (alla flyttade till "Stängda" 2026-05-18 i en separat Steward-städning): B64, B65, B66, B69, B70, B73, B74, B76, B77, B78, B79, B80, B81, B82 och B84. Efter Project DNA semantic follow-up V1 är B71 också stängd. Kvar öppna (medvetet eller deferred) från bug-sweep-listan: B67, B72, B75, B83, B85, B86 och B87.

### Demo-baseline-fix 1C closure note (2026-05-18)

Lokal mainline-commit `b5ee710` stängde B88 (kontakt-placeholder dev-jargong), B94 (tom team-grid på `/om-oss`), B95 (landnamn som hero-ortstag) och B96 (scaffold-omedveten hero-CTA). Inga andra B-IDs påverkade. Kvar från re-Verifierings-Scout 2026-05-15 är B97 + B98 (låg-impact). Re-Verifierings-Scout med samma fyra prompter (`elektriker Malmö`, `frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som säljer keramik`) körs efter denna bump för att jämföra mot 5.54-baselinen. Förväntad effekt: snitt 6.5-7.0/10.

### B121 discovery-integration closure (2026-05-19)

Steward stängde B121 formellt efter PR A+B+C+D. Merge-baseline `e3fa67b`
(PR #37 baseline smoke). PR A (#34 `70c261b`) resolver + taxonomy, PR B
(#35 `ec32913`) Viewser overlay alignment, PR C (#36 `89680fa`) Backoffice
Discovery Control, PR D (#37 `e3fa67b`) CLI baseline-smoke mot fyra
produktbaseline-prompter — rapport i
`docs/archive/b121-baseline-smoke.md`. Scout 5 read-only-punkter bedöms
täckta av PR A–C-kod + 54 discovery-tester + PR D smoke; full Viewser →
`/api/prompt` → preview E2E är medveten icke-blocker (samma kategori som
dry-run ≠ Viewser-payload). Medvetna icke-blockers kvar: per-run trace i
Backoffice, capability/dossier gaps (booking, contact-form, payments, FAQ).

### PR #38 variant-promotion merge — post-merge-triage (2026-05-19)

Operatör-OK-merge av PR #38 `feat(variants): add eight scaffold variants
(variantModel)` via merge-commit `48a6a22` ovanpå Steward mikro-bump
`99ec56d`. PR:n landade åtta nya canonical Scaffold Variants (4×
`local-service-business` `midnight-counsel`/`warm-craft`/`pulse-fit`/
`clinical-calm` + 4× `ecommerce-lite` `noir-editorial`/`earth-wellness`/
`mono-tech`/`street-vivid`), alla `enabled: true`, schema-valida, plus
mirrors under `data/variant-candidates/<scaffold>/` för backoffice
review. CI grön (governance + builder-smoke + GitGuardian); lokala
guards efter merge: ruff 0 findings, governance 17 policies OK,
rules_sync --check OK, pytest 62 passed för
test_variant_candidate_generator + test_cross_policy_consistency +
test_docs_freshness + test_bug_scope_discipline. Coach-direktiv
2026-05-19 var "ingen variant-promotion under Steward/Scout, separat
sprint/PR krävs"; operatör överskred medvetet med vetskap om att
variant-selection-logik fortfarande saknas (de åtta nya variants är
dead code i prod-flödet tills något specifikt aktiverar dem) och att
en hardcoded default-mapping i `plan.py` introduceras som teknisk
skuld. **Variant-promotion-sprint (Queue #6) kvarstår** för: (a)
variant-selection-logik kopplad till dossier-rationale/wizard-val
eller operator-decision, (b) flytt av default-mapping från kod till
governance-policy + ADR, (c) Re-Verifierings-pass som bekräftar att
de nya variants faktiskt kan aktiveras i prod. **B129 öppen** (se
nedan) för teknisk skuld-spåret. PR #37-like-merge-commit kvar för
att inte squasha bort `4cd1058` + `0511299`-historiken. Branch
`feat/eight-scaffold-variants` lämnad kvar på origin (delete-branch
opt-out) tills variant-promotion-sprint avgör om branchen behövs
för follow-up eller ska städas.

- **`B129` Låg-Medel** - `_DEFAULT_VARIANT_BY_SCAFFOLD` hardcoded
  i `packages/generation/planning/plan.py:_pick_variant`
  (rad ~364-370) istället för i en governance-policy. PR #38
  (`48a6a22`) introducerade en `dict[str, str]` som mappar
  `"local-service-business" → "nordic-trust"` och
  `"ecommerce-lite" → "clean-store"` för att garantera att de åtta
  nya `enabled: true`-variants inte råkar bli defaults via
  `variants[0]`-fallbacken. Tekniskt korrekt och defensivt, men
  bryter mot repo-konventionen att `governance/policies/` är
  sanningskällan för policy-data. Effekt idag: dead code-risk
  (de nya variants kan inte väljas i prod-flödet eftersom alla
  scaffolds har en preferred default), framtida regression-risk
  om någon ändrar en variants `id`-värde utan att uppdatera
  mappningen (ingen cross-policy-test fångar mismatch i dag).
  Fix-skiss: skapa
  `governance/policies/scaffold-default-variants.v1.json` med
  schema som mappar `scaffoldId → defaultVariantId` plus
  `effectiveDate`/`rationale`-fält, läs in via
  `packages/generation/policies.load_default_variant_map`, lägg
  cross-policy-test som verifierar att alla referenced variants
  finns på disk och är `enabled: true`. Egen ADR-sprint per
  repo-konvention. Kopplar mot Queue #6 (variant-promotion-
  sprint) som ändå måste leverera variant-selection-logik
  parallellt. Källa: PR #38 post-merge-triage 2026-05-19
  (parent-agent review efter operatör-override av coach-
  direktiv). Fix: open. Test: open.

### Sköldpaddssoppa-run follow-up (orchestrator 2026-05-19, sen kväll)


### Scout-rapport PR #47 — ytterligare fynd (2026-05-19, sen kväll)

### Vercel MCP cross-repo signal 2026-05-25 (sajtmaskin → sajtbyggaren)

Plug-in-driven scan av Vercel-projektet `sajtmaskin`
(`prj_AK7FqC8NwKorjoxGpkXi6nKGUsoe` under `team_j7KE5zKTm5rdg7zfWzOZhJ89`,
predecessor som migreras till detta repo) visar att 9 av de 10 senaste
deployerna är `state: ERROR`. Senaste production-deps-bumpen
(`dpl_hpugHL6h1DfCDspZ5MYvJwJNPd2C`, branch
`dependabot/npm_and_yarn/production-dependencies-44424f4526`,
commit `a8800bd`) faller i preflight-gate och loggar
`Error: Command "npm run build" exited with 1` direkt efter
`check-lucide-icons` FAIL. En preexisting bug i ett systerrepo, men
samma kodmönster lever vidare här — därav posten:

- **`B145` Låg-Medel** - Vercel-build-loggar för
  `dpl_hpugHL6h1DfCDspZ5MYvJwJNPd2C` (sajtmaskin) failar i
  `scripts/dev/check-lucide-icons.mjs` med
  "36 icon(s) in LUCIDE_ICONS are not exported by installed lucide-react"
  — alla brand-ikoner (Github, Slack, Twitter, Youtube, Facebook,
  Instagram, Figma, Framer, Twitch, Linkedin, Pocket, Trello, Codepen,
  Codesandbox, Dribbble, RailSymbol, Chrome, plus deras `Lucide*`-
  aliaser). lucide-react har tagit bort brand-ikonerna i en senare
  version än `^1.14.0`-baseline:n som sajtmaskin och sajtbyggaren
  delar. Relevans för **detta** repo: ADR 0020 dokumenterar redan
  att `scripts/build_site.py:write_pages` (`render_home`/`render_about`/
  `render_contact`/`render_layout`/`render_products`) hardkodar
  `import { ... } from "lucide-react"`, och att den underliggande
  arkitekturskulden (icon-bibliotek-agnostisk codegen, "väg B" i
  ADR 0020) är öppen. Fem `package.json`-filer pinnar
  `"lucide-react": "^1.14.0"` med caret (`apps/viewser/package.json`,
  `data/starters/marketing-base/package.json`,
  `data/starters/commerce-base/package.json`,
  `data/starters/portfolio-base/package.json`,
  `data/starters/docs-base/package.json`). Så fort dependabot bumpar
  en av dessa starters förbi den version som tar bort brand-ikonerna,
  kommer varje genererad kund-sajt som använder `render_home`/
  `render_layout` att få samma `Module not found`/`Cannot find name`-
  fel som sajtmaskin fastnat på sedan ~april 2026. Sajtmaskins
  fail-state är alltså en levande early-warning för sajtbyggarens
  nästa generation. Fix-skiss i fallande prioritet: (1) pinna
  lucide-react exakt utan caret i alla fem package.json plus en
  cross-policy-test som verifierar samma version över starters +
  apps/viewser (köper tid), (2) realisera ADR 0020 "väg B" — gör
  `write_pages` icon-bibliotek-agnostisk via starter-config eller
  inline-SVG (permanent, egen ADR-sprint), (3) migrera brand-ikoner
  i `render_*`-helpers till dedicerat brand-icon-paket
  (`simple-icons`/`react-icons`) eftersom brand-ikoner inte längre är
  lucide-react:s domän. Källa: Vercel MCP scan 2026-05-25
  (deployment build log limit=80). Cross-ref: ADR 0020,
  `B13a` (architectural debt i `scripts/build_site.py`). Fix: open.
  Test: open.

- **`B156` Låg** - `tests/test_b154_next_dev_tdz.py` är ett *chunk-heuristik*-
  test (curlar fyra routes + grep:ar emitterade webpack-chunks för
  `let w; ... w.X ...`-mönstret), inte ett riktigt browser-hydration-
  smoke. För att helt täcka B154-klassens
  `Uncaught ReferenceError: Cannot access 'w' before initialization`-fel
  behöver vi en headless-browser-smoke (playwright/puppeteer) som laddar
  `/` på en levande `npm run dev`-server och assertar att inga
  hydration-errors loggas i console. Det här gapet flaggades i extern
  review av PR #131 (2026-05-27). Vid implementation: ersätt eller
  komplettera chunk-grep med browser-baserad assertion. Källa: extern
  review 2026-05-27 (PR #131). Fix: open. Test: open.

### Operatörsfynd 2026-06-10 morgon (havre-ab-sessionen)

Alla fyra fynd (B176–B179) är stängda och flyttade till Stängda-sektionen (Steward-pass 2026-06-10).

### Brief-reuse/latest-run-härdning 2026-06-10 (agent-triage, diff-verifierad)

B183–B186 är stängda och flyttade till Stängda-sektionen (Steward-pass +
extern granskning 2026-06-10); B192 (dialog-vägens answer-only-UI) stängdes
2026-06-11 efter att Christophers #269-rebase landat (se Stängda).

### Hostat bygge — publik-deploy-uppföljningar (#284, ADR 0048/0049/0050)

PR #284 (mergad 2026-06-11, `9cd8624`) införde hostat bygge i Vercel-sandbox +
KV-store-adapter + publik rate-limit. Den blockerande säkerhetsbuggen
(spoofbar klient-IP) fixades före merge (`e44dcbb`). Tre fynd från extern
granskning är bekräftade som **publik-deploy-uppföljningar, inte
jakob-be-blockerare** — hostat läge är default AV på jakob-be (lokalt/localhost-
grindat). **Driftspärr HÄVD av operatör 2026-06-11:** publik hostad deploy är
PÅ (`VIEWSER_ENABLE_HOSTED_BUILD=1` + `VIEWSER_ALLOW_NON_LOCALHOST=true` i alla
Vercel-miljöer, konsoliderat via env-städningen + PR #286). Operatörsbeslut:
användare ska kunna skapa sajter publikt nu; B195 är fixad (#287) och B196 är
fixad i review-sweepen 2026-06-11 (site-bunden status-route, se Stängda) —
utan att stänga av publik drift. Skyddet i drift är rate-limit per IP
(ADR 0050) + sandbox-TTL. Samma sweep fixade KV-preflighten (hård fail före
sandbox-start utan Upstash-env hostat) och det synkrona /api/prompt-kontraktet
(icke-streamande klienter tolkade 202-accepted som färdigt bygge).

- **`B197` Låg-Medel** (P3-spår) - discovery-paritet hostat: den hostade
  byggvägen (`runHostedPromptFlow` -> `startHostedBuild`) skickar bara
  `PROMPT_TEXT` in i bygg-sandboxen — wizardens strukturerade
  `discovery`-payload (validerad av `/api/prompt`) når aldrig
  `prompt_to_project_input.py` hostat, så hostade wizard-byggen tappar de
  strukturerade directives lokala byggen får. Kräver att payloaden
  serialiseras in i sandboxen (env/fil) när P3-persistensen läggs.
  Källa: extern granskning #284 (fynd 4), kod-verifierad i review-sweepen
  2026-06-11. Fix: open. Test: open.

### Bygg-logg-observationer 2026-06-14 (hostat bygge, ej blockers — bokförda, ej fixade)

Två icke-blockerande observationer från en bygg-logg, bokförda för
spårbarhet i takeover-prep-rundan 2026-06-14. Ingen åtgärd nu.

- **`B202` Låg** - Turbopack output-file-tracing över-inkluderar för
  `/api/discovery-options` ("traced the whole project unintentionally" i
  bygg-loggen). Karakterisering (kod-läst): `apps/viewser/next.config.ts`
  breddar medvetet `outputFileTracingRoot` till repo-roten (`REPO_ROOT`, två
  nivåer upp) och pinnar policy-/variantfiler via `outputFileTracingIncludes`
  (bl.a. glob `scaffolds/**/variants/*.json`); routen
  `apps/viewser/app/api/discovery-options/route.ts` gör runtime-`fs`-läsningar
  (`readdir`/`readFile`) av governance-policyer + scaffold-varianter via en
  dynamiskt resolvad `repoRoot()` (provar `process.cwd()`, `..`, `../..`).
  Kombinationen breddad trace-rot + dynamiska fs-läsningar + bred glob gör att
  tracern inte kan avgränsas statiskt → den drar med stora delar av monorepot
  → uppblåst funktionsbunt/kallstart. Sannolik fix: snäva
  `outputFileTracingIncludes` till exakta filer och/eller gör route-läsningen
  statiskt avgränsbar. Källa: bygg-logg, takeover-prep 2026-06-14. Fix: open.
  Test: open.
- **`B203` Låg** - runtime-varning `webpsave_buffer: no property named
  'smart_deblock'` i bild-/webp-vägen (sharp/libvips-versionsglapp: koden
  skickar en `smart_deblock`-parameter som den installerade libvips-versionen
  inte känner till). Kosmetisk — webp-utdata skrivs ändå, bara en
  brus-varning. Sannolik fix: pinna/uppgradera sharp så libvips-versionen
  stödjer parametern, eller släpp parametern. Källa: bygg-logg, takeover-prep
  2026-06-14. Fix: open. Test: open.

### Encoding-rot på följdprompt-gränsen 2026-06-14 (#318 bokförd; rotfix i PR #319, inväntar Windows-verifiering)

- **`B204` Medel** - inledande "Ä" i en följdprompt manglas till "*" på vägen
  viewser-chatt → CLI. Symptom (operatörsfynd, site `olkultur-ab-e9594d`): den
  lagrade `meta.followUpPrompt` blev `*ndra …` (ett manglat `Ändra …`), vilket
  strippar verb-nyckelordet ur den normaliserade texten.
  Karakterisering (kod-läst, EJ reproducerad här): följdprompten skickas som
  ett **process-argv** till Python-helpern — `apps/viewser/lib/prompt-runner.ts`
  `runPromptToProjectInput` gör `args.push("--", trimmed)` och `spawn(pythonCommand(), args, …)`.
  På Windows kan icke-ASCII i argv manglas vid Node→OS→Python-överföringen
  beroende på konsolens code page samt Node-/Python-version (jfr AGENTS.md:s
  PowerShell-noter om arg-encoding). Samma helper skriver redan
  `discovery`-payloaden till en **tempfil** (`writeFileSync(..., "utf-8")` +
  `--discovery <path>`) just för att undvika argv-vägen — så det finns en
  beprövad, säker mall.
  Varför ej blind-fixad: en pålitlig repro kräver operatörens exakta
  Windows/PowerShell/Node/Python-miljö + code page, och en fix (rutta prompten
  via tempfil/stdin med explicit UTF-8 och lägg en `--prompt-file`/stdin-läsare
  på Python-sidan) rör det språköverskridande CLI-kontraktet och **alla**
  spawn-sömmar (`prompt-runner.ts`, `build-runner.ts`, `hosted-build-runner.ts`,
  `vercel-sandbox-runner.ts`) — den kan inte verifieras utan repro-miljön, så
  den faller under "riskabelt: blind-fixa INTE".
  Mildring som redan landat (#318): ärlighetssignalerna är gjorda robusta mot
  just denna mangling — `_followup_requested_copy_replace` och
  `compute_unapplied_followup_intents` nycklar på det citerade OLD/NEW-paret,
  inte på verb-nyckelordet, så en citerad copy-replace som inte landar ALLTID
  ger ett ärligt no-op (#313-kontraktet håller även manglat), och den citerade
  copy-replace-vägen (`_extract_literal_replace_directives`-grinden) landar
  numera även med manglat verb. Kvarstår tills roten fixas: en O-CITERAD
  verb-ledd redigering ("Ändra namnet till X" → "*ndra namnet till X") tappar
  fortfarande verbet och blir en tyst no-op. Rekommenderad fix: tempfil/stdin
  med explicit UTF-8, spegla discovery-payload-mönstret.
  Källa: operatörsfynd 2026-06-14 (#318). Fix: open (rotfix landad i PR #319 men
  ej mergad/Windows-verifierad än — status open tills PR:en mergas och operatören
  verifierat). Rotfix: prompten och
  klassificerings-/OpenClaw-meddelandet trådas via UTF-8-tempfil +
  `--prompt-file`/`--message-file` i stället för rå argv (ny delad helper
  `apps/viewser/lib/text-arg-file.ts` + `scripts/cli_text.py`; alla fyra lokala
  spawn-sömmar — `prompt-runner.ts`, `router-classify-runner.ts`,
  `openclaw-runner.ts` ×2 — plus mottagarna `prompt_to_project_input.py`,
  `classify_message.py`, `run_openclaw_followup.py`). Den positionella argan och
  den hostade sandbox-vägen (säker Linux-env-expansion) är bakåtkompatibla/orörda.
  Inväntar Windows-verifiering på operatörens maskin (kör "Ändra …", bekräfta att
  lagrad `meta.followUpPrompt` = "Ändra …", inte "*ndra …"). Test (transport-
  invariant, Windows-manglingen kan inte reproduceras i CI):
  `tests/test_b204_prompt_transport.py`; manglings-robust ärlighet täckt av
  `tests/test_followup_copy_directives.py::test_quoted_copy_replace_miss_is_honest_even_with_mangled_verb`
  + `tests/test_followup_honest_no_op.py::test_copy_replace_no_op_is_honest_under_mangled_verb`.

## Bug-sweep 2026-06-10 (extern RO-granskning, verifierad av tre subagenter)

Fyra externa read-only-agenter rapporterade ~16 fynd; tre interna
granskningsagenter verifierade dem mot kod (jakob-be @ 2dbe3f9). Sex
fixades direkt i bug-sweep round 1 (`65e5cec`, se Stängda). Fyra
bekräftade men ofixade registrerades här (B164/B166/B169/B172); resten var
redan kända (B119/B155/B89), avsiktliga (recommendedPages-halvwire,
msg-0058) eller medvetna fallbacks (change-set-baseline). **Alla fyra är nu
stängda** — B166 via `8f0681d`, B164/B169/B172 via `e35eef8` (bug-sweep
round 2); se Stängda-sektionen.

### Route/Nav Mutation V1 (ADR 0060) — skjutet review-fynd 2026-06-15

- **`B205` Låg** - `ecommerce-lite`-scaffolden (Starter `commerce-base`) har en
  Shopify-CMS-catch-all `data/starters/commerce-base/app/[page]/page.tsx` som
  resolvar valfri en-segments-path via `getPage(handle)` och annars `notFound()`.
  En `route_remove` (`directives.disabledRoutes`) tas bort ur den enda
  activeRoutes-sömmen (`_filter_disabled_routes`), så builden skriver ingen
  statisk `app/<slug>/page.tsx` och navet tappar länken. I preview/design-läget
  (ingen riktig Shopify-backend) ger den borttagna pathen därför 404 — den gamla
  sidan renderas alltså inte. Gapet: på en riktig Shopify-uppkopplad deploy kan
  samma path fortfarande matcha catch-allen och rendera en CMS-sida med samma
  handle, eftersom `disabledRoutes` bara filtrerar scaffold-routes, inte CMS-
  innehåll. Att täppa till det kräver att de borttagna handlesen trådas in i en
  vendored Shopify-template-route (`commerce-base`) plus en guard där —
  icke-trivialt och brett mot hela ecommerce-lite-spåret, som ligger utanför
  kärn-småföretagsflödet. Medvetet skjutet (ADR 0060 review-fynd 3) till en
  dedikerad e-handels-slice hellre än en riskabel punktfix; finding 1 (site-plan-
  artefakt-drift) fixades i samma pass. Källa: ADR 0060 route_remove-review
  (skjutet fynd 3), verifierat 2026-06-15. Fix: open. Test: open.

## Stängda - regression-test säkrar fixet

- **`B160` Låg** (stängd 2026-06-14, regressions-lås komplett — kod-fixen
  fanns redan) - Viewser-headern renderade logon via Next.js `Image` med bara
  `width`/`height` styrt (inte båda eller `style.width: "auto"`), vilket gav
  console-varningen "Image with src … has either width or height modified, but
  not the other" + en CLS/a11y-risk. Kod-fixen (`style={{ width: "auto" }}` +
  `w-auto`) fanns redan i alla tre logo-renderarna (`site-header.tsx`,
  `discovery-wizard.tsx`, `marketing-header.tsx`); det som höll buggen formellt
  öppen var att regressions-låset bara täckte två av tre filer. Denna commit
  utökar låset till `marketing-header.tsx` så ingen header-yta kan tappa
  aspect-ratio-skyddet igen. Fix: kod redan i presentationslagret; lås
  komplett 2026-06-14. Test:
  `tests/test_viewser_marketing.py::test_b160_logo_image_has_explicit_auto_width`
  (täcker site-header + discovery-wizard + marketing-header).

- **`B201` Medel** (stängd 2026-06-12, uppgift G del G1 - bokförd och stängd i samma pass) - hostad
  REN FRÅGA spinner upp full sandbox-pipeline: prod-E2E-incidenten 2026-06-12
  (site-3e7d71ad) visade att följdprompten "Vad tycker du om sajten?" — ren
  fråga utan ändringsintention — hostat drog igång hela sandbox-kedjan
  (Sandbox.create + pip install + OpenClaw-konduktorbeslut) bara för att nå
  answer-only-utfallet, vilket sprängde stream-budgeten (504) och fick chatten
  att hänga. Klient-hotfixen samma dag (`8fed842e`) gjorde submit-gaten ärlig
  men serversidan spann fortfarande upp sandbox för rena frågor. Fix (G1):
  lättviktig pre-klassificering i `/api/prompt`:s hostade väg
  (`lib/hosted-answer-only.ts`) som FÖRE `startHostedBuild` kortsluter till ett
  grundat answer-only-svar (composition + site-brief via KV/blob) — ENBART vid
  hög konfidens "ren fråga"; varje tveksamhet (no-key, timeout, låg konfidens,
  toolIntent/markedSections/baseRunId, saknad kontext) tar byggvägen
  oförändrat. Konduktorn äger fortsatt alla ändringsbeslut; svaret skriver
  inga KV-pekare/artefakter, bumpar ingen version och fejkar aldrig ett
  konduktorbeslut. Källa: operatörens prod-E2E 2026-06-12 + agentutredning
  (P2 i incidentbeviset). Fix: `bde88828` (uppgift G-passet 2026-06-12).
  Test: `tests/test_viewser_hosted_answer_only.py`.

- **`B200` Medel** (stängd 2026-06-12, uppgift G del G2 / ADR 0058 - bokförd och stängd i samma pass) - hostad
  preview-uppstart hämtar hundratals enskilda blobbar: prod-E2E-incidenten
  2026-06-12 (site-3e7d71ad) visade 6–7 min källinhämtning (12–13 min totalt)
  eftersom `collectSourceFromBlob` listar + hämtar varje fil under
  `generated/<siteId>/` (inkl. förbyggd `.next`-output sedan ADR 0055) in i
  funktionen och skriver dem fil-för-fil i sandboxen. Hotfixen `883aff15`
  parallelliserade till 16 samtidiga fetchar — bättre men fortfarande långsamt
  och skört nära `MAX_FILES`/`MAX_TOTAL_BYTES`-vakterna. Fix (G2, ADR 0058):
  bygget paketerar det publicerade fil-setet som EN preview-bundle-tarball
  under `preview-bundles/<siteId>/<buildId>/preview-bundle.tar.gz`
  (best-effort, bara med komplett `.next/BUILD_ID`, inom samma 4000/64MB-tak),
  current-pekaren bär `previewBundleUrl`, och preview-starten skapar sandboxen
  direkt från tarballen med ärlig fil-för-fil-fallback för sajter byggda före
  G2 (vägval + `sourceMs` loggas i `sandbox-preview-start`-raden så vinsten är
  verifierbar). Källa: operatörens prod-E2E 2026-06-12 + agentutredning (P1 i
  incidentbeviset). Fix: `bde88828` (uppgift G-passet 2026-06-12). Test:
  `tests/test_viewser_preview_bundle.py` +
  `apps/viewser/lib/hosted-preview-bundle.test.ts`.

- **`B199` Låg** (stängd 2026-06-12, B199 v2 - hostad run-historik + artefakt-läsning) - hostade run-artefakter:
  `/api/runs/[runId]/{artifacts,trace,files}` var hostat en MEDVETEN 404 +
  `hostedNotice` (artefakterna låg på lokal disk, `data/runs/`), `/api/runs`
  alltid tom, och builder-läget dog vid en hård omladdning. #307 (B199 v1)
  persisterade artefakt-tarballen till blob men ingen UI-yta läste den.
  **B199 v2 stänger kedjan:** orkestrerings-skriptet publicerar ett durabelt
  KV-index per lyckat bygge (`HostedRunIndexEntry` under runId-indexet
  `viewser:run:<runId>` + per-versions-posten
  `viewser:site:<siteId>:run:v<N>`, naming-dictionary v39) med ärlig
  `buildStatus`; `lib/hosted-run-history.ts` läser indexet + packar upp
  run-artifacts-tarballen i minnet och serverar samma RunMeta-/bundle-/
  trace-former som lokalt; `/api/runs?siteId=` listar sajtens historik
  (siteId är capability-nyckeln, samma åtkomstmodell som B196 — INGEN
  global publik listning), artifacts/trace serveras från blob, och en
  olösbar run är en VANLIG 404 utan `hostedNotice` (latchen armas aldrig
  mer på fungerande ytor; bannern flyttade till eget fält `hostedBanner`).
  Builder-valet persisteras i sessionStorage och återställs efter
  omladdning (lokalt + hostat). Init-byggen returnerar nu den KANONISKA
  build_site-runIden (result-block även för init), och en historisk
  `baseRunId` hydrerar SIN versions artefakter via runId-indexet
  (siteId-bundet) — #307:s "bara senaste versionen"-begränsning är stängd.
  Kvarvarande ärliga gap (ej blockers): filträdet per run
  (StackBlitz-fallback) serveras inte hostat, och `changeSet` är fortsatt
  `null` i hostade followup-svar. Källa: agentutredning 2026-06-12 +
  operatörsmandat (B199 v2-passet). Fix: B199 v2-passet 2026-06-12. Test:
  `tests/test_viewser_hosted_run_history.py`.

- **`B198` Medel** (stängd 2026-06-12, del b #306 - contact-form synlig på ecommerce-lite) - följdprompt kan inte aktivera en NAMNGIVEN dossier:
  kedjan följdprompt → hard-dossier-montering är inte trådad. Konkret
  operatörsfall (kottbulle-ab-efadae v5→v6): "Skapa en badge eller sektion
  för min resend-funktion för mejl" gick tekniskt igenom (bygge ok) men
  landade som ett generiskt tjänstekort i `services`-listan;
  `selectedDossiers.required` förblev tom och `resend-contact-form`-dossiern
  (ADR 0053, #295) monterades aldrig ("copied 0 dossier components"). Tre
  staplade gap: (1) section_add resolvar typ → capability → DEFAULT-dossier,
  och `resend-contact-form` har `defaultForCapability: false` (mailto är
  soft default) så den kunde inte väljas via chatt; (2) contact-form saknar
  synlig render-väg på alla scaffolds — faq/team har dedikerad route och
  hours har inline-väg, men bara på local-service-business (kottbulle kör
  ecommerce-lite); (3) ordval utan sanktionerad typ-slug ("badge", "resend",
  "mejl") matchade ingen sektionstyp i routern, så prompten föll igenom till
  legacy-brief-vägen som sydde in ett tjänstekort. **Del a LEVERERAD
  (#301 + hardening):** router-cues (resend/mejlformulär → contact-form-typ)
  + validerad dossier-preferens i section_add→apply — OBS att bara ordet
  "resend" väljer resend-dossiern ("mejlformulär" namnger typen, inte
  dossiern); preferensen är exklusiv per capability (ersätter monterad
  mailto) och negeras av "inte/utan/ej resend". **Del b LEVERERAD
  (2026-06-12):** contact-form surfas nu VISIBELT på ecommerce-lite genom
  den BEFINTLIGA `/kontakt`-routen (routeId `contact`, ingen ny wizard-extra-
  sida som skulle dedupliceras bort) när `resend-contact-form`-dossiern
  faktiskt är monterad — `render_contact` injicerar `<ResendContactForm>`, så
  targeted rebuild diffar `app/kontakt/page.tsx` och kedjan rapporterar ärligt
  `appliedVisibleEffect=true` med `affectedRoutes=["contact"]`. Smal gate:
  `CONTACT_FORM_VISIBLE_SCAFFOLDS={ecommerce-lite}` (speglar
  `INLINE_SECTION_SCAFFOLDS`, breddar INTE `_WIZARD_ROUTE_SCAFFOLDS`) + grundat
  på monterad resend-dossier. mailto-defaulten saknar synlig komponent och
  förblir ärligt mount-only, liksom contact-form på alla andra scaffolds.
  Källa: operatörsfynd 2026-06-11 (orkestratorpass) + kodverifiering
  (`section_directives`, action-registry, kottbulle-PI-snapshots v5/v6).
  Fix: `05e62911` (del a #301; del b #306, 2026-06-12). Test:
  `tests/test_section_directives.py`, `tests/test_patch_apply.py`,
  `tests/test_router_classify.py` (del a); `tests/test_section_directives.py`
  + `tests/test_followup_chain_cli.py` (del b).

- **`B195` Medel** (stängd 2026-06-11, #287 manifest-baserad servering) - blob-upload skriver över
  `generated/<siteId>/...` men raderade aldrig gamla filer → en borttagen
  route/asset blev kvar i preview vid ombygge mot samma `siteId` (stale fil).
  Åtgärdad med manifest-baserad servering (approach a): det hostade bygget
  publicerar sist ett `generated/<siteId>/.manifest.json` med byggets exakta
  fil-set, och `collectSourceFromBlob` serverar bara manifest-listade filer, så
  stale blobbar ignoreras utan radering eller race-känslighet. Den tidigare
  upload-loop-härdningen (`fa268c5` — manifest-fil + verifierat antal) löste en
  annan bugg (tyst noll-uppladdning från trasig processsubstitution) och stänger
  inte B195. Källa: extern granskning #284 (fynd B). Fix:
  `08575a03` (PR #287, mergad 2026-06-11). Test:
  `apps/viewser/lib/generated-blob-source.test.ts` (`selectServedRelPaths`) +
  `tests/test_viewser_hosted_blob_cleanup.py`.

- **`B194` Låg** (stängd 2026-06-11, P3-spårets första slice) - hostade
  följdpromptar (`startHostedBuild(... followup: true)`) kunde inte härleda
  föregående version: `prompt_to_project_input.py --followup-site-id` läser
  `data/prompt-inputs/<siteId>.{project-input,meta}.json` som aldrig fanns i
  en färsk sandbox → ärlig fail. Fixad med run-state-persistens: varje lyckat
  hostat bygge publicerar det färska PI/meta-paret versions-scopat till blob
  (`run-state/<siteId>/v<N>/`, immutabelt — pekaren flyttas först när BÅDA
  filerna är uppe) och sätter durabla KV-pekaren
  `viewser:site:<siteId>:run-state`; vid followup preflight-läser
  `startHostedBuild` pekaren (saknad → ärlig fail FÖRE Sandbox.create med
  byggråd) och sandboxen curlar ner paret till `data/prompt-inputs/` innan
  followup-kommandot körs. Run-state-upload-fel efter lyckat bygge faller
  aldrig bygget (sajten är publicerad) men lämnar pekaren orörd så nästa
  followup utgår från senast konsistenta paret. `--base-run-id` hostat ingår
  inte (v<N>-layouten är förberedd för det). Källa: extern granskning #284
  (fynd A). Fix: `feat/b194-hosted-run-state`. Test:
  `tests/test_viewser_hosted_run_state.py`.

- **`B192` Låg-Medel** (stängd 2026-06-11, dagen efter #269-rebasen som
  deferrade den) - answer-only-svar via DIALOG-vägen (färgväljare,
  modul-dialog, uploader, scrape, variant, colorize, inspector-sheet — alla
  som konsumerar `use-followup-build`) renderades som RÖTT fel trots
  `isAnswer`-diskriminatorn: hooken la svarstexten i `error`-state och
  callers stylade den destructive. Fixad enligt fix-skissen: hooken
  separerar `answer` från `error` (clearError rensar båda, nytt bygge
  nollställer båda) och varje inline-yta renderar `answer` som neutral
  info (`role="status"`). Resultatkontraktet
  (`{ok: false, error, isAnswer: true}`) oförändrat så builder-shellens
  toast-väg (variant info) fungerar identiskt. Källa: extern
  GPT-granskning 2026-06-10 (fynd 1). Fix: `eed5efc`. Test:
  `tests/test_viewser_dialog_answer_state.py`.

- **`B196` Medel** (stängd 2026-06-11, review-sweep samma vecka som fyndet) -
  `GET /api/hosted-build/<runId>` exponerade bygg-status för valfritt `runId`
  utan site-binding/auth — i publikt läge en enumererings-/informations-
  läckage-yta (på jakob-be ofarligt: localhost-grindat + UUID-skyddat).
  Fixad genom site-bindning: routen kräver query-param `?siteId=` (validerad
  med samma mönster som runnern) och jämför mot statusens `siteId` före svar;
  saknad nyckel och siteId-mismatch ger EXAKT samma svenska 404-text så
  svaret aldrig bekräftar att ett gissat runId existerar (ingen orakel-läcka).
  Klientpåverkan: ingen klient anropade status-routen vid fixtillfället
  (prompt-routens NDJSON-stream pollar KV server-side); budget-slut-
  hänvisningarna i `/api/prompt` pekar nu på den siteId-bundna URL:en.
  Publik drift stängdes ALDRIG av (operatörens spärr-hävning respekterad).
  Källa: extern granskning #284 (fynd C). Fix: `cc5e6e5`. Test:
  `tests/test_viewser_hosted_build_status.py`.

- **`B193` Medel** (stängd 2026-06-10, samma dag som operatörsfyndet) -
  rollerna delade inget minne i chatten: dirigenten svarade "jag ändrade
  inget i den här turen" direkt EFTER att stylisten byggt v2 (operatörens
  snickesnackarn-session) — tekniskt sant men kontextlöst, så systemet såg
  ut att motsäga sig självt. Rotorsak: `generateConversationAnswer`
  (`apps/viewser/app/api/prompt/route.ts`) hade ingen bygghistorik alls i
  systemprompten. Fix: ny `latestChangeSnippet(siteId)` läser senaste
  KOMPLETTA runens version + ändringsprompt (via B164-helpern
  `latestCompletedRunForSite` + runens `input.json`, defensiv på alla
  läsfel) och trådas in som refererbara FAKTA — medan ärlighetslinjen
  "du har inte ändrat något i DENNA tur" kvarstår. Utan historik: ärlig
  fallback-rad. Källa: operatörsfynd + read-only-granskning 2026-06-10
  ("chatten motsäger sig själv", prioriterad 1:a). Fix:
  `apps/viewser/app/api/prompt/route.ts`. Test:
  `tests/test_viewser_api_prompt.py::test_conversation_answer_carries_build_history_memory`.

- **`B187` Medel** (stängd 2026-06-10, extern granskning samma dag) - en
  frågeformad section_add ("kan du lägga till en FAQ-sektion?", "skulle du
  kunna lägga till en team-sektion?") klassades som answer-only `question`
  i stället för edit → användaren fick ett chat-svar och INGET bygge.
  Rotorsak: routerns `_ADD_VERBS` bar bara imperativformerna ("lägg till");
  infinitivets "lägga till" matchade inte (ordgräns: "lägg" ≠ "lägga") så
  add-verbet missades och ?-grenen vann. Restyle/copy-edits i frågeform
  ("kan du göra sajten mörkblå?") klarade sig — bara add-verben saknade
  infinitiv. Fix: infinitivformerna ("lägga till/in/dit", "sätta in/dit")
  tillagda i `_ADD_VERBS` (`packages/generation/orchestration/router/
  classify.py`), additiv lexikon-utökning, negativa kontroller intakta
  ("vad är en FAQ-sektion?" förblir question). Källa: extern GPT-granskning
  2026-06-10 (fynd 2), repro-verifierad före fix. Test:
  `tests/test_openclaw_roles.py::test_question_formed_edits_classify_as_edit`
  + `::test_genuine_conversation_stays_answer_only_after_infinitive_verbs`.

- **`B188` Medel** (stängd 2026-06-10, extern granskning samma dag) -
  cross-site-guarden för explicit baseRunId (B185) hoppades över när
  `_build_result_site_id` gav `None` (saknad/oläsbar `build-result.json`
  eller tomt siteId) — en overifierbar/trasig run-dir kunde alltså passera
  skyddet och bli följdpromptens bas. Fix: `None` behandlas nu som "kan
  inte verifiera ägarskap" → ärligt stopp med åtgärdsförslag (välj komplett
  run eller auto-resolve). Källa: extern read-only-granskning 2026-06-10
  (F2), diff-verifierad. Fix: `scripts/build_site.py`. Test:
  `tests/test_followup_chain_cli.py::test_followup_chain_rejects_unverifiable_base_run_id`.

- **`B189` Låg-Medel** (stängd 2026-06-10, extern granskning samma dag) -
  brief-reusens removed-notes-guard (B184) detekterade "förra briefen hade
  en operator-/mood-not" via RÅTT substring-test på prefixet — fri
  brief-prosa som bara nämnde strängen "Operator: " mitt i ett block
  tvingade en onödig regenerering på varje följdbygge för den sajten
  (= exakt copy-driften B180 dödade, fast i smalt kantfall). Fix:
  prefix-matchning per BLOCK (`notesForPlanner` är `\n\n`-separerade block,
  injektorn prependar sina block). Källa: extern read-only-granskning
  2026-06-10 (F3), kod-verifierad. Fix:
  `packages/generation/brief/site_brief.py`. Test:
  `tests/test_brief_carry_forward.py::test_prose_mentioning_operator_prefix_does_not_force_regen`.

- **`B190` Medel** (stängd 2026-06-10, extern granskning samma dag) -
  `/api/prompt`-conversation-grinden läste bara `conversationKind` mot
  kind-mängden, INTE `expectsAnswer` — medan use-followup-build och
  FloatingChat (efter #274) hedrar `expectsAnswer` som självständig signal.
  Skulle konduktorn någonsin svars-markera en kind utanför mängden hade
  servern kört vidare till legacy-build medan klienterna väntade svar
  (kontraktsdivergens mellan lagren). Fix: grinden hedrar nu BÅDE
  kind-mängden OCH `expectsAnswer === true`, och återanvänder den redan
  extraherade `conversationMeta` (granskningens F5, dubbelanropet bort).
  Källa: extern read-only-granskning 2026-06-10 (F4+F5), kod-verifierad.
  Fix: `apps/viewser/app/api/prompt/route.ts`. Test:
  `tests/test_viewser_floating_chat.py::test_prompt_route_gate_honours_expects_answer`.

- **`B191` Låg** (stängd 2026-06-10, extern granskning samma dag) -
  `_metadata_int`-fixen (B-posten för Arrow-kraschen) hade ett kvarvarande
  kraschfönster: en patologisk sträng som `"--5"` passerade
  `lstrip("-").isdigit()`-heuristiken men fick `int()` att kasta
  `ValueError` → grafvyn kraschade igen (samma symptom fixen skulle döda).
  Fix: `try/except (ValueError)` i stället för heuristiken. Källa: extern
  read-only-granskning 2026-06-10 (F8), kod-verifierad. Fix:
  `backoffice/asset_graph.py`. Test:
  `tests/test_backoffice_asset_graph.py::test_metadata_int_never_raises_on_pathological_strings`.

Äldre stängda buggar (159 st, stängda 2026-05-08 till 2026-06-10, B18 till B186 m.fl.) är arkiverade ordagrant: se [docs/archive/known-issues-closed-2026-06-15.md](archive/known-issues-closed-2026-06-15.md).

## Process

- En bugg som hittas i en audit MÅSTE få ett ID här (`<bokstav><nummer>`)
  innan den fixas.
- En fix MÅSTE komma med en regressionstest. Tester utan koppling till en
  ID i den här filen får finnas men är inte regression-tester.
- "Fix" markeras med kort commit-sha; det räcker att den första commiten
  ligger där eftersom följdfixar refererar tillbaka.
- "Test" pekar på en konkret `tests/<file>.py::<test_name>` som blockerar
  regression i framtida körningar.

## Allmänna principer som inte blir buggar förrän de bryts

- Builder skriver aldrig riktiga `.env`-filer.
- Engine Run-trace är append-only.
- `understand` / `plan` / `build` är canonical; reviewer-vokabulär är intern
  läs-karta.
- En Dossier-realisering är scaffold-specifik; en Dossier-definition är
  portabel.
- Backoffice får läsa allt och skriva via guarded helpers; aldrig direkt mot
  `data/runs/` eller `packages/`.
