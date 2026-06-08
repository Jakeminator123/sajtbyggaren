# SKILL: layout_change

## Mål
Flytta/ordna om sektioner via följdprompt, t.ex. "flytta team-sektionen överst"
eller "byt ordning på tjänster och om-oss".

## Väg (planerad)
router (layout_change) -> patch/plan mot sektion-ordning i Project Input/
blueprint -> apply -> targeted render -> ny version. Ingen fri CSS.

## Gränser
Endast sanktionerad omordning/placering av befintliga sektioner. Per-element-
finlir och fri layout ligger utanför MVP.

## Status
planned (efter section_add).
