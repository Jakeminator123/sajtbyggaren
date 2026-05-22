# Handoff – Sajtbyggaren

**Datum:** 2026-05-22 morgon (**fräsch start efter Dev Artifact Cleanup
körd ovanpå Eval Retention v1**). Senaste produkt-/kod-commit är
`78baaa1` (`chore(tooling): add dev artifact cleanup`); senaste
Steward-commit är `686ab06` (`docs(steward): sync after dev artifact
cleanup`) plus dagens morgon-handoff. Repo är rent, synkat med
`origin/main`, full mini-eval **4/4 grön** och bugg-scope **24 aktiva,
0 misplaced, 5 unknown, 107 stängda**. Inga öppna PRs.

**Nattens cleanup-runda (ingen ny commit, bara lokal disk):**

- `--evals --keep 2 --apply`: 5 → 2 mini-eval-mappar.
- `--generated --keep 5 --apply`: 16 → 5 generated previews.
- `--python-cache --apply`: 14 → 0 cache-kataloger.
- Frigjort utrymme: ca 1.25 GB.
- `data/runs/` och `data/prompt-inputs/` rördes inte.
- Ingen kodändring och ingen commit gjordes; cleanup ändrar bara
  lokal disk under `../sajtbyggaren-output/` och repo-cache.

**Direkt nästa spår — vänta tills operatör väljer:**

1. **B125 preview-fallback-implementation** ovanpå mergat
   decision-spår (`3418cdb`, PR #58). Läs
   `governance/decisions/0025-browser-fallback-preview.md` och
   `docs/reports/b125-preview-fallback-decision-2026-05-22.md` först.
2. **Annat smalt produktspår** om operatör vill växla, t.ex. en
   bug-sweep mot låg-prio B-IDs (B97/B98/B110/...) eller någon yta
   kring Project Input/builder som mini-evalen pekade på.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många
nya starters och Project DNA V2 tills sprinten är formellt vald.

**Startprompt för ny agent:**

[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md)
har en färdig första prompt med läs-ordning, sanity-kommandon, och
gränser för vad agenten får göra utan att fråga.

**Senaste landade spår, nyast först:**

- `78baaa1` Dev Artifact Cleanup / Eval Retention v1
  (`chore(tooling): add dev artifact cleanup`).
- `a54e06f` mixed follow-up tone guard
  (`fix(builder): preserve tone intent in mixed follow-ups`).
- `991f152` naprapat tone-sweep
  (`fix(builder): handle calm trust follow-ups`).
- `25a435d` follow-up intent hardening
  (`fix(builder): harden follow-up intent handling`).
- `defd196` Mini-eval runner v1 + CSS-kaskadfix
  (`chore(eval): add isolated mini eval runner`).
- `eb5a81d` PR #57 / B139/B140 brand+tone token propagation
  (`fix(builder): propagate brand and tone tokens`).
- `aef5825` PR #56 / B71 Project DNA semantic follow-up V1
  (`feat(builder): add Project DNA semantic follow-up`).
- `3418cdb` PR #58 / B125 preview fallback decision merge
  (`docs(adr): update B125 preview fallback decision`).

PR #57 squash-mergades efter att en P2-review om foreground-token-
kontrast fixats i branchcommit `6ffc43f`; final fix-SHA för B139/B140
är `eb5a81d`.
Föregående commits
i sessionsordning från äldst till nyast: `2e274ac` (SNI core),
`bf8d6c2`, `f40564e`, `7289732` (Steward-bumpar), `e822a2c` (PR #55-
merge av annan agent), `06cdc51`, `369ed48`, `b75b664` (Steward-
bumpar), `f137f92` (SNI-followup-tooling), `1150424` (operator-rules
+ workspace autosave), `f6f4f30` (Steward-bump), `5114fb2` (Backoffice
SNI-diagnostik-utökning), `18b88c0` (Steward-bump), `919d564` (rules-
sync link-rewrite för spegel-djup), `c20270f` (Steward-bump),
`465b8fa` (separator-order-fix), `891fca0` (Steward-bump), `aef5825`
(PR #56 squash-merge), `059b4ae` (Steward efter PR #56), `eb5a81d`
(PR #57 squash-merge), `b93ed50` (Steward efter PR #57), `defd196`
(Mini-eval runner + CSS-kaskadfix), `25a435d` (follow-up intent-
hardening), `991f152` (naprapat tone-sweep), `3418cdb` (PR #58 B125
decision merge), `a54e06f` (mixed additiv + tone guard), `78baaa1`
(Dev Artifact Cleanup / Eval Retention v1).

**Mixed follow-up guard (`a54e06f`):**

- `Lägg till FAQ och gör tonen mer premium` klassas nu som `tone-shift`,
  behåller additiv service/page-merge och patchar `tone`.
- `Lägg till en lugnare sida om vår historia` är fortsatt konservativ:
  additivt page/story-scope får inte oavsiktligt patcha global tone eller
  `company.story`.
- Ny full mini-eval är fortsatt **4/4 grön**:
  `C:\Users\jakem\Desktop\sajtbyggaren-output\.evals\20260522T030947Z-mini-eval\mini-eval-report.md`.

**Dev Artifact Cleanup / Eval Retention v1:**

- `scripts/cleanup_dev_artifacts.py` finns som samlad dry-run-first
  cleanup för lokala artefakter.
- Mini-eval-runs rensas från `SAJTBYGGAREN_EVALS_DIR` eller default
  `../sajtbyggaren-output/.evals` med `--evals --keep N`; radering kräver
  `--apply`.
- Generated previews rensas separat med `--generated --keep N`; `--evals`
  rör aldrig `.generated`.
- Python-cache-cleanup (`--python-cache`) raderar bara `__pycache__` och
  `.pytest_cache` under tillåtna rötter.
- `--summary` och `--json` finns för rapportering utan radering.

**Naprapat mini-eval bug-sweep (`991f152`):**

- Root cause: `gör den lugnare och mer förtroendeingivande` matchade
  varken tone-scope/phrase-whitelist eller tone-word-map; `lugnare` och
  `förtroendeingivande` gav därför `no-semantic-change`.
- Fix: utökar den lilla follow-up tone-whitelisten med
  `lugnare`/`calmer` och `förtroendeingivande`/`trustworthy`/`tryggare`
  så prompten blir `tone-shift` och Project Input v2 får
  `tone.primary="lugn"` + `tone.secondary=["förtroendeingivande"]`.
- Guardrails: story/tagline bevaras byte-stabilt för rena tone-prompter;
  additiva prompts med `lägg till ... historia` fortsätter vara
  `no-semantic-change`; blandade additiv + tone-prompts kräver explicit
  tone-scope (`ton`, `tone`, `känsla`, etc.) för att tone-delen ska vinna;
  CSS-token-effekt är inte del av denna V1-fix.
- Ny full mini-eval är **4/4 grön**:
  `C:\Users\jakem\Desktop\sajtbyggaren-output\.evals\20260522T030947Z-mini-eval\mini-eval-report.md`.
  Naprapat-case passerar utan raw prompt-läckage; placeholder-contact-
  warnings är fortsatt väntade i mock/brief-vägen.
- PR #58/B125 decision-spår är mergat i `3418cdb`. Nästa agent bör läsa
  ADR 0025 + B125-rapporten innan eventuell preview-fallback-
  implementation startas.

**Follow-up-reviewfynd som nyss fixades (`25a435d`):**

- Additiva prompts som `Lägg till en sida om vår historia` klassas nu som
  `no-semantic-change` i stället för `story-emphasize`, så de kan inte
  skriva över `company.story` via ordet `historia`.
- Explicit story/tagline-copy kräver nu kolon (`till:`/`to:`), så
  frasen `lägg till` fångas inte längre som explicit public copy.
- `clarify` stoppar `generate_followup()` innan ny version skrivs, i linje
  med Project DNA-policyns "ingen Engine Run startas"-riktning.
- Blandade prompts som ber om flera semantiska ändringar samtidigt är
  fortfarande V1-kvalitetsglapp/multi-intent-scope, inte fixat i denna
  smala patch.

**Det som nyss landade i B139/B140-spåret (`eb5a81d`):**

- `scripts/build_site.py` har en smal token-override-kanal:
  giltig `brand.primaryColorHex` skriver `--primary`, giltig
  `brand.accentColorHex` skriver `--accent`.
- Whitelistad `tone.primary` (`grön`/`green`, `blå`/`blue`,
  `varm`/`warm`, `premium`) kan påverka tokens när explicit brand-hex
  saknas.
- Ogiltig hex ignoreras med `variant_tokens.warning` i trace och
  variant-default bevaras utan crash. Ogiltig explicit hex faller inte
  vidare till tone-keyword.
- Foreground-tokens (`--primary-foreground`, `--accent-foreground`) räknas
  om från hex-luminans/kontrast så ljusa overrides inte ger låg kontrast.
- Backoffice Wizardfält → generation visar nu brand-color/tone-token-
  kedjan som deterministisk i stället för downstream-gap.
- Tester låser helpernivå, faktisk `build(..., do_build=False)` till
  `globals.css`, invalid-hex-trace och Backoffice-diagnostiken.

**Direkt nästa spår:**

`scripts/mini_eval.py` finns nu som Mini-eval runner v1. Kör den gärna i
separat terminal medan annat Cursor-arbete fortsätter:
`python scripts/mini_eval.py` skriver en isolerad eval under
`SAJTBYGGAREN_EVALS_DIR` eller `../sajtbyggaren-output/.evals` med egna
`prompt-inputs/`, `runs/`, `generated/`, `mini-eval-report.json` och
`mini-eval-report.md`. Default-casen är elektriker Malmö, frisör Göteborg,
naprapat Stockholm och sköldpaddssoppa, med init + follow-up per case.
Runnern jämför tone/story/tagline, CSS-token-diff, raw prompt-läckage och
warnings utan att skriva till canonical `data/runs/`.

Viktigt fynd från runner-smoken: PR #57-tokenblocket låg före starter-
default-tokens i `globals.css`, så CSS-kaskaden kunde göra B139/B140-
overrides osynliga i faktisk output. `defd196` fixar detta genom att
append:a Sajtbyggarens token-block sist och låser sista token-värde i
`tests/test_builder_smoke.py`. Single-case smoke (`electrician-malmo`) är
grön och visar v2 `tone.primary=premium` + ändrade `--primary`/`--accent`.

Nästa agent bör köra full mini-eval och använda rapporten för att välja
mellan B125 preview-fallback och nästa produktspår. Starta inte embeddings,
SNI-runtime, många nya starters eller variant-promotion innan mini-evalen
visar stabilare kvalitet.

**Det som nyss landade i Project DNA-spåret (`aef5825`):**

- `scripts/prompt_to_project_input.py` har deterministisk FollowUp
  Intent-klassning för `tone-shift`, `story-emphasize`,
  `tagline-update`, `positioning-shift`, `no-semantic-change` och
  `clarify`.
- Tydliga följdprompter kan patcha exakt tillåtet Project Input-fält:
  `tone.*`, `company.story` eller `company.tagline`. Additiva/no-change-
  prompts behåller story/tagline/tone byte-stabila.
- `projectDna` skrivs i befintlig prompt-input-meta-sidecar. Full
  `data/projects/<projectId>/dna.json`-lagring är V2-scope enligt
  `governance/decisions/0027-semantic-followup-merge.md`.
- Review-fixcommitten innan squashen adresserade PR-kommentarerna:
  explicit tagline/story-copy efter `till`/`to` kan användas när den är
  publik-safe, breda content-ord som `texten`/`copy` triggar inte längre
  tone-shift själva, och `projectDna.followUpIntent` speglar senaste
  follow-up även när inga semantiska fält ändras.
- `docs/known-issues.md` flyttar B71 till stängda med fix-SHA `aef5825`.

**Sessionens tidigare tre huvudleveranser:**

1. **SNI 2025-import + Discovery-map-diagnostik** (`2e274ac` +
   `f137f92` + `5114fb2`) — stdlib-only extractor, 1882-poster
   JSON-spegel, handstyrd policy (21 huvudgrupp + 18 grupp-overrides),
   resolver-helper, lookup-CLI, Backoffice read-only diagnostik med
   coverage-gaps, confidence-breakdown och parent-chain. V1 är
   diagnostiskt; ingen runtime-konsumtion av SNI sker än.
2. **rules_sync link-rewrite** (`919d564` + `465b8fa`) — relativa
   länkar i `governance/rules/*.md` skrivs nu automatiskt om för
   `.cursor/rules/*.mdc`-speglarna så markdown-linter inte längre
   varnar om brutna paths. Hanterar parent-relative (`../policies/`),
   sibling (`*.md` → `*.mdc`), anchor- och query-suffix samt edge
   case när båda finns. 20 nya regression-tester.
3. **Operatör-finaliserade rules + workspace** (`1150424`) — två nya
   stycken i `governance/rules/always-swedish.md` om engelsk debug-
   narration och unicode_escape, plus `files.autoSave: afterDelay` i
   workspace.

**Det som nyss landade i Backoffice-polishen (`5114fb2`):**

- `backoffice/sni_diagnostics.py` får tre nya helpers:
  - `confidence_breakdown(rows)` returnerar `{high, medium, low, other}`
    räknat per policyrad. Aktuell policy: 30 high, 9 medium, 0 low,
    0 other.
  - `taxonomy_coverage_gaps(rows=None, taxonomy=None)` returnerar
    Discovery Taxonomy-kategorier som saknar varje SNI-policymappning.
    V1 har 6 gaps (landing/other/blog/business/food/music) — inte ett
    fel, bara en indikator på var policyn kan breddas i framtida sprint.
  - `lookup_parent_chain(value, reference=None)` ger samma avdelning →
    huvudgrupp → grupp → undergrupp → detaljgrupp-kedja som
    `scripts/lookup_sni.py code <CODE>` ger på CLI. Trunkerar syntetisk
    prefix-form (`56100`) till närmaste verkliga kod (`561`) så
    operatör-vänlig input fungerar.
- `backoffice/views/building_blocks.py` får tre nya UI-sektioner under
  "SNI → Discovery category": confidence-metric-rad (high/medium/low/
  other), expander för taxonomy-coverage-gaps, och parent-chain-tabell
  ovanför operator-lookup-resultatet.
- `tests/test_backoffice_sni_diagnostics.py` får 19 nya regression-
  tester som låser shape och kontrakt för alla tre helpers.

**Cleanup i samma pass:**

- `../sajtbyggaren-pr55/` worktree borttagen via `git worktree remove`
  (per PR55-agentens slut-handover 2026-05-22).
- Lokal branch `fix/viewser-followup-stale-state` raderad via
  `git branch -d` (PR55 mergad squash, origin-branch togs bort av
  PR55-agenten).
- `backup-bra-änä` är kvar både lokalt och på origin. Namnet bryter mot
  `branch-discipline.md` (åäö är förbjudet i branchnamn) men backup-
  branches får bara operatören radera. Flaggad för operatörsbeslut.

**Vad som följt-committades 2026-05-22 efter PR #55-mergen:**

- `f137f92` `feat(taxonomy): SNI follow-up tooling + cursor/git ignore
  consolidation` — 5 filer +446 rader. PR55-agentens untracked SNI-
  stödfiler stageade efter operatör-OK: `scripts/lookup_sni.py` stdlib-
  only CLI (subkommandon `code`/`text`/`section`/`level`/`stats` med
  `--json`-stöd, lint-clean, manuellt verifierat via `code 56110` ->
  full parent-chain, `text frisör` -> 9621/96210, `stats` -> 1882 items),
  `data/taxonomies/sni/README.md` dokumenterar rebuild-flödet (SCB xlsx
  -> extractor -> JSON-spegel -> radera xlsx) plus konsumentlistan,
  `.cursorindexingignore` exkluderar SNI JSON från Cursor-sökindex
  (25 000 rader bloat), `.cursorignore` speglar Read-blockeringen,
  `.gitignore` får `data/taxonomies/**/*.xlsx` säkerhetsbälte plus
  `.cursor/tmp_*` och `eval-tmp/`-konsolidering.
- `1150424` `chore(rules): finalize always-swedish additions and
  workspace autosave` — 3 filer +15/-1. Operatör-finaliserade tillägg
  som suttit unstaged genom flera sessioner: `governance/rules/always-
  swedish.md` får två nya stycken (ingen engelsk intern-debug-narration
  i chatten; ingen `unicode_escape` på redan UTF-8 svensk text utom
  för tekniska id som slug/filename/route), `.cursor/rules/always-
  swedish.mdc` är spegeln (redan synkad), `sajtbyggaren.code-workspace`
  byter `files.autoSave` från `off` till `afterDelay`.

**Cloud-agentens DNA-spår (PR #56, DRAFT):** Skapad 2026-05-22 23:59
UTC, branch `cursor/project-dna-followup-cdad`, titel `feat(builder):
add Project DNA semantic follow-up`, 5 filer +1152/-19. Lokal
orchestrator startar inga DNA-ändringar och rör inte `scripts/
prompt_to_project_input.py`, `packages/generation/discovery/resolve.py`,
Project Input-versionering eller tone/story/tagline-spåret tills cloud-
agenten flaggar PR:n ready-for-review.

**PR #55-mergen (PR55-agentens spår, inte mitt):** Stängde tre distinkta
viewser-fixar i 6 filer (113 ins / 8 del):

1. Stale-closure i `applyRunsData` (apps/viewser/app/page.tsx)
2. `setBundle(null)`-cleanup före refetch i `run-details-panel.tsx`
3. Ny `runSiteIdUnknown`-prop genom `console-drawer.tsx` →
   `project-input-picker.tsx` → `prompt-builder.tsx` som blockerar
   follow-up när `siteId === "unknown"`

3 nya regression-tester i `tests/test_viewser_files.py` låser fix-
kontrakten via regex-/substring-match. Reviewerns observation om
namnkonflikt med Discovery Resolver-konceptet stämde: PR-bodyn nämnde
ett `ApplyRunsContext`-namn som aldrig blev en *named type*. Mergens
andra commit "avoid governance term for run context" gjorde ctx inline
(`ctx?: { selectedRunId: string | null; selectedSiteId: string }`).
Squash-merge-commit `e822a2c`.

**Untracked + lokalt-modifierade filer som PR55-agenten lämnade för
operatör-/orchestrator-beslut:**

| Fil | Tillhör | Innehåll |
|---|---|---|
| `data/taxonomies/sni/README.md` | SNI-followup | Komplett dokumentation av SNI-mappen + rebuild-flöde + lookup-CLI + konsumentlista |
| `scripts/lookup_sni.py` | SNI-followup | Stdlib-only CLI med `code`/`text`/`section`/`level`/`stats`-subkommandon + `--json`. Lint-passerar; manuellt verifierat. |
| `.cursorindexingignore` | SNI + tooling | Lägger till lockfile-kommentar, `.cursor/plans/`, `.cursor/tmp_*`, `eval-tmp/`, `data/embedding-index/`, `*.mp4` och blockerar `data/taxonomies/sni/sni-2025.v1.json` från Cursor-indexering (25 000 rader JSON-bloat undviks; Read funkar fortfarande på enskilda poster) |
| `.cursorignore` | Operatör + tooling | Speglade ignores för agent Read (`embedding-index`, `.cursor/plans/`, `.cursor/tmp_*`, `eval-tmp/`, `*.mp4`) |
| `.gitignore` | SNI + operatör | `.cursor/tmp_*`, `eval-tmp/` plus `data/taxonomies/**/*.xlsx` säkerhetsbälte mot framtida xlsx-commits |
| `.cursor/rules/always-swedish.mdc` | Operatör (spegel) | Nya stycken om engelsk debug-narration och unicode_escape — speglad fil, ändras inte direkt |
| `governance/rules/always-swedish.md` | Operatör (källa) | Två nya stycken: ingen engelsk intern-debug-narration; ingen unicode_escape-decoding av redan UTF-8 svensk text |
| `sajtbyggaren.code-workspace` | Operatör | `files.autoSave: afterDelay` istället för `off` |

PR55-agenten skrev explicit i sin slutrapport att "mina otrackade SNI-
filer ... du bestämmer när de ska stageas". Operatören har 2026-05-22
bekräftat att en separat **cloud agent jobbar med Project DNA-spåret**,
så lokal orchestrator håller main stabil och rör inget DNA-relaterat
(`scripts/prompt_to_project_input.py`, `packages/generation/discovery/
resolve.py`, Project Input-versionering, tone/story/tagline/positionering)
tills cloud-agentens spår återkommer för review eller blockas.

**Föreslagen följd-Steward-pass när operatören ger OK:** commit:a
SNI-followup-filerna (README + lookup_sni.py) + ignore-/gitignore-
uppdateringarna som en samlad `docs(steward): SNI follow-up tooling +
cursor/git ignore consolidation`. Operatör-lokala filer
(`always-swedish.md` källa + spegel via `rules_sync.py`,
`sajtbyggaren.code-workspace`) kan committas separat eller stayas där
de är.

**Föregående datum-paragraf:**

**Datum:** 2026-05-22 (**SNI 2025 import + Discovery-map-diagnostik
landat på main; Project DNA / semantic follow-up är fortsatt nästa
huvudspår**). Senaste produkt-/kodläge var `2e274ac`
(`feat(governance): add SNI 2025 import + discovery map diagnostics`).
`backup-42` skapad från synkad `main`-`1edb089` + pushad till origin
innan sprintarbetet. Inga öppna PRs. Bug-scope oförändrat: **27 aktiva,
0 misplaced, 5 unknown, 104 stängda** — SNI-sprinten introducerar ingen
ny B-ID. Arbetskopian kan fortfarande ha operatörsägda lokala filer som
inte ska stageas av nästa agent: `.cursor/tmp_known_issues_pr52.md`,
`.cursor/rules/always-swedish.mdc`, `governance/rules/always-swedish.md`,
`sajtbyggaren.code-workspace` och de `.gitignore`-tillägg
(`.cursor/tmp_*`, `eval-tmp/`) som dök upp under parallell-agentarbete
mitt i sessionen.

**Det som nyss landade i SNI-sidospåret:**

- `scripts/extract_sni_2025.py` — ny stdlib-only extractor som läser
  SCB:s SNI 2025-Excel via `zipfile` + `xml.etree.ElementTree` och
  skriver deterministisk JSON utan timestamps eller BOM. CLI har
  `--source`/`--out`/`--check` där `--check` failar vid drift och
  SKIP:ar tyst när källfilen inte ligger i repo:t (förväntat normalfall
  eftersom Excel är operatörsinput, inte committad).
- `data/taxonomies/sni/sni-2025.v1.json` — canonical referens: 1882
  poster (22 avdelningar, 87 huvudgrupper, 287 grupper, 651 undergrupper,
  835 detaljgrupper). UTF-8 utan BOM, trailing newline, sorterad på
  (level, code).
- `governance/schemas/sni-discovery-map.schema.json` — schema låser
  `divisionMappings`/`groupOverrides`-shape, regex-validerar SNI-koder
  (2 siffror division, 3 siffror group) och förbjuder explicit
  `starterId`/`scaffoldId`/`variantId`/`dossierId`/`selectedDossiers`-
  fält via `false`-schemas så SNI inte kan välja runtime-objekt direkt.
- `governance/policies/sni-discovery-map.v1.json` — operatörens
  handstyrda mappning (21 huvudgrupp + 18 grupp-overrides). Spänner
  business/ecommerce/restaurant/portfolio/landing/blog/consulting/tech/
  healthcare/realestate/salon/fitness/construction/event/legal/
  accounting/auto/photo/hotel/travel/nonprofit-kategorier från
  Discovery Taxonomy. Operatörens konfidensnivå (`high`/`medium`/`low`)
  per rad så Backoffice kan visa när SNI-signal är stark vs grov.
- `packages/generation/discovery/sni_map.py` — resolver-helper med
  `normalize_sni_code()` (hanterar `56`, `56.1`, `56.10`, `56.100`,
  `56100`, whitespace, section-bokstäver, None), `load_sni_discovery_map()`
  och `resolve_sni_discovery_category()`. Algoritm: mest specifik först
  (3-siffrig grupp-override innan 2-siffrig huvudgrupp); trasig eller
  okänd kod returnerar `matchedLevel="unknown"` utan exception. Returnerar
  aldrig `starterId`/`scaffoldId`/`variantId`/`dossierId`/`selectedDossiers`.
- `backoffice/sni_diagnostics.py` — Backoffice-helper som bygger
  read-only radlista (SNI labelSv + wizardCategoryId-kandidat + Discovery
  Taxonomy-konsekvenser som `supportStatus`/scaffold/variant/starter/
  capabilities/dossiers) och en operator-lookup. Tre svenska
  varningsrader: "SNI är branschsignal, inte runtime-sanning.", "SNI
  väljer inte starter, scaffold, variant eller Dossier direkt.",
  "Discovery Taxonomy avgör fortsatt scaffold/variant/expectedStarterId/
  requestedCapabilities."
- `backoffice/views/building_blocks.py` — ny sektion "SNI → Discovery
  category" under Kontrollplan med antals-metrics (SNI-poster per nivå +
  mappning-räkningar), kategori-filter, datatabell och lookup-fält där
  operatorn matar in en SNI-kod och ser hela kedjan med Discovery
  Taxonomy-konsekvenser.
- `scripts/check_term_coverage.py` — allowlist-tillägg för SNI-helper-
  symboler (`SniDiscoveryMap`, `SniMapping`, `SniMatch`,
  `SniExtractionError`) och stdlib-symboler (`ElementTree`, `ZipFile`,
  `IndexError`, `ContentType`, `AB12`).
- 81 nya regression-tester (`tests/test_sni_extraction.py`,
  `tests/test_sni_discovery_map.py`, `tests/test_backoffice_sni_diagnostics.py`)
  som låser extractor-determinism, `--check`-drift, schema-reject av
  förbjudna direktvals-fält, resolverns testfall (alla externa-agent-
  cases verifierade: 43/432/43210, 56/561/56100, 62/620/62010, 691, 692,
  742, 931, 932, 953, 962, plus unknown/garbage-fallbacks utan exception)
  och Backoffice-diagnostikens read-only-radbyggare.

**Vad SNI inte gör i V1:** SNI får inte sätta `starterId`, `scaffoldId`,
`variantId`, `dossierId` eller `selectedDossiers` direkt. SNI är en
branschsignal som ska föreslå `wizardCategoryId`; Discovery Resolver +
Discovery Taxonomy avgör fortsatt scaffold/variant/expectedStarterId/
requestedCapabilities. Viewser-overlay, `apps/viewser/components/
discovery-wizard/*`, `/api/prompt`, `packages/generation/discovery/
resolve.py`, planning och codegen är oförändrade. Inget i runtime
konsumerar SNI; sprinten är read-only diagnostik som förbereder V2
(SNI-fält i Viewser overlay + sniCode i DiscoveryPayload + SNI-label
i composeMasterPrompt + Discovery Resolver-konsumtion av sniCode) utan
att aktivera den.

**Mid-session-fenomen:** En parallell-agent skapade branchen
`fix/viewser-followup-stale-state` med commit `042319c` mitt under min
session och min shell-context växlade tillfälligt dit; jag växlade
tillbaka till `main` utan att röra deras filer. `.gitignore` har sedan
dess lokala operatör-tillägg som inte committades i SNI-sprinten (ägs
av annat spår — sannolikt samma parallell-agent eller operatören
manuellt). Branchen `fix/viewser-followup-stale-state` finns på origin
och rörs inte av denna sprint.

**Handoff till nästa orkestratoragent:** starta med
`docs/current-focus.md`, `docs/handoff.md`, `docs/product-operating-context.md`
och `docs/orchestrator-playbook.md`. Kör `python scripts/focus_check.py`
som första steg — den ska säga `OK - repo matches docs/current-focus.md`
(inom bump tolerance om Steward-bump är pågående).

**Repo-tillstånd vid handover** (2026-05-22 03:10 CEST):

- `main` = `origin/main` = `891fca0` före denna lokala handover/docs-
  uppdatering. `docs/current-focus.md` pekar fortfarande på `465b8fa`
  inom bump-tolerance från efterföljande Steward-bumpen `891fca0`.
- PR #56 är inte längre draft: head `4b78b6a`, `mergeStateStatus=CLEAN`,
  GitHub checks gröna (`governance`, `builder-smoke`, `GitGuardian`).
  PR:n innehåller merge från aktuell `main` + follow-up-fix för false
  positives i Project DNA intentklassning (`lägg till premium produkt`,
  `lägg till personalsida`, `lägg till premium tjänst`). Nästa steg:
  slutreview/merge-beslut. Om PR:n squash-mergeas ska B71 Fix-SHA i
  `docs/known-issues.md` uppdateras av Steward efter merge.
- `backup-42` finns på origin från pre-SNI-läget som säkerhet.
- `backup-bra-änä` finns både lokalt och på origin med åäö-namn som
  bryter mot `branch-discipline.md`. **Operatör-only-beslut**; nästa
  orchestrator ska inte radera utan explicit OK.
- Working tree har lokala ändringar i `.cursorignore`,
  `.cursorindexingignore`, `governance/rules/workspace-discipline.md`,
  `.cursor/rules/workspace-discipline.mdc`, `docs/handoff.md` och den
  trackade `.cursor/plans/discovery_resolver_b121_3ec927a0.plan.md`
  (bara radslut/CRLF-varning, ingen innehållsdiff). `.cursorignore`
  har `.env`/`.env.*`/`!.env.example` kommenterade, så de är inte längre
  aktiva hårda Read-blockers i den lokala arbetskopian.
- `.env`-läget: `.gitignore` skyddar fortsatt `.env*` från commit.
  `workspace-discipline` säger nu att agenter får läsa lokala `.env*`
  inom workspacet när uppgiften kräver det eller operatören uttryckligen
  ber om det, men aldrig skriva ut hemligheter eller committa dem.
  `.cursorindexingignore` har `.env`/`.env.*` så indexet slipper dem,
  medan explicit agentläsning kan fungera när operatören ber om det.
  `.env` laddas inte automatiskt av PowerShell/Python; kommandon måste
  få env via `$env:...` eller en medveten dotenv-loader i dev-script.
- Alla guards gröna: `ruff check .` 0, `governance_validate` 18 OK,
  `rules_sync --check` OK, `check_term_coverage --strict` OK, full
  `pytest tests/ -q` grön (3 E2E skippade).
- Bug-räkning oförändrad: **27 aktiva, 0 misplaced, 5 unknown, 104
  stängda**. Sessionen introducerade inga nya B-IDs.

**Arbetsdelning 2026-05-22:** En **separat cloud agent** äger Project
DNA / semantic follow-up-spåret end-to-end via DRAFT PR #56 (branch
`cursor/project-dna-followup-cdad`). Lokal orchestrator ska **inte**
starta egna DNA-ändringar (`scripts/prompt_to_project_input.py`,
`packages/generation/discovery/resolve.py`, follow-up-versionering,
tone/story/tagline-spåret) eller review:a/merge:a PR #56 förrän
cloud-agenten flaggar den ready-for-review.

**Föreslagna lokala spår (välj ett, inte alla):**

1. **Viewser-overlay-E2E mini-eval** (Scout RO-pass) — kör
   live overlay-flödet på de fyra baseline-prompterna (elektriker
   Malmö, frisör Göteborg, naprapat Stockholm, sköldpaddssoppa) +
   `scripts/verify_run.py --json` per case. Sannolikt scout-snitt
   över 6.5/10 nu efter B132/B137/B138/B141/B143/B144 + PR #54-fixarna.
   Värdefullt produktbevis utan att röra DNA-spårets filer. Inga
   write-operationer i Builder utan Scout-OK.
2. **Preview-stabilisering / B59-B125 decision sprint** —
   landa ADR ovanpå `governance/decisions/0025-browser-fallback-preview.md`
   (status Proposed) om vilken fallback-väg (server-byggd statisk
   preview, lokal `next dev`-park, "Öppna i StackBlitz"-fallback,
   eller Vercel preview-deployments) som blir V1. Detta är launch-
   blocker för Safari/Firefox-användare. Hela ADR-passet kan göras
   utan att röra DNA-spårets kod.
3. **SNI policy v2-bredding** (om operatör vill) — utöka
   `governance/policies/sni-discovery-map.v1.json` med fler grupp-
   overrides där täckningsluckor finns (Backoffice visar nu 6
   wizardCategoryIds utan SNI-mappning: blog/business/food/landing/
   music/other; en del kan medvetet lämnas tomma, andra kan kopplas
   till specifika SNI 58/59/63/etc.). Liten policy-only-sprint utan
   runtime-ändring.

**Starta INTE i samma sprint:** embeddings, SNI-runtime-taxonomi (V2-
spår som väntar tills DNA + preview-stabilisering är klara), nya
starters utöver befintliga fyra, variant-promotion, eller
`apps/viewser`-ändringar som riskerar konflikt med PR55-spårets fixar.

**Operatör-flaggad branch som väntar på beslut:** `backup-bra-änä`
finns både lokalt och på origin med ett åäö-namn som bryter mot
`branch-discipline.md`. Backup-branches får bara operatören radera;
nästa orchestrator ska inte röra branchen utan explicit OK.

Föregående datum-paragraf:

**Datum:** 2026-05-22 (**B132/PR54-spåret avslutat; nästa spår Project
DNA / semantic follow-up**). Senaste produkt-/kodläge som verifierats är
`9225244` (`fix(backoffice): make wizard diagnostic wizard-truth-driven
(#54)`). Efterföljande Steward-docs-bumpar ligger på `e84d2fb` och
`2057241`; kör `git log -1` för faktisk lokal HEAD om ännu en docs-sync
har landat efter denna notis. PR #54 är mergad; inga öppna PRs.
Arbetskopian kan ha operatörsägda lokala filer som inte ska stageas,
bland annat `.cursor/tmp_known_issues_pr52.md`, `data/taxonomies/sni/`,
`sajtbyggaren.code-workspace` och eventuella regeländringar i
`governance/rules/` + `.cursor/rules/`.

**Det som nyss stängdes:** Backoffice-vyn "Wizardfält -> generation" är
nu wizard-truth-driven. Alla 15 `MUST_HAVE_OPTIONS` och alla 8
`CTA_OPTIONS` får egna diagnostikrader. `Priser och paket` visas som
aktiv route-emission till `/priser`; supported must-have-routes visas
som deterministic för `local-service-business`; scaffold-defaults visas
som basroutes; `Bokning online`, `Blogg / Nyheter`, `Nyhetsbrev` och
CTA-valet `Läs mer` visas som ärliga gaps/deferred/no-known-destination
i stället för att döljas. SCOUT54 gav `OK_TO_MERGE`, GitHub checks var
gröna, och PR:n mergades via squash till `9225244`.

**Live Viewser Scout-resultat:** B132 route-emission fungerar i live
overlay-artefakter. Elektriker Malmö, frisör Göteborg, naprapat
Stockholm och sköldpaddssoppa fick rätt supported routes i Run Details,
`site-plan.json` och genererade app-routes. Supported routes gav inte
längre `pageIntentWarnings`; booking/blogg/nyhetsbrev varnade ärligt när
de valdes.

**Kvarvarande blocker:** StackBlitz-iframe visade `Unable to run
Embedded Project` på alla live-runs, så Scout kunde inte visuellt klicka
igenom previewn. Det är känt B59/B125-previewspår och launch-blocker för
extern kundyta, men inte blocker för nästa interna produktspår.
Icke-blockerande UI-risk: Run Details-panelen kan bli stale när
operatören byter äldre run i listan; artefakterna var korrekta enligt
verifieringsscriptet.

**Handoff till ny orkestratoragent:** starta med
`docs/current-focus.md`, `docs/handoff.md`, `docs/product-operating-context.md`
och `docs/orchestrator-playbook.md`. Nästa huvudspår är Project DNA /
semantic follow-up med B71 som primär buggankare: följdprompt ska kunna
ändra tone/story/tagline/positionering synligt i v2 utan rå prompt-läckage
och utan drift i oändrade fält. Börja read-only: kartlägg
`scripts/prompt_to_project_input.py::merge_followup_project_input`,
aktuella Project Input-versioner och vilka artefakter som ska visa
skillnaden. Föreslå sedan en smal Builder-sprint med regressionstester
och eventuell ADR om kontraktet behöver ändras. Starta inte embeddings,
SNI-runtime-taxonomi, nya starters, variant-promotion eller B59/B125-
preview-fallback i samma sprint.

**SNI-notis:** operatören har flyttat SNI-underlaget till
`data/taxonomies/sni/sni-2025.xlsx`. Det ska tills vidare behandlas som
referensmaterial för senare bransch-/taxonomy-spår, inte som runtime-
sanning.

Föregående datum-paragraf:

**Datum:** 2026-05-21 (kvällen, **B132 follow-up Builder-sprint pushad
ovanpå Backoffice-diagnostiken `0ff2a54`**). Lokal `main` och
`origin/main` är `63d7264` (`feat(builder): emit wizard mustHave routes
for local-service-business`). Inga öppna PRs.
Bug-scope **oförändrat**: 27 aktiva, 0 misplaced, 5 unknown, 104 stängda
— sprinten är en produktutvidgning av B132-spåret från "warning-only
observability" till faktisk route-emission, inte en ny bug-fix.
`backup-41` skapad från synkad `main`-`0ff2a54` + pushad till origin
innan sprintarbetet. Lokalt finns fortfarande operatörsägda filer som
inte ska stageas: `.cursor/plans/discovery_resolver_b121_3ec927a0.plan.md`
(deleted), `sajtbyggaren.code-workspace`,
`.cursor/tmp_known_issues_pr52.md`, `sni-2025.xlsx` och eval-arbetskatalog
`eval-tmp/` (lokal mini-eval-output).

**Det som nyss landade i Builder-sprinten:** Wizard `mustHave` som
innehåller `FAQ`, `Bildgalleri`, `Karta / Hitta hit`, `Vårt team`,
`Priser och paket` eller `Portfolio / Case` får nu riktiga routes
(`/faq`, `/galleri`, `/karta`, `/team`, `/priser`, `/portfolio`) i
stället för enbart `pageIntentWarnings` — under förutsättning att
scaffolden är `local-service-business`. ecommerce-lite + framtida
scaffolds får warnings tills deras renderer-set granskats explicit.
`Bokning online`, `Blogg / Nyheter` och `Nyhetsbrev` håller
warning-shape med specifika reason-strängar så Backoffice/Run Details
kan skilja "integration saknas" från "scaffold har ingen sådan yta".
Ingen falsk booking-, betal-, auth- eller nyhetsbrev-integration emitteras.

**Filer som ändrats:**

- `packages/generation/planning/plan.py` — nya helpers
  `_wizard_extra_routes` + `_insert_wizard_extras_before_contact` plus
  konstanter `_WIZARD_ROUTE_DEFINITIONS`, `_WIZARD_ROUTE_SCAFFOLDS`
  (frozenset, `local-service-business` opt-in),
  `_WIZARD_ROUTE_UNSUPPORTED_REASONS`. `_page_intent_warnings` får
  specifika reason-strängar för unsupported pages. `produce_site_plan`
  infogar wizard-extras i routePlan EFTER scaffold-trim men FÖRE
  kontakt-routen (matchar nav-layouten). `_trim_route_plan` rör inte
  wizard-extras (operatörens explicita val vinner över
  `brief.pageCount`-trim).
- `scripts/build_site.py` — nya render-helpers `render_faq`,
  `render_gallery`, `render_team`, `render_pricing`, `render_portfolio`,
  `render_map` + delade `_wizard_section_heading`,
  `_wizard_contact_cta`, `_wizard_page_footer`, `_faq_pairs`,
  `_gallery_images`, `_team_members`, `_url_quote`. Renderar ärlig
  svensk copy med fallback ("Vi laddar upp bilder snart...", "Pris
  efter offert", "Vägbeskrivning kommer...") när dossier-data saknas.
  `write_pages` får ny `extra_routes`-parameter med dispatch via
  `_WIZARD_ROUTE_RENDERERS`. `render_layout` + `_nav_items_from_scaffold`
  får `extra_routes`-stöd som infogar wizard-extras före kontakt i nav.
  Ny `_extract_wizard_extra_routes` läser `site_plan["routePlan"]` så
  routePlan är single source of truth för dispatch. `build()` trådar
  wizard-extras genom `routes_to_write` så Quality Gate route-scan
  kollar både scaffold-defaults och wizard-routes.
- `scripts/check_term_coverage.py` — `.cursor/tmp_*`-prefix exkluderas
  (samma kategori som `.cursor/plans/` och `.cursor/rules/`); 6 nya
  Next.js page-komponenter (`FaqPage`, `GalleryPage`, `MapPage`,
  `PortfolioPage`, `PricingPage`, `TeamPage`) registrerade i
  `COMMON_WORDS` som React-symboler.
- `tests/test_page_intent.py` — omformulerade kontrakt: warning bara
  för unsupported pages (booking + blogg), emission för supported
  pages (FAQ + Bildgalleri etc.), ecommerce-lite får warning även för
  supported pages, B138+B132-interaktion (trim rör inte wizard-extras),
  end-to-end build-result-test som verifierar både `/galleri` +
  `/karta` page.tsx-filer och bibehållen warning för booking.
- `tests/test_wizard_route_emission.py` (NY, ~350 rader) — 16 nya
  tester som täcker plan-helper, build-helper, enskilda
  render-funktioner, `write_pages`-dispatch och nav-utvidgning.
- `docs/current-focus.md` + `docs/handoff.md` (denna fil) — sprint-info
  och nästa-steg-direktiv.

**Mini-eval-resultat (CLI, mock-väg, `--skip-build`, 4 cases):**

| Case | Wizard mustHave | Routes före | Routes efter | Warnings före | Warnings efter |
|---|---|---|---|---|---|
| elektriker Malmö | `Portfolio / Case`, `FAQ` | 4 | 6 (`/portfolio`, `/faq`) | 2 | 0 |
| frisör Göteborg | `Bokning online`, `Priser och paket`, `Bildgalleri`, `Karta / Hitta hit` | 4 | 7 (`/priser`, `/galleri`, `/karta`) | 4 | 1 (booking, ärlig reason) |
| naprapat Stockholm | `Vårt team`, `Bokning online`, `Karta / Hitta hit`, `FAQ` | 4 | 7 (`/team`, `/karta`, `/faq`) | 4 | 1 (booking, ärlig reason) |
| sköldpaddssoppa | `FAQ` | 4 | 5 (`/faq`) | 1 | 0 |

Alla fyra builds gröna med `status=skipped` (förväntat med `--skip-build`).
Sköldpaddssoppa-spåret: B137 + B138 + Intent Guard light fortsätter
fungera oförändrat (`_trim_route_plan` rör inte wizard-extras, tagline-
läckage-skyddet ovanpå). I denna mock-baserade eval returnerade
briefen inte `pageCount: 2` så B138-trim triggade inte live; det är ett
pre-existing LLM-variations-fenomen, inte en regression från denna
sprint.

**Tester/guards efter sprinten:**

- `python -m ruff check .` — 0 findings.
- `python scripts/governance_validate.py` — 17 OK.
- `python scripts/rules_sync.py --check` — OK.
- `python scripts/check_term_coverage.py --strict` — OK (efter
  allowlist-tillägg för `.cursor/tmp_*` + 6 Next.js page-symboler).
- `python -m pytest tests/ -q` — alla passerar; 3 skippade E2E
  (oförändrat).
- Fokuserad: `tests/test_page_intent.py` (9 passerar),
  `tests/test_wizard_route_emission.py` (16 passerar). Plus
  `tests/test_builder_route_emission.py` (80 passerar, inga
  regressioner), `tests/test_builder_hardening.py`,
  `tests/test_planning.py`, `tests/test_intent_guard.py`.

**Risker/öppna trådar:**

- Sköldpaddssoppa-eval körde mock-brief som inte gissade
  `businessTypeGuess: "restaurant"` — Intent Guard-warningen för
  `fitness` + `mat` triggade därför inte i in-memory-evalen. Det är
  pre-existing mock-output-variation; live-LLM-flödet bör fortsätta
  emittera warningen som vanligt eftersom `_intent_guard_warnings`-
  koden i `scripts/build_site.py:build_plan_artefakts` är oförändrad
  av denna sprint.
- `Bokning online`-warning är medvetet kvar — en framtida sprint som
  inför riktig bookingUrl-integration (separat datakanal i
  Project Input + render_booking-helper med external-link CTA) kan
  flytta det från warning till route.
- Render-helpers för wizard-routes använder `_jsx_safe_string` för all
  customer-supplied data, så JSX-special-chars och B30-disciplinen
  bevaras. Däremot är de svenska fallback-strängarna när dossier-data
  saknas hårdkodade i Python ("Vi laddar upp bilder snart...", "Pris
  efter offert", etc.) — engelska sajter (`language=en`) får svensk
  fallback. Detta är en känd icke-blocker som passar en framtida
  i18n-sprint.
- Eval-output ligger i `eval-tmp/` lokalt; raderad innan commit
  (operatör kan inspektera om hen vill köra mini-eval igen).
- `scripts/verify_run.py` letar bara i `data/runs/` (inte i
  `eval-tmp/runs`) — eval kördes mot eval-tmp så `verify_run.py`
  användes inte direkt i denna sprint. Nästa Scout som kör mini-eval i
  Viewser-overlayflödet får artefakter under `data/runs/` och kan
  använda `verify_run.py --json` som vanligt.

**Scout RO-review redan körd:** verdict `OK_PUSH` med PASS på alla sex
acceptanskriterier (scope, ingen falsk integration, opt-in scaffold,
testtäckning, `_intent_guard_warnings` orörd, `packages/generation/discovery/resolve.py`
orörd). Pushen är gjord på `63d7264`; Steward-bumpen ligger på
`f178456`. Scout föreslog tre framtida regression-tester som **inte** är
blockers: `test_page_intent_warns_nyhetsbrev_with_newsletter_reason`
(spegel av booking/blogg), parametriserade mini-eval-fixtures som låser
operatörens före/efter-tabell, och negativt test för okänt wizard-id i
`routePlan` utan registrerad renderer.

**Nästa agent ska göra:** starta en read-only Viewser-overlay-mini-eval
Scout mot post-push-`main` = `f178456`. Scouten ska verifiera att de
emitterade routes faktiskt landar i StackBlitz preview och att
Backoffice Building Blocks-vyn speglar de nya routes-emissionsvägarna
korrekt. Mini-eval-direktivet är oförändrat (sköldpaddssoppa,
elektriker, frisör, naprapat) men med nya acceptanskriterier per case
(se `docs/current-focus.md` → "Next action").

Föregående datum-paragraf:

**Datum:** 2026-05-21 (Backoffice wizardfält-diagnostik). Lokal `main` och
`origin/main` är `650c518` (`feat(backoffice): add wizard propagation
diagnostics`). Inga öppna PRs. Bug-scope är oförändrat: **27 aktiva, 0
misplaced, 5 unknown, 104 stängda**. `backup-41` finns på origin från
pre-sprint-läget. Lokalt finns fortfarande operatörsägda filer som inte
ska stageas i nästa sprint: `.cursor/plans/discovery_resolver_b121_3ec927a0.plan.md`
(deleted), `sajtbyggaren.code-workspace`, `.cursor/tmp_known_issues_pr52.md`
och `sni-2025.xlsx`.

**Det som nyss landade i `650c518`:** Building Blocks/Kontrollplan har en
ny read-only del "Wizardfält → generation". Den visar kända wizardfält,
destination, `status`, `propagationLevel`, source chain och source path.
Vyn skiljer deterministiska mappings från prompt-signaler, Project
Input-only/downstream-gap och diagnostic-only. Den läser befintlig
Discovery Taxonomy, Capability Map, Dossier Selection och resolverns
mapping-konstanter, men skriver inget och är inte ny runtime-sanning.
Fokuserade tester finns i `tests/test_backoffice_discovery_wizard_diagnostics.py`.
Guards gröna: ruff, governance, rules sync, term coverage, fokuserad
backoffice/discovery-svit och full `pytest tests/ -q` efter att
`/sajtbyggaren-output` fick write-permissions enligt AGENTS.md.

Föregående datum-paragraf:

**Datum:** 2026-05-21 (post-merge Steward-sync). Lokal `main` och
`origin/main` är `5dfa2c7` (`fix(codegen): close B141 brief-ref summary
contract (#52)`). Inga öppna PRs. Bug-scope är **27 aktiva, 0 misplaced,
5 unknown, 104 stängda**. Lokalt finns fortfarande operatörsägda filer som
inte ska stageas i nästa sprint: `.cursor/plans/discovery_resolver_b121_3ec927a0.plan.md`
(deleted), `sajtbyggaren.code-workspace`, `.cursor/tmp_known_issues_pr52.md`
och `sni-2025.xlsx`.

**Det som nyss landade:** B144 är inne på main sedan `aee67d7`: Run
Details visar `pageCountWarning`, `intentGuardWarnings` och
`pageIntentWarnings` från `site-plan.json` i UI:t. B143 är inne via
`d3b77ff`/PR #53: befintlig Intent Guard-tabell utökades med engelska
business-type-slugs och bevarar warning-shape `{categoryId,
conflictingTerm, reason, businessTypeGuess}`. PR #51 var ett felspår och
stängdes utan merge. B141 är inne via `5dfa2c7`/PR #52: codegen-summaryn
laddar faktisk Site Brief via `siteBriefRef`, medan Generation Package
fortsatt är by-reference och inte duplicerar inline `siteBrief`.

**Viktig produktbedömning:** B144 är ett tydligt operatörslyft. B141
stänger ett riktigt LLM-flödesglapp. B143 är däremot taktisk
ord-/slugmatchning, inte embeddings eller governance-ägd branschtaxonomi.
Starta inte embeddings, ny Intent Guard v2, nya starters eller
variant-promotion innan vi har mätt post-merge-flödet.

**Nästa agent ska göra:** starta en read-only Scout för
Viewser-overlay-mini-eval mot `650c518`. Kör minst sköldpaddssoppa
conflict-case, elektriker Malmö, frisör Göteborg och naprapat Stockholm.
Verifiera renderad output, Run Details-varningar och relevanta
`site-plan.json`-fält; använd `python scripts/verify_run.py --site-id <X>
--json` där artefakter finns. Beslutsregel: snitt >= 7 och inget case
under 6.5 -> Project DNA / semantic follow-up. Annars riktad Builder
bug-sweep på sämsta case. Steward ska först verifiera att
`docs/current-focus.md` pekar på `650c518` och att `python
scripts/focus_check.py` inte längre varnar för stale focus.

**Datum:** 2026-05-21 (B144 + PR #51-stop). Lokal `main` har `aee67d7` (`fix(viewser): close B144 - render site-plan warnings`) ovanpå `c2f0b0b`; en Steward-docs-sync följer som bump-tolerance-commit. `backup-40` finns på origin från pre-B144-läget. **B144 är klar:** Run Details renderar nu `pageCountWarning`, `intentGuardWarnings` och `pageIntentWarnings` från `site-plan.json` i amber-blocket `site-plan-warnings`; testlåset är `tests/test_viewser_files.py::test_run_details_panel_renders_site_plan_warnings`. Bug-scope efter B144: **29 aktiva, 0 misplaced, 5 unknown, 102 stängda**. **PR #51/B143 ska inte mergas:** Scout RO-review 2026-05-21 gav verdict stop eftersom branchen bygger på pre-Intent-Guard-main, skapar parallell `_intent_guard_warnings`/`_INTENT_GUARD_CONFLICTS`, ger dead code efter merge, får add/add-konflikt i `tests/test_intent_guard.py`, duplicerar B143 i `docs/known-issues.md` och byter warning-shape bort från schema/B144-UI-kontraktet. Nästa B143-arbete ska starta på current `main`, bevara warning-shape `{categoryId, conflictingTerm, reason, businessTypeGuess}`, och utöka befintlig Intent Guard med engelska slugs eller bucket-normalisering. **PR #52/B141** (`cursor/codegen-brief-data-ef0b`) är separat cloud-grind-spår; reviewa/mergea bara efter rebase mot current `main`, gröna checks och verifierat disjunkt scope från B143/B144. Tidigare datum-paragraf:

**Tillägg 2026-05-21:** `origin/main` är nu `bb76c2a` efter B144 + Steward-sync. **PR #53** (`cursor/b143-intent-guard-en-slugs-5156`) ersätter PR #51 för B143 och verkar ha rätt kod-scope (befintlig `_INTENT_GUARD_CONFLICTS` utökas, warning-shape bevaras), men GitHub `governance` är röd på docs-format: B143-stängningsposten använder `öppnad + stängd` + em dash och matchar inte `list_open_bugs.py`-kontraktet. Fixa till `- **\`B143\` Medel** (stängd 2026-05-21, Intent Guard English slug matching) - ...` och summary `28 aktiva / 103 stängda`, kör om checks, sedan Scout-review. **PR #52** har gröna checks men `mergeStateStatus=dirty`; rebase krävs före merge och bug-scope-räkningen beror på om #53 landar först.

**Datum:** 2026-05-21 (Builder-sprint: B137 + B138 + Intent Guard light landade i 4 commits ovanpå `8ba2b20`; aktuell `origin/main` HEAD är `da79056` per separat **Aktuell repo-HEAD**-rad nedan). **Builder-sprint 2026-05-21 ovanpå `8ba2b20`:** Riktad bug-sweep på Scout case 4 (sköldpaddssoppa). Fyra commits direkt på `main` efter `backup-37`-pushen: `3875716` (chore — operatör-lokala plan-filer skippas i `check_term_coverage.py` + `.gitignore`; samma kategori som `.cursor/rules/`-speglar), `1b5275d` (**B137** wizard-overlay tagline-sanering: ny `_offer_looks_like_ui_directive()`-helper i `packages/generation/discovery/resolve.py:_apply_company_fields` detekterar UI-direktiv via sidantals-regex `\b\d+\s+sidor?\b`, färg-regex `\b(röd|grön|blå|gul|svart|vit|grå)a?\s+(färger|färg|tema)\b`, instruktions-prefix `"hemsida om"`/`"bygg"`/`"skapa"`/`"gör en"`/`"vill ha"`/`"behöver"` och längd-bounds 8-120 tecken; brief-taglinen får företräde när offer matchar UI-direktiv, fallback till `_derived_fallback_tagline()` om brief saknar; ny `"derived"`-värde i `FieldSourceLiteral` + `discovery-decision.schema.json`-enum; 10 nya tester i `tests/test_discovery_resolver.py` med modul-lokal `BLOCKED_TAGLINE_PHRASES`-fixture), `299257d` (**B138** `brief.pageCount` → `routePlan`: ny `_trim_route_plan()` i `packages/generation/planning/plan.py` läser `site_brief["pageCount"]` och trimmar route_plan med prioritetslista `home`+`contact` aldrig borta, minsta körbara set = 2, fyller mitten i scaffold-defaultordning; ny optional `pageCountWarning`-property i `site-plan.schema.json` med `reason ∈ {"trimmed-to-brief-page-count","below-minimum-keeping-default"}`; trim funkar både för pinned-vägen (`scripts/build_site.py`) och planning-helper-vägen; 7 nya tester), `da79056` (**Intent Guard light**: ny `_intent_guard_warnings()` i `scripts/build_site.py:build_plan_artefakts` läser `prompt_meta["discoveryDecision"]["categoryIds"]` + `site_brief.businessTypeGuess`/`servicesMentioned` och emitterar non-blocking warnings vid konflikt; konflikt-tabell minimal i v1 — `fitness`/`construction`/`beauty` mot svenska term-set; warning-only, blockar inte build; ny optional `intentGuardWarnings`-array i `site-plan.schema.json`; ny `intent_guard_warnings`-parameter på `produce_site_plan` med bakåtkompatibel default `None`; 12 nya tester). **End-to-end-mätning på sköldpaddssoppa-payload (in-memory)**: tagline gick från `"Hemsida om sköldpaddssoppa, mat, 2 sidor, gröna färger"` till `"Tydlig hjälp inom restaurant"` (source: `"brief"`); routes gick från `[/, /tjanster, /om-oss, /kontakt]` (4) till `[/, /kontakt]` (2) med `pageCountWarning`; `intentGuardWarnings` emitterar `{categoryId: "fitness", conflictingTerm: "mat", businessTypeGuess: "restaurant", reason: "category-vs-business-mismatch"}`. **B137 + B138 stängda** i `docs/known-issues.md`. **B139/B140/B141 lämnas öppna** (out of scope per coach + operatör-OK). Backup-branch `backup-37` skapad från `main`-`8ba2b20` + pushad till origin INNAN sprintarbetet. Push-strategi (c) per operatör-OK 2026-05-21: backup-37 + commits direkt på `main`, ingen PR-flow. Buggräkning: **28 aktiva, 0 misplaced, 5 unknown, 101 stängda** (B137 + B138 stängda; B129 + B142 stängda i tidigare pass; tidigare 30 aktiva, 99 stängda). 29 nya regression-tester. Alla 5 guards gröna före push: ruff (0), governance_validate (17 OK), rules_sync --check (sync), check_term_coverage --strict (inga okända), pytest tests/ -q (319 passed, 3 E2E skipped). **Edge-case-rester noterade till framtida sprint:** (a) B137 ensamt färgord utan `färger`/`färg`/`tema`-suffix passerar detektorn (acceptabel risk för v1, dokumenterat i `_offer_looks_like_ui_directive`-docstring); (b) Intent Guard konflikt-tabell är minimal v1 — 3 kategorier × ~4 termer per kategori (utbyggnad vid Scout-fynd av nya false-negative-case); (c) Intent Guard mirrors INTE warnings till `build-result.json` denna sprint — Backoffice/Run Details läser `site-plan.json` direkt; (d) `_derive_tagline` i `scripts/prompt_to_project_input.py` inte lyft till paket-modul (skopet förblev minimalt, derived fallback klarade sig med inline-helper i resolve.py). **PR #48** (`cursor/adr-0026-embeddings-postponed-f36b: docs(adr): add 0026 — embeddings parkeras tills LLM contract propagation klar`) är öppen men utanför min scope — operatören får hantera den separat (focus_check flaggade den för Steward-update när nästa Steward kör). **Tre-commit-budget** (per coach plan) blev 4 commits — chore-infra-commiten lades till för att hantera `.cursor/plans/`-skip + `.gitignore` så future agent-plan-filer inte triggar term-coverage. Operatören accepterade detta implicit via "kör"-direktivet. Tidigare datum-paragraf:

**Datum:** 2026-05-19 (sen kväll, post-Orkestrator-pass: Scout case 4 sköldpaddssoppa körd + B137 öppnad + ADR 0025 (B125) levererad av Cloud Agent B + två nya governance-regler aktiverade (`shell-windows-defaults.md` + `branch-discipline.md` here-string-pattern); aktuell `origin/main` HEAD är `9089b7a` per separat **Aktuell repo-HEAD**-rad nedan). **Steward Pass 1 ovanpå `9089b7a`:** B138 + B139 öppnade (B138 Medel: pageCount-läckage från brief till routePlan i sköldpaddssoppa-runen; B139 Låg-medel: tone-extraction propageras inte till brand-tokens), B137-fix-pekare flaggad som WIP via NOTE i `docs/known-issues.md` (discovery-metans `fieldSources.company.tagline = "wizard"` säger att taglinen kommer från wizard-overlay-mappningen, inte från `prompt_to_project_input.py`), Scout RO-pass pågår parallellt och kartlägger exakt kodväg; Steward Pass 2 uppdaterar B137-entryn efter Scout-rapport. Bug-räkning bumpas 26 → 28. **Steward Pass 2 ovanpå `1d6fadf` (denna commit, post-PR #47-merge):** Efter Scout RO-rapport `docs/reports/scout-wizard-tagline-pagecount-tone-2026-05-19.md` uppdaterades fix-pekarna för B137 (från `scripts/prompt_to_project_input.py:_derive_tagline` till `packages/generation/discovery/resolve.py:_apply_company_fields` rad 609-628 — wizardens `answers.offer` skriver över briefens tagline efter brief-produktion; `_derive_tagline` kvarstår som fri-prompt-fallback) och B139 (från `packages/generation/codegen/` till `scripts/build_site.py:variant_css()` rad 701-737 + `patch_globals_css()` rad 2107-2136); B140 (Låg, ny: `brand.primaryColorHex` ignoreras av `variant_css` — separat data-kanal från B139:s tone-extraction) och B141 (Låg-medel, ny: `packages/generation/planning/plan.py:_assemble_generation_package()` skriver bara `siteBriefRef`, INTE `siteBrief`-objektet, så `packages/generation/codegen/codegen.py:_summarise_generation_package()` läser `tone`/`businessType` från död pipeline) öppnade. NOTE-blockquoten i B137-entryn från Pass 1 borttagen. Bug-räkning bumpas 28 → 30. Inga produktfiler rörda — Builders sprint öppnar nästa. **Steward Pass 3 ovanpå `bfab769` (denna commit):** Builder-pass `f8d6a52` (`feat(viewser): sync ProjectInputPicker to selected run`) + dev-tooling-commit `bfab769` (`chore(dev-tooling): default Viewser to HTTPS locally`) landade mellan Pass 2 och Pass 3; Pass 3 öppnade + stängde **B142 (Låg-medel, ProjectInputPicker följer vald run)** i samma docs-commit — operatörspanelen kunde visa fel runs Project Input (t.ex. `painter-palma` medan vald run var `snus-ab`), Fix: `f8d6a52`, Test: open med ärlig nice-to-have-rad i Queue eftersom dedikerad React-state-test för run-following saknas i repo idag. Bug-räkning bumpas 30 aktiva oförändrat / 98 → 99 stängda. Inga produktfiler rörda i Pass 3 — Builder-passet kickas direkt efter denna push. Tidigare datum-paragraf gällde keramik-/e-handel-passet `bfcad8d` ovanpå `923f680`/`6e5c33c`/`d1fee90`. Riktad Builder-runda stängde **B101** (hero-CTA shop-variant → /produkter via ny `_hero_cta_target_path`-helper), **B102** (`/produkter`-bottom-CTA shop-ton via ny `_commerce_bottom_cta_label`-helper med whitelist; länken mot kontakt-routen behålls eftersom builder MVP saknar checkout) och **B128 (Hög, ny + stängd same-day)** (planner-imperativ-läcka till /om-oss — `_customer_safe_planner_note` släppte igenom svenska/engelska build-imperativ i `notesForPlanner` ("Bygg en liten e-handel på svenska för försäljning av keramik med fokus på köpkonvertering."); ny `_starts_with_planner_imperative()`-guard + utökad `_PLANNER_NOTE_BLOCKLIST` med operator-tokens). Composer-2.5 read-only review hittade en B128 bypass där ledande icke-bokstavsprefix (`-Bygg ...`, `**Bygg ...**`, `1. Bygg ...`) slipped past — hardening `bfcad8d` strippar en run av ledande non-letter-chars före token-match så markdown/list/numeral-wrappade imperativ blockeras identiskt med rena. Separat dev-tooling-commit `6e5c33c` lägger opt-in `-Https`-flag i `scripts/dev-viewser.ps1` så Viewser kan starta på `https://localhost:3000` (StackBlitz embed-konsol kräver https://-origins). Variant-spåret `feat/eight-scaffold-variants` (commit `4cd1058`, åtta gpt-5.4-genererade scaffold-varianter) finns kvar på origin som separat feature-branch och rörs inte i detta pass — coach-direktiv: ingen variant-promotion under Steward eller Scout, separat sprint/PR krävs. Föregående pass (B121 discovery-integration sealed via PR #34–#37, merge `e3fa67b`): PR #31 `feat(viewser): integrate christopher-ui discovery and asset workflow` mergades via fast-forward — merge-commit `3f4543d`, integrationscommit `0510146`. Den lyfte in hela discovery wizard, asset upload pipeline, URL-scrape, SiteHeader/ConsoleDrawer, shadcn-primitives, schema-fält för brand/gallery och naming-dictionary v15 → v16. Bugsweep i tre rundor med totalt 13 commits direkt på main: `d63fab3` (BuildProgressCard `elapsedSec`-reset), `61da065` (`--discovery` + `--followup-site-id` rejection), `d06e628` (pyright optional-narrowing cleanup), `cd03897` (B113 SSRF redirect-validation + 6 regressionstester), `fe9748e` (B114 early `Content-Length`-guard i `/api/upload-asset`), `07f9cbb` (docs-bump runda 1), `6772a14` (B117 SVG-XSS via CSP sandbox + nosniff på `/api/asset-preview`), `df24488` (B118 scrape-runner SIGKILL-fallback), `0361121` (docs-bump runda 2), `c7049b3` (operatör-direktcommit, `package-lock.json`-städning från postcss-override `^8.5.10` i `apps/viewser/package.json` som tystar npm audit GHSA-qx2v-qp2m-jg93 — Vercels eps1lon säger explicit att det är false positive eftersom postcss bara körs vid build-tid och inte på untrusted CSS, men 0 vulnerabilities är värt 3 rader JSON), `5f23d13` (B123 cross-origin isolation headers — `Cross-Origin-Embedder-Policy: credentialless` + `Cross-Origin-Opener-Policy: same-origin` i `apps/viewser/next.config.ts` + 4 source-locks i `tests/test_viewser_isolation_headers.py`; tog bort gammal felformulerad negativ lock i `tests/test_viewser_files.py:test_viewser_does_not_set_global_cross_origin_isolation_headers` från `98e8364`), `e325c67` (docs B123-registrering), `5d05e0d` (B124 iframe credentialless-attribut — `document.createElement`-patch runt `sdk.embedProject(...)` i `apps/viewser/components/viewer-panel.tsx` så iframen får `setAttribute("credentialless", "")` innan src-fetch + 3 nya source-locks; även `DevTools` + `ElementCreationOptions` tillagda i `scripts/check_term_coverage.py:COMMON_WORDS`), `60515c6` (docs B124-registrering). Ovanpå `60515c6` cherrypickades sex commits från stängda PR #32 `Backoffice kontrollplan mvp` (`cursor/backoffice-kontrollplan-mvp-62aa`, skapad från `ca59529` innan PR #31-mergen så three-way merge hade haft trädets-delta-risk trots `mergeStateStatus=CLEAN` — cherry-pick valdes som säkrare väg, christopher-UI bevarades intakt): `3338d79` `fix(backoffice): normalize compatible dossier graph edges`, `b636450` `feat(backoffice): add read-only impact preview`, `c22bc1d` `feat(backoffice): add selection profile editor`, `2065a33` `feat(backoffice): improve variant candidate review`, `855a605` `fix(backoffice): use atomic model role writes`, `00103e3` `feat(backoffice): add soft dossier candidate generator`. Tillsammans lyfter de Backoffice till en kontrollplan: ny `Kontrollplan`-vy med dynamisk graf över Starters/Scaffolds/Variants/Dossiers/Model Roles + Doctor-fynd + konsekvensvy som klassificerar `riskLevel`/`runtimeEffect` per nod, ny `Selection Profiles`-vy med signal-coverage-fynd och atomic edit-toggle, refaktorerad `Variant Candidates`-vy med field-level diff + similarity-table mot canonical variants, ny `Dossier Candidates`-vy som driver `scripts/generate_dossier_candidate.py` (mirror av `generate_variant_candidate.py`: pydantic structured output via dossierModel-rollen + mock-fallback), och gemensam `backoffice/io.py` med `atomic_write_text`/`atomic_write_json` (temp + `os.fsync` + `os.replace`) som ersätter lokala helpers i `views/governance.py` + `views/llm_engine.py`. PR #32 stängdes (inte mergades) och `cursor/backoffice-kontrollplan-mvp-62aa` raderades från origin. Samtidigt rensades `frontend/christopher-import` (PR #17 CLOSED, ersattes av PR #31 från annan branch). Denna handoff-bumpcommit kommer ovanpå `0fe353f` (B126/B127-stängning). Sex nya öppna fynd registrerade över de tre review-rundorna: B115 (binär-dubbletter `/public/` vs `apps/viewser/public/`, ~3.4 MB), B116 (`BUILD_TIMEOUT_MS` 10 min globalt serialiserad), B119 (kontaktdata via alfabetisk sortering ger fel-men-plausibel-info), B120 (adress-till-stad-regex för snäv), B121 (medel arkitekturskuld — discovery-sanning splittrad i fyra lager utan explicit konfliktlösning), B122 (UI thinking→building via `setTimeout(1500)` istället för backend-signal). PR #32-cherrypicken är feature work — inga B-IDs öppnade eller stängda. B110/B111 från föregående pass kvarstår oförändrade. **B59 (StackBlitz embed parkerad efter 2026-05-15 header-experiment) är förmodligen löst i B123/B124 för Chromium-browsers** men kvar att operatörverifiera end-to-end med en grön preview innan den stängs formellt. **B125 (Hög, produktblocker innan launch) registrerad** efter operatörsdiskussion 2026-05-18: embedded StackBlitz/WebContainer-preview funkar bara i Chromium (Chrome 110+, Edge, Brave, Vivaldi) — Safari (inkl. iPhone) och Firefox kan inte ladda embeddet. ~25-35% av svenska SMB-slutkunder behöver server-byggd fallback för preview-fliken. Slutpublicerade kund-sajter är vanlig Next.js och funkar i alla browsers. Browser-support-kravet dokumenterat i README.md "Browser-stöd för preview-läge" och `docs/product-operating-context.md` "Runtime och preview". Fyra fallback-kandidater listade i B125 — beslut ska landa i ny ADR innan implementation. Aktuellt bug-scope: **25 aktiva, 0 misplaced, 5 unknown, 91 stängda** (B101 + B102 + B128 stängda i `d1fee90` + `bfcad8d`; B121 stängd i `e3fa67b`; B126 + B127 stängda i `0fe353f`; **B129 ny** — `_DEFAULT_VARIANT_BY_SCAFFOLD` hardcoded i `plan.py` istället för governance, registrerad i PR #38 post-merge-triage). **Direkt nästa uppgift:** **Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning via det faktiska overlayflödet (4-6 case inkl. keramik som verifierar B101/B102/B128 live, tjänsteföretag med adress, scrape-case, sköldpaddssoppa-conflict, "2 sidor"-case och follow-up). Se `docs/current-focus.md` → "Next action". B123/B124-end-to-end-verifikation (Chromium-browser + `npm run dev` i `apps/viewser/`) och nya backoffice-vyerna (Kontrollplan, Selection Profiles, Variant Candidates, Dossier Candidates via `streamlit run backoffice.py --server.headless true`) kan operatören köra när det passar — det är inte längre prerequisite för nästa sprint. **Därefter:** ny ADR för B125-fallback-väg (server-byggd statisk preview vs lokal `next dev`-park vs "Öppna i StackBlitz"-fallback vs Vercel preview-deployments) + Re-Verifierings-Scout 5 med fyra demo-prompter.)
**Aktuell repo-HEAD på `main`:** `c2f0b0b` (`chore(term-coverage): allowlist status-strängar för verify_run.py`, 2026-05-21, kvällen, post-sprint tooling + reviewer-feedback bump). Sedan `da79056`: `432d2ab` (Builder-Steward-bump), `cdb2063` (post-rebase chore), `5573bb9` (PR #48 ADR 0026 mergad), `7288d3d` (PR #49 Run Details inventering mergad; PR #50 stängd som duplikat), `38f86da` (orchestrator-commit: `chore(tooling): add verify_run.py + agent-integration docs` — nytt stand-alone verktyg `scripts/verify_run.py` med 9 checks + JSON-output, `docs/tools/verify_run.md` ger agent-integrationsguide, `docs/agent-handbook.md` får ny "Post-build-verifiering utan preview"-sektion), `c2f0b0b` (term-coverage allowlist). **Live-verifiering bekräftad** på sköldpaddsoppa-ab-c39f01: B137 + Intent Guard fungerar end-to-end; B138 in-memory-bevisad men ej triggad live (briefen returnerade `pageCount: None` denna körning). **Extern reviewer-feedback ~7/10:** två nya buggar öppnade — **B143 (Medel)** Intent Guard slug-glapp svenska↔engelska, **B144 (Medel)** intentGuardWarnings + pageCountWarning renderas inte i Run Details UI. Bug-räkning: **30 aktiva, 0 misplaced, 5 unknown, 101 stängda**. **Nästa orkestrator-fokus:** B144 frontend-render-sprint (störst praktiskt värde — stänger gapet mellan sanning-i-artefakter och operatörens arbetsyta), eventuellt kombinerat med B143 slug-hardening (1-1,5h). PR #49-inventeringen ger redan placeringsskissen för B144.

**Föregående repo-HEAD på `main`:** `9089b7a` (`chore(term-coverage): allowlist 'B137 fix' phrase in Steward-prose`, 2026-05-19, sen kväll). Sedan `ed1d743` har 8 commits landat under Orkestrator-pass: `840e73f` (Steward-bump med felaktigt commit-msg från stale system-temp — diff korrekt, msg fel), `ce1b137` (errata — `branch-discipline.md` byter `$env:TEMP` → `$env:LOCALAPPDATA\Temp` + gotcha-paragraf), `f448925` (Steward-bump till ce1b137 + dokumentera 840e73f-erratan), `2998275` (ny `governance/rules/shell-windows-defaults.md` med alwaysApply som låser PowerShell-default + bannar Unix-verb i Shell-anrop), `4440361` (ADR 0025 `governance/decisions/0025-browser-fallback-preview.md` av Cloud Agent B — rekommenderar server-byggd statisk preview för Safari/Firefox-fallback, status: Proposed), `e1103c5` (Scout case 4 sköldpaddssoppa körd live i Viewser-wizarden + B137 tagline-läckage öppnad), `fc8f96d` (Steward-bump efter case 4 + ADR 0025 + here-string-pattern), `9089b7a` (term-coverage-allowlist-followup för 'B137 fix'). **B137 ny (öppen, Medel)** — `company.tagline` läcker rå prompt-/beskrivnings-text till Hero på sajter där briefModel inte producerar tagline. Aktuellt bug-scope: **26 aktiva, 0 misplaced, 5 unknown, 98 stängda**. Inga öppna PRs, inga lokala feature-branches. `branch-discipline.md` har nu **here-string + stdin-pipe** som primary multi-line commit-pattern (skapar inga disk-filer; Cursor-IDE-panelen får inga false-positives på temp-tracking). `shell-windows-defaults.md` är ny `alwaysApply: true`-regel som låser PowerShell-default och bannar Unix-verb i Shell-anrop (operatör har drabbats av `head`/`tail`/`cat`-fel i ~1 år; nu sticky via governance).
**Viewser-overlay-E2E-Scout 2026-05-19:** passet är nu **körd över 4 case + delvis Case 5** med snitt **~6.6/10** (Case 1: 7.3, Case 2: 7.4, Case 3a: 6.6, Case 4: 5.0). Verifierade B101/B102/B128 + B88/B130/B131/B132 håller live, identifierade B130-B137 (alla utom B137 stängda). **Case 4 (sköldpaddssoppa / conflict) körd 2026-05-19 19:00-19:10 UTC+2** — siteId `skoldpaddssoppa-karlsson-099d5c`, build ok, Quality Gate alla gröna (typecheck/route-scan/build-status/policy-compliance), 4 routes, gpt-5.4 codegen 524/169 tokens. Case 4-snittet (5.0) är **under 6.5-golvet** → beslutsregeln (≥7 OCH inget <6.5 → Project DNA-sprint) är **EJ uppfyllt**. Riktad bug-sweep på Case 4-fynden är nästa steg. Case 5 ("2 sidor") delvis täckt av Case 4 eftersom prompten innehöll explicit "2 sidor" som ignorerades. Case 6 (follow-up byte-stabilitet, B71-verifiering), Case 3b (riktig scrape-test) och Spår B (variant-experiment) kvarstår för senare körning.

**Orkestrator-pass 2026-05-19 sen kväll (ny handover för nästa orkestrator):**

| Aspekt | Status |
| --- | --- |
| **Lokal main = origin/main** | `9089b7a`, **100 % synkat** (push lyckades på alla 8 commits) |
| **Working tree** | Bara operatör-ägda filer (`sajtbyggaren.code-workspace`, `post-frontend-merge.txt`). Inget från agent-pass |
| **Disk-state utanför repo** | Stale `sb-commit-msg.txt`-filer i `C:\Users\jakem\AppData\Local\Temp\` från tidigare Cloud Agents — **utanför repo, git ser dem aldrig**. Cursor IDE:s session-tracking-panel visar dem som "files changed" vilket är false positive (panel-artefakt, inte git-state) |
| **Backups** | `backup-30/31/32` lokala + på origin. Äldre `backup-11..29` orörda |
| **Öppna PRs** | 0 |
| **Lokala feature-branches** | 0 |
| **Scout-rapport** | `docs/reports/viewser-overlay-e2e-scout-2026-05-19.md` är komplett för 4 case + topp-5-hinder + builder-prio + verdict |
| **ADR-status** | ADR 0025 (B125 browser-fallback) status `Proposed`, väntar operatörsbeslut mellan 4 fallback-kandidater (server-byggd statisk preview / lokal `next dev` / "Öppna i StackBlitz" / Vercel preview-deployments). Cloud Agent B rekommenderar kandidat 1 (server-byggd statisk) |
| **Embeddings-status** | **POLICY DEFINIERAD MEN IMPLEMENTATIONEN EJ BYGGD.** `governance/policies/embedding-policy.v1.json` låser kontraktet för 5 domäner (scaffolds, dossiers, reference-templates, section-patterns, style-signatures) men `implementationStatus: "Index byggs i kommande sprint. Policyn låser kontraktet."`. `data/embedding-index/`-mappen är gitignored som förberedelse. Inga aktiva embeddingModel-anrop i prod-flödet idag. Egen sprint krävs (modellval + index-pipeline + Selection Trace-storage + ADR) |

**Direkt nästa steg (operatör väljer):**

1. **B137 fix** — `_derive_tagline`-helper i `scripts/prompt_to_project_input.py` ska producera deterministisk fallback ("Lokalt tjänsteföretag i Stockholm" eller liknande) när briefModel inte ger tagline. ~1 h Builder-arbete. Snitt-impact: case 4 5.0 → ~5.5/10.
2. **Intent Guard** — ny modul som flaggar prompt-vs-wizard-mismatch (Coach-prompt 02 finns färdig i `övrigt/agent-prompts-2026-05-19/`). ~2-3 h Builder + Viewser-warning-display. Snitt-impact: case 4 → ~7/10.
3. **Page Intent Variant B** — B132 från warning-only till route-emission. ~3-5 h Builder, kräver scaffold-template-utvidgning. Löser case 5-spåret. Egen ADR sannolikt nödvändig.
4. **ADR 0025 implementation** — operatör beslutar fallback-kandidat först. Implementation kräver hostingval + TTL-policy + budget. Kanske Vercel preview-deployments är enklast om operatör redan har Vercel-konto.
5. **Case 6 (follow-up + B71-stabilitet)** — operatör kör i wizard ~15 min. Krävs för komplett Project DNA-data.
6. **Spår B (variant-experiment)** — operatör + Scout. Två builds med non-default variants för visuell jämförelse. Underlag till B129-sprint.

**Vad nästa orkestrator inte ska göra:**

- Inte amend/force-push på `main` (`840e73f`-erratan visade att felaktigt commit-meddelande är acceptabelt cost vs force-push-risk).
- Inte använda `$env:TEMP` i Shell-kommandon (resolveras till `C:\WINDOWS\TEMP` i elevated agent-shell — ger stale-file-bugs). Använd here-string + stdin-pipe (primary) eller `$env:LOCALAPPDATA\Temp` (fallback). Se `branch-discipline.md`.
- Inte lyfta in produktkod-ändringar utan Scout-RO-review först. Scout-rapport är kanonisk.
- Inte starta Project DNA-sprint förrän case 4-fynden är åtgärdade och Case 6 är körd.
- Inte starta embedding-implementation utan egen ADR + modellval-beslut.
**Föregående repo-HEAD på `main`:** `7a4e450` (`chore(term-coverage): allowlist 'Cleanup' rubrik i scout-handoff`, 2026-05-19, post-Steward-verified-state-bump efter PR #39-#43 + tree-utility-commits). Stängde B130 (PR #40 `f56d327`, siteId från `company.name`), B131 (PR #42 `2901e4e`, capability-alias-dedup), B132 (PR #41 `89435ac`, warning-only `pageIntentWarnings`), B133 (PR #39 `7ac14c4` + PR #43 `c1dce9c` Codex P2-hardening) plus tree-utility-commits `2188fb5`/`b1c42f9` och term-coverage-städ `7a4e450`.

**Föregående repo-HEAD på `main`:** `9d7c4ba` (`chore(gitignore): ignore embedding index cache`, 2026-05-19, cherry-picked från övergiven branch `cursor/embedding-index-livscykel-3065`, 1 rad till `.gitignore`) ovanpå `9176f5e` (`docs(steward): bump for PR #38 merge (48a6a22) + register B129`) ovanpå merge-commit `48a6a22` för PR #38. Samtidig branch-cleanup pushad: raderade `origin/cursor/embedding-index-livscykel-3065` (chore-fix räddad), `origin/christopher-ui` (taggen `archive/christopher-ui-2026-05-18` säkrar), `origin/feat/eight-scaffold-variants` (PR #38 mergad, inga unika commits kvar), + lokal `feat/eight-scaffold-variants`. Origin-branches efter städ: `main` + 14 backup-branches (oförändrade). Föregående **Aktuell repo-HEAD på `main`:** `48a6a22` (`Merge pull request #38 from Jakeminator123/feat/eight-scaffold-variants`, 2026-05-19) ovanpå `0511299` (`fix(tests): align variant context test with promoted variants`) + `4cd1058` (`feat(variants): add eight gpt-5.4 scaffold variants for planning`) — PR #38 mergad via operatör-OK trots coach-direktiv 2026-05-19 ("ingen variant-promotion under Steward/Scout"); 8 nya canonical Scaffold Variants (4× `local-service-business`, 4× `ecommerce-lite`) + 8 mirrors under `data/variant-candidates/<scaffold>/` + `_DEFAULT_VARIANT_BY_SCAFFOLD`-guard i `packages/generation/planning/plan.py:_pick_variant` som garanterar att `nordic-trust`/`clean-store` förblir defaults (de nya variants är dead code i prod-flödet tills variant-selection-logik kommer i dedikerad sprint). **B129 öppen** för teknisk skuld (hardcoded mapping i kod istället för governance). Merge-commit ligger ovanpå `99ec56d` (`docs(steward): mikrobump current-focus + handoff for cd720aa + park PR #38`), `cd720aa` (`chore(gitignore): ignore local scout artifacts and certificates`), `6d66c0e` (`docs(steward): bump current-focus + handoff after keramik-/e-handel-pass`) och `bfcad8d` (`fix(builder): harden B128 imperative guard against leading non-letter prefix`) ovanpå `923f680` (docs B101/B102/B128 stängningar), `6e5c33c` (dev-viewser `-Https`-flag), `d1fee90` (Builder-pass keramik/e-handel), `2ffe065` (chore-ignore övrigt/), `76f6888` (docs B121-stängning) och `e3fa67b` (merge PR #37 B121 PR D). **HEADS-UP TILL PÅGÅENDE VIEWSER-OVERLAY-E2E-SCOUT**: Scout-rapport `docs/reports/viewser-overlay-e2e-scout-2026-05-19.md` har låst `HEAD-SHA vid scout-start: 99ec56d`. Faktiskt main är nu `48a6a22` efter PR #38-merge. Scout-agenten bör notifieras för att antingen uppdatera HEAD-SHA-raden + fortsätta (de nya variants aktiveras inte i prod via `_DEFAULT_VARIANT_BY_SCAFFOLD`-guarden så Scout-observationerna är fortfarande representativa) eller stoppa och omstart vid `48a6a22`. Operatören ska ta beslutet. **Nästa spår: Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning via overlayflödet, inte mer CLI-discovery-plumbing. Kör `git log --oneline -1` eller `python scripts/focus_check.py` för faktisk HEAD-SHA. `0fe353f` stängde B126 (dossier-graf-nyckel-mismatch — `_compatible_dossier_edges` byggde `dossier:{id}` medan noder var registrerade som `{class}-dossier:{id}`; impact-vyn blev blind för scaffold→dossier-spåret) och B127 (Doctor-villkor inverterat — `run_health_checks` varnade på `status == "implemented"` med tom details-sträng och tystnade på riktiga `incomplete`/`placeholder`-scaffolds). Båda fynden kom från extern review mot PR #32-cherrypicken (`3338d79` + `b636450`) och låses av två nya regressionstester i `tests/test_backoffice_asset_graph.py`. Guards gröna efter `0fe353f`: ruff 0 findings, governance 16 policies OK, rules_sync --check OK, term-coverage strict OK, **pytest 701 passed, 3 skipped E2E** (+2 nya regressionstester). Föregående relevanta commits i kronologisk ordning: `eb1a4ec` (B125 browser-support-fallback-registrering), `00103e3` (soft dossier candidate generator), `855a605` (atomic model role writes), `2065a33` (variant candidate review), `c22bc1d` (selection profile editor), `b636450` (impact preview), `3338d79` (compatible dossier edges normalised), `60515c6` (docs B124-bump), `5d05e0d` (B124 fix), `e325c67` (docs B123-bump), `5f23d13` (B123 fix), `c7049b3` (operatör postcss-cleanup), `0361121` (docs-bump runda 2), `df24488` (B118 fix), `6772a14` (B117 fix), `07f9cbb` (docs-bump runda 1), `fe9748e` (B114 fix), `cd03897` (B113 fix), `d06e628` (pyright cleanup), `61da065` (--discovery rejection), `d63fab3` (BuildProgressCard fix), `3f4543d` (PR #31 merge), `0510146` (PR #31 integration), `ca59529` (handoff-close docs-bump), `e67cd90` (handoff-skriv), `9bf3893` (B112-fynd-logg), `adde45c` (B112-fix), `b3800ca` (Steward focus-bump efter B109), `fa277a1` (B109-fix), `7742d39` (Steward bug-scope cleanup), `1c68035` (B108-fix), `860e553` (Backoffice control-plane).
**Aktiv branch:** `main`. `backup-pre-christopher-ui-merge` är pushad till origin som extra säkerhet före PR #31-mergen (pekar på `ca59529`); kan städas separat när ångerläget inte längre behövs. Taggen `archive/christopher-ui-2026-05-18` pekar på `4a16528` (christopher-ui:s HEAD) så hela branchen kan återställas. `origin/christopher-ui` är raderad. `cursor/backoffice-kontrollplan-mvp-62aa` (PR #32 source) och `frontend/christopher-import` (PR #17 CLOSED) raderades från origin under PR #32-passet. Kvar och flaggad för operatör-OK innan radering: `feat/demo-baseline-fix-1b-bug-sweep` (alternativ-väg till PR #28 som istället mergades från `cursor/demo-baseline-buggsvep-44a5`). `backup-32` (denna Steward-post-handoff-bump), `backup-31` (pre-final-handoff), `backup-30` (pre-auto-merge-pipeline), `backup-26-VIKTIG`, `backup-27`, `backup-28`, `backup-29` plus äldre `backup-11..backup-25-VIKTIG` finns kvar på origin från tidigare pass och rörs inte utan instruktion. Lokala backups: `backup-30`, `backup-31`, `backup-32` finns även lokalt. Inga lokala feature-branches.
**Stash-läge:** `git stash list` är **tom**.

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet. Läs den FÖRE `docs/current-focus.md` om du är helt ny på projektet; läs `current-focus.md` FÖRE den om du bara behöver veta nästa konkreta uppgift.
Färdiga startprompter för Scout/Builder/Steward finns i [`docs/agent-prompts.md`](agent-prompts.md). För längre fleragentpass används [`docs/orchestrator-playbook.md`](orchestrator-playbook.md); den samordnar befintliga roller och skapar inte en fjärde fast roll.

## Branch-policy: var jobbar agenten egentligen?

**`main` är arbetsytan.** Du står på `main` före, under och efter sprinten om operatören inte uttryckligen säger något annat. Inför varje ny sprintrunda skapar agenten en numrerad backup-branch från ren/synkad `main`, men fortsätter jobba på `main`.

Detta är definierat i [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md):

### Sprintstart – backup först

1. Kör `python scripts/focus_check.py`.
2. Verifiera att branch är `main` och att den är synkad med `origin/main`.
3. Lista `backup-*` och välj högsta nummer + 1.
4. Skapa `git branch backup-N` från aktuell `main`.
5. Pusha backupen om operatören vill ha fjärrbackup: `git push origin backup-N`.
6. Stanna kvar på `main` och gör arbetet där.

Backup-branchen är bara fallback. Den är inte arbetsbranch och ska inte få PR.

### Tre agentroller

- **Scout-agent** är read-only: audit, plan, risker, RO-bugggranskning före push, nästa Builder-prompt.
- **Builder-agent** implementerar: skapar sprintens backup, jobbar på `main`, testar, rapporterar och pushar först efter gröna guards. Om Scout säger att push är OK och working tree är clean får Builder pusha utan ny manuell operatörs-OK.
- **Steward-agent** håller ordning: docs/current-focus, handoff, sanity och låg-risk governance på `main`. Efter Builder-push verifierar Steward origin/main-SHA, `git status`, `python scripts/focus_check.py`, om `origin/main` matchar lokal `main`, samt om docs behövde uppdateras.

### PR är undantag

PR skapas bara om operatören uttryckligen ber om PR/separat arbetsbranch. Annars används Scout-agentens RO-review + lokala guards före `git push origin main`.

Cursor Bugbot triggar i nuvarande repo-konfig främst på PR. Eftersom operatörspreferensen nu är `main` + backup används Bugbot inte som standardgate. För direkt-main-flödet är Scout-agenten pre-push-granskare. För större risker ska agenten stoppa, rapportera och låta operatör + extern reviewer besluta innan push.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:

- `governance/` — JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- `backoffice/` + `backoffice.py` — Streamlit-administration (inte runtime).
- `packages/` + `apps/` — runtime + kund-UI.

## Vad funkar idag (post cleanup/prune-sprint, kod-baseline `2acdeca`)

### Governance + guards

- ADR 0001–0020 + 15 policies + matchande schemas under `governance/schemas/`.
- Fem automatiska checks: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. GitHub Actions kör dem på push + PR. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift.
- Tree-utility för LLM-context: `python scripts/tree_view.py [path] [--llm] [--copy] [--with-size] [--ext .py,.tsx] [--max-depth N]`. Delad utility som alla agenter (Scout/Builder/Steward/Cloud) kan köra för repo-strukturöversikt utan att klistra hela trädet manuellt. Ersätter operatör-lokal tree_v*.py-arbetsflöde.
- **3 nya source-lock-tester** lades till i audit-hotfixen (Zod 400, trim, `--`-separator). 0 ruff findings.

### Phase 1 + 2 (Sprint 2A + 2B)

- `briefModel` via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- `planningModel` via shared `packages.generation.planning.produce_site_plan`. Både `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper.

### Phase 3 (Sprint 3A → 3C-lite + B13b + B20)

- Real Quality Gate-checks (typecheck, route-scan, build-status, policy-compliance) i `packages/generation/quality_gate/`.
- Repair Pipeline med ensure-default-export-fix och sandwich-loop i `packages/generation/repair/`.
- Real `codegenModel` (scope: `marketing-base`) i `packages/generation/codegen/`. `_REAL_CODEGEN_STARTERS = {"marketing-base"}` (ADR 0017). Truth-fields: `real` / `mock-llm-error` / `mock-no-key` / `deterministic-v1`.
- **B13b route-emission (PR #19, `fda1464`):** `scripts/build_site.py:write_pages` är scaffold-drivet. `ecommerce-lite` genererar `/produkter` (inte `/tjanster`), nav följer scaffolden, contact-CTA på `render_products` följer scaffold (`_pick_contact_route`).
- **B45 contact-route propagation (`6daee58`):** layout, home, services och products får sina kontakt-CTA:er via scaffoldens contact-route (`_pick_contact_route`/`contact_path`). En scaffold som flyttar contact-id till `/kontakta-oss` får därmed nav och CTA:er i synk.
- **B20 step 2 (PR #20, `75c980b`, ADR 0019):** `SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Ecommerce-lite-fixturen `examples/atelje-bird.project-input.json` producerar `/produkter` via `source=deterministic-v1` codegen. Real codegenModel-scope förblir `marketing-base`-only tills separat sprint utvidgar via ADR ovanpå 0017.
- **B20-followup-lucide (PR #21, `04fc2fa`, ADR 0020):** `lucide-react` ^1.14.0 tillagd i `commerce-base/package.json` så `scripts/build_site.py:write_pages`s hardcodade lucide-imports inte längre ger `Module not found` vid full `npm run build`.

### Prompt-till-sajt MVP v1 + follow-up versions + audit-fix (kod-HEAD `2701b00`, audit-fix landar 2026-05-14, PR #27 versionerade snapshots landar 2026-05-15)

- **`/api/prompt`** tar fri prompt, kör `runPromptToProjectInput` (spawnar `scripts/prompt_to_project_input.py` med `--`-separator så dash-prefixade prompts inte fastnar i argparse), och triggar `runBuild` med dossier-path-override (whitelist via `ALLOWED_DOSSIER_ROOTS` mot `examples/` + `data/prompt-inputs/`). Response-payloaden inkluderar nu `buildStatus` (B44) så klienten kan klassificera ok/degraded/failed istället för att tolka varje returnerad `runId` som lyckad build.
- **PromptBuilder** är enda promptytan på Viewser-home (legacy `ChatPanel` är raderad i B46-fixen). ProjectInputPicker är read-only-select (Build-knappen togs bort). Stage-indikatorn renderar tre distinkta paneler (success/degraded/failed) baserat på `classifyBuildStatus(buildStatus)`; `app/page.tsx` skickar `PromptBuildOutcome` vidare till `headerStatusForOutcome` så headern aldrig säger "Build klar via prompt:" för en degraderad eller failed run.
- **Dev-driver follow-up-semantik** är nu trådad: `scripts/dev_generate.py --mode followup --project-id <id>` skriver både `input.json` och `generation-package.json` som follow-up med samma `projectId`. Backoffice Playground skickar `--project-id` + `SAJTBYGGAREN_MODE=followup` till subprocessen och har regressionstest.
- **Payload-validering**: `z.string().trim().min(1).max(4000)` så whitespace-only payloads fångas vid API-gränsen. `ZodError` returneras som `400` med valideringsmeddelandet; bara genuina serverfel blir `500`.
- **Helper-skriptet** `scripts/prompt_to_project_input.py` använder briefModel + Site Brief och skriver `data/prompt-inputs/<siteId>.project-input.json` + sidecar `<siteId>.meta.json` med `projectId/version/originalPrompt/briefSource`. Brief-imports ligger på modulnivå så fallback-tester monkeypatchar lookup-namnen som `generate()` faktiskt använder.
- **Follow-up prompt versions** är landat: operatören kan fortsätta på befintlig prompt-input/run, behålla `projectId`, bumpa `version` och få ny build/run för samma sajtspår.
- **PR #27 follow-up versions v2** (mergad `e057fbd`): `scripts/prompt_to_project_input.py` skriver immutable `<siteId>.vN.project-input.json` + `<siteId>.vN.meta.json`-snapshots i `data/prompt-inputs/`, behåller current pointer-filerna, bevarar `projectId`/`originalPrompt`, skriver `followUpPrompt`, och merger follow-up-prompts konservativt på existerande Project Input. `scripts/build_site.py` läser sidecar-meta intill dossier-pathen och trådar `mode`/`projectId`/`version`/`originalPrompt`/`followUpPrompt` in i `input.json`/`generation-package.json`/`build-result.json`. `apps/viewser/lib/runs.ts` läser per-run-meta från `build-result.json` -> `input.json` -> mutable sidecar legacy-fallback (RunHistory är stabil per `projectId` + `version` även när nya follow-ups landar). `apps/viewser/lib/project-inputs.ts` filtrerar `.vN.project-input.json`-snapshots från ProjectInputPicker. `apps/viewser/lib/prompt-runner.ts` + `lib/build-runner.ts` föredrar repo-roten `.venv` Python när den finns och cleanar prompt-/build-mutex via `try/finally`. PR #27 rörde inte StackBlitz-fronten (`apps/viewser/lib/stackblitz-files.ts`, `components/viewer-panel.tsx`, `next.config.ts`, `tests/test_viewser_files.py`).
- **ViewerPanel** fallback-copy hänvisar nu till promptfältet, inte den borttagna Build-knappen.

### Backoffice trace/playground (PR #23, produkt-HEAD `e1ad5ca`)

- Engine-runs-vyn och playground-vyn använder en gemensam strukturerad trace-viewer i `backoffice/views/_trace.py` för `trace.ndjson`: halvskrivna rader hoppas över defensivt, events summeras, grupperas per fas och kan filtreras på fas/status/söktext.
- Playground-vyn kör `scripts/dev_generate.py` via kontrollerad `subprocess.Popen`-runner istället för svart-låde-`subprocess.run`, och visar status, elapsed time, exit code och loggutdrag under/efter körning.
- Backoffice trace/playground-posterna är stängda i `docs/known-issues.md`; kvar finns bara lågprioriterad cancellation-followup för riktig cancellation/background-jobb.

### Starter-katalog

- `data/starters/portfolio-base/` (PR #22) och `data/starters/docs-base/` (PR #24) finns nu som harmoniserade starters. Båda är starter-underlag, inte aktiverade i `SCAFFOLD_TO_STARTER`-mappning och inte i real-codegen-scope.
- `docs-base` (Nextra 4.6.1 + Pagefind + MDX): sidomenyn i `src/app/layout.tsx` är manuellt underhållen — scaffold-injektion av nya MDX måste också uppdatera `<aside>`-blocket. Detta är dokumenterat ärligt i `authoring.mdx`/`index.mdx`/starter-README och spårat som `B49` i `known-issues.md` (page-map-driven sidebar krävs innan runtime-aktivering).
- Befintliga aktiva starterflöden är oförändrade i routing/codegen: `marketing-base` för real codegen-scope och `commerce-base` för ecommerce-lite deterministic-v1 enligt tidigare ADR-spår. Dependency-baslinjen är däremot hårdnad i `1c68035`: båda ligger på `next@16.2.6`, `eslint-config-next@16.2.6`, `postcss@^8.5.10` och `overrides.next.postcss=8.5.10`; `copy_starter()` tvingar om-installation när dessa package-inputs ändras.

### Builder UX MVP

`apps/viewser/` har en `<RunDetailsPanel>` med fem sektioner (Build / Quality / Repair / Codegen / Models) som läser från `/api/runs/[runId]/artifacts`. Build-sektionen visar `generatedFilesDir`, `devPreviewDir`, `npmSteps` och eventuella `logExcerpt` från failed npm-steg så transient build-mismatch kan felsökas från artefakten. `<RunHistory>` har status-färgning. PreviewRuntime / StackBlitzRuntime / FlyRuntime är parkerat som Sprint 4-5.

## Vad är parkerat

- **B59 - StackBlitz `template:"node"`/WebContainer-preview** är parkerat
  efter empirisk header-utvärdering 2026-05-15: inga COOP/COEP-headers
  blockerar iframe-load, `require-corp` ger VM-handshake-timeout,
  `credentialless` får iframe att ladda men StackBlitz `sign_in`-check
  faller. Header-experimentet committades **inte**. Nästa arkitekturbeslut
  bör vara byte till lokal `next dev`-process som same-origin iframe på
  `localhost:NNNN`, eller static StackBlitz-template - inte mer
  header-toggling. Tills dess fungerar Run History + Run Details för
  diagnostik och lokal `npm run build` på den genererade siten som
  verifikation. Rör inte `apps/viewser/lib/stackblitz-files.ts`,
  `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts`
  eller `tests/test_viewser_files.py` utan separat sprintbeslut.

## Nästa konkreta uppgift

Se `docs/current-focus.md` → **"Next action"**. Kort version: keramik-/e-handel-passet är stängt (`bfcad8d`: B101 + B102 + B128 stängda, hardening efter Composer-2.5-review). Nästa är **Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning via det faktiska overlayflödet (wizard → prompt → eventuell scrape/upload → build → preview). 4-6 case inkl. keramik (verifierar B101/B102/B128 live), tjänsteföretag med adress, scrape-case, sköldpaddssoppa-conflict, "2 sidor"-case och en follow-up. Vid ≥7/10 och inget case <6.5 → Project DNA-sprint. StackBlitz/HTTPS för lokal preview körs nu via `.\scripts\dev-viewser.ps1 -Https` (https://-origins är vad embed-konsolen accepterar).

Kända lågprio-rester (oförändrat): B97 (`/kontakt`-copy), B98 (bredare e-handelsserviceområde-yta; B104 stängde bara country-only-läckan). B119/B120 (kontakt/adress) prioriteras om Scout visar fel kontaktdata. B125 (browser-preview-fallback) är produktblocker före extern kundyta. Variant-spåret `feat/eight-scaffold-variants` (`4cd1058`) ligger som separat feature-branch tills variant-promotion-sprint körs.

## Handoff från detta agentpass till nästa Steward

Detta pass (2026-05-18, kvällskörning) gick i fyra ron, alla på direkt
`main` enligt branch-discipline:

1. **Steward bug-scope-cleanup** (`7742d39` + `0d3e9b8`): flyttade
   15 misplaced 1B-fixar (PR #28 / `885431b`) från "Öppna" till "Stängda"
   i `docs/known-issues.md`. Rättade också 1B closure-noten — den
   listade tidigare B71/B72/B75/B83 som stängda men de har `Fix: open`
   i sina poster och är medvetet öppna (B71 markerad som unverified av
   re-Scout). Bumpade summary-raden från `17/15/6/62` till `17/0/6/77`.
2. **B109 reviewer-hotfix** (`fa277a1` + `b3800ca`): extern reviewer
   (Cursor Bugbot-stil) mot baseline `1c68035` hittade att
   `_npm_install_inputs_changed` fångade bara `(OSError, JSONDecodeError)`
   men `load_json` läser med `encoding="utf-8"`, så ogiltig UTF-8 i
   target-`package.json` raisade `UnicodeDecodeError` och kraschade
   builden. Fix: lägg till `UnicodeDecodeError` i except-tuple.
   Två regressionstester i `tests/test_builder_hardening.py`.
3. **B112 reviewer-triage** (`adde45c` + `9bf3893`): extern reviewer
   mot post-1E-baseline. Tre fynd verifierade genom kodläsning:
   - B112 (Låg, stängd `adde45c`) — `_product_category_name`
     joinade `label.split()` utan separator, så
     `services_mentioned=["handgjord keramik"]` på e-handel-prompt gav
     H1 `"Handgjordkeramikbutik"`. Fix: använd sista ordet
     (grammatiska substantivet) → `"Keramikbutik"`,
     `"Matbutik"`, `"Smyckenbutik"`. Single-word oförändrade. Tre
     regressionstester + B106-regressionen kvarstår.
   - B110 (Låg-Medel, öppen) — `_normalize_business_type` (B107-fixen)
     körs bara i CTA-flödet; tagline/service-summary-mapparna i
     `prompt_to_project_input.py` nycklar på rå briefModel-output, med
     luckor särskilt på `webshop`/`webbshop` SV och `naprapatklinik` EN.
     Inte krash — "split sanning" som ger inkonsekvent copy. Kopplar
     mot B13a (arkitektur-flytt av `scripts/build_site.py` till
     `packages/`). Verklig fix kräver delad helper, för stor för ett
     snabbpass.
   - B111 (Låg, öppen) — `scripts/generate_variant_candidate.py`
     faller tillbaka till mock vid alla `Exception` från
     `_call_variant_model` med `source="mock-llm-error"` + stderr-print
     + `exit 0`. Medveten design men saknar
     `--fail-on-llm-error`/`--strict`-CLI-flagga för CI-strict-mode.
     Enhancement, inte bug.

### Vad du som nästa Steward bör göra först

1. `python scripts/focus_check.py` — drift-check. Förvänta dig
   `Result: OK` med eventuell "1 commit ahead - within bump tolerance".
2. `python scripts/list_open_bugs.py` — bug-scope. Förvänta dig
   `Active: 19  Misplaced: 0  Unknown: 6  Closed: 79`. Misplaced > 0
   är direkt städningssignal (öppna-poster med `Fix: <sha>` som inte
   flyttats till Stängda).
3. `git log --oneline -10` — kontrollera att HEAD är `9bf3893` eller
   nyare. Två commits per sprint (Builder + Steward bump) är normalt
   mönster sedan föregående pass.
4. Kontrollera operatörens fråga: om hen explicit ber om att fixa
   B110/B111 är det Builder-arbete (rör `scripts/`); annars lämna dem
   öppna.

### Vad du som nästa Steward INTE bör göra

- Lämna inte B110 utan att också flytta `_normalize_business_type` till
  delad helper. Halv-fix (ad-hoc-duplicering av normalisering) är värre
  än ingen fix här — det skulle hänga kvar som teknisk skuld utan
  spårning. Den hör hemma i samma sprint som B13a-arkitektur-flytten.
- Skapa inte nya B-IDs för samma fynd som B110 eller B111 om en framtida
  reviewer hittar dem igen. Hänvisa till befintliga B-IDs i stället.
  Reviewer-prompter har en tendens att åter-rapportera samma observation.
- Acceptera inte `Misplaced > 0` ohanterat. Antingen flytta dem eller
  rapportera tillbaka till operatören att en Builder/Cloud Agent är
  skyldig dem.
- Bumpa inte Last verified-SHA till en docs-only-commit om det finns
  en ny Builder-commit ovanpå. Last verified pekar på senaste
  produktcommit, inte på sin egen bump.

### Operatörsförslag som väntar på beslut (inte påbörjat)

**Mini-bot-automation för Steward-städ.** Operatören frågade om
automation i detta pass. Förslaget i tre nivåer, ingen implementerad
ännu:

- **Mini-bot (lätt):** pre-push hook eller GitHub Action som kör
  `python scripts/list_open_bugs.py --quiet` + verifierar
  summary-raden. Fångar ~80 % av Steward-städ-skulden för ~30 raders
  Python. Lägst risk och snabbast påverkan.
- **Steward-Action (medel):** GitHub Action vid push till `main` som
  kör hela steward-guardsetet (governance, rules_sync, term_coverage,
  bug_scope, docs_freshness) och öppnar draft-PR om något driftar.
- **Auto-Steward (tyngre):** schemalagd Cursor Cloud Agent med fast
  `Roll: Steward` + tydligt write-set
  (`docs/known-issues.md`, `docs/current-focus.md`, `docs/handoff.md`).
  Risken är scope-läckage; mitigeras via Scout RO-review före push.

Lägg fram förslaget igen om operatören återupptar diskussionen.

### Backup-tillstånd

`backup-26-VIKTIG` (pre-B108), `backup-27` (post-B108, pre-cleanup),
`backup-28` (post-cleanup, pre-B109) och `backup-29` (post-B109, pre-B112)
är alla pushade på origin. Inga lokala branches utöver `main` enligt
operatörens uttryckliga preferens. Inget nytt backup-N skapas för denna
handoff-commit eftersom det är ren docs-only och inte ändrar
beteende.

**Demo-baseline-fix 1C closure note (2026-05-18, `b5ee710`):**

- **B88** — `scripts/prompt_to_project_input.py:_placeholder_contact()` skriver inte längre dev-jargong i publika kontaktfält. Default-placeholdern är nu `"Adress lämnas på förfrågan"` (sv) / `"Address available on request"` (en); operatören kan fortfarande skriva över via Project Input.
- **B94** — `scripts/build_site.py:render_about` omittar hela "Teamet"-blocket (rubrik + grid) när `company.team=[]`. Samma conditional-render som B66:s trust-fix.
- **B95** — ny `_COUNTRY_NAME_LOCATION_HINTS`-set (Sweden, Sverige, Norway, Norge, Denmark, Danmark, Finland, Iceland, Island) i `prompt_to_project_input.py`. När `locationHint` matchar ett landnamn returnerar `_normalize_location_hint` `None`, och `_placeholder_location` faller tillbaka till `city == country` som country-only-markör. Ny `_location_is_country_only`-helper i `build_site.py` suppressar hero-ortstag-spanen i `render_home` när markern är satt. Bredare än B91 — täcker även `locationHint="Sverige"` (inte bara `"Sweden"`-translit).
- **B96** — ny `_hero_cta_label(dossier)`-helper i `build_site.py` routar genom `_hero_cta_variant` med prioritet shop > booking > quote. Värden från `_HERO_CTA_VARIANT_LABELS`-whitelist (`"Shoppa nu" / "Shop now"`, `"Boka tid" / "Book a time"`, `"Begär offert" / "Request a quote"`). `render_home` (hero) och `render_services` (bottom-CTA) använder samma helper. Default fallback är fortfarande "Begär offert" så painter-palma-stilen demos inte regresserar.

19 nya regression-tester låser fixerna. Guards: ruff 0 findings, full pytest grön (3 skipped E2E/slow), governance_validate, rules_sync --check, check_term_coverage --strict, `list_open_bugs` grönt (15 aktiva, 15 misplaced, 6 unknown, 54 stängda).

Off-limits-områden enligt operatorns 1C-direktiv respekterades: `apps/viewser/lib/stackblitz-files.ts`, `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts`, `tests/test_viewser_files.py` (B59 parkerat), `data/starters/`-innehåll, `examples/`, `.env*`, `packages/preview-runtime` orörda.

Bakgrund: demo-baseline-fix 1B + bug-sweep mergead i `885431b` via PR #28 stängde B64, B65, B66, B69, B70, B71, B72, B73, B74, B75, B76, B77, B78, B79 och B83. Kvar från bug-sweep: B67, B80, B81, B82, B84, B85, B86, B87. Kvar från re-Scout 2026-05-15: B97, B98 (låg-impact). Övriga öppna B-IDs: B89-B93 (extern reviewer-triage), B49, B53, B47, B13a, BO4-followup-cancel (äldre). StackBlitz B59 är fortsatt parkerad. B71 (PR #28-stängd, men markerad som unverified av re-Scout) bör verifieras i två-pass-test nästa gång någon ändå provkör follow-up-flödet.

## Operatörspreferenser (2026-05-13)

- **Språk:** alltid svenska. Riktiga svenska tecken (`å`, `ä`, `ö`). Se [`governance/rules/always-swedish.md`](../governance/rules/always-swedish.md).
- **Reply-style:** kort + koncist. Förklara dev-uttryck med korta parenteser första gången per konversation (operatören är inte utvecklare i grunden). Se [`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
- **Backup-branches:** inför varje sprintrunda skapas nästa `backup-N` från synkad `main`. Backupen är fallback och ska inte raderas utan uttryckligt beslut.
- **Create-PR-knappen i Cursor:** användaren kan av misstag trycka den. Standard är att inte öppna PR; fråga operatören om PR verkligen är avsikten.
- **PowerShell + git commit -m flerrads:** PowerShell saknar bash heredoc. Skriv message till `$env:TEMP\sb-commit-msg.txt` och `git commit -F`. Aldrig `.commit-msg.tmp` i repo-roten (race med `git add -A`). Detaljerat i `governance/rules/branch-discipline.md` "Multi-line commit-meddelanden på Windows/PowerShell".
- **Cursor IDE git-editor pipe error på Windows** är vanligt (`ENOENT \\\\.\\pipe\\vscode-git-...sock`). Fall tillbaka till `git commit -m` eller `-F` från shell direkt.

## Bugbot-loop vid PR-undantag

Standardflödet är inte PR, men om operatören uttryckligen väljer PR-flöde står hela rutinen i [`governance/rules/bugbot-pr-loop.md`](../governance/rules/bugbot-pr-loop.md). Sammanfattning:

1. Efter `gh pr create`: verifiera att Bugbot är aktiverad (en check med `name == "Cursor Bugbot"` ELLER en review från `author.login == "cursor"`). Om aktiverad: skriv exakt strängen `kommer nu vänta i upp till högst 8 min på att bugbotten blir klar` till operatören.
2. Polla 60–90s × max 8 min. Stoppa så fort `Cursor Bugbot`-checken är `COMPLETED`.
3. **Tolka resultatet via 3 signaler — inte via Bugbots summary-body.** Bodyn säger "found N issues" från första körningen och uppdateras inte mellan commits. Använd istället: (a) check-conclusion, (b) GraphQL `reviewThreads.isResolved` för att räkna aktiva trådar, (c) övriga checks.
4. Grönt = check `SUCCESS` ELLER (`NEUTRAL` OCH 0 aktiva trådar) OCH alla övriga checks `SUCCESS` OCH `mergeStateStatus == "CLEAN"`. Grönt → `gh pr merge --squash --delete-branch` automatiskt + Standard loop steg 8.
5. Rött → fix-loop iteration N (max 10). Per iteration: läs aktiva trådar, minimal-fix, push, **markera trådar som resolved via GraphQL** så loopens nästa poll blir korrekt.
6. > 10 iterationer → posta `[NÖDLÄGE PR]`-kommentar och lämna åt operatör.

## Pre-push self-review checklist

Innan `git push origin main`:

1. `git diff origin/main..HEAD --stat` — jämför listan rad för rad mot sprintens deklarerade scope.
2. Sök efter samma sorts hardcoded-pattern som sprinten säger sig fixa. Klassiskt blindspot på nya filer (PR #19: vi fixade hardcoded `/tjanster` i existerande renderers men introducerade hardcoded `/kontakt` i den nya `render_products`).
3. Print-/logg-meddelanden i present tense ("Writing X") måste komma FÖRE handlingen, inte efter, så operatören ser vad som är i flygt vid crash.
4. För varje ny renderer/komponent som tar `dossier`: kontrollera om den länkar någonstans och om pathen ska komma från scaffolden (`_pick_*_route`) eller dossiern.
5. Om sprinten ändrar `SCAFFOLD_TO_STARTER` eller `data/starters/<starter>/`: skapa motsvarande ADR i samma ändringsrunda (lärdom från PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019; för starter-deps se PR #21:s ADR 0020).
6. Om sprinten har en informativ followup som inte blockerar push: lägg den i `docs/current-focus.md`, inte som blocker.

## Standard loop (för referens)

Hela rutinen står i [`docs/agent-handbook.md`](agent-handbook.md) under "Standard loop". Tio steg, varav steg 8 (Steward post-push-verifierar och uppdaterar `current-focus.md`/`handoff.md` vid faktisk fokusförändring) är obligatoriskt agentens ansvar — inte operatörens.

```text
0. Drift-check (python scripts/focus_check.py).
1. Scout-agent vid behov.
2. Skapa nästa backup-N från synkad main.
3. Builder/Steward jobbar på main.
4. Scout-agent gör RO-review före push.
5. Operatör + extern reviewer beslutar om Scout inte redan gett push-OK.
6. Final sanity (python scripts/review_check.py).
7. Commit + push till main.
8. Steward verifierar pushed SHA, git status, focus_check, origin/main == local main, och docs-beslut. Uppdatera current-focus/handoff när HEAD, active sprint, next action/queue/blocked, agentflöde, branchflöde, grindmode, rollansvar, risk/blocker/nice-to-have eller extern PR/Grind-agent ändrar nästa agents arbete.
9. Nästa etapp.
```

## Sista commit-historiken (för snabb orientering)

```text
b5ee710 fix(builder): close demo-baseline-fix 1C (B88 B94 B95 B96)
b09f935 docs(focus): record backup-1..backup-8 prune on origin
7fdfee2 docs: bump verified SHA + sprint state after PR #29 + #30 merge
b3a32fc Backoffice maintenance and enabled toggles (#30)
c2c6f39 feat(tooling): list_open_bugs script + bug-scope-discipline rule (#29)
38d0af9 feat(maintenance): opt-in auto-prune via .env caps
0c549ac docs: queue live pipeline-matrix backoffice idea
ac33b3f docs: log Re-Scout findings (B94-B98) and 1C plan
948d2f9 chore(rules): add read-only-shell-windows rule
d0ded58 docs: align verified SHA with post-1B bump
cc3c6f3 docs: bump verified SHA after demo-baseline-fix 1B
8282bd9 docs: triage external reviewer findings B88-B93
885431b Demo-baseline-fix 1B + bug-sweep (B64-B79) (#28)
64c30d6 docs: log B64-B67 (Scout) + B69-B87 (bug-sweep) and queue Grind sprint
c273b1a docs: bump verified SHA after 1A-hotfix
d99f8ba fix(prompt-helper): close B61 B62 B63 (demo-baseline-fix 1A-hotfix)
a12314f chore(cursorignore): pin viewser node_modules and .next explicitly
b78484f docs: record verifierings-Scout findings (B61/B62/B63)
824cd3a docs: bump verified SHA to demo-baseline-fix 1A
ab74c2a feat(builder): demo-baseline-fix 1A
f29688c docs: bump verified SHA to rules commit
d072c98 chore(rules): add powershell-glob and cli-safety-belt rules
054e3b2 docs: bump verified SHA to Finding 1 fix
2acdeca feat(scripts): add prune_generated_previews.py with dry-run default
7b90c0c docs: record B60 fix and bump verified SHA
65f052a fix(prompt-helper): harden follow-up snapshots and meta loading (B60)
dd5464f docs: sync current-focus and handoff after PR #27 merge
e057fbd feat(viewser): preserve follow-up prompt versions (#27)
86d03bf docs: record B59 StackBlitz WebContainer embed blocker
210a1d1 chore(env): document Cursor API key placeholder
9927bd2 fix(viewser): harden StackBlitz payload size handling
4b98d8b chore(repo): remove visningsexempel artifacts and keep bug notes
869b2da chore(workspace): sync docs state and editor settings
cf523ed docs(adr): add ADR 0021 for StackBlitz preview workarounds
488f8a0 feat(viewser): harden StackBlitz preview payload handling
d9c244a chore(rules): add server-lifecycle-discipline rule
1cba454 docs(product): add operating context for agents
04fb92f docs(agents): align Codex with Cursor rules
9446200 docs(focus): record B45 contact route fix
6daee58 fix(builder): thread contact route through CTAs
3178a82 chore(workspace): integrate operator + parallel-agent docs/settings touch
c073d486 docs: add cloud agent gotcha for /sajtbyggaren-output permissions (PR #25)
19c3564 docs(focus): post-PR #24 docs-base merge + B49 follow-up
c2d8632 feat(starters): add harmonized docs-base starter (PR #24)
8997596 docs(focus): bump verified SHA after workspace cleanup
97ce7a8 chore(workspace): ignore PR review worktrees and sync build-runner comment
5199d94 docs(focus): record B48 follow-up semantics landing
10eb286 fix(dev-generate): thread follow-up mode into plan phase
ec11c41 docs: sync generated output path across docs
de7fd7c docs(focus): bump verified SHA after workspace hygiene pass
134df07 chore(workspace): perf hygiene + .generated externalization + viewser prettier setup
9ff7c50 docs(focus): bump verified SHA + queue after audit-fix B44+B46
5d746e9 fix(viewser): audit-fix sprint for B44 + B46
34551b4 docs(cleanup): modernize viewser copy and starter routing notes
d43bce2 docs: sync handoff after settings commit
e9093c0 Liten settings.json bara som committades
9944abb feat(starters): add harmonized portfolio-base starter
e1ad5ca feat(backoffice): improve trace viewer and playground logs
2701b00 feat(viewser): add follow-up prompt versions
006be38 docs(workflow): formalize steward post-push verification
c3dcc14 docs: correct verified HEAD to 2f0af68 in focus + handoff
2f0af68 docs: bump focus + handoff to e421a00 post-audit-hotfix-sprint
e421a00 chore(check_term_coverage): allowlist ZodError TS symbol
c039ebd fix(viewer-panel): refresh stale fallback copy after legacy chat panel removal
e067006 fix(prompt-runner): pass -- to argparse so dashed prompts spawn cleanly
1033bf6 fix(prompt-route): return 400 on Zod errors and trim whitespace at API edge
cb54ca9 docs(agent-prompts): expand role catalog with parallel-agent rules
fe56344 fix(prompt-helper): hoist brief imports to module level for monkeypatching
fb11925 docs(focus): record Viewser prompt surface cleanup
fd67fbd refactor(viewser): remove legacy chat panel from home
ea4b165 fix(viewser): isolate StackBlitz preview mount
0a060e1 docs(focus): bump Last verified after prompt fallback hotfix
c6e2f1d fix(viewser): fall back when prompt brief extraction raises
7eea2f0 docs(focus): bump Last verified to 4d5b4de + queue post-prompt-till-sajt-mvp-v1
4d5b4de feat(viewser): prompt-till-sajt MVP v1
afaa8a8 docs(workflow): formalize progress estimate + scout model level
504befc docs(workflow): move agent prompts into docs
2aafa41 docs(workflow): formalize main backup agent flow
```
