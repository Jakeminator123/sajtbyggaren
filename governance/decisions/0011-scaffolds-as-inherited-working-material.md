# ADR 0011 – Scaffolds är ärvt arbetsmaterial, inte hugget i sten

**Status:** accepted
**Datum:** 2026-05-07
**Beroenden:** ADR 0006 (scaffold-contract), naming-dictionary.v1.json

## Kontext

`scaffold-contract.v1.json:primaryScaffoldRegistry` listar 14 scaffold-IDs (`local-service-business`, `restaurant-hospitality`, etc.). Dessa kommer från `Jakeminator123/sajtmaskin` där segmenteringen var halvt slumpmässig och vissa scaffolds (`event-campaign`, `app-landing`, `consultant-expert`) överlappar varandra eller med varianter.

Operatör har uttryckligen flaggat att Sajtmaskins scaffolds inte ska "tas för hugget i sten" i Sajtbyggaren.

## Beslut

Scaffold-registret behandlas som ärvt arbetsmaterial med tre regler:

1. Att lägga till ny scaffold kräver ADR + naming-dictionary-uppdatering + selection-profile-fil i `packages/generation/orchestration/scaffolds/<id>/`.
2. Att ta bort scaffold kräver ADR + migration-anteckning om eventuella beroenden i dossier-contract eller scaffold-selection.
3. Att byta namn på scaffold kräver ADR + alias-period i `naming-dictionary.v1.json` (gammalt namn flaggas som `aliasesAllowed` med deprecation-datum) tills alla referenser är uppdaterade.

Registret revideras formellt när tre scaffolds har körbart innehåll i `packages/generation/orchestration/scaffolds/` och vi kan jämföra hur väl de täcker reella prompter.

## Konsekvens

- Inget i koden får hårdkoda hela listan av 14 scaffold-IDs - läs alltid från `scaffold-contract.v1.json:primaryScaffoldRegistry`.
- `governance_validate.py` ska varna men inte fail:a om scaffold-IDs nämns i kod utan att finnas i registret (för att tillåta WIP-scaffolds under utveckling).
- Dossier-contract ska kunna ange `compatibleScaffolds: "*"` istället för att räkna upp alla 14.
- Operatör äger revisionerna; agenten får föreslå men inte besluta.

## Alternativ vi övervägde

- **Lås registret nu**: avvisat, eftersom vi inte vet om alla 14 är meningsfulla.
- **Ta bort registret helt och låta LLM bestämma**: avvisat, eftersom det skulle återskapa Sajtmaskins kaos.
- **Krympa till 5 grupper baserat på reviewerns starter-modell**: möjligt senare via ADR, inte nu.

## Referenser

- `governance/policies/scaffold-contract.v1.json` (registryStatus-block)
- `referens/utlatanden/konversation-allmant-arkitektur.txt` (reviewer-input om grupperingar; borttaget i #191, finns i git-historiken)
- ADR 0006 (scaffold-kontraktets grundregler)
