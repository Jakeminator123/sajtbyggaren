# `packages/generation/orchestration/dossiers/`

Den här mappen är ägar-pathen för alla **Dossier**-definitioner enligt
[`repo-boundaries.v1.json`](../../../../governance/policies/repo-boundaries.v1.json)
och [`naming-dictionary.v1.json`](../../../../governance/policies/naming-dictionary.v1.json).

## Två oberoende axlar

Varje Dossier har två klassningar:

1. Klass (tekniskt krav): `soft` / `hybrid` / `hard`. Avgör om Dossiern
   kräver env, backend, integration eller bara påverkar content/layout.
2. Typ (vad den levererar): `Site Dossier` / `Feature Dossier` /
   `Integration Dossier` / `Data Dossier`. Registrerad i naming-dictionary v7.

Mappstrukturen följer klass-axeln tills vidare, eftersom den styr
filuppsättning och env-kontrakt:

```text
packages/generation/orchestration/dossiers/
  soft/
    <dossierId>/
      dossier.json
      prompt.md
      code-contract.json
      examples.md
  hybrid/
    <dossierId>/
      dossier.json
      prompt.md
      code-contract.json
      env-contract.json
      examples.md
  hard/
    <dossierId>/
      dossier.json
      prompt.md
      code-contract.json
      env-contract.json
      integration-contract.json
      examples.md
      evals.json
  README.md  (this file)
```

Varje `dossier.json` deklarerar både `class` och `type` (en av de fyra
typerna ovan). Migration av mappstruktur till `site/feature/integration/data/`
är ett separat ADR-beslut.

## Status

Inga Dossiers är implementerade än. Builder MVP använder bara
`examples/painter-palma.site-dossier.json` som körbar Site Dossier-input,
inte en formell Dossier-definition under denna mapp.

## Inte autoinjektion

Reviewer-konversationen i
[`referens/scaffolds-dossiers/konversation.txt`](../../../../referens/scaffolds-dossiers/konversation.txt)
betonar:

> Dossierer är portabla. Dossier-realiseringar är scaffold-specifika.

En Dossier får alltså användas av många scaffolds, men injiceras aldrig
automatiskt i alla. `compatible-dossiers.json` per scaffold + Dossier
Selector + Policy Gate avgör om Dossiern aktiveras.
