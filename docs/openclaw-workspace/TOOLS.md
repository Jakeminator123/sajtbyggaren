# TOOLS.md — tillåtna actions för Sajtbyggarens OpenClaw

OpenClaw får BARA köra de sanktionerade actions nedan, och bara genom den
befintliga apply-kedjan (router -> context -> patch -> apply -> targeted
render). Inga fria shell-kommandon, ingen filsystemåtkomst utanför sanktionerade
ytor, inga nätverksanrop.

## Tillåtna actions (status i `action-registry.json`)
- restyle — färg/typsnitt/tema (skriver brand/tone, aldrig fri CSS)
- copy_change — namn/tagline/om-oss/tjänstetexter (per-sajt Project Input)
- section_add — montera EN sanktionerad sektion/dossier
- layout_change — flytta/ordna sektioner (planerad)
- site_review — svara/granska read-only, ingen build

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
