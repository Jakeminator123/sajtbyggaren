# KÖR 1b — briefModel fyller brief-blueprintet

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md) §2,
[`kor-1a-blueprint-schema-skelett.md`](kor-1a-blueprint-schema-skelett.md).
**Beror på:** `kor-1a`.

---

## Mål

Låt `briefModel` faktiskt fylla `businessFacts`, `positioning`, `contentStrategy` och
`conversion` i Site Brief — med mock-fallback. Ingen renderer-ändring (det är `kor-2`).

## Varför

Det är här "sidan får själ": skilja fakta från antaganden, sätta vinkel/ton, och binda
CTA-logik till ärlighetsreglerna. Utan detta förblir copy generisk oavsett prompt.

## Scope (filer)

- `packages/generation/brief/extract.py` (utöka `SiteBrief`-Pydantic + systemprompt;
  `_mock_brief` ger branschrimliga men ärliga mock-värden)
- `packages/generation/brief/` (ev. modell-/prompt-helpers)
- `tests/test_extract_site_brief.py`

**Off-limits:** schema-ändringar (gjordes i `kor-1a`), `plan.py`/Generation Package
(det är `kor-1c`), renderers, preview/adaptrar.

## Konkret arbete

1. Utöka `SiteBrief`-Pydantic med blueprint-fälten; uppdatera `_SYSTEM_INSTRUCTIONS` så
   `briefModel` returnerar `positioning`/`contentStrategy`/`businessFacts`/`conversion`.
2. `businessFacts.unknowns` ska fyllas med det modellen *inte* vet (telefon, cert, …) —
   detta är ärlighetsmotorn som `kor-2` och critic respekterar.
3. `_mock_brief` (utan `OPENAI_API_KEY`) ger ärliga mock-värden: inga fake-certs,
   `unknowns` markerade, neutral men branschrimlig positioning. `briefSource` oförändrat
   kontrakt (`real` / `mock-no-key` / `mock-llm-error`).

## Testfall (DoD)

- Fyra baseline-prompter (elektriker Malmö, frisör Göteborg, naprapat Stockholm,
  keramik-e-handel) ger **tydligt olika** `positioning.oneLiner`/`differentiator`.
- Saknad kontakt/cert hamnar i `businessFacts.unknowns`, aldrig som påhittad copy.
- Utan nyckel: identiskt kontrakt via mock.
- Befintliga brief-tester gröna.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/brief/` ·
`pytest tests/test_extract_site_brief.py -q` · mock-körning utan nyckel.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 1b - lat briefModel fylla businessFacts/positioning/contentStrategy/
conversion i Site Brief (mock + real path). Bygg pa schemat fran KOR 1a.

Krav:
- Bara brief-vagen (extract.py). Ingen schemaandring, ingen plan.py, ingen renderer.
- businessFacts.unknowns fylls arligt; inga fake-certs; CTA foljer conversion-reglerna.
- Mock utan OPENAI_API_KEY ger samma kontrakt (briefSource mock-no-key).

Definition of done: fyra baseline ger olika positioning, unknowns korrekt, mock verifierad,
brief-tester grona, ruff pa berord modul gron.
```
