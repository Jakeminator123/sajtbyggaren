# Cloud-grind-prompt 3 — Doc/workboard-städ + sync med kod-läge

> **Copy-paste hela detta block som första prompt i en ny Cursor Cloud Agent-session.**
> Agenten ska kunna jobba self-contained utan att läsa andra docs.

---

Du är Steward-agent som kör i en cloud-agent-VM (Ubuntu). Repo: `Jakeminator123/sajtbyggaren`. Arbets-branch: **`jakob-be`** (Jakob-lane; Steward-arbete på docs är OK direkt på arbets-branchen enligt `governance/rules/branch-discipline.md`). Du touchar bara GitHub-remoten.

## Mission

Sanity-check 2026-05-26 sen kväll hittade **drift mellan docs och faktisk kod-status**. Syftet med den här prompten är ren bokföring: synka `docs/handoff.md`, `docs/current-focus.md`, `docs/workboard.json` och relevanta gap-filer mot vad kod-läget faktiskt säger. **Inga kod- eller policy-ändringar.**

## Branch + förutsättningar

```bash
git fetch origin --prune
git switch jakob-be
git pull --ff-only origin jakob-be
git status                                                  # ska vara clean
git log --oneline -5
git rev-list --left-right --count origin/main...origin/jakob-be
```

Rapportera startsläget i din första rapport (`HEAD = <SHA>`, commits framför main, senaste 5 commits) så operatören kan jämföra mot `docs/current-focus.md` "Last verified state".

## Tillåtna paths (write-set)

- `docs/handoff.md`
- `docs/current-focus.md`
- `docs/workboard.json`
- `docs/gaps/*.md` (bara stale poster — verifiera mot kod innan ändring)
- `docs/backend-handoff.md` (bara om Prompt 1 / Prompt 4 / Prompt 5 mergats — i annat fall är status-tabellen redan korrekt)
- `docs/handoff-2026-05-26-late-evening.md` — markera som "arkiverad" om dess innehåll är replikerat i `handoff.md`. Ingen radering om operatören inte uttryckligen säger det.

## Off-limits paths (do not touch)

- All kod under `scripts/`, `packages/`, `apps/`, `tests/`, `governance/policies/`, `governance/schemas/`.
- `.cursor/rules/**` (regenereras via `scripts/rules_sync.py` — bara kör script om du måste).
- `governance/rules/**` (källan; ändras bara via separat prompt).
- `.cursor/settings.json` (operatörens lokala fil — finns kanske inte ens i cloud-VM:n; rör inte oavsett).

## Drift-poster att åtgärda

### Drift 1: commit-count

`docs/current-focus.md` (rad ~62) säger `jakob-be` är **15** commits framför `origin/main`. Verifiera med `git rev-list --left-right --count origin/main...origin/jakob-be` — siffran har växt sedan dess (var 19 vid sanity 2026-05-26 sen kväll, kan ha vuxit ännu mer om Prompt 1/2 redan landat). Bumpa till faktiskt antal. Lika gärna `docs/handoff.md` (rad ~25) om den citerar samma siffra.

### Drift 2: "inga öppna gaps" vs workboard har poster

`docs/handoff.md` (rad ~64) säger: *"Öppna gaps på workboarden: inga aktiva eller queuade gaps just nu."*

`docs/workboard.json` säger:

- **queued:** `GAP-backend-build-trace-endpoint` (Christophers scope-leak-implementation, ej PR:ad än).
- **active:** `GAP-viewser-restaurant-wizard-hint` + `GAP-viewser-mobile-hero-safe-zone` (Christopher-UI, completedAt-tidsstämplar i notes men status fortfarande "active").

**Beslutsregel:**

- Om en `active` gap har `completedAt`-tidsstämpel och dess `fixCommits` syns i `git log` på `origin/jakob-be` eller `origin/main`: flytta posten till `completedGaps[]` i `workboard.json`. Behåll alla fält.
- Om en `queued` gap har `note` som säger "Christopher implementerade hela gapet under operator-OK scope-leak": låt den ligga kvar (väntar på PR från `christopher-ui` enligt handoff). Men `docs/handoff.md` mening "inga öppna gaps" ska bytas mot exakt aktuell sanning. T.ex.: *"Workboarden har 1 queued gap (`GAP-backend-build-trace-endpoint` — Christopher-implementerat under scope-leak, väntar PR från `christopher-ui` mot `main`). Inga aktiva gaps."*

### Drift 3: backend-handoff-status

`docs/backend-handoff.md` status-tabellen (rad ~12-23) säger **7 stängda / 3 delvis / 1 öppen**. Verifiera mot kod:

- Gap 6: "Delvis — metadata-render finns, `.ico`-konvertering saknas". Korrekt om Prompt 1 *inte* mergats. Om Prompt 1 mergats: flytta till **Stängd** med commit-SHA.
- Gap 7: "Delvis — metadata-render finns, 1200×630-crop saknas". Samma logik.
- Gap 9: "Delvis — prompt-sammanfattning finns, `__mood/`-isolering saknas". Korrekt om Prompt 4 inte mergats; flytta annars.
- Gap 10: "Öppen — backend-kopiering + renderer-stöd saknas". Korrekt om Prompt 5 inte mergats.

**Inga ändringar om motsvarande prompt inte landat på `origin/jakob-be` än.**

### Drift 4: B147-status

`docs/known-issues.md` lista B147 som **öppen Medel-Hög**. Om Prompt 2 mergats: flytta B147 till "Stängda"-sektionen med commit-SHA + test-fil-referens.

Om Prompt 2 inte mergats: bara verifiera att B147-entry-texten fortfarande stämmer med koden (`apps/viewser/lib/localhost-guard.ts` har bara `VIEWSER_ALLOW_NON_LOCALHOST` idag).

### Drift 5: stale "TODO"-pekare

Verifiera att följande filer inte längre nämns som "aktuella att radera":

- `docs/operations/vercel-production-branch-todo.md` — operatören bekräftade 2026-05-26 sen kväll att Vercel-flippen är gjord. Filen verkar redan vara borta (Read sade "File not found" vid sanity). Sök efter referenser till den i `docs/current-focus.md`, `docs/handoff.md`, `docs/handoff-2026-05-26-late-evening.md` och `docs/known-issues.md` och ta bort de raderna (eller skriv om dem som "(åtgärdat 2026-05-26)" så vi inte tappar historiken).

### Drift 6: Last verified state-SHA

`docs/current-focus.md` rad 33: `Last verified state: f7c437e (2026-05-26 late evening UTC, post docs-slim + branch-model-clarification).` Bumpa till nuvarande HEAD på `origin/jakob-be` om den växt sedan.

## Acceptanskriterier

1. `docs/current-focus.md` rad 33 "Last verified state" matchar `git log -1 --format="%H" origin/jakob-be`.
2. `docs/current-focus.md` commit-count-meningen ("X commits framför origin/main") matchar `git rev-list --left-right --count origin/main...origin/jakob-be`.
3. `docs/handoff.md` säger inte längre "inga öppna gaps" om workboard säger något annat.
4. `docs/workboard.json` har inga `active`-poster med `completedAt`-stämpel och `fixCommits` som redan är i `git log`.
5. Inga rader i `docs/current-focus.md` / `docs/handoff.md` / `docs/known-issues.md` pekar på `docs/operations/vercel-production-branch-todo.md` som "att göra" — den filen är historik nu.
6. Backend-handoff status-tabellen reflekterar exakta stängda/delvis/öppna räkningen (verifierat mot kod, inte mot text).
7. Bug-count-raden i `docs/known-issues.md` rad 3 stämmer med faktisk räkning (kör `python scripts/list_open_bugs.py` om det finns för verifiering).
8. Inga textändringar i någon `.md`-fil utöver de poster som faktiskt är drift. Hold-the-line.

## Final guards (alla ska vara gröna före push)

```bash
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python scripts/sprintvakt_check.py
python -m ruff check .
python -m pytest tests/ -q
python scripts/focus_check.py
```

`focus_check.py` ska vara helt grön i cloud-VM:n (ingen operatörs-`.cursor/settings.json`-dirty-state att exkludera).

## Stoppvillkor

Stoppa och rapportera om:

- En guard failar och du inte ser hur du fixar det inom docs-write-set.
- Du upptäcker att kod faktiskt är trasig och docs är korrekta (då är det inte ett doc-städ-fall, det är en bug — rapportera till operatören).
- MCP Sprintvakt-server är inte konfat i cloud-VM:n. Använd vanlig `git`-edit av `docs/workboard.json` istället för MCP-tools.

## Commit-format

En atomisk commit (eller två om bug-count-städ är separat):

```
docs(steward): sync handoff/focus/workboard with actual code state 2026-05-26

- Bumps Last verified state to <SHA> and commit-count to <N>.
- Moves completed UI-gaps from active to completedGaps in workboard.json.
- Replaces "inga öppna gaps"-line with accurate count.
- Removes stale references to vercel-production-branch-todo.md.
- (If applicable) flips B147 to Stängda after Prompt 2 merge.
- (If applicable) bumps backend-handoff status table after Prompt 1/4/5 merge.

Pure bookkeeping. No code/policy/test changes.
```

## Push

```bash
git push origin jakob-be
```

Ingen PR. Operatörens beslut om sync-PR ligger separat.

## Rapport tillbaka till operatör

```
Pushed <SHA> till origin/jakob-be.
Drift-poster åtgärdade: <lista, t.ex. "commit-count 15 → 19", "1 active gap flyttad till completed", "B147 ej rörd (Prompt 2 inte mergad än)">.
Alla guards gröna inkl. focus_check.

Kvarvarande drift som väntar på annan prompt:
- backend-handoff Gap 6+7 (väntar Prompt 1-merge)
- backend-handoff Gap 9 (väntar Prompt 4-merge)
- backend-handoff Gap 10 (väntar Prompt 5-merge)
- known-issues B147 (väntar Prompt 2-merge)
```

## Parallellitet

- **OK att köra parallellt med:** Prompt 1, Prompt 2, Prompt 4, Prompt 5 — den här rör bara docs + workboard, vilket är disjunkt från all kod-arbete.
- **Re-run rekommenderas** efter att Prompt 1/2/4/5 mergats för att bumpa backend-handoff + known-issues. Steward kan köra om Prompt 3 flera gånger i samma session — den är idempotent (varje run bara fixar drift som finns vid det tillfället).
