---
status: active
owner: governance
truth_level: historical-reference
last_verified_commit: f56ac30
---

# Arkiverade docs — 2026-06

Historiska handoffs, scout-rapporter, spikes, health-checks och engångs-
agentprompter som inte längre styr aktivt arbete. Flyttade hit i docs
honesty-cleanup-passet (lane A, 2026-06) efter att deras roll tagits över av
`docs/current-focus.md`, `docs/handoff.md` (toppblock) och `docs/workboard.json`.

> **Arkiv = historik, inte sanningskälla.** Se [`../README.md`](../README.md).
> För nuläget: `docs/current-focus.md` + `docs/handoff.md` toppblock. Verifiera
> alltid mot git/koden, aldrig mot ett arkiverat block. Arkivet får inte
> användas som aktuell köplan.

Historik bevaras via `git mv` — `git log --follow <fil>` visar hela
versionshistoriken inklusive innan flytten.

## Flyttade filer i detta pass

- `handoff-viewser-ui-overhaul-2026-06-03.md` — historisk Christopher-UI-handoff;
  superseded av current-focus + handoff. Flyttad från `docs/`.
- `section-design-treatments-scout.md` — historisk scout-rapport (ADR 0032,
  Phase 1+2+3a shipped). Flyttad från `docs/`.
- `codeowners-proposal.md` — förslag utan aktivt arbete (ingen `.github/CODEOWNERS`).
  Flyttad från `docs/`.

## Steward-pass 2026-06-09 (docs-steward-cleanup)

- `current-focus-2026-06-09-pre-refresh.md` — full snapshot av `docs/current-focus.md`
  precis före steward-refresh till `0c89942` (stale `Last verified state: 2ffce4a` +
  "14 commits före main" bumpades till verklig HEAD/`32`). Superseded av
  `docs/current-focus.md`.
- `handoff-history-2026-06-09.md` — historik utbruten ur `docs/handoff.md` (allt som
  låg under topblockets historiklinje `---`). `docs/handoff.md` behåller bara det
  auktoritativa toppblocket + länk hit. Superseded av `docs/handoff.md` toppblock +
  `docs/current-focus.md`. `git log --follow docs/handoff.md` visar hela historiken.

## Heavy-llm-flow honesty-pass 2026-06-12

- `handoff-orchestration-heavy-llm-flow-2026-06-03.md` — historisk
  orchestrerings-handoff. Flyttad från `docs/heavy-llm-flow/` eftersom den
  aktiva texten påstod att follow-up-bryggan inte var inkopplad i någon
  användarväg; `/api/prompt` använder nu OpenClaw apply-bryggan.
- `post-build-plan-heavy-llm-flow-2026-06-04.md` — historisk post-build-plan.
  Flyttad från `docs/heavy-llm-flow/` eftersom statusen om `/api/prompt`,
  kor-5 repair och hostad 501 är förbi-sprungen av dagens kod. Stubben i
  `docs/heavy-llm-flow/post-build-plan.md` pekar till aktuell README-status.

## Markerade historical *på plats* (ej flyttade)

Vissa historiska docs behölls på sin ursprungssökväg och fick bara
`status: historical` + arkivnot, eftersom en flytt antingen bryter en guard
eller blockeras av repo-secret-scannern:

- `docs/migration-plan.md` — `tests/test_decisions_and_docs.py` kräver sökvägen.
- `docs/path-b-backend-scout.md` — inbäddad i runtime-kommentarer.
- `docs/scaffold-runtime-extension-needed.md` — inbäddad i runtime-kommentarer + sprintvakt-seed.
- `docs/handoff-pr-117-merge.md` — branch-referens blockeras vid filflytt.
- `docs/diagnosis-and-handoff-2026-06-08.md` — branch-referens blockeras vid filflytt.
