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
| 1 — beslutsenhet | Kedjan KONSUMERAR dirigentens routerbeslut (`run_followup_chain(decision=...)`); en beslutsyta, max ett modellanrop. | ✅ KLAR (#338) |
| 2 — roll-driven exekvering | Dirigentens roll väljer exekutor (`stylist`/`section_builder`/`route_editor`/`copy`/`component_builder`). | ✅ Bevisad + generaliserad (route_editor + nav_hide + component_builder) |
| 3 — contextLevel driver kontext | Dirigentens contextLevel styr vad exekutorn assemblar. | 🟡 DELVIS — KVAR (kedjan respekterar level, dirigenten driver inte fullt) |
| 4 — generativ förmåga | Exekutor som skriver NY tsx-kod säkert (sandbox + versionering + quality-gate) → "lägg till modal/knapp/ny komponent"-glappet. | ✅ V1 KLAR (#341 — image-placeholder-grid genom build+QG+versionering, deterministiskt recept). V2 (fler recept / fri TSX) KVAR |

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

### Vad funkar i prod nu (för operatörens live-test)

Kärnloopen `prompt → hemsida → preview → följdprompt → ny version` är live. Följdpromptar som FUNGERAR (synlig ny version):
- Stil/tema ("gör sajten mörkblå/premium"), copy ("byt rubriken till X").
- Sektion: faq/team/hours/gallery (synliga); reviews/trust/pricing/location monteras (delvis synliga).
- **ta bort sida** ("ta bort sidan Om oss") + **dölj nav-länk** ("dölj Om oss i menyn", nav_hide).
- **generativ V1**: "lägg till 6 bildplatshållare" / "lägg till en bildgrid" → genererar en ny komponent.
- Rena frågor ("vad kan du göra?") svaras direkt utan bygge (chat-fixen live).

**Känd begränsning (nästa spår):** tyngre edits (allt som rebuildar) kör en kall bygg-sandbox → **minuter**, och kan slå i sandbox-TTL (410 SANDBOX_STOPPED). Inte en bugg — hostad edit-perf-luckan.

### Kapacitetsspår (delivery-bias: förmåga före kartläggning)

- **Hostad edit-perf/pålitlighet** (störst praktiskt värde nu): skippa `next build`
  för direktiv-edits (minuter→sekunder); höj sandbox-TTL + `VIEWSER_SANDBOX_REUSE`;
  cacha pip. Tar bort 410-känslan i prod.
- **Förstaversionens kvalitet 8.2 → 9/10**: eval-driven — tema-trohet, inga
  påhittade tjänstekort (grundning/wizard). Embeddings förblир PARKADE (ADR 0026).
- **reviews/trust synliga** (ADR 0059) — kräver operatörens visuella riktning.
- **generativ V2** (fas 4) — fler recept / sandboxad fri TSX, ovanpå V1-rälsen.
- **Fas 3** — låt dirigentens contextLevel driva kontext-assemblingen.
- Skjutet (ej blockerande): route_remove fynd 3 (`ecommerce-lite` catch-all, B205).

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

`main = jakob-be = origin/main = origin/jakob-be = cd6eec9f`. build-context
(Python-motorn) uppladdad + i synk → Fas 1 + generativ V1 live i hostad prod.
Öppen PR: **#324** (Christophers viewser UI/UX — väntar operatörens browser-check;
rör viewser-UI-filer, INTE vår route.ts/openai.ts/Python, men är stale mot färska
`jakob-be` → Christopher bör rebasa #324 innan merge). `origin/christopher`-branchen
ligger långt bakom main (rebasas per pass enligt lane-modellen, klobbrar inte vårt).

## Historik

Allt äldre än det auktoritativa orienteringsblocket ovan är flyttat till
[`docs/archive/2026-06/handoff-history-2026-06-15.md`](archive/2026-06/handoff-history-2026-06-15.md)
(arkiv = historik, inte sanningskälla — verifiera mot git). Den filen länkar i sin
tur vidare till äldre handoff-historik. Hela versionshistoriken finns kvar via
`git log --follow docs/handoff.md`.
