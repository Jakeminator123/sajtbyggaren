# Handoff 2026-05-26 eftermiddag — till nästa jakob-be-agent

**Skapad:** 2026-05-26 ~14:10 UTC, post-PR #117-merge + B151-B153-fix + sync-PR #118 öppnad.
**Av:** cursor-jakob-be-orchestrator (Claude Opus 4.7, denna session).
**För:** nästa Cursor/agent som tar över jakob-be-lane.
**HEAD:** `origin/jakob-be` = `05a84bb` (lokalt synkat, working tree clean förutom operatörs-personliga filer).

---

## TL;DR

PR #117 (mobil-anpassning, 31 commits, Christopher) mergad. PR #116 (dossier-intake) mergad. 12 buggar stängda denna session (B97, B98, B148, B149, B150, B90, B91, B92, B93, B151, B152, B153). 1 ny aktiv (`B147`, operatörsbeslut a/b/c kvarstår). Sync-PR #118 `jakob-be → main` öppen och väntar på operatörsgranskning + merge. Alla grindar gröna.

---

## Sessionens leverans (45 commits till `jakob-be`)

| SHA | Vad |
|---|---|
| `a337f01` | Operator audit-report för PR #113 `--ours`-konflikter |
| `f2e84b0` + `e6a23a3` | B148+B149+B150 stängda (nav contact-path, Intent Guard substring, multi-word business-type) + 14 tester |
| `c85ae70` + `3b5a798` | B97+B98 stängda (kontakt-page hero per CTA-variant, om-oss areas-block per scaffold) + 9 tester |
| `6d4a096` + `49f5513` | B90+B91+B92+B93 stängda (language/location/business-type-kluster) + ~20 tester |
| `8c057b1` | **PR #116 squash-merged** — `feat(backoffice): add dossier candidate intake from local files` |
| `a2b4726` | Steward bump efter PR #116 + register PR #117 |
| `9fe9546` | Inbox `msg-0010-6f4bed` till christopher-ui (PR #117 review + 3 AI-fynd flaggade) |
| `2319ef9` | **PR #117 merge** — `feat(viewser): mobile responsive` (31 commits från christopher-ui, 100 % UI-only) |
| `4a6243a` + `1471d16` | B151+B152+B153 fixade direkt (AI Bug Review-fynd från PR #117) + 3 source-lock-tester |
| `05a84bb` | Inbox `msg-0017-c3f924` till christopher-ui (uppföljning: vi tog fynden själva) |

## Aktuellt state

```
local jakob-be   = origin/jakob-be   = 05a84bb (in sync)
origin/main      = 50217e3 (12 commits efter jakob-be)
PR #118 sync     = OPEN, MERGEABLE, mergeStateStatus UNSTABLE (CI run pending)
PR #117          = MERGED (mergeCommit 2319ef9)
PR #116          = MERGED (mergeCommit 8c057b1)

Bugs   14 aktiva / 0 misplaced / 5 unknown / 126 stängda
Gates  ruff 0, pytest pass + 6 expected skips, governance 18/18,
       rules-sync OK, term-coverage --strict OK, sprintvakt OK,
       tsc --noEmit OK, eslint OK, list_open_bugs konsistent med summary
```

## Pending — operatörsbeslut krävs

1. **Sync-PR #118** — granska body + CI checks → merge till `main`. Notera: UNSTABLE = CI fortfarande igång när PR öppnades. Vänta tills checks blir GREEN innan merge.
2. **Vercel production branch-flip** — `docs/operations/vercel-production-branch-todo.md` dokumenterar att Production Branch sattes till `jakob-be` 2026-05-25 tills B146 var löst. B146 är nu både mergad till `jakob-be` (#112) OCH till `main` (via #113 + #118 efter merge). Flip-instruktion ligger i TODO-docen. Efter flip: radera TODO-docen.
3. Vercel wizard 403 — `B147` vägval a/b/c. Medel-Hög-bugg, blockerar fungerande wizard på `*.vercel.app`-deployer. Tre alternativ dokumenterade i `docs/known-issues.md`:
   - (a) sätt `VIEWSER_ALLOW_NON_LOCALHOST=true` på Vercel-projektets Preview- + Production-env. Snabbast, men bekräftar `no auth, no rate limit, no public deploy`-modellen på publik URL. Bör dokumenteras i `docs/architecture/viewser.md` + uppdaterad docstring i `apps/viewser/lib/localhost-guard.ts`.
   - (b) host-whitelist via ny env-knapp `VIEWSER_ALLOWED_HOSTS`. Mer kontrollerat, ny policy-yta.
   - (c) ADR-beslut om Viewser-på-Vercel auth-strategi (långsiktig).

## Pending — nästa kodspår (ditt val)

I prioritetsordning enligt produktkompassen + Golden Path eval-signal:

1. **Naprapat scaffold-selection fix** — embeddings-gate-blockare. `naprapat-stockholm`-prompten routar till `local-service-business/nordic-trust` istället för `clinic-healthcare/clinic-calm`. Eval-id `golden-path-20260525T204935Z`, naprapat-score 5.83 (under 6.5-tröskeln) → enda case som drar embeddings-gate till `no-go`. Resolver/brief-signal-arbete i `packages/generation/planning/plan.py` (`_pick_scaffold_from_brief` rad 346) + `packages/generation/discovery/resolve.py`. Inte byggt eftersom ingen scope-leak-risk men en egen sprint.
2. **Lane 2 LLM contract propagation** — parkerad WIP på `cursor/jakob-be-llm-contract-propagation`. Behind med ~4 commits. Resume-instruktion finns i `docs/current-focus.md`.
3. **Golden Path eval-omkörning** — verifiera att inga regressions införts av denna sessions fixar. Kör `python scripts/run_golden_path_eval.py` (kräver `OPENAI_API_KEY`).
4. **B125 Vercel preview-fallback** — Safari/Firefox-stöd för embedded WebContainers. Hög-prio-blockare men kräver ADR-beslut. Se `docs/reports/b125-preview-fallback-decision-2026-05-22.md` + `docs/reports/preview-runtime-matrix-2026-05-25.md`.

## Pending — kosmetiskt / lågprio

- **5 stubb-branches** från tidigare squash-merges kan rensas: `b146-port-section-dispatcher` (#112), `cursor/runtime-scaffold-smoke-8efe` (#109), `cursor/golden-path-scorecard-888a` (#110), `cursor/setup-dev-environment-d745` (#111), `chore/gitignore-pycache-build-package` (#114). Plus 2 äldre WIP-rescue-branches: `cursor/jakob-be-golden-path-eval`, `cursor/jakob-be-viewser-local-next-preview`.
- **3 backup-branches** (`backup-43-INNAN-SAMMARBETE`, `backup-44-BRA`, `backup-45-BRA`) — operatör äger, rör inte utan instruktion.

## Working tree-filer (inte rörda, operatörs-territorium)

```
M .cursor/settings.json        [operatörs personliga, rör aldrig]
?? apps/viewser/vercel.json    [Vercel-deploy-config, operatörs-beslut commit/.gitignore]
?? docs/operations/             [pre-existing operatörs-TODO-mapp, väntar på Vercel-flip]
```

## Hur du startar

1. **Läs först:**
   - `docs/current-focus.md` (huvudkö-plan, denna handoff är komplement)
   - `docs/handoff.md` (kanonisk handoff, denna sessions-narrative är där)
   - `docs/known-issues.md` (för B147 + B-IDs som stängdes denna session)

2. **Verifiera state:**
   ```powershell
   git fetch origin
   git status                                    # ska vara clean (utöver operatörs-files)
   git log --oneline -5                          # senaste 5 commits, jämför med detta dokument
   .\.venv\Scripts\python.exe scripts/focus_check.py
   .\.venv\Scripts\python.exe scripts/list_open_bugs.py
   ```

3. **Operatörsdialog:**
   - "PR #118 sync är öppen, vill du att jag mergar den nu eller granskar du själv först?"
   - "B147 vägval — vill du köra (a) snabb VIEWSER_ALLOW_NON_LOCALHOST=true eller (b) host-whitelist eller (c) ADR?"
   - "Naprapat-scaffold-fix är embeddings-gate-blockare. Vill du köra den nu eller annat spår?"

4. **Vid ovisshet om scope:** följ `governance/rules/branch-scope-ui-ux.md`. Jakob-be-lane rör Python (`scripts/`, `packages/`, `tests/`, `governance/`), inte `apps/viewser/components/**` (Christopher-lane). UNDANTAG: per operatörsdirektiv 2026-05-26 (msg-0017-c3f924) kan jakob-be-orchestrator ta UI-fixar när Christopher har levererat tunga PRs och momentum är värt mer än lane-disciplin. Ska INTE upprepas utan operator-OK varje gång.

## Reviewers (för transparens)

Denna session fick två externa AI-reviewers + en read-only build_site-scout:

- reviewer-pass 1 (94 % säkerhet) — verifierade tidigare sessions sync-läge, rekommenderade B147 known-issues-entry + naprapat som nästa spår.
- reviewer-pass 2 (tekniskt buggar-fokuserat) — flaggade 10 risker inkl. silent regression-risk från PR #113 `--ours` (92 %), Vercel wizard 403 (98 %), naprapat scaffold (95 %). Audit-rapport i `docs/reports/pr113-ours-conflict-audit-2026-05-26.md` bekräftade clean.
- **Read-only build_site-scout** — flaggade B148+B149+B150 (alla stängda denna session) plus några låg-konfidens-fynd som hör hemma under B13a (`build_site.py` arkitektur-skuld, Unknown).

## Christophers ack-status

Christopher (christopher-ui-lane) har bekräftat msg-0008 + msg-0009 (ack 2026-05-26 08:22 UTC). Han har lärt sig från scope-leak-direktivet och PR #117 var 100 % UI-only utan tillbakablick. Inga ytterligare scope-leak-risker observerade. När operatören vill kan han informeras om merge-resultat (eller läsa msg-0017-c3f924 själv).

---

**Slut på handoff.** Lycka till. Om något i denna doc verkar inaktuellt: `git log --oneline origin/main..origin/jakob-be` visar sanningen.
