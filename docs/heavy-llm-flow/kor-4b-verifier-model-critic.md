# KÖR 4b — verifierModel critic (smak-bedömning ovanpå)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-4a-deterministic-critic.md`](kor-4a-deterministic-critic.md),
[`00-malbild-och-lager.md`](00-malbild-och-lager.md) §3.3.
**Beror på:** `kor-4a`.

---

## Mål

Wira `verifierModel` (rollen finns i `llm-models.v1.json`) som ett read-only smak-lager
ovanpå den deterministiska critic:n — för bedömningar heuristik inte fångar.

## Varför

Deterministisk critic fångar mätbara brister (placeholder, antal tjänster). Smak-fynd
(`generic_copy` som "kunde gälla vilket tjänsteföretag som helst", `weak_hero`,
`too_template_like`) behöver en LLM som läser blueprint + render. Den deterministiska
lanen finns kvar som billig guardrail och fallback.

## Output (kontrakt)

Samma `critic`-sektion, men `source: "verifierModel"` (eller `mock-no-key` /
`mock-llm-error`). LLM-fynd **mergas** med de deterministiska (deduplicera per
`type`+`target`). Issue-typer som tillkommer: `fake_or_ungrounded_trust`, `weak_hero`,
`too_template_like` (+ förfinade `generic_copy`).

## Scope (filer)

- `packages/generation/quality_gate/` (verifierModel-anrop, `generateObject`-stil)
- `packages/generation/` `verifierModel`-resolver (mönster som `resolve_brief_model`)
- `governance/policies/llm-models.v1.json` (verifiera/aktivera `verifierModel`)
- `tests/`

**Off-limits:** repair-tillämpning (`kor-5`), göra critic blockerande, renderers,
preview/adaptrar.

## Konkret arbete

1. Lägg `verifierModel`-resolver + read-only anrop som tar blueprint + `generated-files`-
   utdrag och returnerar strukturerade findings (schema-validerat).
2. Merga LLM-findings med deterministiska (`kor-4a`); deduplicera per `type`+`target`.
3. Mock utan nyckel: `critic.source = mock-no-key`, falla tillbaka till bara de
   deterministiska fynden (ingen regression mot `kor-4a`).

## Testfall (DoD)

- De fyra baseline-branscherna får score + LLM-issues utöver de deterministiska.
- Utan `OPENAI_API_KEY`: identiskt beteende som `kor-4a` (deterministiska fynd, mock-källa).
- Dedup fungerar (ingen dubbel `generic_copy` på samma target).
- Fortfarande icke-blockerande.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på berörd modul · quality-gate-pytest · mock-körning utan
nyckel · `check_term_coverage --strict` om `verifierModel`-term/fält tillkom.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 4b - wira verifierModel som read-only smak-critic ovanpa den deterministiska
critic:n (KOR 4a). LLM-findings mergas + dedupas med de deterministiska.

Krav:
- Tillkommande typer: fake_or_ungrounded_trust, weak_hero, too_template_like.
- Mock utan OPENAI_API_KEY -> samma beteende som KOR 4a (deterministiska fynd).
- Fortfarande icke-blockerande. Ingen repair-tillampning (KOR 5).

Definition of done: baseline far LLM-issues + score, mock = KOR 4a-beteende, dedup funkar,
icke-blockerande, ruff + pytest + ev. term-coverage grona.
```
