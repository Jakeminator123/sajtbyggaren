# Arkiv: current-focus kvällsblocket 2026-06-12 (~18:45, per `54de9b9c`)

> Arkiverat 2026-06-14 ~17:00 vid takeover-prep-rundan (#316 noterad i ett
> nytt 2026-06-14-block). Detta är historik — verifiera alltid mot git/koden.
> Aktuell köplan: `docs/current-focus.md`.

## Status nu (2026-06-12 ~18:45 — kvällens avslutningsrunda: #314/#315 landade, slutlig main-sync)

**Git:** `main = jakob-be` (rent träd, local == origin) efter denna rundas
slutsynk. Production deployar från `main`. Tarball-omladdningen är GJORD
efter #314 (verifierad via blob-uploadedAt 17:51:48, 27 s efter mergen) —
build-kontexten i blob speglar `de04e8f6`. #315 krävde ingen omladdning
(endast `apps/viewser/` + `tests/`). Alla PR-köer är tomma.

**Landat under kvällen (squash-mergat till `jakob-be`):**

- **#314 (uppgift G, `de04e8f6` — stänger B200/B201, ADR 0058):**
  G1 hostad answer-only — ren fråga med hög konfidens besvaras på sekunder
  utan sandbox-spinn (`apps/viewser/lib/hosted-answer-only.ts`, kortslutning
  före `startHostedBuild`); G2 preview-bundle-tarball — bygget paketerar
  publicerade fil-setet som EN tarball i blob, preview-sandboxen skapas
  direkt från den (`source=preview-bundle` i loggarna) med ärlig
  fil-för-fil-fallback för äldre sajter. Naming v41.
- **#315 (uppgift H, restpost-svep, `54de9b9c`):** dedikerad deterministisk
  `intent_not_executable`-rad i FloatingChat (no-key-fallbacken säger ärligt
  att önskemålet saknar byggförmåga — aldrig "var mer specifik"-rådet;
  LLM-answerText från #313 vinner fortsatt); rolletiketten
  `component_builder` → "komponenter" (ADR 0057). Plus hygientak-split:
  copy-directive-/change-set-låsen bor nu i
  `tests/test_viewser_copy_change_set.py`.

Eftermiddagens runda (#310–#313 + första main-synken) är historik:
[`docs/archive/current-focus-2026-06-12-em.md`](current-focus-2026-06-12-em.md).

**Nästa 3 prioriteringar:**

1. **Operatörens produktions-E2E på `main`** (görs av operatören separat —
   agenter ska INTE förekomma testet). Konkreta verifieringspunkter:
   (i) ren fråga i chatten ska svara på sekunder utan sandbox;
   (ii) första hostade bygget efter merge skapar första preview-bundlen —
   andra previewn därefter ska starta på sekunder (kolla `sourceMs` +
   `source=preview-bundle` i runtime-loggarna; äldre sajter tar
   fil-för-fil-fallback tills de byggs om);
   (iii) no-op-följdprompt ska ge ärlig no-op-rad, aldrig grön "Klart!".
2. **Uppgift I (nästa byggsteg): B197 discovery-paritet hostat** — idag
   skickas endast prompttexten in i sandboxen; discovery-svar/
   konversationskontext trådas inte. (Koordinera med Christophers spår,
   msg-0085 begärde tidig rebase på `hosted-build-runner.ts`.)
3. **Backlog/deferred (ej blockers):** dossierfälten componentSource/
   mountRules/qualityGate från E (kräver design/ADR först — ej specade i
   ADR 0054/0057); targeted-apply-trådning av
   `appliedFollowupDirectiveKinds`; blob-prune-skulden + dubbellagring av
   källan per bygge tills bundle-vägen är prod-bevisad (ADR 0058); G1:s
   medvetna klassificeringslatens (~1–3 s, 8 s tak) på byggvägen;
   `changeSet` hostat; Preview-miljöns reuse-flagga; Safari/Firefox-E2E
   för B125.

**Öppna blockers:** inga hårda.

Last verified state: `54de9b9c` (2026-06-12 ~18:45 UTC+2; squash-merge av
#315 ovanpå #314. #315-mergen krävde en hygientak-split i CI-rundan
(`test_viewser_floating_chat.py` 1221 > 1200 rader — copy-directive-/
change-set-låsen flyttade till `tests/test_viewser_copy_change_set.py`,
samma mönster som tidigare splittar). Kvällsrundan: handoff + detta block,
slutlig `jakob-be` → `main`-sync så operatörens produktions-E2E kör på
dagens fulla leverans.)
