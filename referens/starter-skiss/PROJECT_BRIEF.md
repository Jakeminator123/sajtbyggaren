# Sajtbyggaren Project Brief

Sajtbyggaren ska bli en bättre och mer styrbar version av `Jakeminator123/sajtmaskin` på GitHub, med `master` som referensbranch.

Syftet med ombygget är att återta kontrollen över arkitekturen. Den tidigare kodbasen upplevs som för utspridd, otydligt namngiven och svår att styra. Den nya versionen ska byggas med tydligare begrepp, bättre governance och en struktur där det är lätt att förstå vad varje del ansvarar för.

## Grundprinciper

- Projektet ska organiseras runt tydliga domänbegrepp för hemsidebygge, redigering, policyer, scheman och publicering.
- `backend.py` ska ligga i roten och fungera som en tydlig samlande startpunkt för backend-logik.
- Redigerbart innehåll ska i hög grad styras av scheman och policyer, inte av lös kod eller otydliga specialfall.
- Governance ska vara en förstaklassdel av projektet: vad som får ändras, av vem, hur ändringar valideras och hur publicering sker ska vara explicit.
- Namn ska hellre vara tydliga än korta. Undvik flera ord för samma sak om de inte betyder olika saker.
- Den gamla `sajtmaskin`-koden ska behandlas som referens och inspirationskälla, inte som något som kopieras in okontrollerat.

## Observationer från referensrepot

Referensrepot är en stor Next.js/TypeScript-applikation för hemsidebyggande med egen LLM-motor, builder-UI, preview/deploy-flöden, quality gate, repair-loop, scaffolds, dossiers, schemas och en omfattande dokumentationsstruktur.

Det finns mycket bra material att återanvända som idéer: repo-router, glossary, schema-dokumentation, quality-gate-tänk, dossier/capability-modell och tydliga agentregler. Samtidigt är just mängden lager, historik, legacy-termer och många parallella mappar ett tecken på varför den nya versionen bör börja mindre och mer principstyrt.

Den nya versionen ska därför inte börja med att återskapa `src/lib/gen/`, `preview-host/`, backoffice, evals och alla docs. Börja med den minsta styrbara kärnan: begrepp, schema, policy, backend-entrypoint och ett enkelt flöde från redigerbar input till validerad hemsidesstruktur.

## Tidig riktning

Bygg från en liten, begriplig kärna först:

1. Definiera centrala begrepp och ansvar.
2. Skapa scheman/policyer för det som ska vara redigerbart.
3. Låt backend läsa och validera mot dessa strukturer.
4. Lägg till UI, generatorer och publiceringsflöden först när kärnan är stabil.

