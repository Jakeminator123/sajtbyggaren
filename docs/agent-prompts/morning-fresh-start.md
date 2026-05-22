# Morgonstart för ny agent (2026-05-22)

Denna fil är en färdig copy-paste-prompt för en agent som startar en
helt ren session efter Dev Artifact Cleanup-rundan i natt. Använd den
som första prompt till Scout, Builder eller Steward beroende på vad
operatör väljer som nästa sprint. Allmän rolllöst läsordning står
fortsatt i [`docs/agent-prompts.md`](../agent-prompts.md) och
[`docs/agent-handbook.md`](../agent-handbook.md).

## Copy-paste-prompt

```text
Du startar en ren session i repo:t sajtbyggaren.

Läs först (i denna ordning):
- docs/current-focus.md
- docs/handoff.md
- docs/product-operating-context.md
- docs/agent-prompts.md
- README.md
- AGENTS.md
- .cursor/BUGBOT.md
- governance/policies/naming-dictionary.v1.json (skumma)

Repo-läge att förvänta:
- HEAD nära 686ab06 / efterföljande Steward-bump på main, synkat med origin/main.
- Senaste produkt-commit: 78baaa1 (chore(tooling): add dev artifact cleanup).
- Mini-eval 4/4 grön; senaste rapport under
  ../sajtbyggaren-output/.evals/20260522T030947Z-mini-eval/.
- Bug-scope: 24 aktiva, 0 misplaced, 5 unknown, 107 stängda.
- Inga öppna PRs.
- Ingen ny sprint är vald än.

Sanity-kommandon innan något annat:
- git status
- git log --oneline -5
- python scripts/focus_check.py

Det du får göra utan att fråga:
- Sanity-kommandon ovan.
- Läsa filer i repo:t.
- Köra dry-run cleanup om disken känns full
  (python scripts/cleanup_dev_artifacts.py --summary).
- Köra mini-eval i separat terminal
  (python scripts/mini_eval.py).

Det du inte får göra utan operatörens OK:
- Starta nya features eller sprints.
- Embeddings, SNI-runtime, nya starters, variant-promotion eller
  Project DNA V2.
- Implementera B125 preview-fallback (kräver beslut först).
- Radera något utan --apply.
- Röra canonical data/runs/ eller data/prompt-inputs/.
- Skriva i .cursor/rules/ direkt (källan ligger i governance/rules/).

Första svar tillbaka till operatören:

"Repo är rent på <HEAD-SHA>. Senaste landade spår är Dev Artifact
Cleanup / Eval Retention v1 (78baaa1) ovanpå B125 decision-merge
(3418cdb) och B139/B140 (eb5a81d). Ingen sprint är aktiv. Vill du att
nästa sprint blir B125 preview-fallback-implementation eller annat
smalt produktspår?"

Avsluta varje svar med säkerhet i %.
```

## Beslut som ska tas före kod

1. B125 preview-fallback. Läs först
   [`governance/decisions/0025-browser-fallback-preview.md`](../../governance/decisions/0025-browser-fallback-preview.md)
   och eventuell rapport under `docs/reports/` med prefix
   `b125-preview-fallback-decision-` innan du föreslår sprintinnehåll.
2. Annat smalt spår. Acceptabla alternativ är t.ex. en bug-sweep mot
   låg-prio B-IDs (B97/B98/B110/B111/B119/B120/B122) eller en smal
   yta kring Project Input/builder som mini-evalen pekade på. Säg
   ifrån om operatör ber om något bredare.

Vänta tills operatör väljer innan kod startas. Mindre dev-tooling
(t.ex. `python scripts/cleanup_dev_artifacts.py --summary`) räknas
inte som sprint.
