---
description: docs/current-focus.md bär bara det aktuella statusblocket (SHA/status, nästa 3 prioriteringar, öppna blockers, länkar). Allt äldre flyttas till arkiv, raderas inte.
alwaysApply: true
---

# Hygien för current-focus.md (och handoff.md)

`docs/current-focus.md` ska vara **kort och läsbar på 30 sekunder**. Den är
nästa agents första källa — staplad historik vilseleder. Samma princip gäller
toppen av `docs/handoff.md`.

## Vad filen får innehålla

1. **Status nu** — aktuellt git-läge (main + arbets-branch SHA), `Last verified
   state: <sha>`-raden och `Nya PRs sedan föregående checkpoint:`-raden.
2. **Nästa 3 prioriteringar** — numrerad lista, en rad var.
3. **Öppna blockers** — kort punktlista.
4. **Öppna PR att känna till** — varje öppen PR måste nämnas vid nummer
   (`focus_check.py` korsar mot detta).
5. **Länkar** — handoff, agent-prompts, openclaw-plan, branch-discipline.
6. Stabil referens som sällan ändras: "Vem uppdaterar denna fil",
   "Branchmodellen (kort)", "Loopen vi följer", "Arkiv".

## Vad som ska bort (till arkiv, inte raderas)

- Gamla `## Current objective (<datum>)`-block. Bara det senaste/aktuella
  statusblocket får finnas. Äldre flyttas till
  `docs/archive/current-focus-<datum>-*.md`.
- `## Föregående checkpoint`-kedjan: behåll **högst ett** historiskt block
  (auto-bump-verktyget lägger till ett kort SHA-block per main-sync); när
  kedjan växer, flytta de äldre till arkivet och lämna en arkivlänk.
- Stale PR-listor, "Direkt nästa fokus", "Aktiv kö" m.m. som inte längre
  styr nästa agents arbete.

## Hårda krav (bryt dem inte vid slimning)

- Behåll en `Last verified state: \`<sha>\``-rad direkt följd av en `## `-rubrik
  (`scripts/steward_auto_bump.py` och `scripts/focus_check.py` förlitar sig på
  detta).
- Behåll en `## Föregående checkpoint`-sektion (auto-bumpens ankare).
- Flytta, radera inte. Snapshotta hela den gamla filen till
  `docs/archive/` innan du skriver om.

## Vem gör städningen

Steward (eller en docs/governance-cloudagent) vid focus-refresh. Om en
cloudagent redan håller filen kort behövs ingen extra åtgärd — denna regel är
sanningen om *vad* kort betyder.
