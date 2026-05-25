# Builder-uppdrag: Steward Auto-Bump GitHub Action

> Klistra in detta i en Cursor Cloud Background Agent eller annan
> isolerad builder-agent. Prompten är self-contained — agenten ska
> inte fråga operatören om förtydligan innan den läst förutsättningarna.

## Roll
Du är en builder-agent som ska implementera en GitHub Action som
auto-bumpar `docs/current-focus.md` och `docs/handoff.md` när en PR
mergeas till `main`. Det här löser observerad drift där Steward-rollen
glömmer bumpa docs efter 30%+ av merges (mätbart i 35%
docs(steward)-commits senaste 100, se
`docs/health-checks/2026-05-25-halvtid.md` §3).

## Förutsättningar (läs först, i denna ordning)
1. `AGENTS.md` — repo-konventioner och godkända kommandon
2. `governance/rules/team-workflow.md` — Steward-loopen steg 8
3. `governance/rules/branch-discipline.md` — branch-flödet
4. `governance/rules/bug-scope-discipline.md` — NEVER ändra known-issues.md
5. `docs/current-focus.md` — se hur den är strukturerad idag
   (rad 33-65: "Last verified state"-blocket)
6. `docs/handoff.md` — samma, header-blocket
7. `.github/workflows/` — befintliga workflows för stilmönster
8. `docs/health-checks/2026-05-25-halvtid.md` §1 — Steward-auto-design

## Mål
En GitHub Action `.github/workflows/steward-auto-bump.yml` som:

1. Triggas på `pull_request.closed` med `merged == true` mot `main`.
2. Läser PR-titeln, PR-numret, merge-commit-SHA och listan av PR-titlar
   sedan föregående verifierade-state-SHA.
3. Kör en ny Python-helper `scripts/steward_auto_bump.py` som:
   - Skriver om "Last verified state"-blocket i `current-focus.md`
     till nya SHA + 2-3-rads sammanfattning av nya PRs
     (titel + nummer).
   - Skriver om header-blocket i `handoff.md` på samma sätt.
   - Lägger gamla blocket i `## Föregående checkpoint`-sektion
     (skapas om den inte finns, annars append).
   - Är **idempotent**: om SHA redan står som verified state, do
     nothing och `sys.exit(0)`.
4. Trivial-detektor: skippa hela bumpen om sammanlagda diff:en är
   <50 rader OCH bara rör `docs/`-paths OCH inte rör
   `current-focus.md`/`handoff.md`/`workboard.json`/`known-issues.md`
   själva. Använd `gh pr diff --name-only` + `gh pr view --json
   additions,deletions`.
5. Pushar commit:en till `main` som
   `docs(steward-auto): bump HEAD to <short-sha> via PR #<num> <title>`
   med `GITHUB_TOKEN` (Action har write permissions).

## Vad du EJ ska göra
- **NEVER ändra `docs/known-issues.md`** (Steward-managed manuellt,
  bug-scope-discipline kräver mänsklig precision för fix-flytt mellan
  Öppna/Stängda).
- **NEVER ändra `docs/workboard.json`** (Steward-managed manuellt).
- **NEVER bumpa när trivial-detektorn säger nej.**
- **NEVER skriva PR-beskrivningar eller commit-meddelanden från
  GitHub-actionen — bara HEAD-pekare + PR-titel-rad.** Långa
  Steward-texten är fortfarande mänskligt/agent-jobb.

## Begränsningar
- Python 3.11+, ruff 0 findings, alla befintliga tester ska passera.
- `python scripts/governance_validate.py`, `python scripts/rules_sync.py
  --check`, `python scripts/check_term_coverage.py --strict`,
  `python scripts/sprintvakt_check.py` — alla måste fortsätta vara OK.
- Lägg nya tester under `tests/test_steward_auto_bump.py` med minst:
  - Idempotens (samma SHA två gånger → ingen commit andra gången)
  - Trivial-detektor positiv (docs-only liten diff → skip)
  - Trivial-detektor negativ (kod-diff eller stor diff → bump)
  - Föregående-checkpoint-arkivering (gammalt block flyttas till
    `## Föregående checkpoint`)
  - SHA-format-validering (rejectar invalid SHA-input)
- ADR krävs **innan** implementation: skapa
  `governance/decisions/0031-steward-auto-bump.md` som ADR-utkast med:
  - Beslutet, alternativen (lokal hook vs server-Action), valda
    konsekvenser, hur regeln team-workflow.md ändras.
  - Lägg till länken i `README.md` ADR-listan.
- Commit-meddelandet på själva implementations-PR:en ska följa
  conventional commits: `feat(steward): auto-bump current-focus +
  handoff on PR merge to main (ADR 0031)`.

## Leverabel
Draft PR mot `jakob-be` (INTE direkt mot `main`). Innehåll:
- `governance/decisions/0031-steward-auto-bump.md` (ADR)
- `.github/workflows/steward-auto-bump.yml`
- `scripts/steward_auto_bump.py`
- `tests/test_steward_auto_bump.py`
- `README.md` (uppdaterad ADR-lista)
- `governance/rules/team-workflow.md` (uppdatera Steward-loopen steg 8
  så det säger: "automatisk vid PR-merge; manuell bara vid annat
  tillfälle")

Verifiering i PR-beskrivningen:
- Visa testkörning lokalt (kopiera output)
- Visa dry-run av actionen (gärna via `act` om möjligt, annars
  beskriv manuell trigger-procedur)
- Bekräfta att alla 6 health-checks gröna

## Modellval för agent
GPT-5 / Claude Opus 4.7 / Composer 2.5 — välj efter tillgänglighet.
Detta är en medium-stor task (~300-500 rader kod + 200 rader tester +
en ADR). Beräknad tid: 2-4 timmar.

## Misslyckande-mod
Om du som agent inte kan slutföra hela uppdraget (t.ex. CI-grön är
omöjlig att uppnå inom rimlig tid), öppna en draft-PR med vad du har
gjort + ett tydligt blockerings-meddelande i Sprintvakt-inboxen via
MCP-tool `post_message` till `jakob-orchestrator`:

```
from: cursor-builder-steward-auto
to: jakob-orchestrator
subject: steward-auto-bump-blocked
body: <kort beskrivning av vad som är klart, vad som blockerar, och
       vilka 1-2 frågor operatören måste besvara för att låsa upp>
```

Lämna inte hängande WIP utan signalering.
