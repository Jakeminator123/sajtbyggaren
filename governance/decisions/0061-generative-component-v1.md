# ADR 0061 — Generative Component V1 (image-placeholder-grid via materialize + Quality Gate)

**Status:** Accepted
**Datum:** 2026-06-15 (Fas 4, minsta säkra skiva)
**Beroenden:** ADR 0057 (component_builder äger component_add),
ADR 0040 (Component Catalog), ADR 0060 (Route/Nav Mutation V1 — samma
direktiv-/sticky-/honest-no-op-mönster), ADR 0015 (Quality Gate + Repair),
B157 (immutabla builds + atomisk current.json-swap).
Källor: [`packages/generation/followup/generative_component_directives.py`](../../packages/generation/followup/generative_component_directives.py),
[`packages/generation/codegen/followup_emit.py`](../../packages/generation/codegen/followup_emit.py),
[`scripts/build_site.py`](../../scripts/build_site.py).

## Kontext

Kärnflödet `prompt -> företagshemsida -> preview -> följdprompt -> ny version`
saknar fortfarande "lägg till en ny komponent". component_add var partial och
mount-only (ADR 0057): en följdprompt kunde inte materialisera en NY `.tsx`.
Att direkt öppna fri LLM-genererad kod är för riskfyllt som första steg — det
behöver bevisade rails för att skriva ny tsx säkert, köra den genom Quality
Gate och kunna rulla tillbaka. Den här skivan bevisar rälsen med EN vitlistad,
deterministisk komponent i stället för fri codegen.

## Alternativ

- Fri LLM-codegen direkt (codegenModel skriver godtycklig tsx). Avvisat nu:
  ingen write-path-räls bevisad, hög hallucinations-/säkerhetsrisk.
- En ny dossier per komponenttyp. Avvisat: dossiers är operatörskurerade
  PR-artefakter (intag -> granskning -> Starter), inte en följdprompts-väg.
- Ett vitlistat, deterministiskt recept genom den befintliga pipelinen.
  **Valt.**

## Beslut

Generative Component V1 är EN vitlistad, deterministisk recept-väg på den
befintliga component_add-rollen (`component_builder`):

- Recept-allowlist (`GENERATIVE_RECIPES`): V1 = endast `image-placeholder-grid`
  (ett responsivt rutnät av bildplatshållare; "lägg till 6 bildplatshållare",
  "lägg till en bildgrid"). Routern klassar receptets noun som component_add
  (componentIntent `image_placeholder_grid`) — ingen ny router-enum.
- Resolver (`resolve_generative_component`) tolkar antalet ur prompten (klamp
  1..12, default 6) och löser routeId (default home). En igenkänd men ostödd
  genererings-familj (en karusell) refuseras ärligt (stage
  `generative_unsupported`); en icke-generativ component_add (en klocka/ett
  kontaktformulär) faller igenom till den befintliga mount-only-no-op:en
  byte-för-byte. Aldrig en påhittad komponent.
- Apply skriver specarna STICKY på `directives.generativeComponents` (union per
  id), precis som `disabledRoutes`/`hiddenNavRoutes`.
- Buildern (`materialize_generative_components`) skriver EN ny Server Component
  under `components/generated/<id>.tsx` från en deterministisk recept-mall och
  splice:ar in import + användning i routens `page.tsx` före stängande `</main>`
  — efter write_pages och FÖRE npm, så den nya filen typkollas, byggs och gatas
  av samma Quality Gate / Repair / immutabla versionering. Ett misslyckat
  bygge/QG swappar aldrig `current.json` (ärvt från `build()`).

## Write-path-vakter (fail closed)

`followup_emit` validerar varje skrivning innan disk: målet måste ligga INUTI
build-katalogen; `package.json`/`package-lock.json`/`.env*`/allt under
`node_modules` refuseras (`GenerativeEmitError`); ett okänt recept eller ett id
som inte är en säker filslug (mönster `^[a-z0-9][a-z0-9-]*$`, ingen traversal)
höjer fel. En routeId vars `page.tsx` saknas blir en ärlig skip (ingen
orphan-fil), aldrig en krasch. Materialiseringen är idempotent: samma direktiv
dubbelinjicerar aldrig import eller användning.

## Placement / position (följdprompt)

En följdprompt som namnger en placering ("lägg till 6 bildplatshållare högst
upp" / "längst ner") respekteras genom att ÅTERANVÄNDA det kanoniska
`position`-fältet — samma `top`/`bottom`-tokens som mountade sektioner och
`RouterTarget.position` (routerns `_detect_position`), inte ett nytt
`placement`-fält. Resolvern läser `decision.target.position` och skriver
`spec["position"]` endast för `top`/`bottom` (intra-sektions-placeringar som
`left`/`right`/`center` ignoreras, de är inte route-ordnings-slots — speglar
`scripts/build_site.py` `section_positions`). Buildern splice:ar då in
användningen direkt efter öppnande `<main>` (`top`, första barn före hero)
respektive före avslutande `</main>` (`bottom`). En utelämnad position behåller
default-slotten före `</main>` (oförändrat, byte-identiskt beteende); en
`top`-begäran på en sida utan öppnande `<main>` faller tillbaka till
default-slotten i stället för att skippa.

## Inga nya beroenden

Mallen använder bara Tailwind-klasser som scaffolden redan levererar (inga
`next/image`-remote-config, inga nya npm-paket). Inga nya Python-beroenden.

## Termer

Allt kod- och fältnamn på engelska (`generativeComponents`, `recipe`, `count`,
`routeId`, `id`, `image-placeholder-grid`); operatörsvänd text på svenska.

## Konsekvenser

- Plus: bevisar rälsen att skriva ny tsx säkert + QG + rollback med noll ny
  codegen-risk; component_add blir supported (mount-only default + ett synligt
  recept); honest no-op bevarad för all icke-recept-component_add.
- Minus: bara ETT recept och bara home-routen i V1; antalsuppdatering på samma
  id är en senare skiva (sticky-union är first-wins per id); fri LLM-codegen för
  godtyckliga komponenter följer i en senare skiva ovanpå denna räls.
