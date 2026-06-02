# KÖR 7b — Artifact Patch Planner (dry-run)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-7a-context-assembler.md`](kor-7a-context-assembler.md),
[`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md) §5,
[`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md) §6.
**Beror på:** `kor-7a`, `kor-1c`.

---

## Mål

Producera **patchförslag** mot artefaktfält — men **applicera inget**. Dry-run + validering.

## Varför

Att separera "föreslå patch" från "applicera patch" gör loopen testbar och säker. Vi vet
att förslaget är giltigt (rails) innan något skrivs.

## Output (transient struktur — INTE en sparad artefakt)

```jsonc
{
  "patches": [
    { "artifact": "generation-package.json",
      "field": "contentBlocks.home.service-summary.accessoryComponent",
      "op": "set",
      "value": { "component": "clock-widget", "variant": "minimal-digital" } }
  ],
  "valid": true,
  "rejected": []
}
```

`patch plan` är ett **transient** objekt (Pydantic/Zod), inte en ny canonical run-artefakt
(se ordregeln i `04` §3).

## Scope (filer)

- `packages/generation/orchestration/` (patch-planner + `validatePatch`)
- `tests/`

**Off-limits:** apply/version (`kor-7c`), build (`kor-7d`), fri kodpatch (planeraren
patchar bara namngivna artefaktfält), renderers, adaptrar, viewser-UI.

## Konkret arbete

1. Givet router-beslut (`kor-6a`) + assembled context (`kor-7a`), producera patchar mot
   namngivna fält (`<route>.<section>.<field>`).
2. `validatePatch` kör **samma rails som planning**: section finns i `sections.json`,
   dossier i `capability-map.v1.json`, fältet finns i schemat. Ogiltigt → `rejected[]`.
3. **Applicera inget.** Returnera planen.

## Testfall (DoD)

- "lägg en klocka i andra sektionen" → giltig patch mot rätt
  `contentBlocks.home.<section>`-fält.
- Patch mot okänd section/dossier → hamnar i `rejected`, `valid: false`.
- Inga skrivningar sker (dry-run).

## Checks (scope-baserat)

`git diff --stat` · `ruff` på modulen · planner-pytest.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 7b - bygg en DRY-RUN Artifact Patch Planner som foreslar patchar mot
namngivna artefaktfalt + validatePatch (samma rails som planning). Applicera INGET.

Krav:
- patch plan ar transient (Pydantic/Zod), INTE en sparad canonical-artefakt.
- LLM/router patchar bara namngivna falt; okand section/dossier -> rejected.
- Inga skrivningar, ingen build.

Definition of done: giltig klock-patch foreslas, rail-brott hamnar i rejected, inga
skrivningar, ruff + planner-pytest grona.
```
