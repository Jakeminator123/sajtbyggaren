# ADR 0007: Språkpolicy (kod engelska, operatör svenska, prompter alla språk)

- Status: accepterat
- Datum: 2026-05-07

## Kontext

Sajtbyggaren har tre språkdimensioner som tidigare blandades ihop:

1. **Kodspråket** - vad ska variabler, funktioner och klasser heta?
2. **Operatörsspråket** - vad ska agenten svara på, vad ska docs vara skrivna på?
3. **Slutanvändarspråket** - en svensk användare promptar på svenska, en engelsk på engelska, vad gör vi?

I `sajtmaskin` blandades svenska och engelska i identifierare (`omraden`, `tjanster`, `kontakt` jämte `services`, `home`, `contact`), vilket gjorde sökning, refaktorering och delning tråkig.

## Beslut

Tre regler kodifierade i [`governance/rules/code-in-english.md`](../rules/code-in-english.md):

1. **All kod är på engelska.** Identifierare, doc-strings, kod-kommentarer, JSON-fältnamn, filnamn, mappnamn, commit-meddelanden, loggrader och felmeddelanden i kod.
2. **Operatörens ytor är på svenska.** Cursor-regler, dokumentation, ADR:er, backoffice-UI och agentens svar. Detta är vårt arbetsspråk.
3. **Slutanvändarens språk är data, inte gissning.** `siteBrief.language` sätts deterministiskt från användarens prompt och används av codegen för att producera content. En version har ett språk; språkbyte är en ny version.

Kanoniska termer i [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json) är på engelska (`Site Brief`, `Scaffold`, `Dossier`, `Quality Gate`) men diskuteras på svenska runtomkring.

## Konsekvenser

- En ny variabel, fil eller mapp som heter något svenskt blockeras i review.
- Agenten svarar på svenska även när operatören skriver på engelska (regel `always-swedish.md`).
- `Site Brief` får ett `language`-fält tidigt i fas 1 (auto-detekterat eller explicit).
- Codegen-promptar måste innehålla språkinstruktion baserat på `siteBrief.language`.
- Tester och evals är på engelska men prompt-fixtures kan vara på vilket språk som helst.
