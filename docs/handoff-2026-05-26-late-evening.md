# Handoff 2026-05-26 sen kväll — till nästa jakob-be-agent

**Skapad:** 2026-05-26 ~23:20 UTC, post docs-slim + branch-model-clarification.
**Av:** cursor-jakob-be-agent (Claude Opus 4.7, denna session).
**För:** nästa Cursor/agent som tar över jakob-be-lane.
**HEAD:** `origin/jakob-be` = `f7c437e` (lokalt synkat, working tree clean förutom operatörs `.cursor/settings.json`).
**Föregående handoff:** `docs/handoff-2026-05-26-evening.md` (lämnas kvar som historiskt arkiv).

---

## TL;DR

Två saker landade denna session:

1. **`docs/current-focus.md` slim** — från 1414 → 207 rader. "Föregående produkt-läge"-kedjan (2026-05-13 → 2026-05-25) och de stale "Current active sprint" / "Next action" / "Blocked items" / "Queue"-blocken flyttade till `docs/archive/current-focus-history-2026-05-26.md`. Topp-blocket + tre senaste checkpointsen kvar.
2. **Branch-modellen förtydligad i governance-källan** — `governance/rules/branch-discipline.md` skriven om för att matcha den faktiska modellen: Jakob default på `jakob-be`, Christopher default på `christopher-ui`, `main` är canonical, PR mot `main` öppnas när en ny officiell version ska in. Den gamla "main-first med backup-N"-regeln (som motsade praktiken sedan PR #61/#64) är borta. `team-workflow.md` + `docs/agent-handbook.md` synkade. `.cursor/rules/*.mdc`-speglarna auto-regenererade.

Inga produktkod-ändringar. Inga schema-ändringar. Inga öppna PRs.

---

## Sessionens leverans (1 commit till `jakob-be`)

| SHA | Vad |
|---|---|
| `f7c437e` | `docs: slim current-focus and clarify branch model` — 7 filer, +1643 / −1565 (massiv del är arkiv-flyttning). |

Filer ändrade:

- `docs/current-focus.md` — 1414 → 207 rader (slim).
- `docs/archive/current-focus-history-2026-05-26.md` — appendad med cascade-content från 2026-05-13 till 2026-05-25.
- `governance/rules/branch-discipline.md` — full rewrite för enkel branch-modell.
- `governance/rules/team-workflow.md` — uppdaterad "Grundregel" + "Steward-loop steg 8" så de matchar.
- `docs/agent-handbook.md` — uppdaterade "Fasta agentroller" + "Standard loop" steg 2-8 + "Reviewer-checklist" item 4+7 + "Parallella agenter".
- `.cursor/rules/branch-discipline.mdc` + `.cursor/rules/team-workflow.mdc` — auto-regen via `scripts/rules_sync.py`.

Operatörens `.cursor/settings.json` är fortsatt rörd men inte committad (operatörens egen fil).

---

## Aktuellt state

```
local jakob-be   = origin/jakob-be   = f7c437e (in sync)
origin/main      = 1004122 (15 commits efter jakob-be)
Inga öppna PRs på jakob-be eller main

Bugs       14 aktiva / 0 misplaced / 5 unknown / 126 stängda
Gates      ruff 0, pytest 100% pass + 6 expected skips (full suite ~3 min),
           governance 18/18, rules-sync OK, term-coverage --strict OK,
           sprintvakt OK, focus_check WARN endast pga .cursor/settings.json
Backend    7 stängda / 3 delvis / 1 öppen (Gap 4 + 5 stängda denna dag,
audit      Gap 6+7 paired, Gap 9, Gap 10 kvar)
Eval       Golden Path 7.34/10, embeddings gate `go` (alla 4 case >= 6.5)
```

---

## Pending — operatörsbeslut krävs

1. **Vercel production branch-flip** — `docs/operations/vercel-production-branch-todo.md` dokumenterar att Production Branch sattes till `jakob-be` 2026-05-25 tills B146 var löst. B146 är nu mergad. Sync-PRs #118 + #120 är i main. Flippen är inte längre blockad. Operatören klickar i Vercel UI: `https://vercel.com/jakeminator123s-projects/sajtbyggaren-viewser/settings/git`. Efter flippen: trigga `vercel --prod` och radera TODO-docen.
2. **B147 Vercel wizard 403 vägval a/b/c** — Medel-Hög-bugg. `assertLocalhost` returnerar 403 på `*.vercel.app`-deployer för 12 API-routes inkl. `discovery-options`. Tre alternativ dokumenterade i `docs/known-issues.md`:
   - (a) `VIEWSER_ALLOW_NON_LOCALHOST=true` på Vercel-projektets Preview + Production env (~5 min, ingen kod-ändring, men bekräftar `no auth, no rate limit, no public deploy`-modellen).
   - (b) Host-whitelist via ny `VIEWSER_ALLOWED_HOSTS`-env (~1-2h kod).
   - (c) ADR-beslut om långsiktig auth-strategi (~1-2 dagar).
3. **Sync-PR `jakob-be → main`** — `jakob-be` är 15 commits framför `origin/main` och bra läge för en sync nu eller efter en av Gap-fixarna nedan.

## Pending — nästa kodspår (ditt val)

I prioritetsordning från `docs/backend-handoff.md` (post-C4-audit):

1. Gap 6 + 7 paired sprint (~3-4h, M) — build-pipeline-konvertering. Gap 6 = multi-size `public/favicon.ico` från `media.favicon`. Gap 7 = center-crop till `public/og-image.png` 1200×630 från `media.ogImage`. Båda Next-metadata redan rendrad i `packages/generation/build/renderers.py:313-367`. Saknar bara konverteringssteg. Kräver `pillow` eller `sharp` i build.
2. Gap 9 (~2h, S-M) — backend-isolering av `moodImages[]` till `data/uploads/<runId>/__mood/` istället för publik `public/uploads/`. Mappa Vision-resultat till `notesForPlanner`. UI-sidan är klar.
3. Gap 10 (~4-6h, M-L) — full backend-mapping för `products[].productImage`. Saknar payload-mapping, schema-fält, `copy_operator_uploads()`-kopiering till `public/products/`, OCH renderer-stöd för produktbild i `packages/generation/build/renderers.py`-produktgrid. Egen sprint.
4. **Christophers `GAP-backend-build-trace-endpoint`-PR** — om Christopher öppnar PR från `christopher-ui` mot `main`: Jakob är reviewer. Granska scope-leak, kontrollera workboard ownership, merge.

## Pending — kosmetiskt / lågprio

- **Stubb-branches städ** — `cursor/jakob-be-llm-contract-propagation`, `cursor/jakob-be-golden-path-eval`, `cursor/jakob-be-viewser-local-next-preview`, `cursor/runtime-scaffold-smoke-8efe`, `cursor/golden-path-scorecard-888a`, `b146-port-section-dispatcher` på origin är obsolet (innehållet mergat via tidigare PRs). Operatören äger raderingen.
- **3 backup-branches** (`backup-43-INNAN-SAMMARBETE`, `backup-44-BRA`, `backup-45-BRA`) — operatör äger, rör inte utan instruktion.

---

## Working tree-filer (inte rörda, operatörs-territorium)

```
M .cursor/settings.json        [operatörs personliga, rör aldrig]
```

`docs/operations/` är fortfarande untracked (Vercel-flip-TODO-mappen). Föregående evening-handoff sa att en separat agent har raderat själva TODO-filen — verifiera om mappen är tom och kan rensas, eller om operatören vill behålla den för nästa pre-flip-period.

---

## Hur du startar

1. **Läs först:**
   - `docs/current-focus.md` (huvudkö-plan, nu slim på 207 rader; Last verified-fältet ska vara `f7c437e` eller högre)
   - `docs/backend-handoff.md` (status-tabellen överst är auktoritativ för 11 gaps; 7 stängda / 3 delvis / 1 öppen)
   - `docs/known-issues.md` (B147 + 14 aktiva bugs)
   - `governance/rules/branch-discipline.md` (NY enklare modell — jakob-be/christopher-ui default, PR mot main vid officiell version)

2. **Verifiera state:**
   ```powershell
   git fetch origin
   git status                                    # ska vara clean (utöver operatörs .cursor/settings.json)
   git log --oneline -5                          # senaste 5 commits, jämför med detta dokument
   .\.venv\Scripts\python.exe scripts/focus_check.py
   .\.venv\Scripts\python.exe scripts/list_open_bugs.py
   ```

3. **Operatörsdialog (vid sessionsstart):**
   - "Har du gjort Vercel production-branch-flippen? Om inte: ska jag radera todo-docen efter du klickat?"
   - "B147 vägval — vill du köra (a) `VIEWSER_ALLOW_NON_LOCALHOST=true` snabbt, eller (b) host-whitelist, eller (c) ADR för långsiktig auth?"
   - "Vill du att jag plockar Gap 6+7 paired som första kod-spår, eller annat?"
   - "Sync-PR `jakob-be → main` — vill du öppna den nu (15 commits framför) eller vänta tills nästa Gap-fix landar?"

4. **Vid ovisshet om scope:** följ den NYA `governance/rules/branch-discipline.md`. Jakob-agent default på `jakob-be`, rör inte `apps/viewser/components/**`, `apps/viewser/app/**/*.tsx`, `apps/viewser/public/**` utan operatörens OK (Christopher-lane). UNDANTAG: per operatörsdirektiv 2026-05-26 (msg-0017-c3f924) kan jakob-be-agent ta UI-fixar när Christopher har levererat tunga PRs och momentum är värt mer än lane-disciplin. Ska INTE upprepas utan operator-OK varje gång.

---

## Reviewers (för transparens)

Denna session var ren docs/governance-hygien:

- **Ingen Scout-pass** — ändringarna var rena docs/policy-rewrites med tydligt scope.
- Verifierat mot tester — full pytest grön (alla aktiva + 6 förväntade skips, ~3 min), targeted docs-tester grönt (test_steward_auto_bump + test_no_legacy_terms + test_docs_freshness + test_bug_scope_discipline).
- **Alla 5 gates gröna** — ruff 0, governance 18/18, rules_sync OK, term-coverage --strict OK, sprintvakt OK.

---

## Operativa observationer

- **`docs/current-focus.md` slim-metoden** — flytta gamla "Föregående produkt-läge"-paragrafer till `docs/archive/current-focus-history-<datum>.md`. Steward-auto-bump-scriptet (`scripts/steward_auto_bump.py`) appenderar nya "Föregående checkpoint"-block automatiskt vid varje PR-merge, så filen kan växa igen — nästa slim-pass bör trigga när filen är över ~500 rader.
- **Branch-modellen är nu konsistent över hela governance-stacken** — `branch-discipline.md` (källa) + `team-workflow.md` (källa) + `.cursor/rules/*.mdc` (speglar) + `docs/agent-handbook.md` (prosa) säger alla samma sak. `docs/ownership-map.md` rörde jag inte (verkar redan stämma).
- **`docs/handoff.md` (kanonisk handoff)** rensad från två stale-claims i samma session: "PR #69 öppen draft" (PR #69 är stängd) och "Direkt nästa spår — parallell sprint i 4 lanes pågår" (alla 4 lanes är klara eller har sedan-länge bytt status). Bumpningen "5 commits efter `jakob-be`" → "15 commits framför `origin/main`" speglar verkligheten.

---

**Slut på handoff.** Lycka till. Om något i denna doc verkar inaktuellt: `git log --oneline origin/main..origin/jakob-be` visar sanningen.
