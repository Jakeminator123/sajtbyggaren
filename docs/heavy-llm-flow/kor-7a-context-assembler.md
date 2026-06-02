# KÖR 7a — Context Assembler (read-only)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md) §4,
[`03-preview-data-och-versioner.md`](03-preview-data-och-versioner.md) §2.
**Beror på:** `kor-1a` (artefakter finns), `kor-6a` (router sätter `contextLevel`).

---

## Mål

Bygg **bara** hämtarna som ger routern rätt kontextnivå, med hårda budgetar. **Ingen
patch, ingen build.** Read-only.

## Varför

Sajtmaskins starkaste OpenClaw-idé: hämta *lagom* mycket kontext per fråga. Att bygga
detta isolerat (utan patch/apply) gör skivan liten och ofarlig.

## Nivåer (från `02` §4)

| `contextLevel` | Källa |
|----------------|-------|
| `project_dna` | `data/prompt-inputs/<siteId>.meta.json` |
| `artifacts` | `data/runs/<runId>/{site-brief,site-plan,generation-package}.json` |
| `artifacts_plus_sections` | + Site Plan `routePlan` + scaffold `sections.json` |
| `component_registry` | `capability-map.v1.json` + dossier-manifests |
| `manifest` / `selected_files` | `generated-files/` listing / utvalda filer |
| `preview_dom` | preview-snapshot (read) |
| `external_reference` | tool call (tillåtelse-gate) |

## Scope (filer)

- `packages/generation/orchestration/` (context-assembler-modul)
- `tests/`

**Off-limits:** patch/apply (`kor-7b`/`kor-7c`), build (`kor-7d`), renderers, adaptrar,
viewser-UI, att skapa runs för loggning.

## Konkret arbete

1. En funktion per nivå som returnerar exakt det `contextLevel` kräver, inget mer.
2. **Tecken-tak per nivå.** Suppress filer som redan är kända i föregående version
   (anti-bloat).
3. Read-only: assemblern skriver inget och startar ingen build/preview.

## Testfall (DoD)

- Varje nivå returnerar förväntat innehåll och **respekterar sitt tak**.
- `external_reference` kräver tillåtelse-gate.
- Inga skrivningar, ingen run skapad, ingen build.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på modulen · assembler-pytest.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 7a - bygg en READ-ONLY Context Assembler som hamtar ratt contextLevel
(02 §4) med tecken-tak per niva och suppression av redan-kanda filer.

Krav:
- Read-only: ingen patch, ingen build, ingen run skapas. external_reference bakom gate.
- En funktion per niva; returnera bara det nivan kraver.

Definition of done: varje niva returnerar ratt innehall inom sitt tak, inga skrivningar,
ruff + assembler-pytest grona.
```
