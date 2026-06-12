# Arkiv: current-focus nattpassblocket 2026-06-12 (~03:30, per `575af63b`)

> Arkiverat 2026-06-12 ~05:45 vid gryningsstängningen. Detta är historik —
> verifiera alltid mot git/koden. Aktuell köplan: `docs/current-focus.md`.

## Status nu (2026-06-12 ~03:30 — nattpass: hostad paritet-fixar shippade, två cloud-prompter köade)

**Git:** `main = jakob-be` (rent träd, local == origin). Senaste
kod/canvas-commit `575af63b`; detta docs-pass ligger ovanpå. Production
(`sajtbyggaren-viewser.vercel.app`) kör senaste app-bygget; rena docs-pushar
skippar prod-rebuild med flit (`ignoreCommand` jämför mot
`VERCEL_GIT_PREVIOUS_SHA`, fallback `HEAD^`), så prod kan peka på senaste
app-ändringen snarare än main-HEAD — väntat monorepo-beteende.

**Shippat i natt (efter midnattsblocket):**

- Banner-ärlighet: "lokalt" = operatörens lokala miljö, inte den hostade
  vyn (`4162a14a`).
- Flagg-medveten hostad notis: med `VIEWSER_ENABLE_HOSTED_BUILD=1` säger
  bannern att byggen kör i Vercel Sandbox, bara historik/artefakter är
  lokala (`bc074edb`).
- Hostad builder-paritet, live-bevisad: FloatingChat tänds när ett bygge
  slutförts i sessionen även med tom `/api/runs`, och följdprompt-byggen
  överlever rebuild hostat via selectedSiteId-fallback (`cdd6785d`,
  `b4f6e2d2`).
- Hostade artifacts/trace/files-404:or tystade i UI:t (lugn notis + latch i
  stället för rött fel och meningslös polling) + B199 dokumenterar
  blob-utredningen (`691bd835`).
- Härdad preview readiness-poll: 502/503/429 räknas inte som "klar", så
  hostad preview inte visar sandbox-uppstart som fel (`15ea0fda`).
- Canvas-rättningar: `OPENAI_MODEL` är `gpt-5.4` i prod (`ed0a2039`),
  autogen-facts regenererad (llmModelsVersion 12, hard-dossier 1)
  (`42a54945`), env/fallback-callout rättad (`575af63b`).
- Sedan midnattspasset: `main` låst med ruleset "protect-main-production-lane"
  och `ignoreCommand`-fällan fixad (`74dc9218`).

**Verifierat/avlivat i natt:**

- Pipen är hybrid (`gpt-5.4` för brief/plan/copy, deterministisk codegen) —
  inte "rent mekaniskt".
- Ingen automatisk `gpt-5.4` → `gpt-5.5`-modellfallback finns (det var en
  sammanblandning); kod-fallbacken `gpt-5.5` träffar bara när env-nyckeln
  saknas.
- Env-domar (lämna osatta på Vercel): `OPENCLAW_ROUTER_LLM_FALLBACK` är
  no-op i hostad väg och `VIEWSER_SANDBOX_REUSE` är disk-only (ingen effekt
  hostat).
- Extern review verifierad: hostat KÖR-7-paritetsgapet är PARTIELLT, inte
  total avsaknad — legacy-vägen kör copy-directives.

**Öppna issues:** B199 (hostad artefakt-hydrering — förutsättning för hostad
KÖR-7), B197 (discovery-paritet hostat), B198 del b (contact-form-render;
fungerar redan hostat via legacy-vägen).

**Köade cloud-prompter (PR:as mot jakob-be):**

1. Hostad follow-up-paritet — tre ordnade commits (B199-hydrering → sandbox
   apply-seam → request/response-paritet), root-cause-ledd, körs först.
2. B198 del b contact-form-render — oberoende spår.

Vår action: reviewa inkommande cloud-PR:ar snabbt (lane review-SLA).

Last verified state (då): `84d4facf` (2026-06-12 ~03:30 UTC+2; `main = jakob-be`,
rent träd, local == origin. Nattpassets kod/canvas-checkpoint `575af63b` +
docs-pass ovanpå. Hostad paritet-fixar `4162a14a`/`bc074edb`/`cdd6785d`/
`b4f6e2d2`/`691bd835`/`15ea0fda` + canvas-rättningar `ed0a2039`/`42a54945`/
`575af63b`. Öppen draft-PR: #306 (B198 del b).)
