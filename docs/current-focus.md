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

Last verified state: `b414c6b` (2026-05-26 PM UTC, post-naprapat scaffold-fix — Lane 3 embeddings-gate-blockaren stängd).
Nya PRs sedan föregående checkpoint: PR #118 (sync(jakob-be -> main): PR #117 mobile responsive + PR #116 dossier-intake + 12 closed bugs + B147 new + audit-report) och PR #120 (sync(jakob-be -> main): repo hygiene 2026-05-26, 4 commits docs-only) mergade till main. PR #119 (feat(backoffice): add dossier intake model review) mergad till jakob-be som `31d8d74` och inkluderad i PR #118-squashen. Direkta commits ovanpå efter jakob-be → main reset:

- `cc1a5aa` chore(viewser): commit vercel.json deploy config.
- `0ed5348` docs(backend-handoff): mark gap 1 + 11 as closed (audit 2026-05-26). Plus 5 prod-refs uppdaterade i wizard-types.ts / visual-step.tsx / asset-store/types.ts / vercel-blob.ts / .env.example så de speglar att Gap 1 + 11 är stängda i kod.
- `4cd367c` fix(planning): close naprapat scaffold-routing for clinic-healthcare. `_CLINIC_SIGNALS` i `packages/generation/planning/plan.py:_pick_scaffold_from_brief` (mock-fallback path) + 6 nya regression-tester (10 parametrize-fanout total) i tests/test_planning.py. Plus stale-doc-string-cleanup i `packages/generation/discovery/resolve.py:_scaffold_hint_from_payload` så den listar 6 runtime-aktiva scaffolds istället för 3.
- `b414c6b` fix(prompt-input): route clinic prompts to clinic-healthcare in pick_scaffold + align eval routes. `_CLINIC_TOKENS` i `scripts/prompt_to_project_input.py:pick_scaffold` (pinned Project Input path), synkad med `_CLINIC_SIGNALS` i plan.py. Plus `expected_routes` i `scripts/run_golden_path_eval.py:naprapat-stockholm` uppdaterade från `("/", "/behandlingar", "/team", "/kontakt")` till `("/", "/behandlingar", "/om-oss", "/kontakta-oss")` för att matcha clinic-healthcare-scaffolds canonical routes (per `packages/generation/orchestration/scaffolds/clinic-healthcare/routes.json` + B45/B101 contact-path-tester). 13 nya regression-tester (parametrize-fanout) i tests/test_prompt_to_project_input.py.

Eval-verifiering (offline deterministic): naprapat-stockholm 5.83 → **6.81** (passes 6.5-threshold), total score 7.10 → **7.34**, embeddings gate `no-go` → **`go`**. Lane 3 embeddings-readiness är därmed inte längre blockad av den deterministiska scaffold-selection-bug:en — nästa Lane 3-spår är ADR 0026:s "befintliga brief/render-signaler ska bevisas" (operatörsbeslut).

Sedan c0b59fbe (PR #60) har följande mergats till `main`, i ordning:

- `a32152d` PR #61 — team parallel workflow + ownership map (parallell-team-flödets grund).
- `7240fcd` PR #62 — viewser/christopher-ui builder-workflow-integration.
- `f9312ec` PR #63 — wizard-directives `useCustomColors` + `scaffoldHint` (backend-Gap 1 + 3 stängda).
- `89f14a1` PR #64 — branch-naming-konventioner för parallellt teamarbete (permanenta arbets-branches `jakob-be` + `christopher-ui` dokumenterade i `docs/ownership-map.md`).
- `d709864` PR #66 — `sourceUrl`-asset-uploads med stream-safe fetch (PR #65 stängd och supersededad).
- `7e900d2` PR #67 — AI bug review-workflow-steg i CI (`gpt-5.4` + repo-specifik prompt).
- `839d0c8` PR #68 — restaurant-hospitality scaffold + 11 soft dossiers + 14 variants (Week 1 declarative expansion). Inkluderade två `[scope-leak]`-commits från Christopher i `plan.py` + `resolve.py` — accepterade som operator-approved engångsundantag.
- `cb5c837` PR #70 — Sprintvakt V1 koordineringsserver + lokal MCP-server (path-overlap-bug i `paths_overlap` verifierad fixad i fix-commit `419d3f1`).
- `7e21b49` PR #71 — Christophers Front 1-4 + wizard minimalism (5 nya UI-gaps: 4 in-review/completed + 1 aktivt + 1 queued backend-spec).
- `84bf9dd` PR #75 — Sprintvakt V1.1+V1.2+V1.2.1 + CI-hardening + Backoffice industry coverage + Path B scout + ADR 0029 + docs sync (16 commits squashade till en).
- `6649b51` docs(steward) — closing-round sync på `jakob-be` efter PR #75 (post-merge docs-bump).
- `92df12c` PR #76 — recovery av tappade #73/#74 regressionstester + Industry Coverage catch-all-fix (mergad till `jakob-be`, inte till `main` än).
- `dc1d53f` docs(steward) — closing-round sync 2026-05-25 04:30 efter recovery #76 (post-merge docs-bump utan kod).
- `d3f51ee` PR #77 — Sprintvakt agent inbox (post/list/ack) + 5 reviewfynd-fixar i samma squash. 5 filer, ~1399 additions (varav 752 är tester). Mergad till `jakob-be`, inte till `main` än.
- `e2574af` PR #78 — candidate generation provenance + helpers (`scripts/candidate_generation_metadata.py`) + sidecar `.meta.json` per kandidat + Backoffice-default `use_llm=False`. 9 filer, ~562 additions. Mergad till `jakob-be`, inte till `main` än.
- `a0b06b5` docs-fix — escape `[runId]` i trace-endpoint-gap så markdown-linter inte klagar (matchar `_MARKDOWN_ESCAPE_RE`-konvention i `core.py`).
- `b12c164` grind-fix — `_load_gap_from_file` unescapes nu markdown backslash-escapes så `sanitize_repo_path` inte producerar korrupta paths. 80 rader, ny regression-test, ren cloud-grind-fix mot `jakob-be`.
- `74e74f2` docs(steward) — parallell-sprint-plan committad, last verified state bumpad till `b12c164`, mcp tools 11→14, lane-strukturen dokumenterad.
- `86c01fa` PR #81 — `fix(grind): close B83 service slug collision`. Status-only-stängning (test fanns redan), cloud-grindens första PR.
- `0ea3f3d` PR #82 — `docs(scout): embedding readiness audit 2026-05-25`. Lane 3 Scout-rapport: No-Go-dom med konkreta Go-villkor (lane 2 mergad + golden-path eval ≥7/10), 386 rader, modellval-jämförelse, B-IDer för schema-bumpar.
- `4d4a27b` PR #80 — `fix(grind): close B85 stdout contract drift`. Source-lock-test för `scripts/prompt_to_project_input.py`-docstring vs stdout-nycklar. Cloud-grind round 2.
- `7654573` PR #79 — `fix(grind): close B87 model fallback warning`. `resolve_brief_model`-fallback loggar nu högt på stderr per B87-fix-direktivet. Cloud-grind round 3.
- `2821e5f` docs(steward) — Sprintvåg 1 stängd, bumpade verified state till `7654573`, dokumenterade alla fyra PRs i landade-spår-listan.
- `2a5d2e5` PR #83 — `docs(grind): close B72 + B75 status-sync to Stängda`. Båda buggarna fixed i `885431b` (PR #28), regression-tester passar mot HEAD, bara docs-position låg fel. Cloud-grind round 4.

**Pågående/öppna PR:s just nu:**

Inga öppna PRs på `jakob-be` eller `main`. PR #116 (`8c057b1`), PR #117 (`2319ef9`), PR #118 (`1740472`), PR #119 (`31d8d74`) och PR #120 (`15aea46`) är alla mergade. `jakob-be` är resetad till `origin/main` 2026-05-26 PM (commit `1004122`) plus följande direkta commits ovanpå: `cc1a5aa` (vercel.json), `0ed5348` (backend-handoff cleanup audit), `3fc187e` (focus bump efter cleanup), `4cd367c` (naprapat plan-fallback fix), `b414c6b` (naprapat pick_scaffold + eval routes fix). `jakob-be` är 5 commits framför `origin/main` — nästa sync-PR till main när nästa större spår är inne (Lane 2 LLM contract propagation eller B147-fixen).

Pending operatörsklick: Vercel production-branch-flip från `jakob-be` till `main` per `docs/operations/vercel-production-branch-todo.md` — se "Direkt nästa fokus" punkt 1 nedan.

**Christophers `origin/christopher-ui` (`9f63f15`)** — Christopher har
under operator-OK scope-leak implementerat hela
`GAP-backend-build-trace-endpoint`: 3 endpoints (`GET /api/runs/\[runId\]/trace`,
utökad `GET /api/runs` med `pending`-rader, `POST /api/prompt` med
`baseRunId`), UI utan clipboard-workaround, 5 bug-hunt-fixes och nya
tester. Plus en versions-tab-fix på `9f63f15`. Ej PR:ad mot `main`;
Jakob är reviewer. Workboardens `owner` är medvetet kvar på `jakob`
så Sprintvakt-lane-policyn passerar (precedent från PR #68).

Pågående parallellt: alla redundanta cursor-branches städade. Kvar på
origin är endast två lane-WIP-branches:

- `cursor/jakob-be-llm-contract-propagation` (`7847e5c`) — Lane 2 WIP-rescue efter bg-subagent-error. Behind med 4 commits. Behöver ny agent som rebasar mot `7654573` och fortsätter regression-test-suiten.
- `cursor/jakob-be-golden-path-eval` (`3bee355`) — Lane 4 WIP-rescue efter delad-worktree-röra. Behind med 4 commits. Väntar på lokala agent att resuma. 

Orchestrator-worktree är isolerad till
`C:\Users\jakem\Desktop\sajtbyggaren-orchestrator` för att slippa
branch-byten i delad mapp.

**Ärlig bedömning av dagens leverans (extern reviewer + orchestrator-
self-audit):** Av 2026-05-25 morgons 5 PRs är endast PR #79 en
substantiell produktkodsförändring. Övriga 4 är koordination, docs,
tester eller status-flyttar. Sprintvåg 1+2 är bokföringsmässigt
imponerande (5 merges) men produktmässigt minimalt. Nästa session
MÅSTE prioritera kärnflödet `prompt → brief → plan/build → preview →
följdprompt` snarare än fler koordinations- eller status-PRs.

**Direkt nästa fokus:**

1. **Vercel production-branch-flip — operatörens manuell klick.** Gå till `https://vercel.com/jakeminator123s-projects/sajtbyggaren-viewser/settings/git`, ändra Production Branch från `jakob-be` till `main`, trigga `vercel --prod` för verifiering. Efter flippen: radera `docs/operations/vercel-production-branch-todo.md`. PR #118 + #120 är mergade till main — flippen är inte längre blockad av sync-drift. Beslut 2026-05-25 om temporär `jakob-be`-prod-branch är nu uppfyllt.
2. **B147 vägval a/b/c** (operatörsbeslut, sen kod). Vercel preview wizard 403 via `assertLocalhost` på `*.vercel.app`. Tre alternativ i `docs/known-issues.md`: (a) `VIEWSER_ALLOW_NON_LOCALHOST=true` på Vercel-projektets Preview- + Production-env (snabbast, men bekräftar `no auth, no rate limit, no public deploy`-modellen på publik URL), (b) host-whitelist via ny `VIEWSER_ALLOWED_HOSTS`-env (mer kontrollerat), (c) ADR-beslut om Viewser-på-Vercel auth-strategi (långsiktig).
3. **Backend-handoff verification deep-dive** (icke-akut, lämplig för cloud-grind eftersom det är read-only audit + 1 docs-uppdatering). Audit 2026-05-26 verifierade Gap 1 + 3 + 11 som stängda i `docs/backend-handoff.md`. Gap 2 + 4 + 5 + 9 + 10 markerade "behöver verifieras". Gap 6 + 7 sannolikt fortfarande öppna. Gap 8 delvis (PR #117 hero-mp4 men `<video>`-rendering på genererad sajt ej granskad). ~30 min audit per gap genom Grep + Read; uppdatera tabellen i `docs/backend-handoff.md` med verifierat status. Kräver inte `OPENAI_API_KEY`.
4. **Vidare current-focus.md slim** (~60-80 KB möjligt enligt repo-hygiene-städ-agenten). Filen är nu 104 KB efter T0+T1+T2 (tier 0 = revert CRLF, tier 1 = arkivera 2026-05-19 scout reports + handoff, tier 2 = slim 147→104 KB). Återstående: arkivera 2026-05-22-blocket + bevara bara senaste 30 dagars commits-listan i 'Sedan c0b59fbe...'-sektionen.

**Redan landat (tidigare session-status korrigerad 2026-05-26 PM):**

- Lane 2 LLM contract propagation — KLAR. B137 + B138 stängda 2026-05-21 (commits `432d2ab` + `299257d` + `da79056`), B141 stängd 2026-05-21 (PR #52 / `5dfa2c7`), B139 + B140 stängda 2026-05-22 (`eb5a81d` + `b93ed50`). Regression-net `tests/test_llm_contract_propagation.py` lade till via PR #84 (`0205212`) 2026-05-25. WIP-branchen `cursor/jakob-be-llm-contract-propagation` (`7847e5c`) är därmed obsolet och raderad från `origin`. **Förra sessions handoff-noten "Lane 2 parkerad WIP" var stale.**
- Lane 4 Golden Path eval — KLAR. Levererad via PR #110 (`1f8966a feat(evals): add deterministic golden path scorecard and embeddings gate`). `scripts/run_golden_path_eval.py` är aktiv och användes 2026-05-26 PM för att verifiera naprapat-fixen (5.83 → 6.81, gate `no-go` → `go`). WIP-branchen `cursor/jakob-be-golden-path-eval` (`3bee355`) på origin är obsolet och kan raderas — operatörsbeslut, inte agent-action.

**Parkerade lanes (väntar trigger):**

- Path B / section-driven renderer — kräver Lane 2 mergad först (delar `scripts/build_site.py`).
- Christophers `GAP-backend-build-trace-endpoint`-PR — Jakob är reviewer när Christopher öppnar PR från `christopher-ui` mot `main`.
- Sajtmaskin inspiration Scout — lokalt-only (kräver `sajtmaskin.rar` på operatörens maskin).
- Backend-Gap 4 + 5, Sprintvakt V1.3, B125 preview-fallback (om Stackblitz-agenten inte plockar upp det) — öppna men ej akuta.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project
DNA V2 tills en sprint är formellt vald.

Startprompt för nya agenter:
[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md).
Föregående produkt-läge:

Föregående verified state: `84bf9dde512ce171abc27ff982b13e43ff8511a1`
(2026-05-25 natt, **PR #75 Sprintvakt V1.1+V1.2+V1.2.1 + CI-hardening +
Backoffice industry coverage + docs sync** mergad ovanpå Christophers PR
#71 Front 1-4 + wizard minimalism). Plus `6649b51` closing-round
docs-sync ovanpå. Det var utgångspunkten för recovery #76 + inbox #77
som sedan stapla des ovanpå `jakob-be`.
Föregående produkt-läge:

Föregående verified state: `cb5c837548125bd94740f19e3b4a7acfa89b44cf`
(2026-05-25, **PR #70 Sprintvakt V1 koordineringsserver mergad ovanpå
parallell-team-uppsättning och restaurant-hospitality Week 1**) —
introducerade Sprintvakt-systemet (workboard, MCP-server, collision-
checker, gap-modell). Den runtiden var hela utgångspunkten för PR
#71 + #75 som sedan landade ovanpå.
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

> **Tidigare djup-historik:** verified-state-paragrafer som täckte
> 2026-05-15 till 2026-05-21 har flyttats till
> [`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md)
> för att hålla denna fil hanterbar (samma metod som `docs/handoff.md`
> fick i historiken — se `git log --follow docs/current-focus.md` för full kontext).

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

## Föregående checkpoint

### 2026-05-25 UTC — current-focus.md före `2057241`

Last verified state: feature-branch `b146-port-section-dispatcher`
(2026-05-25 **kväll**, B146-port: Christophers PR #105 + #108
section-arkitektur portad ovanpå jakob-be:s PR #107 split). `main`
HEAD är `84bf842`; `jakob-be` HEAD är `ee2a91e`. PR mot `jakob-be`
öppnas härnäst, följt av en sync-PR `jakob-be → main` när feature
PR:n mergat. Bug-räkning: **19 aktiva / 5 unknown / 114 stängda**
(B146 stängd via denna port).

**Kvällens fönster — B146 + Phase 3 port:**
- `packages/generation/build/dispatcher.py` (ny, ~370 rader): section-id
  registry, `_SECTION_TREATMENTS_BY_VARIANT`, `_treatment_for_section`,
  `_operator_pin_for_section`, `_load_scaffold_sections`,
  `_section_renderer_kwargs`, `_call_section_renderer`,
  `render_route_generic`.
- `packages/generation/build/renderers.py`: utvidgat från 2357 → ~4700
  rader. Alla ~30 nya `render_section_*` + uppdaterade page renderers
  (`render_home` etc.) från Christophers main-versioner. Initial
  registrering av basic sections vid modul-slut.
- `scripts/build_site.py`: utökade re-exports + `__getattr__`-shim så
  `from scripts.build_site import render_section_X` fortsätter fungera
  utan att vi listar alla 46 namn manuellt.
- Phase 3 backend: `_apply_directives_fields` i resolve.py additivt-mergar
  `directives.sectionTreatments`; `plan.py` får `_SECTION_TREATMENTS_CATALOGUE`
  och prompt-update; schema-bump i `governance/schemas/project-input.schema.json`.
- ADR 0031 från main (PR #108 section-treatments) renumrerad till
  **0032** eftersom jakob-be:s 0031 (Steward auto-bump, PR #106) var
  äldre. Renumber-not i ADR-toppen + uppdaterade referenser i alla
  source-/test-/doc-filer som pekade på 0031:section-treatments.
- Wizard-UI: `treatment-options.ts`, `wizard-types.ts`,
  `wizard-payload.ts`, `steps/visual-step.tsx`, `demo-answers.ts`,
  `wizard-constants.ts` (113 rader Phase 3-additioner ovanpå PR #105:s
  cherry-pickade 126), `docs/contracts/wizard-discovery.v2.md`.
- Tester: `test_section_treatments_{prompts,propagation,resolve}.py`,
  `test_section_renderer_registry.py`, `test_project_input_schema.py`
  (utökat). 126 nya cases passerar.

**Dagens fönster (eftermiddag) — 4 PRs landade i `jakob-be` + sync-PR
#103 till main:**
- PR #97 — pedagogiskt preview-fel i local-next mode (404/missing_artifacts mapping)
- PR #100 — per-siteId build mutex (Map ersätter global inFlight) → stänger B116
- PR #101 — StackBlitz embed unblocker (cross-origin-isolated permissions policy)
- PR #104 — honor preview mode end-to-end + mode-aware progress copy
- PR #103 — sync-merge `jakob-be → main` (16 commits totalt)

Christopher-koordination: `origin/christopher-ui` är `399cf39` och
ligger **21 commits framför `origin/main`** (har inte pullat sync-PR
#103). Senaste commit `[scope-leak]`-taggad. Meddelande postat till
hans Sprintvakt-inbox 2026-05-25 (`msg-0007-ae0ac0`) om
rebase-behov. PR mot main blockerad tills han har merge:at + löst
konflikter i `apps/viewser/components/viewer-panel.tsx`.

**Föregående checkpoint (samma dag):** `2a5d2e5` (morgon, Sprintvåg 1+2:
fem grind/scout-PRs landade på `jakob-be` inom 2 timmar — #81 B83
service slug, #82 Lane 3 Embeddings readiness audit, #80 B85 stdout
contract, #79 B87 model fallback warning, #83 B72+B75 status-sync).
`origin/main` låg då på `6649b51`. Bug-räkning vid det
tillfället: 19 aktiva / 112 stängda.

PR #77 (agent inbox) mergades med 5 reviewfynd-fixar i samma squash
(symlink-resistens, deterministic id, idempotent ack, ordinal > 9999,
UTC-aware since-filter). PR #78 (candidate provenance) lyfte fyra
helpers till `scripts/candidate_generation_metadata.py`, lade
provenance-sidecar `.meta.json` per kandidat, och defaultade
Backoffice-checkbox för LLM-call till `False` (operatören väljer aktivt
att kalla LLM). `b12c164` fixade en latent bugg i `_load_gap_from_file`:
gap-parsern returnerade backslashes från `\[runId\]`-escape vidare till
`sanitize_repo_path`, vilket gav korrupta paths (`[runId/]`) i
`paths_overlap` + `generate_agent_prompt`. Hela pytest-suiten är grön;
ruff 0 findings; `python scripts/sprintvakt_check.py --strict` ger
`Sprintvakt check: OK`.

### 2026-05-25 UTC — current-focus.md före `ee31eb1`

Last verified state: `ee31eb1` (2026-05-25 UTC, steward-auto efter PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime smoke-lock + golden-path eval (#112, #109, #110)).
Nya PRs sedan föregående checkpoint: PR #55 — fix(viewser): stale run-following och
artefakt-panel; PR #59 — feat(backoffice): add read-only asset graph lens; PR #60 —
tooling: Starter Candidate Auditor v1 (read-only); PR #61 — docs: add team parallel
workflow and ownership map; PR #62 — feat(viewser): integrate christopher-ui builder
workflow; PR #63 — feat(discovery): respect wizard directives — useCustomColors +
scaffoldHint (Gap 1 + 3); PR #64 — docs(ownership): add branch-naming conventions for
parallel team work; PR #66 — fix(assets): sourceUrl uploads with stream-safe fetch
(supersedes #65); PR #67 — ci: add AI bug review workflow step; PR #68 — feat(week1):
restaurant-hospitality scaffold + 11 soft dossiers + 14 variants (fantastic sites W1);
PR #70 — feat(tooling): add Sprintvakt V1 coordination guard; PR #71 — feat(viewser):
Front 1-3 + wizard minimalism — preview, iteration & polish; PR #75 — feat: Sprintvakt
V1.1+V1.2 + CI hardening + industry coverage + docs sync (post-PR70 batch); PR #76 —
fix(backoffice): recover regression tests and catch-all coverage status; PR #77 —
feat(tooling): add Sprintvakt agent inbox (post/list/ack); PR #78 — fix(backoffice):
harden candidate generation provenance and defaults; PR #81 — fix(grind): close B83
service slug collision; PR #82 — docs(scout): embedding readiness audit 2026-05-25; PR
#80 — fix(grind): close B85 stdout contract drift; PR #79 — fix(grind): close B87 model
fallback warning; PR #83 — docs(grind): close B72 + B75 status-sync to Stängda; PR #84 —
test(generation): contract regression net for B137-B141 + extend B139 tone fallback; PR
#87 — feat(backoffice): add one-click eval smoke runs; PR #89 — feat(eval-probe): add
scaffold-selection probe + docs; PR #88 — fix(viewser): make preview mode drive local
iframe headers; PR #92 — fix(viewser): handle quoted-with-comment + $VAR expansion in
dev-dispatcher .env-parser; PR #93 — feat(builder): wire menu+booking renderers so
restaurant-hospitality builds; PR #94 — docs(dossiers): import-readiness scope-doc for
Sajtmaskin material; PR #95 — feat(evals): add cafe-bistro to FULL_CASES so full suite
covers all 3 on-disk scaffolds; PR #97 — fix(viewser): pedagogical preview-error in
local-next mode + soft transport-mismatch warning; PR #99 — docs(adr): 0030
preview/deploy-providers are adapters, not canonical runtime; PR #98 — chore(tooling):
lucide-react cross-policy lock + ADR 0021 upstream-issue recheck + B145 entry; PR #100 —
fix(viewser): per-siteId build mutex so unrelated sites can build in parallel; PR #101 —
fix(viewser): cross-origin-isolated permissions policy + dispatcher https signal; PR
#102 — fix(evals): cherry-pick timeout-hardening + helper API from #96; PR #104 —
fix(viewser): honor preview mode end-to-end + mode-aware progress copy; PR #103 —
sync(jakob-be -> main): 5 produkt + 6 härdning + 2 docs (13 commits); PR #105 — Live
Build Sync + Restaurant Path A + Wizard polish + Side-by-side preview; PR #106 —
feat(steward): auto-bump current-focus + handoff on PR merge to main (ADR 0031); PR #107
— refactor(builder): extract page renderers from build_site.py to
packages/generation/build (B13a step C); PR #108 — Phase 3 — section-treatments
operator-pin + scout-driven polish; PR #112 — feat(b146): port Christopher's
section-arkitektur ovanpå PR #107-splitten; PR #109 — test(builder): lock runtime
scaffold smoke coverage on jakob-be; PR #110 — feat(evals): add deterministic golden
path scorecard and embeddings gate; PR #111 — fix(agents): correct python3-venv package
name for Ubuntu Noble; PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime
smoke-lock + golden-path eval (#112, #109, #110).

### 2026-05-26 UTC — current-focus.md före `858f8e8`

Last verified state: `858f8e8` (post-merge `jakob-be` HEAD, 2026-05-26 ~13:15 UTC, merge av PR #117 — `feat(viewser): mobile responsive — foundation + polish + final (fas 1+2+3 + scout passes)` + PR #119 dossier intake model review + docs-hygien T0+T1 ovanpå).

Nya PRs / direkta commits till `jakob-be` sedan föregående checkpoint (`50217e3`):

- `a337f01` (du / Jakob, 2026-05-26 ~01:55) — committade `docs/reports/pr113-ours-conflict-audit-2026-05-26.md` (audit-rapport: PR #113 `--ours`-konfliktresolution är clean; symbol-complete port, 14/16 filer differar bara genom ADR 0031 → 0032 renumber + path-refs).
- `f2e84b0` (direkt commit, 2026-05-26) — `fix(builder): close B148+B149+B150 from external read-only audit`. B148 nav `_nav_items_from_scaffold` letar contact-path från scaffold istället för att hårdkoda `/kontakt` (restaurant-hospitality bites). B149 Intent Guard tokeniserar candidate_terms för exact-token-match (substring-match gav `"bar" in "barber"` false-positives). B150 `_normalize_business_type` collapsar multi-word slugs via dash-prefix-walking. 14 nya regression-tester.
- `e6a23a3` — `docs(steward): move B148+B149+B150 to Stängda with fix=f2e84b0`.
- `c85ae70` — `fix(builder): close B97 + B98 (contact-page copy + om-oss areas-block per scaffold)`. B97 ny `_CONTACT_PAGE_HERO_BODY_BY_VARIANT`-dict + helper för per-variant (shop/booking/quote) × language (sv/en) kontakt-page hero body — eliminerar "Beskriv jobbet kort … med tider och offert"-läckaget för e-handel/booking. B98 suppress `Områden vi arbetar i` för `ecommerce-lite`. 9 nya regression-tester.
- `3b5a798` — `docs(steward): move B97 + B98 to Stängda with fix=c85ae70`.
- `6d4a096` — `fix(brief): close B90+B91+B92+B93 (language/location/business-type cluster)`. B90 ta bort "a"/"an" ur ENGLISH_HINTS. B91 `_ENGLISH_TO_SWEDISH_CITY` (Gothenburg→Göteborg, Helsinki→Helsingfors, Copenhagen→Köpenhamn) på sv-byggen. B92 bare `naprapat`/`naprapath` → `naprapat` (sole-practitioner), bara explicita `*-clinic`/`naprapatklinik` → `naprapatklinik`. B93 22 nya multi-word engelska business-slugs → svenska. ~20 nya regression-tester.
- `49f5513` — `docs(steward): move B90+B91+B92+B93 to Stängda with fix=6d4a096`.
- `8c057b1` — **PR #116 squash-merged till `jakob-be`**, `feat(backoffice): add dossier candidate intake from local files`. 1453 inser / 21 del, 8 filer, ny `scripts/dossier_candidate_intake.py` (614 rader) + ny `tests/test_dossier_candidate_intake.py` (269 rader).
- **PR #117 merged via lokal merge-commit till `jakob-be`** — `feat(viewser): mobile responsive — foundation + polish + final (fas 1+2+3 + scout passes)`. 31 commits från `christopher-ui`, 100 % UI-only mot merge-base `3bedddd` verifierat. 35 filer ändrade, +1866 / -252 rader. Konfliktlösning: `docs/agent-inbox.jsonl` (append båda sidors meddelanden) + `docs/current-focus.md` (kombinerad version — den här filen). Tre AI Bug Review-fynd (B151+B152+B153) registrerade efter merge.

Christophers commits från PR #117 (mobil-anpassningen, mergebase→HEAD):

- `a1d1a1f` docs(inbox): ack msg-0008 (scope-process-PR-105) + msg-0009 (b146-port).
- `ea62e45` docs(gap): open GAP-viewser-mobile-responsive-foundation. Pausar tillfälligt
  `GAP-viewser-pipeline-status-polling` + `GAP-viewser-side-by-side-preview` till queuedGaps.
- `31a888a` feat(viewser/ui): mobile foundation — `pb-safe`/`pt-safe`/`px-safe`,
  `min-tap` (44px Apple HIG), `touch-visible`, `bottom-sheet-handle` + `sheet.tsx`
  bottom-sheet-stöd.
- `3b2420d` feat(viewser/wizard): mobile pass — `validationError` alltid synlig,
  close/konsol/popover-close min-tap, wizard-padding `px-5 sm:px-10`, footer
  `pb-safe-or-4`, `PayloadAlignmentPopover` clamp, moodboard/produktbild-delete
  `touch-visible`, `site-header` `pt-safe`.
- `9593769` feat(viewser/builder): mobile pass — `FloatingChat` bottom-sheet på mobil
  med drag-handle + pb-safe, 56×56 FAB minimerat, composer-textarea `text-base
  sm:text-[13px]` (iOS-zoom-fix), `BuilderActions` `hidden md:flex`,
  `SiteInspectorSheet` bottom-sheet på mobil + tabs `overflow-x-auto`.
- `fb87699` docs(focus) + governance-fixar (fidelity-term ut, FloatingChat-syntax).
- `b0140b1` docs(inbox): msg-0010 notify jakob-be om PR #117 + pausade gaps.
- `62437de` docs(gap): open GAP-viewser-mobile-responsive-polish (fas 2).
- `d7ca301` fix(viewser/prompt): PromptBuilder composer tap-targets + iOS-zoom-fix.
- `6b2d68c` fix(viewser/wizard,builder): systematic tap-target upgrade — InlineHelpButton,
  AssetDropzone "Välj fil", DirectivesPreview Copy, QuickPromptButton.
- `64445bb` fix(viewser/canvas): hero typography scale + console-drawer safe-area.
- `712a3c2` fix(viewser/dialogs): mobile-friendly grids + iOS-zoom-fix på inputs
  (ai-image-generator, asset-uploader, color-picker — alla responsiva).
- `e05c443` docs(gap): complete fas 1+2 (in-review), open fas 3 — final polish.
- `18d84f5` fix(viewser): mobile responsive height + compare-modal swipe A/B.
- `f850882` feat(viewser/canvas): device-toggle desktop preview (375/768/1024/Full)
  + edge-pulse motion polish.
- `8724798` chore(viewser): term-coverage compliance (Device-typ slimmad, scroll-pos
  detection).
- `6d0c896` docs(gap): complete fas 3, open scout-fixes GAP.
- `cb6f43d` fix(viewser): scout P0 batch — pb-safe-or-3 utility, wizard iOS-zoom,
  steg-chips min-tap, footer-knappar min-tap.
- `6e06129` fix(viewser): scout P1 batch — hydration mismatch, layout-flash, iOS
  keyboard `useKeyboardInset`, ModePill min-tap, A/B-pill desync, FAB → composer
  focus-flytt, Site Inspector drag-handle, Inspector + FloatingChat mikro-kontroller,
  iPad portrait zoom-risk.
- `420efb0` chore(viewser): lint + term-coverage compliance för scout-fixes.
- `59eed4c` feat(viewser): mobile hero stacked flow + SM-mobile.mp4 banner — adress
  fynd från manuell test på iPhone 14 Pro 393×852 (3D-objekt bakom rubrik,
  `<br />`-radbrytning, sömlöst hero-flöde).
- `c5d1ba9` fix(viewser): scout pass 4 P1-batch — hero safe zone på iPhone SE,
  wizard företagsnamn-asterisk borttagen (WCAG 2.2), composer pb-safe-or-4.
- `6f24786` + `9964f16` + `07973ca` — docs/focus + docs/inbox handoff-promp till jakob-be.

Inga off-limits-paths rörda i någon av faserna eller scout-fixes-passet
(`scripts/`, `packages/generation/`, `apps/viewser/app/api/`, `apps/viewser/lib/`,
`middleware.ts`, `next.config.ts`, `package.json` — alla intakta verifierat mot
merge-base `3bedddd`).

AI Bug Review-fynd från PR #117 (filerades direkt som Stängda i samma session — se docs/known-issues.md):

1. B151 (Medel) — `floating-chat.tsx` useIsMobileViewport kallar matchMedia-listenern (addEventListener-signaturen) ovillkorligt. iOS Safari <14 stödjer inte den signaturen → chat kan krascha på äldre iOS. Fix: feature-detect mot addListener-fallback.
2. B152 (Medel) — `compare-preview-modal.tsx` mobile snap-scroll har `w-full` per pane + `gap-2` → kan overflowa och bryta one-pane-snap. Fix: `w-screen` eller `w-[calc(100%-0.5rem)]`.
3. B153 (Låg) — `viewer-panel.tsx` sessionStorage-hydration restorerar `'mobile'`/`'tablet'`/`'laptop'`-preset men hoppar `'full'`. Fix: inkludera `'full'` i accepterade värden.

Operatör-beslut 2026-05-26 ~13:10: jakob-be-orchestrator tar dessa själv (samtidigt med merge) trots att de ligger i Christophers lane — för momentum. Christopher informerad via inbox msg-0010-6f4bed + uppföljnings-msg efter fixarna landat.

Plus: ny aktiv bugg **B147 Medel-Hög** filerades (Vercel preview wizard 403 via `assertLocalhost` på `*.vercel.app`). **Operatörsbeslut a/b/c krävs** innan kod-fix kan väljas. Cross-ref: `docs/reports/b125-preview-fallback-decision-2026-05-22.md`.

Net bug-räkning post-#117-merge + B151-B153-fix: bumpning skedde i samma session, slutläge anges i Stängda-sektionen av `docs/known-issues.md`.

`origin/jakob-be` är 8+ commits före `origin/main`. Sync-PR `jakob-be → main` är queued men ej öppnad — Christophers `christopher-ui` är nu mergad (genom #117), så den blockaren är löst. Kvarvarande blockare: B147-vägval + Vercel-production-branch-flip (`docs/operations/vercel-production-branch-todo.md`).
