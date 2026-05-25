# ADR 0031 — Steward auto-bump vid PR-merge

**Status:** Proposed
**Datum:** 2026-05-25
**Beroenden:** `governance/rules/team-workflow.md`,
`governance/rules/branch-discipline.md`,
`governance/rules/bug-scope-discipline.md`.

## Kontext

Steward-loopen kräver att `docs/current-focus.md` och `docs/handoff.md`
pekar på faktisk verifierad HEAD efter merge eller direktpush. I praktiken
har detta drivit: efter flera PR-merges krävs separata `docs(steward)`-
commits för att bara flytta pekaren. Det skapar brus i historiken och gör
nästa agent osäker på om dokumenten beskriver den kod som faktiskt är
mergad.

Den mänskliga delen av Steward-arbetet behövs fortfarande för prioriteringar,
buggflyttar, workboard och längre handoff-text. Det automatiska behovet är
smalare: när en PR mergas till `main` ska huvudpekaren i de två handoff-
dokumenten flyttas till merge-commitens SHA med en kort, spårbar PR-rad.

## Beslut

Inför en server-side GitHub Action som körs på `pull_request.closed` när PR:en
är mergad mot `main`. Actionen ska:

1. Hämta PR-titel, PR-nummer, merge-commit-SHA och PR-rader sedan tidigare
   verifierad state.
2. Köra `scripts/steward_auto_bump.py`.
3. Uppdatera enbart `docs/current-focus.md` och `docs/handoff.md`.
4. Arkivera tidigare toppblock i en sektion `## Föregående checkpoint`.
5. Skippa helt om ändringen är trivial docs-only enligt helperns
   trivial-detektor.
6. Commit:a direkt till `main` med ett kort, maskinellt commit-meddelande som
   bara innehåller ny HEAD-pekare och PR-rad.

Helpern ska vara idempotent: om ny SHA redan står som verifierad state gör den
ingen filändring och returnerar exit-kod 0.

Scope:t är avsiktligt `main`-only. `jakob-be` kan vara aktiv review- eller
integrationsbranch, men Steward auto-bump ska registrera den kanoniska
produktionsliknande HEAD som nästa agent normalt utgår från efter merge till
`main`. Om `jakob-be` i framtiden byter roll till canonical base krävs en ny
regeländring som uttryckligen lägger till den branchen.

## Alternativ som övervägdes

| Alternativ | Bedömning |
| --- | --- |
| Lokal git-hook hos Steward | Avslogs. Lokala hooks följer inte med alla agenter, fungerar inte för GitHub-merge-knappen och kan inte garantera att `main` bumpas efter server-side merge. |
| Manuell Steward-bump efter varje merge | Avslogs som ensam mekanism. Det är den nuvarande rutinen och har redan visat drift. |
| Server-side GitHub Action | Valt. Kör där merge-händelsen sker, kan använda `GITHUB_TOKEN` med write permissions och kan hållas smal till två dokument. |
| Full autonom Steward-textgenerator | Avslogs. Längre handoff, bug-status och workboard kräver mänsklig/agentmässig precision och ska inte ersättas av en maskinell PR-trigger. |

## Konsekvenser

Positiva:

- Nästa agent ser snabbare vilken HEAD som dokumenten senast verifierade.
- Separata `docs(steward)`-commits blir färre när de bara skulle flytta HEAD-
  pekaren.
- Drift efter GitHub-merge minskar utan att automatisera bug-scope eller
  workboard.
- Trivial docs-only PRs kan mergas utan att skapa ytterligare bump-brus.

Negativa:

- `main` får en extra bot-commit efter icke-triviala PR-merges.
- PR-merges till `jakob-be` bumpas inte automatiskt; när de senare lyfts till
  `main` sker bumpen i den PR-merge som faktiskt ändrar `main`.
- Om toppblockens markdown-format ändras utan att helpern uppdateras kommer
  actionen faila i stället för att gissa.
- PR-listan blir kortfattad och mekanisk; den ersätter inte riktig handoff-
  redigering när nästa agents arbetsläge har ändrats.

## Regeländring

`governance/rules/team-workflow.md` ändras så Steward-loopens steg 8 säger:
vid PR-merge till `main` sker HEAD-bumpen automatiskt; manuell uppdatering
krävs bara vid direktpush, andra grenar eller när fokus, risk, blocker,
workboard eller längre handoff-text faktiskt ändras.

## Gränser

- `docs/known-issues.md` ändras aldrig av actionen.
- `docs/workboard.json` ändras aldrig av actionen.
- Actionen skriver inte långa PR-beskrivningar eller fria commitmeddelanden.
- Helpern får bara skriva `docs/current-focus.md` och `docs/handoff.md`.
