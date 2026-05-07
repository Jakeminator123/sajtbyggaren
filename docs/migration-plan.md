# Migrationsplan från sajtmaskin

Sajtbyggaren ärver inte `Jakeminator123/sajtmaskin@master` rakt av. Vi gör en kontrollerad rekonstruktion. Detta dokument håller listan över vad som plockats från vilken commit och varför. Manual ports loggas i [`docs/migration/import-log.md`](migration/import-log.md).

Beslutet att skjuta upp baseline-eval (tidigare steg 3) tills LLM-flödet finns är dokumenterat i [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md).

## Arbetsordning (uppdaterad efter ADR 0008)

1. **Governance-skelett** (klart)
   - Alla policies under [`governance/policies/`](../governance/policies/)
   - Schemas, rules, decisions
2. **Backoffice-skelett** (klart): [`backend.py`](../backend.py) + `backoffice/`-modulen
3. **Term-disciplin och regression-tester** (klart): scripts + `tests/` + GitHub Actions
4. **Fas 1 runtime - Site Brief** som CLI: `prompt -> Site Brief`
5. **Fas 2 runtime - Orchestration**: Scaffold, Variant, Route, Dossier, Contract, BuildSpec → Generation Package
6. **Fas 3 runtime - Codegen + Finalize + liten Quality Gate**: codegen, mekanisk autofix, validate, finalize, 4 gate-checks
7. **PreviewRuntime - LocalRuntime först**, StackBlitzRuntime när delningsbar preview behövs, FlyRuntime när hard-Dossiers kräver det
8. **Eval-batch på Sajtbyggarens egna körningar** (inte sajtmaskin): regression-tester per scaffold-/dossier-selection
9. **apps/web** byggs sist, tunt och konsumerar motorn
10. **Followup-flöde** först när init är `~9.0/10` stabilt
11. **Sajtmaskin-baseline-eval (om alls)**: jämförande eval mot taggade sajtmaskin-versioner när Sajtbyggaren själv har 20-50 körningar att stå sig på.

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
| Fas 1 runtime (Site Brief CLI) | inte startad |
| Fas 2 runtime (Orchestration) | inte startad |
| Fas 3 runtime (Codegen + Quality Gate) | inte startad |
| LocalRuntime | inte startad |
| StackBlitzRuntime | inte startad |
| Eval på egna körningar | inte startad |
| Sajtmaskin-baseline-jämförelse | uppskjuten enligt ADR 0008 |
| `apps/web` | inte startad |
