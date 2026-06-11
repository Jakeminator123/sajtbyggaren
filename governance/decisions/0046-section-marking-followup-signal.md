# ADR 0046 — Sektionsmarkering som följdprompt-signal

**Status:** Accepted
**Datum:** 2026-06-10
**Beroenden:** ADR 0034 (copyDirective-kontraktet), B155 (ärliga
no-op-signaler i build-result.json). Markörinjektionen i codegen
(`data-section-id` + `emittedSections` i build-result.json) är
förutsättningen och landade i samma arbetspaket.

## Kontext

Operatören kan nu klicka "Markera modul" i preview-overlayn (viewser)
och peka ut upp till fem sektioner på den genererade sajten. Klicket
fångas via element-map (server-sidans Playwright-insamling) — previewn
är cross-origin, så vi läser aldrig iframe-DOM direkt. Frågan är hur
markeringen får påverka följdprompt-pipelinen utan att bryta de
befintliga ärlighetsgarantierna (ingen påhittad effekt, ingen gissning).

## Beslut

1. **Vokabulär.** En markering är `{routeId, sectionId, note?}`.
   `routeId` kommer ur base-runens `site-plan.json` routePlan och
   `sectionId` ur scaffoldens `sections.json`-vokabulär — samma id:n som
   dispatchern stämplar som `data-section-id` i genererade sidor och som
   `build-result.json` samlar i `emittedSections`. `note` är fri text
   (overlayn skickar sektionens rubriktext) och behandlas alltid som
   opålitlig kontext, aldrig som instruktion.
2. **Transport.** `/api/prompt` får ett valfritt fält
   `markedSections` (max 5 poster, endast follow-up-läge). Viewser
   skickar fältet vidare som CLI-flagga `--marked-sections <json>` till
   `scripts/prompt_to_project_input.py` (kräver `--followup-site-id`).
   Samma markeringar skickas som `RouterContext.routeSections`-payload
   till den deterministiska router-klassificeringen
   (`scripts/classify_message.py --route-sections`).
3. **Ärlighetsgrindar.** Python-sidan validerar varje markering mot
   base-runens facit innan den används:
   - Primärt: `emittedSections` i base-runens `build-result.json`
     (suppression-aware — en sektion som aldrig renderades kan inte
     markeras i efterhand).
   - Fallback för äldre runs utan markörer: routePlan-id:n ur
     `site-plan.json` + sektionsvokabulären i scaffoldens
     `sections.json`.
   - Okänd route/sektion ⇒ markeringen droppas med en varningspost
     (`droppedFocusSections` på meta-sidecaren, speglad i
     build-result.json). Aldrig gissning, aldrig tyst remapping.
4. **Mjuk signal.** Validerade markeringar är kontext/prioritering:
   de berikar copyDirective-planerarens site-state och styleDirective-
   extraktorns prompt med en fokus-notis, så "skriv om texten här"
   binder till rätt fält. En markering triggar ALDRIG ensam en build,
   ändrar aldrig `classify_followup_intent`-utfallet och utökar inte
   copyDirective-target-enumen — hero-copy nås fortfarande bara via
   `tagline`-mappningen. Ny target-vokabulär är ett separat ADR-beslut.
5. **Spårbarhet.** Validerade markeringar skrivs som
   `appliedFocusSections` på meta-sidecaren och speglas i
   `build-result.json`, där viewsers changeSet
   (`lib/run-change-set.ts`) plockar upp dem så FloatingChat kan visa
   vad operatören pekade på i den version som byggdes.

## Kända begränsningar

- `render_about` m.fl. sidshims har flera logiska block i en enda
  `<section>` — markeringen blir sidnivå-grov där tills shimsen styckas
  upp.
- Äldre runs utan `emittedSections` valideras mot scaffoldens deklarerade
  vokabulär, som är en superset av vad som faktiskt renderades —
  fallbacken kan alltså godkänna en markering mot en suppressad sektion.
  Det är acceptabelt eftersom signalen är mjuk (kontext, aldrig build).
- Routerns deterministiska heuristik använder `routeSections` endast som
  kontext för `sectionOrdinal`-upplösning; ingen ny messageKind har
  införts (router-decision-schemat är orört).

## Konsekvenser

- `prompt_to_project_input.py` får flaggan `--marked-sections` och
  meta-sidecaren två nya valfria fält (`appliedFocusSections`,
  `droppedFocusSections`). Båda är additiva — utan markeringar är
  flödet byte-identiskt med tidigare beteende.
- Valideringen och fokus-notisen ägs av
  `packages/generation/followup/marked_sections.py`; tester låser
  grindarna (okänd sektion droppas med varning, max 5, dedupe).
