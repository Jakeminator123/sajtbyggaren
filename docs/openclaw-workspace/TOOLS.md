# TOOLS.md — tillåtna actions för Sajtbyggarens OpenClaw

OpenClaw får BARA köra de sanktionerade actions nedan, och bara genom den
befintliga apply-kedjan (router -> context -> patch -> apply -> targeted
render). Inga fria shell-kommandon, ingen filsystemåtkomst utanför sanktionerade
ytor, inga nätverksanrop.

## Tillåtna actions (status i `action-registry.json`)
- restyle — färg/typsnitt/tema (skriver brand/tone, aldrig fri CSS)
- copy_change — namn/tagline/om-oss/tjänstetexter (per-sajt Project Input)
- section_add — montera EN sanktionerad sektion/dossier. Nio sanktionerade
  typer: team, faq, trust/garantier, recensioner, galleri, priser,
  öppettider, karta, kontaktformulär. `faq` och `team` renderar synligt på
  scaffolden local-service-business (grundad dedikerad route); övriga sju är
  mount-only tills synlig render finns (`applied=true`,
  `appliedVisibleEffect=false`). Registryts `visibleTypes` är sanningen för
  vad som syns och korsvalideras mot rollkontrakten i
  `tests/test_openclaw_registry_consistency.py`.
- component_add — lägga till en katalog-grundad komponent. Ägs av
  `component_builder`-rollen (ADR 0057), grundad i Component Catalog (ADR 0040:
  capability-map `components` + per-Starter `component-manifest.json`). PARTIAL +
  mount-only i denna slice: en component_add-följdprompt ger ett katalog-grundat
  svar ELLER en ÄRLIG no-op som pekar på det kurerade shadcn-intaget
  (`scripts/component_intake.py`) — den monterar inget och skriver inga filer
  (kedjan rapporterar no-op:en via `unappliedFollowupIntents`). Att vendorera in
  en ny komponent förblir en operatörs-PR (intag → granskning → Starter), aldrig
  en runtime-montering.
- layout_change — flytta/ordna sektioner (planerad)
- site_review — svara/granska read-only, ingen build. Ägs av dispatchern
  (router-rollen) by design — ingen egen agentroll och inget eget
  rollkontrakt.

## Samtalsgrinden (svar utan bygge)
Dispatchern besvarar `small_talk`, `site_opinion` och `question` direkt i
chatten utan build. Sanningskällan är `ANSWER_ONLY_CONVERSATION_KINDS` i
`packages/generation/orchestration/openclaw/roles.py`, speglad av
`scripts/run_openclaw_followup.py` och Viewsers `/api/prompt`-route. En edit
klassas alltid som edit och byggs (eller blir ärlig no-op) — den besvaras
aldrig som konversation, och en frågeformad edit ("kan du lägga till en
faq-sektion?") byggs, besvaras inte.

## Dossier-arbete: läs formatguiden först
En agent/roll som ska montera, författa eller ändra en dossier läser FÖRST
`packages/generation/orchestration/dossiers/AGENT-GUIDE.md` — den låser
manifest-fälten, de fem instructions-sektionerna, soft/hard-reglerna och
konsumtionsvägen (capability-map -> selectedDossiers -> mount -> ev. synlig
render). Schema: `governance/schemas/dossier.schema.json`. Guiden är
förhandsinfon som gör att merparten av implementationen kan plockas färdig
ur dossier-kitet i stället för att uppfinnas.

## Förbjudet
- fri filpatch i genererad output
- ändring av delade mallar för en enskild sajts effekt
- nya dependencies utan policy + operatörsgodkännande
- extern nätverksåtkomst, daemon eller gateway-process
- påhittade fakta i kundcopy

## Princip
Ett förmågekort (`skills/<namn>/SKILL.md`) är text, inte behörighet. En action
körs bara om den (1) finns sanktionerad här, (2) har en apply-väg, och (3)
klassas av routern. Saknas något -> ärlig no-op.
