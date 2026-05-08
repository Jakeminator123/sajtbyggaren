# `packages/generation/orchestration/dossiers/`

Den här mappen är ägar-pathen för alla **Dossier**-definitioner enligt
[`repo-boundaries.v1.json`](../../../../governance/policies/repo-boundaries.v1.json)
och [`naming-dictionary.v1.json`](../../../../governance/policies/naming-dictionary.v1.json).

## Dossier i en mening

En Dossier är en återanvändbar capability/legokloss som kan kopplas på vilken
sajt som helst om den är kompatibel. Default-kompatibel med alla Scaffolds.
En Dossier är inte ett konkret kundprojekt - det är `Project Input`, som bor
under `examples/<siteId>.project-input.json`.

## Klasser (ADR 0012)

Bara två klasser:

- **`soft`** - återanvändbar frontend/content capability utan secrets eller
  externa API:er. Exempel: `pacman-game`, `mouse-reactive-background`,
  `pricing-calculator`, `before-after-slider`.
- **`hard`** - kräver env, secrets, backend, auth, databas, betalning eller
  extern API. Får ha `mockMode`-konfiguration för designläge. Exempel:
  `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart`.

Tidigare versioner hade också `hybrid` som klass och en separat typ-axel.
Båda är borttagna - se ADR 0012 för detaljer och de termer som nu ligger i
`naming-dictionary.v1.json:globallyForbidden`.

## Mappstruktur

```text
packages/generation/orchestration/dossiers/
  soft/
    <dossierId>/
      dossier.json
      prompt.md
      code-contract.json
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

Varje `dossier.json` deklarerar `class` (soft eller hard).

## Status

En (1) soft Dossier är implementerad idag: [`soft/interactive-game-loop/`](soft/interactive-game-loop/)
(capability `interactive-game`, defaultForCapability=true). Den är instructions-
only (inga verbatim filer) och definierar state/loop/controls/collision/score/
restart-kontraktet för spelbara mini-spel.

Övriga 11 capability-slugs i [`governance/policies/capability-map.v1.json`](../../../../governance/policies/capability-map.v1.json)
har tomma `dossiers`-listor och är dokumenterade gap (`empty list = gap, not
feature`). De väntar på MIN_IDE-import i Sprint 3+. Ingen hard Dossier
(stripe-checkout, supabase-auth, clerk-auth, shopify-cart) är implementerad än.

Builder MVP läser primärt ett `Project Input` under
`examples/<siteId>.project-input.json` (t.ex. `painter-palma`) och patchar
startern (`site_plan["starterId"]`) med dess content. Det är inte en formell
Dossier-realisering — den första riktiga Dossier-mountingen ligger i Sprint 3
tillsammans med `codegenModel`.

## Kompatibilitet är default-allow

En Dossier är kompatibel med alla Scaffolds tills den explicit deklarerar
motsatsen via en `incompatibleScaffolds`-lista i `dossier.json`. Detta är
omvänt mot tidigare modell där Scaffolds opt-in:ade Dossiers via
`compatible-dossiers.json` (den blir framöver bara en hint, inte ett filter).

## Inte autoinjektion

En Dossier får användas av många Scaffolds, men injiceras aldrig automatiskt
i alla. Operator (eller Selector i framtida runda) avgör vilka Dossiers som
aktiveras per Project Input.
