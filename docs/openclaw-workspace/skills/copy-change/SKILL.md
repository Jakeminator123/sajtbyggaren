# SKILL: copy_change

## Mål
Ändra textinnehåll via följdprompt: företagsnamn, hero-rubrik/tagline, om-oss,
tjänstetexter. T.ex. "byt hero-rubriken till X" eller "gör herotexten X istället
för Y".

## Väg
router (copy_change) -> copyDirective {target, value} -> apply till per-sajt
Project Input -> ny version. Förståelsen är modell-driven (copyDirectiveModel);
deterministiska guards validerar (leak-guard, grounding, schema, honesty).

## Gränser
Bara company-name | tagline | about-text | services. Rå instruktion blir aldrig
kundcopy. Inget värde extraheras -> ärlig no-op.

## Status
supported (LLM-förståelse som primärlager, deterministik som validator).
