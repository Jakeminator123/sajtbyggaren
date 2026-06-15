# Handoff – Sajtbyggaren

**Datum:** 2026-06-15 ~17:30 UTC+2 — `main = jakob-be = cd9bb0ba` + denna rundas
commits. Stor-plan-/orienteringsrunda för nästa orchestreringsagent: route_remove
härdat (#333) + en SystemExit-fix, delivery-bias (#330) och build-context-guard
(#331) mergade, floaters städade. Köplan: [`docs/current-focus.md`](current-focus.md).

## ORIENTERING FÖR NÄSTA ORCHESTRERINGSAGENT (AUKTORITATIVT — läs först)

**Detta är det enda auktoritativa blocket. Allt nedan är historik — verifiera
alltid mot git/koden.**

### Vad vi bygger (north star)

Bättre småföretagshemsidor via kärnloopen `prompt → företagshemsida → preview →
följdprompt → ny version`, mål 9/10 i kvalitet. Operatören (Jakob) testar live på
hostad prod (`sajtbyggaren-viewser.vercel.app`). Allt arbete ska tjäna den loopen;
docs/tester är medel, inte mål (se `docs/delivery-bias.md`).

### Arkitekturen: två flöden + en brygga

- **Grundflödet (KÖR-kedjan)** — `scripts/build_site.py:run_followup_chain`:
  `router → context → patch → apply → targeted render`. Deterministiskt, ärligt
  (ingen falsk success), validerat. Det som faktiskt bygger och ändrar sajten.
- **Tunga LLM-flödet (dirigenten)** — `OpenClaw Core decide()` i
  `packages/generation/orchestration/openclaw/`: klassar konversationsart, väljer
  roll, ger grundade planeringssvar, väljer contextLevel. En REN funktion (ingen
  disk/build/nätverk).
- **Action-bryggan** — `scripts/run_openclaw_followup.py --apply`: dirigenten
  beslutar; för en edit DELEGERAR den till KÖR-kedjan. Konsumeras av Viewser i
  `apps/viewser/app/api/prompt/route.ts`.

### Stora planen: sammanfläta de två flödena (4 faser)

Syftet: göra dirigenten till FÖRAREN av kärnloopen, inte bara en grind. Regel: ny
förmåga läggs som en roll + skill + editKind som dirigenten dispatchar genom EN
kedja — aldrig en parallell silo. Roadmap-detalj:
[`docs/heavy-llm-flow/conductor-vision-roadmap.md`](heavy-llm-flow/conductor-vision-roadmap.md).

| Fas | Innebörd | Status |
|-----|----------|--------|
| 1 — beslutsenhet | Kedjan ska KONSUMERA dirigentens routerbeslut i st.f. att klassa om (`run_followup_chain` rad ~4189 klassar idag om → två beslutsytor, upp till två modellanrop, driftrisk). | KVAR — kärnan |
| 2 — roll-driven exekvering | Dirigentens roll väljer exekutor (`stylist`/`section_builder`/`route_editor`/`copy`/`component_builder`). | Mönster KLART (`route_editor` bevisade det), generaliseras |
| 3 — contextLevel driver kontext | Dirigentens contextLevel styr vad exekutorn assemblar. | Delvis (kedjan respekterar level, dirigenten driver inte) |
| 4 — generativ förmåga | Exekutor som skriver NY tsx-kod säkert (sandbox + versionering + quality-gate) → stänger "lägg till modal/knapp/ny komponent"-glappet. | KVAR — störst hävstång |

### Vad som är gjort (de senaste passen)

- **Route/Nav Mutation V1 (ADR 0060)** — ta bort sida + nav + interna länkar:
  Slice A (#328, icke-obligatorisk sida), Slice B (#332, contact + CTA-retarget +
  länk-scan), härdning av 5 review-fynd (#333), samt en SystemExit-fix i
  `_base_disabled_route_ids` (denna runda). route_remove lades som editKind +
  `route_editor`-roll + skill + action-registry → BEVISADE fas 2-mönstret.
- **#320** bygg-kort (perceived latency), **#329** test-tiers (markers),
  **#330** delivery-bias-guardrail (`docs/delivery-bias.md`), **#331**
  build-context-guard (`npm run build-context:check` + KV `sha`/`dirty` + SHA-logg).
- Model routing v13 (`llm-models.v1.json`), ADR 0059 slice 1 (`pricing` synlig
  `/priser`), direktiv-läckage-fix — alla i prod.

### Kapacitetsspår (delivery-bias: förmåga före kartläggning)

- **nav-only** (`nav_edit`: "dölj i menyn men behåll sidan") — liten, naturlig
  efter route_remove-fynd 4.
- **generativ komponent V1** (fas 4) — störst effekt mot "lägg till"-glappet.
- **katalog-render synlig** (reviews/trust, ADR 0059) — kräver operatörens
  visuella riktning.
- Skjutna route_remove-fynd: fynd 1 (`site-plan.json` listar borttagna routes —
  ren artefakt-drift; `build()` omfiltrerar, route-scan grön) + fynd 3
  (`ecommerce-lite` catch-all `[page]/page.tsx`).

### Driftregler (viktigast för nästa agent)

- **Efter en Python/generation/OpenClaw-ändring som ska till hostad prod: kör
  `cd apps/viewser && npm run build-context:upload`.** Den paketerar
  `scripts/`+`packages/`+`governance/`+`data/starters/` till en tarball, laddar
  upp den till blob och sår nu även KV `sha`/`dirty` (#331). `npm run
  build-context:check` varnar om KV-SHA ≠ git för de ytorna. Annars kör hostad
  prod gammal Python.
- Viewser-appen (tsx, t.ex. route_remove-fynd 6) deployar via Vercel från `main`.
- Underagenter sparsamt (AGENTS.md). Read-only referensmappar rörs ALDRIG.
- jakob-be + main: governance-CI kör på push till BÅDA (inte bara PR).

### Git nu

`main = jakob-be = origin/main = origin/jakob-be = cd9bb0ba` (+ denna rundas
SystemExit-fix- och docs-commits). Öppen PR: #324 (Christophers viewser UI/UX —
väntar operatörens browser-check). Cloud-agenterna bakom #330/#331 är klara
(PR mergade) och kan stängas.

## Historik

Allt äldre än det auktoritativa orienteringsblocket ovan är flyttat till
[`docs/archive/2026-06/handoff-history-2026-06-15.md`](archive/2026-06/handoff-history-2026-06-15.md)
(arkiv = historik, inte sanningskälla — verifiera mot git). Den filen länkar i sin
tur vidare till äldre handoff-historik. Hela versionshistoriken finns kvar via
`git log --follow docs/handoff.md`.
