# Migrationsplan från sajtmaskin

Sajtbyggaren ärver inte `Jakeminator123/sajtmaskin@master` rakt av. Vi gör en kontrollerad rekonstruktion. Detta dokument håller listan över vad som plockats från vilken commit och varför. Manual ports loggas i [`docs/migration/import-log.md`](migration/import-log.md).

Beslutet att skjuta upp baseline-eval (tidigare steg 3) tills LLM-flödet finns är dokumenterat i [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md).

## Arbetsordning (uppdaterad efter ADR 0008 och ADR 0009)

1. **Governance-skelett** (klart)
   - Alla policies under [`governance/policies/`](../governance/policies/) inkl. `engine-run.v1.json` och `llm-models.v1.json`
2. **Backoffice-skelett** (klart): [`backend.py`](../backend.py) + `backoffice/`-modulen
3. **Term-disciplin och regression-tester** (klart): scripts + `tests/` + GitHub Actions
4. **Sprint 1 - Mock Engine Run** (klart): [`scripts/dev_generate.py`](../scripts/dev_generate.py) producerar alla 8 artefakter + `trace.ndjson` utan riktiga LLM-anrop. Låser artefaktkontraktet.
5. **Sprint 2 - Riktig fas 1 + fas 2 + första scaffolden**: koppla in `briefModel` och `planningModel`. Skapa `local-service-business`-scaffolden med alla obligatoriska filer, en variant (`premium-local`), två dossiers (`contact-form`, `reviews`).
6. **Sprint 3 - Riktig fas 3**: `codegenModel` + Repair Pipeline (mekaniska fixes + ev. LLM-fix) + Quality Gate (typecheck + route-scan + policy-compliance + manual score).
7. **Sprint 4 - LocalRuntime placeholder och iframe-preview**: enklast tänkbara dev-runtime.
8. **Sprint 5 - StackBlitzRuntime** som secondary (delningsbar preview).
9. **Sprint 6+ - Fler scaffolds, dossiers, eval-batch på egna körningar**.
10. **`apps/web`** byggs sist, tunt och konsumerar motorn.
11. **Followup-flöde** när init är `~9.0/10` stabilt.
12. **Sajtmaskin-baseline-eval (om alls)** sist, när Sajtbyggaren har 20-50 egna körningar att stå sig på.

## Baseline-kandidater (referens, inte mål)

Tre April-taggar är intressanta som **inspiration** under manual port. De portas inte automatiskt.

| Tag/Commit | Datum | Varför intressant |
|------------|-------|-------------------|
| `ba33b28` (`baseline-before-design-priority`) | 2026-04-16 | Liten build-fix-commit; "exceptionally good generation quality" innan Design Priority-lagret tillkom. |
| `1f4e869` (`restore-milstolpe-4232ab3`) | 2026-04 | "Simpler pipeline, richer prompts" - närmast vår målarkitektur. |
| `04b3215` (`milestone-best-version`) | 2026-04-10 | Tagg "best generation quality so far"; bevisas inte av commit ensamt. |

## Februari-commits (selektivt)

| Commit | Område | Använd för |
|--------|--------|------------|
| `3e7ca17` | Builder/auth checkpoint | Builder-livscykel-mönster (kommer i `apps/`-fasen) |
| `a5b4fb2` | Builder baseline | Builder-livscykel-mönster |
| `29971fb` | Stream UX | Streaming-handling i UI (fas 3 codegen) |
| `9eccc75` | Stream/builder responsiveness | Streaming-handling i UI |

## Inte-ta-med-listan

- `master` som-är (för bred yta, för många namnskuggor).
- Februari-snapshot (emergency backup följt av massradering).
- Tier-uppdelad quality gate. Vi har EN gate.
- Termer i [`naming-dictionary.v1.json:globallyForbidden`](../governance/policies/naming-dictionary.v1.json).
- `templates_v0/`, `archive/`, `infra/`-mappar utan klart syfte.
- Glossary/terminologi som dupliceras över `docs/`, `.cursor/rules`, kod.

## Källor till bedömningen

- [`referens/utlatanden/utlatande-1-rebuild-vs-restore.txt`](../referens/utlatanden/utlatande-1-rebuild-vs-restore.txt)
- [`referens/utlatanden/utlatande-2-llm-flode.txt`](../referens/utlatanden/utlatande-2-llm-flode.txt)
- [`referens/scaffolds-dossiers/`](../referens/scaffolds-dossiers/)
- [`referens/preview-runtime/`](../referens/preview-runtime/)
- [`referens/llm-flode/`](../referens/llm-flode/)
- Reviewerns kritik 2026-05-07 om sajtmaskin-arv och evals-ordning, vilken ledde till [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md).

## Status

| Steg | Status |
|------|--------|
| Governance-skelett | klart |
| Backoffice-skelett | klart |
| Regression-tester (governance) | klart |
| GitHub Actions (CI) | klart |
| Sprint 1 - Mock Engine Run | klart |
| Sprint 2 - Riktig fas 1 + fas 2 + första scaffolden | inte startad |
| Sprint 3 - Riktig fas 3 (codegen + repair + quality gate) | inte startad |
| Sprint 4 - LocalRuntime | inte startad |
| Sprint 5 - StackBlitzRuntime | inte startad |
| Sprint 6+ - Fler scaffolds, dossiers, evals | inte startad |
| `apps/web` | inte startad |
| Sajtmaskin-baseline-jämförelse | uppskjuten enligt [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md) |
