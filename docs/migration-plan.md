# Migrationsplan från sajtmaskin

Sajtbyggaren ärver inte `Jakeminator123/sajtmaskin@master` rakt av. Vi gör en kontrollerad rekonstruktion. Detta dokument håller listan över vad som plockats från vilken commit och varför.

## Arbetsordning

1. **Governance-skelett** (klart i denna iteration)
   - [`governance/policies/page-quality-traits.v1.json`](../governance/policies/page-quality-traits.v1.json)
   - [`governance/policies/llm-flow-concepts.v1.json`](../governance/policies/llm-flow-concepts.v1.json)
   - [`governance/policies/naming-dictionary.v1.json`](../governance/policies/naming-dictionary.v1.json)
   - [`governance/policies/repo-boundaries.v1.json`](../governance/policies/repo-boundaries.v1.json)
   - [`governance/policies/preview-runtime-policy.v1.json`](../governance/policies/preview-runtime-policy.v1.json)
2. **Backoffice-skelett** (klart): [`backend.py`](../backend.py)
3. **Baseline-eval** (kvarstår): kör 5-10 företagshemside-prompts mot kandidaterna nedan och välj generation-bas.
4. **Fas 1 runtime**: implementera `Site Brief` enligt naming-dictionary.
5. **Fas 2 runtime**: implementera scaffold/variant/route/dossier/contract/build-spec/package.
6. **Fas 3 runtime**: implementera codegen, finalize, quality-gate.
7. **PreviewRuntime**: StackBlitz först.
8. **apps/web**: byggs sist; followup-flöde först när init är `~9.0/10`.

## Baseline-kandidater

| Tag/Commit | Datum | Varför intressant | Plan |
|------------|-------|-------------------|------|
| `ba33b28` (`baseline-before-design-priority`) | 2026-04-16 | Liten build-fix-commit; explicit "exceptionally good generation quality" innan Design Priority-lagret tillkom (`bbc0910f` ~10 min senare). | **Primärt ankare** för generation-bas. |
| `1f4e869` (`restore-milstolpe-4232ab3`) | 2026-04 | "Restoration point där LLM-pipelinen återställdes till milstolpe-kvalitet; simpler pipeline, richer prompts". | **Stark sekundär.** Jämförs mot `ba33b28`. |
| `04b3215` (`milestone-best-version`) | 2026-04-10 | Tagg "best generation quality so far"; commit-innehåll är dock liten cleanup. | **Backup**; bevisas inte av commit ensamt. |

## Februari-commits (selektivt)

Plockas endast om motsvarande funktion behövs när vi når den fasen, inte hela trädet:

| Commit | Område | Använd för |
|--------|--------|------------|
| `3e7ca17` | Builder/auth checkpoint | Builder-livscykel-mönster |
| `a5b4fb2` | Builder baseline | Builder-livscykel-mönster |
| `29971fb` | Stream UX | Streaming-handling i UI |
| `9eccc75` | Stream/builder responsiveness | Streaming-handling i UI |

## Inte-ta-med-listan

- `master` som-är (för bred yta, för många namnskuggor).
- Februari-snapshot RAR (emergency backup följt av massradering).
- F2/F3-tier-quality-gate (förenklas till EN gate).
- `preview_host`, `VM`, `sandbox` som produkttermer.
- `templates_v0/`, `archive/`, `infra/`-mappar utan klart syfte.
- Glossary/terminologi som dupliceras över `docs/`, `.cursor/rules`, kod.

## Källor till bedömningen

- [`referens/utlatanden/utlatande-1-rebuild-vs-restore.txt`](../referens/utlatanden/utlatande-1-rebuild-vs-restore.txt) - rebuild-vs-restore-bedömning.
- [`referens/utlatanden/utlatande-2-llm-flode.txt`](../referens/utlatanden/utlatande-2-llm-flode.txt) - LLM-flödesförslag som ligger till grund för fas 1-3-strukturen.
- [`referens/starter-skiss/`](../referens/starter-skiss/) - reviewerns starter (utkast till `page-quality-traits.v1.json`, `llm-flow-concepts.v1.json`, `PreviewRuntime.ts`, `REPO_MAP.md`). Migrerat in i `governance/` med kontroll.
- [`referens/scaffolds-dossiers/`](../referens/scaffolds-dossiers/) - scaffold-/dossier-modell + paket. Destillerat till `scaffold-contract.v1.json` och `dossier-contract.v1.json`.
- [`referens/preview-runtime/`](../referens/preview-runtime/) - WebContainer-implementationsguide. Sammanfattat i `docs/integrations/webcontainers-notes.md`.
- [`referens/llm-flode/`](../referens/llm-flode/) - mermaid-diagram över init- och follow-up-flödena.

## Status

| Steg | Status |
|------|--------|
| Governance-skelett | klart |
| Backoffice-skelett | klart |
| Baseline-eval | inte startad |
| Fas 1 runtime | inte startad |
| Fas 2 runtime | inte startad |
| Fas 3 runtime | inte startad |
| PreviewRuntime | inte startad |
| apps/web | inte startad |
