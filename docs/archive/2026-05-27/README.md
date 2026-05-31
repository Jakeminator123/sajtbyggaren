# Arkiverade docs — 2026-05-27

Denna mapp innehåller historiska sprint-handoffs och scout-rapporter
som inte längre styr aktivt arbete. De flyttades hit i städpasset
2026-05-27 kväll efter att deras motsvarande sprintar hade stängts
och ansvar tagits över av andra dokument (`docs/current-focus.md`,
`docs/handoff.md`, `docs/workboard.json`).

För aktuell state: se `docs/current-focus.md` + `docs/handoff.md`.

Filer i denna mapp:

- `active-sprint-team-parallel-work-v1.md` — kort plan för "Team Parallel
  Work v1" från innan medutvecklaren var känd. Arbetsmodellen lever vidare
  i [`docs/team-workflow.md`](../../team-workflow.md) och
  [`docs/orchestrator-playbook.md`](../../orchestrator-playbook.md).
  Flyttad från `docs/active-sprint.md` 2026-05-27.
- `backend-handoff-discovery-wizard.md` — backend-handoff för Discovery
  Wizard 5-stegs-omstrukturering. Alla 11 listade gaps verifierat
  stängda 2026-05-26 (gap-tabell i toppen är auktoritativ). Flyttad från
  `docs/backend-handoff.md` 2026-05-27.
- `llm-golden-path-handoff.md` — handoff-doc efter LLM Golden Path v1
  låstes i kod via smoke-tests, multi-intent-chain-test och real-build-
  test. Den **operatör-vända runbooken**
  [`docs/llm-golden-path-runbook.md`](../../llm-golden-path-runbook.md)
  ligger kvar som aktiv dokumentation. Flyttad från
  `docs/llm-golden-path-handoff.md` 2026-05-27.
- `llm-golden-path-references/` — primärkällorna som låg bakom
  handoff-dokumentet (Scout-audit, coach-arkitektur-noter, reviewer-
  feedback). Flyttad från `docs/llm-golden-path-references/` 2026-05-27.

Historik bevarad via `git mv` så `git log --follow <fil>` ser den fulla
versionshistoriken inklusive innan flytten.

## Inte arkiverade i detta pass (kvarliggande beslut)

- `docs/path-b-backend-scout.md` och
  `docs/scaffold-runtime-extension-needed.md` är fortfarande
  fossila (Path B fas 1+2+3a är klar enligt
  `docs/section-design-treatments-scout.md` och
  `docs/workboard.json::completedGaps`). De arkiverades inte i detta
  pass eftersom deras path-strängar är inbäddade i ~7 andra filer
  (`scripts/check_term_coverage.py` allowlist, `packages/generation/
  planning/plan.py`, `packages/generation/build/renderers.py`,
  `tests/test_backoffice_discovery_control.py`, `tooling/
  sprintvakt_mcp/core.py`, `tooling/scaffold-generator/README.md`,
  `docs/handoff.md`). En separat städ-iteration kan plocka dem.
- `docs/codeowners-proposal.md` är ett "proposal"-dokument som väntar
  på ett operatör-beslut: verkställa (skapa skarp `.github/CODEOWNERS`)
  eller arkivera. Christophers GitHub-username är känt, så
  blockeraren från originaltexten är borta.
