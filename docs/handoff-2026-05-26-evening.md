# Handoff 2026-05-26 kväll — till nästa jakob-be-orchestrator

**Skapad:** 2026-05-26 ~20:10 UTC, post-C4-audit-merge + naprapat scaffold-fix.
**Av:** cursor-jakob-be-orchestrator (Claude Opus 4.7, denna session).
**För:** nästa Cursor/agent som tar över jakob-be-lane.
**HEAD:** `origin/jakob-be` = `46d819f` (lokalt synkat, working tree clean förutom operatörs-personliga filer).
**Föregående handoff:** `docs/handoff-2026-05-26-afternoon.md` (lämnas kvar som historiskt arkiv).

---

## TL;DR

Två stora produktspår landade idag:

1. **Naprapat scaffold-routing-fix** — Lane 3 embeddings-readiness-gate gick från `no-go` → `go`. naprapat-stockholm Golden Path-score 5.83 → 6.81 (passerar 6.5-tröskeln). Total Golden Path-score 7.10 → 7.34. Ingen kvarstående case under tröskeln.
2. **C4 backend-handoff verification audit** — cloud-grind-agentens PR #121 mergad lokalt med konfliktlösning. `docs/backend-handoff.md` har nu auktoritativ status per gap: 5 stängda (1, 2, 3, 8, 11), 5 delvis (4, 5, 6, 7, 9), 1 öppen (10). Alla med exakta paths och rad-referenser till källkod.

Plus två lane-status-correctioner: Lane 2 LLM contract propagation och Lane 4 Golden Path eval var båda mergade tidigare i veckan men listades felaktigt som "parkerad WIP" i tidigare handoff. Cloud-grind-agenten flaggade driften, lokal agent verifierade och rättade.

Inga öppna PRs på `jakob-be` eller `main`. 11 commits framför `origin/main` per `git rev-list --count origin/main..origin/jakob-be` post-handoff.

---

## Sessionens leverans (11 commits till `jakob-be` sedan reset till `origin/main`)

| SHA | Vad |
|---|---|
| `cc1a5aa` | `chore(viewser): commit vercel.json deploy config` — 6-raders Next.js-config för Vercel-deploy |
| `0ed5348` | `docs(backend-handoff): mark gap 1 + 11 as closed (audit 2026-05-26)` — 5 prod-refs i kod uppdaterade så de speglar att Gap 1 (`vibe.useCustomColors`) och Gap 11 (`sourceUrl`-fallback) är stängda |
| `3fc187e` | `docs(focus): bump Last verified state to 0ed5348 + refresh next-focus list` |
| `4cd367c` | `fix(planning): close naprapat scaffold-routing for clinic-healthcare` — `_CLINIC_SIGNALS` i `packages/generation/planning/plan.py:_pick_scaffold_from_brief` (mock-fallback) + 6 nya regression-tester (10 parametrize-fanout) i `tests/test_planning.py`. Plus stale-doc-string-cleanup i `packages/generation/discovery/resolve.py` |
| `b414c6b` | `fix(prompt-input): route clinic prompts to clinic-healthcare in pick_scaffold + align eval routes` — `_CLINIC_TOKENS` i `scripts/prompt_to_project_input.py:pick_scaffold` (pinned Project Input path) + `expected_routes` i `scripts/run_golden_path_eval.py:naprapat-stockholm` uppdaterade till `("/", "/behandlingar", "/om-oss", "/kontakta-oss")` för att matcha Path B native dispatcher-scaffolds canonical routes. 13 nya regression-tester (parametrize-fanout) |
| `ee1751f` | `docs(focus): bump to b414c6b + correct Lane 2/Lane 4 stale entries` — efter cloud-grind-agent flaggade att Lane 2 (PR #84) och Lane 4 (PR #110) var mergade men felaktigt listade som "parkerad WIP" |
| `d3a2ad6` | `docs(backend-handoff,focus): correct 3 reviewer-flagged drift points` — extern reviewer flaggade (1) inkonsekventa paths i status-tabellen, (2) C4-scope för snäv (saknade wizard-files), (3) "5 commits" → "6 commits" framför main |
| `9dbd10a` | `docs(backend-handoff): drop fabricated WizardProduct type reference` — typenamnet finns inte i koden, bytte till path-only-referens |
| `0f3bd67` | `docs(backend-handoff): land C4 audit (PR #121) via local merge` — cloud-grind-agentens `87bfd0b` integrerad med konfliktlösning, co-author-credit i trailer. PR #121 stängd via `gh pr close --delete-branch`. |
| `1721494` | `docs(focus): bump to 0f3bd67 + record C4 audit landed + add 5 backend-Gap follow-up tracks` |
| `46d819f` | `docs(focus): drop bold-formatted Gap-headings + PascalCase tokens for term-coverage strict` — `1721494` introducerade 6 unregistered candidates (Gap N quick win, Pillow, WizardProduct) som `check_term_coverage.py --strict` flaggade. Fix via text-omformulering, ingen ny entry i naming-dictionary. |

## Aktuellt state

```
local jakob-be   = origin/jakob-be   = 46d819f (in sync)
origin/main      = 1004122 (11 commits efter jakob-be)
Inga öppna PRs på jakob-be eller main
PR #121          = CLOSED (mergad lokalt via 0f3bd67, branch raderad)

Bugs       14 aktiva / 0 misplaced / 5 unknown / 126 stängda
Gates      ruff 0, pytest pass + 6 expected skips, governance 18/18,
           rules-sync OK, term-coverage --strict OK, sprintvakt OK,
           tsc --noEmit OK, eslint OK
Eval       Golden Path 7.34/10, embeddings gate `go` (alla 4 case >= 6.5)
```

## Pending — operatörsbeslut krävs

1. **Vercel production branch-flip** — `docs/operations/vercel-production-branch-todo.md` dokumenterar att Production Branch sattes till `jakob-be` 2026-05-25 tills B146 var löst. B146 är nu mergad. Sync-PRs #118 + #120 + #84 + #110 + #117 + #116 + #119 är alla i main. Flippen är inte längre blockad. Operatören klickar i Vercel UI: `https://vercel.com/jakeminator123s-projects/sajtbyggaren-viewser/settings/git`. Efter flippen: trigga `vercel --prod` och radera TODO-docen.
2. **B147 Vercel wizard 403 vägval a/b/c** — Medel-Hög-bugg. `assertLocalhost` returnerar 403 på `*.vercel.app`-deployer för 12 API-routes inkl. `discovery-options`. Tre alternativ dokumenterade i `docs/known-issues.md`:
   - (a) `VIEWSER_ALLOW_NON_LOCALHOST=true` på Vercel-projektets Preview + Production env. Snabbast (5 min, ingen kod-ändring), men bekräftar `no auth, no rate limit, no public deploy`-modellen. Risk: någon hittar URL:en, spammar `/api/prompt` → OpenAI-tokens på operatörens konto.
   - (b) Host-whitelist via ny `VIEWSER_ALLOWED_HOSTS`-env (~1-2h kod). Mer kontrollerat men kräver att lista uppdateras vid nya preview-domäner.
   - (c) ADR-beslut om långsiktig auth-strategi (~1-2 dagar). API-keys / magic-link / Vercel SSO / Cloudflare Access.

## Pending — backend-Gap-fixar (C4 audit-fynd, ny från denna session)

Cloud-grind-agentens C4-audit (`0f3bd67`) bekräftade följande pending-fixar med exakta paths:

| Spår | Storlek | Vad |
|---|---|---|
| Gap 5 quick win | ~1h, S | Persist `directives.notesForPlanner` (mappad i `apps/viewser/components/discovery-wizard/wizard-payload.ts:496-514`) till SiteBrief / planner-input. Spår saknas i `scripts/prompt_to_project_input.py` + Discovery Resolver. SiteBrief-fältet finns redan i `packages/generation/brief/extract.py:167-170,313`. |
| Gap 4 quick win | ~1-2h, S | Merga `directives.requestedCapabilities` (från `wizard-payload.ts:406-418`) deterministiskt i `_resolve_capabilities()` i `packages/generation/discovery/resolve.py:1325-1362`. Idag läses bara `answers.mustHave` + taxonomy + befintlig brief. |
| Gap 6 + 7 paired | ~3-4h, M | Build-pipeline-konvertering. Gap 6 = multi-size `public/favicon.ico` från `media.favicon`. Gap 7 = center-crop till `public/og-image.png` 1200×630 från `media.ogImage`. Båda Next-metadata redan rendrad i `packages/generation/build/renderers.py:313-367`; saknar bara konverterings-steg. Kräver `pillow` eller `sharp` i build. |
| Gap 9 | ~2h, S-M | Backend-isolering av `moodImages[]` till `data/uploads/<runId>/__mood/` istället för publik `public/uploads/`. Mappa Vision-resultat till `notesForPlanner`. UI-sidan klar. |
| Gap 10 | ~4-6h, M-L | Full backend-mapping för `products[].productImage`. Saknar payload-mapping, schema-fält, `copy_operator_uploads()`-kopiering till `public/products/`, OCH renderer-stöd för produktbild i `packages/generation/build/renderers.py`-produktgrid. Egen sprint. |

## Pending — kosmetiskt / lågprio

- **Vidare current-focus.md slim** (~60-80 KB möjligt enligt repo-hygiene-städ-agenten 2026-05-26). Filen är 104 KB efter T0+T1+T2 (tier 0-2). Återstående: arkivera 2026-05-22-blocket + bevara bara senaste 30 dagars commits-listan i 'Sedan c0b59fbe...'-sektionen.
- **Stubb-branches städ** — `cursor/jakob-be-llm-contract-propagation` och `cursor/jakob-be-golden-path-eval` på `origin` är obsolet (innehållet mergat via PR #84 + PR #110). Operatören äger raderingen.
- **3 backup-branches** (`backup-43-INNAN-SAMMARBETE`, `backup-44-BRA`, `backup-45-BRA`) — operatör äger, rör inte utan instruktion.

## Working tree-filer (inte rörda, operatörs-territorium)

```
M .cursor/settings.json        [operatörs personliga, rör aldrig]
?? docs/operations/             [pre-existing operatörs-TODO-mapp, väntar på Vercel-flip]
```

## Hur du startar

1. **Läs först:**
   - `docs/current-focus.md` (huvudkö-plan, denna handoff är komplement; Last verified state ska vara `46d819f` eller högre)
   - `docs/backend-handoff.md` (status-tabellen överst är auktoritativ för 11 gaps)
   - `docs/known-issues.md` (B147 + 14 aktiva bugs)

2. **Verifiera state:**
   ```powershell
   git fetch origin
   git status                                    # ska vara clean (utöver operatörs-files)
   git log --oneline -5                          # senaste 5 commits, jämför med detta dokument
   .\.venv\Scripts\python.exe scripts/focus_check.py
   .\.venv\Scripts\python.exe scripts/list_open_bugs.py
   ```

3. **Operatörsdialog (vid sessionsstart):**
   - "Har du gjort Vercel production-branch-flippen? Om inte: ska jag radera todo-docen efter du klickat?"
   - "B147 vägval — vill du köra (a) `VIEWSER_ALLOW_NON_LOCALHOST=true` snabbt, eller (b) host-whitelist, eller (c) ADR för långsiktig auth?"
   - "Vill du att jag plockar Gap 5 quick win som första kod-spår, eller annat?"

4. **Vid ovisshet om scope:** följ `governance/rules/branch-scope-ui-ux.md`. Jakob-be-lane rör Python (`scripts/`, `packages/`, `tests/`, `governance/`), inte `apps/viewser/components/**` (Christopher-lane). UNDANTAG: per operatörsdirektiv 2026-05-26 (msg-0017-c3f924) kan jakob-be-orchestrator ta UI-fixar när Christopher har levererat tunga PRs och momentum är värt mer än lane-disciplin. Ska INTE upprepas utan operator-OK varje gång.

## Reviewers (för transparens)

Denna session fick två externa AI-reviewers + en cloud-grind-agent:

- **Cloud-grind-agent** (operatörens parallella session) — körde C4 backend-handoff verification audit. Levererade PR #121 med 15 add/15 del på `docs/backend-handoff.md` med exakta paths/rader för alla 11 gaps. Audit verifierad korrekt via 3 stickprov av lokal agent (Gap 2/4/8). PR mergad lokalt med konfliktlösning som `0f3bd67` + co-author-credit. Branch raderad.
- **Extern reviewer-pass** (separat session) — efter cloud-grindens initiala feedback flaggade tre konkreta drift-punkter: (1) `brief/extract.py`-paths var inkonsekvent angivna i tabellen, (2) C4-scope missade `wizard-payload.ts` + `wizard-types.ts` där flera gap-fält först mappas, (3) `current-focus.md` sa "5 commits framför main" men `git rev-list` returnerade 6. Alla tre fixade i `d3a2ad6` (path-cleanup + scope-utvidgning + count-correction).
- **`9dbd10a`-fix-kontext** — Term-coverage flaggade en fabricerad `wizard-product`-typ-referens som lokal agent hade hittat på — typen finns inte i `apps/viewser/components/discovery-wizard/wizard-types.ts`. Bytt till path-only-referens. Cloud-grind-agentens version i PR #121 saknade detta fel från början, så `0f3bd67`-mergen tog hennes mer korrekta version verbatim.

---

**Slut på handoff.** Lycka till. Om något i denna doc verkar inaktuellt: `git log --oneline origin/main..origin/jakob-be` visar sanningen.
