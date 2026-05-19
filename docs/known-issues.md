# Known issues + audit-derived bug log

> **Aktivt bug-scope:** 26 aktiva, 0 misplaced (har Fix-SHA men borde flyttas till Stängda), 5 unknown, 98 stängda. Kör `python scripts/list_open_bugs.py` för full lista. Format-disciplin: se governance/rules/bug-scope-discipline.md.

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

## Round 1 audit (2026-05-07) - tre subagents granskade Builder MVP

### Säkerhets/race - alla fixade i round 2

- **`B4` Hög** - `.env`-guard i `scripts/build_site.py:67` var case-sensitive;
  `.ENV`, `.Env.Local` slank igenom.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_env_guard_blocks_case_variants`.
- **`B5` Hög** - `copy_starter` ignorerade inte `.env*`; en starter med
  `.env.local` skulle kopierats igenom.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_copy_starter_ignore_blocks_env_files`.
- **`B6/B10` Hög** - `runId` hade bara sekundprecision; två regenerationer
  inom samma sekund kunde dela run-mapp och truncera trace.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_run_id_unique_under_rapid_calls`.
- **`B7` Hög** - `patch_layout` / `patch_globals_css` / `patch_package_json`
  använde direkt `Path.write_text` istället för guarded helper.
  Fix: `c466f58`+ (alla tre går via `write()`).
- **`BO3` Hög** - `backoffice/views/governance.py:66` skrev policy
  non-atomiskt; crash mellan truncate och write skulle korrumpera.
  Fix: `c466f58`+ (`atomic_write_text`).

### Kontraktsbrott - alla fixade i round 2

- **`B1` Medel-Hög** - Phase 3 saknade `generated-files/`,
  `repair-result.json`, `quality-result.json` enligt `engine-run.v1.json`.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_all_eight_engine_run_artifacts_present`.
- **`B2/BO1` Medel-Hög** - `build-result.json` saknade `modelUsage`; ingen
  token-spårning ens som nollor.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_build_result_has_model_usage_stub`.
- **`B8/B9` Medel** - route-guard kollade bara att filer fanns, inte att
  pages hade `export default`.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_route_guard_blocks_missing_default_export`.
- **`B11` Hög** - `generatedFilesDir` pekade på dev preview istället för
  canonical snapshot under `data/runs/<runId>/generated-files/`.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_generated_files_dir_points_to_run_snapshot`.

### Konsistens - alla fixade i round 2

- **`B3` Medel** - trace event-namn `input_written` vs `dev_generate.py`'s
  `input.written` (snake vs dotted).
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_trace_event_names_use_dotted_form`.
- **`BO5` Medel** - Backoffice visade scaffolds med `_status: placeholder`
  som "Implementerad: ja".
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_placeholder_detector_recognises_status_field`.
- **`N1` Låg** - `docs/glossary.md` saknade Site/Feature/Integration/Data
  Dossier (registrerade i naming-dictionary v7).
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_glossary_lists_four_dossier_types`.
- **`N2` Låg** - `docs/architecture/pipeline-mapping.md` ljög om vad som
  står i `globallyForbidden`.
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_pipeline_mapping_does_not_misclaim_globally_forbidden`.
- **`N3` Låg** - `packages/generation/orchestration/dossiers/` finns inte
  fysiskt trots att policies pekar dit.
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_dossier_owner_path_exists_on_disk`.
- **`N4` Medel** - `preview-runtime-policy.v1.json` självmotsade sig
  ("no F2/F3 tier" + "F3-likt scenario", "tier-3 SDK:er").
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_preview_runtime_policy_self_consistent`.

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

- **`B71` Hög** - Follow-up merge fryser `company.story`,
  `company.tagline`, `tone` i strid med egen docstring.
  `scripts/prompt_to_project_input.py:merge_followup_project_input`
  docstring säger att kandidat bidrar med "additive signals (new
  services, capabilities, conversion goals and a visible story note)",
  men koden tar aldrig `story` från kandidat, och `tone` lämnas orörd
  när det redan är ett dict. Källa: brief-pipeline-bug-sweep
  2026-05-15. Två val: (a) uppdatera docstring + test att matcha
  faktisk byte-stabil semantic, eller (b) semantic patching nu
  (kräver ADR, hör hemma i Project DNA-sprinten). Fix: open. Test:
  open.
- **`B72` Medel** - `apps/viewser/lib/runs.ts:40-84` `listRuns` läser
  `build-result.json` för alla run-kataloger trots att svaret bara
  behåller `limit` poster. O(N) disk-läsningar per `GET /api/runs`,
  skalar obegränsat när `data/runs/` fylls. Källa: viewser-app-bug-
  sweep 2026-05-15. Fix: stat alla först, sortera på mtime descending,
  slice till limit, läs `build-result.json` bara för survivors. Fix:
  open. Test: open.
- **`B75` Medel** - `governance/schemas/project-input.schema.json`
  saknar `additionalProperties: false` på root och underobjekt
  (`company`, `contact`, `location`, `services`-items, `tone`,
  `selectedDossiers`). En felstavad/extra nyckel passerar
  `jsonschema`-valideringen tyst och kan ge `KeyError` nedströms.
  Jämför `site-brief.schema.json` som låser
  `additionalProperties: false`. Källa: brief-pipeline-bug-sweep
  2026-05-15. Fix: lägg till `additionalProperties: false`; kör full
  test-suite (kan exponera latenta extra-fält). Fix: open. Test:
  open.
- **`B83` Låg** - `scripts/prompt_to_project_input.py:_build_services`
  släpper tysta dubblet-tjänster när två brief-items slugifierar till
  samma ASCII-key. Kundsidans tjänstegrid blir kortare än briefen
  anger utan spår. Källa: brief-pipeline-bug-sweep 2026-05-15. Fix:
  disambiguerande suffix på slug-id eller stderr-warning. Fix: open.
  Test: open.
- **`B85` Låg** - `scripts/prompt_to_project_input.py` modul-
  docstring säger att stdout-kontraktet är `siteId:` + `dossierPath:`,
  men `main()` skriver sex nycklar. Drift mellan spec och
  implementation. Källa: brief-pipeline-bug-sweep 2026-05-15. Fix:
  uppdatera docstring eller lås nycklar med source-lock-test.
  Fix: open. Test: open.
- **`B86` Låg** - `scripts/build_site.py:1387-1388` hårdkodar
  `NPM_INSTALL_TIMEOUT_SECONDS = 600` och `NPM_BUILD_TIMEOUT_SECONDS
  = 300`. Långsamma Cloud Agent VMs överskrider regelbundet, ger
  flaky failures orelaterade till site-correctness. Källa: builder-
  renderer-bug-sweep 2026-05-15. Fix: CLI-flagga eller env-knapp.
  Fix: open. Test: open.
- **`B87` Låg** - `scripts/prompt_to_project_input.py:1091-1096`
  fallbackar tyst till `model = "gpt-5.4"` när `resolve_brief_model()`
  misslyckas. Operatör märker inte att policy-konfigurationen är
  trasig. Källa: brief-pipeline-bug-sweep 2026-05-15. Fix: logga
  högt på stderr vid resolution failure. Fix: open. Test: open.

### Extern reviewer-triage 2026-05-15 (mot `d99f8ba` + `c273b1a`)

- **`B89` Medel** - `packages/generation/brief/extract.py:detect_language`
  defaultar till `sv` för korta engelska prompts utan träff i
  `ENGLISH_HINTS` (t.ex. `plumber stockholm`, `barber malmo`,
  `ceramic studio`). Kategoriöverlapp med B62 men annan edge-yta. Källa:
  extern reviewer + RO-verifierings-subagent 2026-05-15. Fix: open.
  Test: open.
- **`B90` Låg-Medel** - `packages/generation/brief/extract.py:ENGLISH_HINTS`
  innehåller `"a"` och `"an"`, vilket kan ge falska engelska träffar
  (`A & O El Malmö` klassificeras som `en`). Källa: extern reviewer +
  RO-verifierings-subagent 2026-05-15. Fix: open. Test: open.
- **`B91` Medel** - `_normalize_location_hint` i
  `scripts/prompt_to_project_input.py` mappar idag i praktiken bara
  `sweden -> Sverige`; övriga vanliga engelska/svenska varianter passerar
  oförändrat. Källa: extern reviewer + RO-verifierings-subagent
  2026-05-15. Fix: open. Test: open.
- **`B92` Låg** - `_BUSINESS_TYPE_LABEL_SV` mappar
  `naprapat -> naprapatklinik`, vilket överanpassar enskild naprapat till
  klinikform i H1-fallback. Källa: extern reviewer +
  RO-verifierings-subagent 2026-05-15. Fix: open. Test: open.
- **`B93` Låg-Medel** - `_company_business_label` fallback i
  `scripts/prompt_to_project_input.py` visar rå slugtext i svensk H1
  (`företag som arbetar med pet grooming`). Svensk mening men engelsk
  slugläcka i kundcopy. Källa: extern reviewer +
  RO-verifierings-subagent 2026-05-15. Fix: open. Test: open.

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

- **`B97` Låg** - `/kontakt`-paragrafen "Beskriv jobbet kort så
  återkommer vi inom en arbetsdag med tider och offert." använder
  `jobbet`+`offert` hardcoded — passar inte e-handel-cases (frågor om
  beställning/retur/leverans). Källa: re-Verifierings-Scout
  2026-05-15. Fix: open. Test: open.
- **`B98` Låg** - "Områden vi arbetar i"-block på `/om-oss` är
  meaningless för e-handel — borde inte renderas (eller annan rubrik)
  när scaffold = `ecommerce-lite`. Källa: re-Verifierings-Scout
  2026-05-15. Fix: open. Test: open.

**B71-not (PR #28 stängde, men markerad som unverified av re-Scout):**
Re-Verifierings-Scout flaggade att follow-up byte-stabilitet inte
kan verifieras i ett första-generations-pass (kräver v1 → v2-test).
B71-stängningen i Grind hänger på kod-/docstring-spårning i
`tests/test_prompt_to_project_input.py`; ingen kritik mot lock-tester,
bara att Scout inte själv kunde verifiera invarianten. Två-pass-test
bör naturligt köras nästa gång någon ändå provkör follow-up-flödet.

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
- **`B120` Låg** - `scripts/prompt_to_project_input.py:_apply_discovery_overrides`
  (rad 1574-1582) försöker plocka ut stad ur kontakt-addressLines med
  regex `r"\b\d{3}\s?\d{2}\s+([A-Za-zÅÄÖåäö\-]+)"`. Mönstret matchar
  bara svensk postnummerstruktur (`xxx xx Stad`), så adresser i
  format `Götgatan 12, 11646 Stockholm` ger ingen träff (kommat),
  och internationella adresser missar helt. Effekten är tyst fallback
  till brief-extracted location. Inte krasch, men halvfel
  platsdata utan signalering. Fix-skiss: prova flera mönster i fallande
  ordning, inklusive `,`-separator och engelska postnummer-format.
  Källa: extern reviewer 2026-05-18 (runda 2). Fix: open. Test: open.
- **`B122` Låg** - `apps/viewser/components/prompt-builder.tsx`
  växlar från `thinking` till `building`-stage via `setTimeout(...,
  1500)` istället för på en faktisk backend-signal. Det fungerar i
  praktiken eftersom `/api/prompt` typiskt tar > 1.5s, men en
  prompt som returnerar snabbt (cache hit, valideringsfel) ger
  operatören en falsk "Bygger sajt"-vy innan svaret faktiskt finns.
  Värre: en hängd prompt visar `building` direkt fast den fastnat
  i `thinking`-fasen, vilket ger fel mental modell. Inte backend-bugg
  men UI-signalering. Fix-skiss: skicka faktisk stage-signal från
  `/api/prompt` (t.ex. via Server-Sent Events eller separat
  `/api/prompt-status?runId=`-poll). Källa: extern reviewer
  2026-05-18 (runda 2). Fix: open. Test: open.

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
  som monterar den. Källa: extern reviewer 2026-05-18. Fix: open.
  Test: open.
- **`B116` Låg** - `apps/viewser/lib/build-runner.ts` har en modul-
  global `let inFlight: Promise<unknown> | null = null;` som
  serialiserar alla bygg-anrop globalt. Kombinerat med
  `BUILD_TIMEOUT_MS = 600_000` (10 min, höjt från 3 min i PR #31 för
  att kalla `.generated/<siteId>/`-byggen ska hinna med `npm install`
  + Next 16 webpack-build) innebär det att en hängd build blockerar
  alla nya prompter i upp till 10 minuter. Inte säkerhets- eller
  korrekthets-bugg, men UX-risk: operatör som triggar ett hängande
  bygge ser sin nästa prompt rejection:as som 409 conflict i upp till
  10 minuter utan tydlig återkoppling. Lösningar är icke-triviala
  (cancel-knapp, progress-baserad early-detection, eller per-projekt
  i stället för global mutex). Källa: extern reviewer 2026-05-18.
  Fix: open. Test: open.

### Övriga öppna

- **`B125` Hög** (produktblocker innan launch) - Embedded
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
  operatörrapport 2026-05-18 (post-B123/B124-diskussion). Fix: open.
  Test: open.

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

PR #28 / `885431b` stängde 15 buggar (alla flyttade till "Stängda" 2026-05-18 i en separat Steward-städning): B64, B65, B66, B69, B70, B73, B74, B76, B77, B78, B79, B80, B81, B82 och B84. Kvar öppna (medvetet eller deferred) från bug-sweep-listan: B67, B71 (markerad unverified av re-Scout), B72, B75, B83, B85, B86 och B87.

### Demo-baseline-fix 1C closure note (2026-05-18)

Lokal mainline-commit `b5ee710` stängde B88 (kontakt-placeholder dev-jargong), B94 (tom team-grid på `/om-oss`), B95 (landnamn som hero-ortstag) och B96 (scaffold-omedveten hero-CTA). Inga andra B-IDs påverkade. Kvar från re-Verifierings-Scout 2026-05-15 är B97 + B98 (låg-impact). Re-Verifierings-Scout med samma fyra prompter (`elektriker Malmö`, `frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som säljer keramik`) körs efter denna bump för att jämföra mot 5.54-baselinen. Förväntad effekt: snitt 6.5-7.0/10.

### B121 discovery-integration closure (2026-05-19)

Steward stängde B121 formellt efter PR A+B+C+D. Merge-baseline `e3fa67b`
(PR #37 baseline smoke). PR A (#34 `70c261b`) resolver + taxonomy, PR B
(#35 `ec32913`) Viewser overlay alignment, PR C (#36 `89680fa`) Backoffice
Discovery Control, PR D (#37 `e3fa67b`) CLI baseline-smoke mot fyra
produktbaseline-prompter — rapport i
`docs/reports/b121-baseline-smoke.md`. Scout 5 read-only-punkter bedöms
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

### Viewser-overlay-E2E Scout 2026-05-19 — Case 4 (sköldpaddssoppa / conflict)

- **`B137` Medel** (öppen, tagline-läckage av rå prompt-text) -
  `scripts/prompt_to_project_input.py` skriver `company.tagline` =
  rå prompt-/beskrivnings-text när briefModel inte producerar en
  kort sammanfattning. Verifierat live i case 4 (sköldpaddssoppa):
  `app/page.tsx:9` på Hero visar `"Hemsida om sköldpaddssoppa, mat,
  2 sidor, gröna färger"` — operatörens fri-prompt-text läcker
  publikt som tagline. Förväntat beteende: briefModel ska producera
  kort marknadsföringsfras (8-15 ord), eller `_derive_tagline`-helper
  ska ge en deterministisk fallback (typ `"Lokalt tjänsteföretag i
  Stockholm"`) i stället för rå prompt. Effekt idag: sajter med sparse
  briefModel-output får promptens egen text som hero-tagline, vilket
  är dev-jargong (`"2 sidor"`, `"gröna färger"`-direktiv etc.) snarare
  än kund-presentation. Bekräftar att briefModel-spåret + post-process-
  fallback inte täcker case där operatören skriver instruktioner i
  beskrivnings-fältet i stället för verksamhetsbeskrivning. Källa:
  Viewser-overlay-E2E Scout case 4, 2026-05-19. Read av
  `..\sajtbyggaren-output\.generated\skoldpaddssoppa-karlsson-099d5c\app\page.tsx`.
  Fix: open. Test: open (rekommenderat
  `tests/test_prompt_to_project_input.py::test_tagline_never_equals_originalprompt_or_offer`
  som låser att `company.tagline` aldrig är identisk med `originalPrompt`
  eller `offer`-fältet).

## Stängda - regression-test säkrar fixet

- **`B134` Medel** (stängd 2026-05-19, wizardMustHave follow-up reset) -
  `scripts/prompt_to_project_input.py:generate_followup()` ärvde alltid
  `existing_meta["wizardMustHave"]` och skickade listan vidare som
  `meta_overrides["wizardMustHave"]`. Eftersom `generate()` först
  deriverade ny `wizardMustHave` från en eventuell ny discovery-payload
  men sedan körde `meta.update(meta_overrides)`, kunde v1-listan skriva
  över v2-listan. Effekt: en följdversion där operatören flyttat
  riktning från t.ex. `["Bokning online", "Bildgalleri"]` till
  `["FAQ"]` kunde få stale `pageIntentWarnings` för sidor operatören
  lämnat. **Fix:** `generate_followup()` ärver nu `wizardMustHave` och
  `discoveryDecision` bara när ingen ny discovery-payload finns, och
  har en explicit reset-flagga för callers som vill nolla page-intent-
  signalen utan ny wizard-runda. `generate()` skyddar dessutom färsk
  discovery-derived `wizardMustHave` och `discoveryDecision` från stale
  `meta_overrides`. Källa: B132-skuggning i
  Viewser-overlay-E2E Scout follow-up-spår, verifierad i kod
  2026-05-19. Fix: `900dae5`. Test:
  `tests/test_prompt_to_project_input.py::test_followup_with_new_discovery_resets_wizard_must_have`,
  `tests/test_prompt_to_project_input.py::test_followup_without_new_discovery_inherits_wizard_must_have`,
  `tests/test_prompt_to_project_input.py::test_followup_with_explicit_reset_flag_clears_wizard_must_have`.

- **`B135` Medel** (stängd 2026-05-19, placeholder fieldSources) -
  B133 surfacade `placeholderContactFields` i meta/build-result, men
  Discovery Resolverns `fieldSources` fortsatte markera samma
  dummy-värden som `"brief"` när wizard och scrape saknade kontaktdata.
  Exempel: `contact.phone = "+46 8 000 00 00"` kom från
  `_placeholder_contact` men `fieldSources["contact.phone"]` sa
  `"brief"`, vilket gjorde Backoffice/Doctor-provenance semantiskt
  osann. **Fix:** `resolve_discovery(...)` tar nu ett bakåtkompatibelt
  `placeholder_fields`-argument från
  `scripts/prompt_to_project_input.py` och `_apply_contact_fields`
  markerar kvarvarande placeholder-contact som `"default"` i stället
  för `"brief"`. Wizard och scrape vinner fortfarande över både
  placeholder och brief. Resolvern sätter också
  `operatorReviewRequired=True` när något contact-fält faktiskt landar
  med `"default"` source, så review-flaggan matchar B133-varningen.
  Källa: Viewser-overlay-E2E Scout Case 3a / Fynd 1, 2026-05-19.
  Fix: `ca43588`. Test:
  `tests/test_discovery_resolver.py::test_apply_contact_fields_sets_default_for_placeholder_phone`,
  `tests/test_discovery_resolver.py::test_apply_contact_fields_keeps_brief_when_value_is_real`,
  `tests/test_discovery_resolver.py::test_resolve_discovery_field_sources_distinguish_placeholder`,
  `tests/test_discovery_resolver.py::test_generate_writes_discovery_decision_to_meta_sidecar`.

- **`B136` Medel** (stängd 2026-05-19, follow-up placeholder recompute mot post-merge contact) -
  PR #45 (B135) stängde fieldSources-felaktigheten för init-flödet, men
  retroaktiva reviews (composer-2.5 + lokala modeller) flaggade att
  `scripts/prompt_to_project_input.py` skickade `candidate_placeholder_contact_fields`
  från `site_brief_to_project_input` direkt vidare till `resolve_discovery`.
  I follow-up-läge ersätts `project_input` av `merge_followup_project_input`
  som bevarar previous `contact` byte-stabilt, så candidate-listan från
  ny brief-kandidat kunde flagga real v1-värden som placeholder och få
  `_apply_contact_fields` att markera dem som `"default"` i `fieldSources`
  + trigga `operatorReviewRequired=True` utan fog. **Fix:** `generate()`
  beräknar nu en pre-resolve `pre_resolve_placeholder_fields` via
  `_recompute_placeholder_contact_fields(project_input.get("contact"),
  pre_resolve_language)` mot post-merge state, och skickar listan vidare
  till `resolve_discovery(..., placeholder_fields=...)` istället för
  candidate-listan. `_recompute_placeholder_contact_fields`-helpern är
  samma som B133-flödet kör post-resolve för meta-sidecaren, så pre- och
  post-resolve recompute använder samma värdebaserade jämförelse mot
  B88-defaults. `pre_resolve_language` föredrar `project_input["language"]`
  (bevaras av `merge_followup_project_input`) framför den prompt-detekterade
  så svensk v1 + engelsk följdprompt fortsätter jämföra mot rätt språks
  defaults. Tuple-unpacking från `site_brief_to_project_input` bevarad
  med `_`-prefix så kontraktet håller.   Källa: PR #45 retroaktiv composer-2.5
  + lokal-modell-review 2026-05-19. Fix: `895d80b` (direkt-main, ej PR;
  ruff-fix `6fe04ef` följde). Test:
  `tests/test_prompt_to_project_input.py::test_followup_with_discovery_recomputes_placeholder_fields_against_merged_contact`.

- **`B131` Medel** (stängd 2026-05-19, capability alias dedup) -
  `_resolve_capabilities` dedupade tidigare `requestedCapabilities`
  med exakt strängmatch. När wizarden mappade `Bokning online` till
  resolverns lokala canonical slug `booking` och briefModel samtidigt
  returnerade aliaset `online-booking` hamnade båda i listan, vilket
  gav en extra `capability-unknown` på alias-slugen. Fixen lägger en
  lokal `_CAPABILITY_ALIASES`-map i
  `packages/generation/discovery/resolve.py` och normaliserar varje
  slug före `seen`-lookup så aliasen `online-booking` → `booking`,
  `webshop`/`online-shop` → `ecommerce`, `newsletter` →
  `newsletter-subscribe` och `contact` → `contact-form` dedupas mot
  samma canonical slug. Governance-flytt till aliases-array i
  `capability-map.v1.json` lämnas till framtida ADR-sprint.
  Källa: Viewser-overlay-E2E Scout case 2, 2026-05-19. Fix:
  `2901e4e`. Test:
  `tests/test_discovery_resolver.py::test_resolve_capabilities_dedups_via_alias`,
  `tests/test_discovery_resolver.py::test_resolve_capabilities_preserves_unknown_slug_when_no_alias`,
  `tests/test_discovery_resolver.py::test_resolve_capabilities_alias_keeps_priority_source`.

- **`B132` Medel** (stängd 2026-05-19, page-intent warning-only) -
  wizardens `mustHave` kunde välja route-bärande sidor som scaffoldens
  `routePlan` inte bygger, utan någon varning i `site-plan.json` eller
  `build-result.json`. Exempel: `local-service-business` bygger bara
  `/`, `/tjanster`, `/om-oss` och `/kontakt`, medan wizard-val som
  `"Bildgalleri"` och `"Karta / Hitta hit"` implicerar `/galleri`
  respektive `/karta`. Effekten var en tyst mindre sajt än operatören
  valt. **Fix:** `packages/generation/planning/plan.py` emitterar nu
  `pageIntentWarnings` i Site Plan för route-hints som saknas i
  route-planen. `scripts/prompt_to_project_input.py` sparar wizardens
  `mustHave` som `wizardMustHave` i meta-sidecaren, och
  `scripts/build_site.py` skickar signalen vidare till planfasen samt
  speglar varningarna i `build-result.json`. Ingen route-emission,
  scaffold-route eller page-renderer ändrades. Källa: operatörs-
  verifierat Viewser-overlay-fynd 2026-05-19. Fix: `104e480`.
  Test:
  `tests/test_page_intent.py::test_page_intent_warns_when_wizard_must_have_not_in_routes`,
  `tests/test_page_intent.py::test_page_intent_silent_when_must_have_matches_routes`,
  `tests/test_page_intent.py::test_page_intent_silent_when_must_have_has_no_route_hint`,
  `tests/test_page_intent.py::test_build_result_carries_page_intent_warnings_without_extra_routes`.

- **`B133` Medel** (stängd 2026-05-19, Viewser-overlay-E2E-Scout
  Case 3a follow-up + Codex P2-review-hardening) -
  `scripts/prompt_to_project_input.py:_placeholder_contact`
  fyllde i B88-fallback-strängar (`"+46 8 000 00 00"`,
  `"kontakt@example.se"`, `"Adress lämnas på förfrågan"`) i Project
  Input.contact när briefModel returnerade tomma kontaktfält OCH
  operatören inte fyllt fälten i wizarden OCH scrape inte kördes.
  Discovery Resolver markerade då fieldSources["contact.phone"]="brief"
  eftersom värdet var icke-tomt — tekniskt sant men semantiskt fel.
  Effekten var att sajten renderade `+46 8 000 00 00` /
  `kontakt@example.se` / `Adress lämnas på förfrågan` publikt utan
  någon signal till operatör att kontakt-fälten var platshållare.
  Verifierat live i Scout Case 3a 2026-05-19 (1753skincare-prompten
  utan scrape eller manuella kontaktfält, snitt 6.6/10 där dummy
  contact drog ner copyConcrete + branchCredibility två poäng).
  **Fix:** `_placeholder_contact` returnerar nu en tuple
  `(contact_dict, placeholder_fields)` där `placeholder_fields`
  listar vilka contact-block-keys (`phone`, `email`, `addressLines`)
  som fick B88-fallback. `site_brief_to_project_input` propagerar
  listan vidare som andra tuple-element. `generate()` kör
  `_recompute_placeholder_contact_fields` mot final Project Input
  efter wizard/scrape/follow-up-merging (Discovery Resolverns
  vinst-ordning är orörd, inga fieldSources-ändringar) och skriver
  `placeholderContactFields` på meta-sidecaren bara när listan är
  non-empty. `scripts/build_site.py:write_build_result` läser
  listan via `_prompt_meta_placeholder_contact_fields` och lägger
  till `placeholderContactFields` + `placeholderContactMessage`
  ("Contact fields phone, email, addressLines are placeholder
  values - operator must fill these before publishing.") på
  `build-result.json` när non-empty. `apps/viewser/components/run-details-panel.tsx`
  Build-sektion renderar en gulorange varning-badge
  ("⚠ Kontakt-fält är platshållare: phone, email, addressLines.
  Slutanvändaren ser dummy-värden tills operatör fyllt dem.")
  baserad på samma fält. Inga rendering-ändringar i builder —
  fallback-strängarna fortsätter renderas som idag, vi lägger bara
  till en metadata-emitterad warning så operatör ser dem. **Codex
  P2-review-hardening (2026-05-19, samma dag):** (a) `generate()`
  använder nu `project_input["language"]` (preserved av
  `merge_followup_project_input`) istället för den prompt-detekterade
  `language` i `_recompute_placeholder_contact_fields`-anropet — en
  svensk v1 + engelsk följdprompt skulle annars ge false negative
  och tappa varningen trots att svenska placeholder-strängar låg kvar
  i `contact`-blocket; (b) `openingHours` ("Mån-Fre 09:00-17:00" /
  "Mon-Fri 09:00-17:00") läggs till i den spårade fält-setet eftersom
  briefen aldrig levererar schemat och `_placeholder_contact` då alltid
  fyller dummyn — operatör kunde tidigare publicera dummy-öppettider
  vid sidan av telefonen utan signal. Källa:
  `docs/reports/viewser-overlay-e2e-scout-2026-05-19.md` Fynd 1
  i Case 3a + Codex review på PR #39 (commit `6121214656`,
  fynd P2 + P2). Fix: `58b6879` + Codex-hardening-commit. Test:
  `tests/test_prompt_to_project_input.py::test_placeholder_contact_returns_field_list`,
  `tests/test_prompt_to_project_input.py::test_placeholder_contact_omits_filled_fields_from_list`,
  `tests/test_prompt_to_project_input.py::test_site_brief_to_project_input_propagates_placeholder_contact_fields`,
  `tests/test_prompt_to_project_input.py::test_generate_writes_placeholder_contact_fields_to_meta`,
  `tests/test_prompt_to_project_input.py::test_followup_uses_preserved_language_for_placeholder_detection`,
  `tests/test_builder_hardening.py::test_placeholder_contact_fields_helpers_validate_meta_input`,
  `tests/test_builder_hardening.py::test_build_result_surfaces_placeholder_contact_fields_when_present`,
  `tests/test_builder_hardening.py::test_build_result_omits_placeholder_contact_fields_when_empty`,
  `tests/test_viewser_files.py::test_run_details_panel_renders_placeholder_contact_warning`.

- **`B130` Medel** (stängd 2026-05-19, Viewser-overlay-E2E-Scout
  follow-up) -
  `scripts/prompt_to_project_input.py:generate()` beräknade automatisk
  `siteId` från prompten före Discovery Resolver hade resolverat Project
  Input. I wizard-overlayflödet börjar master-prompten med
  `[Operatörens beskrivning]`, så sluggen blev
  `operatorens-beskrivning-<tail>` även när resolverat
  `company.name` var kundnamn som "Atelje Vit Lera" eller
  "Frisörsalongen Tussilago". Källa: Viewser-overlay-E2E-Scout
  2026-05-19, Case 1 Obs 1 + Case 2. **Fix (`88e1296`):**
  `slugify_site_id()` tar nu valfri `company_name`-kwarg och föredrar
  den när den är non-empty efter trim; prompt-fallbacken strippar
  defensivt master-prompt-headern; `generate()` väntar med automatisk
  siteId-beräkning tills efter Project Input + Discovery Resolver och
  synkar därefter `project_input["siteId"]` med meta-sidecarens
  `siteId`. Explicit caller-pinnad `site_id` behålls oförändrad.
  Test:
  `tests/test_prompt_to_project_input.py::test_slugify_site_id_uses_company_name_when_provided`,
  `tests/test_prompt_to_project_input.py::test_slugify_site_id_falls_back_to_prompt_when_company_empty`,
  `tests/test_prompt_to_project_input.py::test_slugify_site_id_strips_master_prompt_header_when_no_company_name`.

- **`B128` Hög** (stängd 2026-05-19, keramik-/e-handel-pass +
  Composer-2.5-review-hardening) -
  `scripts/prompt_to_project_input.py:_customer_safe_planner_note` /
  `_derive_story` blockerade B99-typisk dev-jargong och planner-noter
  men släppte igenom rena svenska/engelska build-imperativ i
  `notesForPlanner` som publik /om-oss-copy. Re-Verifierings-Scout
  2026-05-19 såg `company.story` läsa `"Bygg en liten e-handel på
  svenska för försäljning av keramik med fokus på köpkonvertering."`
  på keramik-caset — operator-/planner-instruktion, inte kundtext.
  B99-blocklistan saknade både imperativ-formerna och tokens som
  `köpkonvertering`/`på svenska`. **Fix (`d1fee90`):** ny
  `_starts_with_planner_imperative()`-guard som avvisar noten när
  första tokenet är en svensk/engelsk build-imperativ (`bygg`,
  `skapa`, `gör`, `generera`, `designa`, `skriv`, `tillverka`,
  `konstruera`, `producera`, `utveckla`, `forma`, `programmera`,
  `rita`, `build`, `create`, `make`, `design`, `write`, `develop`,
  `generate`, `construct`, `produce`, `draft`, plus fraserna
  `lägg upp`, `sätt upp`, `set up`). `_PLANNER_NOTE_BLOCKLIST` får
  också nya tokens (`konvertering`, `köpkonvertering`, `på svenska`,
  `på engelska`, `in english`, `in swedish`). Tredje person presens
  ("Bygger på 25 års erfarenhet ...") fortsätter passera så legitim
  kundcopy inte blockeras. **Hardening:** read-only
  Composer-2.5-review hittade en bypass där ledande icke-bokstavs-
  prefix (`"-Bygg ..."`, `"**Bygg ..."`, `"1. Bygg ..."`) släppte
  imperativen igenom eftersom `re.match(r"[a-zåäöéü]+", stripped)`
  returnerade `None` på första-tecken-icke-bokstav. Hotfix
  strippar en run av ledande icke-bokstavstecken före token-match
  så markdown/list/numeral-wrappade imperativ blockeras identiskt
  med "rena" imperativ-noter. Källa: Re-Verifierings-Scout
  2026-05-19 + Composer-2.5 read-only review. Fix: `d1fee90`
  + hardening-commit. Test:
  `tests/test_prompt_to_project_input.py::test_story_discards_swedish_build_imperative_planner_note`,
  `tests/test_prompt_to_project_input.py::test_customer_safe_planner_note_rejects_build_imperative`,
  `tests/test_prompt_to_project_input.py::test_customer_safe_planner_note_keeps_present_tense_business_copy`,
  `tests/test_prompt_to_project_input.py::test_customer_safe_planner_note_blocks_konvertering_tokens`,
  `tests/test_prompt_to_project_input.py::test_b128_full_pipeline_blocks_keramik_planner_instruction`,
  `tests/test_prompt_to_project_input.py::test_customer_safe_planner_note_rejects_imperative_with_leading_prefix`,
  `tests/test_prompt_to_project_input.py::test_customer_safe_planner_note_keeps_leading_numeral_when_no_imperative`.

- **`B101` Låg** (stängd 2026-05-19, keramik-/e-handel-pass) -
  Hero-CTA "Shoppa nu" på e-handel-case länkade till `/kontakt`
  istället för `/produkter`. `render_home` i `scripts/build_site.py`
  använde `contact_path` som primär CTA-route oavsett
  `_hero_cta_variant`, så texten lovade shop-yta men klicket
  landade på kontakt. **Fix:** ny `_hero_cta_target_path(dossier,
  listing_route, contact_path)`-helper som routar shop-varianten
  till listing-routen när scaffolden faktiskt deklarerar
  `id="products"`. Booking- och quote-varianter fortsätter peka på
  `contact_path`. Shop-varianten faller tillbaka till `contact_path`
  när scaffolden saknar products-route (ingen uppfinning av
  `/produkter` när routen inte finns). Bottom-of-page "Kontakta oss"
  CTA är orörd. Källa: Re-Verifierings-Scout 3 2026-05-18 +
  2026-05-19. Fix: `d1fee90`. Test:
  `tests/test_builder_route_emission.py::test_hero_cta_target_path_routes_shop_variant_to_products`,
  `tests/test_builder_route_emission.py::test_hero_cta_target_path_falls_back_to_contact_when_no_products_listing`,
  `tests/test_builder_route_emission.py::test_hero_cta_target_path_keeps_contact_for_booking_and_quote_variants`,
  `tests/test_builder_route_emission.py::test_render_home_hero_cta_links_to_products_when_shop_variant`,
  `tests/test_builder_route_emission.py::test_render_home_hero_cta_links_to_contact_when_booking_variant`,
  `tests/test_builder_route_emission.py::test_render_home_hero_cta_uses_threaded_contact_path_for_quote_variant`,
  `tests/test_builder_route_emission.py::test_render_home_hero_cta_links_to_threaded_products_path`.

- **`B102` Låg** (stängd 2026-05-19, keramik-/e-handel-pass) -
  `/produkter`-bottom-CTA "Fråga om en beställning" matchade inte
  hero-CTA "Shoppa nu" på e-handel-case. Pre-fix `render_products`
  hade hardcoded `ShoppingBag`-CTA som läste som offerttjänst-
  förfrågan i stället för shop-flöde. **Fix:** ny
  `_commerce_bottom_cta_label(dossier)`-helper med
  `_COMMERCE_BOTTOM_CTA_LABELS`-whitelist (`"Hör av dig för att
  beställa"` / `"Get in touch to order"`). Länken mot kontakt-routen
  behålls eftersom builder MVP saknar checkout, men verbet
  ("beställa"/"order") matchar shop-tonen från hero. Whitelist-
  baserade strängar håller TSX-interpolationen säker utan
  JSX-escape. Källa: Re-Verifierings-Scout 3 2026-05-18 + 2026-05-19.
  Fix: `d1fee90`. Test:
  `tests/test_builder_route_emission.py::test_render_products_bottom_cta_uses_shop_flavoured_label`,
  `tests/test_builder_route_emission.py::test_render_products_bottom_cta_still_links_to_contact`,
  `tests/test_builder_route_emission.py::test_render_products_bottom_cta_localizes_for_english_dossier`,
  `tests/test_builder_route_emission.py::test_commerce_bottom_cta_label_whitelist_is_safe_for_tsx`.

- **`B121` Medel** (stängd 2026-05-19, discovery-integration B121 A–D) -
  discovery-sanningen passerade tidigare fyra lager innan den landade i
  Project Input. **PR A** (PR #34, `70c261b`): canonical resolver
  (`packages/generation/discovery/resolve.py`), taxonomy
  (`governance/policies/discovery-taxonomy.v1.json`), `DiscoveryDecision`/
  `fieldSources` på meta-sidecar, ADR 0024. **PR B** (PR #35,
  `ec32913`): Viewser overlay läser `/api/discovery-options` från
  governance taxonomy; `starterId` blockas i frontend; follow-up utan
  discovery; `scaffoldHint` hint-only. **PR C** (PR #36, `89680fa`):
  Backoffice Discovery Control — mapping-tabell, Doctor error/warning-
  distinktion, graph/impact, dry-run-resolver, gated edit-toggle mot
  `discovery-taxonomy.v1.json` (`06c9d5f` review-fix). **PR D** (PR #37,
  `e3fa67b`): verifierings-smoke mot fyra produktbaseline-prompter —
  alla fyra klarar resolver → Project Input → plan → build via CLI.
  Källa: extern reviewer 2026-05-18 (runda 2) + B121 smoke-rapport.
  Fix: `e3fa67b`. Test:
  `tests/test_discovery_taxonomy.py`,
  `tests/test_discovery_resolver.py`,
  `tests/test_viewser_files.py` (PR B guards),
  `tests/test_backoffice_discovery_control.py` (PR C, 16 tester);
  smoke: `docs/reports/b121-baseline-smoke.md`.

- **`B126` Medel** (stängd 2026-05-18, post-PR-#32 reviewer-fynd 1) -
  `backoffice/asset_graph.py:_compatible_dossier_edges` byggde
  scaffold→dossier-edges som `dossier:{id}`, men `build_graph()`
  registrerar Dossier-noder som `{class}-dossier:{id}` (t.ex.
  `soft-dossier:interactive-game-loop`). Kontrollplanens konsekvensvy
  (`impact_for_node` i `backoffice/impact.py`) matchar på exakt
  `{type}:{id}`-nyckelformat, så edges träffade aldrig sina dossier-
  noder och hela scaffold→dossier-spåret blev blint i impact-vyn.
  Pre-existerande sedan PR #32-cherrypicken (`3338d79` +
  `b636450`). **Fix:** `build_graph()` förberäknar nu
  `dossier_class_by_id`-mapping via befintliga `_dossier_manifests_by_id()`
  och skickar den till `_compatible_dossier_edges`. Edges byggs som
  `{class}-dossier:{id}` när id finns registrerat; saknade id:n
  faller tillbaka till `dossier:{id}`-formen som intentionellt blir
  en orphan-edge — `run_health_checks` fångar den som "okänd Dossier"-
  warning i stället för att tyst slukas. Källa: extern reviewer
  2026-05-18 (post-PR-#32 control-plane review). Fix: `0fe353f`. Test:
  `tests/test_backoffice_asset_graph.py::test_compatible_dossier_edges_match_dossier_node_keys`,
  `tests/test_backoffice_asset_graph.py::test_real_asset_graph_contains_core_edges`
  (uppdaterad till korrekt `soft-dossier:`-nyckelformat).

- **`B127` Medel** (stängd 2026-05-18, post-PR-#32 reviewer-fynd 2) -
  `backoffice/asset_graph.py:run_health_checks` scaffold-loopen
  kontrollerade `if state["status"] == "implemented":` och emitterade
  en "följer inte scaffold-contract fullt ut"-varning **exakt** när
  scaffolden var komplett. `state["missing"]` och
  `state["placeholders"]` är båda tomma per `scaffold_file_state` när
  status är `"implemented"`, så varningen fick alltid en tom
  details-sträng — och faktiska `"incomplete"`/`"placeholder"`-
  scaffolds slapp helt fri. Doctor-vyn signalerade alltså
  inverterat: brus på healthy scaffolds, tystnad på de som var
  trasiga. Pre-existerande sedan PR #32-cherrypicken (`3338d79`).
  **Fix:** flip villkoret till `if state["status"] != "implemented":`
  så Doctor varnar på precis `incomplete` + `placeholder` och tiger
  om `implemented`. Kommentar i koden förklarar varför så nästa
  läsning inte åter ramlar i samma fälla. Källa: extern reviewer
  2026-05-18 (post-PR-#32 control-plane review). Fix: `0fe353f`. Test:
  `tests/test_backoffice_asset_graph.py::test_doctor_warns_on_incomplete_and_placeholder_scaffolds_not_implemented`.

- **`B124` Medel** (stängd 2026-05-18, operatör-rapporterat efter
  B123-fix) - B123 satte `Cross-Origin-Embedder-Policy: credentialless`
  på Viewser-host-sidan, vilket gjorde att host-dokumentet blev
  cross-origin isolated och `SharedArrayBuffer` blev tillgängligt. Men
  Chrome rapporterade i DevTools Issues-panelen "Specify a Cross-Origin
  Embedder Policy to prevent this frame from being blocked" på
  StackBlitz embed-iframen
  (`https://stackblitz.com/run?embed=1&...`) eftersom **parent-COEP
  räcker inte för iframes**: när host har `COEP: credentialless`
  kräver Chrome att varje embedded iframe antingen själv svarar med
  en COEP-header (`require-corp` eller `credentialless`) ELLER att
  `<iframe>`-elementet bär `credentialless` HTML-attributet.
  StackBlitz embed-respons skickar ingen COEP-header, så iframen
  blockerades trots att host-headers var korrekt satta. **Fix:**
  patcha `document.createElement` runt `sdk.embedProject(...)` i
  `apps/viewser/components/viewer-panel.tsx` så att den `<iframe>`
  StackBlitz SDK skapar internt får
  `setAttribute("credentialless", "")` **innan** den infogas i DOM
  (browsern börjar fetcha iframe:ns src så fort den kommer in i
  dokumentet, så attributet måste vara satt redan vid skapandet, inte
  efteråt). Patchen är scopead via try/finally så
  `document.createElement` återställs så fort embedProject är klar
  — vi muterar aldrig globala API:t längre än SDK:ns iframe-skapande
  kräver. Bakgrund:
  https://developer.chrome.com/blog/iframe-credentialless beskriver
  credentialless-iframe-modellen och varför parent-COEP ensamt inte
  täcker iframe-fallet. Chromium-only (Chrome 110+, Edge, Brave,
  Vivaldi) — Firefox/Safari stöder inte attributet ändå, vilket
  matchar StackBlitz egen Chromium-only-baseline för embedded
  WebContainers. Källa: operatörrapport 2026-05-18 (Chrome DevTools
  Issues-screenshot post-B123-fix). Fix: `5d05e0d`. Test:
  `tests/test_viewser_isolation_headers.py::test_viewer_panel_patches_create_element_for_credentialless_iframe`,
  `tests/test_viewser_isolation_headers.py::test_viewer_panel_restores_create_element_in_finally`,
  `tests/test_viewser_isolation_headers.py::test_viewer_panel_only_tags_iframe_elements`
  (source-lock).

- **`B123` Medel** (stängd 2026-05-18, operatör-rapporterat post-PR-#31) -
  `apps/viewser/next.config.ts` var en tom `NextConfig`-export utan
  `headers()`-funktion. `apps/viewser/components/viewer-panel.tsx`
  embeddar `stackblitz.com` via `sdk.embedProject(..., { template:
  "node" })`, vilket bootar en WebContainer i iframen. WebContainers
  kräver `SharedArrayBuffer`, vilket bara fungerar när host-sidan är
  **cross-origin isolated** (Chrome och övriga Chromium-browsers
  blockerar SAB annars). Utan `Cross-Origin-Embedder-Policy` +
  `Cross-Origin-Opener-Policy` på Next.js-host-sidan visade
  StackBlitz "Unable to run Embedded Project — Looks like this project
  is being embedded without proper isolation headers" i preview-
  canvasen i stället för en faktisk preview. Krav uttryckligen
  dokumenterat sedan v1 i `docs/integrations/webcontainers-notes.md`,
  `docs/architecture/preview-runtime.md` och
  `docs/integrations/stackblitz-research.md`, men aldrig implementerat
  i koden — pre-existerande sedan första `apps/viewser`-commiten.
  **Fix:** lägg till `async headers()` i `next.config.ts` som sätter
  `Cross-Origin-Embedder-Policy: credentialless` +
  `Cross-Origin-Opener-Policy: same-origin` på alla routes
  (`source: "/:path*"`). `credentialless` (inte `require-corp`)
  eftersom vi embeddar tredjeparts-iframe vars
  `Cross-Origin-Resource-Policy`-headers vi inte kan styra; StackBlitz
  egen browser-support-sida dokumenterar `credentialless` som rätt
  embedder-mode för embed-fallet
  (https://developer.stackblitz.com/platform/webcontainers/browser-support#embedding).
  Docs uppdaterade i samma commit för att skilja embed-fallet
  (`credentialless`) från en framtida egen-WebContainer-app
  (`require-corp`). Notera: embedded WebContainers stöds officiellt
  bara i Chromium-baserade browsers — Firefox/Safari ger samma fel
  även med headers korrekt satta. Tidigare negativ source-lock
  (`tests/test_viewser_files.py::test_viewser_does_not_set_global_cross_origin_isolation_headers`,
  införd i `98e8364`) baserades på antagandet att enda möjliga
  COEP-värdet var `require-corp` (vilket hade blockerat StackBlitz-
  iframen) — den togs bort i samma commit och ersattes av en
  positiv lock i `tests/test_viewser_isolation_headers.py` som
  faktiskt kräver att headers finns OCH att värdet är
  `credentialless`. End-to-end-verifierat genom `npm run dev` +
  `Invoke-WebRequest -Method Head http://localhost:3000/` som
  returnerade `Cross-Origin-Embedder-Policy: credentialless` och
  `Cross-Origin-Opener-Policy: same-origin` på root-routen.
  Källa: operatörrapport 2026-05-18 (Konsol-screenshot). Fix:
  `5f23d13`. Test:
  `tests/test_viewser_isolation_headers.py::test_next_config_sets_cross_origin_embedder_policy`,
  `tests/test_viewser_isolation_headers.py::test_next_config_uses_credentialless_for_embed_case`,
  `tests/test_viewser_isolation_headers.py::test_next_config_sets_cross_origin_opener_policy_same_origin`,
  `tests/test_viewser_isolation_headers.py::test_next_config_headers_apply_to_all_routes`
  (source-lock).

- **`B118` Låg** (stängd 2026-05-18, post-PR-#31 reviewer-triage runda 2) -
  `apps/viewser/lib/scrape-runner.ts` timeout-handler kallade
  `child.kill("SIGTERM")` utan SIGKILL-eftersläp. En hängd Python-
  process (väntande på långsam socket, fast i C-extension busy loop,
  eller blockerad i tredjepartslib som ignorerar SIGTERM) skulle
  överleva timeouten och stanna kvar i bakgrunden, ta RAM/fil-handles
  tills manuell intervention. `build-runner.ts` och `prompt-runner.ts`
  har sedan länge samma två-stegs kill-mönster: SIGTERM först, sen
  SIGKILL via en `.unref()`'d 5-sekunders follow-up-timer om
  `child.killed` fortfarande är `false`. scrape-runner var enda
  spawn-helpern som saknade det. **Fix:** kopiera build-runners
  mönster verbatim. Praktisk impact är låg (Python `requests` har
  socket-timeout på lägre nivå), men inkonsekvensen mellan de tre
  runners var en latent maintenance trap. Pre-existerande sedan
  PR #31 (christopher-ui-integration, `0510146`). Källa: extern
  reviewer 2026-05-18 (runda 2). Fix: `df24488`. Test: open (mild
  praktisk konsekvens + matchar redan-testade mönster i build- och
  prompt-runner; källkods-läsning räcker för regression-skydd).

- **`B117` Medel** (stängd 2026-05-18, post-PR-#31 reviewer-triage runda 2) -
  `apps/viewser/lib/asset-store/local.ts:save` sparar SVG-uppladdningar
  orörda (rad 70-75) och `apps/viewser/app/api/asset-preview/route.ts`
  serverar dem med `Content-Type: image/svg+xml`. När operatören
  öppnar `/api/asset-preview?...`-URL:n direkt i en ny flik parsar
  webbläsaren SVG:n som ett dokument och kör `<script>`-block plus
  `onload`/`onclick`-attribut i `localhost:3000`-origin. `<img src=...>`-
  referenser körs däremot inte som dokument så de är fortfarande
  inerta. En malicious SVG som operatören laddar upp av misstag ger
  alltså XSS i samma domän som backoffice-flödet. Routen är
  `assertLocalhost`-gated, så hotmodellen är operator-pivot snarare än
  remote attacker — men en undvikbar foot-gun. **Fix:** sätt
  `Content-Security-Policy: "sandbox allow-same-origin"` på responsen
  när serverad mime är `image/svg+xml`. Sandbox-direktivet skapar
  isolerad browsing-kontext där inline-scripts och event-handlers
  blockeras. `allow-same-origin` behålls så interna asset-referenser
  fortfarande fungerar. Påverkar inte `<img src=...>`-konsumenter
  eftersom de aldrig parsar responsen som dokument. Routen får också
  `X-Content-Type-Options: nosniff` för alla content-types — stoppar
  en "fake JPEG" som faktiskt är HTML från att sniffas och renderas
  som dokument. Pre-existerande sedan PR #31 (christopher-ui-
  integration, `0510146`). Källa: extern reviewer 2026-05-18 (runda 2).
  Fix: `6772a14`. Test: open (route är localhost-gated + manuell
  XSS-verifiering kräver malicious SVG-fixture som inte är värd att
  committa; CSP-headern är källkods-låst genom kommentaren).

- **`B114` Låg** (stängd 2026-05-18, post-PR-#31 reviewer-triage) -
  `apps/viewser/app/api/upload-asset/route.ts` POST-handler kallade
  `await request.formData()` på rad 47 innan storlekscheck mot
  `file.size > MAX_FILE_BYTES` (10 MB) på rad 83. En multi-hundra-MB
  multipart-payload buffrades därför fullt i minnet bara för att
  sedan rejection:as i size-checken. Praktisk konsekvens är mild
  eftersom routen är gated av `assertLocalhost(request)` på rad 42,
  så DoS-vektorn kräver att operatören eller en lokal process redan
  kan tala med loopback. Reviewer flaggade det som "MAX_FILE_BYTES
  vs rå upload" på samma pass som B113. **Fix:** läs
  `Content-Length`-headern före `request.formData()` och rejection:a
  deklarerade payloads större än `MAX_FILE_BYTES * 2` (ger
  multipart-boundary + extra form-field-overhead nära per-fil-gränsen).
  Existing `file.size`-check kvarstår och enforcar exakta 10 MB-per-fil-
  ceilingen för välformade uploads nära tröskeln. Pre-existerande
  sedan PR #31 (christopher-ui-integration, `0510146`). Källa: extern
  reviewer 2026-05-18 (post-PR-#31). Fix: `fe9748e`. Test: open (mild
  praktisk konsekvens + localhost-gated, så enbart källkods-läsning i
  PR-review räcker; manuell verifiering möjlig via stor multipart-
  curl mot lokal dev-server).

- **`B113` Hög** (stängd 2026-05-18, post-PR-#31 reviewer-triage) -
  `scripts/scrape_site.py:fetch_html` kallade
  `requests.get(..., allow_redirects=True, ...)`. `validate_ssrf()`
  kördes bara på den ursprungliga operatör-supplied URL:n, så en
  publik host som 302:ade till en intern adress (AWS metadata
  `169.254.169.254`, loopback `127.0.0.1:8501` Streamlit-backofficen,
  link-local, eller `file:///etc/passwd` via icke-HTTPS-scheman)
  hämtades utan ny SSRF-koll. Klassisk SSRF via redirect chain.
  Reviewer flaggade det som "den skarpaste faktiska buggen" på post-
  PR-#31-passet. **Fix:** följ redirects manuellt, hop-by-hop. Varje
  Location-target går nu genom `validate_ssrf()` + scheme-allowlist
  (`http`/`https` bara) innan nästa request fyrar. Max 5 hops för
  att begränsa runaway redirect-loops. Pre-existerande sedan PR #31
  (christopher-ui-integration, `0510146`). Källa: extern reviewer
  2026-05-18 (post-PR-#31). Fix: `cd03897`. Test:
  `tests/test_scrape_site_ssrf.py::test_fetch_html_blocks_redirect_to_loopback`,
  `tests/test_scrape_site_ssrf.py::test_fetch_html_blocks_redirect_to_link_local_metadata`,
  `tests/test_scrape_site_ssrf.py::test_fetch_html_blocks_redirect_to_file_scheme`,
  `tests/test_scrape_site_ssrf.py::test_fetch_html_follows_public_redirect_chain`,
  `tests/test_scrape_site_ssrf.py::test_fetch_html_caps_redirect_loops`,
  `tests/test_scrape_site_ssrf.py::test_fetch_html_does_not_set_allow_redirects_true`
  (source-lock).

- **`B112` Låg** (stängd 2026-05-18, extern reviewer-triage) -
  `scripts/prompt_to_project_input.py:_product_category_name` joinade
  alla `label.split()`-delar utan separator innan `_derive_company_name`
  appendade `"butik"`. En briefModel-output med
  `servicesMentioned=["handgjord keramik"]` på en e-handel-prompt gav
  därför H1 `"Handgjordkeramikbutik"` i stället för den läsbara svenska
  sammansättningen `"Keramikbutik"`. Reviewer flaggade det som
  "naming för butikskategorier ser skör ut". **Fix:**
  `_product_category_name` plockar nu det avslutande ordet i labeln
  (det grammatiska substantivet) och returnerar bara det, så
  `_derive_company_name` får ett rent ordstem att hänga `"butik"`-
  suffixet på: `"handgjord keramik" -> "Keramik" -> "Keramikbutik"`,
  `"ekologisk mat" -> "Mat" -> "Matbutik"`, `"unika handgjorda
  smycken" -> "Smycken" -> "Smyckenbutik"`. Single-word categories
  fortsätter fungera oförändrat (`"keramik" -> "Keramikbutik"`). Källa:
  extern reviewer 2026-05-18. Fix: `adde45c`. Test:
  `tests/test_prompt_to_project_input.py::test_product_category_name_uses_last_word_for_multi_word_service`,
  `tests/test_prompt_to_project_input.py::test_product_category_name_preserves_single_word_categories`,
  `tests/test_prompt_to_project_input.py::test_ecommerce_company_name_produces_clean_compound_for_multi_word_brief`,
  `tests/test_prompt_to_project_input.py::test_ecommerce_company_name_uses_product_category_when_name_missing`
  (B106-regressionen kvarstår oförändrad).

- **`B109` Låg** (stängd 2026-05-18, post-B108 reviewer-hotfix) -
  `scripts/build_site.py:_npm_install_inputs_changed` fångade bara
  `OSError` och `json.JSONDecodeError` när target `package.json` lästes
  via `load_json` (som öppnar filen med `encoding="utf-8"`). En target
  med ogiltig UTF-8 (manuell edit, korrupt download, fel encoding-write
  i en framtida `apps/viewser`-väg) raisade `UnicodeDecodeError`, vilket
  propagerade hela vägen ut ur `copy_starter()` och kraschade builden i
  stället för det dokumenterade safe-fallback-beteendet "force reinstall".
  Inkonsekvent jämfört med `(OSError, json.JSONDecodeError)`-grenen som
  redan finns. Källa: extern reviewer (Cursor Bugbot-stil)
  2026-05-18 mot baseline `1c68035`. **Fix:** lägg till
  `UnicodeDecodeError` i except-tuple så alla tre läsningsfel ger samma
  fallback `return True` (force reinstall). Source-pkg-läsningen lämnas
  orörd avsiktligt — source-starters är repo-kontrollerade och korrupt
  source ska larma högt. Fix: `fa277a1`. Test:
  `tests/test_builder_hardening.py::test_npm_install_inputs_changed_falls_back_when_target_has_invalid_utf8`,
  `tests/test_builder_hardening.py::test_copy_starter_drops_node_modules_when_target_package_json_has_invalid_utf8`.

- **`B108` Medel** (stängd 2026-05-18, starter dependency hardening) -
  genererade `marketing-base`/`commerce-base`-sajter ärvde
  `next@16.2.5` och sårbar transitiv `postcss`, vilket gav
  `npm audit`-fynd i nya output-mappar. Befintliga output-mappar kunde
  dessutom behålla gammal `node_modules/` efter starter-bumps.
  **Fix:** `marketing-base` och `commerce-base` matchar nu den redan
  hårdnade `docs-base`/`portfolio-base`-baslinjen (`next@16.2.6`,
  `eslint-config-next@16.2.6`, `postcss@^8.5.10` och
  `overrides.next.postcss=8.5.10`). `copy_starter()` tar bort
  `node_modules/` när dependency-relevanta package-inputs ändras så
  nästa build installerar om. Fix: `1c68035`. Test:
  `tests/test_builder_hardening.py::test_all_starters_use_audited_next_postcss_baseline`,
  `tests/test_builder_hardening.py::test_copy_starter_drops_node_modules_when_dependencies_change`.
- **`B105` Medel** (stängd 2026-05-18, demo-baseline-fix 1E) -
  `_service_summary` i `scripts/prompt_to_project_input.py` skrev
  publik filler-copy som `"{Label} - kontakta oss för mer information."`,
  vilket Re-Verifierings-Scout 4 såg på alla fyra demo-case och särskilt
  drog ner konkret copy/branschpassning för elektriker-caset. **Fix:**
  `_service_summary()` och `_placeholder_services()` tar nu
  `business_type` och använder branschspecifika summaries/labels, t.ex.
  `Elservice` + "Tydlig hjälp med elarbeten, felsökning och nästa steg."
  för elektriker och sortimentscopy för e-handel. Fix: `bc43eb8`. Test:
  `tests/test_prompt_to_project_input.py::test_service_summary_uses_business_specific_copy_for_empty_brief`,
  `tests/test_prompt_to_project_input.py::test_service_summary_uses_business_specific_copy_for_stub_service`.
- **`B106` Låg** (stängd 2026-05-18, demo-baseline-fix 1E) -
  e-handel utan explicit `companyName` föll tillbaka till generic
  `Webbshop`, vilket gav svag H1 på keramik-caset. **Fix:**
  `_derive_company_name()` tar nu `services_mentioned` och använder
  första verkliga produktkategori som e-handelsnamn när businessType är
  commerce, t.ex. `keramik` → `Keramikbutik`. Fix: `bc43eb8`. Test:
  `tests/test_prompt_to_project_input.py::test_ecommerce_company_name_uses_product_category_when_name_missing`.
- **`B107` Låg** (stängd 2026-05-18, demo-baseline-fix 1E) -
  briefModel varierade mellan `naprapat-clinic`, `naprapath-clinic` och
  svensk `naprapatklinik`; B100 fungerade men var beroende av många
  explicita strängar. **Fix:** `scripts/build_site.py` har nu
  `_normalize_business_type()` för CTA-fallbacken (lowercase, strip,
  `naprapat*`/`naprapath*` → `naprapat-clinic`, `webshop`/`webbshop`
  → `e-commerce`, etc.). Fix: `bc43eb8`. Test:
  `tests/test_builder_route_emission.py::test_hero_cta_label_uses_booking_business_type_fallback`.

- **`B99` Hög** (stängd 2026-05-18, demo-baseline-fix 1D) -
  `_derive_story` i `scripts/prompt_to_project_input.py` skrev publik
  platshållartext ("Byt ut den här texten...") på `/om-oss` och kunde
  använda `notesForPlanner` utan att skilja intern planner-orientering
  från kundsäker copy. **Fix:** `_customer_safe_planner_note()` tillåter
  bara rena, kundvända notes; intern meta (`prompt`, `brief`, `website`,
  `webbplats`, `focus on`, etc.) faller tillbaka till neutral publik
  story utan operator-instruktioner. Fix: `9cc3067`. Test:
  `tests/test_prompt_to_project_input.py::test_story_constructs_placeholder_when_notes_missing`,
  `tests/test_prompt_to_project_input.py::test_story_uses_customer_safe_notes_for_planner`,
  `tests/test_prompt_to_project_input.py::test_story_discards_internal_notes_for_planner`.
- **`B100` Medel** (stängd 2026-05-18, demo-baseline-fix 1D) -
  `_hero_cta_label` i `scripts/build_site.py` byggde CTA-variant bara
  från `scaffoldId` + `conversionGoals`, vilket lämnade korta
  booking-prompter (`frisör Göteborg`, `naprapatklinik Stockholm`) på
  quote-default när briefModel returnerade `conversionGoals=[]`.
  **Fix:** `_hero_cta_variant()` prioriterar explicit `conversionGoals`
  först, faller sedan tillbaka på `company.businessType` (inkl.
  `hair-salon`, `frisör`, `naprapat-clinic`, `naprapath-clinic`,
  `naprapatklinik`, `dentist`, commerce-varianter) och sist på
  `scaffoldId`. Smoke 2026-05-18 verifierade `Boka tid` för frisör +
  naprapat och `Shoppa nu` för e-handel. Fix: `9cc3067`. Test:
  `tests/test_builder_route_emission.py::test_hero_cta_label_uses_booking_business_type_fallback`,
  `tests/test_builder_route_emission.py::test_hero_cta_label_uses_shop_business_type_fallback`,
  `tests/test_builder_route_emission.py::test_hero_cta_label_explicit_goals_beat_business_type_fallback`.
- **`B103` Medel** (stängd 2026-05-18, demo-baseline-fix 1D) -
  `_derive_tagline` i `scripts/prompt_to_project_input.py` föll
  tillbaka till "Lokal {label} i {city}", vilket upprepade H1 på korta
  prompts. **Fix:** nya branschspecifika tagline-mappar för sv/en
  ger konkreta, kundvända vinklar (t.ex. "Klippning, färg och styling
  med enkel bokning", "Behandling och rådgivning med enkel bokning",
  "Utvalt sortiment med enkel beställning") och service-fallbacken
  används först när businessType inte är känd. Fix: `9cc3067`. Test:
  `tests/test_prompt_to_project_input.py::test_derive_tagline_builds_from_business_type_and_location`,
  `tests/test_prompt_to_project_input.py::test_derive_tagline_booking_businesses_do_not_repeat_h1`,
  `tests/test_prompt_to_project_input.py::test_tagline_never_uses_notes_for_planner`.
- **`B104` Låg** (stängd 2026-05-18, demo-baseline-fix 1D) -
  `render_about` använde inte B95-helpern `_location_is_country_only`,
  så `/om-oss` kunde fortfarande visa "Områden vi arbetar i: Sverige"
  för country-only e-handel även när hero redan suppressade ortstaget.
  **Fix:** `render_about` bygger service-area-sektionen villkorat och
  omittar den när `city == country`, men behåller den för riktiga
  serviceområden. Fix: `9cc3067`. Test:
  `tests/test_builder_route_emission.py::test_render_about_omits_service_areas_when_country_only`,
  `tests/test_builder_route_emission.py::test_render_about_keeps_service_areas_for_real_city`.

- **`B88` Hög** (stängd 2026-05-18, demo-baseline-fix 1C) -
  `scripts/prompt_to_project_input.py:_placeholder_contact()` skrev
  dev-jargong i publika kontaktfält
  (`"Address placeholder - update Project Input"` /
  `"Adress saknas - uppdatera Project Input"`), vilket syntes på
  alla fyra demo-case i re-Verifierings-Scout 2026-05-15 som rå
  text i `<address>`-taggen på `/kontakt`. Kategoriöverlapp med B61
  ("intern arbetscopy -> publik yta") men på kontaktytan. **Fix:**
  default-placeholdern är nu en branschneutral fras
  (`"Adress lämnas på förfrågan"` på sv, `"Address available on
  request"` på en) som läser acceptabelt för en riktig besökare;
  operatören kan fortfarande skriva över via Project Input. Schema-
  constraint `addressLines minItems=1 + items minLength=1` förbjuder
  tom sträng, så signaleringen sker via copy istället för omit-
  render. Fix: `b5ee710`. Test:
  `tests/test_prompt_to_project_input.py::test_placeholder_contact_address_has_no_dev_jargon_on_swedish_brief`,
  `tests/test_prompt_to_project_input.py::test_placeholder_contact_address_has_no_dev_jargon_on_english_brief`,
  `tests/test_prompt_to_project_input.py::test_placeholder_contact_address_prefers_brief_value_over_fallback`.

- **`B94` Medel** (stängd 2026-05-18, demo-baseline-fix 1C) -
  `scripts/build_site.py:render_about` renderade alltid "Teamet"-
  rubrik + tom `<ul>` även när `company.team=[]`, vilket syntes på
  alla fyra demo-case i re-Verifierings-Scout 2026-05-15. Samma
  pattern som B66 (conditional section render). Prompt-genererade
  Project Inputs populerar inte team idag, så sektionen blev
  alltid tom. **Fix:** `render_about` bygger ett `team_section`-
  fragment bara när `team` har medlemmar; annars omittas hela
  blocket (rubrik + grid). Fix: `b5ee710`. Test:
  `tests/test_builder_route_emission.py::test_render_about_omits_team_section_when_team_empty`,
  `tests/test_builder_route_emission.py::test_render_about_omits_team_section_when_team_missing`,
  `tests/test_builder_route_emission.py::test_render_about_keeps_team_section_when_members_present`.

- **`B95` Medel** (stängd 2026-05-18, demo-baseline-fix 1C) -
  `_normalize_location_hint` i
  `scripts/prompt_to_project_input.py` fångade inte att briefModel
  returnerade `locationHint="Sverige"` (utan stad) på
  `liten e-handel som säljer keramik`-prompten i re-Verifierings-
  Scout 2026-05-15. Värdet passerade som `location.city="Sverige"`
  och renderades som ortstag i hero. Bredare variant av B91 -
  Sverige-på-city-fältet specifikt, inte bara `"Sweden"`-translit.
  **Fix:** ny `_COUNTRY_NAME_LOCATION_HINTS`-set (Sweden, Sverige,
  Norway, Norge, Denmark, Danmark, Finland, Iceland, Island) som
  `_normalize_location_hint` använder för att returnera `None`
  oavsett språk när hintet matchar ett landnamn.
  `_placeholder_location` faller då tillbaka till `city == country`
  som country-only-markör, och `scripts/build_site.py` får ny
  `_location_is_country_only`-helper plus en conditional ortstag-
  span i `render_home`. Ortstaggen renderas inte när markern är
  satt; riktiga städer fortsätter rendera ortstag oförändrat.
  Fix: `b5ee710`. Test:
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_drops_english_country_names`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_drops_swedish_country_names`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_drops_other_nordic_country_names`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_preserves_real_city`,
  `tests/test_prompt_to_project_input.py::test_swedish_brief_with_country_location_uses_country_only_marker`,
  `tests/test_prompt_to_project_input.py::test_english_brief_with_country_location_uses_country_only_marker`,
  `tests/test_builder_route_emission.py::test_render_home_omits_hero_location_tag_when_country_only`,
  `tests/test_builder_route_emission.py::test_render_home_keeps_hero_location_tag_when_real_city`,
  `tests/test_builder_route_emission.py::test_render_home_country_only_marker_is_case_insensitive`.

- **`B96` Medel** (stängd 2026-05-18, demo-baseline-fix 1C) -
  Hero-CTA `"Begär offert"` var hardcoded i
  `scripts/build_site.py:render_home` och CTA i `render_services`
  oavsett `scaffoldId` / `conversionGoals`. För `ecommerce-lite` +
  `conversionGoals=["product_purchase", "shop_visit"]` blev CTA
  fortfarande "Begär offert", vilket bröt trovärdighet på
  e-handel-case (3.9/10 i re-Scout) och passade dåligt för
  frisör/naprapat där "boka tid" är rätt verb. **Fix:** ny
  `_hero_cta_label(dossier)`-helper som routar genom
  `_hero_cta_variant`: shop > booking > quote-prioritet. Värdena
  är hämtade ur `_HERO_CTA_VARIANT_LABELS`-whitelist
  (`"Shoppa nu" / "Shop now"`, `"Boka tid" / "Book a time"`,
  `"Begär offert" / "Request a quote"`) så strängen är säker att
  interpolera in i TSX utan JSX-escape. `render_home` (hero) och
  `render_services` (bottom-CTA) använder båda samma helper.
  Default-fallbacken är fortfarande "Begär offert" så
  painter-palma-stilen demos inte regresserar.
  Fix: `b5ee710`. Test:
  `tests/test_builder_route_emission.py::test_hero_cta_label_defaults_to_quote_when_no_signals`,
  `tests/test_builder_route_emission.py::test_hero_cta_label_uses_shop_verb_for_ecommerce_scaffold`,
  `tests/test_builder_route_emission.py::test_hero_cta_label_uses_shop_verb_for_purchase_conversion_goal`,
  `tests/test_builder_route_emission.py::test_hero_cta_label_uses_booking_verb_for_booking_conversion_goal`,
  `tests/test_builder_route_emission.py::test_hero_cta_label_shop_beats_booking_in_priority`,
  `tests/test_builder_route_emission.py::test_render_home_emits_scaffold_aware_hero_cta_for_ecommerce`,
  `tests/test_builder_route_emission.py::test_render_home_emits_booking_hero_cta_for_booking_business`,
  `tests/test_builder_route_emission.py::test_render_home_falls_back_to_quote_cta_for_default_service_business`,
  `tests/test_builder_route_emission.py::test_render_services_uses_same_hero_cta_label_as_home`.

- **`B64` Hög** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `SiteBrief` (`packages/generation/brief/extract.py`)
  saknar `company_name`-fält. Prompts som "Skapa hemsida för Volt & Co
  i Malmö" får H1 "Elektriker i Malmö" eftersom
  `_derive_company_name()` bara läser `businessTypeGuess` +
  `locationHint`. Riktigt företagsnamn extraheras inte. Kräver
  brief-schema-bump + ADR. Fix: `885431b` (ADR 0022 + Site Brief `companyName`). Test: `tests/test_prompt_to_project_input.py::test_site_brief_company_name_overrides_derived_h1`, `tests/test_extract_site_brief.py::test_site_brief_to_artifact_real_run`.

- **`B65` Hög** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  Kontaktuppgifter är alltid placeholder
  (`+46 8 000 00 00`, `kontakt@example.se`, "Adress saknas"). Brief
  saknar contact_phone/email/address-fält och `_placeholder_contact()`
  returnerar fasta värden. Kräver brief-schema-bump + ADR (samma som
  B64). Fix: `885431b` (ADR 0022 + Site Brief contact fields). Test: `tests/test_prompt_to_project_input.py::test_site_brief_contact_fields_override_placeholders`, `tests/test_extract_site_brief.py::test_site_brief_to_artifact_real_run`.

- **`B66` Medel** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `scripts/build_site.py:930-935` "Varför oss"-
  sektion renderades alltid trots tom `trustSignals`. `<h2>Varför oss</h2>`
  var hårdkodad i `render_home`; när `trustSignals=[]` (alltid efter
  prompt-flödet idag) blev det stor rubrik + tom `<ul>`. Fix:
  conditional rendering eller fyll med generic-by-business-type-
  fallback. Fix: `885431b`. Test: `tests/test_builder_route_emission.py::test_render_home_omits_trust_section_when_trust_signals_empty`.

- **`B69` Hög** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  Quality Gate route-scan fick bara `required_routes()`
  (subset där `required: true`), men `write_pages` emitterar alla
  `defaultRoutes`. Scaffolden `local-service-business/routes.json`
  har `about` (`/om-oss`) som `required: false`. Resultat: en
  `/om-oss/page.tsx` utan default export eller med trasig syntax
  kunde landa på `main` utan att route-scan flaggade det. Quality Gate
  rapporterade `ok` trots brott mot eget kontrakt. Källa: builder-
  renderer-bug-sweep 2026-05-15. Bevis: `scripts/build_site.py:1327`
  (`required_routes()` filtrerade på `required=True`),
  `packages/generation/quality_gate/gate.py:81-94` (kommentar
  bekräftade att gate tog `required`-subsetet). Fix: `885431b` (route-scan receives all emitted routes; aggregate severity unchanged). Test: `tests/test_builder_route_emission.py::test_non_required_about_route_is_scanned_for_default_export`, `tests/test_builder_route_emission.py::test_build_route_scan_receives_all_emitted_default_routes`.

- **`B70` Hög** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `apps/viewser/lib/localhost-guard.ts:5-10` parsade
  Host-headern fel för IPv6 localhost. `hostHeader.split(":")[0]` på
  `"[::1]:3000"` gav `"["` (alla `:` splittade, inklusive de inom
  bracket); efterföljande `replace(/^\[|\]$/g, "")` på `"["` gav tom
  sträng → `isAllowedHost` returnerade `false` → 403. IPv6 localhost
  blockades alltid trots att `"::1"` fanns i `LOCAL_HOST_NAMES`. Källa:
  viewser-app-bug-sweep 2026-05-15. Fix: parsa Host enligt RFC 3986
  (separera `[ipv6]:port` med regex). Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_localhost_guard_parses_bracketed_ipv6_hosts`.

- **`B73` Medel** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  Tagline-fallback innehöll "Project Input-filen"
  dev-jargong i den fallback-gren som triggade när både businessType
  och location saknades. Samma slag som B61 men på en kvarvarande edge-
  fallback i `scripts/prompt_to_project_input.py:_derive_tagline`.
  Källa: brief-pipeline-bug-sweep 2026-05-15. Fix: `885431b` (docstring + byte-stability lock; semantic patching deferred to Project DNA). Test: `tests/test_prompt_to_project_input.py::test_followup_merge_keeps_story_tagline_and_tone_byte_stable`, `tests/test_prompt_to_project_input.py::test_followup_merge_docstring_describes_conservative_semantics`.

- **`B74` Medel** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `scripts/dev_generate.py:365-393` mock-pipeline
  anropade `produce_codegen_artefakt(routes_written=[])`. Codegen-
  manifestet skrev då noll routes för mock-driven trots att real
  build alltid spelar in dem. Artefakt-konsumenter fick inkonsekvent
  bild av vad mocken täckte. Källa: builder-renderer-bug-sweep
  2026-05-15. Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_list_runs_slices_before_reading_build_results`.

- **`B76` Medel** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `apps/viewser/lib/runs.ts:203-211 readRunArtefacts`
  och `apps/viewser/components/run-details-panel.tsx:531-544` saknade
  `site-plan.json`. Bara `build-result`, `quality-result`,
  `repair-result`, `site-brief` lästes. Plan-fas-krascher blev svåra
  att diagnostisera i RunDetailsPanel. Källa: viewser-app-bug-sweep
  2026-05-15. Fix: `885431b`. Test: `tests/test_prompt_to_project_input.py::test_derive_tagline_falls_back_when_brief_is_empty`.

- **`B77` Medel** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `scripts/build_site.py:mount_dossier_components`
  upptäckte filnamnskollisioner bara mellan dossiers, inte mellan
  dossier och starter. En dossier med `components/Navbar.tsx` skrev
  tyst över starter-ens egen `components/Navbar.tsx`. Docstringen
  lovade "hard collision error" men det gällde bara dossier-vs-
  dossier. Källa: builder-renderer-bug-sweep 2026-05-15. Fix: `885431b`. Test: `tests/test_dev_generate.py::test_dev_generate_codegen_manifest_includes_planned_routes`.

- **`B78` Hög-säkerhet** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `apps/viewser/lib/build-runner.ts:34-51`
  `assertDossierPathAllowed` använde `path.resolve()` som INTE följde
  symlinks. En symlink under `data/prompt-inputs/` som pekade på en
  fil utanför whitelist passerade kontrollen. Källa: viewser-app-bug-
  sweep 2026-05-15. Fix: `885431b`. Test: `tests/test_project_input_schema.py::test_project_input_schema_rejects_unknown_fields`.

- **`B79` Låg** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `scripts/prompt_to_project_input.py:726-734`
  `selectedDossiers.rationale` var alltid engelska även när
  `language="sv"`. Språkblandning i artefakter. Källa: brief-
  pipeline-bug-sweep 2026-05-15. Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_run_details_bundle_and_panel_include_site_plan`.

- **`B80` Låg** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `apps/viewser/lib/prompt-runner.ts:137-143`
  stdout-parsing använde `match(/^siteId:\s*(.+)$/m)` - första match
  vann. Om Python skrev flera rader som matchade togs fel värde.
  Källa: viewser-app-bug-sweep 2026-05-15. Fix: `885431b`. Test: `tests/test_dossier_mounting.py::test_dossier_component_cannot_shadow_starter_component`.

- **`B81` Låg** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `brief.language` returnerades av briefModel utan
  enum-validering. JSON-schemat krävde bara `minLength: 2`. Modell-
  output `language="zz"` skulle passerat och drivit fel språkgren.
  Källa: brief-pipeline-bug-sweep 2026-05-15. Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_build_runner_realpaths_dossier_override_before_whitelist`.

- **`B82` Låg** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `packages/generation/quality_gate/checks.py:131-136`
  typecheck-filter truncerade findings till rader med `"error TS"`
  eller substring `".ts"`. Wrapper-diagnostik utan markörer filtrerades
  bort. Operatör såg failed status med tom findings-lista. Källa:
  builder-renderer-bug-sweep 2026-05-15. Fix: `885431b`. Test: `tests/test_prompt_to_project_input.py::test_selected_dossiers_rationale_matches_project_language`.

- **`B84` Låg** (stängd 2026-05-15, demo-baseline-fix 1B + bug-sweep PR #28) -
  `apps/viewser/lib/project-inputs.ts:85-93`
  `listProjectInputs` konkatinerade `examples/` och `data/prompt-inputs/`
  utan deduplicering på `siteId`. Samma `siteId` i båda gav React-
  key-kollision i ProjectInputPicker. Källa: viewser-app-bug-sweep
  2026-05-15. Fix: `885431b`. Test: `tests/test_prompt_to_project_input.py::test_service_slug_collisions_get_deterministic_suffixes`.

- **`B61` Hög** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) -
  `notes_for_planner` läckte som customer-facing copy på `/om-oss`,
  som `company.tagline` och som dev-jargong i service summaries efter
  demo-baseline-fix 1A. Källa: verifierings-Scout 2026-05-15.
  `scripts/prompt_to_project_input.py:_derive_story` föredrog
  `brief.notesForPlanner` som story-fallback, men briefModel skriver
  fältet på engelska som intern Phase 2-orientering ("Likely a Swedish
  electrician website targeting Malmö; prompt is minimal, so keep
  scope conservative and local."). Samma sträng landade också i
  `company.tagline` via `(notes or tagline_default)`-mönstret i
  `site_brief_to_project_input`. Plus `_service_summary` skrev
  `Justera Project Input för att förbättra texten` på rendered
  service grid (svensk dev-jargong) och `_placeholder_services` hade
  motsvarande "platshållare som genererats från din prompt"-fras.
  **Fix:** `_derive_story` ignorerar nu `notes_for_planner` helt
  (parametern kvar på signaturen för bakåtkompatibilitet, men aldrig
  använd); ny `_derive_tagline`-helper bygger taglinen från
  `businessTypeGuess` + `locationHint`; `_service_summary` returnerar
  neutral kundsvenska (`Konsultation - kontakta oss för mer
  information.`); `_placeholder_services` motsvarande engelska/svenska
  varianter. Smoke-verifierat med real briefModel: `elektriker Malmö`
  ger story `Vi är en elektriker i Malmö. Byt ut den här texten...`,
  tagline `Lokal elektriker i Malmö`, service summary `Konsultation -
  kontakta oss för mer information.` Fix: `d99f8ba`. Test:
  `tests/test_prompt_to_project_input.py::test_story_never_uses_notes_for_planner`,
  `tests/test_prompt_to_project_input.py::test_tagline_never_uses_notes_for_planner`,
  `tests/test_prompt_to_project_input.py::test_service_summaries_do_not_leak_dev_jargon`,
  `tests/test_prompt_to_project_input.py::test_placeholder_services_summary_is_customer_friendly`,
  `tests/test_prompt_to_project_input.py::test_full_pipeline_locks_no_planner_jargon_for_scout_prompt`,
  `tests/test_prompt_to_project_input.py::test_derive_tagline_builds_from_business_type_and_location`,
  `tests/test_prompt_to_project_input.py::test_derive_tagline_falls_back_when_brief_is_empty`,
  `tests/test_prompt_to_project_input.py::test_story_constructs_placeholder_when_notes_missing`
  (uppdaterad: låser nu frånvaron av "Justera Project Input"-jargong).
  **Scope-förtydligande:** stängningen gäller notesForPlanner/story/tagline/
  service-summary-ytorna i 1A-hotfixen; relaterade öppna poster i samma
  kategori är B65, B68 och B88.

- **`B62` Hög** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) -
  `packages/generation/brief/extract.py:detect_language` slog fel på
  korta svenska prompts utan stop-ord. `SWEDISH_HINTS` är en hårdkodad
  lista på ~20 vanliga ord; prompts som "frisör Göteborg" eller
  "naprapatklinik Stockholm" har inget av dessa tokens, så language
  detekterades som "en" och hela sajten genererades på engelska ("Hair
  salon in Göteborg", `country=Sweden`). Verifierat på 2 av 4
  Verifierings-Scout-case 2026-05-15. **Fix:** ny cascading heuristik:
  (1) SWEDISH_HINTS-match → sv (samma som tidigare); (2) ENGLISH_HINTS-
  match (ny lista med ~30 engelska stopord och website-shaped verbs)
  → en; (3) någon token har å/ä/ö → sv (fångar `frisör Göteborg`);
  (4) default sv (operatörspopulation ~95% svensktalande, fångar
  `naprapatklinik Stockholm`). Cascade-ordningen sätter ENGLISH_HINTS
  FÖRE å/ä/ö-checken så `electrician website in Malmö` fortsatt blir
  `en` (Malmö har ö men prompten har stark engelsk signal). Plus ny
  `_normalize_location_hint`-helper i `prompt_to_project_input.py`
  som skriver om `locationHint="Sweden"` till `Sverige` på svenska
  builds, så `location.city` inte landar som engelsk land-namn på en
  svensk sajt. Smoke-verifierat med real briefModel: `frisör Göteborg`
  ger nu `language=sv`, `H1=Frisör i Göteborg`, `country=Sverige`.
  Fix: `d99f8ba`. Test:
  `tests/test_extract_site_brief.py::test_detect_language_short_swedish_prompts_default_to_sv`
  (parametriserad över `frisör Göteborg`, `naprapatklinik Stockholm`,
  `Skapa en hemsida för Volt & Co`, `elektriker Malmö`,
  `tandläkarpraktik`, `yoga`),
  `tests/test_extract_site_brief.py::test_detect_language_english_prompts_with_swedish_chars_stay_en`
  (parametriserad över fyra engelska prompts, inkl. `electrician
  website in Malmö`),
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_translates_country_on_swedish_builds`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_preserves_english_country`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_preserves_real_city`,
  `tests/test_prompt_to_project_input.py::test_swedish_brief_with_country_location_renders_swedish_city`.
  **Scope-förtydligande:** stängningen gäller language-cascaden och
  `Sweden -> Sverige`-normalisering i 1A-hotfixen; relaterade öppna poster
  för end-to-end-språkstöd är B67, B89, B90 och B91.

- **`B63` Medel** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) -
  `scripts/prompt_to_project_input.py:_BUSINESS_TYPE_LABEL_SV` hade
  glipor mot briefModels faktiska businessType-slugs. briefModel
  returnerade `business_type="e-commerce"` (med bindestreck) men
  map:en hade bara `"ecommerce"` och `"ecommerce-shop"`; `naprapath-
  clinic` saknades helt. Resultat: H1 blev `Sajt för e commerce` /
  `Sajt för naprapath clinic` istället för `Webbshop` / `Naprapatklinik`.
  Källa: verifierings-Scout 2026-05-15. **Fix:** map:en utökad med
  ~10 hyphen-varianter för briefModel-slugs som faktiskt observerats
  eller är symmetri-fix för befintliga entries: `e-commerce` →
  `webbshop`, `ecommerce-store` → `webbshop`, `naprapath-clinic` →
  `naprapatklinik`, `naprapat-clinic` → `naprapatklinik`,
  `electrical-services` → `elektriker`, `electrical-contractor` →
  `elektriker`, `plumbing-services` → `rörmokare`, `barber-shop` →
  `barberare`, `flower-shop` → `blomsterhandel`, `chiropractic-clinic`
  → `kiropraktor`, `physiotherapy-clinic` → `sjukgymnast`,
  `painting-services` → `målare`, `carpentry-services` → `snickare`,
  `construction-company` → `byggfirma`. `naprapat` och `naprapath`
  pekar nu också på `naprapatklinik` (uppdaterat från `naprapat` så
  H1 läser `Naprapatklinik i Stockholm` snarare än `Naprapat i
  Stockholm`). Plus fallback i `_company_business_label` om-skriven
  från `Sajt för {slug}` till `företag som arbetar med {slug}` så
  framtida obekanta briefModel-slugs läser som svensk prosa istället
  för broken placeholder copy. Lookup strippar och lower-casar redan
  via `business_type.strip().lower()`, så `E-Commerce` /
  whitespace-runt `e-commerce` matchar också. Fix: `d99f8ba`. Test:
  `tests/test_prompt_to_project_input.py::test_business_type_map_covers_briefmodel_hyphenated_slugs`
  (parametriserad över 12 hyphen-varianter inkl. `e-commerce`,
  `naprapath-clinic`, `electrical-services`, `plumbing-services`),
  `tests/test_prompt_to_project_input.py::test_unknown_business_type_uses_swedish_fallback_phrase`,
  `tests/test_prompt_to_project_input.py::test_business_type_map_lookup_is_case_and_whitespace_safe`,
  `tests/test_prompt_to_project_input.py::test_company_name_for_e_commerce_brief_uses_swedish_label`,
  `tests/test_prompt_to_project_input.py::test_company_name_for_naprapath_clinic_brief_uses_swedish_label`,
  `tests/test_prompt_to_project_input.py::test_company_name_falls_back_for_unknown_business_type_slug`
  (uppdaterad: låser nu frånvaron av pre-hotfix `Sajt för X`-fallbacken).

- **`B60` Hög** (stängd 2026-05-15, post-merge audit av PR #27) -
  follow-up-versioneringen från PR #27 hade fyra kontraktsbrott:
  1. Versionerade snapshots inte immutabla:
     `scripts/prompt_to_project_input.py:write_project_input` skrev
     `<siteId>.vN.project-input.json` + `<siteId>.vN.meta.json` med
     `Path.write_text`, som tyst skriver över befintliga filer. Två
     samtidiga follow-ups som båda läste version=N och valde N+1
     hade skrivit över varandras snapshots; en operatör som av
     misstag återanvände ett siteId/projectId/version-tripp hade
     skrivit över v1. Det bryter PR #27:s "older versions stay
     byte-stable"-löfte.
  2. Engelsk workflow-text läckte ut i kundvänd copy:
     `merge_followup_project_input` la in `" Follow-up request: <prompt>"`
     i slutet av `company.story`. `scripts/build_site.py:render_about`
     renderar `company.story` som JSX direkt på `/om-oss`-sidan, så
     varje follow-up-prompt blev synlig som engelsk intern
     workflow-text på en svensk kundsajt. `meta.followUpPrompt` fanns
     redan som korrekt operatörs-yta för samma data.
  3. Pekar-uppdateringen var icke-atomisk: fyra sekventiella
     `Path.write_text`-anrop betydde att en process-crash mellan två
     anrop kunde lämna pointer-meta och pointer-project-input ur
     synk (t.ex. meta v=2 men pointer-project-input fortfarande v=1).
  4. `load_prompt_input_meta` föll tyst tillbaka till `init` när ett
     dossier-filnamn matchade prompt-input-mönstret men sidecaren
     saknades. En korrupt `data/prompt-inputs/`-mapp hade då
     producerat follow-up-builds märkta som init utan `projectId`/
     `version` istället för att larma operatören.
  **Fix:** `_write_immutable_snapshot` använder `open(..., "x")` så
  versionerade snapshots failar med `SystemExit` om filen redan
  finns. `_atomic_write_text` skriver via `tempfile.mkstemp` +
  `os.replace` så pointer-filer är atomic-replace istället för
  truncate-and-write. `merge_followup_project_input` bevarar nu
  `previous.company.story` byte-för-byte och låter `meta.followUpPrompt`
  vara den enda operatörs-/system-ytan för follow-up-prompten.
  `scripts/build_site.py:load_prompt_input_meta` skiljer nu på (a)
  versionerade snapshots utan sidecar och (b) current pointer under
  `data/prompt-inputs/` utan sidecar (båda failar) vs (c) curated
  examples utanför `data/prompt-inputs/` (behåller init-mode-kontraktet).
  Test:
  `tests/test_prompt_to_project_input.py::test_versioned_snapshot_refuses_overwrite`,
  `tests/test_prompt_to_project_input.py::test_followup_does_not_inject_workflow_text_into_company_story`,
  `tests/test_prompt_to_project_input.py::test_pointer_writes_use_atomic_replace`,
  `tests/test_prompt_to_project_input.py::test_generate_followup_bumps_version_and_reuses_project_id`
  (uppdaterad: lock:ar att `Follow-up request` INTE finns i
  `company.story` och att story matchar v1 byte-för-byte),
  `tests/test_builder_hardening.py::test_load_prompt_input_meta_fails_loud_when_versioned_sidecar_missing`
  (täcker versioned-, current-pointer-under-prompt-inputs- och
  curated-examples-scenarierna).

- **`B57` Medel** (stängd 2026-05-14, reviewer-fynd-follow-up efter A-mini
  cleanup) - B55-guarden från föregående sprint kollade bara
  `apps/viewser/.env` och `apps/viewser/.env.local` med hårdkodade
  Path-objekt. `.gitignore` säger däremot `.env.*` (allt) undantag
  `.env.example`, så en framtida `.env.production`, `.env.staging`,
  `.env.development` eller någon annan variant skulle kunna trackas
  utan att fångas av testet. Reviewer-fyndet (Cursor-agent, 2026-05-14)
  flaggade detta som 35% sannolikhet, 8/10 impact (secret leakage).
  **Fix:** testet kör nu `git ls-files apps/viewser/.env*` och bygger
  ett set av alla trackade matchningar. Den enda tillåtna är
  `apps/viewser/.env.example` (publik placeholder, explicit
  `!.env.example` i `.gitignore`). Alla andra trackade `.env*` failar
  testet med tydlig `git rm --cached`-remediation.
  Test:
  `tests/test_viewser_files.py::test_viewser_env_file_is_not_committed`
  (samma test, ny robust glob-baserad logik).

- **`B58` Låg** (stängd 2026-05-14, reviewer-fynd-follow-up efter A-mini
  cleanup) - B54-filtret från föregående sprint blockerade alla
  `.env*`-filer från StackBlitz-upload-loopen via prefix-check på
  `.env`. Det inkluderade `.env.example`, vilket är publik placeholder
  som **ska** följa med upp till preview så operatörer ser vilka
  env-vars sajten förväntar sig. Reviewer-fyndet (Cursor-agent, 2026-05-14)
  flaggade detta som 20% sannolikhet, 3/10 impact (dev/preview-friktion,
  funktionell regression).
  **Fix:** `isDotenvFile` i `apps/viewser/lib/stackblitz-files.ts` har
  nu explicit allowlist-check: `if (lower === ".env.example") return false`
  innan den generella `startsWith(".env")`-check:en. `.env.example` följer
  därför med upp till preview medan alla andra `.env*`-varianter
  (`.env`, `.env.local`, `.env.production`, `.ENV`, `.Env.Local`) blockas.
  Test:
  `tests/test_viewser_files.py::test_stackblitz_files_filter_dotenv_files_from_preview_upload`
  (utökad till att kräva både prefix-check, `toLowerCase()` och
  `.env.example`-allowlist),
  `tests/test_viewser_files.py::test_stackblitz_files_allow_env_example_through_filter`
  (källkods-lock på `=== ".env.example"`-pattern).

- **`B56` Medel** (stängd 2026-05-14, commit `8fae26a`) - StackBlitz-preview
  för Next 16-runs startade via `next dev` (Turbopack default), vilket kunde
  faila i WebContainer med felet "Turbopack is not supported on this
  platform ... use next dev --webpack".
  **Fix:** `apps/viewser/lib/stackblitz-files.ts` patchar nu bara
  `package.json`-bytesen som skickas till StackBlitz (ingen diskmutation av
  starter eller run-snapshot): `scripts.dev` säkras via
  `ensureWebpackFlag(...)` och `stackblitz.startCommand` sätts till
  `npm run dev`. Inline-patchen körs endast för
  `relPath === "package.json"`.
  Test:
  `tests/test_viewser_files.py::test_stackblitz_files_patches_package_json_for_webpack`,
  `tests/test_viewser_files.py::test_stackblitz_files_does_not_duplicate_webpack_flag`,
  `tests/test_viewser_files.py::test_stackblitz_files_does_not_write_back_package_json_to_disk`.

- **`B51` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `scripts/build_site.py:render_layout` skrev nav-labels direkt som JSX-
  text utan `_jsx_safe_string`-wrap. Kända route-id:n (`home`, `services`,
  `products`, `about`, `contact`) gav alltid säkra svenska labels från
  `_NAV_LABEL_BY_ROUTE_ID`-lookupen, men en framtida scaffold som
  introducerar ett okänt route-id föll via `_nav_label_for_route` till
  `route_id.replace("-", " ").replace("_", " ").title()` och labeln
  skrevs rått som JSX-text. Inkonsistent jämfört med kundtext (B30 gör
  redan all kundtext via `_jsx_safe_string`); en governance-driven
  ändring av ett route-id skulle kunna producera ogiltig TSX.
  **Fix:** header-nav och footer-nav-länkar i `render_layout` wrappar
  nu `label` i `_jsx_safe_string(label)`. Diskussion om varför labeln
  inte är "trusted" trots att den kommer från scaffold-fil: route-id är
  inte path-validerat på samma sätt som `_route_href` validerar paths
  (B50), så samma defensiva discipline appliceras nu uniformt.
  Test:
  `tests/test_builder_route_emission.py::test_render_layout_jsx_escapes_unknown_nav_label_fallback`,
  `tests/test_builder_route_emission.py::test_render_layout_escapes_known_nav_labels_consistently`.

- **`B52` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `_nav_items_from_scaffold` appenderade `("/spel", "Spel")` till
  nav-items om dossier-routen `/spel` fanns, utan dedupe mot scaffoldens
  `defaultRoutes`. För aktuella scaffolds är `/spel` inte deklarerat så
  duplicering triggas inte idag, men en framtida scaffold som adopterar
  `/spel` som default-route + samtidig interactive-game-loop-dossier
  hade gett två identiska nav-länkar.
  **Fix:** `_nav_items_from_scaffold` bygger nu en `existing_paths`-set
  av scaffold-paths och appendrar bara `/spel` från dossier-routes om
  pathen inte redan finns. Scaffold-ordning bevaras, dossier-injicerad
  `/spel` hamnar sist.
  Test:
  `tests/test_builder_route_emission.py::test_nav_items_dedupes_spel_when_scaffold_also_declares_it`.

- **`B54` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `apps/viewser/lib/stackblitz-files.ts:readRunFilesForStackblitz` läser
  varje fil under run-mappens `generated-files/`-snapshot och bundlar
  den för StackBlitz-preview-uploaden. Filterlogiken hade bara
  `FILES_TO_SKIP = {"package-lock.json"}` + `BINARY_EXTENSIONS`; den
  filtrerade **inte** `.env*`-filer explicit. Builder blockerar redan
  `.env*` från att hamna i `generated-files/` (B4/B5,
  case-insensitive ignore i `copy_starter`), så scenariot triggas
  inte i normalt flöde. Men upload-lagret bör ha egen defensiv guard
  så en framtida starter, manuell operatörsedit eller drift i buildern
  inte kan läcka en `.env`/`.env.local`/`.env.production` upp till en
  publik StackBlitz-preview.
  **Fix:** ny `isDotenvFile(basename)`-helper som returnerar
  `basename.toLowerCase().startsWith(".env")`. Walk-loopen i
  `readRunFilesForStackblitz` hoppar över filer som matchar. Speglar
  B4:s case-variant-täckning (`.ENV`, `.Env.Local`).
  Test:
  `tests/test_viewser_files.py::test_stackblitz_files_filter_dotenv_files_from_preview_upload`
  (källkods-lock som kräver att `.toLowerCase().startsWith(".env")`
  finns i filen).

- **`B55` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `tests/test_viewser_files.py::test_viewser_env_file_is_not_committed`
  hette `_is_not_committed` men kontrollerade `(path).exists()`, vilket
  failed-fel på en gitignored lokal `.env.local` (en korrekt Next.js-
  dev-workflow för Viewser). Operatören fick en falsk "committed"-alarm
  trots att filen var ignorerad. Testnamn och kontroll var ur fas.
  **Fix:** ny `_is_tracked_in_git(path)`-helper kör
  `git ls-files --error-unmatch <rel>` och returnerar `True` iff filen
  är trackad. Testet kollar nu git-tracking, inte disk-existens. En
  lokal gitignored `.env.local` får finnas; en faktiskt committad
  `.env`/`.env.local` failar testet med tydligt meddelande inkluderande
  remediation (`git rm --cached`).
  Test:
  `tests/test_viewser_files.py::test_viewser_env_file_is_not_committed`
  (samma test, ny korrekt semantik).

- **`B50` Medel** (stängd 2026-05-14, commits `4940cbb` + `f787eb7`) -
  `scripts/build_site.py` interpolerade scaffold-route-paths direkt i
  TSX-attribut (`href="{contact_path}"`, `href="{listing_path}"`) och
  `_pick_contact_route()` föll tyst tillbaka till `/kontakt` när
  scaffold saknade contact-route. Fix: ny `_route_href()` serialiserar
  scaffold-route-hrefs som JSX-uttryck, `_pick_contact_route()` fail-fastar
  med route-id-lista när contact-route saknas och `render_home()` omitar
  listing-CTA:n när scaffolden saknar både `services` och `products`
  i stället för att hitta på `/tjanster`. Scout-follow-up `f787eb7`
  lägger samma kanoniska route-path-validering framför både `_route_href()`
  och `route_to_page_path()`, så protocol-relative URLs, backslashes,
  query/fragments och dot-segments inte kan bli hrefs eller page paths.
  Test:
  `tests/test_builder_route_emission.py` låser syntetisk route med
  specialtecken, saknad contact-route, saknad listing-route,
  non-canonical route paths och befintliga B13/B45-regressioner.
  `painter-palma --skip-build` verifierades isolerat under
  `.generated/b50-*` och `.generated/route-hardening-*`.

- **`B45` Låg** (stängd 2026-05-14, B45 Builder-mini-sprint) -
  `scripts/build_site.py` hade hardcoded `/kontakt`-CTAs i
  `render_layout`, `render_home` och `render_services`, trots att
  `_pick_contact_route` redan fanns och användes av `render_products`.
  En framtida scaffold som flyttar contact-routen till exempelvis
  `/kontakta-oss` skulle därför få nav + products-CTA rätt men layout/home/
  services-CTAs fel.
  **Fix:** `render_layout`, `render_home`, `render_services` och
  `render_products` route:ar nu kontakt-CTA:er via `contact_path`, och
  `write_pages()` trådar `contact_route["path"]` från scaffoldens
  `defaultRoutes` till alla fyra renderer-ytor. Direkta renderer-unit-
  tester behåller bakåtkompatibel fallback `/kontakt`.
  Fix: `6daee58`.
  Test:
  `tests/test_builder_route_emission.py::test_contact_ctas_use_threaded_contact_path_across_renderers`,
  `tests/test_builder_route_emission.py::test_contact_renderer_helpers_do_not_literal_code_kontakt_href`,
  `tests/test_builder_route_emission.py::test_write_pages_threads_contact_path_into_all_contact_ctas`.

- **`B48` Medel** (stängd 2026-05-14, follow-up-semantik sprint) -
  `scripts/dev_generate.py` exponerade `--mode followup` och
  `--project-id`, och Backoffice Playground skickade dessa vidare till
  subprocessen, men dev-driverns planfas hårdkodade fortfarande
  `engine_mode="init"` och `project_id=None` när den anropade
  `produce_site_plan()`. Resultat: `input.json` kunde säga
  `mode=followup` medan `generation-package.json` sa `engineMode=init`
  och saknade `projectId`.
  **Fix:** `run_phase_plan()` tar nu `mode` och `project_id` som
  keyword-only argument och skickar dem vidare till
  `produce_site_plan()`. `main()` trådar CLI/env-värdena från
  `--mode` / `--project-id` hela vägen till planfasen, både för
  `--phase all` och separata `--phase plan`-körningar.
  Test:
  `tests/test_dev_generate.py::test_dev_generate_followup_threads_mode_and_project_id_to_package`
  låser att `input.json` och `generation-package.json` matchar i
  follow-up-läget. `tests/test_backoffice_trace.py::test_playground_runner_forwards_followup_project_id`
  låser att Backoffice Playground-runnern skickar `--project-id` och
  `SAJTBYGGAREN_MODE=followup` till subprocessen.

- **`B44` Hög** (stängd 2026-05-14, post-audit Builder-fix) - PromptBuilder
  och `app/page.tsx` tolkade alla returnerade `runId` som lyckad build.
  `lib/build-runner.ts` returnerar medvetet `runId` + `buildResult` även
  när `buildResult.status === "failed"` (B40-kontraktet: failed runs
  måste synas i Run History), men `/api/prompt` skickade inte vidare
  status-fältet och PromptBuilder visade grön "Build klar" för fail-
  runs. Sannolikhet 85%, impact 7/10.
  **Fix:** `/api/prompt/route.ts` läser nu `build-result.json:status`
  via en defensiv `extractBuildStatus`-helper och exponerar fältet som
  `buildStatus` på response-payloaden. PromptBuilder klassificerar
  utfallet via en ny `classifyBuildStatus`-helper (`ok` /
  `degraded` / `failed` / `unknown`) och renderar tre distinkta UI-
  paneler (grön success, gul varning, röd failed). `app/page.tsx`
  tar emot `PromptBuildOutcome` i `onBuildDone` och använder
  `headerStatusForOutcome` så headern aldrig säger "Build klar via
  prompt:" för en degraderad eller failed run.
  Test:
  `tests/test_viewser_files.py::test_prompt_route_surfaces_build_status`,
  `tests/test_viewser_files.py::test_prompt_builder_classifies_failed_build_distinctly`,
  `tests/test_viewser_files.py::test_page_uses_outcome_aware_header_for_prompt_build_done`.

- **`B46` Låg** (stängd 2026-05-14, post-audit Builder-fix) - Legacy
  `apps/viewser/components/chat-panel.tsx` var inte längre monterad
  någonstans (PromptBuilder tog över i `fd67fbd`), men filen levde
  kvar och innehöll samma "runId == success"-logik som B44. Audit
  rekommenderade antingen samma status-fix eller borttagning;
  borttagning valdes för att eliminera duplicerad surface i
  stället för att underhålla två parallella prompt-/build-paneler.
  **Fix:** `components/chat-panel.tsx` raderad. `tests/test_viewser_files.py`
  uppdaterad: `chat-panel.tsx` borttaget från required-files-listan,
  `test_chat_panel_marks_prompt_as_experimental` ersatt med
  `test_chat_panel_component_is_removed` som låser borttagningen.
  `tests/test_viewser_prompt_primary.py` docstring uppdaterad,
  inline-asserts pekar nu på audit-fixen istället för "remains as a
  component for now". `scripts/check_term_coverage.py` allowlist
  rensar `ChatPanel`/`ChatPanelProps`/`BuildModelUsage` som inte
  längre finns någonstans i koden. `governance/rules/vocabulary-discipline.md`
  byter exempel `ChatPanel` mot `PromptBuilder`; `.cursor/rules/`
  spegeln synkad via `scripts/rules_sync.py`. `/api/chat`-routen
  och `lib/openai.ts` lämnas orörda — de är fortfarande standalone
  endpoints och Scout pekade inte ut dem.

- **`BO2` Medel** (stängd 2026-05-14, squash-merge `e1ad5ca` via PR #23) - Backoffice trace
  viewer dumpade tidigare bara rå dataframe för `trace.ndjson`.
  Fix: ny backoffice-helper `backoffice/views/_trace.py` läser halvskrivna
  trace-rader defensivt, summerar events, grupperar per fas, lägger filter för
  fas/status/söktext och markerar fel, varningar, quality-, repair- och
  codegen-events tydligt. Både `Engine Runs` och `Playground` använder samma
  viewer och behåller rådata i expander.
  Test: `tests/test_backoffice_trace.py::test_load_trace_events_tolerates_partial_ndjson`,
  `tests/test_backoffice_trace.py::test_trace_summary_and_severity_mark_important_events`,
  `tests/test_backoffice_trace.py::test_trace_views_use_structured_trace_viewer`.

- **`BO4` Medel** (stängd 2026-05-14, squash-merge `e1ad5ca` via PR #23) -
  `backoffice/views/playground.py` var en svart låda medan
  `scripts/dev_generate.py` körde via `subprocess.run(... timeout=180)`.
  Fix: Playground använder nu en kontrollerad `subprocess.Popen`-runner som
  visar körstatus, fas, tid, exit code och senaste loggrader under/efter
  körning. Timeout dödar endast den startade processen och bevarar fångad
  output. RunId-parsningen ligger i egen helper.
  Test: `tests/test_backoffice_trace.py::test_playground_extracts_run_id_from_supported_outputs`,
  `tests/test_backoffice_trace.py::test_playground_runner_uses_popen_not_subprocess_run`.
  Kvarvarande avgränsning: riktig cancellation/background-jobb kräver separat
  design och spåras som `BO4-followup-cancel`.

- **`B20-followup-lucide` Låg** (stängd 2026-05-13, squash-merge
  `04fc2fa` via PR #21) - följduppgift på den stängda B20-posten:
  full `npm run build` mot `.generated/atelje-bird/` (eller någon
  annan ecommerce-lite-genererad sajt) fallerade med
  `Module not found: lucide-react` eftersom
  `scripts/build_site.py:write_pages` hardcodar lucide-imports per
  renderer men `commerce-base/package.json` bara hade
  `@heroicons/react`. `marketing-base` har lucide som dep så
  konflikten var osynlig pre-B20.

  **Fix:** ny [ADR
  0020](../governance/decisions/0020-commerce-base-lucide-react.md)
  dokumenterar operatörsgivet dep-godkännande. `lucide-react`
  ^1.14.0 (matchar marketing-base:s exakta version) tillagd i
  `data/starters/commerce-base/package.json`;
  `data/starters/commerce-base/package-lock.json` regenererad via
  `npm install` (1 added package). `data/starters/commerce-base/
  README.md` ny sektion "Runtime-deps utöver upstream" som pekar
  på ADR 0020.

  Verifiering: `cd data/starters/commerce-base && npm run build`
  grön (13 routes prerendered, Shopify env-skip-loggrad);
  `cd .generated/atelje-bird && npm install && npm run build`
  grön (11 statiska sidor inkl `/produkter` plus commerce-base:s
  egna dynamiska routes); `pytest tests/ -q` 381 passed + 3 skipped;
  4 guards + ruff gröna; Cursor Bugbot på PR #21 SUCCESS-conclusion
  (inga inline-fynd).

  Out of scope (architecturskuld kvarstår): `write_pages` är
  fortfarande hardcoded mot lucide. En framtida starter utan
  lucide skulle träffa samma konflikt. Spåras i
  `docs/current-focus.md` Queue som "`write_pages` icon-bibliotek-
  agnostisk refactor".

- **`B20` Låg** (stängd 2026-05-13, squash-merge `75c980b` via PR #20)
  - aktiverade `ecommerce-lite -> commerce-base`-routingen. Spåret
  hade två steg: step 1 (vendor-import av
  `data/starters/commerce-base/` från `vercel/commerce` upstream
  `1df2cf6`) landade i PR #16 commit `4b4c3af` enligt [ADR
  0018](../governance/decisions/0018-b20-commerce-base-harmonisering.md).
  Step 2 var blockerat av B13b (route-emission) tills `fda1464`
  löste `scripts/build_site.py:write_pages` att vara scaffold-driven.

  **Fix:** ny [ADR
  0019](../governance/decisions/0019-b20-step-2-mapping-activation.md)
  aktiverar mappningen explicit (adresserar ADR 0018:s "kräver egen
  ADR" och `.cursor/BUGBOT.md` "Mapping and routing risk"-regelns
  krav på ADR i samma PR).
  `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER` har
  `ecommerce-lite: commerce-base`. `data/starters/README.md`:s
  `scaffold-starter-mapping`-block har raden
  `ecommerce-lite: commerce-base` utan `(B20: ...)`-noten,
  Status-kolumnen för `commerce-base` uppdaterad till "aktiverad i
  B20 step 2", och avsnittstexten ovanför mapping-blocket
  avgenericerad.
  `packages/generation/codegen/codegen.py:_REAL_CODEGEN_STARTERS`
  förblir `{"marketing-base"}` (ADR 0017 + ADR 0019:s "INTE
  beslutar"-sektion): ecommerce-lite kör genom
  `source=deterministic-v1` codegen tills real-codegen-scope
  utvidgas i en separat sprint med egen ADR-utökning.

  Test: `tests/test_starter_scaffold_mapping.py` (8 tester) gröna,
  inklusive `test_b20_temporary_mapping_is_explicit` som auto-skippar
  positivt när mappningen är `commerce-base`.
  `tests/test_planning.py::test_produce_site_plan_picks_ecommerce_lite_on_commerce_signal`
  source-lock uppdaterad till `commerce-base`.
  `python scripts/build_site.py --dossier
  examples/atelje-bird.project-input.json --skip-build` ger
  `build-result.json starterId=commerce-base`,
  `routes=[/, /kontakt, /om-oss, /produkter]` (inget `/tjanster`),
  `quality-result.json status=ok`.
  `app/produkter/page.tsx` emitteras, `app/tjanster/page.tsx` INTE.

  Bugbot-rundor: 1 iteration, 2 fynd. Fynd 1 (Hög: SCAFFOLD_TO_STARTER
  utan ADR) löst via ADR 0019 i `af7fac4`. Fynd 2 (Medium: PR Ready
  trots Known risks/blockers) hanterad genom att flytta
  lucide-react-noten till "Post-merge sanity needed" i PR-
  beskrivningen; Bugbots inline-comment-API rapporterade fyndet
  som carry-over på senaste commit men UI markerade fynd 1 som
  "Show resolved" och alla CI-checks (Cursor Bugbot NEUTRAL,
  governance SUCCESS, GitGuardian SUCCESS) passerade.

  **Known follow-up (stängd 2026-05-13 via PR #21 + ADR 0020 — se
  separat post nedan):** lucide-react-konflikten är löst via väg A
  (lägg dep i commerce-base). Full `npm run build` mot
  `.generated/atelje-bird/` är nu grön. `write_pages` hardcodar
  fortfarande lucide-imports vilket lämnar arkitekturskuld för en
  framtida starter som inte använder lucide; den skulden spåras
  i `docs/current-focus.md` Queue och i ADR 0020:s "INTE beslutar".

- **`B13b` Låg** (stängd 2026-05-13, squash-merge `fda1464` via PR #19) -
  `scripts/build_site.py:write_pages` var hårdkodad mot
  `local-service-business`-routes (`/tjanster`, `/om-oss`, `/kontakt`)
  på fyra nivåer (`_nav_items()`, hardcoded `/tjanster`-CTA i
  `render_home`, `write_pages()`, avsaknad av `render_products`).
  Blockerade aktiveringen av `ecommerce-lite -> commerce-base` (B20
  step 2): ad-hoc-generation gav Quality Gate `status=degraded` med
  route-scan failure `"/produkter -> app\produkter\page.tsx
  (saknas)"`.

  **Fix:** `write_pages` läser nu scaffoldens `routes.json` och
  dispatchar per route id (home/services/products/about/contact). Ny
  `render_products`-renderer för `/produkter` med scaffold-driven
  `contact_path`. Nya helpers `_nav_items_from_scaffold`,
  `_pick_listing_route`, `_pick_contact_route`, `_NAV_LABEL_BY_ROUTE_ID`,
  `_LISTING_COPY_BY_ROUTE_ID`. Okänt route-id ger `SystemExit` så
  scaffolds inte tyst kan saknas en renderer.
  "Writing pages: ..."-printet flyttat till FÖRE `write_pages`-anropet
  (Bugbot-fynd: tidigare post-call print gav operatör inga ledtrådar
  när `write_pages` misslyckades med `SystemExit`). Ny
  `examples/atelje-bird.project-input.json` (ecommerce-lite-fixture)
  för end-to-end-smoke.

  Test: `tests/test_builder_route_emission.py` (21 tester) låser
  scaffold-driven dispatch, nav/listing/contact-path-threading,
  print-ordningen samt ecommerce-lite-smoken
  `test_ecommerce_lite_fixture_writes_produkter_and_passes_route_scan`.

  Bugbot-rundor under granskning: 3 fynd, alla åtgärdade (print-order
  `7f670b8`, `/kontakt`-hardcoding i `render_products` `5ac4ab8`,
  PR-description-scope `gh pr edit`). Pre-existing hardcoded
  `/kontakt`-CTAs i `render_home/services/layout` kvarstår som
  teknisk skuld (predaterar denna PR) - tracked under "Öppna" om
  någon vill skriva ny B-ID på det.

- **`B43` Medel** (stängd 2026-05-11, post-review-2 audit) -
  `apps/viewser/components/viewer-panel.tsx` success-path-grenen hade
  cancelled-guard FÖRE `await import("@stackblitz/sdk")` men inga
  guards EFTER. Två awaits till (dynamisk import + `embedProject`)
  exekverade utan ny cancelled-check, så om operatör bytte runId
  mid-flight rann den gamla embedProject färdig och mountade stale
  preview i den always-mounted ref-divden (post-PR-#13 ref-div är
  alltid monterad — så avmontering räddar inte längre). Fix:
  cancelled-check EFTER dynamic import + cleanup-branch EFTER
  embedProject som rensar `containerRef.current.innerHTML` om
  cancelled blev true under embed-flight. Test:
  `tests/test_viewser_files.py::test_viewer_panel_guards_cancelled_after_dynamic_import_and_embed`
  kräver minst 2 cancelled-referenser i success-path-blocket OCH
  source-lockar att `innerHTML = ""`-cleanup existerar inom en
  `if (cancelled)`-gren.

- **`B42` Medel** (stängd 2026-05-11, post-review-2 audit) -
  `apps/viewser/lib/build-runner.ts` använde
  `runIdMatch?.[1] ?? (await detectLatestRunIdByMtime())` i BÅDA
  success- och failure-grenarna. När `scripts/build_site.py`
  kraschar FÖRE den skriver ut `runId: ...` (t.ex. KeyError på
  Project Input-load, FileNotFoundError på scaffold-lookup),
  faller mtime-fallbacken tillbaka till TIDIGARE run-dir på disk
  och felaktigt märker den som denna build:s "strukturerade
  failure" (B40-kontraktet). UI:t fick då en gammal run med
  fel siteId returnerad som om den var det aktuella failed-
  resultatet. Reviewer flaggade detta i post-review-2-audit som
  "B40 sväljer riktiga fel". Fix: ny `runIdFromStdout`-variabel
  som STRIKT använder process-stdout i failure-grenen.
  Success-grenen behåller mtime-fallback eftersom `exitCode === 0`
  garanterar att senaste dir IS denna build:s. Test:
  `tests/test_viewser_files.py::test_build_runner_returns_structured_failure_instead_of_throwing`
  utökad med assertion som söker upp `if (exitCode !== 0) { ... }`-
  blocket och kräver att `detectLatestRunIdByMtime` INTE förekommer
  där.

- **`B41` Medel** (stängd 2026-05-09, Builder UX MVP smoke-test) -
  `npm run build` mot `.generated/painter-palma/` hade failat Next 16
  prerendering på `/_global-error` med
  `TypeError: Cannot read properties of null (reading 'useContext')`.
  Nattdiagnosen verifierade att både en helt färsk
  `.generated/painter-palma/` och `data/starters/marketing-base/`
  byggde grönt med samma `next@16.2.5` / `react@19.2.4`, vilket pekade
  bort från kundcopy, Dossier-montering och starter-dependencies. Den
  kvarvarande driftkällan var `scripts/build_site.py:copy_starter`:
  funktionen bevarade både `node_modules/` och `.next/` mellan
  regenerationer. `node_modules/` är en avsiktlig npm-cache, men `.next/`
  är framework-genererad build output och kan bära stale prerender-state
  över template- eller dependency-ändringar. Fixen bevarar därför bara
  `node_modules/` och tar bort `.next/` vid varje regeneration innan
  startern kopieras in. Verifierat med färsk
  `python scripts/build_site.py --dossier examples/painter-palma.project-input.json`
  utan `OPENAI_API_KEY`: `build-result.json:status=ok`,
  `quality-result.json:status=ok`, `generated-files/` finns. Standalone
  `cd data/starters/marketing-base && npm run build && npm run lint`
  passerar också. Fix: `fix(starters): repair marketing base build`.
  Test: `tests/test_builder_hardening.py::
  test_copy_starter_drops_stale_next_cache_but_preserves_node_modules`.

- **`B40` Medel** (stängd 2026-05-09, Builder UX MVP smoke-test) -
  `apps/viewser/lib/build-runner.ts:runBuildOnce` kastade
  ovillkorligt en error så fort `scripts/build_site.py` exit:ade
  med kod != 0. Det bröt det dokumenterade Builder MVP-kontraktet
  (`docs/architecture/builder-mvp.md` "Builder-guards"): när
  `npm install` / `npm run build` failar skriver `build_site.py`
  ändå alla canonical artefakter (`build-result.json` med
  `status=failed`, `quality-result.json`, `repair-result.json`,
  `generated-files/`-snapshot) och exit:ar 1 - exit-koden är en
  **avsiktlig** signal till operatören, inte en crash. Wrappers
  exception droppade dock runId:et på golvet, vilket gjorde att
  `/api/build` returnerade 500 utan att UI:t fick en runId att
  navigera till. Run History uppdaterades inte och RunDetailsPanel
  fick aldrig se den strukturerade failure-rapporten. Upptäckt under
  smoke-test efter `e80148c` när marketing-base-startern råkade
  failed på `/_global-error`-prerendering (separat issue, se nedan).
  Fix: i `exitCode !== 0`-grenen försöker wrappers nu läsa
  `build-result.json` från disk via samma `readBuildResult(runId)`-
  helper som success-pathen. Lyckas läsningen returneras
  `{runId, buildResult}` precis som vid framgång - UI:t ser då en
  failed run i Run History och kan rendera artefaktpanelerna
  pedagogiskt. Endast när läsningen failar (exit !=0 + ingen
  strukturerad output på disk) kastar wrappers exception som
  tidigare. Test: `tests/test_viewser_files.py::
  test_build_runner_returns_structured_failure_instead_of_throwing`
  (source-lock på "structured-failure"-comment + `readBuildResult(runId)`
  i exit-branch).

- **`B38` Medel** (stängd 2026-05-09, post-3C-lite-audit-2) -
  `scripts/dev_generate.py:run_phase_build` byggde `modelUsage`-
  envelopen via `compose_model_usage(base_source="mock-no-key", ...)`.
  Värdet var hårdkodat trots att `compose_model_usage`-helperns
  dokumenterade semantik säger att `base_source` är `briefSource`-
  värdet och spårar hur OVERALL pipeline kördes (`real` /
  `mock-no-key` / `mock-llm-error`). Resultat: en operator som körde
  `python scripts/dev_generate.py "..."` med `OPENAI_API_KEY` satt
  fick `site-brief.json:briefSource=real` men
  `build-result.json:modelUsage.source=mock-no-key`. Det bryter
  Sprint 2A-invarianten och skulle få Builder UX-paneler att visa
  fel modellstatus när de läser dev_generate-runs. Fix:
  `run_phase_build` tar nu en valfri `site_brief: dict | None`-
  parameter och läser `briefSource` därifrån; `main()` skickar in
  briefen från Phase 1 (eller läser `site-brief.json` från disk
  när `--phase build` körs ensam). Default-fallback är fortfarande
  `mock-no-key` så bakåtkompatibla anrop inte spricker. Test:
  `tests/test_artefact_schema_3c_lite.py::test_dev_generate_modelusage_source_follows_brief_source`
  (parametriserad över real/mock-no-key/mock-llm-error utan att kräva
  riktig OpenAI-call - `site_brief["briefSource"]` muteras direkt) +
  `test_dev_generate_modelusage_source_defaults_to_mock_no_key_without_brief`
  (låser fallback-pathen).

- **`B39` Låg** (stängd 2026-05-09, post-3C-lite-audit-2) -
  `docs/handoff.md` "Skiriptyta"-sektionen sade generiskt
  "`--runs-dir` för isolerade test-paths" - men flaggnamnet skiljer
  sig per script: `scripts/build_site.py` har `--runs-dir`,
  `scripts/dev_generate.py` har `--data-runs-dir`. Risk: nästa
  agent copy-paste:ar fel flagga och misslyckas tyst eller skriver
  till fel path. Samtidigt rättades `known-issues.md:138` line-ref
  för B35 (`scripts/build_site.py:1565` → faktiskt
  `scripts/build_site.py:1523` där `run_dir.mkdir(...)` sitter).
  Fix: handoff förtydligad per-script + line-ref korrigerad.
  Inga regression-tester - detta är ren doc-drift utan
  runtime-impact, men nämns här så framtida audit ser att fyndet
  inte var nytt vid Builder UX MVP-runda.

- **`B33` Medel** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  `scripts/dev_generate.py:run_phase_build` skrev `build-result.json`
  utan `modelUsage`-fältet. När operatören körde dev_generate med
  `OPENAI_API_KEY` aktiverade `produce_codegen_artefakt` real LLM
  (matching marketing-base), `codegen.source` blev `real`, men
  build-result.json saknade ändå modelUsage. Backoffice / Builder UX
  som läser alla runs (mock + real builder) skulle hamna i
  shape-mismatch. Fix: flyttat composition-logiken till
  `packages/generation/artifacts/model_usage.py:compose_model_usage`
  (publik shared helper); både `scripts/build_site.py:write_build_result`
  och `scripts/dev_generate.py:run_phase_build` anropar samma
  helper med samma codegen_summary-shape (riskNotes + usage
  inkluderade). Test:
  `tests/test_artefact_schema_3c_lite.py::test_dev_generate_writes_modelusage_into_build_result`
  och `test_compose_model_usage_lives_in_shared_artifacts_module`.

- **`B34` Låg** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  Drift-guards i `tests/test_artefact_schema_3c_lite.py:207-248`
  jämförde bara top-level Pydantic-fält mot top-level schema
  ``properties``. Nested ``$defs/checkResult`` (vs `CheckResult`-
  modellen) och ``$defs/repairFix`` (vs `RepairFix`-modellen) var
  inte fält-låsta, så ett tillagt Pydantic-fält på `CheckResult`
  utan motsvarande `$defs/checkResult.properties`-bump skulle
  passera testet trots att artefakten-på-disk och in-memory-modellen
  drev isär. Test-claim "schema↔Pydantic locked" var överdrivet.
  Fix: ny `_assert_no_drift`-helper + `_schema_property_names(schema,
  defs_key=...)`-parameter; två nya tester
  (`test_quality_result_nested_check_result_matches_pydantic`,
  `test_repair_result_nested_repair_fix_matches_pydantic`)
  täcker nested-drift för båda artefakterna.

- **`B35` Låg** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  `docs/architecture/builder-mvp.md` påstod att schema-överträdelse
  fails build "innan `data/runs/<runId>/` skapas". Det stämmer inte:
  `run_dir.mkdir(...)` körs i Phase 0 init (`scripts/build_site.py:1523`)
  innan Phase 1 / 2 / 3 — och schema-validators för
  `quality-result.json` / `repair-result.json` kör först i Phase 3.
  Ett sent schemafel lämnar därför en partial run-dir med
  Phase 1+2-artefakter på disk. Inte en runtime-bug men fel ops-
  förväntan. Fix: doc-stycket omskrivet att vara ärligt om vad
  validatorn faktiskt gör (skyddar de två specifika artefakterna,
  inte hela run-dir); operatörer som vill ha all-or-nothing får
  rensa partial run-dir manuellt.

- **`B36` Låg** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  Schemafilernas description-fält refererade `tests/test_artefact_schema_drift.py`
  som inte finns i repot; korrekt filnamn är
  `tests/test_artefact_schema_3c_lite.py`. Onboarding-fel som ledde
  ny agent fel när hen följde länken från schemat. Fix: båda schemafiler
  uppdaterade till korrekt filnamn med tillägget "(top-level + nested
  $defs)" så scope är tydlig.

- **`B29` Hög** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  `governance/schemas/project-input.schema.json` (introducerat i
  PR #10 / commit `124b13f`) markerade `services[].summary`,
  `company.tagline`, `company.story`, `location.serviceAreas` och alla
  fyra `contact.*`-fält som **valfria**, men `scripts/build_site.py`-
  renderers indexerar dem ovillkorligt (t.ex. `svc["summary"]`,
  `company["tagline"]`, `contact["addressLines"]`). En schema-valid
  Project Input kraschade därför med `KeyError` mid-build, **innan**
  Quality Gate hann skriva ett strukturerat felresultat. Fix: stramat
  schemat så `required` reflekterar builder-kontraktet. Övriga
  fält (`team`, `founded`, `region`) är fortsatt valfria eftersom
  buildern hanterar deras frånvaro via `.get()`. Test:
  `tests/test_builder_audit_post_3b_next.py::
  test_company_required_includes_tagline_and_story` plus de övriga
  per-fält-låsen + en negativ test
  (`test_schema_rejects_payload_missing_company_tagline`).

- **`B30` Hög** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  Renderers i `scripts/build_site.py` (`render_home`, `render_services`,
  `render_about`, `render_contact`) interpolerade rå kundtext direkt
  in i TSX/JSX via f-strings utan escape. Tecken som `<`, `>`, `{`,
  `}` eller `"` i kundnamn / tagline / service-summary / address-rader
  kunde producera ogiltig TSX som `next build` (eller en typecheck-
  pass) skulle avvisa. Fix: ny `_jsx_safe_string(text)`-helper som
  wrapar all dynamic text i `{"..."}` JSX-expression-form via
  `json.dumps`. Alla raw f-string-interpoleringar i de fyra renderers
  passerar genom helpern. `_phone_href`-resultat (digit-only) behåller
  kvotad attribut-form via `_jsx_safe_string("tel:" + ...)` för
  konsistens. `_member_initials`-helper extraheras ur den tidigare
  inline-expressionen i `render_about` så att initial-strängen är ett
  plain-string-värde innan escape. Test:
  `tests/test_builder_audit_post_3b_next.py::
  test_jsx_safe_string_wraps_text_as_jsx_expression`,
  `test_render_home_jsx_escapes_special_characters`,
  `test_render_contact_jsx_escapes_phone_and_email`,
  `test_renderers_use_jsx_safe_string_for_customer_text`
  (källkods-lock som kräver att alla fyra renderers anropar helpern).

- **`B31` Medel** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  `scripts/build_site.py:write_phase1_understand` anropade
  `dossier_path.relative_to(REPO_ROOT)` utan fallback. CLI:n accepterar
  godtycklig `--dossier`-path, så en operator som pekar på en
  ad-hoc-fixture utanför repot fick en `ValueError`-stack-trace
  istället för ett strukturerat fel. Den befintliga
  `_to_repo_relative()`-helpern (rad 131-142) hade redan rätt
  beteende (try/except). Fix: bytt till helpern. Test:
  `test_to_repo_relative_handles_external_path` +
  `test_write_phase1_understand_does_not_raise_on_external_path`
  (källkods-lock).

- **`B32` Låg** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  `scripts/build_site.py:run_npm` byggde bara
  `partial_text` från `exc.stdout` när `isinstance(exc.stdout, bytes)`,
  och fall till `else`-grenen som inte hanterade `exc.stdout=None +
  exc.stderr="<error log>"`-fallet. Operatören tappade den enda
  diagnostik npm-timeout producerade. Fix: ny
  `_coerce_subprocess_text(stream)`-helper hanterar `None | bytes |
  str` enhetligt; `run_npm` decodar `exc.stdout` och `exc.stderr`
  separat och konkatenerar. Test:
  `test_coerce_subprocess_text_handles_all_three_types`,
  `test_run_npm_timeout_preserves_stderr_when_stdout_is_none`,
  `test_run_npm_timeout_preserves_stderr_with_bytes_stream`.

- **`B28` Låg** (stängd 2026-05-08, audit-4) - `tests/test_docs_freshness.py`
  parsade ruffs felräknings-output med regexen `r"Found\s+(\d+)\s+error"`
  (utan `errors?`). Reviewer-claim: "regex fails to match on 2+ findings,
  actual = -1, safety assertion fails". Verifiering visade att claimet
  är **tekniskt felaktigt** - `re.search` tillåter partiell match så
  `error` matchar som prefix av `errors`, vilket bevisades med
  `re.search(r"Found\s+(\d+)\s+error", "Found 5 errors.")` → match,
  group1=`'5'`. Men förslaget är ändå värt att applicera av tre
  defensiva skäl: (1) codifierar intent istället för att lita på
  substring-prefix-tillfällighet, (2) framtidssäkrar mot ruff-format-
  ändringar, (3) samma strukturella lärdom som B27 ("regex som råkar
  fungera men inte uttrycker intent"). Fix: bytt till
  `r"Found\s+(\d+)\s+errors?"` med explicit `s?`, kompilerad en gång
  som modul-konstant `_RUFF_FOUND_RE`. Test:
  `tests/test_docs_freshness.py::test_ruff_found_regex_handles_singular_and_plural`
  med fyra explicita assertioner (singular+plural+stort tal+full
  ruff-output med både singular- och plural-fall).
- **`B27` Låg** (stängd 2026-05-08, audit-3) - `tests/test_docs_freshness.py`
  använde `dossier_id in readme` (Python `str in str` substring-match) för
  att verifiera att en disk-Dossier nämns i `dossiers/README.md`. Det gav
  falsk-positiv för överlappande IDs: en hypotetisk `game`-Dossier på disk
  skulle räknas som "nämnd" bara för att README:n nämner
  `interactive-game-loop` (`'game' in 'interactive-game-loop' == True`).
  Bevis: `python -c "print('game' in 'interactive-game-loop')"` → `True`.
  Risk-fönster: idag bara en Dossier på disk så testet passerade ändå,
  men så fort en andra Dossier vars id är substring av den första
  importerades skulle testet ge tyst "OK" trots att README:n inte hade
  uppdaterats. Fix: ny `_id_appears_as_token()`-helper i samma fil som
  matchar med custom token-boundary `(?<![\w-])id(?![\w-])` så att hyphen
  räknas som id-tecken, inte token-separator. Tester:
  `tests/test_docs_freshness.py::test_dossier_readme_implementation_status_matches_disk`
  (uppdaterad till att använda helpern), och nya
  `tests/test_docs_freshness.py::test_id_appears_as_token_distinguishes_overlapping_dossier_ids`
  som täcker sex överlapps-scenarier (full id, prefix, suffix, mid-substring,
  hyphen-prefix, hyphen-suffix) plus ett "bara id"-scenario.
- **`B23` Låg** (stängd 2026-05-08, post-audit-2) - Bug C end-to-end:
  `build_plan_artefakts` i `scripts/build_site.py` anropar
  `validate_site_plan(site_plan)` EFTER `merge_operator_selected_with_helper`,
  men det specifika anrops-ordet var inte regression-skyddat. Två rena
  enhetstester fanns för mergens beteende, ett brett schema-test fanns
  för validatorn, men inget test gjorde det olagligt att flytta tillbaka
  validate-anropet till **före** mergen. Fix: nytt source-regex-test
  som hittar `merge_operator_selected_with_helper(` och
  `validate_site_plan(site_plan)` i funktionsbody:n och säkrar att
  validate kommer efter merge. Samma stil som B19-skyddstesterna.
  Test: `tests/test_planning.py::test_b23_build_site_revalidates_site_plan_after_operator_merge`.
- **`B24` Låg** (stängd 2026-05-08, post-audit-2) - Bug A coverage gap:
  `merge_operator_selected_with_helper` har tre kodpaths (operator=None,
  list, dict) men bara None- och dict-paths var direkt testade. List-pathen
  (`plan.py:535-544`) var funktionellt korrekt vid läsning men hade inget
  test som blockerade en framtida regression där t.ex. helperns
  `rejected[]` tappas när operator skickar en plain list. Fix: två nya
  tester för list-form-mergen. Test:
  `tests/test_planning.py::test_merge_operator_list_with_no_helper_signal_returns_plain_list`,
  `tests/test_planning.py::test_merge_operator_list_with_helper_gap_promotes_to_object_form`.
- **`B25` Låg** (stängd 2026-05-08, post-audit-2) - `AGENTS.md` Gotchas-
  stycket sade "only 4 findings remain, all in the bug-bear family"
  trots att `python -m ruff check .` returnerade `All checks passed!`
  (0 findings). Drift uppstod i en tidigare ruff-städ-commit som inte
  uppdaterade AGENTS.md. Risk: ny agent läser docs och tror 4 findings
  är "intentional", lägger tillbaka dem för konsistens. Fix: AGENTS.md
  uppdaterad till "baseline is **0 findings**" + ny pytest-guard
  `tests/test_docs_freshness.py::test_agents_md_ruff_baseline_claim_matches_reality`
  som parsar AGENTS.md för "baseline is **N findings**", kör ruff,
  och bryter om siffrorna inte matchar.
- **`B26` Låg** (stängd 2026-05-08, post-audit-2) -
  `packages/generation/orchestration/dossiers/README.md` sade "Inga
  Dossiers är implementerade än" trots att `soft/interactive-game-loop/`
  fanns på disk med `manifest.json`, `instructions.md` och
  `components/pacman-game.tsx`. `docs/handoff.md:29` hade redan korrekt
  status, så de två dokumenten motsa varandra. Risk: ny agent läser
  README (ägar-pathens lokala doc) före handoff och skriver om
  `pacman-game` från scratch. Fix: README uppdaterad med korrekt status
  samt `interactive-game-loop`-länk och förklaring att övriga 11 capability-
  slugs är gap. Ny pytest-guard
  `tests/test_docs_freshness.py::test_dossier_readme_implementation_status_matches_disk`
  walkar `soft/`, `hard/` och bryter om README påstår 0 Dossiers när disk
  har minst en, eller om en disk-Dossier inte nämns vid id i README.
- **`B21` Medel** (stängd 2026-05-08) - `filter_capabilities()` i
  `packages/generation/planning/plan.py` antog att `default` i
  `capability-map.v1.json` alltid fanns i capabilityns `dossiers`-lista.
  Om policyn drev isär kunde plan-helpern välja en Dossier som inte var
  tillåten av samma entry. Fix: fail-loud runtime-check i helpern
  (`default not in dossiers` -> `RuntimeError`) + dedupe av
  `requestedCapabilities` för att undvika dubbletter i `rejected[]`.
  Tester: `tests/test_planning.py::test_filter_capabilities_raises_when_default_not_in_dossiers`,
  `tests/test_planning.py::test_filter_capabilities_dedupes_input`.
- **`B22` Medel** (stängd 2026-05-08) - alla scaffold-filer pekade på
  `$schema=governance/schemas/scaffold.schema.json` men filen saknades.
  Det gav falsk trygghet i IDE/validering och ingen central guard för
  scaffold.json-fälten. Fix: ny
  `governance/schemas/scaffold.schema.json`, `validate_scaffold()` i
  `packages/generation/artifacts/validate.py`, auto-validering i
  `packages/generation/planning/load_scaffold_registry()`, samt ny testfil
  `tests/test_scaffold_schema.py`.
- **`B12` Låg** (stängd 2026-05-08) - smoke-tester skrev tidigare till
  riktiga `.generated/` och `data/runs/` istället för `tmp_path`, vilket
  spammade run-historiken med ~10-15 mappar per `pytest`-körning.
  Fix: `e376439`. `scripts/build_site.py::build()` accepterar nu en
  `runs_dir`-parameter och `--runs-dir`-flagga, och alla tester i
  `tests/test_builder_smoke.py`, `tests/test_builder_hardening.py` och
  `tests/test_dossier_mounting.py` skickar in `tmp_path`. Verifierat
  2026-05-08: `data/runs/` har 6 mappar både före och efter en full
  `pytest tests/ -q`-körning.
- **`B14` Låg** (stängd 2026-05-08) - efter Sprint 2A drev tre docstrings
  isär från koden: `README.md` "Engine Run"-stycket sa fortfarande att
  dev-drivern kör utan LLM-anrop, `scripts/dev_generate.py` modul-docstring
  sa "fully mocked: no LLM calls", och `packages/generation/brief/__init__.py`
  påstod att `extract_site_brief` returnerar `SiteBrief` (canonical signatur
  är `BriefResult`). Fix: docs-only commit som synkar alla tre med
  verkligheten. README listar nu också ADR 0010-0013. Test: dokumentations-
  ändringar fångas av `check_term_coverage --strict` om nya termer smyger in.
- **`B15` Medel** (stängd 2026-05-08) - `OPENAI_API_KEY` med whitespace-
  only värde (t.ex. `"   "`, `"\n"`) räknades som satt i fem callsites
  (`packages/generation/brief/extract.py`, `scripts/dev_generate.py`,
  `scripts/build_site.py`, `backoffice/views/status.py`,
  `backoffice/views/playground.py`). Det skickade real-LLM-vägen mot
  OpenAI med en tom nyckel och föll med en otydlig auth-error istället
  för att rent fall back till mock. Fix: ny `has_openai_api_key()`-helper
  i `packages/generation/brief/models.py` strippar och kollar non-empty.
  Alla fem callsites importerar samma helper. Test:
  `tests/test_brief_model_resolver.py::test_has_openai_api_key_treats_whitespace_as_missing`
  (parametriserad över fem whitespace-varianter) plus tre tester för
  unset / empty / surrounding whitespace.
- **`B16` Medel** (stängd 2026-05-08) - `scripts/build_site.py::run_npm`
  saknade `timeout`-parameter; ett hängande `npm install` eller `npm run
  build` skulle blockera buildern på obestämd tid och lämna
  `data/runs/<runId>/` halvskrivet. Fix: konstanterna
  `NPM_INSTALL_TIMEOUT_SECONDS = 600` och `NPM_BUILD_TIMEOUT_SECONDS = 300`,
  `subprocess.TimeoutExpired` fångas i `run_npm` och returnerar
  `(False, elapsed, "timeout: ...")` så `build-result.json` får
  `status=failed` istället för att processen hänger. Test:
  `tests/test_builder_hardening.py::test_run_npm_returns_failure_on_timeout`
  och `test_build_calls_run_npm_with_documented_timeouts`.
- **`B17` Medel** (stängd 2026-05-08) - `scripts/dev_generate.py`
  build-fasen läste fortfarande gamla nycklar (`scaffold`,
  `scaffoldVariant`) från Generation Package när placeholder-filen
  skrevs, trots att ADR 0013 låste den canonical formen till
  `scaffoldId` / `variantId` / `starterId`. Resultatet: placeholder
  innehöll `// scaffold: None` istället för faktiska värden. Inget
  produktionsproblem (det är en mock-fil) men exakt det driftmönster
  som ADR 0013 var skriven för att blockera. Fix: byt
  `generation_package.get('scaffold')` → `.get('scaffoldId')`,
  `.get('scaffoldVariant')` → `.get('variantId')` plus tillägg av
  `starterId`. Test:
  `tests/test_dev_generate.py::test_dev_generate_placeholder_uses_canonical_field_names`.
- **`B19` Medel** (stängd 2026-05-08, Sprint 2B) - Två nästan-parallella
  init-pipelines: `scripts/build_site.py` (Project Input → Next.js + alla
  artefakter) och `scripts/dev_generate.py` (prompt → mock artefakter)
  skrev samma artefakttyper men via olika kod-vägar - exakt det
  driftmönster ADR 0013 var skriven för att blockera. Sprint 2B introducerar
  `packages/generation/planning/produce_site_plan` som enda källan för
  Site Plan + Generation Package. Båda scripten är tunna wrappers ovanpå
  helpern: builder skickar `pinned={scaffoldId, variantId}` från Project
  Input (planSource=`pinned`), `dev_generate` lämnar `pinned=None` så
  helpern kan välja via planningModel (real när `OPENAI_API_KEY` finns,
  annars mock-no-key/mock-llm-error). Capability-map.v1-principen "tom
  dossier-lista = gap" hanteras centralt så `selectedDossiers.rejected[]`
  alltid speglar verkligheten. Builder läser nu också `starterId` från
  planen istället för att hårdkoda `marketing-base` i `copy_starter`-anropet,
  vilket gör `produce_site_plan` faktiskt auktoritativ.
  Fix: `c70392e` (Sprint 2B-commit), tightened by `6582040` (post-audit-1
  cleanup) och `e8143cf` (hygiene pass). Tester:
  `tests/test_planning.py::test_b19_dev_generate_imports_produce_site_plan`,
  `tests/test_planning.py::test_b19_build_site_imports_produce_site_plan`,
  `tests/test_planning.py::test_b19_neither_script_keeps_legacy_local_planner_function`,
  `tests/test_planning.py::test_registry_contains_at_least_two_scaffolds_with_content`.
- **`B18` Medel** (stängd 2026-05-08) - Konceptuell namnkrock: termer
  som `service-list`, `service-area`, `reviews`, `trust-badges`,
  `contact-cta`, `trust-proof` användes både som **sektioner** (i
  `local-service-business/sections.json`, vilket är korrekt per ADR
  0012) och som **Dossier-IDs** (i `compatible-dossiers.json` och
  `selectedDossiers.recommended` på alla tre Project Inputs:
  `painter-palma`, `arcade-hall`, `foto-ram`). Det är samma
  vokabulär-läcka som ADR 0012 var skriven för att rensa.
  Fix: rensade `compatible-dossiers.json` (ingen sektion listad som
  Dossier längre, comment-fältet förklarar varför), tomma `recommended`-
  listor i alla tre Project Inputs (med rationale som dokumenterar
  beslutet), `dev_generate.py` mock-plan skriver `selectedDossiers: []`
  istället för `["contact-form", "reviews"]`. Capability-map principle
  uppdaterad: "empty capability list = gap, not feature - planningModel
  must not pretend to implement a capability that has no Dossier".

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
