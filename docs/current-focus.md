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

Last verified state: `cb5c837548125bd94740f19e3b4a7acfa89b44cf`
(2026-05-25, **PR #70 Sprintvakt V1 koordineringsserver mergad ovanpå
parallell-team-uppsättning och restaurant-hospitality Week 1**) — `main`
är grön efter squash-merge. Sprintvakt V1 ger lokal filbaserad workboard
(`docs/workboard.json`), gap-modell (`docs/gaps/`), collision-checker
(`scripts/sprintvakt_check.py`) och dependency-free MCP-server
(`tooling/sprintvakt_mcp/`) så Jakob (backend, `jakob-be`) och Christopher
(UI/frontend, `christopher-ui`) kan reservera path scopes utan att två
agenter ändrar samma fil. `python scripts/sprintvakt_check.py` ger
`Sprintvakt check: OK` och 14 sprintvakt-tester är gröna.

Sedan c0b59fbe (PR #60) har följande mergats till `main`, i ordning:

- `a32152d` PR #61 — team parallel workflow + ownership map (parallell-team-flödets grund).
- `7240fcd` PR #62 — viewser/christopher-ui builder-workflow-integration.
- `f9312ec` PR #63 — wizard-directives `useCustomColors` + `scaffoldHint` (backend-Gap 1 + 3 stängda).
- `89f14a1` PR #64 — branch-naming-konventioner för parallellt teamarbete (permanenta arbets-branches `jakob-be` + `christopher-ui` dokumenterade i `docs/ownership-map.md`).
- `d709864` PR #66 — `sourceUrl`-asset-uploads med stream-safe fetch (PR #65 stängd och supersededad).
- `7e900d2` PR #67 — AI bug review-workflow-steg i CI (`gpt-5.4` + repo-specifik prompt).
- `839d0c8` PR #68 — restaurant-hospitality scaffold + 11 soft dossiers + 14 variants (Week 1 declarative expansion). Inkluderade två `[scope-leak]`-commits från Christopher i `plan.py` (`SCAFFOLD_TO_STARTER` + `_DEFAULT_VARIANT_BY_SCAFFOLD`) och `resolve.py` (`_PAGE_TO_CAPABILITY` + `_CAPABILITY_ALIASES`) — accepterade som operator-approved engångsundantag, inte permanent norm.
- `cb5c837` PR #70 — Sprintvakt V1 koordineringsserver + lokal MCP-server (path-overlap-bug i `paths_overlap` verifierad fixad i fix-commit `419d3f1` innan merge).

Pågående parallellt: PR #69 (`docs: add product north star runtime ladder`)
är fortfarande öppen draft mot `main` med grön CI — docs-only, väntar på
operatörens grönt ljus.

**Direkt nästa fokus:** Sprintvakten är nu användbar för path-reservation
och gap-koordination. Vänta på operatörens nästa sprintval, men möjliga
riktningar:

- **Path B (section-driven renderer i `scripts/build_site.py:write_pages`)** är dokumenterad i `docs/scaffold-runtime-extension-needed.md` och är nästa stora backend-jobb (~20-26h). Den låser upp `restaurant-hospitality` fullt + ger nollkostnad för 4 framtida scaffolds. Kräver explicit operator-OK innan start eftersom estimatet är stort och bör vara dedikerad session.
- **Backend-Gap 4 + 5** från `docs/backend-handoff-2026-05-22.md` är öppna men ej akuta.
- **Sprintvakt V1.1 follow-up:** klart på `jakob-be` (`593735f` Fynd 2 reservedPaths dedupe, `db0b565` Fynd 1 file-only gap support, `90df708` Fynd 3 editable install). 14 → 18 sprintvakt-tester gröna; `pip install -e .` registrerar `tooling`-paketet via ADR 0029. Väntar på samlad PR från `jakob-be` → `main` när operatören är klar med kvällens batch.
- **CI-integration av `scripts/sprintvakt_check.py`** — klart i `e0af0bd` + `1ed702b` (push-trigger split, AI-bug-review-jobb isolerat, `tests/test_github_workflow.py` regression-test). Collision-checken är nu merge-grindad i GitHub Actions.
- **`activate_gap` + `complete_gap` MCP-tools (Sprintvakt V1.2)** — klart i `bd8fc03`. Workboard-state-transitions går nu genom MCP med samma dryRun/confirm-säkerhet som `create_gap`.
- **Sprintvakt V1.2.1 (PR #75-review-svar)** — status-enum-validering (`queued`/`active`/`in-review`/`completed`) + collision-recheck i `activate_gap` så ett queued gap inte kan aktiveras om paths har fått nya röda krockar sedan det köades. 22 → 25 sprintvakt-tester.
- **PR #75 (`jakob-be` → `main`)** öppen med hela kvällens batch. Squash-merge när operatören är redo. Christopher har redan mergat PR #71 (Front 1-4 + wizard minimalism) ovanpå main; #75 mergeas ovanpå det.
- **`GAP-backend-build-trace-endpoint`** queued av Christopher i workboarden — backend-spec för Live Build Sync: `GET /api/runs/[runId]/trace`, `GET /api/runs` med pending, `POST /api/prompt` med `baseRunId`. Min nästa backend-runda efter PR #75-merge.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project
DNA V2 tills en sprint är formellt vald.

Startprompt för nya agenter:
[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md).
Föregående produkt-läge:

Föregående verified state: `c0b59fbe53a4e081cc8f09f22173a7050cb35b66`
(2026-05-22, PR #60 Starter Candidate Auditor v1 mergad ovanpå PR #59
Backoffice Asset Graph) — produkt-/kodläget innehöll bara den read-only
Starter Candidate Auditorn (`scripts/audit_starter_candidate.py`), dess
tester och term-coverage-uppdateringen. Intern starter-guard mot
`data/starters/marketing-base` gav `classification=blocked`. PR #59:s
read-only Asset Graph fanns i Backoffice efter Discovery/SNI och före
Konsekvensvy. Inga runtime mappings, policies, starters, scaffolds,
Dossiers, planning/codegen-ytor eller B125-filer ändrades. **Direkt nästa
fokus** vid bumpen var att vänta på operatörens nästa sprintval (B125
preview-fallback eller annat smalt produktspår) — istället landade
parallell-team-uppsättningen (PR #61, #64), Viewser-integration (PR #62),
wizard-directives + restaurant-hospitality (PR #63, #68), AI-bug-review
(PR #67) och Sprintvakt V1 (PR #70) som backend-spår.
Föregående produkt-läge:

Föregående verified state: `78baaa1` (2026-05-22, **Dev Artifact Cleanup /
Eval Retention v1 efter mixed follow-up tone guard**) — produkt-/kodläget
innehåller `a54e06f` plus `scripts/cleanup_dev_artifacts.py`, en samlad
dry-run-first cleanup för lokala mini-evals, generated previews och
Python-cache. Föregående produkt-läge:

Föregående verified state: `a54e06f` (2026-05-22, **mixed follow-up tone guard
efter naprapat mini-eval bug-sweep**) — produkt-/kodläget innehåller
naprapat-fixen plus `a54e06f` som låter `Lägg till FAQ och gör tonen mer
premium` behålla additiv merge samtidigt som den patchar `tone`, men
fortsatt håller `lägg till en lugnare sida om vår historia` konservativ.
Ny full mini-eval är **4/4 grön**:
`C:\Users\jakem\Desktop\sajtbyggaren-output\.evals\20260522T030947Z-mini-eval\mini-eval-report.md`.
PR #58/B125 decision-spår är mergat i `3418cdb`; nästa faktiska steg är
att läsa B125-ADR/rapporten och välja om preview-fallback ska bli nästa
implementation, eller om den gröna mini-evalen motiverar annat
produktspår. Dev Artifact Cleanup / Eval Retention v1 finns nu via
`scripts/cleanup_dev_artifacts.py` (dry-run default, `--apply` krävs);
mini-eval-runs under `SAJTBYGGAREN_EVALS_DIR` eller
`../sajtbyggaren-output/.evals` kan rensas säkert med
`python scripts/cleanup_dev_artifacts.py --evals --keep 10 --apply`.
Föregående produkt-läge:

Föregående verified state: `991f152` (2026-05-22, **naprapat mini-eval
bug-sweep efter Mini-eval runner v1**) — produkt-/kodläget innehåller
`eb5a81d` (`fix(builder): propagate brand and tone tokens`), `defd196`
(`chore(eval): add isolated mini eval runner`), `25a435d`
(`fix(builder): harden follow-up intent handling`) och naprapat-fixen
som lär follow-up-intent att förstå `lugnare`/`förtroendeingivande`.
B139/B140 är stängda:
giltig `brand.primaryColorHex` / `brand.accentColorHex` skriver nu
renderade CSS-token `--primary` / `--accent`, whitelistad `tone.primary`
kan mappa till tokens när explicit hex saknas, ogiltig hex ger trace-
warning, och foreground-tokens räknas om för kontrast. Bug-räkning efter
merge: **24 aktiva, 0 misplaced, 5 unknown, 107 stängda**. Efterföljande
dev-tooling-spår lägger `scripts/mini_eval.py`, en isolerad Mini-eval
runner v1 som kan köras i separat terminal mot
`SAJTBYGGAREN_EVALS_DIR`/`../sajtbyggaren-output/.evals` utan att skriva
till canonical `data/runs/`. Under smoke av runnern hittades och fixades
även en CSS-kaskadregression: Sajtbyggarens token-block appendas nu sist i
`globals.css` så starter-defaults inte kan vinna över overrides. **Direkt nästa fokus:** kör mini-evalen över
alla fyra baseline-case och använd rapporten för att välja mellan B125
preview-fallback eller nästa produktspår. Vänta fortsatt med embeddings,
SNI-runtime, variant-promotion och nya starters tills mini-evalen visar
stabilare kvalitet. Reviewfynd efter PR #56 är delvis åtgärdade:
additiva `lägg till ... historia/story`-prompter patchar inte längre
`company.story`, och `clarify` stoppar versionering i stället för att
skapa ny run. Blandade multi-intent-prompter är fortsatt V2-/kvalitets-
scope. Ny full mini-eval efter naprapat-fixen är **4/4 grön**:
`C:\Users\jakem\Desktop\sajtbyggaren-output\.evals\20260522T030947Z-mini-eval\mini-eval-report.md`.
Naprapat v2 ändrar nu `tone.primary` till `lugn` och `tone.secondary`
till `["förtroendeingivande"]` utan story/tagline- eller CSS-token-
ändring. Blandade prompts får bara släppa igenom additiv + tone när det
finns explicit tone-scope (`ton`, `tone`, `känsla`, etc.); `lägg till en
lugnare sida om vår historia` är fortsatt konservativ. **Direkt nästa fokus:** använd den gröna eval-rapporten för att
välja mellan B125 preview-fallback och nästa produktspår; vänta fortsatt
med embeddings, SNI-runtime, variant-promotion och nya starters.
Föregående produkt-läge:

Föregående verified state: `25a435d` (2026-05-22, **follow-up intent
hardening efter Mini-eval runner v1**) — produkt-/kodläget var `25a435d`
(`fix(builder): harden follow-up intent handling`). Föregående produkt-läge:

Föregående verified state: `defd196` (2026-05-22, **isolerad Mini-eval
runner v1 efter B139/B140**) — produkt-/kod-läget var `defd196`
(`chore(eval): add isolated mini eval runner`). Föregående produkt-läge:

Föregående verified state: `eb5a81d` (2026-05-22, **B139/B140 tone/brand
token propagation V1 mergad via PR #57**) — produkt-/kod-läget var
`eb5a81d` (`fix(builder): propagate brand and tone tokens`). Föregående
produkt-läge:

Föregående verified state: `aef5825` (2026-05-22, **Project DNA semantic
follow-up V1 mergad via PR #56**) — produkt-/kod-läget var `aef5825`
(`feat(builder): add Project DNA semantic follow-up`). B71 är stängd
med faktisk v1 → v2-effekt: tydliga följdprompter kan deterministiskt
ändra `company.story`, `company.tagline` och `tone`, medan additiva/no-
change-prompter håller semantiska fält byte-stabila. `projectDna` skrivs
i befintlig prompt-input-meta-sidecar; full `data/projects/<projectId>/
dna.json`-lagring är fortsatt V2-scope enligt ADR 0027. Bug-räkning efter
merge: **26 aktiva, 0 misplaced, 5 unknown, 105 stängda**. Föregående
produkt-läge:

Föregående verified state: `465b8fa` (2026-05-22, **rules_sync separator-
order-fix ovanpå link-rewrite-passet**) — produkt-/kod-läget var
`465b8fa` (`fix(rules-sync): pick earliest separator when splitting
path from query/anchor`). External reviewer-feedback om separator-
iterationsordningen i `_rewrite_link_target` bekräftad: `file.md?foo=
bar#anchor` plockade `#` först och missade `.md`-rewriten. Bytte till
earliest-index-sökning + 4 nya regression-tester. Ingen källfil använder
mönstret idag så rules_sync är fortsatt i synk och ingen mirror
regenererades. Föregående produkt-läge:

Föregående verified state: `919d564` (2026-05-22, **rules_sync skriver om
relativa länkar för .cursor/rules-speglarna ovanpå Backoffice SNI-
diagnostik-utökningen**) — produkt-/kod-läget var `919d564`
(`fix(rules-sync): rewrite relative links so .cursor/rules mirrors
resolve`). `scripts/rules_sync.py` skriver nu automatiskt om
``../policies/``/``../schemas/``/``../decisions/``-länkar till
``../../governance/...``-form och sibling ``.md``-extensioner till
``.mdc`` när speglarna genereras. Sju spegelfiler regenererades; ingen
ändring i `governance/rules/`-källan. 16 nya regression-tester i
`tests/test_rules_sync.py` (inkl. en scanner som faljar om någon ny
``(../policies/`` smyger in i mirror-filerna). Operator-rapporterad
markdown-linter-varning (`link.no-such-file` på
`.cursor/rules/always-swedish.mdc:37`) är därmed löst för alla
mirror-filer, inte bara den specifika raden. Föregående produkt-läge:

Föregående verified state: `5114fb2` (2026-05-22, **Backoffice SNI-diagnostik
utökad med coverage gaps + confidence-breakdown + parent-chain ovanpå
SNI-followup-tooling**) — produkt-/kod-läget var `5114fb2`
(`feat(backoffice): expand SNI diagnostics with coverage gaps and parent
chain`). Föregående följdcommits 2026-05-22: `1150424` operator-finalized
rules + workspace, `f137f92` SNI-followup-tooling, `b75b664`/`369ed48`/
`06cdc51` Steward-bumpar, `e822a2c` PR #55-merge. Nya backoffice-helpers:
`confidence_breakdown` (high/medium/low/other-räkning per policyrad),
`taxonomy_coverage_gaps` (Discovery Taxonomy-kategorier utan SNI-
mappning — landing/other/blog/business/food/music i V1), och
`lookup_parent_chain` (avdelning → huvudgrupp → grupp → undergrupp →
detaljgrupp; syntetiska prefix som `56100` trunkeras till närmaste
verkliga kod `561`). Backoffice-vyn under Building Blocks/Kontrollplan
visar nu confidence-metrics, en expander med taxonomy-täckningsluckor
och parent-chain ovanför operator-lookup-resultatet. 19 nya regression-
tester. Cleanup: `../sajtbyggaren-pr55/` worktree borttagen, lokal
`fix/viewser-followup-stale-state`-branch raderad. `backup-bra-änä` är
kvar (åäö-namnet bryter mot `branch-discipline.md` men backup-branches
får bara operatören radera). Föregående produktlägespunkt:

Föregående verified state: `1150424` (2026-05-22, **SNI-followup tooling +
operator-finalized rule additions committade ovanpå PR #55-mergen**) —
produkt-/kod-/rule-läget var `1150424` (`chore(rules): finalize always-
swedish additions and workspace autosave`). Föregående commits i samma
pass: `e822a2c` (PR #55 merge: viewser run-following + artefakt-panel),
`06cdc51` (Steward-bump till `e822a2c`), `369ed48` (PR #56 cloud-agent-
spår-flagging), `b75b664` (Steward-tail-bump), `f137f92` (`feat(taxonomy):
SNI follow-up tooling + cursor/git ignore consolidation` — 5 filer / +446:
`scripts/lookup_sni.py` CLI med code/text/section/level/stats-
subkommandon + `--json`, `data/taxonomies/sni/README.md` med rebuild-
flöde + konsumentlista, `.cursorindexingignore` blockerar SNI JSON-
indexering, `.cursorignore` speglar Read-blockeringar, `.gitignore`
+ `data/taxonomies/**/*.xlsx` säkerhetsbälte plus `.cursor/tmp_*` +
`eval-tmp/`-konsolidering), `1150424` (operator-finalized rules: två
nya stycken i `governance/rules/always-swedish.md` om engelsk debug-
narration och unicode_escape + workspace `files.autoSave: afterDelay`). PR55-agenten stängde tre distinkta viewser-fixar (stale-closure
i `applyRunsData`, `setBundle(null)`-cleanup i Run Details, ny
`runSiteIdUnknown`-prop som blockerar follow-up vid `siteId === "unknown"`)
i 6 filer (113 ins / 8 del). Reviewerns observation att den
ApplyRunsContext-typ PR-bodyn nämnde aldrig blev en *named type* stämmer
— mergens andra commit "avoid governance term for run context" gjorde
ctx inline (`ctx?: { selectedRunId: string | null; selectedSiteId: string }`).
3 nya regression-tester i `tests/test_viewser_files.py` låser fix-
kontrakten via regex-/substring-match. Lokala operatör- och PR55-agent-
tweaks (`.cursorignore`/`.cursorindexingignore`/`.gitignore` med tightare
operatör-scratch-ignores + `data/taxonomies/**/*.xlsx` säkerhetsbälte +
SNI JSON-indexering blockerad, `data/taxonomies/sni/README.md`,
`scripts/lookup_sni.py` CLI med `--json`-stöd, `governance/rules/
always-swedish.md`-tillägg om engelska debug-narration och unicode_escape,
`sajtbyggaren.code-workspace` autoSave-toggle) väntar fortfarande på
operatörens explicita beslut att stagea — flaggade i mid-session-
handoffen från PR55-agenten. Bug-räkning oförändrad: **27 aktiva, 0
misplaced, 5 unknown, 104 stängda**. **Direkt nästa orkestrator-fokus:**
Project DNA / semantic follow-up med B71 som primärt ankare drivs av
separat cloud agent (operatör-notis 2026-05-22). Lokal orchestrator
håller main stabil tills cloud-agentens DNA-spår landar eller blockas
av deras review. Inga SNI-runtime-taxonomi/Viewser-overlay-integration,
embeddings, nya starters, variant-promotion eller B59/B125-preview-
fallback ska startas parallellt med cloud-agentens spår. Tidigare
paragraf:

Föregående verified state: `f40564e` (2026-05-22, **SNI 2025 import +
Discovery-map-diagnostik sidospår + PR #55-handoff-notis**) — produkt-/
kodläget var `2e274ac` (`feat(governance): add SNI 2025 import + discovery
map diagnostics`); efterföljande docs-bumpar `bf8d6c2` och `f40564e`
registrerar landningen i Steward + PR #55-parallell-agent-spåret.
`backup-42` skapades från synkad `main`-`1edb089` + pushad till origin
innan sprintarbetet. Sprinten är en read-only/diagnostisk
sidospår-leverans: ny extractor `scripts/extract_sni_2025.py` läser
SCB:s SNI 2025-källfil (stdlib `zipfile` + `xml.etree`, ingen ny pip-
dependency) och skriver deterministisk JSON-spegel till
`data/taxonomies/sni/sni-2025.v1.json` (1882 SNI-poster: 22 avdelningar,
87 huvudgrupper, 287 grupper, 651 undergrupper, 835 detaljgrupper).
Excel-källan committas inte; den behandlas som transient operatörsinput.
Ny policy `governance/policies/sni-discovery-map.v1.json` (21 division-
mappningar + 18 grupp-overrides) mappar SNI-prefix till kandidat
`wizardCategoryId` i Discovery Taxonomy; nytt schema
`governance/schemas/sni-discovery-map.schema.json` förbjuder explicit
`starterId`/`scaffoldId`/`variantId`/`dossierId`/`selectedDossiers`-fält
så SNI inte kan kringgå Discovery Taxonomy. Ny resolver-helper
`packages/generation/discovery/sni_map.py` (`normalize_sni_code`,
`load_sni_discovery_map`, `resolve_sni_discovery_category`) returnerar
`SniMatch` utan starter/scaffold/variant/dossier-direktval; trasig eller
okänd kod ger `matchedLevel="unknown"` utan exception. Ny Backoffice-
sektion under Building Blocks/Kontrollplan visar SNI → wizardCategoryId
→ Discovery Taxonomy-kedjan read-only med ett operator-lookup-fält
(`backoffice/sni_diagnostics.py` + sektion i
`backoffice/views/building_blocks.py`). V1 har **ingen runtime-
konsumtion**: Viewser-overlay, Discovery Resolver, generation, planning
och codegen är oförändrade. Tester: 81 nya regression-tester i
`tests/test_sni_extraction.py`, `tests/test_sni_discovery_map.py` och
`tests/test_backoffice_sni_diagnostics.py` täcker extraktorns
determinism, `--check`-drift-detektion, schemats förbjudna direktvals-
fält, resolverns testfall (`43/432/43210` → construction, `56/561/56100`
→ restaurant, `62/620/62010` → tech, `691` legal, `692` accounting,
`742` photo, `931` fitness, `932` event, `953` auto, `962` salon,
trasiga/okända koder → unknown utan exception) och Backoffice-
diagnostikens read-only-radbyggare. Guards efter sprinten: `ruff check .`
0 findings, `governance_validate` 18 policies OK (18 från 17), `rules_sync
--check` OK, `check_term_coverage --strict` OK efter allowlist-tillägg
för SNI-helper-symboler + stdlib zip/XML-typer, full `pytest tests/ -q`
gröna (3 skippade E2E). Bug-räkning oförändrad: **27 aktiva, 0 misplaced,
5 unknown, 104 stängda** — SNI-sprinten introducerar ingen ny B-ID. Mid-
session-fenomen: parallell-agent skapade branchen
`fix/viewser-followup-stale-state` (`042319c`) och min shell-context
växlade tillfälligt dit; jag växlade tillbaka till `main` utan att röra
deras filer. `.gitignore` har lokala operatör-tillägg
(`.cursor/tmp_*`, `eval-tmp/`) som inte committades i denna sprint —
ägs av annat spår. **Direkt nästa orkestrator-fokus:** Project DNA /
semantic follow-up med B71 som primärt ankare. Börja read-only: kartlägg
`scripts/prompt_to_project_input.py::merge_followup_project_input`,
aktuella Project Input-versioner och vilka artefakter som ska visa v2-
skillnaden; avgör om ADR behövs innan Builder-sprint. SNI är klar för
sin V1-roll (read-only diagnostik); SNI-runtime-taxonomi/Viewser-overlay-
integration är **out of scope** tills Project DNA är stängt. Tidigare
paragraf:

Last verified state: `2057241` (2026-05-22, **Steward-docs efter PR #54
och README/handoff-synk**) - produkt-/kodläget som verifierades är
`9225244` (`fix(backoffice): make wizard diagnostic wizard-truth-driven
(#54)`); efterföljande docs-bumpar `e84d2fb` och `2057241` registrerar
merge, live-eval och README-status.
PR #54 gjorde Backoffice-vyn "Wizardfält -> generation" wizard-driven
i stället för backend-map-driven: alla 15 `MUST_HAVE_OPTIONS` och alla
8 `CTA_OPTIONS` får nu egna rader. `Priser och paket` visas som
deterministisk route-emission till `/priser`; `FAQ`, `Bildgalleri`,
`Karta / Hitta hit`, `Vårt team` och `Portfolio / Case` visas som
supported routes för `local-service-business`; `Startsida / Hero`,
`Om oss / Om mig` och `Kontaktformulär` visas som scaffold-default/
basroute; `Bokning online`, `Blogg / Nyheter` och `Nyhetsbrev` visas
som ärliga warning-only/deferred gaps; CTA-valet `Läs mer` visas som
`no-known-destination` i stället för att döljas. SCOUT54 gav
`OK_TO_MERGE`, CI var grön och PR:n är mergad. Live Viewser-overlay
Scout mot B132-route-emissionen bekräftade att alla valda supported
must-have-routes hamnar i Run Details, `site-plan.json` och genererade
app-routes för elektriker Malmö, frisör Göteborg, naprapat Stockholm
och sköldpaddssoppa. **Viktig kvarvarande blocker:** StackBlitz-iframe
visade `Unable to run Embedded Project` på alla live-runs, så Scout
kunde inte visuellt klicka igenom previewn; verifieringen byggde därför
på Run Details + artefakter + `scripts/verify_run.py --json`. Detta är
ett känt B59/B125-previewspår och en launch-blocker, men det blockerar
inte nästa interna produktspår. Icke-blockerande UI-risk från Scout:
Run Details-panelen kan bli stale när operatören byter äldre run i
listan; verifieringsscriptet visade korrekt artefaktdata.

Tidigare paragraf:

Last verified state: `63d7264` (2026-05-21, **B132 follow-up:
wizard-route emission för local-service-business ovanpå Backoffice
diagnostik `0ff2a54`**) — lokal `main` och `origin/main` är synkade
på `63d7264` (`feat(builder): emit wizard mustHave routes for
local-service-business`). Sprinten tar
`pageIntentWarnings`-spåret från "warning-only observability" till
faktisk route-emission när `wizardMustHave` innehåller pages som
kan byggas deterministiskt: `FAQ` → `/faq`, `Bildgalleri` →
`/galleri`, `Karta / Hitta hit` → `/karta`, `Vårt team` → `/team`,
`Priser och paket` → `/priser`, `Portfolio / Case` → `/portfolio`.
Bara `local-service-business` är opt-in i v1 via
`_WIZARD_ROUTE_SCAFFOLDS` i `packages/generation/planning/plan.py`;
ecommerce-lite och framtida scaffolds får warnings tills deras
renderer-set granskats. `Bokning online` håller warning-shape men
får specifik `reason` ("requires a real booking integration; ...")
så Backoffice/Run Details kan skilja "integration saknas" från
"scaffold har ingen sådan yta". Render-helpers i `scripts/build_site.py`
läser dossier-data (services, contact, location, gallery, team)
och faller tillbaka på ärlig svensk copy när data saknas — ingen
falsk booking-, betal-, auth- eller nyhetsbrev-integration emitteras.
`_nav_items_from_scaffold` infogar wizard-extras före kontakt-routen
i header/footer, `_extract_wizard_extra_routes` läser
`site_plan["routePlan"]` så routePlan blir single source of truth
för dispatch. `_trim_route_plan` rör inte wizard-extras (operatörens
explicita val vinner över `brief.pageCount`-trim av scaffold-defaults).
Mini-eval (CLI, mock-väg, `--skip-build`) på fyra cases:
elektriker Malmö (`FAQ`, `Portfolio / Case` → 6 routes, 0 warnings),
frisör Göteborg (`Bokning online`, `Priser och paket`, `Bildgalleri`,
`Karta / Hitta hit` → 7 routes, 1 warning för `Bokning online`),
naprapat Stockholm (`Vårt team`, `Bokning online`, `Karta / Hitta hit`,
`FAQ` → 7 routes, 1 warning), sköldpaddssoppa (`FAQ` → 5 routes,
0 warnings). Sköldpaddssoppa-spåret: B137 + B138 + Intent Guard
oförändrade — `_trim_route_plan` + tagline-läckage-skydd + Intent
Guard light fortsätter funka som tidigare (sköldpaddssoppa-routePlan
i denna eval blev `[/, /tjanster, /om-oss, /faq, /kontakt]` eftersom
mock-brief inte returnerade `pageCount: 2`; den live-LLM-vägen
trimmar fortfarande korrekt när `pageCount` fångas). `backup-41`
skapad från synkad `main`-`0ff2a54` + pushad till origin innan
sprintarbetet. Tester/guards: `ruff check .` (0 findings),
`governance_validate` (17 OK), `rules_sync --check` (sync),
`check_term_coverage --strict` (inga okända efter allowlist-tillägg
för `.cursor/tmp_*` operatör-lokala filer + 6 nya Next.js
page-komponentnamn `FaqPage`/`GalleryPage`/`MapPage`/`PortfolioPage`/
`PricingPage`/`TeamPage`), `pytest tests/ -q` (alla passerar; 3
skippade E2E). 24 nya regression-tester (8 i `test_page_intent.py`
uppdaterade + reformulerade kontrakt, 16 nya i
`test_wizard_route_emission.py` som täcker plan-helpern,
render-funktionerna, write_pages-dispatch och nav-utvidgningen).
Bug-räkning oförändrad: **27 aktiva, 0 misplaced, 5 unknown, 104
stängda** — sprinten introducerar ingen ny B-ID utan utvidgar
B132-spåret från warning-only till faktisk route-emission. **Direkt
nästa orkestrator-fokus:** kör Scout RO-review på diffen + ny mini-eval
i Viewser-overlayflödet (sköldpaddssoppa + elektriker/frisör/naprapat)
för att verifiera att de emitterade routes faktiskt landar i StackBlitz
preview och att Backoffice Building Blocks-vyn (`650c518`) speglar de
nya routes-emissionsvägarna korrekt. `Bokning online` är medvetet
parkerad till framtida sprint med riktig booking-integration. Tidigare
paragraf:

Last verified state: `650c518` (2026-05-21, **Backoffice read-only
wizardfält → generation-diagnostik ovanpå B144 + B143 + B141**) — lokal
`main` och `origin/main` är synkade på `650c518`
(`feat(backoffice): add wizard propagation diagnostics`). Ny Building
Blocks/Kontrollplan-del visar kända wizardfält, destination,
`status` och `propagationLevel` utan att ändra runtime, policies eller
schemas. Vyn skiljer deterministiska mappingar från prompt-signaler,
Project Input-only/downstream-gap och diagnostic-only, och synliggör
Capability Map-gap/unknowns samt taxonomy planned/fallback. `backup-41`
finns på origin från pre-sprint-läget. Tester/guards: `ruff check .`,
`governance_validate`, `rules_sync --check`, `check_term_coverage --strict`,
fokuserad backoffice/discovery-svit och full `pytest tests/ -q` gröna
efter att `/sajtbyggaren-output` fick write-permissions enligt AGENTS.md
gotcha. Bug-räkning oförändrad: **27 aktiva, 0 misplaced, 5 unknown, 104
stängda**. **Direkt nästa orkestrator-fokus kvarstår:** kör
Viewser-overlay-mini-eval med verkligt UI-flöde och `scripts/verify_run.py`
där artefakter behöver kontrolleras. Tidigare paragraf:

Last verified state: `5dfa2c7` (2026-05-21, **post-merge Steward-sync efter
B144 + B143 + B141**) — lokal `main` och `origin/main` är synkade på
`5dfa2c7` (`fix(codegen): close B141 brief-ref summary contract (#52)`).
Sedan `bb76c2a` har två PR-spår mergats och ett dåligt spår stängts:
`d3b77ff` (**PR #53 / B143**) utökar befintlig
`_INTENT_GUARD_CONFLICTS` i `scripts/build_site.py` med engelska
business-type-slugs utan ny parallell funktion och utan warning-shape-byte;
`5dfa2c7` (**PR #52 / B141**) gör att codegen-summaryn laddar faktisk
`site-brief.json` via `siteBriefRef` i generation-package-kontraktet.
B144 var redan inne: Run Details renderar nu `pageCountWarning`,
`intentGuardWarnings` och `pageIntentWarnings` från `site-plan.json`.
PR #51 stängdes utan merge och ska inte återupplivas. Inga öppna PRs.
Bug-räkning: **27 aktiva, 0 misplaced, 5 unknown, 104 stängda**. B143 är
en taktisk ord-/slugmatchningsfix, inte embeddings eller ny taxonomi;
framtida Intent Guard v2 bör ägas av governance/backoffice med tydliga
bransch-buckets, men startas först efter ny mini-eval. **Direkt nästa
orkestrator-fokus:** kör Viewser-overlay-mini-eval med verkligt UI-flöde
och `scripts/verify_run.py` där artefakter behöver kontrolleras. Tidigare
paragraf:

Last verified state: `bb76c2a` (2026-05-21, **B144 push + PR #53/#52 status bump; Steward-docs-syncen är inom bump tolerance**) — `origin/main` har `bb76c2a` (`docs(steward): close B144 and stop PR51 path`) ovanpå `aee67d7` (`fix(viewser): close B144 - render site-plan warnings`). B144 är Scout-RO-godkänd och stängd: Run Details läser nu `sitePlan.pageCountWarning`, `sitePlan.intentGuardWarnings` och `sitePlan.pageIntentWarnings` från `site-plan.json` och renderar ett amber-block `data-testid="site-plan-warnings"` med svensk non-blocking-copy; source-locken `tests/test_viewser_files.py::test_run_details_panel_renders_site_plan_warnings` låser canonical källa + UI-yta. Bug-räkning efter B144: **29 aktiva, 0 misplaced, 5 unknown, 102 stängda**. **B143 är fortfarande öppen. PR #51 (`cursor/b143-intent-guard-slugs-5156`) ska inte mergas:** Scout RO-review 2026-05-21 gav verdict stop eftersom branchen bygger på pre-Intent-Guard-main, introducerar parallell `_intent_guard_warnings`/`_INTENT_GUARD_CONFLICTS`, får dead code efter merge, har add/add-konflikt i `tests/test_intent_guard.py`, duplicerar B143 i `docs/known-issues.md` och byter warning-shape bort från schema/B144-UI-kontraktet. **PR #53** (`cursor/b143-intent-guard-en-slugs-5156`) är det nya rätt-basade B143-spåret: kodscopet ser smalt ut (utökar befintlig konflikt-tabell, bevarar warning-shape), men GitHub `governance` är röd eftersom B143-stängningsposten i `docs/known-issues.md` har fel parserformat (`öppnad + stängd` + em dash i stället för `(stängd ...) - ...`) och bug-scope-räkningen måste vara 28 aktiva / 103 stängda när B143 stängs. Fixa #53-docsformatet och kör om checks innan Scout/merge. **PR #52** (`cursor/codegen-brief-data-ef0b`, B141) är separat cloud-grind-spår med gröna checks men `mergeStateStatus=dirty`; den behöver rebase mot aktuell `main` (och sannolikt mot #53 om B143 mergeas först) plus korrekt `docs/known-issues.md`-räkning. **Direkt nästa orkestrator-fokus:** fixa #53 CI-formatfelet, Scout-reviewa #53, mergea B143 om godkänd, därefter rebase/review #52. Kör mini-eval med `scripts/verify_run.py` efter B143/B141 innan Project DNA-beslut. Tidigare paragraf:

Last verified state: `c2f0b0b` (2026-05-21, kvällen, **Post-sprint tooling + reviewer-feedback bump ovanpå Builder-sprint**) — aktuell `origin/main` är `c2f0b0b` (`chore(term-coverage): allowlist status-strängar (OK/FAIL/WARN/UNKNOWN/SKIP) för verify_run.py`). Sedan `da79056` (Builder-sprint slut): `432d2ab` (Builder-Steward-bump efter sprint), `cdb2063` (post-rebase chore — SHA-refs efter rebase ovanpå origin/main när PR #48 + #49 hunnit landa under sprinten), `5573bb9` (**PR #48 mergad** — `docs(adr): add 0026 — embeddings parkeras tills LLM contract propagation klar (Proposed)`, cloud-agent levererade ADR-skiss, 112 rader, 1 fil), `7288d3d` (**PR #49 mergad** — `docs(reports): inventory of Run Details warnings + Intent Guard placement skiss`, cloud-agent levererade RO-inventering av warning-fält och var Intent Guard bör renderas, 332 rader; **PR #50** stängdes som duplikat efter Composer-2.5 RO-review hittade felaktiga claims i den), `38f86da` (orchestrator-commit — `chore(tooling): add verify_run.py post-run smoke-checker + agent-integration docs` — nytt stand-alone verktyg under `scripts/verify_run.py` med 9 checks/`--checks`/`--json`/`--latest`; `docs/tools/verify_run.md` ger komplett agent-integrationsguide; `docs/agent-handbook.md` får ny "Post-build-verifiering utan preview"-sektion; verifierat live mot sköldpaddsoppa-ab-c39f01: B137 OK, Intent Guard OK, B138 SKIP pga briefen inte fångade `pageCount` i den körningen — Builder-fixen aktiv men ej triggad), `c2f0b0b` (denna term-coverage allowlist för status-strängar). **Live-verifiering bekräftad:** B137 + Intent Guard fungerar end-to-end på sköldpaddssoppa-payloaden — tagline `"Hjälp med sköldpaddssoppa"` (source: `"brief"`), 1 intentGuardWarning `{categoryId: "fitness", conflictingTerm: "mat"}`. B138 in-memory-bevisad av Builder men ej triggad live denna körning eftersom briefen råkade returnera `pageCount: None` (LLM-variation mellan körningar med olika prompt-formuleringar). **Extern reviewer-feedback (2026-05-21 kväll, ~7/10):** giltiga fynd; två nya buggar öppnade: **B143 (Medel)** — Intent Guard konflikt-tabell matchar svenska termer (`mat`/`hår`/`elektriker`) men briefens `businessTypeGuess` är engelska sluggar (`restaurant`/`electrician`/`hairdresser`); false-negative-risk i live-flödet. Fix-pekare: `scripts/build_site.py:_intent_guard_warnings` — utöka tabell med synonym-map svenska↔engelska. **B144 (Medel)** — `intentGuardWarnings` + `pageCountWarning` skrivs till `site-plan.json` men renderas inte i Run Details UI; PR #49-inventeringen ger placeringsskissen (target: amber-box i `apps/viewser/components/run-details-panel.tsx`-likvärdig komponent). Bug-räkning: **30 aktiva, 0 misplaced, 5 unknown, 101 stängda** (B143 + B144 nya; B137 + B138 stängda i sprinten). Inga öppna PRs, inga lokala feature-branches. `backup-37` (Builder-sprint pre-bas) + `backup-38` (denna tooling-pass pre-bas) finns på origin. **Direkt nästa orkestrator-fokus:** dagens reviewer-rekommendation pekar mot **B144 frontend-render-sprint** (Run Details ska visa intentGuardWarnings + pageCountWarning + ev. B132 pageIntentWarnings) som det enskilt mest värdefulla nästa steg eftersom det stänger gapet mellan sanning-i-artefakter och operatörens arbetsyta. **B143 Intent Guard slug-hardening** kan göras i samma sprint eller separat (1-1,5h Builder). **B139/B140/B141** står kvar öppna för separat sprint (brand/tone-propagation + codegen tone dead pipeline). Mini-eval på 4 baseline-prompter (elektriker / frisör / naprapat / sköldpaddssoppa) med `python scripts/verify_run.py --site-id <X> --json` per case är värd att köra innan eller efter B144 för regressions-bevis. Tidigare paragraf:

Föregående verified state: `da79056` (2026-05-21, **Builder-sprint B137 + B138 + Intent Guard light** ovanpå `8ba2b20`) — aktuell `origin/main` är `da79056` (`feat(planning): add intentGuardWarnings light (warning-only)`). Sprinten stänger Scout case 4-fynden (sköldpaddssoppa) i 4 commits ovanpå `8ba2b20`: `3875716` (`chore: ignore .cursor/plans/ and skip in term-coverage` — operatör-lokala plan-filer skippas i term-coverage + .gitignore, samma kategori som `.cursor/rules/`-speglar), `1b5275d` (B137 — wizard-overlay tagline-sanering via ny `_offer_looks_like_ui_directive`-helper i `packages/generation/discovery/resolve.py:_apply_company_fields`; UI-direktiv-detektor med sidantals-/färg-regex + instruktions-prefix + längd-bounds 8-120 tecken; brief-tagline vinner när offer är UI-direktiv, derived fallback via `_derived_fallback_tagline` när brief saknar tagline; ny `"derived"`-värde i `FieldSourceLiteral` + `discovery-decision.schema.json`-enum), `299257d` (B138 — `produce_site_plan` läser `site_brief.pageCount` och trimmar `route_plan` via ny `_trim_route_plan`-helper med prioritetslista `home`+`contact` aldrig borta, minsta körbara set = 2; ny `pageCountWarning`-property i `site-plan.schema.json` med `reason ∈ {"trimmed-to-brief-page-count","below-minimum-keeping-default"}`; trim funkar i både pinned-vägen och planning-helper-vägen), `da79056` (Intent Guard light — ny `_intent_guard_warnings`-helper i `scripts/build_site.py:build_plan_artefakts` läser `prompt_meta["discoveryDecision"]["categoryIds"]` + `site_brief.businessTypeGuess`/`servicesMentioned` och emitterar warnings vid konflikt; konflikt-tabell minimal i v1 — `fitness`/`construction`/`beauty` mot svenska term-set; warning-only, blockar inte build; ny optional `intentGuardWarnings`-array i `site-plan.schema.json`; ny `intent_guard_warnings`-parameter på `produce_site_plan` med bakåtkompatibel default `None`). End-to-end-mätning på sköldpaddssoppa-payload (in-memory): tagline `"Hemsida om sköldpaddssoppa, mat, 2 sidor, gröna färger"` → `"Tydlig hjälp inom restaurant"` (source: `"brief"`); routes `[/, /tjanster, /om-oss, /kontakt]` (4) → `[/, /kontakt]` (2) med `pageCountWarning`; `intentGuardWarnings` emitterar `{categoryId: "fitness", conflictingTerm: "mat", businessTypeGuess: "restaurant", reason: "category-vs-business-mismatch"}`. **B137 + B138 stängda** i `docs/known-issues.md`. **B139/B140/B141 lämnas öppna** (out of scope per coach + operatör-OK 2026-05-21). Backup-branch `backup-37` skapad från ren `main`-`8ba2b20` + pushad till origin INNAN sprintarbetet. Push-strategi (c) per operatör-OK: backup-37 + commits direkt på `main`, inget PR-flöde. Aktuell buggräkning: **28 aktiva, 0 misplaced, 5 unknown, 101 stängda** (B137 + B138 stängda denna pass; tidigare 30 aktiva, 99 stängda). 19 nya regression-tester (10 i B137, 7 i B138, 12 i Intent Guard — varav 2 är pre-existing B137-tester räknade dubbelt eftersom tabellen blir 29 totalt; faktiskt **29 nya tester**, ny totalsumma 319 passed lokalt + 3 E2E skipped). Alla 5 guards gröna före push: `ruff check .` (0 findings), `governance_validate` (17 OK), `rules_sync --check` (sync), `check_term_coverage --strict` (inga okända), `pytest tests/ -q` (319 passed). Inga öppna lokala feature-branches. PR #48 (ADR 0026 embeddings-postponed, Cloud Agent-arbete) är öppen men utanför min scope — operatören får hantera den separat. Edge-case-rester noterade till framtida sprint: (a) B137 ensamt färgord utan `färger`/`färg`/`tema`-suffix passerar detektorn (acceptabel risk för v1, dokumenterat i `_offer_looks_like_ui_directive`-docstring); (b) Intent Guard konflikt-tabell är minimal v1 — 3 kategorier × ~4 termer per kategori (utbyggnad vid Scout-fynd av nya false-negative-case); (c) Intent Guard mirrors INTE warnings till `build-result.json` denna sprint — Backoffice/Run Details läser `site-plan.json` direkt; (d) `_derive_tagline` i `scripts/prompt_to_project_input.py` inte lyft till paket-modul (skopet förblev minimalt, derived fallback klarade sig med inline-helper). Steward-bump-commiten själv är inom focus_check bump-tolerance (1 commit ahead OK). Tidigare paragraf:

Föregående verified state: `6e592de` (2026-05-20, **Steward Pass 3 docs-bump — B142 öppnad + stängd same-pass ref `f8d6a52`**) — aktuell `origin/main` är `6e592de` (`docs(steward): close B142 (ProjectInputPicker run-following) ref f8d6a52 + Pass 3 sync`). Sedan föregående `9c4d6a1`: `3709a23` (Steward Pass 2 focus-bump), `1d6fadf` (Scout RO-rapport PR #47), `9c4d6a1` (Steward Pass 2 — fix-pekare B137/B139 + B140/B141), `f8d6a52` (Builder: ProjectInputPicker sync till vald run — `apps/viewser/components/prompt-builder.tsx` skickar `siteId` i `onBuildDone`; `apps/viewser/app/page.tsx` får ny `selectRunAndSyncSiteId()`-helper; `console-drawer.tsx` + `project-input-picker.tsx` visar "följer vald run"-badge + amber-varning), `bfab769` (`chore(dev-tooling): default Viewser to HTTPS locally` — `npm run dev` defaultar till `--experimental-https`, ny `dev:http`-script som opt-out; `scripts/dev-viewser.ps1` byter `-Https` mot inverterad `-Http`-flag; `scripts/dev-panel.ps1`-launcher pekar nu på `https://localhost:3000`), `6e592de` (denna Pass 3 docs-only ovanpå `bfab769`). **Steward Pass 3 (2026-05-20, docs-only):** öppnade och stängde **B142 (Låg-medel, ProjectInputPicker följer vald run)** i samma pass — operatörspanelens picker synkade inte med vald run (kunde visa `painter-palma` medan vald run var `snus-ab`); rörde inte renderad output, bara operatörens översiktsyta. Fix: `f8d6a52` (Builder), Test: open — manuell verifiering rekommenderas eftersom dedikerad React-state-test för run-following saknas i repo idag (breda viewser-smoke-tester gröna lokalt). Nice-to-have-rad inlagd i Queue (`viewser React-state-test-setup för run-following + framtida picker-syncs`). Aktuell buggräkning: **30 aktiva, 0 misplaced, 5 unknown, 99 stängda** (B142 öppnad + stängd 2026-05-20). Inga öppna PRs, inga lokala feature-branches. `backup-36` skapad från `origin/main`-`bfab769` + pushad innan Pass 3-arbetet. Inga produktfiler rörda i Pass 3 — Builder-passet kickas direkt efter denna push. Tidigare paragraf:

Föregående verified state: `9c4d6a1` (2026-05-19, sen kväll, **Steward Pass 2 docs-bump — B137/B139 fix-pekare uppdaterade + B140 + B141 öppnade**) — aktuell `origin/main` är `9c4d6a1` (`docs(steward): fix B137/B139 pointers + open B140 (brand.primaryColorHex) + B141 (codegen tone dead pipeline)`). Sedan föregående `ff7890b`: `369036f` (Steward Pass 1 focus-bump), `1d6fadf` (Scout RO-rapport PR #47 mergad — `docs/reports/scout-wizard-tagline-pagecount-tone-2026-05-19.md` kartlägger wizard-tagline + brief.pageCount + tone-propagation-kodvägar), `9c4d6a1` (denna Steward Pass 2 docs-only ovanpå `1d6fadf`). **Steward Pass 2 (sen kväll, docs-only):** Efter Scout-rapport PR #47 uppdaterades fix-pekarna för B137 (från `scripts/prompt_to_project_input.py:_derive_tagline` till `packages/generation/discovery/resolve.py:_apply_company_fields` rad 609-628 — wizardens `answers.offer` skriver över briefens tagline efter brief-produktion; `_derive_tagline` kvarstår som fri-prompt-fallback) och B139 (från `packages/generation/codegen/` till `scripts/build_site.py:variant_css()` rad 701-737 + `patch_globals_css()` rad 2107-2136 — helpern läser bara `variant["tokens"]`). Två nya öppna ytterligare fynd registrerade: **B140 (Låg, ny)** — `brand.primaryColorHex` ignoreras av `variant_css` (angränsande till B139, separat data-kanal: explicit operatörshex vs extraherad tone). **B141 (Låg-medel, ny)** — `packages/generation/planning/plan.py:_assemble_generation_package()` skriver bara `siteBriefRef`, INTE `siteBrief`-objektet, så `packages/generation/codegen/codegen.py:_summarise_generation_package()` läser `tone`/`businessType` från död pipeline. NOTE-blockquoten i B137-entryn från Pass 1 är borttagen (rätt kodväg nu inlagd). Aktuell buggräkning: **30 aktiva, 0 misplaced, 5 unknown, 98 stängda** (B140 + B141 nya). Inga öppna PRs, inga lokala feature-branches. Inga produktfiler rörda — Builders sprint öppnar nästa pass. Tidigare paragraf:

Föregående verified state: `ff7890b` (2026-05-19, sen kväll, **Steward Pass 1 docs-bump — B138 + B139 öppnade + B137-NOTE WIP**) — aktuell `origin/main` är `ff7890b` (`docs(steward): open B138 (pageCount leak) + B139 (tone propagation) + flag B137 fix-pointer WIP`). Sedan föregående `e1103c5`: `fc8f96d` (Steward post-Scout-case-4 focus-bump till `e1103c5`), `9089b7a` (term-coverage-allowlist för `'B137 fix'`-fras i Steward-prose), `6f91810` (docs(steward) orkestrator-handover efter Scout case 4 + ADR 0025 + nya regler), `ff7890b` (denna Steward Pass 1 docs-only ovanpå `6f91810`). **Steward Pass 1 (sen kväll, docs-only):** B138 (Medel, ny — pageCount-läckage från brief till routePlan; briefModel fångar `"2 sidor"` korrekt men `produce_site_plan` ignorerar `brief.pageCount` och emitterar scaffold-defaults; verifierat i sköldpaddssoppa-runen `data/runs/20260519T190606.540Z-51cef6dd-skoldpaddssoppa-karlsson-099d5c/`) och B139 (Låg-medel, ny — tone-extraction propageras inte till brand-tokens; `tone.primary="grön"` läses inte av renderern, brand-tokens kommer enbart från variant-CSS-vars) öppnade. B137-fix-pekaren (mot `_derive_tagline` i `scripts/prompt_to_project_input.py`) flaggad som WIP via NOTE i `docs/known-issues.md` — discovery-metans `fieldSources.company.tagline = "wizard"` säger att taglinen kommer från wizard-overlay-mappningen, inte från `prompt_to_project_input.py`. Scout RO-pass pågår parallellt och kartlägger exakt kodväg; Steward Pass 2 uppdaterar entryn med rätt fil/funktion + test-pekare. Aktuell buggräkning: **28 aktiva, 0 misplaced, 5 unknown, 98 stängda** (B138 + B139 nya). Inga öppna PRs, inga lokala feature-branches. `backup-34` skapad lokalt + pushad till origin för denna docs-pass. Tidigare paragraf:

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

`main` är vid `465b8fa` på origin och lokalt efter en defensiv separator-
order-fix i `scripts/rules_sync.py`. Den föregående link-rewrite-fixen
(`919d564`) hade en kantfallsbug där sibling-länkar med både `?query`
och `#anchor` aldrig fick `.md` → `.mdc`-konverteringen. Båda länk-
rewriterna är nu kompletta. Markdown-linter-varningen som operatören
rapporterade på `.cursor/rules/always-swedish.mdc:37` är borta för alla
sju spegelfiler. Inga ändringar i `governance/rules/`-källan. PR55-
agentens worktree är fortsatt städad. Öppen DRAFT-PR #56 från cloud-
agenten driver Project DNA-spåret och rörs inte av lokal orchestrator.
Bug-räkning oförändrad: **27 aktiva, 0 misplaced, 5 unknown, 104
stängda**. `backup-42` finns på origin från pre-SNI-läget. Inga öppna
PRs förutom PR #56 (cloud-agent-DRAFT). Föregående stage snapshot:

`main` var vid `2e274ac` på origin och lokalt efter SNI-sidospår-pushen.
SNI 2025-importen ger nu repo:t en deterministisk JSON-spegel under
`data/taxonomies/sni/sni-2025.v1.json` (1882 SNI-poster över alla fem
nivåer från avdelning till detaljgrupp). En ny handstyrd policy
(`governance/policies/sni-discovery-map.v1.json`) översätter SNI-prefix
till kandidat `wizardCategoryId` i Discovery Taxonomy, med tydliga
schema-guards mot starter/scaffold/variant/dossier-direktval. En read-
only Backoffice-vy under Building Blocks/Kontrollplan visar SNI →
wizardCategoryId → Discovery Taxonomy-kedjan med operator-lookup-fält.
Inget i runtime konsumerar SNI än: Viewser-overlay, Discovery Resolver,
generation, planning och codegen är oförändrade. Sprinten är en
sidospår-leverans inför Project DNA / semantic follow-up som blir nästa
huvudspår med B71 som primärt ankare. Inga öppna PRs. Bug-räkning
oförändrad: **27 aktiva, 0 misplaced, 5 unknown, 104 stängda**. `backup-
42` finns på origin från pre-sprint-läget. Föregående stage snapshot:

`main` var vid `63d7264` på origin och lokalt efter Scout-godkänd push.
B132 follow-up-sprinten har landat wizard-route-emission för
`local-service-business`: när wizardens `mustHave` säger `FAQ` /
`Bildgalleri` / `Vårt team` / `Priser och paket` / `Portfolio / Case` /
`Karta / Hitta hit` får operatören riktiga sidor (`/faq`, `/galleri`,
`/team`, `/priser`, `/portfolio`, `/karta`) i stället för enbart
`pageIntentWarnings`. `Bokning online`, `Blogg / Nyheter` och
`Nyhetsbrev` håller warning-shape med specifika reason-strängar
eftersom de kräver integration som inte finns i deterministiska
Builder v1. Mini-eval över fyra cases (CLI mock-väg, `--skip-build`)
visar 2→0 warnings för elektriker, 4→1 för frisör, 4→1 för naprapat,
1→0 för sköldpaddssoppa, med korrekta route-filer under
`app/<route>/page.tsx`. Scout-RO-review gav `OK_PUSH`-verdict med
PASS på alla sex acceptanskriterier. B144/B143/B141 och Backoffice
Building Blocks-diagnostiken (`650c518`) är kvar oförändrade ovanpå
sprinten. Inga öppna PRs. Bug-räkning oförändrad: **27 aktiva,
0 misplaced, 5 unknown, 104 stängda**. Föregående stage snapshot:

`main` var vid `650c518` på origin och lokalt. B144, B143 och B141 är
stängda, och Backoffice har nu en read-only Kontrollplan-del för
wizardfält → generation som diagnostiserar befintliga källor utan ny
runtime-sanning. PR #51 är stängd utan merge, PR #53 och PR #52 är
squash-mergade, och det finns inga öppna PRs. Nästa produktsteg var
en Viewser-overlay-mini-eval som verifierar att fixarna märks i
operatörsflödet: varningar syns i Run Details, Intent Guard missar inte de
engelska slug-fallen, codegenModel-prompten får faktisk Site Brief-data via
`siteBriefRef`, och den nya Backoffice-diagnostiken kan användas som stöd
för att se om wizard-svar överlever i generationen. Föregående stage
snapshot:

`main` är vid `da79056` (`feat(planning): add intentGuardWarnings light (warning-only)`) ovanpå 4 commits ut från `8ba2b20`. Builder-sprint 2026-05-21 har stängt **B137** (wizard-overlay tagline-läckage av UI-direktiv) och **B138** (`brief.pageCount` ignorerades i `produce_site_plan`) samt landat **Intent Guard light** (warning-only conflict-flagging mellan wizardens `categoryIds` och briefens `businessTypeGuess`/`servicesMentioned`). Scout case 4 (sköldpaddssoppa, 5.0/10) är därmed adresserad på alla tre fynd-vektorerna. **Direkt nästa steg:** ny **Viewser-overlay-E2E-Scout** på sköldpaddssoppa + minst ett konsistent baseline-case för att verifiera att tagline + routePlan + Intent Guard-warning beter sig korrekt live (in-memory-mätningarna är gröna men live-renderad output mot StackBlitz preview är ännu inte verifierad). Beslutsregeln (≥7 OCH inget <6.5 → Project DNA-sprint) återkommer när Scout har nytt snitt; om sköldpaddssoppa nu landar över 6.5 + övriga case fortsatt OK kan Project DNA-sprinten starta. Kvarvarande Case 4-spår-rester som ej rörs i denna pass: **B139** (tone-extraction propageras inte till brand-tokens, Låg-medel), **B140** (`brand.primaryColorHex` ignoreras av `variant_css`, Låg), **B141** (`_assemble_generation_package` skriver bara `siteBriefRef` inte inline `siteBrief`, Låg-medel) — alla öppna för separat sprint.

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

Ingen pågående lokal produktimplementation efter PR #54-merge och
Steward-synk (`2057241`). B132 route-emission är verifierad via live
Viewser-overlay-artefakter och Backoffice-diagnostiken är korrigerad.
Aktivt orkestreringsläge: avsluta B132/PR54-spåret och starta nästa
produktspår, **Project DNA / semantic follow-up**, med B71 som primär
buggankare. StackBlitz/B59/B125 är fortsatt launch-blocker för extern
kundyta, men parkeras som separat preview-sprint så det inte blockerar
intern follow-up-kvalitet.

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

**Aktuellt direktiv efter PR #54 + live Viewser Scout (2026-05-22):**
B132 route-emission är godkänd i live-overlay-artefakter och PR #54 är
mergad. StackBlitz-felet är känt B59/B125-previewspår, inte en ny
B132-regression. **Nästa agent ska starta Project DNA / semantic
follow-up-spåret** och hålla scope smalt:

1. Läs B71 i `docs/known-issues.md` och nuvarande
   `scripts/prompt_to_project_input.py::merge_followup_project_input`.
   Målet är att följdprompt mot tone/story/tagline/positionering ska ge
   synlig v2-ändring utan att släppa igenom rå prompt som kundcopy.
2. Börja med read-only Scout/design: kartlägg vilka fält som i dag fryser,
   vilka som är säkra att semantiskt mergea, vilka artefakter som ska visa
   ändringen, och om en liten ADR behövs innan Builder-implementation.
3. Föreslå sedan en Builder-sprint med fokuserade regressionstester för:
   story/tagline/tone update, byte-stabilitet för oändrade fält,
   svensk teckenhantering, och synlig skillnad i genererad v2.
4. Starta inte embeddings, SNI-runtime-taxonomi, nya starters,
   variant-promotion eller preview-fallback i samma sprint.

SNI-underlaget ligger som operatörsplacerad referens på
`data/taxonomies/sni/sni-2025.xlsx`. Använd det inte som runtime-sanning
ännu; det hör hemma i ett senare taxonomy-/branschmappningsspår.

Äldre Scout-/previewdirektiv nedan ligger kvar som historiskt eval-underlag
men är inte längre första next action.

Scout RO-review på Builder-sprint-diffen (B132 follow-up) är **redan
körd och godkänd** i sprintens egen session: verdict `OK_PUSH` med PASS
på alla sex acceptanskriterier (ingen falsk booking-/payments-/auth-/
newsletter-integration, `Bokning online` håller warning med specifik
reason, `local-service-business` opt-in via `_WIZARD_ROUTE_SCAFFOLDS`,
tester täcker både emission och warning-only-spår, `_intent_guard_warnings`
byte-identisk mellan bas och sprint-commit, ingen ändring av
`packages/generation/discovery/resolve.py`). Pushen är gjord på `63d7264`
och Steward-bumpen ligger på `f178456`. Scout föreslog tre framtida
regression-tester som **inte** är blockers: `test_page_intent_warns_nyhetsbrev_with_newsletter_reason`
(spegel av booking/blogg), parametriserade mini-eval-fixtures som
låser operatörens före/efter-tabell, och negativt test för okänt
wizard-id i `routePlan` utan registrerad renderer.

**Direkt nästa steg:** Starta en ny **Viewser-overlay-mini-eval Scout**
mot post-push-`main` = `f178456`. Målet är att avgöra om nästa
Builder-sprint ska vara Project DNA / semantic follow-up eller en
riktad bug-sweep, och att verifiera att de nya wizard-routes faktiskt
renderas i StackBlitz-preview och att Backoffice Building Blocks-vyn
(`650c518`) speglar de nya routes-emissionsvägarna korrekt.

Minsta case-set:

1. **sköldpaddssoppa conflict-case** - verifiera renderad output +
   `site-plan.json`: ingen tagline-läcka av `"2 sidor"`/`"gröna färger"`,
   route-trim till `/` + `/kontakt` när briefen fångar pageCount,
   `intentGuardWarnings` syns i Run Details, samt att `FAQ` i mustHave
   nu landar som `/faq` istället för warning.
2. **elektriker Malmö** - baseline utan Intent Guard false positive;
   verifiera att `Portfolio / Case` i mustHave nu blir `/portfolio` med
   svensk copy och kontakt-CTA.
3. **frisör Göteborg** - baseline för beauty/salon-spåret efter B143;
   verifiera att `Priser och paket` → `/priser`, `Bildgalleri` →
   `/galleri`, `Karta / Hitta hit` → `/karta` faktiskt renderar och
   att `Bokning online` ger warning med ny reason-sträng (inte route).
4. **naprapat Stockholm** - vanlig tjänst med kontakt/adress;
   verifiera `Vårt team` → `/team`, `Karta / Hitta hit` → `/karta`,
   `FAQ` → `/faq`.

Om tid finns: ett follow-up-case där v2 ska ge synlig ändring. Scout ska
leverera per-case-poäng, blocker/risk/nice-to-have, samt beslutsregel:
snitt >= 7 och inget case < 6.5 -> Project DNA-sprint; annars riktad
bug-sweep på sämsta case. Använd `python scripts/verify_run.py --site-id
<X> --json` som artefaktkontroll när en build finns.

Äldre Scout-direktiv nedan ligger kvar som eval-underlag:

**Re-run Viewser-overlay-E2E-Scout case 4 (sköldpaddssoppa) live mot
post-sprint-`main` (`da79056`)** för att verifiera att Builder-sprint
2026-05-21 (`3875716` → `da79056`) faktiskt löser fynden i renderad
output, inte bara i in-memory-tester:

- **B137-verifiering:** öppna `app/page.tsx` på den nya sköldpaddssoppa-
  builden — Hero-taglinen ska inte längre läcka `"2 sidor"`,
  `"gröna färger"` eller `"Hemsida om ..."`.
- **B138-verifiering:** `site-plan.json` ska visa 2 routes (`/`, `/kontakt`)
  och en `pageCountWarning` med `requestedPageCount: 2`,
  `scaffoldDefaultCount: 4`, `emittedRouteCount: 2`,
  `reason: "trimmed-to-brief-page-count"`. Generated `app/`-mappen ska
  bara innehålla home- och kontakt-routes — inga `/tjanster` eller
  `/om-oss`.
- **Intent Guard-verifiering:** `site-plan.json` ska innehålla
  `intentGuardWarnings: [{categoryId: "fitness", conflictingTerm: "mat",
  businessTypeGuess: "restaurant", reason: "category-vs-business-
  mismatch"}]`. Builden ska gå igenom (warning-only).
- Kör samtidigt ett **konsistent baseline-case** (electrician eller
  frisör) för att bekräfta att Intent Guard inte triggar false positives
  på normala flöden.
- Beslutsregeln återstår (≥7 OCH inget <6.5 → Project DNA-sprint). Om
  sköldpaddssoppa nu landar över 6.5 + övriga case fortsatt OK kan
  Project DNA-sprinten startas.

Föregående next action (Viewser-overlay-E2E-Scout-pass 4-6 case) gäller
fortsatt — sköldpaddssoppa-verifieringen är **steg 1** av det passet,
inte ersättning. Case 5 (`"2 sidor"`-explicit-prompt utan wizard-konflikt)
är nu naturligt att köra direkt efteråt eftersom B138 är fixad och bör
ge synlig 2-route-output.

**Föregående Builder-sprint (2026-05-21, sköldpaddssoppa-spår) — landad
i `3875716` → `da79056`:** B137 (wizard-overlay tagline-sanering),
B138 (`brief.pageCount` → `routePlan` trim), Intent Guard light
(warning-only). 29 nya regression-tester, 5 guards gröna, 319 pytest
passed. Backup-37 skapad och pushad innan sprintarbetet.

**Föregående next action (Viewser-overlay-E2E-Scout):**

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

**PR #56** (`cursor/project-dna-followup-cdad`, **DRAFT**,
`feat(builder): add Project DNA semantic follow-up`, 5 filer +1152
/-19, skapad 2026-05-22 23:59 UTC av cloud agent) är **det aktiva
DNA-spåret**. Lokal orchestrator ska inte starta egna DNA-ändringar
och inte review:a/merge:a PR:n förrän cloud-agenten flaggar den som
ready-for-review (då görs Scout RO-review innan eventuell merge). Det
här är operatörens uttryckliga arbetsdelning 2026-05-22: cloud agent
äger DNA-spåret tills annat sägs.

**PR #55** är mergad i `e822a2c` (2026-05-22 23:50 UTC). Tre viewser-
fixar: stale-closure i `applyRunsData`, `setBundle(null)`-cleanup i Run
Details och ny `runSiteIdUnknown`-prop. Reviewerns observation om att
PR-bodyn felaktigt nämnde ett `ApplyRunsContext`-named-typ stämmer —
mergens andra commit gjorde ctx inline. Branchen `fix/viewser-followup-
stale-state` raderad från origin; lokal kopia kan finnas kvar i
operatörens separata worktree `../sajtbyggaren-pr55/`.

PR #51 stängdes utan merge. PR #53/B143 och PR #52/B141 är mergade.
Äldre PR-blockers är stängda/mergade: PR #38 mergades 2026-05-19
(merge-commit `48a6a22`, se B129), PR #25 är mergad i `c073d486`.

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

1. **Project DNA / follow-up semantic merge** - nästa produktspår. Utgå
   från B71: följdprompt ska kunna ändra tone/story/tagline/positionering
   synligt i v2 utan rå prompt-läckage och utan att oändrade fält driftar.
   Börja med Scout/design och landa ADR bara om ändringen påverkar
   kontraktet mellan Project Input, Site Brief och builder-output.
2. **Preview-stabilisering / B59-B125 decision sprint** - live
   Viewser-overlay Scout 2026-05-22 bekräftade route-emission i
   artefakter men StackBlitz-preview visade `Unable to run Embedded
   Project` på alla runs. Detta är launch-blocker för extern kundyta,
   men inte blocker för intern Project DNA-sprint.
3. **Viewser-overlay-E2E-Scout follow-up** - återuppta verklig
   frontend-kvalitetsmätning när previewn kan klickas igenom visuellt:
   wizard → prompt → eventuell scrape/upload → build → preview. Se
   historiskt case-set i "Next action".
4. **B119/B120 kontakt/adress-kvalitet** - om Scout visar fel kontaktdata:
   prioritera `_pick_contact_route`-poängsättning och adress-till-stad-regex.
5. **Intent Guard + Page Intent** (om Scout-fynd bekräftar) - prompt-mot-
   wizard-mismatch-guard och pageIntent som faktiskt påverkar route-planen.
   Båda var parkerade post-B121 men aktualiseras om Scout visar att fri
   prompt och wizard fortfarande motsäger varandra.
6. **Capability/dossier gaps** - booking, contact-form, payments, FAQ ska
   inte bara varna utan ha Dossier-implementation när taxonomy flaggar dem.
7. **Variant-promotion-sprint** - PR #38 `feat/eight-scaffold-variants`
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
8. **Bug-sweep round 3 (om Scout fortsatt under tröskel)** -
   prioritera B67, B80, B81, B82, B84, B85, B86, B87 + B89-B93
   (extern reviewer-triage) + B97/B98 (låg-impact-rester) eller
   riktad fix på det case som dröjer.
9. **Live pipeline-matris i backoffice (operatörsförslag 2026-05-15
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
10. B49 (medel): page-map-driven sidebar för `docs-base`-startern; måste vara klar innan `course-education -> docs-base` aktiveras i `SCAFFOLD_TO_STARTER`.
11. **B59 follow-up** (aktualiserad av live-scout 2026-05-22): byte till lokal `next dev`-process som same-origin iframe på `localhost:NNNN` eller static StackBlitz-template. Ingen mer COOP/COEP-toggling. Bredare extern research om SDK-/Codeflow-/Teams-/MCP-ytan, kommersiell licens och browser-baseline ligger i [`docs/integrations/stackblitz-research.md`](integrations/stackblitz-research.md) som underlag inför arkitekturbeslutet.
12. B53 (låg): `governance/schemas/routes.schema.json` för scaffold-routes-kontraktet.
13. B47 (låg): commerce-base Shopify-handles dokumenteras eller får fallback.
14. B13a arkitektur-flytt (egen sprint, kräver ADR).
15. `write_pages` icon-bibliotek-agnostisk refactor.
16. Cancellation-followup (låg): riktig cancellation/background-jobb i playground-vyn om operatören behöver avbryta redan startade körningar.
17. **Viewser React-state-test-setup (nice-to-have, post-B142)** - dedikerad React-state-/komponent-test-setup för `apps/viewser/` saknas i repo idag. B142 stängdes utan regression-test (manuell verifiering + breda viewser-smoke-tester gröna). Liknande UI-sync-buggar (run-following, picker-syncs, console-drawer-state) skulle få bättre låsning om vi inför Vitest + React Testing Library i `apps/viewser/` med ett par mönstertester (page.tsx run-following, ProjectInputPicker badge-/varning-rendering). Egen mini-sprint; ej blocker.
18. **SNI-/branschtaxonomi-underlag** - `data/taxonomies/sni/sni-2025.xlsx`
    finns som operatörsplacerad referens. Använd som underlag för framtida
    kontrollerad branschmappning, inte som direkt runtime-sanning.

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
