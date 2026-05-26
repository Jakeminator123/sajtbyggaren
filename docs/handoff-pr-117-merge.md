# PR #117 merge-handoff till Jakob

**Skapad:** 2026-05-26 (christopher-ui-lane)
**För:** jakob-orchestrator / jakob-be-lane
**Branch:** `christopher-ui` → mergas till `jakob-be`
**HEAD:** `4023d81` (lokalt + origin synkat)
**PR:** [#117 — feat(viewser): mobile responsive — foundation + polish + final (fas 1+2+3)](https://github.com/Jakeminator123/sajtbyggaren/pull/117)

---

## TL;DR — klistra in nedanstående prompt i Cursor (jakob-be-lane)

Allt under separatorn `>>> COPY-PASTE PROMPT >>>` är en autonom prompt
som du kan klistra in i ett tomt Cursor-agentfönster i jakob-be-lane.
Agentet har då allt den behöver för att merga PR #117 säkert, lösa
den enda kända konflikten, verifiera, pusha och informera tillbaka.

---

## Fakta som handoff bygger på

### Branch state

- `christopher-ui` HEAD = `4023d81` (origin matchar)
- PR-bas = `jakob-be`
- merge-base = `3bedddd` (= forken där vår lane började)
- Antal commits ahead av jakob-be: 31 (alla christopher-uis)
- PR-state: `open`, `mergeable: CONFLICTING` (1 konflikt, se nedan)

### Diff omfattning (våra 31 commits, från merge-base)

- **35 filer ändrade**, +1866 / -252 rader
- **100% UI-only** mot PR-basen — verifierat med:
  ```bash
  git diff --stat $(git merge-base origin/jakob-be christopher-ui)..christopher-ui \
    -- apps/viewser/app/api/ apps/viewser/lib/ apps/viewser/middleware.ts \
       apps/viewser/contracts/ packages/ scripts/ tests/ governance/ tooling/ \
       apps/viewser/next.config.ts apps/viewser/package.json
  # Output: (tomt — guard OK)
  ```
- Filgruppering:
  - 25 filer under `apps/viewser/components/`
  - 1 fil: `apps/viewser/app/globals.css` (utility-classes: `pb-safe`, `min-tap`, `touch-visible`, `bottom-sheet-handle`)
  - 1 ny asset: `apps/viewser/public/SM-mobile.mp4` (960×960 hero-banner, 1.1MB)
  - 6 nya GAP-filer under `docs/gaps/`
  - 2 docs-filer: `docs/current-focus.md`, `docs/agent-inbox.jsonl`
  - 1 governance-fil: `docs/workboard.json` (GAP-statusar)

### Konflikt-status

Endast **en** fil överlappar mellan jakob-be och christopher-ui:

- `docs/current-focus.md` — båda lanes har bumpat HEAD-SHA + uppdaterat
  sektionen "Aktuellt fokus" parallellt. Standard merge-konflikt.

Resolution-strategi: **behåll christopher-uis version** (mobil-PR-status
är aktuellaste handoff-context), bumpa "Last verified state"-SHA till
post-merge HEAD efter att Jakobs egna ändringar i filen folats in.

### Check-svit på `christopher-ui`@`4023d81` (verifierat)

| Check | Resultat |
|-------|----------|
| `python scripts/sprintvakt_check.py` | OK |
| `python scripts/focus_check.py` | OK (warnings: working tree clean efter push) |
| `python scripts/governance_validate.py` | 18/18 policies OK |
| `python scripts/rules_sync.py --check` | OK (alla speglar synk) |
| `python scripts/check_term_coverage.py --strict` | OK (0 okända begrepp) |
| `python -m ruff check .` | 0 findings |
| `cd apps/viewser && npx tsc --noEmit` | OK |
| `cd apps/viewser && npm run lint` | OK (`eslint` exit 0) |
| `python -m pytest tests/test_discovery_resolver.py tests/test_llm_contract_propagation.py` | 89/89 passed |

Full pytest-svit (540+ tests) körd och grön i tidigare commits i samma
lane; ej nödvändigt att köra om för UI-only diff.

### Commits ahead av jakob-be (31 st, läs nedifrån-och-upp)

```
4023d81 docs(inbox): notify jakob-orchestrator — PR #117 ready after scout pass 4 (msg-0014)
6f24786 docs(focus): bump SHA to c5d1ba9 (scout pass 4 P1-batch pushed)
c5d1ba9 fix(viewser): scout pass 4 P1 batch — hero safe zone, wizard asterisk, prompt-builder safe-area
59eed4c feat(viewser): mobile hero stacked flow + SM-mobile.mp4 banner
3e312f2 docs(inbox): notify jakob-orchestrator about scout-fixes — PR #117 redo for review
420efb0 chore(viewser): lint + term-coverage compliance för scout-fixes-passet
6e06129 fix(viewser): scout P1 batch — hydration, flash, keyboard, tap-targets, focus
cb6f43d fix(viewser): scout P0 batch — pb-safe-or-3, wizard iOS-zoom, steg-chips + footer
6d0c896 docs(gap): complete fas 3 (in-review), open scout-fixes GAP
a87533a docs(workboard): close two stale paused GAPs already implemented
564ab80 docs(inbox): post msg-0012 — PR #117 utokat med fas 3 (13 commits totalt)
71257ce docs(focus): bump current-focus till 8724798 + fas 3-summary
8724798 chore(viewser): term-coverage compliance — Device + scroll-pos detection
f850882 feat(viewser/canvas): device-toggle desktop preview + edge-pulse motion polish
18d84f5 fix(viewser): mobile responsive height + compare-modal swipe between A/B
e05c443 docs(gap): complete fas 1+2 (in-review), open fas 3 — final polish
86db492 docs(inbox): notify jakob-be om fas 2 leverans (msg-0011)
7e580b4 docs(focus): bump current-focus till 712a3c2 + fas 2 commits-log
712a3c2 fix(viewser/dialogs): mobile-friendly grids + iOS-zoom-fix på inputs
64445bb fix(viewser/canvas): hero typography scale + console-drawer safe-area
6b2d68c fix(viewser/wizard,builder): systematic tap-target upgrade — utility buttons
d7ca301 fix(viewser/prompt): mobile-friendly composer tap-targets + iOS-zoom-fix
62437de docs(gap): open GAP-viewser-mobile-responsive-polish (fas 2)
b0140b1 docs(inbox): notify jakob-be about PR #117 + paused gaps
fb87699 docs(focus): bump current-focus to 9593769 + governance fixes
9593769 feat(viewser/builder): mobile pass — bottom-sheet chat + inspector
3b2420d feat(viewser/wizard): mobile pass — validation, tap-targets, touch-delete
31a888a feat(viewser/ui): mobile foundation — safe-area, min-tap, bottom-sheet
ea62e45 docs(gap): open GAP-viewser-mobile-responsive-foundation
a1d1a1f docs(inbox): ack msg-0008 (scope-process-PR-105) + msg-0009 (b146-port)
3bedddd docs(steward-auto): bump HEAD to 50217e3 via PR #115 sync(jakob-be -> main)
```

(`3bedddd` är merge-base, inte ahead — listad för referens.)

### GAPs som påverkas

**Completed via denna PR (alla har commits attached):**

- `GAP-viewser-mobile-responsive-foundation` (31a888a/3b2420d/9593769)
- `GAP-viewser-mobile-responsive-polish` (d7ca301/6b2d68c/64445bb/712a3c2/18d84f5/f850882)
- `GAP-viewser-mobile-responsive-final-polish` (8724798)
- `GAP-viewser-mobile-scout-fixes` (cb6f43d/6e06129/420efb0)
- `GAP-viewser-mobile-hero-flow` (59eed4c)
- `GAP-viewser-mobile-hero-safe-zone` (c5d1ba9/6f24786)

**Pausade GAPs som ska re-aktiveras post-merge:**

- `GAP-viewser-pipeline-status-polling` (christopher, paused → queued)
- `GAP-viewser-side-by-side-preview` (christopher, paused → queued)

(Båda pausades när mobil-PR startade eftersom de delar samma kärnfiler.
Efter PR #117 mergas är path-locks frigjorda och dessa kan plockas upp.)

### Off-limits-guard final-check

Mot PR-basen (`jakob-be`) från merge-base = `3bedddd`:

| Path | Vår diff |
|------|----------|
| `apps/viewser/app/api/` | tomt |
| `apps/viewser/lib/` | tomt |
| `apps/viewser/middleware.ts` | tomt |
| `apps/viewser/contracts/` | tomt |
| `apps/viewser/next.config.ts` | tomt |
| `apps/viewser/package.json` | tomt |
| `packages/` | tomt |
| `scripts/` | tomt |
| `tests/` | tomt |
| `governance/` | tomt |
| `tooling/` | tomt |

Garanterat ingen påverkan på engine, datakontrakt, builder, planner,
governance-policies, scripts eller tester.

---

>>> COPY-PASTE PROMPT >>>

Du är jakob-be-lane-agent i Sajtbyggaren-2.0. Operatören (Jakob) har bett
dig merga in PR #117 från christopher-ui-lane (mobil responsive
end-to-end, 31 commits, 100% UI-only). Christopher har redan kört scout-
bug-hunt fyra gånger och fixat alla P0+P1. PR är `mergeable: CONFLICTING`
men det är bara ÉN trivial docs-konflikt.

Följ denna kedja exakt. Stoppa och fråga operatören om något avviker.

## Steg 0 — sanity-check baseline

```bash
cd /Users/<host>/Desktop/Sajtbyggaren_2.0
git status --short                     # ska vara clean
git rev-parse HEAD                     # notera nuvarande jakob-be HEAD
git fetch origin
git log --oneline origin/jakob-be..HEAD  # tomt = du är på samma SHA som origin
gh pr view 117 --json mergeable,state,headRefOid
# Förväntat: state=open, mergeable=conflicting, headRefOid=4023d81...
```

Om `git status` inte är clean: stoppa och fråga operatören innan du
fortsätter. Om HEAD inte är jakob-be: `git checkout jakob-be && git pull
--ff-only origin jakob-be`.

## Steg 1 — kontrollera off-limits-guard MOT VÅR LANE

Christopher har påstått att alla 31 commits är 100% UI-only mot PR-bas.
Verifiera själv (1 sekund att köra):

```bash
MB=$(git merge-base origin/jakob-be origin/christopher-ui)
echo "merge-base: $MB"   # ska vara 3bedddd

git diff --stat $MB..origin/christopher-ui -- \
  apps/viewser/app/api/ \
  apps/viewser/lib/ \
  apps/viewser/middleware.ts \
  apps/viewser/contracts/ \
  apps/viewser/next.config.ts \
  apps/viewser/package.json \
  packages/ \
  scripts/ \
  tests/ \
  governance/ \
  tooling/
```

Om utdata INTE är tom: **stoppa**, ping operatören med diff-stat. PR ska
inte mergas om guard bryts.

Om utdata är tom: fortsätt till steg 2.

## Steg 2 — pull christopher-ui lokalt och starta merge

```bash
git fetch origin christopher-ui:christopher-ui
git checkout jakob-be
git merge --no-ff --no-commit origin/christopher-ui
```

Förvänta dig:
```
Auto-merging docs/current-focus.md
CONFLICT (content): Merge conflict in docs/current-focus.md
Automatic merge of changes paused; fix conflicts and then commit the result.
```

Om FLER filer än `docs/current-focus.md` konfliktar: **stoppa**,
ping operatören. Christopher har bara verifierat 1 konflikt
(`docs/current-focus.md` — båda lanes bumpat HEAD-SHA + status).

## Steg 3 — lös konflikten i docs/current-focus.md

Strategi: **behåll christopher-uis version** (den är aktuellaste
handoff-context och beskriver hela mobil-arbetet i detalj). Sedan bumpa
"Last verified state"-SHA till den NYA merge-commit-SHA:n efter steg 5.

```bash
git checkout --theirs docs/current-focus.md
git add docs/current-focus.md
```

Verifiera att inga andra konflikter återstår:
```bash
git diff --name-only --diff-filter=U   # ska vara tomt
git status --short                      # ska visa endast M-rader, inga UU/DU/AU
```

## Steg 4 — kör full check-svit före commit

```bash
.venv/bin/python scripts/sprintvakt_check.py
.venv/bin/python scripts/focus_check.py
.venv/bin/python scripts/governance_validate.py
.venv/bin/python scripts/rules_sync.py --check
.venv/bin/python scripts/check_term_coverage.py --strict
.venv/bin/python -m ruff check .
(cd apps/viewser && npx tsc --noEmit)
(cd apps/viewser && npm run lint)
.venv/bin/python -m pytest -q tests/ 2>&1 | tail -20
```

Alla ska returnera 0. Om någon faller: stoppa, ping operatören med
output. christopher-ui hade allt grönt vid `4023d81` så fel sannolikt
introducerades av merge-resolution.

## Steg 5 — commit merge + post-merge SHA-bump i samma sekvens

```bash
git commit -m "Merge pull request #117 from Jakeminator123/christopher-ui

feat(viewser): mobile responsive — foundation + polish + final + scout pass 4

31 commits, 35 filer, 100% UI-only. Mobile-first end-to-end (375px → tablet
→ desktop) för hela viewser-flödet inkl. wizard, builder, dialogs, hero,
prompt-builder. SM-mobile.mp4 (960×960) som mobil hero-banner. Fyra scout-
bug-hunt-pass körda (composer-2.5-fast, read-only) — alla P0+P1 fixade.

Completed GAPs:
- GAP-viewser-mobile-responsive-foundation
- GAP-viewser-mobile-responsive-polish
- GAP-viewser-mobile-responsive-final-polish
- GAP-viewser-mobile-scout-fixes
- GAP-viewser-mobile-hero-flow
- GAP-viewser-mobile-hero-safe-zone

Conflict: docs/current-focus.md (resolved with christopher-ui version).
"
NEW_HEAD=$(git rev-parse HEAD)
echo "Ny jakob-be HEAD efter merge: $NEW_HEAD"
```

Nu bumpa "Last verified state"-SHA i `docs/current-focus.md` till
`$NEW_HEAD` (ersätt `4023d81` eller `c5d1ba9` på rad ~33 med nya SHA:n).
Sedan:

```bash
git add docs/current-focus.md
git commit -m "docs(focus): bump SHA to $NEW_HEAD (post-merge PR #117)"
```

## Steg 6 — verifiera + push

```bash
.venv/bin/python scripts/sprintvakt_check.py
.venv/bin/python scripts/focus_check.py
git log --oneline -5
git push origin jakob-be
```

PR #117 ska automatiskt stängas som "merged" av GitHub eftersom HEAD nu
är reachable från jakob-be.

Verifiera:
```bash
gh pr view 117 --json state,mergedAt
# Förväntat: state=MERGED
```

Om PR fortfarande visar `open` efter push: stäng manuellt med
```bash
gh pr close 117 --comment "Merged manually into jakob-be at $NEW_HEAD."
```

## Steg 7 — re-aktivera pausade christopher-GAPs

Christopher pausade två GAPs när mobil-PR startade (samma kärnfiler):

```bash
.venv/bin/python -c "
from tooling.sprintvakt_mcp import core
result1 = core.activate_gap({'gapId': 'GAP-viewser-pipeline-status-polling',
                              'dryRun': False, 'confirm': True})
print('pipeline-status-polling:', result1.get('gap', {}).get('status'))
result2 = core.activate_gap({'gapId': 'GAP-viewser-side-by-side-preview',
                              'dryRun': False, 'confirm': True})
print('side-by-side-preview:', result2.get('gap', {}).get('status'))
"
```

Om de inte finns i queuedGaps: kör `core.list_gaps` först och kolla
status — kan vara `completedGaps` redan (i så fall: skippa).

Commit + push workboard-uppdateringen:
```bash
git add docs/workboard.json
git commit -m "docs(workboard): re-activate christopher-paused GAPs after PR #117 merge"
git push origin jakob-be
```

## Steg 8 — skicka inbox-svar till christopher-ui

```bash
.venv/bin/python -c "
from tooling.sprintvakt_mcp import inbox
inbox.post_message({
    'from': 'jakob-orchestrator',
    'to': ['christopher-ui'],
    'subject': 'PR #117 merged — mobil responsive komplett i jakob-be',
    'body': '''Hej Christopher,

PR #117 mergad i jakob-be. 31 commits + 1 trivial docs-konflikt löst
(behöll din current-focus-version, bumpade SHA efter merge).

Verifierat:
- Off-limits-guard mot merge-base: tomt (100% UI-only bekräftat)
- Full check-svit grön post-merge
- Pausade christopher-GAPs (pipeline-status-polling, side-by-side-preview)
  återställda till queuedGaps

Tack för fyra scout-pass och konsekvent check-svit-disciplin. Tar nästa
sync jakob-be -> main när rätt fönster öppnar.

/ Jakob''',
    'dryRun': False,
    'confirm': True,
})
"
git add docs/agent-inbox.jsonl
git commit -m "docs(inbox): notify christopher-ui — PR #117 merged"
git push origin jakob-be
```

## Färdig

Standard loop steg 8 är då uppfylld: HEAD-SHA bumpad, GAPs uppdaterade,
pausade GAPs återställda, motpart-lane informerad. Sync till main kan
göras i separat fönster när det är dags.

<<< END COPY-PASTE PROMPT <<<

---

## Bonus — om konflikten är värre än förväntat

Om steg 2 visar **fler** filer i konflikt (t.ex. `docs/agent-inbox.jsonl`
om både lanes skrivit till slutet utan newline, eller `docs/workboard.json`
om jakob-be också ändrat workboard):

- `docs/agent-inbox.jsonl`: behåll **båda** rader. JSONL är append-only,
  ordning spelar ingen roll så länge varje rad är giltig JSON.
- `docs/workboard.json`: använd `tooling.sprintvakt_mcp.core.list_gaps`
  + manuell merge. Christopher har bara lagt till 6 GAPs i
  `completedGaps`/`activeGaps`. Jakob-be:s ändringar (om någon) berör
  troligen `inProgressGaps` eller olika `owner: 'jakob'`-poster.
  Behåll båda sidors poster.

Om någonting i `apps/viewser/components/` konfliktar: stoppa direkt och
ping christopher-ui på inbox. Det betyder att jakob-be har börjat röra
samma UI-filer som vi och behöver koordineras.

---

Frågor: skicka till `christopher-ui` via inbox eller pinga direkt i
operatörstråden.
