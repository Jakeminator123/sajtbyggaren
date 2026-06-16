# ADR 0064 — cta-contact-block som deterministiskt generativt recept

**Status:** Accepted
**Datum:** 2026-06-16
**Beroenden:** ADR 0061 (Generative Component V1), ADR 0057
(component_builder äger component_add), ADR 0015 (Quality Gate + Repair).
Källor:
[`packages/generation/followup/generative_component_directives.py`](../../packages/generation/followup/generative_component_directives.py),
[`packages/generation/codegen/followup_emit.py`](../../packages/generation/codegen/followup_emit.py),
[`governance/schemas/project-input.schema.json`](../schemas/project-input.schema.json).

## Kontext

`image-placeholder-grid` bevisade rälsen för att materialisera en ny `.tsx`
från en följdprompt utan fri LLM-codegen: resolver -> sticky direktiv ->
deterministisk mall -> splice i `page.tsx` -> vanlig build och Quality Gate.
Nästa smala produktsteg är en tydlig kontakt-/boknings-CTA, eftersom
småföretagarsajter ofta förbättras av en följdprompt som "lägg till en
kontaktknapp", "lägg till en kontaktruta", "boka" eller "offert".

## Beslut

Vi lägger till `cta-contact-block` som andra vitlistade deterministiska recept
på exakt samma rails som ADR 0061:

- `GENERATIVE_RECIPES` känner igen receptet via befintligt router-intent
  `contact_button` samt cues: `kontaktruta`, `boka`, `offert`, `cta` och
  `kontaktknapp`.
- Receptet skriver ett sticky `directives.generativeComponents`-direktiv med
  `recipe="cta-contact-block"`, `id="cta-contact-block"`, `routeId="home"` och
  fast `count=1`.
- Placering återanvänder samma kanoniska `position`-fält som bildgridreceptet:
  `top` splice:as direkt efter öppnande `<main>`, `bottom` och default splice:as
  före avslutande `</main>`. `left`/`right`/`center` ignoreras som
  intra-sektionsplaceringar.
- Emit-mallen är en Server Component utan imports, utan nya npm-beroenden och
  utan fri LLM-kod.

## Grundning av kontaktfakta

Receptet får inte hitta på telefonnummer, e-postadresser eller kontaktvägar.
Emit-lagret får bara receptspecen och build-katalogen, inte Project Input
`contact`-objektet eller scaffoldens faktiska route-path. Därför renderar första
skivan en generisk CTA med säker svensk copy och en knapp-liknande label, men
inga `tel:`/`mailto:`-länkar, inga direkta kontaktvärden och ingen gissad
`/kontakt`-länk. En senare slice kan tråda in redan grundad kontaktdata i specen
och då låta mallen rendera den.

## Konsekvenser

- Plus: component_add får en andra synlig förmåga som hjälper kärnloopen
  `prompt -> företagshemsida -> preview -> följdprompt -> ny version` utan att
  öppna fri codegen.
- Plus: OpenClaw-registret och `component_builder`-rollkontraktet listar båda
  `image-placeholder-grid` och `cta-contact-block` som synliga undantag från
  mount-only-defaulten.
- Minus: CTA-knappen är inte en route-länk i denna skiva, eftersom en hårdkodad
  kontaktväg vore ogroundad på scaffolds som inte använder `/kontakt`.
- Fortsatt: okända eller icke-vitlistade komponentfamiljer blir ärliga no-op
  (t.ex. `generative_unsupported`), aldrig en påhittad komponent.
