---
description: Färre arkitekturtermer. Inga nya begrepp utan ADR och naming-dictionary-bump. Operatorflödet är låst i åtta steg.
alwaysApply: true
---

# Vocabulary discipline

Efter ADR 0012 är operator-vokabulären låst. Det här är de enda begreppen vi
använder för att beskriva flödet, och vi lägger inte till nya utan en ny ADR.

## Det enda flödet

```
Init Prompt
  ↓
Project Input (Deep Brief)
  ↓
Starter
  ↓
Scaffold
  ↓
Variant
  ↓
Dossier (soft eller hard)
  ↓
Generation Package
  ↓
Build
```

## Hård regel

- Inga nya arkitekturtermer i `governance/policies/naming-dictionary.v1.json`
  utan en ADR som motiverar varför ett befintligt begrepp inte räcker.
- Inga nya `*-dossier`, `*-input`, `*-project`, `*-brief`, `*-package`-suffix
  på filnamnsmönster utan samma ADR-krav.
- UI-komponentnamn (`ChatPanel`, `RunHistory`, `TokenMeter`, `ProjectInputPicker`)
  räknas som lokala implementationsidentifierare och hör inte hemma i
  naming-dictionary om de bara bor i en enda app.
- Inga interna mellannamn för redan registrerade begrepp. Ett namn per begrepp.

## Vad agenten ska göra när den vill införa ett nytt begrepp

1. Stoppa.
2. Föreslå en ADR-text under `governance/decisions/00XX-<slug>.md`.
3. Vänta på godkännande från operatören.
4. Bumpa `naming-dictionary.v1.json:version` i samma PR som ADR.
5. Implementera först därefter.

## Vad agenten ska göra när det redan finns två namn för samma sak

1. Stoppa.
2. Vänd det till en cleanup-PR (samma karaktär som ADR 0012). Välj canonical
   namnet, förbjud det andra via `globallyForbidden`, döp om filnamn på disk.
3. Driv inte funktionsarbete på en bas där samma sak heter två saker.

## Operator-ord vs kod-ord

| Operator får säga | Kod/policies använder |
|---|---|
| `repo` (när hen menar starter-bas) | `Starter` |
| `sajt` / `site` | `Project Input` när det är operator-data; `Build Result` när det är genererad output |
| `legokloss` | `Dossier` |
| `mall` | `Scaffold` (inte `Template`) |
| `tema` / `look` | `Variant` |

## Förbjudet

- Att kalla ett konkret kundprojekt (t.ex. `painter-palma`) för Dossier i kod,
  UI eller docs. Se `dossier-vs-project-input.md`.
- Att lägga till nya Dossier-typer (t.ex. `Site Dossier`, `Feature Dossier`,
  `Integration Dossier`, `Data Dossier`, `Hybrid Dossier`). De är medvetet
  borttagna i ADR 0012.
- Att driva en cleanup-PR och en feature-PR samtidigt. En sak åt gången.
