# Arkiv: current-focus-block 2026-06-12 ~16:00 (eftermiddagens avslutningsrunda, #310–#313 + main-sync)

Flyttat hit från `docs/current-focus.md` när kvällens avslutningsrunda
(#314/#315 mergade, slutlig main-sync) tog över som aktuellt block.

## Status nu (2026-06-12 ~16:00 — avslutningsrunda: dagens mergar landade, main synkad för produktionstest)

**Git:** `main = jakob-be` (rent träd, local == origin) efter denna rundas
main-sync. Production deployar från `main`. Tarball-omladdningen är GJORD
(efter #312/#313-mergarna, se handoff) — build-kontexten i blob speglar
`56dc754f`. Alla PR-köer är tomma; sessionsbranches och worktrees städade
(se handoff).

**Landat under eftermiddagen (squash-mergat till `jakob-be`):**

- **#310 (ADR 0056, dossier-dependencies):** dossierer deklarerar pinnade
  npm-paket som följer med in i genererad `package.json`; npm ci med
  install-fallback.
- **#311 (Projektinnehåll-panelen):** site-composition-API +
  panel i ConsoleDrawer som visar sidor/dossiers/komponenter/paket,
  deriverat ur befintliga run-artefakter (lokalt + hostat).
- **#312 (uppgift E, komponentintag v1):** kurerad shadcn-intake-CLI
  (`scripts/component_intake.py`, ADR 0054), component_builder-rollkontrakt
  (ADR 0057), zero-dep accordion-pilot synlig på FAQ, naming v40,
  repo-boundaries v13, ny pip-dep `openai-agents==0.17.5`.
- **#313 (del F+D, ärlighetsfix):** `appliedFollowupDirectiveKinds`-signal +
  `intent_not_executable` stoppar falska "Klart!" (byte-diff räcker inte
  längre som framgångsbevis); ärlig okänd-slug i `unappliedFollowupIntents`;
  honesty-gates kräver konkreta direktiv; `generateFollowupOutcomeSummary`
  ger ärlig LLM-svarsrad på varje följdprompt.

Förmiddagens ADR 0055-pass (preview-standardisering) + hotfixarna är
historik: [`docs/archive/current-focus-2026-06-12-middag.md`](current-focus-2026-06-12-middag.md).

**Nästa 3 prioriteringar (som de stod):**

1. **Operatörens produktionstest på `main`:** hela E2E-flödet på `/studio`
   i produktion (init → pre-built preview → no-op-följdprompt → edit-
   följdprompt → reuse), nu inklusive #312/#313-beteendet. Görs av
   operatören separat — agenter ska INTE förekomma testet.
2. **Uppgift G (nästa byggsteg):** snabb chat utan sandbox-spinn för rena
   frågor + tarball-bundling för förbyggda previews.
3. **Backlog/deferred (ej blockers):** componentSource/mountRules/
   qualityGate-dossierfälten från E; viewser-rolletikett för
   component_builder; deterministisk intent_not_executable-rad för
   no-key-fallet från F+D; B197 discovery-paritet hostat (Christophers,
   tidig rebase msg-0085); blob-/KV-prune; `changeSet` hostat;
   Preview-miljöns reuse-flagga; Safari/Firefox-E2E för B125.

**Öppna blockers:** inga hårda.

Last verified state (som den stod): `56dc754f` (2026-06-12 ~16:00 UTC+2;
squash-merge av #313 ovanpå #312/#311/#310-kedjan. Avslutningsrundan:
branch-/worktree-städning, known-issues-städning (B195 flyttad till Stängda,
B155-slice för #313), handoff + detta block, `main` synkad till samma
innehåll för operatörens produktionstest. Tarball-omladdningen till blob
`build-context/current.tar.gz` gjordes direkt efter #313-mergen.)

PR-läget som det stod: inga öppna. #306–#313 squash-mergade till `jakob-be`
och synkade till `main`.
