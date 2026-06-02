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

Sajtbyggaren ska inte låsa sig vid en enda runtime för tidigt — preview körs
via `PreviewRuntime`-adaptrar som väljs med `VIEWSER_PREVIEW_MODE`.

Praktisk riktning (uppdaterad 2026-06-01, se
[ADR 0033](../governance/decisions/0033-vercel-sandbox-primary-preview.md)):

- `vercel-sandbox` är **primärt förstahandsval** för användarnära preview: en
  isolerad Vercel Sandbox kör den genererade sajten och returnerar en publik
  URL som fungerar i alla browsers (live-verifierat via spike #146).
- `local-next` (`LocalRuntime`) är snabb intern utveckling, felsökning och
  garanterad fallback om sandbox inte är tillgänglig.
- `static-export`, `FlyRuntime` eller annan produktionslik runtime är framtida
  fallback/verifieringsnivå när build, routes, miljövariabler, assets och
  deploybarhet måste testas mer realistiskt.
- `StackBlitzRuntime` är **pausad**: begränsad till Chromium (Safari/Firefox
  saknar `credentialless`-stöd) och behålls bara som icke-blockerande,
  icke-default alternativ.

Produktkoden ska fortsätta prata med `PreviewRuntime` som abstraktion. Att
`vercel-sandbox` är primärt val ändrar inte portabilitetsskyddet i ADR 0030:
generated output förblir vanlig Next.js, leverantörsberoenden stannar i
preview-runtime-lagret, en non-Vercel-fallback hålls inwirad, och Sajtbyggaren
äger projekt/versioner (`data/runs`) — sandbox kör bara en ephemeral kopia.

### Browser-begränsning för embedded WebContainer-preview

`StackBlitzRuntime` valdes bland annat för att skala kostnadseffektivt:
WebContainer-runtimen körs i slutkundens egen browser, vilket gör att
preview-kompute inte belastar Sajtbyggarens server. Det är därför
`FlyRuntime`/server-side container-park inte är default-vägen, även om
operatören har erfarenhet av Fly från sajtmaskin.

Trade-offen är att **embedded** WebContainer-projekt officiellt bara stöds i
Chromium-baserade browsers (Chrome, Edge, Brave, Vivaldi). Safari och
Firefox kan inte ladda embeddet eftersom det kräver iframe-attributet
`credentialless` som bara finns i Chromium. Det betyder att 25-35% av
svenska SMB-kunder kommer behöva en server-byggd fallback för att kunna
använda preview-fliken. Slutpublicerade kund-sajter är vanlig Next.js och
funkar i alla browsers — det här är **bara** ett konstrastat krav på
preview-fliken inne i Sajtbyggarens egen UI.

`PreviewRuntime`-abstraktionen ska därför fortsätta hålla dörren öppen för
en server-byggd fallback (kandidater i fallande ordning av oberoende från
externa hostar: lokal `next dev`-process som same-origin iframe, ephemeral
deploy till valfri hosting med URL i iframe, eller pre-built static export
embed). Vägen är nu vald: ADR 0033 gör `vercel-sandbox` till primär
server-byggd preview (publik URL i iframe, alla browsers), med `local-next`
som garanterad fallback. B125-registreringen i
[`docs/known-issues.md`](known-issues.md) täcks därmed av sandbox-vägen. Tekniska detaljer kring
WebContainer-fallet finns i
[`docs/integrations/webcontainers-notes.md`](integrations/webcontainers-notes.md).

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

### Operatörsbeslut 2026-06-02: auth + billing aktiverat (eget stack)

Operatören har uttryckligen sagt "annat": bygg auth + billing + credits +
Stripe som eget stack (scrypt-sessioner + SQLite-store + Stripe-prenumeration
som ger en månatlig kreditpott). Det landade i christopher-ui-lanen (PR #150).
Detta är alltså undantaget enligt vänta-listan ovan, inte ett brott mot den.

Hård gräns som gäller framåt: auth/credits får INTE läcka in i bygg-ingången
(`app/api/prompt`). Kärnflödet prompt → preview ska förbli friktionsfritt och
utloggade ska kunna bygga. Källlås-testet `test_build_pipeline_untouched_by_auth`
upprätthåller gränsen. Om/när byggen ska kreditmäteras är det ett separat
produktbeslut (utloggad demo vs tvingad inloggning, var krediten dras) — inte en
mekanisk fix i bygg-routen.

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
