# Produktkompass för Sajtbyggaren

Det här dokumentet är den korta målbild som varje agent ska ha i ryggen
innan den ändrar kod, tester, governance eller dokumentation. Det ersätter
inte `docs/current-focus.md`; det förklarar varför köplanen ser ut som den
gör.

## Nordstjärna

Sajtbyggaren ska bli ett seriöst AI-verktyg för småföretagare som vill få
en riktigt bra företagshemsida utan att förstå design, kod, hosting eller
modern webbutveckling.

Kärnflödet är:

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

Allt agentarbete ska testas mot frågan:

> Hjälper detta kärnflödet att bli stabilare, tydligare eller mer
> kvalitativt?

Om svaret är nej ska ändringen normalt parkeras, även om den är tekniskt
intressant.

`docs/current-focus.md` är fortfarande köplanen. Produktkompassen ersätter
inte valda B-ID:n eller blockerande följdsteg; den förklarar varför de ska
hjälpa kärnflödet. En enabling-uppgift som B49 är rätt när den gör nästa
småföretagarsajt mer korrekt, previewbar eller aktiverbar.

## Produktlöfte

Slutanvändaren ska kunna beskriva sitt företag i fri text och få en
trovärdig, mobilklar och redigerbar företagshemsida som systemet kan
förbättra genom följdprompter utan att tappa kontext eller kvalitet.

Produkten ska därför kombinera:

- förståelse av bransch, målgrupp, ton, erbjudande och lokal kontext
- sidstruktur med rätt sidor, sektioner, prioritering och kontaktvägar
- designkvalitet som känns modern, trovärdig och branschnära
- iteration där tidigare val, versioner och användarens riktning bevaras
- verifiering så att output fungerar, inte bara ser rimlig ut

## Förhållande till lovable och sajtmaskin

Lovable och andra breda AI-appbyggare är kvalitetsreferenser för enkelhet,
iteration, finish och deploy-känsla. De är inte arkitekturmallar.
Sajtbyggaren ska vara smalare och bättre på företagshemsidor, inte bli en
bred appbyggare.

Gamla sajtmaskin är referens och baslinje, inte kodbas att återinföra rakt
av. Det gamla projektets bredd är en varning: auth, credits, domäner,
integrationslager, media, för många starter-spår, deploy-spår och
agentfunktioner fanns samtidigt och gjorde helheten svårstyrd. Nya
Sajtbyggaren ska låna
produktidéer, men bara när de stärker kärnflödet.

## Governance-princip

Governance ska skydda riktningen, inte kväva bygget.

Det betyder:

- policy och ADR behövs när en ändring skapar ett nytt gemensamt begrepp,
  ändrar mappgränser, ändrar runtime-kontrakt eller påverkar flera lager
- dokumentation ska vara kort, användbar och kopplad till faktisk handling
- intern arkitekturstädning får inte prioriteras över huvudflödet om den
  inte minskar verklig risk eller blockerar nästa produktsteg

## Runtime och preview

Sajtbyggaren ska inte låsa sig vid en enda runtime för tidigt.

Praktisk riktning:

- `LocalRuntime` är snabb intern utveckling och felsökning.
- `StackBlitzRuntime` är första användarnära preview-yta. Eventuell
  editbarhet ska testas som produktupplevelse ovanpå previewn, inte som
  ansvar som flyttas in i runtime-lagret.
- `FlyRuntime` eller annan produktionslik runtime är högre verifieringsnivå
  när build, routes, miljövariabler, assets och deploybarhet måste testas mer
  realistiskt.

Produktkoden ska därför fortsätta prata med `PreviewRuntime` som abstraktion.
StackBlitz ska testas ordentligt, men arkitekturen ska hålla dörren öppen för
produktionslik deploy-check senare.

## Framtida sajtagent

Den gamla agentidén från sajtmaskin är strategiskt viktig, men ska inte
byggas stort innan kärnflödet är stabilt.

En framtida sajtagent ska kunna förstå:

- senaste promptar och följdpromptar
- aktuell `projectId`, version och run
- genererad filstruktur och relevanta filer
- tidigare val användaren gjort
- om användaren vill förstå, granska eller ändra sajten

Första versionen bör vara en kontextmedveten rådgivare i Viewser, inte en
agent som okontrollerat skriver över filer.

## Tidigt scope

Prioritera:

1. stabil prompt-input och brief/plan/build-kedja
2. follow-up-versionering som bevarar `projectId`, tidigare val och riktning
3. kontaktvägar och CTA:er som följer scaffold/starter
4. preview som är snabb, begriplig och stabil
5. run history och artefakter som gör versioner jämförbara
6. enkelt kvalitetsscorecard för några småföretagarbranscher

Vänta om inte operatören uttryckligen säger annat:

- auth
- billing och credits
- Stripe, Supabase, Shopify och andra externa integrationslager
- custom domains
- booking
- avancerad e-post
- avatar/media-funktioner
- marketplace eller för många starter-spår
- flera konkurrerande initieringsvägar

## Första kvalitetsbaseline

Nästa tydliga produktbevis är att kunna demonstrera fyra småföretagssajter
från fri prompt, följa upp med ändringar, se en ny version och bedöma
kvaliteten med ett enkelt scorecard.

Bra första testbranscher:

- elektriker i Malmö
- frisörsalong i Göteborg
- naprapatklinik i Stockholm
- liten e-handel som säljer keramik

Scorecardet bör börja enkelt: tydlighet, CTA, trovärdighet,
branschpassning, mobilkänsla, konkret copy, designbalans och konvertering.
