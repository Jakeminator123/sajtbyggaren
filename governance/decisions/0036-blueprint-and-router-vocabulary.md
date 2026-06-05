# ADR 0036 — Blueprint- och router-vokabulär som canonical

**Status:** Accepted
**Datum:** 2026-06-03
**Beroenden:** ADR 0006 (term-discipline), ADR 0012 (vocabulary compression),
ADR 0013 (schema-lock innan Sprint 2B). Referens:
[`docs/heavy-llm-flow/01-artefakt-kontrakt-blueprint.md`](../../docs/heavy-llm-flow/01-artefakt-kontrakt-blueprint.md)
+ `kor-1a`. Relaterade PR: #157 (KÖR-1a blueprint-schema), #159 (deterministisk
router, KÖR-6a), #160 (allowlist av heavy-llm-flow-doctermer).

## Kontext

KÖR-1a (PR #157) lägger valfria blueprint-fält på de tre befintliga
artefakterna (Site Brief / Site Plan / Generation Package). Fälten blir
riktiga schema-kontrakt: efterföljande skivor (kor-1b/1c brief+planning, kor-2
renderer, kor-3b visual-direction, kor-4 verifier, kor-7 patch-planer) läser
och skriver dem via samma adresseringsnyckel `<routeId>.<sectionId>`.

Per `.cursor/BUGBOT.md` och ADR 0006 måste nya canonical fältnamn antingen
registreras i `naming-dictionary.v1.json` med en åtföljande ADR, eller
allowlistas i `COMMON_WORDS`. Fältgrupperna är operatörssynlig vokabulär (de
syns i artefakter, Backoffice och docs), inte bara Python-implementation-
symboler, så de hör hemma i naming-dictionary med en ADR. KÖR-1a registrerade
dem redan i naming-dictionary v23; denna ADR är den motivering som saknades.

Samtidigt landar KÖR-6a (PR #159) en deterministisk router vars beslutstyper
är samma kategori av canonical vokabulär. De förbokas i denna ADR så
blueprint-bron och router-bron delar en beslutspunkt i stället för att
canonicalisera var för sig.

## Beslut

### 1. Blueprint-fältgrupperna är canonical (registreras nu)

Åtta fältgrupper är canonical fältnamn i `naming-dictionary.v1.json` (v23,
levereras i PR #157):

| Fältgrupp | Artefakt |
| --- | --- |
| `businessFacts`, `positioning`, `contentStrategy`, `conversion` | Site Brief |
| `sectionPlan` | Site Plan |
| `contentBlocks`, `visualDirection`, `qualityRisks` | Generation Package |

Endast top-level fältgrupperna är canonical. Nästlade leaf-properties
(`positioning.oneLiner`, `visualDirection.heroStyle`, ...) är fält i schemat
men registreras **inte** som egna canonical termer.

### 2. Router-beslutsvokabulären registreras när #159 landar (samma ADR)

Router-beslutstyperna `messageKind`, `editKind`, `buildRequirement`,
`contextLevel` samt själva router-beslutsobjektet (router decision) registreras
som canonical i samma naming-dictionary-spår när KÖR-6a (PR #159) mergas. De
exakta canonical-symbolnamnen, inklusive den sammansatta router-beslutstypen,
ägs och registreras av #159. Kontraktet bor i ett router-decision-schema som
#159 levererar — inte i blueprint-artefakterna. Denna ADR förbokar bara
vokabulären.

### 3. Ingen ny artefaktfil

"Blueprint" är ett **arbets-/samlingsnamn** för de utökade fälten — inte en
sparad canonical artefakt. Det skapas **ingen** `site-blueprint.json` och ingen
ny canonical typ. Kontraktet bor i de tre befintliga artefakterna
(`site-brief`, `site-plan`, `generation-package`) plus router-decision-schemat.
Detta följer 01-artefakt-kontrakt-blueprint: vi inför inte en ny artefakt
"Site Blueprint" utan utökar de tre artefakter som redan finns.

## Vad ADR 0036 INTE beslutar

- Ingen modell fyller fälten i KÖR-1a (det är kor-1b/kor-1c).
- Ingen renderer-, prompt- eller generation-ändring (kor-2 läser fälten senare).
- Ingen ny Preview Runtime, auth, billing eller scaffold-arkitektur.
- Nästlade leaf-properties blir inte canonical termer.
- Router-implementationen beslutas av KÖR-6a / PR #159; denna ADR förbokar bara
  dess vokabulär.

## Verifiering

- `python scripts/governance_validate.py` — naming-dictionary v23 validerar.
- `python scripts/check_term_coverage.py --strict` — grön (blueprint-fälten är
  camelCase och dessutom registrerade; doctermerna allowlistade i #160).
- `python -m pytest tests/test_artifact_schemas.py` — blueprint-fälten
  validerar med och utan värde; adresseringen `<routeId>.<sectionId>` hävdas på
  `sectionPlan`, `contentBlocks` och `visualDirection.sectionTreatments`.
- `tests/test_decisions_and_docs.py::test_decisions_are_uniquely_numbered` —
  0036 är unikt efter 0035.
