---
description: Svara alltid på svenska och använd alltid riktiga svenska tecken, aldrig escape-sekvenser eller ASCII-transliteration
alwaysApply: true
---

# Språk och teckenformat

## Språk

- Svara alltid på svenska, även när användaren skriver på engelska eller blandar språk.
- Etablerade tekniska termer (API, schema, scaffold, dossier, policy, runtime, codegen, build, lint, typecheck) får vara på engelska.
- Egennamn och kommando-utdata översätts inte.
- Narrera inte intern felsökning på engelska. Skriv inte självrättande
  mellansteg som "Found a bug" eller "Let me fix the parser" i chatten;
  gör ändringen och sammanfatta kort på svenska.

## Teckenformat (gäller all text och alla verktygsanrop)

- Använd alltid riktiga svenska tecken: `å`, `ä`, `ö`, `Å`, `Ä`, `Ö`. Filer ska sparas i UTF-8.
- Använd ALDRIG Unicode-escape-sekvenser i text som visas för användaren eller sparas i filer:
  - Fel: `f\u00f6r`, `\u00e4r`, `fr\u00e5n`
  - Rätt: `för`, `är`, `från`
- Använd ALDRIG ASCII-transliteration som ersättning för svenska tecken:
  - Fel: `ar`, `for`, `fran`, `nar`, `manskliga`, `kalla`
  - Rätt: `är`, `för`, `från`, `när`, `mänskliga`, `källa`
- Detta gäller alla format: markdown, JSON-strängar, kod-kommentarer, plan-filer, commit-meddelanden, terminalutdata, parametrar i verktygsanrop.
- Om ett verktyg verkar vilja serialisera tecken som escape-sekvenser: skriv ändå riktiga tecken; verktyget hanterar UTF-8.
- Avkoda inte svensk text som redan är Unicode/UTF-8 med `unicode_escape`
  eller liknande escape-decoding. Behåll riktiga tecken i operator- och
  kundsynlig text. ASCII-folding får bara användas där fältet uttryckligen
  är ett tekniskt id, till exempel slug, filnamn eller route-segment.

## Format-konsekvens

- Inom ett dokument får inte två stavningar av samma ord användas (`för` och `for` blandat).
- Inom hela projektet ska samma terminologi gälla; se [`governance/policies/naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json) som sanningskälla.
