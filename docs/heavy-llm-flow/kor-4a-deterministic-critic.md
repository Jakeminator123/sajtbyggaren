# KÖR 4a — Deterministic critic (critic v0)

> Börja kvalitetskritiken **utan** LLM. Snabbt, billigt, ger regressionstest och
> riktning direkt. `verifierModel` kommer i `kor-4b`.

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`00-malbild-och-lager.md`](00-malbild-och-lager.md) §3.3,
[`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md).
**Beror på:** `kor-1c`, `kor-2`.

---

## Mål

En **deterministisk** critic som läser blueprint + renderad output och producerar
reparerbara issues + ett enkelt score. Ingen LLM, ingen model role, ingen OpenAI-call.
Kör som icke-blockerande lane i Quality Gate.

## Varför

Om första critic-versionen vore LLM-beroende skulle den dra med sig model role, prompts
och fallback direkt. En deterministisk critic ger i stället ett stabilt regressionstest
och en tydlig riktning — och blir en billig guardrail som `kor-4b` kan bygga ovanpå.

## Output (kontrakt)

`critic`-sektion i `quality-result.json` (icke-blockerande). Samma form som
`kor-4b` sedan återanvänder:
`{ score, issues: [{severity, type, target, message, repairHint}], source: "deterministic-v0" }`.

## Deterministiska checks (v0)

| Issue-typ | Heuristik |
|-----------|-----------|
| `generic_copy` | fraslista / likhet mot generiska mallmeningar |
| `thin_offer` | antal tjänster/bullets under tröskel |
| `placeholder_leakage` | regex mot `08-000…`, `example.se`, "lämnas på förfrågan" |
| `missing_local_context` | `locationHint` finns men output nämner inte orten |
| `missing_cta` | ingen CTA i hero/contact |

## Scope (filer)

- `packages/generation/quality_gate/` (ny deterministisk critic-check)
- `packages/generation/quality_gate/models.py` (utöka `QualityResult` med `critic`)
- `governance/schemas/quality-result.schema.json`
- `tests/`

**Off-limits:** `verifierModel`/LLM (det är `kor-4b`), göra critic blockerande, repair-
tillämpning (`kor-5`), renderers, preview/adaptrar.

## Konkret arbete

1. Implementera de fem heuristikerna; varje fynd får `target` (`<route>.<section>`),
   `severity`, `message`, `repairHint`.
2. Integrera som **warning-lane** (påverkar inte `ok/degraded/failed`). Logga i
   `trace.ndjson` när en run finns.
3. Score = enkel viktad funktion av antal/severity (dokumentera formeln).

## Testfall (DoD)

- En medvetet generisk blueprint → `generic_copy`. Placeholder-kontakt →
  `placeholder_leakage`. En tjänst → `thin_offer`.
- `locationHint` utan ortsnämning i output → `missing_local_context`.
- Critic är icke-blockerande (build-status-tester oförändrade).
- Inga LLM-anrop i denna skiva.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/quality_gate` · quality-gate-pytest ·
`governance_validate` (schema rört).

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 4a - bygg en DETERMINISTISK Quality Critic (v0) som laser blueprint +
generated-files och skriver issues + score till quality-result.json (critic-sektion),
icke-blockerande. INGEN LLM/model role.

Checks (heuristik): generic_copy, thin_offer, placeholder_leakage, missing_local_context,
missing_cta. Varje issue: target, severity, message, repairHint.

Krav:
- Icke-blockerande lane (ror inte ok/degraded/failed). Inga OpenAI-anrop.
- Dokumentera score-formeln. Logga i trace.ndjson nar run finns.

Definition of done: de fem heuristikerna flaggar ratt i testfall, build-status-tester
oforandrade, inga LLM-anrop, quality-gate-pytest + ruff grona.
```
