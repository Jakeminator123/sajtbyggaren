---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

> **Arkivnot (lane A, 2026-06):** Historisk import-readiness — behållen som
> referens (ej sanningskälla). Nuläge: `docs/current-focus.md`. Se `docs/archive/README.md`.

# Sajtmaskin dossier-import readiness

**Scope:** docs-only inventering av det material som operatören parkerat i
`MIN_IDE/dossier-inspection/` (extraherat från en zip med äldre
dossier-paket från Sajtmaskin). Dokumentet fastställer *vad* som ligger
där, *hur* det förhåller sig till nuvarande dossier-kontrakt, och en
föreslagen pipeline för senare import. Det landar **ingen schemaändring,
ingen kodändring och ingen capability-map-mutation** - bara
läs-och-bestäm-läge så nästa agent inte tankar in 13 (eller 100) gamla
dossiers rakt in i canonical runtime.

## 1. Inventering

> **Verifierbarhets-disclaimer:** `MIN_IDE/` är operator-lokal och
> gitignored - originalmaterialet (manifest.json + instructions.md +
> components/*.tsx per paket) finns inte i GitHub-repot och kan inte
> verifieras från en standard-clone ensam. För att denna inventerings-
> tabell ändå ska vara reproducerbart granskbar är en frusen snapshot
> av slugs + class + capability + status committad som
> `docs/dossiers/sajtmaskin-inventory.snapshot.json` (snapshotDate
> 2026-05-25). Tabellen nedan är härledd från den snapshoten. Om zippen
> uppdateras med nya eller ändrade paket bumpas snapshoten i en
> separat PR; gamla snapshots blir historisk record.

Materialet innehåller 13 dossier-paket (5 soft + 8 hard):

| Dossier | Klass | Capability | Status mot nytt repo |
|---|---|---|---|
| cmdk-command-palette | soft | command-search | candidate (capability-map-gap) |
| embla-carousel | soft | carousel | candidate (capability-map-gap) |
| faq-accordion | soft | faq-section | superseded (finns redan i `soft/faq-accordion/`) |
| interactive-game-loop | soft | interactive-game | superseded (finns redan i `soft/interactive-game-loop/`) |
| marquee-scroller | soft | marquee | candidate (capability-map-gap) |
| clerk-auth | hard | auth | candidate (capability-map-gap) |
| mailchimp-newsletter | hard | newsletter-subscribe | candidate (capability-map-gap) |
| openai-chat | hard | ai-chat | candidate (capability-map-gap) |
| plausible-analytics | hard | analytics | candidate (capability-map-gap) |
| resend-contact-form | hard | contact-form | candidate (mailto-fallback finns idag) |
| sentry-error-tracking | hard | error-tracking | candidate (capability-map-gap) |
| stripe-checkout | hard | payments | candidate (capability-map-gap) |
| vercel-analytics | hard | analytics | candidate (alternativ till plausible) |

Nio kandidater (3 soft + 6 hard) träffar direkt något av de capability-slugs
som README under `packages/generation/orchestration/dossiers/` listar som
explicit gap ("empty list = gap, not feature").

## 2. Slutsats: råmaterial, inte canonical

Gamla Sajtmaskin-paket är **kandidater för inspiration och framtida
import**, inte ett canonical artefakt-flöde. De passar inte rakt in i
nuvarande `governance/schemas/dossier.schema.json` av tre skäl:

1. **Manifestets `envVars`/`files`/`exposes` är platta strängar idag.**
   Gamla formatet hade nästlade objekt med `purpose`/`enforcement`/`role`/
   `injectionMode`. Det är information Quality Gate och operator-UI:t
   behöver för att svara på "vad händer om secret saknas?" och "får den
   filen paraphraseras eller måste den vara verbatim?" - särskilt för
   hard-dossiers.
2. **Inget `sourceRepoUrl` eller `mockMode`-fält i nya schema.** Båda är
   värdefulla för hard-import (provenance + design-läge), men kräver
   schema v2 + en uppdaterad `dossier-contract.v1`.
3. **Nuvarande elva soft-dossiers är `files: []` ("instructions-only").**
   Gamla materialet har `components/*.tsx`-filer även för soft, vilket
   är ett *annat* aktiveringskontrakt (codegen mountar fil) än
   instructions-only (codegen genererar fil från prompt + instructions).

Prosa-rikedom är inte problemet: nuvarande `instructions.md`-filer ligger
på 4.5-7.9 KB jämfört med 2.3-7.3 KB i det gamla materialet. Den
"stökigheten" som inspirationen söker finns redan i prosa-lagret - det
är manifest-ytan som är plattare än vad ett hard-import behöver.

## 3. Föreslagen import-pipeline

```
candidate → reviewed → verified → enabled
```

| Steg | Var | Vad krävs |
|---|---|---|
| candidate | `MIN_IDE/dossier-inspection/` | Inget - bara ligga där, läsbar för operatör och agent via shell. |
| reviewed | docs-only PR med per-dossier-bedömning | Schema-gap-analys, dependency-audit, risk-klass, capability-mappning. |
| verified | feature-branch som faktiskt mountar dossiern | Smoke-build mot 1 starter, Quality Gate grön, regressionstest tillagt. |
| enabled | PR som sätter `enabled: true` + uppdaterar `capability-map.v1.json` | Operator-review-protokoll för hard, eval-svit-täckning för soft. |

Ingen dossier får hoppa direkt från candidate till enabled.

## 4. Soft vs hard: olika aktiverings-trösklar

Per `governance/policies/dossier-contract.v1.json:activationFieldRequirements`:

- **soft** kan aktiveras via semantic match från Site Brief alene. Lägre
  tröskel eftersom de inte rör secrets, externa API:er eller env-vars.
  Första naturliga import-kandidater (capability-map-gap-coverage):
  marquee-scroller, embla-carousel, cmdk-command-palette. Kräver troligen
  schema v2 *eller* en explicit instructions-only-adaptation som strippar
  `files`/`components` från originalet.
- **hard** kräver explicit eller stark semantisk signal **plus**
  operator-review. Får aldrig "råka hamna" i en vanlig småföretagar-build.
  Första naturliga import-kandidaten är troligen resend-contact-form
  (stänger contact-form-gapet på riktigt, redan nämnd som "planned import"
  i nuvarande dossiers-README). Kräver schema v2 + `mockMode`-fält +
  env-fallback-test.

## 5. Vad denna doc INTE beslutar

- Inget om vilka kandidater som faktiskt importeras (eller när).
- Inget om schema v2-tidsplan - kräver separat ADR när första hard-import
  motiverar det.
- Inget om `capability-map.v1.json`-redigering (det är enabled-steget).
- Inget om hur `_RUNTIME_SCAFFOLD_HINTS`-deferren i
  `packages/generation/discovery/resolve.py` ska lösas.

Pipeline + schema v2-ADR är pre-requisite för all riktig import-aktivering.
Innan de finns på plats är materialet i `MIN_IDE/dossier-inspection/`
referensmaterial, inget annat.

## Referenser

- `docs/dossiers/sajtmaskin-inventory.snapshot.json` - frusen snapshot av
  inventeringen som gör tabellen i avsnitt 1 verifierbar utan tillgång
  till operator-lokal `MIN_IDE/`.
- `governance/decisions/0012-vocabulary-compression.md` - ADR som
  komprimerade dossier-klasserna till soft/hard.
- `governance/policies/dossier-contract.v1.json` - aktuella kontraktet.
- `governance/schemas/dossier.schema.json` - manifest-schemat som
  hard-import ska tvingas passa in i.
- `governance/rules/dossier-format-discipline.md` - låser
  `manifest.json` + `instructions.md` + `components/`.
- `governance/rules/dossier-vs-project-input.md` - distinktionen Dossier
  vs Project Input.
- `packages/generation/orchestration/dossiers/README.md` - nuvarande
  status över 11 implementerade soft-dossiers + gap-listan.
