PROMPT - Init

"LLM SOM TAR ANVÄNDARENS PROMPT OCH BRODERAR UT DEN ELLER FÖRMINASKAR".

En användare uttrycker att de vill ha en tv-spelsbutik för personer som gillar 80-tal och retro, med fyrkantiga former, Billy's panpizza och Jolt Cola. Utifrån detta kan Deep Brief utveckla konceptet. Det kan antas att sidan har en maskulin ton och att ett `8-bit` typsnitt skulle passa bra. Användaren kan också vilja ha en medlemssida, enklare tv-spel, gammaldags 3D-animering och en highscore-lista för besökare eller de som köpt flest spel. 

"Deep Brief bör kunna utvidga och förkorta texter, och det kan vara bra att sätta en ungefärlig storlek på prompten
 i antal rader eller tecken. Det kan vara värt att överväga om allt detta ska dokumenteras i ett strikt
 policydokument eller om det ska gå direkt till `variants`. Jag föreslår att ha 10-15 olika typer av frågor,
 vilket kan ingå i en dynamisk prompt. Vi vill alltid ha svar på typ av `repo`, `scaffold`, `docin`,
 samt antal sidor eller `routes`. Det kan också vara bra att inkludera
 specifikationer för färger och andra antaganden, om de inte redan finns i `scaffold variants`."

Vi kommer då ha typ:
	- initsial prompt
	- expanderad/förminskad rpompt som broderats ut från LLMen som sköter deta
	- repo
	- scaffold
	- ev dessein(er)
	- variant
	- (möjligen någoi nform av spec som svarar på alla frågor utan avtaganden eller expleceita önskemål frn prompt

I stort sätt tänker jag att detta är den dynamiska delen

---

Den statiska delen är väl kanske just vilken stack som används som typ finns mestadels i package-filen.
(här vet jag itne helt säkert), men kanske finns här också explecita bygginstruktioner och guardrails.

---

TILLSAMMANS BORE DETTA BLI EN SYSTEMPROMPT FRÅN EN INIT:

Deep breef -> Väljer repo -> välkjer scaffold -> Variant -> (eventuella dosseiner) = DYNAMIC PROMPT + STATIC PROMPT



---------------------------------------------------------------------------------------------------------------------------

PROMPT - Follow up

Här tänker jag att vi kan titta på `site-machine`-reporten, eller så gör vi inte det, men vi måste separera vad som faktiskt sker i en follow-up.
 Ta följande exempel: Jag kan skriva i chatten, "vad är klockan?" eller
 "kan du lägga in en klocka?"
 Jag kan specificera, "kan du lägga in en klocka på första sidan under headern?"
 eller "jag vill lägga in en klocka men också en 3D-dinosaurie."
 Jag kan fråga, "föreslår du att jag ska sätta in en klocka?"
 eller "kan du gå till Aftonbladet eller www.aftonbladet.se
 och ta den klockan samt det typsnittet och sätta in på den tredje sidan med en egen inspiration?"
 Allt detta skiljer sig åt beroende på hur en fråga ställs, vilket gör att vi måste kategorisera.
 Jag hänvisar till `sajtmaskin` som löser detta någorlunda bra, även om vi behöver ha det mer strukturerat.
 En follow-up måste ha koll på kontexten, vilken version det är, alltså någon form av chatt-ID, versions-ID,
 projekt-ID eller liknande. Tidigare i `site-machine`-repot kallades det för delta brief.
 Jag trodde att man skickade med en summering av tidigare ändringar, och jag är osäker på om hela variant,
 dossier och allt som kommer i init-prompten ligger som grund för den att se över. Jag är osäker på detta.