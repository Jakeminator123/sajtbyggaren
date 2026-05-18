---
description: Kod är på engelska. Operatörens dokumentation och agentsvar är på svenska. Slutanvändarens prompter får vara på vilket språk som helst.
alwaysApply: true
---

# Språk per yta

| Yta | Språk |
|-----|-------|
| Identifierare i kod (variabler, funktioner, klasser, typer, JSON-fältnamn, filnamn, mappnamn) | **Engelska** |
| Doc-strings, kod-kommentarer | **Engelska** |
| `governance/policies/*.json` fältnamn (`policyId`, `purpose`, `rules`...) | **Engelska** |
| `governance/policies/*.json` värdetext (definitioner, beskrivningar, rationale) | Engelska eller svenska, valt per policy för läsbarhet |
| `governance/rules/*.md` och `.cursor/rules/*.mdc` | **Svenska** (operatörens språk) |
| `docs/` (architecture, decisions, handbok) | **Svenska** |
| Commit-meddelanden | **Engelska** |
| Agentens svar till operatören | **Svenska** (se [`always-swedish.md`](always-swedish.md)) |
| Slutanvändarens prompter | **Auto-detekteras** via `siteBrief.language` |
| Genererad sajt-content | **Matchar `siteBrief.language`** om inte explicit override |
| Backoffice UI-strängar (`backoffice.py`) | **Svenska** (operatörens UI) |

## Hårda regler för kod

- Variabler, funktioner, klasser, typer, JSON-fältnamn, filnamn och mappnamn ska vara på engelska. Ingen `tjänster`, `bokning`, `företag`, `omraden` som identifierare.
- Doc-strings och kod-kommentarer på engelska.
- Felmeddelanden i kod på engelska. UI-presentation översätts via UI-lagret.
- Loggrader på engelska (lättare att grepa, dela, automatisera).

## Hårda regler för operatörsytor

- `governance/rules/`, `.cursor/rules/`, `docs/`, ADR:er och `backoffice.py`-UI är på svenska. Det är vårt arbetsspråk.
- Operatörens namn på saker som `Site Brief`, `Scaffold`, `Dossier` är engelska eftersom de är **kanoniska identifierare** i [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json), men vi pratar om dem på svenska runtomkring.

## Hårda regler för slutanvändarspråk

- Vi gissar inte språk på slutanvändarens prompt baserat på vart de kommer ifrån. Vi använder en deterministisk språkdetektor (eller så är det fält i Site Brief) och låser språket i `siteBrief.language`.
- Codegen får aldrig översätta innehåll utan att fältet `siteBrief.language` säger det explicit.
- Ett enskilt projekt har **ett** språk per version. Om användaren vill byta språk är det en ny version, inte en silent translation.

## Vad detta löser

- Engelsk kod blir delbar, sökbar och slipper teckenkompatibilitetsproblem.
- Svenska docs/regler/UI är operatörsvänligt.
- Slutanvändarens språk är data, inte gissning.
