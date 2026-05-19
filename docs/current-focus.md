# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.
Startpromptar och rollgränser finns i
[`docs/agent-prompts.md`](agent-prompts.md).

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Standard loop steg 8 i
[`docs/agent-handbook.md`](agent-handbook.md) är obligatoriskt: efter
varje merge eller direktpush till `main` ska agenten i samma eller direkt
efterföljande commit:

1. Uppdatera "Current stage" och "Current active sprint" till nya läget.
2. Stryka från "Queue" / "Blocked" det som blev klart.
3. Lägga till nya blockers eller queue-items om något upptäcktes.
4. Bumpa "Last verified state"-SHA:n till nya HEAD.

Steward ska dessutom post-push-verifiera origin/main-SHA, `git status`,
`python scripts/focus_check.py` och om `origin/main` matchar lokal `main`.
Uppdatera `current-focus.md` och/eller `handoff.md` när ny faktisk HEAD
avslutar en sprint, active sprint ändras, next action/queue/blocked ändras,
ett beslut påverkar agentflöde, branchflöde, grindmode eller rollansvar, ny
risk/blocker/nice-to-have blir viktig för nästa agent, eller extern PR/
Grind-agent ändrar vad `main` betyder. Uppdatera inte för ren mikrostatus
som inte ändrar nästa agents arbete.

Operatören (Jakob) **verifierar** att det är gjort. Om operatören
upptäcker att filen är inaktuell är det första instruktionen till nästa
agent: "uppdatera current-focus innan något annat".

Last verified state: `ff7890b` (2026-05-19, sen kväll, **Steward Pass 1 docs-bump — B138 + B139 öppnade + B137-NOTE WIP**) — aktuell `origin/main` är `ff7890b` (`docs(steward): open B138 (pageCount leak) + B139 (tone propagation) + flag B137 fix-pointer WIP`). Sedan föregående `e1103c5`: `fc8f96d` (Steward post-Scout-case-4 focus-bump till `e1103c5`), `9089b7a` (term-coverage-allowlist för `'B137 fix'`-fras i Steward-prose), `6f91810` (docs(steward) orkestrator-handover efter Scout case 4 + ADR 0025 + nya regler), `ff7890b` (denna Steward Pass 1 docs-only ovanpå `6f91810`). **Steward Pass 1 (sen kväll, docs-only):** B138 (Medel, ny — pageCount-läckage från brief till routePlan; briefModel fångar `"2 sidor"` korrekt men `produce_site_plan` ignorerar `brief.pageCount` och emitterar scaffold-defaults; verifierat i sköldpaddssoppa-runen `data/runs/20260519T190606.540Z-51cef6dd-skoldpaddssoppa-karlsson-099d5c/`) och B139 (Låg-medel, ny — tone-extraction propageras inte till brand-tokens; `tone.primary="grön"` läses inte av renderern, brand-tokens kommer enbart från variant-CSS-vars) öppnade. B137-fix-pekaren (mot `_derive_tagline` i `scripts/prompt_to_project_input.py`) flaggad som WIP via NOTE i `docs/known-issues.md` — discovery-metans `fieldSources.company.tagline = "wizard"` säger att taglinen kommer från wizard-overlay-mappningen, inte från `prompt_to_project_input.py`. Scout RO-pass pågår parallellt och kartlägger exakt kodväg; Steward Pass 2 uppdaterar entryn med rätt fil/funktion + test-pekare. Aktuell buggräkning: **28 aktiva, 0 misplaced, 5 unknown, 98 stängda** (B138 + B139 nya). Inga öppna PRs, inga lokala feature-branches. `backup-34` skapad lokalt + pushad till origin för denna docs-pass. Tidigare paragraf:

Föregående verified state: `e1103c5` (2026-05-19, kvällen, **Steward post-Scout-case-4-bump + B137 öppnad + branch-discipline here-string-pattern + shell-windows-defaults-regel + ADR 0025 browser-fallback**) — aktuell `origin/main` är `e1103c5` (`docs(scout): record case 4 sköldpaddssoppa results + open B137 tagline leak`). Sedan föregående `ce1b137`: `2998275` (ny `governance/rules/shell-windows-defaults.md` med alwaysApply som låser PowerShell-default + bannar Unix-verb i Shell-anrop), `4440361` (ADR 0025 `governance/decisions/0025-browser-fallback-preview.md` skriven av Cloud Agent B — rekommenderar server-byggd statisk preview för Safari/Firefox-fallback, status: Proposed, väntar operatörsbeslut), `e1103c5` (Scout case 4 sköldpaddssoppa körd + B137 tagline-läckage öppnad). Scout case 4 gav snitt **5.0/10** (under 6.5-golvet) → **beslutsregeln EJ uppfyllt → Project DNA-sprint blockerad** → riktad bug-sweep på Case 4-fynd (B137 + Intent Guard + Page Intent Variant B från B132 warning-only till route-emission) är nästa steg. Aktuell buggräkning: **26 aktiva, 0 misplaced, 5 unknown, 98 stängda** (B137 ny: tagline läcker rå prompt-/beskrivnings-text till Hero-tagline; verifierat live i `skoldpaddssoppa-karlsson-099d5c/app/page.tsx:9`). Inga öppna PRs, inga lokala feature-branches. Backups oförändrade (`backup-30/31/32`). Branch-discipline.md uppdaterad med here-string + stdin-pipe som primary commit-msg-pattern (skapar inga disk-filer; Cursor-IDE-panelen får inga false-positives på temp-tracking) — denna commit är samtidigt smoke-test av nytt mönster (one BOM-byte hamnade i titeln pga PowerShell default UTF-8-encoding; ej blocker, dokumenterat för framtida fix). Tidigare paragraf:

Föregående verified state: `ce1b137` (2026-05-19, kvällen, **Steward post-handoff-bump efter auto-merge-pipeline PR #44-#46 + B136 + scout-orchestrator-finalize + branch-discipline harden**) — aktuell `origin/main` är `ce1b137` (`chore(rules): harden multi-line commit-msg path against elevated shell $env:TEMP`). Föregående HEAD `ed1d743` (`docs(scout): finalize handoff after auto-merge-pipeline + B136 fix`) — Steward-docs-bumpens commit-meddelande blev fel i `840e73f` ('feat(discovery): align Viewser overlay with taxonomy' från stale `C:\WINDOWS\TEMP\sb-commit-msg.txt` när PowerShell-shellens `$env:TEMP` resolverades till system-temp i stället för user-temp); diffen i `840e73f` var korrekt Steward-docs-sync. Force-push-amend till `main` förbjuden per safety-protokoll så meddelandet står kvar. `ce1b137` är erratan som hardar `governance/rules/branch-discipline.md` mot återfall (`$env:TEMP` → `$env:LOCALAPPDATA\Temp` + gotcha-paragraf + tidsstämpel-suffix på filnamn; rules_sync uppdaterar `.cursor/rules/branch-discipline.mdc` automatiskt). Sedan föregående `7a4e450`: PR #46 `cd05ee7` (Steward F2 fix-SHA + verified state-bump till `7a4e450`), PR #44 `cb046e1` (B134 — `wizardMustHave`-reset i `generate_followup` när follow-up har ny discovery), PR #45 `ebf5988` (B135 — `fieldSources` distinguish placeholder från brief), `496b750` (Steward sync stale body-text + scout-rapport-sammanfattning efter post-merge composer-2.5 + lokal-modell-reviews), `895d80b` (B136 — pre-resolve placeholder_fields mot post-merge contact, uppföljning av PR #45 follow-up provenance-glapp), `6fe04ef` (ruff F821-fix — drop unused `dict[str, Any]`-annotation i B136-test), `ed1d743` (finalize `docs/scout-orchestrator-handoff-2026-05-19.md`-tilläggssektion + B136 i `scripts/check_term_coverage.py`-allowlist). **B130-B136 alla stängda denna session** (började på 92, nu 98). Aktuell buggräkning: **25 aktiva, 0 misplaced, 5 unknown, 98 stängda**. Inga öppna PRs, inga lokala feature-branches. `backup-30` (pre-auto-merge), `backup-31` (pre-final-handoff) och `backup-32` (denna Steward-bump) finns på origin. Scout-orkestrator-handoff `docs/scout-orchestrator-handoff-2026-05-19.md` är aktuell handoff för sessionen — innehåller pågående/avslutade Cloud Agents, auto-merge-pipeline, RO-review-subagents, post-merge composer-2.5-review-cykel + 3 info-fynd som föreslagits för en framtida samlad cleanup-pass: B134-04 (unit-tester för `_clean_wizard_must_have`), B135-F6 (placeholder_fields=None vs set() + okänd nyckel-edge-cases), PR #44 docstring-puts i `generate_followup`. Viewser-overlay-E2E-Scout är fortsatt pågående efter Case 1-3a (snitt cirka 7.1/10); Case 4 (sköldpaddssoppa), Case 5 ('2 sidor'), Case 6 (follow-up), Case 3b (scrape) och Spår B (variant-experiment) återstår. Denna bump är ren Steward-docs-sync; den adderar inga nya B-ID:n och gör inget bug-scope-bump.

Föregående verified state: `7a4e450` (2026-05-19, **Steward verified-state bump efter PR #39-#43 + tree-utility-commits**) — aktuell `origin/main` är `7a4e450f47657e5675bb1d16b39a34c82791a992` (`chore(term-coverage): allowlist 'Cleanup' rubrik i scout-handoff`). Sedan föregående `9d7c4ba`: PR #39 `7ac14c4` stängde B133 första delen genom placeholder-contact-warning i Run Details; PR #40 `f56d327` stängde B130 genom att derivera `siteId` från `company.name`; PR #41 `89435ac` stängde B132 genom warning-only `pageIntentWarnings` när wizardens `mustHave` saknar scaffold-route; PR #42 `2901e4e` stängde B131 genom capability-alias-dedup; PR #43 `c1dce9c` hardenade B133 efter Codex P2-review med preserved-language-detektion + `openingHours` i placeholder-setet. Post-PR-commits: `2188fb5` + `b1c42f9` lade till delad `scripts/tree_view.py` och relaxade `tree_v*.py`-ignore-mönstret, `7a4e450` allowlistade `Cleanup`-rubriken för term coverage; `8d866fb` ignorerade operatörslokala `tree_v*.py`-utilityscripts; Scout-rapporten addades/revertades under `ba74bb7`/`c33d0ac` innan den nuvarande rapportfilen åter finns på main. Viewser-overlay-E2E-Scout 2026-05-19 nådde snitt cirka 7.1/10 över tre körda case (Case 1 ~7.3, Case 2 ~7.4, Case 3a ~6.6), identifierade B130-B133 och lämnade Case 4/6/3b + Spår B för senare körning. Inga B134/B135-entryer finns på aktuell HEAD. Öppna PR:er vid verifieringen: #44 (`fix(prompt-helper): close B134 — reset wizardMustHave when followup has new discovery`) och #45 (`fix(discovery): close B135 — fieldSources distinguish placeholder from brief`) är inte mergade och ingår därför inte i denna verified-state-bump. Aktuell buggräkning: **25 aktiva, 0 misplaced, 5 unknown, 95 stängda**. Denna PR är en ren Steward-docs-sync + F2 fix-SHA-rättning; den adderar inga nya B-ID:n till Stängda och gör inget bug-scope-bump.

Föregående verified state: `9d7c4ba` (2026-05-19, **branch-städning + räddad gitignore-fix**) ovanpå Steward-bump `9176f5e` ovanpå PR #38-merge `48a6a22`. Cherry-pickade `22d5f54` (`chore(gitignore): ignore embedding index cache`, 1 rad i `.gitignore` som la till `data/embedding-index/`) från övergiven branch `cursor/embedding-index-livscykel-3065` (Cursor-agent-commit från 2026-05-19 01:15 UTC som aldrig PR:ades). Förebygger att framtida embedding-index-cache committas. Branch-cleanup samtidigt: raderade `origin/cursor/embedding-index-livscykel-3065` (chore-fix räddad via cherry-pick), `origin/christopher-ui` (PR #31 mergad, taggen `archive/christopher-ui-2026-05-18` är fortsatt arkiv-säkerhet), `origin/feat/eight-scaffold-variants` (PR #38 mergad 48a6a22 — branchen lämnades först kvar för ev. follow-up men inga unika commits visade sig finnas vs main), plus lokal `feat/eight-scaffold-variants` som skapades temporärt under min PR #38-inspektion. **Backup-branches RÖRDA EJ**: 14 st `backup-11/13/15/17/19/21/22/24/25-VIKTIG/26-VIKTIG/27/28/29` + `backup-pre-christopher-ui-merge` ligger oförändrade på origin som operatörens säkerhetsnät. Aktuell origin-branch-list efter städ: `main` + 14 backups (var: `main` + 14 backups + 3 mergade/stale feature-branches). Aktuell buggräkning oförändrad: **25 aktiva, 0 misplaced, 5 unknown, 91 stängda** (cherry-pick var ren .gitignore, ingen B-ID-rörelse). Föregående verified state: `48a6a22` (2026-05-19, **merge-commit för PR #38 `feat/eight-scaffold-variants`**) ovanpå Steward mikrobump `99ec56d`. **Operatör-OK-merge** trots coach-direktiv 2026-05-19 ("ingen variant-promotion under Steward/Scout"); operatören valde merge_now medvetet med vetskap om att (a) variant-selection-logik fortfarande saknas så de åtta nya variants är dead code i prod-flödet, (b) en hardcoded default-mapping i `plan.py:_pick_variant` (`_DEFAULT_VARIANT_BY_SCAFFOLD`) introducerar teknisk skuld som B129 nu täcker, (c) merge under pågående Viewser-overlay-E2E-Scout-pass kan göra Scout-rapportens HEAD-SHA-låsning (`99ec56d`) inkonsistent med faktisk `main`. PR #38-innehåll: åtta nya canonical Scaffold Variants (4× `local-service-business` `midnight-counsel`/`warm-craft`/`pulse-fit`/`clinical-calm` + 4× `ecommerce-lite` `noir-editorial`/`earth-wellness`/`mono-tech`/`street-vivid`) i `packages/generation/orchestration/scaffolds/<scaffold>/variants/` + mirrors under `data/variant-candidates/<scaffold>/` för backoffice review, alla `enabled: true` och schema-valida; `packages/generation/planning/plan.py:_pick_variant` får en `_DEFAULT_VARIANT_BY_SCAFFOLD: dict[str, str]`-guard som garanterar att `nordic-trust`/`clean-store` förblir defaults (utan guarden skulle `variants[0]`-fallbacken råka välja en av de nya); `tests/test_variant_candidate_generator.py::test_load_variant_context_reads_exact_scaffold_files` justerad att läsa `_variant_ids_on_disk(scaffold_id)` istället för hardcoded `{"nordic-trust"}`. CI grön på PR (governance + builder-smoke + GitGuardian); lokala guards efter merge: ruff 0 findings, governance 17 policies OK, rules_sync --check OK, term coverage strict OK (förutom untracked Scout-rapport som registreras i hennes pass), pytest 62 passed (test_variant_candidate_generator + test_cross_policy_consistency + test_docs_freshness + test_bug_scope_discipline). **Variant-promotion-sprint (Queue #6) kvarstår** för: (a) variant-selection-logik kopplad till dossier-rationale/wizard-val/operator-decision, (b) flytt av default-mapping från kod till governance-policy + ADR (B129), (c) Re-Verifierings-pass som bekräftar att de nya variants faktiskt kan aktiveras i prod. Branch `feat/eight-scaffold-variants` lämnad kvar på origin (delete-branch opt-out) tills sprint avgör städning. Aktuell buggräkning: **25 aktiva, 0 misplaced, 5 unknown, 91 stängda** (B129 ny — `_DEFAULT_VARIANT_BY_SCAFFOLD` hardcoded i kod istället för governance). **Viewser-overlay-E2E-Scout** fortsätter som direkt nästa steg — rapportskeleton finns på `docs/reports/viewser-overlay-e2e-scout-2026-05-19.md` med HEAD-SHA-låsning på `99ec56d`. Scout-agenten bör notifieras att main är post-merge `48a6a22` så hen kan beslut: uppdatera HEAD-SHA i rapporten + fortsätta, eller stoppa-och-omstart vid `48a6a22`. Föregående verified state: `cd720aa` (2026-05-19, **Steward mikro-bump** efter två rena drift-commits ovanpå keramik-/e-handel-passet `bfcad8d`: `6d66c0e` (`docs(steward): bump current-focus + handoff after keramik-/e-handel-pass`, 2 filer) och `cd720aa` (`chore(gitignore): ignore local scout artifacts and certificates`, `.gitignore` + `apps/viewser/.gitignore`, 6 insertions för mkcert-cert + lokala scout-temp-outputs). Ingen ny produktimplementation, ingen B-ID-rörelse, ingen runtime-ändring. Båda inom bump-tolerance enligt `focus_check.py`-konvention. Aktuell buggräkning oförändrad: **24 aktiva, 0 misplaced, 5 unknown, 91 stängda**. **Öppen PR #38** (`feat/eight-scaffold-variants`, +755/-1 över 18 filer, commit `4cd1058`, åtta gpt-5.4-genererade scaffold-varianter: 4× `local-service-business` `midnight-counsel`/`warm-craft`/`pulse-fit`/`clinical-calm`, 4× `ecommerce-lite` `noir-editorial`/`earth-wellness`/`mono-tech`/`street-vivid`) parkerad i Blocked items per coach-direktiv 2026-05-19: **ingen variant-promotion under Steward/Scout**. Discovery taxonomy defaultar fortfarande till `nordic-trust` / `clean-store`; PR #38 saknar variant-selection-logik och kräver dedikerad variant-promotion-sprint (Queue #6) innan merge. Nästa konkreta steg oförändrat: **Viewser-overlay-E2E-Scout** — se "Next action". Föregående verified state: `bfcad8d` (2026-05-19, **B128-hardening (post-Composer-2.5-review)** ovanpå keramik-/e-handel-passet `d1fee90` + `6e5c33c` + `923f680`). Riktad Builder-pass på keramik-/e-handel-caset som Scout 3 (5.9/10) tappade på: **B128 (Hög, ny + stängd same-day)** — `_customer_safe_planner_note` släppte igenom svenska/engelska build-imperativ i `notesForPlanner` ("Bygg en liten e-handel på svenska för försäljning av keramik med fokus på köpkonvertering.") som publik /om-oss-copy; ny `_starts_with_planner_imperative()`-guard + utökad `_PLANNER_NOTE_BLOCKLIST`. Composer-2.5 read-only review hittade en ledande-icke-bokstavsprefix-bypass (`-Bygg ...`, `**Bygg ...**`, `1. Bygg ...`) som hardening `bfcad8d` stänger genom att strippa leading non-letter run före token-match. **B101 (Låg, stängd)** — hero-CTA "Shoppa nu" länkade till `/kontakt` istället för `/produkter`; ny `_hero_cta_target_path(dossier, listing_route, contact_path)` routar shop-varianten till listing-routen när scaffolden deklarerar `id="products"`. **B102 (Låg, stängd)** — `/produkter`-bottom-CTA "Fråga om en beställning" matchade inte shop-tonen; ny `_commerce_bottom_cta_label(dossier)` med whitelist (`"Hör av dig för att beställa"` / `"Get in touch to order"`), länk mot kontakt-routen behålls (ingen checkout i MVP). Separat dev-tooling-commit `6e5c33c` lägger opt-in `-Https`-flag i `scripts/dev-viewser.ps1` så Viewser kan starta på `https://localhost:3000` (StackBlitz embed-konsol kräver https:// origins, http:// rejectas). Guards efter `bfcad8d`: `python -m ruff check .` (0 findings), `python scripts/governance_validate.py` (17 policies OK), `python scripts/rules_sync.py --check` (alla speglar i synk), `python scripts/check_term_coverage.py --strict` (inga okända kandidater), `python -m pytest tests/test_prompt_to_project_input.py tests/test_builder_route_emission.py tests/test_bug_scope_discipline.py tests/test_docs_freshness.py -q` (197 passed). Aktuell buggräkning: **24 aktiva, 0 misplaced, 5 unknown, 91 stängda** (B101 + B102 + B128 stängda; B128 fix-SHA pekar på initial `d1fee90` + hardening commit). Variant-spåret `feat/eight-scaffold-variants` (commit `4cd1058`) finns kvar på origin som separat feature-branch och rörs inte i detta pass — coach-direktiv: ingen variant-promotion i Steward-rundan, separat sprint/PR krävs. Föregående verified state: `e3fa67b` (2026-05-19, **merge-commit för PR #37 `feature/b121-baseline-smoke` (B121 PR D)** ovanpå `89680fa`). PR #37 (`2713d0d` smoke-rapport + `c675607`/`1274d92` rapport-justeringar + merge `e3fa67b`): CLI baseline-smoke mot fyra produktbaseline-prompter (`elektriker Malmö`, `frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som säljer keramik`) — alla fyra klarar `prompt_to_project_input --discovery` → `build_site.py` med korrekt `DiscoveryDecision`, scaffold/variant/starter-mappning, `fieldSources`, `fallbackWarnings` och `selectedDossiers.required = []`. Rapport: `docs/reports/b121-baseline-smoke.md`. **B121 stängd formellt** i `known-issues.md` via PR A (#34 `70c261b`) + PR B (#35 `ec32913`) + PR C (#36 `89680fa`) + PR D (#37 `e3fa67b`). Medvetna icke-blockers kvar: full Viewser → `/api/prompt` → preview E2E, per-run trace i Backoffice, capability/dossier gaps. Föregående verified state: `89680fa` (PR #36 B121 PR C — Backoffice Discovery Control, mapping-tabell, dry-run-resolver, gated edit-toggle, 16 tester i `tests/test_backoffice_discovery_control.py`). Mergade feature-branches `feature/discovery-resolver-taxonomy`, `feature/discovery-frontend-alignment`, `feature/backoffice-discovery-control`, `feature/b121-baseline-smoke` kan städas från origin vid operatör-OK; `backup-*` rörs inte.

Föregående verified state: `0fe353f` (2026-05-18, `fix(backoffice): close two control-plane review findings (graph key + doctor)` ovanpå PR #32-cherrypick-serien och `eb1a4ec` B125-docs-bump). Stängde två post-PR-#32-control-plane-fynd från extern review: B126 (dossier-graf-nyckel-mismatch — `_compatible_dossier_edges` byggde `dossier:{id}` medan noder var registrerade som `{class}-dossier:{id}`, vilket gjorde impact-vyn blind för scaffold→dossier-spåret) och B127 (Doctor-villkor inverterat — `run_health_checks` varnade på `status == "implemented"` med tom details-sträng och tystnade på riktiga `incomplete`/`placeholder`-scaffolds). Båda introducerades i cherry-pick-arvet från `3338d79` + `b636450` och är låsta av regressionstester i `tests/test_backoffice_asset_graph.py`. Guards efter `0fe353f`: `python -m ruff check .` (0 findings), `python scripts/governance_validate.py` (16 policies OK), `python scripts/rules_sync.py --check` (alla speglar i synk), `python scripts/check_term_coverage.py --strict` (inga okända kandidater), `python -m pytest tests/` (**701 passed, 3 skipped E2E** — +2 nya regressionstester från B126/B127-passet). Den efterföljande commiten `9291c46` (`chore(vscode): set PowerShell default formatter to ms-vscode.powershell`) är inom bump-tolerance och rör enbart `.vscode/settings.json`. Föregående produktpass var **Backoffice-kontrollplans-MVP via cherry-pick av PR #32**: sex commits från `cursor/backoffice-kontrollplan-mvp-62aa` (skapad från `ca59529` innan PR #31 Christopher-UI:n mergades, så `mergeStateStatus=CLEAN` mot main men diff-trädet hade raderat hela `apps/viewser/`-frontenden om en three-way merge gjorts) cherrypickades ovanpå `60515c6` i bevarad ordning: `3338d79` `fix(backoffice): normalize compatible dossier graph edges` (`backoffice/asset_graph.py` lyfter dossier-edge-extraktion ur `view_control_plane` till modulnivå, namngivna helpers `_compatible_dossier_id`/`_compatible_dossier_details`/`_compatible_dossier_edges`, hanterar dict-entries med `id`/`when`-fält), `b636450` `feat(backoffice): add read-only impact preview` (ny modul `backoffice/impact.py` + `impact_for_node()` som returnerar `incoming`/`outgoing`/`affectedNodes`/`affectedPaths`/`riskLevel`/`runtimeEffect`, plus konsekvensvy under `view_control_plane`), `c22bc1d` `feat(backoffice): add selection profile editor` (ny modul `backoffice/selection_profiles.py` med `validate_profile`/`signal_findings`/`write_profile`, ny gemensam `backoffice/io.py` med `atomic_write_text`/`atomic_write_json` via temp + `os.fsync` + `os.replace`, ny vy `view_selection_profiles` med edit-toggle), `2065a33` `feat(backoffice): improve variant candidate review` (`compare_variant_to_existing`/`variant_diff_rows`/`list_variant_candidates` i `asset_graph.py`, kandidater valideras via `packages/generation/artifacts.validate_variant` och Variant Candidates-vyn visar similarity table + field-level diff), `855a605` `fix(backoffice): use atomic model role writes` (refactor av `views/governance.py` + `views/llm_engine.py` att använda gemensam `..io.atomic_write_text`/`atomic_write_json` istället för lokal helper — rollback-flödet kvarstår, men alla policy-writes är nu atomic via temp-fil + rename), `00103e3` `feat(backoffice): add soft dossier candidate generator` (ny `scripts/generate_dossier_candidate.py`, mirror av `generate_variant_candidate.py`: pydantic structured output via dossierModel-rollen med mock-fallback utan `OPENAI_API_KEY`, skriver `data/dossier-candidates/soft/<id>/{manifest.json,instructions.md,components/}`, validerar via `packages/generation/artifacts.validate_dossier`, ny vy `view_dossier_candidates` i backoffice). Inga konflikter; en automatisk merge i `scripts/check_term_coverage.py` där operatörens `DevTools`/`ElementCreationOptions`-tillägg från `c7049b3` och PR #32:s nya `DossierCandidateModel`/`DossierGenerationError`/`DossierGenerationResult`/`DossierManifestModel`/`DossierModelResolutionError` samexisterar rent. PR #32 stängdes (inte mergades) med kommentar och `cursor/backoffice-kontrollplan-mvp-62aa` raderades från origin. Samtidigt städades den döda branchen `frontend/christopher-import` (PR #17 var CLOSED, ersattes av PR #31 `integrate/christopher-ui-into-main` med annan branch). Föregående produktpass var **StackBlitz embed-preview unblock + npm audit cleanup**: B123 (Medel — `apps/viewser/next.config.ts` saknade `Cross-Origin-Embedder-Policy`/`Cross-Origin-Opener-Policy` så StackBlitz embed visade "Unable to run Embedded Project" istället för preview) och B124 (Medel — uppföljare där parent-COEP visade sig otillräcklig: Chrome krävde dessutom `credentialless`-attribut på själva `<iframe>`-elementet eftersom StackBlitz embed-respons inte skickar egen COEP-header) stängda i samma pass. Båda gör B59 (parkerad header-experiment-skuld från 2026-05-15) **förmodligen löst** men kvar att verifiera end-to-end med en grön preview — se uppdaterad B59-entry i `docs/known-issues.md` (status: parkerad → "förmodligen löst i B123 + B124, väntar end-to-end-verifiering"). Föregående commits i samma pass: `5d05e0d` (B124 — `document.createElement`-patch runt `sdk.embedProject(...)` så iframen får `credentialless`-attribut innan src-fetch + 3 source-locks i `tests/test_viewser_isolation_headers.py`), `5f23d13` (B123 — `next.config.ts:async headers()` med `Cross-Origin-Embedder-Policy: credentialless` + `Cross-Origin-Opener-Policy: same-origin` på `/:path*` + 4 source-locks; tog bort gammal felformulerad negativ lock i `tests/test_viewser_files.py:test_viewser_does_not_set_global_cross_origin_isolation_headers` från `98e8364`), `c7049b3` (operatör-direktcommit, `package-lock.json`-städning från postcss-override `^8.5.10` i `apps/viewser/package.json` som tystar npm audit GHSA-qx2v-qp2m-jg93 på Nexts vendored postcss 8.4.31 — false positive per Vercels eps1lon, men ren `0 vulnerabilities` är värt 3 rader JSON). Föregående produktpass (parallel-agent-runda före): `df24488` (B118 scrape-runner SIGKILL-fallback), `6772a14` (B117 SVG-XSS via CSP sandbox + nosniff på `/api/asset-preview`), `fe9748e` (B114 upload size guard), `cd03897` (B113 SSRF redirect-validation + 6 regressionstester). PR #31 `feat(viewser): integrate christopher-ui discovery and asset workflow` är fortsatt frontend-basen (merge `3f4543d`, integration `0510146`): hela `apps/viewser/components/discovery-wizard/**`, asset upload pipeline (`apps/viewser/lib/asset-store/**` + `/api/upload-asset` + `/api/asset-preview`), URL scrape (`scripts/scrape_site.py` + `/api/scrape-site` + `apps/viewser/lib/scrape-runner.ts`), SiteHeader/ConsoleDrawer, shadcn-primitives, `BUILD_TIMEOUT_MS` 3 min → 10 min, schema-fält `brand{logo, heroImage, primaryColorHex, accentColorHex, logoText, heroText}` + `gallery[]` + `$defs/assetRef` i `governance/schemas/project-input.schema.json`, naming-dictionary v15 → v16 (AssetRef, AssetStore, operator upload). Aktuell buggräkning: **27 aktiva, 0 misplaced, 5 unknown, 87 stängda** (B126 + B127 stängda i `0fe353f`; PR #32 var feature work — inga B-IDs öppnades/stängdes där; B125 öppnad i en uppföljande docs-pass efter operatörsdiskussion om StackBlitz-embed-browserstöd, se nedan). Guards gröna efter PR #32-cherrypick: `python -m ruff check .` (0 findings), `python scripts/governance_validate.py` (16 policies OK), `python scripts/rules_sync.py --check` (alla speglar i synk), `python scripts/check_term_coverage.py --strict` (inga okända kandidater), `python -m pytest tests/` (**699 passed, 3 skipped E2E** — +24 nya tester från `tests/test_backoffice_asset_graph.py` + `test_backoffice_impact.py` + `test_backoffice_selection_profiles.py` + `test_dossier_candidate_generator.py`). `backup-pre-christopher-ui-merge` finns pushad på origin som extra säkerhet före PR #31-mergen; taggen `archive/christopher-ui-2026-05-18` pekar på `4a16528` så hela christopher-ui-branchen kan återställas vid behov. `origin/christopher-ui` är raderad enligt operatörens policy om inga långa parallella branches. **Branch-rensning under PR #32-passet:** `cursor/backoffice-kontrollplan-mvp-62aa` (PR #32 source) och `frontend/christopher-import` (PR #17 CLOSED) raderade från origin. **Kvar och flaggade som potentiellt onödiga** (väntar operatör-OK innan radering): `feat/demo-baseline-fix-1b-bug-sweep` (alternativ-väg till PR #28 som istället mergades från `cursor/demo-baseline-buggsvep-44a5`). Alla 19 `backup-*` är operatörens säkerhetskopior och rörs inte utan instruktion. PR #33 (denna docs-only state-sync) är aktuellt öppen.

Föregående produktcommit: `ab74c2a` (2026-05-15, demo-baseline-fix 1A landade direkt på `main`. Konvention för denna rad: SHA pekar på senaste produkt-/kodcommit; den efterföljande Steward-bump-commiten själv (denna rad-ändring) räknas som "within bump tolerance" av `focus_check.py` och får inte ge en till bump-rundgång. `feat(builder): demo-baseline-fix 1A` (`ab74c2a`) stängde Scout-auditens topp 3 demo-blockers i ett pass: (1) `/_global-error` prerender-fel (regression/variant av B41) löst genom att lägga explicit `app/global-error.tsx` i `data/starters/marketing-base/app/` och `data/starters/commerce-base/app/` med `"use client"` och inga third-party-imports - verifierat end-to-end via `painter-palma` (marketing-base) + `atelje-bird` (commerce-base) som båda nu landar `status: ok`, `quality: ok`, `npm install + npm run build` gröna; (2) rå prompt läckte ut som `company.name`/`company.story` på rendererade sajter - `scripts/prompt_to_project_input.py` skriver om `_company_name_from_prompt` till `_derive_company_name` (läser bara `brief.businessTypeGuess` + `brief.locationHint` via en liten svensk business-type label-map: electrician -> elektriker, hairdresser -> frisör, ceramics-studio -> keramikstudio, ...) och `_derive_story` (föredrar `brief.notesForPlanner`, fallback till strukturerad svensk platshållartext, aldrig raw prompt); (3) svenska tecken förstördes i service-labels (`F Rska Gg Direkt Fr N G Rden`) - `_slugify_label` NFKD-foldar för id-fältet (`färska ägg -> farska-agg`) men `_service_label_from_text` behåller å/ä/ö i labeln, och brief `services_mentioned` Field-description + system-prompt frågar nu efter natural-language fraser på originalspråk istället för kebab-case English slugs. `slugify_site_id` NFKD-foldar också före substitution så `elektriker i Malmö` ger `elektriker-i-malmo-<tail>` (förut `elektriker-i-malm-<tail>` med `ö` kollapsad till dash). Regression-tester: `test_company_name_and_story_never_contain_raw_prompt` (låser exakta tokens från den failande real-runen `enehmsida-som-s-ljer-b-t-661e23`: `Enehmsida`, `båtari`, `2 sidor`), `test_swedish_service_labels_preserve_case` (`färska ägg direkt från gården -> Färska ägg direkt från gården` som label, ASCII-only slug), `test_slugify_label_ascii_folds_swedish_chars`, `test_company_name_uses_swedish_business_type_mapping`, `test_story_prefers_notes_for_planner` plus fyra fallback-tester. Out-of-scope per Scout/coach: ingen Project DNA / semantic follow-up merge, ingen StackBlitz/COOP/COEP, inga nya starters, ingen docs/rules-sprint utöver denna bump. `backup-19` skapad från synkad `main` innan sprintarbetet (lokalt + push). Föregående mainline-pushar samma dag: `f29688c` (Steward-bump efter rules-commit), `d072c98` (powershell-glob + cli-safety-belt rules), `8d45140` (Steward-sync efter prune-sprinten), `2acdeca` (prune-script + tester), `7b90c0c` (Steward-sync efter B60), `65f052a` (B60 fix), `dd5464f` (post-PR-#27 sanity-bump), `e057fbd` (PR #27 follow-up versions squash-merge). `backup-15` t.o.m. `backup-19` finns lokalt och på origin. Inga öppna PRs.)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `e1103c5` (`docs(scout): record case 4 sköldpaddssoppa results + open B137 tagline leak`) ovanpå `4440361` (ADR 0025 `governance/decisions/0025-browser-fallback-preview.md` av Cloud Agent B). Scout-passet är nu körd över **4 case** (Case 1: 7.3, Case 2: 7.4, Case 3a: 6.6, Case 4: 5.0) — snitt **6.6/10** men Case 4 är **5.0 < 6.5-golvet**, så beslutsregeln (≥7 OCH inget <6.5 → Project DNA-sprint) är **EJ uppfyllt**. **Direkt nästa steg:** riktad bug-sweep på Case 4-fynden — (a) **B137 fix** (tagline-läckage av rå prompt-text, snabb post-process-fix i `_derive_tagline`, ~1 h), (b) **Intent Guard** (ny modul som flaggar prompt-vs-wizard-mismatch, ~2 h, krävs för verklig SMB-användning), (c) **Page Intent Variant B** (B132 från warning-only till route-emission, ~3-5 h, krävs för wizard-mustHave + fri-prompt-sidantal-respekt), eller (d) **ADR 0025 operatörsbeslut + implementation** (server-byggd statisk preview vs alternativen — produktblockare innan extern kund). Project DNA-sprint väntar tills Case 4-spåret är åtgärdat och Case 5/6 + Spår B körda.

Föregående baseline: PR #28 squash-merge (`885431b`) för demo-baseline-fix 1B + bug-sweep. 1B stängde must-/should-land-spåret och alla nice-to-have som hanns med: B64/B65 (Site Brief company/contact-fält + ADR 0022), B66 (tom trustSignals renderar inte "Varför oss"), B69 (Quality Gate route-scan får alla emitterade default-routes inkl. `/om-oss`; aggregate-status ändrades medvetet inte), B70 (IPv6 localhost Host-header), B71 (follow-up merge-docstring + byte-stabil story/tagline/tone), B72 (`listRuns` slicar innan JSON-läsning), B73 (tagline-fallback utan Project Input-jargong), B74 (dev_generate codegen routes), B75 (`additionalProperties: false` i Project Input-schema), B76 (Run Details visar site-plan), B77 (dossier-komponenter får inte skugga starter-komponenter), B78 (realpath-baserad dossier-whitelist), B79 (svensk selectedDossiers-rationale) och B83 (service slug-kollisioner får suffix). PR #28 verifierades med ruff, full pytest, governance/rules/term checks, Viewser `npm run build` och två isolerade smoke-builds (`elektriker Malmö`, `frisör Göteborg`) som båda landade `status=ok`, `quality=ok`. Bugbot var inte aktiv på PR:n; GitHub governance, builder-smoke och secret-scan var gröna före merge.

**Verifierings-Scout 2026-05-15 (pre-hotfix)** körde fyra skarpa prompter (`elektriker Malmö`, `frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som säljer keramik`) via `prompt_to_project_input.py` + `build_site.py` mot 1A-koden. Alla fyra byggde grönt med `status: ok`. **Totalsnitt 6.2 / 10** — precis över 6/10-tröskeln, men tre regressioner/buggar identifierades och loggades som **B61** (notes_for_planner-läckage som customer copy — 1A-regression), **B62** (`detect_language` slår fel på korta svenska prompts → engelska sajter på 2 av 4 case) och **B63** (`_BUSINESS_TYPE_LABEL_SV` slug-glipor mot briefModels faktiska slugs). Alla tre stängda i 1A-hotfix `d99f8ba`; nästa steg är re-verifierings-Scout med samma fyra prompter för att jämföra mot 6.2-baselinen — se "Next action".

Föregående produktcommit före hotfix: `ab74c2a` (demo-baseline-fix 1A): Scout-auditens topp 3 demo-blockers stängda i ett pass — `/_global-error` build-fel borta (verifierat på `painter-palma` + `atelje-bird` med båda `status: ok`), rå prompt landar inte längre i `company.name`/`company.story` (brief-driven `_derive_company_name` + `_derive_story` ersätter prompt-as-H1/story-mönstret med Swedish business-type label-map), svenska tecken bevarade i service-labels (NFKD-fold för slugs, original-string för labels). 10 regression-tester i `tests/test_prompt_to_project_input.py` från 1A-passet kvarstår.

Föregående cleanup/prune-sprint är fortfarande klar: nytt `scripts/prune_generated_previews.py` med dry-run default + `--apply`-gate (env-flaggan `SAJTBYGGAREN_PREVIEW_RETENTION_DRY_RUN` defaultar till OFF så `--apply` ensamt räcker; sätts den explicit till `true` blockas radering även med `--apply` som operatörs-safety-belt) + current-pointer-skydd + port-3000-refusal landade tillsammans med tolv regression-tester i `tests/test_prune_generated_previews.py` (tio från första passet plus två som låser env-/CLI-interaktionen efter Finding 1-fixen) och utvidgad allowlist i `scripts/check_term_coverage.py`. B60 är stängd: follow-up-versioneringen från PR #27 hade fyra kontraktsbrott som upptäcktes i post-merge audit (versionerade snapshots inte immutabla, follow-up-prompt läckte i `company.story`, icke-atomisk pointer-update, tyst init-fallback vid saknad sidecar) och alla fyra är nu fixade i `scripts/prompt_to_project_input.py` + `scripts/build_site.py:load_prompt_input_meta` med 5 nya/uppdaterade regression-tester. PR #27 (`feat(viewser): preserve follow-up prompt versions`, `e057fbd`) är fortfarande merge-baseline: follow-up promptar skriver immutable `<siteId>.vN.project-input.json`/`<siteId>.vN.meta.json`-snapshots i `data/prompt-inputs/`, behåller `projectId`/`originalPrompt` och lägger `followUpPrompt` på snapshot-meta. `scripts/build_site.py` läser sidecar-meta intill dossier-pathen och trådar `mode`/`projectId`/`version`/`originalPrompt`/`followUpPrompt` in i `input.json`, `generation-package.json` och `build-result.json`. `apps/viewser/lib/runs.ts` läser per-run-meta från `build-result.json` -> `input.json` -> mutable sidecar legacy-fallback, så RunHistory visar stabil `projectId` + `version` även när nya follow-ups landar. `apps/viewser/lib/project-inputs.ts` filtrerar `.vN.project-input.json`-snapshots från ProjectInputPicker (bara current pointer är valbar). `apps/viewser/lib/prompt-runner.ts` + `lib/build-runner.ts` föredrar repo-roten `.venv` Python när den finns (cloud/lokal dev-konsistens) och cleanar prompt-/build-mutex via `try/finally`.

StackBlitz-preview-spåret är inte längre payload-only: B123/B124-passet 2026-05-18 satte `Cross-Origin-Embedder-Policy: credentialless` + `Cross-Origin-Opener-Policy: same-origin` i `apps/viewser/next.config.ts:async headers()` (`/:path*`) och patchar dessutom `document.createElement` runt `sdk.embedProject(...)` i `apps/viewser/components/viewer-panel.tsx` så att `<iframe>` StackBlitz SDK skapar internt får `setAttribute("credentialless", "")` innan src-fetch — utan iframe-attributet blockerar Chrome embeddet trots korrekta host-headers eftersom StackBlitz embed-respons inte själv skickar COEP. Tidigare (felformulerade) negativa source-lock i `tests/test_viewser_files.py` är borttagen; ny positiv lock i `tests/test_viewser_isolation_headers.py` täcker (1) host-COEP måste finnas, (2) värdet måste vara `credentialless` (inte `require-corp`), (3) host-COOP måste vara `same-origin`, (4) headers gäller alla routes, (5)-(7) iframe-attribut-patchen finns + scopas korrekt + återställs i finally. `apps/viewser/lib/stackblitz-files.ts` patchar fortfarande in-memory (`next dev/build --webpack`, `npm run build && npm run start`, lockfile med i payload, `app/global-error.tsx`-override, patched payload-bytes mot size cap, `next start`-fallback). Ingen ändring i starters, builder eller preview-runtime-paketet; ADR 0021 är källan för beslut/avgränsning.

B59 (StackBlitz `template:"node"`/WebContainer-embed blockerad/instabil i moderna Chrome-runtimes) var **parkerad** efter att tre header-lägen testades 2026-05-15 utan grön preview. B123/B124-passet 2026-05-18 implementerade `credentialless`-host-header **plus** `credentialless`-iframe-attribut, vilket är en kombination som inte testades i 2026-05-15-experimentet. Det löser åtminstone Chromes blockering av embeddet på header-nivå (verifierat med en HEAD-request mot host-URL:n som returnerar båda headers). B59 är därför **förmodligen löst** för Chromium-browsers, kvar att operatörverifiera end-to-end genom att se en grön preview faktiskt rendera. Status uppdaterad i `docs/known-issues.md`. Om verifikationen lyckas kan B59 stängas i en separat docs-commit; om den misslyckas är nästa arkitekturbeslut byte till lokal `next dev`-process som same-origin iframe på `localhost:NNNN` eller static StackBlitz-template.

Browser-stöd är nu en explicit produkt-begränsning: B125 (Hög, produktblocker innan launch) registrerad efter operatörsdiskussion 2026-05-18. Embedded WebContainer-preview funkar bara i Chromium (Chrome 110+, Edge, Brave, Vivaldi) — Safari (inkl. iPhone) och Firefox kan inte ladda embeddet. ~25-35% av svenska SMB-slutkunder behöver server-byggd fallback för preview-fliken. Slutpublicerade kund-sajter är vanlig Next.js och funkar i alla browsers. Fyra fallback-kandidater listade i B125 (server-byggd statisk preview, lokal `next dev`-park, "Öppna i StackBlitz"-fallback, Vercel preview-deployments) — beslut ska landa i ny ADR innan implementation. Browser-support-kravet dokumenterat i README.md "Browser-stöd för preview-läge" och `docs/product-operating-context.md` "Runtime och preview".

Läget bygger på orkestrator-playbooken i `e026642`, `27f7fe9` (focus efter PR #26), PR #26:s produktkompass (`docs/product-operating-context.md`) i `1cba454`, `6daee58` (B45 `_pick_contact_route`-propagation till layout/home/services/products), `c2d8632` (PR #24 docs-base starter, squash-merge), `10eb286` (B48 follow-up-semantik i dev-driver/backoffice), `5d746e9` (Builder audit-fix för B44 + B46) och `9944abb` efter Prompt-till-sajt MVP v1 (Builder-
sprint 2026-05-13/14, Scout-RO-godkänd), review-hotfix för
prompt-helperns brief-fallback, Viewser mini-sprint som tog bort
gamla ChatPanel från home och en audit-hotfix-sprint som städade
fyra Scout-fynd i prompt-flödet. Operatören kan nu skriva
en fri prompt i Viewser, helpern (`scripts/prompt_to_project_input.py`)
kör briefModel, mappar Site Brief deterministiskt mot en schema-valid
Project Input, skriver den till `data/prompt-inputs/SITE_ID.project-input.json`
plus sidecar `SITE_ID.meta.json` (projectId/version/originalPrompt/
briefSource), och `apps/viewser/app/api/prompt/route.ts` triggar
`runBuild` med dossier-path-override. PromptBuilder är nu den enda
primära promptytan på Viewser-home; legacy ChatPanel är raderad. Follow-up
prompt versions är nu landat: operatören kan fortsätta på befintlig
prompt-input/run, behålla `projectId`, bumpa version och få ny build/run
för samma sajtspår. RunHistory uppdateras via samma `fetchRuns`-loop som
`/api/build`. PR #23 har dessutom landat backoffice trace/playground-
förbättringar: engine-runs-vyn och playground-vyn använder en gemensam strukturerad
trace-viewer och playground visar subprocess-status/loggutdrag medan körningen
pågår. `backup-9` finns lokalt från pre-PR-#23-läget; backup-8 finns lokalt
efter follow-up-sprinten; backup-7 från `fb11925` ligger på origin som fallback
efter audit-hotfix-sprinten. PR #22 har också landat `portfolio-base` som ny
harmoniserad starter under `data/starters/portfolio-base/`. Commit `e9093c0`
ändrar bara `.cursor/settings.json` och aktiverar `linear` + `sanity`; commit
`d43bce2` synkar handoff/focus efter settings-commiten.

Föregående: PR #21 (lucide-react i commerce-base + ADR 0020,
mergad `04fc2fa` 2026-05-13 19:55 UTC) gjorde full `npm run build`
mot `.generated/atelje-bird/` grön (11 statiska sidor + commerce-
base:s dynamiska routes utan `Module not found`). PR #20 (B20 step 2
mapping-flip + ADR 0019, samma dag 19:33 UTC) aktiverade
`SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Real
codegenModel-scope är fortsatt låst till `marketing-base` per
ADR 0017 (ingen utvidgning beslutad).

Prompt-till-sajt MVP v1-pushen (2026-05-14):

- `afaa8a8` — `docs(workflow): formalize progress estimate + scout
  model level`. Operatörs-supplied: Builder slutrapport ska ge en
  grov progress-procent + bedömning av nästa etapp; Scout föreslår
  modell-/insatsnivå 1-10; Steward verifierar att current-focus +
  handoff fortfarande pekar rätt.
- `4d5b4de` — `feat(viewser): prompt-till-sajt MVP v1`. Ny
  `scripts/prompt_to_project_input.py` (briefModel + Site Brief →
  schema-valid Project Input + sidecar meta i `data/prompt-inputs/`),
  ny `/api/prompt` route med localhost-guard + Zod-payload (1-4000
  tecken), ny PromptBuilder-UI-panel, `runBuild` får
  dossier-path-override bakom ALLOWED_DOSSIER_ROOTS-whitelist
  (examples/ + data/prompt-inputs/), 11 nya helper-tester + 2 nya
  viewser-guards. Ingen ADR/policy-bump (sidecar-meta undviker
  project-input.schema.json-migration).
- `c6e2f1d` — `fix(viewser): fall back when prompt brief extraction
  raises`. Review-hotfix: `extract_site_brief` och
  `site_brief_to_artifact` ligger nu i fallback-try/catch så
  promptflödet skriver schema-valid mock Project Input även vid
  oväntade LLM-/serialiseringsfel. Regressions täcker båda grenarna.
- `ea4b165` — `fix(viewser): isolate StackBlitz preview mount`.
  StackBlitz SDK embed mountas nu i en unmanaged child-node istället
  för att ersätta React-ägda preview-shellen. Cleanup använder
  `replaceChildren()`. Source-lock uppdaterad i `test_viewser_files.py`.
- `fd67fbd` — `refactor(viewser): remove legacy chat panel from home`.
  `app/page.tsx` importerar/renderar inte längre `ChatPanel`; nya
  `test_viewser_prompt_primary.py` låser att PromptBuilder är canonical
  promptyta på Viewser-home.

Audit-hotfix-sprint (2026-05-14, post-Scout-bug-audit):

- `fe56344` — `fix(prompt-helper): hoist brief imports to module level
  for monkeypatching`. Lyfter `detect_language`,
  `extract_site_brief`, `site_brief_to_artifact` och
  `resolve_brief_model` från function-scope till modulnivå så
  fallback-tester faktiskt patchar lookup-namnen som
  `prompt_to_project_input.generate` använder. Tidigare patch mot
  `packages.generation.brief.*` no-opp:ade tyst.
- `cb54ca9` — `docs(agent-prompts): expand role catalog with parallel-
  agent rules`. Utökar Scout/Builder/Steward-startprompter och låser
  parallell-agent-disciplinen.
- `1033bf6` — `fix(prompt-route): return 400 on Zod errors and trim
  whitespace at API edge`. Splitt:ar try/catch så `ZodError` -> 400
  med valideringsmeddelandet, lägger `.trim()` före `.min(1)` i
  payload-schemat så whitespace-only prompts fångas vid API-gränsen
  istället för att slinka ned till helperns 500-gren. Två nya
  source-lock-tester i `tests/test_viewser_files.py`.
- `e067006` — `fix(prompt-runner): pass -- to argparse so dashed
  prompts spawn cleanly`. `spawn(...,[scriptPath, "--", trimmed])` så
  en prompt som börjar med `-` eller `--` (vanlig punktlista) inte
  tolkas som CLI-option av argparse i `prompt_to_project_input.py`.
- `c039ebd` — `fix(viewer-panel): refresh stale fallback copy after
  legacy chat panel removal`. 404-fallback och tip-block hänvisar nu
  till promptfältet istället för den borttagna Build-knappen i
  ChatPanel.
- `e421a00` — `chore(check_term_coverage): allowlist ZodError TS
  symbol`. Speglar Pydantic `ValidationError`-behandlingen så
  `ZodError` (extern lib-symbol från `zod`) inte räknas som
  okänt domänbegrepp i strict-läget.
- `2f0af68` — `docs: bump focus + handoff to e421a00 post-audit-
  hotfix-sprint`. Standard loop steg 7 efter audit-hotfix-sprinten:
  bumpar SHA + uppdaterar Queue/Blocked.
- `c3dcc14` — `docs: correct verified HEAD to 2f0af68 in focus +
  handoff`. Följdfix ovanpå `2f0af68`; lokal `main` och `origin/main`
  är post-push-verifierade på denna SHA.
- `006be38` — `docs(workflow): formalize steward post-push
  verification`. Låser Builder→Steward-post-push-flödet i docs,
  governance-spegeln och `focus_check.py`-remindern.
- `2701b00` — `feat(viewser): add follow-up prompt versions`.
  Follow-up prompt versions landat direkt på `main`: promptflödet kan
  fortsätta på befintligt `projectId`, bumpa version och skriva nya
  prompt-inputs/runs för samma sajtspår.
- `e1ad5ca` — `feat(backoffice): improve trace viewer and playground
  logs`. PR #23 squash-mergead: backoffice trace/playground-städning med
  gemensam trace-viewer, synlig subprocess-status/loggar och stängda
  backoffice-poster i `docs/known-issues.md`.
- `9944abb` — `feat(starters): add harmonized portfolio-base starter`.
  PR #22 squash-mergead efter update-branch mot post-PR-#23 main och gröna
  governance-, Bugbot- och secret-scan-checkar.
- `e9093c0` — `Liten settings.json bara som committades`.
  Aktiverar `linear` och `sanity` i `.cursor/settings.json`; ingen
  produktkod ändrad.
- `d43bce2` — `docs: sync handoff after settings commit`.
  Synkar current-focus/handoff efter settings-commiten.
- `34551b4` — `docs(cleanup): modernize viewser copy and starter
  routing notes`. Steward-cleanup efter Scout-fynd: README, Viewser,
  starter-routing och migration-plan moderniserade till PromptBuilder
  samt follow-up versions; `.cursor/settings.json`-status och stale
  PromptBuilder-timeout-nice-to-have rensade.
- `5d746e9` — `fix(viewser): audit-fix sprint for B44 + B46`. B44 stängd:
  `/api/prompt` exponerar `buildStatus`, PromptBuilder klassificerar
  utfall via `classifyBuildStatus`, `app/page.tsx` använder
  `PromptBuildOutcome` + `headerStatusForOutcome`. B46 stängd:
  `apps/viewser/components/chat-panel.tsx` raderad, tester +
  vocabulary-discipline + check_term_coverage rensade. Två nya öppna
  poster: B45 (hardcoded `/kontakt`) och B47 (commerce-base Shopify
  handles).
- `9ff7c50` — `docs(focus): bump verified SHA + queue after audit-fix
  B44+B46`. Standard loop steg 8 efter audit-fix-sprinten.
- `134df07` — `chore(workspace): perf hygiene + .generated externalization + viewser prettier setup`. Workspace-hygien-pass: utökad `.cursorignore`,
  ny `.cursorindexingignore` + `.editorconfig`, `.vscode/settings.json`
  får watcher-exclude + tsserver memory-bump + prettier-format-on-save,
  `scripts/build_site.py` skriver dev-preview-output till
  `../sajtbyggaren-output/.generated/SITE_ID` som default (override via
  `--generated-dir`/`SAJTBYGGAREN_GENERATED_DIR`), ny `builder-smoke`
  CI-job, `apps/viewser` får prettier 3.8.3 + plugin, `konversation.txt`
  untrackas. Inte en buggfix - se note i `docs/known-issues.md`
  "Notera (inte en bugg)" om den nya output-pathen.
- `de7fd7c` — `docs(focus): bump verified SHA after workspace hygiene pass`.
  Standard loop steg 8 efter workspace-hygien-passet.
- `ec11c41` — `docs: sync generated output path across docs`.
  Synkar `AGENTS.md`, `README.md` och `docs/architecture/builder-mvp.md`
  till nya defaulten `../sajtbyggaren-output/.generated/<siteId>/`.
- `10eb286` — `fix(dev-generate): thread follow-up mode into plan phase`.
  B48 stängd: `run_phase_plan()` tar `mode`/`project_id` och skickar dem
  till `produce_site_plan()`, så `generation-package.json` matchar
  `input.json` vid follow-up. Tester låser både CLI/dev-driver och
  Backoffice Playground-subprocessen.
- `5199d94` — `docs(focus): record B48 follow-up semantics landing`.
  Standard loop steg 8 efter B48-sprinten; dokumenterar PR #24 draft.
- `97ce7a8` — `chore(workspace): ignore PR review worktrees and sync
  build-runner comment`. `.review-*/` ignoreras i git/Cursor/VS Code
  watcher och `build-runner.ts`-kommentaren pekar på external
  generated preview directory.
- `8997596` — `docs(focus): bump verified SHA after workspace cleanup`.
  Standard loop steg 8 efter parallell-agentens workspace-cleanup.
- `c2d8632` — `feat(starters): add harmonized docs-base starter (PR #24)`.
  Squash-merge: ny `data/starters/docs-base/`-starter (Nextra 4.6.1 +
  Pagefind + MDX) + Steward-fixup för coachens fynd: ärlig sidebar-
  copy i `authoring.mdx`/`index.mdx`/starter-README + harden:ad
  ThemeToggle (useState lazy-init istället för DOM-mutation, plus
  aria-pressed + suppressHydrationWarning, lint-clean mot React 19/
  Next 16's `react-hooks/set-state-in-effect`-regel). `docs-base` är
  starter-underlag, inte aktiverad i `SCAFFOLD_TO_STARTER`. B49 öppen
  som följdsteg innan runtime-aktivering: page-map-driven sidebar
  istället för manuell `<aside>` i `layout.tsx`.
- `19c3564` — `docs(focus): post-PR #24 docs-base merge + B49 follow-up`.
  Standard loop steg 8 efter PR #24, plus B49 öppnad i
  `known-issues.md` och term-coverage allowlist för
  `ThemeToggle`/`Layout`/`B49`.
- `c073d486` — `docs: add cloud agent gotcha for /sajtbyggaren-output
  permissions (PR #25)`. Cloud-agent docs-PR: AGENTS.md får en
  gotcha för Cloud Agent VMs som visar att
  `/sajtbyggaren-output/` måste finnas med write-permissions för
  builder-tester (annars failar de tysta).
- `04fb92f` — `docs(agents): align Codex with Cursor rules`.
  `AGENTS.md` låser att Codex-IDE-agenten agerar Cursor-kompatibel
  repo-agent och följer `.cursor/BUGBOT.md` + `.cursor/rules/`, men
  fortsätter ändra governance-källorna i stället för genererade speglar.
- `9446200` — `docs(focus): record B45 contact route fix`.
  Standard loop steg 8 efter B45: current-focus/handoff synkar nästa
  konkreta uppgift till B49.
- `3178a82` — `chore(workspace): integrate operator + parallel-agent
  docs/settings touch`. Sopar upp tre filer som drev i working tree
  efter parallell-agent-aktivitet: `.cursor/settings.json` vercel-
  blocket borttaget (operator-toggle), `README.md` ADR-lista 0016-0020
  samt Sprint 3B+3B-next-status, `docs/agent-prompts.md` ny "Baseline för
  Codex-IDE"-sektion som kodifierar Scout-/Builder-/Steward-disciplin
  vid parallella agentpass.

Mainline-steward-pushar efter PR #21 (pure docs/governance):

- `0db29e6` — `.cursorignore` ignorerar nu hela `referens/`.
- `06a6047` — `docs/handoff.md` refreshad till post-PR-#20/#21-state.
- `09c53b0` — `check_term_coverage.py` allowlistar Bugbot/GitHub-
  statussträngar.
- `ebc9c09` — `current-focus.md` Queue/Next action efter RO-audit.
- `2aafa41` — agentflödet formaliseras (3 fasta roller +
  backup-N-disciplin + Scout som RO-bugggranskare).
- `504befc` — `agent-prompts.md` flyttad in i `docs/`.

Mainline-steward-pushar som också ligger på main:

- `bba8e36` - ny `bugbot-pr-loop`-regel (8-min poll + 10-iter
  fix-loop + nödläge-eskalering) under `governance/rules/`.
- `af8b337` - refresh av `docs/handoff.md` för main-as-default-
  policy + post-B13b-state.
- `61f9f69` - `reply-style`-regel (kort+koncis svenska med
  parens-förklaringar för dev-uttryck) under `governance/rules/`.
- `b4fe4a8` + `1c2227b` - `.gitignore`/`.cursorignore` pre-allokerar
  `packages/generation/build/` (B13a-destinationen) och blockar
  `.cursor/mcp.json`.

Branches städade 2026-05-13/14: feat/b20-step-2-mapping-flip raderad
lokalt + remote efter merge. 2026-05-14 skapades remote `backup-12`
från `9446200` som aktuell fallback, och de verifierat mergeade
PR-head-brancherna `cursor/env-setup-9fef`,
`cursor/docs-base-starter-harmonisering-98ec`,
`cursor/portfolio-base-starter-upps-ttning-bf2e` och
`cursor/backoffice-sp-r-lekplats-st-dning-d1d5` raderades från GitHub
eller bekräftades redan raderade. Backup-prune 2026-05-17 (efter
PR #29 + PR #30-merge): `backup-1` t.o.m. `backup-8` raderade från
origin på explicit operatörsdirektiv (~4 sprintar gamla, fallback-
behovet täckt av yngre backup-N). `backup-9` och `backup-10` har
aldrig existerat. Kvarvarande origin-fallbacks: `backup-11` t.o.m.
`backup-22` (12 st, äldsta från 2026-05-14). Inga lokala backup-N
finns kvar — alla raderades 2026-05-17 efter SHA-jämförelse mot
origin. Kvarvarande remote arbetsbrancher som inte ska raderas utan
separat beslut: `christopher-ui` och `frontend/christopher-import`
(PR #17 stängd utan merge, reference only). Stale PR-head-branch
`feat/demo-baseline-fix-1b-bug-sweep` (PR #28 mergad ovanpå) finns
också kvar på origin men är fri att radera i nästa Steward-städ.

## Current active sprint

Ingen pågående produktimplementation på `main`. **Keramik-/e-handel-pass stängd** (`d1fee90` + `6e5c33c` + `923f680` + `bfcad8d`): B101 (hero-CTA → /produkter), B102 (commerce bottom CTA shop-ton), B128 (planner-imperativ-läcka till /om-oss + Composer-2.5-hardening mot ledande-non-letter-prefix), dev-viewser `-Https`-flag för StackBlitz-kompatibel preview. **Aktivt spår: Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning, inte mer CLI-discovery-plumbing. Se "Next action".

Tidigare klara sprintar: B121 discovery-integration (PR #34–#37, `e3fa67b`),
starter dependency hardening (B108),
demo-baseline-fix 1E (B105 B106 B107),
demo-baseline-fix 1D (B99 B100 B103 B104),
demo-baseline-fix 1C (B88 B94 B95 B96), A-mini cleanup
(B51/B52/B54/B55 + B53 registrerad), Prompt-till-sajt MVP v1,
mini-sprinten som gjorde PromptBuilder till enda primära promptyta, follow-up
prompt versions, PR #23 backoffice trace/playground, PR #22 `portfolio-base`
starter, B48 follow-up-semantik, PR #24 `docs-base` starter, B45
kontakt-route-propagation, B50 route-hardening, Codex-IDE agent-parity-regeln,
mergead branch-cleanup, PR #26 produktkompass/agentläsordning,
orkestrator-playbooken för längre fleragentpass, StackBlitz preview
payload-hardening (ADR 0021 + B59 dokumentation), PR #27 follow-up
prompt versions (versionerade Project Input-snapshots, stabil
`projectId`/`version` i RunHistory, repo-`.venv` Python preferred),
PR #28 demo-baseline-fix 1B + bug-sweep, demo-baseline-fix 1A-hotfix.

## Next action - direktiv till nästa agent

**Viewser-overlay-E2E-Scout — verklig frontend-kvalitetsmätning.**

Keramik-/e-handel-passet är stängt (`bfcad8d`, B101+B102+B128). B121
discovery-integration är stängd. Bygg inte mer CLI-discovery-plumbing och
kör inte ännu en torr CLI-re-scout — coach 2026-05-19: nästa riktiga spår
är att gå genom **det faktiska Viewser-overlayflödet** (frontend wizard,
prompt, eventuell scrape/upload, build, preview) i 4-6 case och mäta
verklig output-kvalitet end-to-end.

Förslagna case (operatör väljer slutligt set):

1. **keramik e-handel** — verifierar B101/B102/B128 i live-output (ska
   nu visa "Shoppa nu" → /produkter, "Hör av dig för att beställa" som
   bottom-CTA, ingen Bygg-/planner-imperativ-läcka på /om-oss).
2. **vanligt tjänsteföretag med adress/kontakt** — verifierar
   `_pick_contact_route`-poängsättning och adress-till-stad-regex
   (skuggar B119/B120 i live-flödet).
3. **scrape-case** — operatör skriver in URL, scrape-runnern hämtar
   data, builder paketerar; verifierar scrape → discovery → build-kedjan.
4. **sköldpaddssoppa / conflict-case** — fri prompt säger A men wizard
   väljer B; mäter om Intent Guard-behovet (parkerat post-B121) blivit
   skarpare nu när keramik-fallet är fixat.
5. **"2 sidor"-case** — operatör skriver explicit sidantal i fri prompt;
   verifierar om planning faktiskt respekterar det eller om scaffold
   tvingar 4 routes.
6. **follow-up-case** — kör en initial build och sedan en följdprompt
   ("ändra färger/stil/text"); verifierar att v2 syns visuellt (B71
   markerades unverified av Scout-3).

Scout levererar: per-case-poäng /10, regressioner mot Scout-4-baseline
6.59/10, vilka av {Intent Guard, Page Intent, variant/style-selection,
B119/B120, Project DNA / semantic follow-up} som Builder bör prio:a först.
Beslutsregel (oförändrad): ≥7/10 OCH inget case <6.5 → Project DNA-sprint;
annars riktad bug-sweep på det case som dröjer.

StackBlitz/HTTPS för lokal preview hanteras nu via `.\scripts\dev-viewser.ps1 -Https`
(StackBlitz embed accepterar bara https://-origins). Variant-spåret
`feat/eight-scaffold-variants` (commit `4cd1058`) får först stabiliseras
av variant-promotion-PR/sprint innan det landar på main — coach-direktiv
i denna pass: ingen variant-promotion under Steward eller Scout.

**Föregående next action (Re-Verifierings-Scout 3 → keramik-pass) —
landad i `bfcad8d`:** Builder-pass stängde B101/B102/B128;
Composer-2.5 read-only-review hittade och hardenade en B128 bypass.

**Föregående next action (B121 PR D) — landad i `e3fa67b`:** CLI
baseline-smoke, rapport `docs/reports/b121-baseline-smoke.md`, B121
stängd i `known-issues.md`.

B59 är fortfarande parkerad — rör inte StackBlitz-fronten utan separat
beslut. B125 (browser-support-fallback) väntar på egen ADR innan
implementation och är produktblocker före extern kundyta.

Föregående cleanup-status:

- A-mini cleanup landad i `2ad01a2`. B51 (nav-label JSX-escape),
  B52 (`/spel`-dedupe), B54 (`.env*`-filter i StackBlitz upload),
  B55 (test_viewser_env_file gitignore-semantik) stängda med
  regression-tester. B53 (routes.schema.json) registrerad som queue.
- B50 stängd i `4940cbb` + Scout-follow-up `f787eb7`: route-hrefs
  går via `_route_href()`, saknad contact-route ger tydligt builder-fel,
  `render_home()` hittar inte längre på `/tjanster` när listing-route
  saknas och route paths avvisar protocol-relative URLs/dot-segments innan
  href/page-path skrivs.
- B45 klar i `6daee58`: `write_pages()` trådar scaffoldens contact-path
  till layout, home, services och products, och tester låser frånvaro av
  hardcoded `href="/kontakt"` i renderer-helpers.
- `AGENTS.md` innehåller Codex-IDE-regeln från `04fb92f`: Codex agerar
  Cursor-kompatibel repo-agent och följer `.cursor`-reglerna, men ändrar
  governance-källorna om en regel behöver uppdateras.
- PR #26 mergead i `1cba454`: produktkompassen i
  `docs/product-operating-context.md`. Den förtydligar att tekniskt
  intressanta sidospår parkeras om de inte hjälper kärnflödet.

Öppna B-IDs: B13a (arkitektur-flytt, kräver ADR), B47 (commerce-base
Shopify handles), B49 (docs-base page-map sidebar), B53 (routes.schema),
BO4-followup-cancel (Playground-cancellation). Ingen är blocker idag.

`portfolio-base` och `docs-base` är båda starter-underlag; ingen
`SCAFFOLD_TO_STARTER`-mappning eller real-codegen-scope är aktiverad
av #22 eller #24. Real codegen-scope är fortfarande `marketing-base`-only
per ADR 0017.

### Pre-push self-review checklist (lärt från B13b + B20)

Innan `git push origin main`:

- Jämför `git diff origin/main..HEAD --stat` rad-för-rad mot sprintens
  deklarerade scope. PR #19-lärdomen kvarstår: ändrade filer som inte
  nämns i scope är ofta scope-läckage.
- Sök efter samma sorts hardcoded-pattern som PR:n säger sig fixa.
  PR #19 fixade hardcoded `/tjanster`/`/om-oss`/`/kontakt`, men en
  ny `render_products` introducerade hardcoded `/kontakt` igen.
  Klassiskt blindspot på nya filer.
- Om printar/loggar har present tense ("Writing X"): placera dem
  FÖRE handlingen, inte efter. Operatör ska se vad som är i flygt
  vid crash.
- För varje ny renderer som tar `dossier`: kontrollera om den
  länkar någonstans och om den pathen ska komma från scaffolden
  (`_pick_*_route`) eller bara från dossiern.
- Om sprinten ändrar `SCAFFOLD_TO_STARTER` eller liknande policy-
  förankrad dict: skapa motsvarande ADR i samma ändringsrunda (lärdom från
  PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019).
- Om sprinten har en informativ post-merge-followup som inte blockerar
  push: lägg den i `docs/current-focus.md`, men håll blocker-listan ren från
  nice-to-have.

## Blocked items

Inga öppna PR-blockers just nu. PR #38 mergades 2026-05-19 (merge-commit
`48a6a22`, operatör-OK trots coach-direktiv — se "Last verified state"
för konsekvenser + B129 för teknisk skuld). PR #25 `cursor/env-setup-9fef`
är mergad i `c073d486` och PR-branchen är inte längre kvar på GitHub.

## Do not start yet

- StackBlitz-preview, Fly-deploy, PreviewRuntime - inte påbörjat.
- Nya starters utöver `marketing-base`, `commerce-base`, `portfolio-base`
  och `docs-base` (vendor).
- Större Builder UX-utbyggnad.
- B13a arkitektur-flytt (`scripts/build_site.py` produktlogik ->
  `packages/generation/build/`) - kvarstår som öppen post men kräver
  egen sprint + sannolikt egen ADR. Destinationen är pre-allokerad i
  `.gitignore` + `.cursorignore` (kommit `b4fe4a8`).
- PR #17 / `frontend/christopher-import` - behåll som design-/copy-
  referens only. Återöppna inte PR #17 och starta inte `apps/web` förrän
  Prompt-till-sajt MVP fungerar.

## Queue

1. **Viewser-overlay-E2E-Scout** - verklig frontend-kvalitetsmätning via
   det faktiska overlayflödet (wizard → prompt → eventuell scrape/upload
   → build → preview). 4-6 case inkl. keramik (verifierar B101/B102/B128
   live), tjänsteföretag med adress, scrape, sköldpaddssoppa-conflict,
   "2 sidor"-case och en follow-up. Se "Next action".
2. **B119/B120 kontakt/adress-kvalitet** - om Scout visar fel kontaktdata:
   prioritera `_pick_contact_route`-poängsättning och adress-till-stad-regex.
3. **Intent Guard + Page Intent** (om Scout-fynd bekräftar) - prompt-mot-
   wizard-mismatch-guard och pageIntent som faktiskt påverkar route-planen.
   Båda var parkerade post-B121 men aktualiseras om Scout visar att fri
   prompt och wizard fortfarande motsäger varandra.
4. **Capability/dossier gaps** - booking, contact-form, payments, FAQ ska
   inte bara varna utan ha Dossier-implementation när taxonomy flaggar dem.
5. **Project DNA / follow-up semantic merge** - om Viewser Overlay E2E
   Scout bekräftar ≥7/10 och inget case <6.5: gör `merge_followup_project_input`
   semantic så följdprompt mot tone/story/tagline ger synlig
   förändring i v2. Kan behöva egen ADR. B71 (PR #28-stängd, men
   markerad som unverified av re-Scout) bör verifieras i två-pass-
   test inom samma sprint.
6. **Variant-promotion-sprint** - PR #38 `feat/eight-scaffold-variants`
   (commit `4cd1058` + `0511299`, åtta gpt-5.4-genererade scaffold-
   varianter) mergades 2026-05-19 (merge-commit `48a6a22`) trots
   coach-direktiv. Variants ligger på `main` men är **dead code** i
   prod-flödet eftersom `_DEFAULT_VARIANT_BY_SCAFFOLD` i `plan.py`
   garanterar att `nordic-trust`/`clean-store` förblir defaults
   (medveten guard för att merge inte skulle introducera
   regressioner). Sprinten kvarstår för att leverera: (a) variant-
   selection-logik kopplad till dossier-rationale/wizard-val/
   operator-decision så de nya variants faktiskt kan aktiveras,
   (b) flytt av default-mapping från kod till governance-policy
   per B129 + ADR, (c) Re-Verifierings-pass mot fyra demo-prompter
   som bekräftar 0 regressions + att minst en av de nya variants
   kan väljas i prod-flödet. Branch `feat/eight-scaffold-variants`
   lämnad kvar på origin (delete-branch opt-out) tills sprinten
   avgör om den behövs för follow-up eller ska städas.
7. **Bug-sweep round 3 (om Scout fortsatt under tröskel)** -
   prioritera B67, B80, B81, B82, B84, B85, B86, B87 + B89-B93
   (extern reviewer-triage) + B97/B98 (låg-impact-rester) eller
   riktad fix på det case som dröjer.
8. **Live pipeline-matris i backoffice (operatörsförslag 2026-05-15
   sent på kvällen)** - visualisera `prompt → brief → plan → codegen
   → build → preview` som en live-uppdaterad matris i backoffice
   playground-vyn. Varje cell visar status (pending/running/ok/fail),
   senaste log-utdrag och artefakt-länk. Kombinerar befintlig
   playground-`subprocess.Popen`-runner (B04-stängning) med en
   pipeline-event-bus som `scripts/build_site.py` + `scripts/
   dev_generate.py` emitterar `phase.<name>.started/finished`-events
   till. Streamlit-realtidsuppdatering kräver `st.empty()`-pattern
   eller WebSocket-shim. Bästa demo-/granskningsverktyg vi kan bygga
   för dig (operatören). Egen sprint, ej blocker för re-Scout.
9. B49 (medel): page-map-driven sidebar för `docs-base`-startern; måste vara klar innan `course-education -> docs-base` aktiveras i `SCAFFOLD_TO_STARTER`.
10. **B59 follow-up** (parkerad - väntar på arkitekturbeslut): byte till lokal `next dev`-process som same-origin iframe på `localhost:NNNN` eller static StackBlitz-template. Ingen mer COOP/COEP-toggling. Bredare extern research om SDK-/Codeflow-/Teams-/MCP-ytan, kommersiell licens och browser-baseline ligger i [`docs/integrations/stackblitz-research.md`](integrations/stackblitz-research.md) som underlag inför arkitekturbeslutet.
11. B53 (låg): `governance/schemas/routes.schema.json` för scaffold-routes-kontraktet.
12. B47 (låg): commerce-base Shopify-handles dokumenteras eller får fallback.
13. B13a arkitektur-flytt (egen sprint, kräver ADR).
14. `write_pages` icon-bibliotek-agnostisk refactor.
15. Cancellation-followup (låg): riktig cancellation/background-jobb i playground-vyn om operatören behöver avbryta redan startade körningar.

**Vänta med ny/sista starter** tills minst följande är sant: marketing-base real codegen stabil, 4 demo-sajter kan byggas (minst 3/4), follow-up versions funkar, build-fail från fri prompt är förstådda, enkelt scorecard finns. Annars blir ny starter mer yta att felsöka utan att stärka kärnflödet.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → skapa `backup-N` → Builder/Steward jobbar på
`main` → Scout RO-review före push → vid push-OK och clean tree får Builder
pusha direkt → Steward post-push-verifierar → uppdatera denna fil vid faktisk
fokus-/handoff-förändring → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
