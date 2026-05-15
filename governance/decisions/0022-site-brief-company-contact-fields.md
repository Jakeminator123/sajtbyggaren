# ADR 0022 - Site Brief: company_name och contact_* i brief

**Status:** accepted
**Datum:** 2026-05-15
**Beroenden:** ADR 0013 (schema-lock innan Sprint 2B), ADR 0012
(vocabulary compression).

## Kontext

Promptflödet kan idag förstå bransch och plats, men Site Brief saknar fält för
verkligt bolagsnamn och kontaktuppgifter. Det gör att prompts som nämner ett
bolag, telefonnummer eller e-post ändå blir Project Input med härlett namn
och tydliga platshållare:

- `company.name` blir exempelvis `Elektriker i Malmö`.
- `contact.phone` blir `+46 8 000 00 00`.
- `contact.email` blir `kontakt@example.se`.
- `contact.addressLines` blir en platshållarad.

Det är korrekt som fallback, men för demo-baseline 1B behöver explicit nämnd
kunddata få följa med från briefModel till Project Input utan manuell edit.

## Beslut

Site Brief utökas med fyra valfria fält:

| Pydantic-fält | Artefaktfält | Typ | Regel |
| --- | --- | --- | --- |
| `company_name` | `companyName` | `string | null` | Fylls bara när prompten nämner ett verkligt bolags- eller varumärkesnamn. |
| `contact_phone` | `contactPhone` | `string | null` | Fylls bara när prompten explicit nämner telefonnummer. |
| `contact_email` | `contactEmail` | `string | null` | Fylls bara när prompten explicit nämner e-postadress. |
| `contact_address` | `contactAddress` | `string | null` | Fylls bara när prompten explicit nämner adress. |

`site-brief.schema.json` har ingen egen semver- eller `version`-property att
bumpa. Ändringen är därför en bakåtkompatibel schema-utökning inom samma
schemafil: nya fält är valfria och äldre artefakter fortsätter validera.

## Schema-diff

```text
SiteBrief:
  + company_name: str | None
  + contact_phone: str | None
  + contact_email: str | None
  + contact_address: str | None

site-brief.json:
  + companyName: string | null
  + contactPhone: string | null
  + contactEmail: string | null
  + contactAddress: string | null
```

## Konsekvenser

- briefModel får en tydlig instruktion att extrahera fälten endast när de
  uttryckligen finns i prompten.
- `scripts/prompt_to_project_input.py` använder `companyName` före härledd
  bransch+plats-rubrik.
- `scripts/prompt_to_project_input.py` använder `contactPhone`,
  `contactEmail` och `contactAddress` före platshållare.
- När fälten saknas är fallbacken oförändrad: Project Input är fortfarande
  schema-valid och operatören ser tydliga platshållare.

## Vad ADR 0022 INTE beslutar

- Ingen generell Project DNA-semantik för följdprompter.
- Ingen automatisk validering eller normalisering av telefonnummer/e-post.
- Ingen trustSignals-extraktion.
- Ingen ändring av Project Input-schemat.
- Ingen ändring av starter-innehåll.

## Verifiering

- `tests/test_extract_site_brief.py` låser att Pydantic-modellen och
  `site_brief_to_artifact` exponerar de nya fälten.
- `tests/test_artifact_schemas.py` låser att `site-brief.schema.json`
  accepterar de valfria fälten.
- `tests/test_prompt_to_project_input.py` låser att explicit bolagsnamn och
  kontaktdata överförs till Project Input, och att fallbacken finns kvar när
  fälten saknas.
