# GAP-followup-prompt-content-passthrough

```yaml
id: GAP-followup-prompt-content-passthrough
type: Gap/Builder
owner: jakob
title: Follow-up prompt content passthrough
status: queued
source: operator verification 2026-05-27
```

## Status 2026-05-31

Backenddelen av lösning B är implementerad: follow-up-builds skriver
`appliedVisibleEffect` och `appliedVisibleEffectReason` i
`build-result.json`, och emitterar trace-eventet `followup.no_op_detected`
när ingen synlig effekt detekteras. FloatingChat-presentationen väntar
Christopher. Lösning A (`copyDirectives[]`) är fortfarande separat och
ADR 0034 står kvar som `proposed`.

## Reproduktion

Operatören verifierade 2026-05-27 att följdpromptar i dag inte når en
synlig codegen-effekt när de uttrycks som fri text i stället för som ett
redan stödat strukturerat fält.

1. Case 1, version v2 -> v3:
   - Följdprompt: "Allt sla vara mycket ljusare".
   - Observerat: `site-brief.json` v3 visar fortfarande
     `tone=["noir", "editorial", "mörk", "utstuderad"]`.
   - Observerat: renderern gör inte färgerna ljusare.
2. Case 2, version v3 -> v4:
   - Följdprompt: "Kan du ändra den där texten vid hero och lite överallt
     till att inkludera 'TEST-JAKOB' i typ alla meninar?"
   - Observerat: `app/page.tsx` i
     `.generated/foretag-som-arbetar-med-f77c5a/` saknar `TEST-JAKOB`.
   - Observerat: bara strängen "en sajt om möss" finns en gång.

## Pipeline-trace

### 1. Följdprompten sparas, men bara som metadata

`scripts/prompt_to_project_input.py:3074-3164` är follow-up-entrypointen.
Den läser föregående Project Input, räknar upp versionen och skickar
senaste prompten vidare till `generate(...)`. Samtidigt sparas råtexten
som `meta.followUpPrompt` (`scripts/prompt_to_project_input.py:3121-3128`).

Buildern bevarar också råtexten i run-artefakter:

- `scripts/build_site.py:3413-3432` skriver `input.json` med
  `rawPrompt`, `originalPrompt`, `followUpPrompt` och `previousVersion`.
- `scripts/build_site.py:3656-3663` kopierar prompt-sammanfattningen till
  `build-result.json`.

Detta är observability, inte en renderings- eller codegen-ingång.

### 2. Prompt helper gör en strukturerad kandidat och tappar fri copy

`scripts/prompt_to_project_input.py:2890-2939` kör briefModel på senaste
prompten, serialiserar ett Site Brief och mappar det till en ny
Project Input-kandidat. Vid follow-up slås kandidaten sedan ihop med
föregående Project Input via `merge_followup_project_input(...)`.

Den deterministiska mappningen är avsiktligt strukturerad:

- `scripts/prompt_to_project_input.py:1566-1680` läser `businessTypeGuess`,
  `companyName`, `locationHint`, `servicesMentioned`, `contactPhone`,
  `contactEmail`, `contactAddress`, `tone`, `conversionGoals` och
  `requestedCapabilities`.
- Samma block sätter `_ = original_prompt` på
  `scripts/prompt_to_project_input.py:1603-1608`, vilket explicit hindrar
  rå prompt från att bli kundcopy.
- `scripts/prompt_to_project_input.py:2597-2666` bevarar tidigare
  `siteId`, `scaffoldId`, `variantId`, `language`, `location`, `contact`
  och `selectedDossiers`, mergar bara services, conversion goals och
  requested capabilities additivt, och anropar en smal semantisk patch.

Den semantiska patchen har bara ett litet känt intent-utrymme:

- `scripts/prompt_to_project_input.py:420-426` listar
  `tone-shift`, `story-emphasize`, `tagline-update`,
  `positioning-shift`, `no-semantic-change` och `clarify`.
- `scripts/prompt_to_project_input.py:2042-2075` klassificerar okända
  följdprompter konservativt som `no-semantic-change`.
- `scripts/prompt_to_project_input.py:532-592` saknar ord som
  "ljusare" i tone-descriptor och tone-phrase-listorna.
- `scripts/prompt_to_project_input.py:599-622` saknar också en
  `ljusare -> ljus`-mappning.
- `scripts/prompt_to_project_input.py:2398-2434` kan bara skriva om
  `tone` när intent redan är `tone-shift`, och hämtar då värden ur den
  begränsade keyword-mappningen eller kandidatens strukturerade tone.

Case 1 faller därför igenom: "ljusare" matchar inte tone-tabellen och
ingen färg-/palettinstruktion får ett fält.

Case 2 faller också igenom: "texten" räknas som content-scope, men
systemet har inget fält för "lägg in exakt token i hero och övrig copy".
Ordet "hero" ensamt matchar inte de smala tagline-nycklarna
`hero-text`, `hero text` eller `herotext`
(`scripts/prompt_to_project_input.py:459-469`), och `TEST-JAKOB`
har inget strukturerat mål.

### 3. briefModel kan inte bära fria copy-direktiv

`packages/generation/brief/extract.py:92-185` definierar Site Brief-
schemat. Det finns fält för språk, business type, company name, target
audience, page count, tone, requested capabilities, location, kontakt,
conversion goals, services, content depth, raw prompt och notes for
planner. Det finns inget fält för fria copy-direktiv, exakta texttokens
eller "ändra hero och lite överallt".

`packages/generation/brief/extract.py:173-185` instruerar dessutom
briefModel att extrahera strukturerade fält konservativt och bara låta
`services_mentioned` vara naturligt språk för renderade labels.
`packages/generation/brief/extract.py:209-226` använder Pydantic-
typen `SiteBrief` som structured output, så outputen kan inte bära ett
fält som schemat saknar. `site_brief_to_artifact(...)` serialiserar
samma begränsade fält på `packages/generation/brief/extract.py:281-318`.

### 4. build_site bygger om Site Brief från Project Input

När buildern kör från Project Input gör fas 1 inte en fri omtolkning av
rå följdprompt. `scripts/build_site.py:3031-3087` bygger en mock Site
Brief från dossiern och projicerar bara strukturerade Project Input-fält:
`language`, `businessTypeGuess`, `tone`, `requestedCapabilities`,
`conversionGoals` och `servicesMentioned`.

Om `OPENAI_API_KEY` finns anropas briefModel, men prompten som skickas är
inte rå följdprompt. `scripts/build_site.py:3165-3203` anropar
`project_input_to_brief_prompt(dossier)`, och den prompten restatar
befintlig Project Input-data (`scripts/build_site.py:3106-3143`).

### 5. planning hoppar över LLM på pinnad Project Input

Buildern pinnar scaffold och variant från Project Input:
`scripts/build_site.py:3331-3390` skapar `pinned = {"scaffoldId": ...,
"variantId": ...}` och skickar det till `produce_site_plan(...)`.

I planeringspaketet är detta en explicit skip-väg:

- `packages/generation/planning/plan.py:1294-1325` dokumenterar att
  `pinned` betyder att planningModel inte kallas och att
  `planSource = "pinned"`.
- `packages/generation/planning/plan.py:1346-1349` implementerar skippen:
  `_resolve_pinned_choice(...)`, `plan_source = "pinned"`,
  `model_used = "mock"`.
- `packages/generation/planning/plan.py:1252-1286` bygger Generation
  Package med referenser till `site-brief.json` och `site-plan.json` samt
  `scaffoldId`, `variantId`, `starterId`, `language`, `engineMode` och
  eventuellt `projectId`; ingen fri följdprompt eller copy-instruktion
  finns som förstaklassfält.

Det betyder att även en tydlig rå följdprompt som finns i meta inte får en
ny planeringschans när Project Input redan pinnar variant.

### 6. renderern läser bara dossierfält, variant och smala directives

Renderingen har inga fria följdprompt-fält att läsa:

- `packages/generation/build/renderers.py:550-669` bygger hero från
  `company`, `location`, `contact`, USP-lista, hero asset, CTA och
  `variant_id`.
- `packages/generation/build/renderers.py:1005-1064` bygger
  services-summary från `dossier["services"]`, branch-copy och
  listing-route.
- `packages/generation/build/renderers.py:1544-1574` bygger about-sidan
  från `company`, `location`, `scaffoldId` och gallery.
- `packages/generation/build/renderers.py:2158-2195` väljer hero-layout
  från `directives.layoutHint`, variant eller `tone.primary`.
- `packages/generation/build/renderers.py:2102-2133` har en framtida USP-
  hook via `uniqueSellingPoints` eller `directives.uniqueSellingPoints`,
  men inget fält för fri copy-edit eller globala texttokens.

Renderern kan alltså bara reagera om följdprompten redan har blivit
Project Input-data som dessa helpers läser.

### 7. codegen-manifestet kan inte ändra filer eller copy

`packages/generation/codegen/codegen.py:76-125` bygger en deterministisk
fillista från `routes_written` och `dossier_components`, plus layout,
package och globals. Den listan innehåller inga copy-patchar.

Även real codegenModel är smalt:

- `packages/generation/codegen/models.py:76-109` säger att
  `CodegenLLMResponse` bara får innehålla `rationale` och `riskNotes`,
  inte filinnehåll.
- `packages/generation/codegen/codegen.py:209-248` summerar bara starter,
  scaffold, variant, business type, tone, conversion goals, services,
  routes, dossier components och dossier ids.
- `packages/generation/codegen/codegen.py:296-312` skapar manifestet innan
  eventuell LLM-call och håller filer deterministiska i alla paths.

Om fria följdprompt-direktiv ändå skulle råka finnas i en artefakt finns
det i dag ingen codegen-yta som kan applicera dem på `.generated/`.

## Var prompten tappas

Gapet är verkligt, men tappet är fördelat:

1. Ja: briefModel och Site Brief saknar fält för fri copy-edit. Det
   strukturerade schemat kan inte bära "inkludera TEST-JAKOB i hero och
   lite överallt".
2. Ja: pinned Site Plan gör att planningModel inte får en chans att tolka
   följdprompten efter merge. Det är korrekt för scaffold/variant-pin, men
   blockerar planeringsbaserad copy-intention.
3. Ja: renderern har inga fält att läsa för godtyckliga copy-direktiv eller
   exakta token-krav. Den läser dossierns strukturerade kunddata,
   variant-defaults och smala directives.
4. Ja: codegen ignorerar fria direktiv även om de skulle finnas, eftersom
   manifestet är deterministiskt och real codegenModel bara får skriva
   metadata.

Primär rotorsak för de två observerade fallen är därför: följdprompten
bevaras som metadata men översätts inte till ett strukturerat,
renderer-/codegen-konsumerat fält.

## Lösningsalternativ

### A. Strikt: nytt brief-fält `copyDirectives[]`

Lägg till ett explicit strukturerat fält, exempelvis `copyDirectives[]`,
i Site Brief och Project Input. Varje direktiv bör vara maskinellt
testbart: target (`hero`, `all-copy`, `services`, `about`), operation
(`include-token`, `rewrite-tone`, `replace-text`) och payload.

Fördelar:

- Bevarar governance-disciplin och gör följdprompten spårbar.
- Går att validera i schema och regressionstesta utan att rå prompt
  läcker till kundcopy.
- Passar kärnflödet eftersom användaren får synlig versionseffekt.

Nackdelar:

- Kräver schema-, brief-, merge-, renderer- och codegen-kontrakt.
- Behöver hårda stoppar för farliga eller otydliga copy-direktiv.
- Kräver beslut om hur breda mål som "lite överallt" får vara.

### B. Lös: ärlig FloatingChat-feedback

Om följdprompten klassas som `no-semantic-change` eller saknar stödat
fält, visa ett ärligt svar i FloatingChat, till exempel: "Jag kunde inte
fånga någon synlig ändring. Testa att ange exakt rubrik, text eller
sektion."

Fördelar:

- Snabbast att göra ärlig för användaren.
- Minskar förtroendeskada från tysta no-ops.
- Kräver inte att renderern börjar tolka fri text.

Nackdelar:

- Löser inte kärnlöftet "följdprompt -> ny version" fullt ut.
- Riskerar att kännas som en chatbot som ursäktar sig i stället för att
  ändra sajten.
- Fångar inte fall där systemet tror att något ändrades men effekten inte
  blir synlig.

### C. Kraftigast: real `copyEditModel` ovanpå `.generated/`

Låt en separat modell läsa aktuell `.generated/`-kod och applicera en
begränsad copy-edit-patch efter ordinarie build, följt av Quality Gate och
Repair Pipeline.

Fördelar:

- Kan hantera fri text nära användarens mentala modell.
- Bra för "ändra texten vid hero och lite överallt" där strukturerad
  intentmodell annars blir stor.
- Kan ge snabb synlig effekt utan att först modellera varje copy-yta.

Nackdelar:

- Störst risk: patchar runtime-kod efter deterministisk builder.
- Kräver hård sandbox, diff-granskning, rollback och testbar
  verifiering.
- Kan krocka med Sprint 3B-principen att codegenModel inte emitterar
  filinnehåll ännu.

## Rekommendation

Utifrån `docs/product-operating-context.md` är kärnflödets förtroende
viktigare än teknisk elegans. Användaren måste kunna se att
följdprompten gav en ny version, eller få ett ärligt besked när systemet
inte kunde göra en synlig ändring.

Rekommenderad ordning:

1. Implementera alternativ A som grund: ett strikt `copyDirectives[]`-
   kontrakt som börjar smalt med `include-token` och `rewrite-section`
   för hero, services och about.
2. Lägg alternativ B som säkerhetsnät samtidigt: om inget synligt direktiv
   fångas ska FloatingChat säga det i stället för att låta versionen se
   lyckad ut.
3. Parkera alternativ C tills Quality Gate och Repair Pipeline har ett
   godkänt kontrakt för modellskrivna filpatchar.

## Utanför scope

- B125 preview-fallback.
- Sprint 3B codegenModel och bredare LLM-baserad file-emission.
- Full Project DNA V2-lagring.
- Variant-promotion, scaffold selection eller ny starter.
- UI-redesign av Viewser utöver eventuell ärlig feedback-yta.

## Stoppvillkor för implementation

Stoppa implementationen om något av följande upptäcks:

- Rå följdprompt kan redan påverka renderern via en existerande,
  verifierad väg som denna audit missade.
- Nytt fält kräver policy- eller schemaändring som inte kan valideras med
  befintliga governance-guards.
- En copy-patch skulle behöva skriva direkt i `.generated/` utan Quality
  Gate och rollback.
- Direktivet är otydligt nog att det riskerar rå prompt-läckage eller
  felaktig kundcopy.

## Acceptanskriterier för faktisk implementation

- Följdprompten "inkludera 'TEST-JAKOB' i hero" producerar en ny version
  där `TEST-JAKOB` finns i renderad hero-copy och i `app/page.tsx`.
- Följdprompten "gör allt mycket ljusare" producerar antingen en mätbar
  token-/style-ändring i relevant Project Input/renderer-kontrakt eller
  ett ärligt FloatingChat-svar om att ingen synlig ändring kunde fångas.
- Site Brief, Project Input, Site Plan, Generation Package och
  build-result redovisar var direktivet tolkades och om det applicerades.
- Rå följdprompt renderas aldrig okontrollerat som kundcopy.
- Pinned scaffold/variant fortsätter vara auktoritativa, men copy-
  direktiv får passera bredvid den pinnen.
- Regressionstester täcker både lyckad copy-passthrough och no-op-
  feedback.
- Governance-guards, term-coverage och relevanta pytest-tester är gröna.
