# Backoffice - översikt och vy-status

Det här är en karta över backoffice (Streamlit-appen `backoffice.py`) och en
ärlig statusbedömning av varje vy. Den finns för att svara på operatörens fråga:
"är backoffice obsolet och hänger den med dagens motor?"

Kort svar: **backoffice är inte obsolet.** Varje sektion mappar mot en levande
governance- eller data-yta. Det som saknades var att appen inte *speglade dagens
produktmodell* (`Golden Path`, blueprint-fältgrupperna, follow-up-versionering,
de två scorecard-betydelserna och `section_add`-render-gapet). Den här PR:en
lägger till den framingen och en read-only golden-status - utan nya
produktfeatures.

Påminnelse om gränsen (ADR 0002 + repo-boundaries): backoffice är operatörens
redigerings-/iakttagelseyta. Den ligger **inte** i användarens runtime och får
inte duplicera generation-logik.

## Status per vy

Klassning: **aktiv** (speglar dagens motor och används), **stale** (fungerar men
texten/innehållet hade drivit från dagens modell - åtgärdas i denna PR), eller
**legacy/obsolet** (kandidat för att gömmas/arkiveras).

| Sektion / vy | Källa | Status | Kommentar |
| --- | --- | --- | --- |
| Status / Idag | `data/runs`, `data/evals/summaries/golden-path`, `governance/policies` | aktiv | Read-only landningsvy (default): senaste golden-path-eval, senaste körning, Quality Gate-sammandrag, kända brister och en färskhetsbricka per vy driven av registret. Inga subprocesser. |
| Status / Översikt | `governance/policies`, `page-quality-traits.v1.json` | aktiv | Policy-/schema-/regel-/ADR-räknare + kvalitetsmål + snabbåtgärder. Får nu en read-only golden-status. |
| Status / System Health | health-checks | aktiv | Kör governance-validate, rules-sync, term-coverage, pytest -m governance, API-nyckel-koll. |
| Status / Cross-Policy Status | flera policies | aktiv | Realtids-konsistens (samma som `pytest -m governance`). |
| Governance / Policies | `governance/policies` | aktiv | Visa/validera policies. |
| Governance / Naming Dictionary | `naming-dictionary.v1.json` | aktiv | Canonical vokabulär (nu inkl. `Golden Path`). |
| Governance / Page Quality Traits | `page-quality-traits.v1.json` | aktiv | Kvalitetsvikter och gate-trösklar. |
| Governance / Rules | `governance/rules` | aktiv | Mänskliga regler (speglas till `.cursor/rules/`). |
| Governance / ADR | `governance/decisions` | aktiv | Beslutslogg. |
| LLM Engine / Mindmap | 7 policies | aktiv | Diagram av hela kedjan (inkl. `project-dna`, embedding). |
| LLM Engine / Init Flow | `engine-run.v1.json` m.fl. | aktiv | Init-flödesdiagram. |
| LLM Engine / Follow-up Flow | `project-dna.v1.json` m.fl. | aktiv | Follow-up/versionerings-flödet (`Project DNA`). |
| LLM Engine / Model Roles | `llm-models.v1.json` | aktiv | Modellroller per fas. |
| LLM Engine / Fix Types | `fix-registry.v1.json` | aktiv | Mekaniska + LLM-fixes. |
| LLM Engine / Embeddings | `embedding-policy.v1.json` | aktiv | Embedding-domäner. |
| Building Blocks / Kontrollplan | scaffolds/dossiers + branschtäckning | aktiv | Sammanhållen kontrollyta. |
| Building Blocks / Scaffolds | `packages/generation/orchestration/scaffolds` | aktiv | Scaffold-grammatik på disk. |
| Building Blocks / Selection Profiles | scaffolds | aktiv | Embedding-/signaler som styr selector. |
| Building Blocks / Variants | scaffold-variants | aktiv | Visuella varianter. |
| Building Blocks / Variant Candidates | `data/variant-candidates` | aktiv | Tooling: generera variant-kandidater. |
| Building Blocks / Dossiers | `packages/generation/orchestration/dossiers` | aktiv | Soft/hard dossiers. |
| Building Blocks / Dossier Candidates | dossier-intake/generator | aktiv | Tooling: kandidat-intag + generering. |
| Building Blocks / Reference Templates | `data/reference-templates` | aktiv | Inspirations-corpus. |
| Runs / Engine Runs | `data/runs/` | aktiv | Inspektera artefakter + `trace.ndjson`. |
| Playground / Playground | `scripts/dev_generate.py` | aktiv | Kör en engine run från backoffice (subprocess). |
| Evals / Evals och telemetri | `scripts/run_eval_suite.py` + manuellt scorecard | aktiv | Smoke/regression + manuellt 1-10. Se `docs/evals.md`. |
| Underhåll / Cleanup - Säker rensning | retention-helpers | aktiv | Säker rensning av artefakter. |
| Underhåll / Cleanup - Med varning | retention-helpers | aktiv | Rensning med varning. |
| Underhåll / Toggle - Aktivera/inaktivera | scaffold-/dossier-/variant-/starter-registry | aktiv | Slå på/av byggblock. |

**Inga vyer klassas som obsoleta/legacy i nuläget.** Om en vy i framtiden inte
kan hållas ärlig mot motorn ska den märkas legacy/diagnostic här hellre än att
låtsas vara aktuell.

### Maskinverifierat vy-register (governance-lås)

Tabellen ovan är den mänskliga kartan. Den maskinläsbara sanningskällan är
`governance/policies/backoffice-views.v1.json` (schema:
`governance/schemas/backoffice-views.schema.json`): ett register där varje vy
har `section`, `ownerSource` (ägande modul), `status`
(`active`/`stale`/`legacy`/`diagnostic`), `readsFrom` (datakällor) och
`lastVerified`. Sektion↔vy-kopplingen bor i `backoffice/view_registry.py` som
både sidomenyn (`backoffice.py`) och registret läser.

`tests/test_backoffice_registry.py` låser de två dubbelriktat: en vy som finns i
koden men saknar entry = rött, och ett entry utan motsvarande vy i koden = rött.
Samma disciplin som naming-dictionary + `check_term_coverage` redan har — en ny
vy kan inte smyga in utan att registreras och statusbedömas.

## Vad som speglar dagens motor (och var)

- `Golden Path`: read-only status i Översikt (senaste eval-summary) + Evals-vyn.
- Blueprint-fältgrupperna + `Project DNA`: LLM Engine-diagrammen (Mindmap,
  Init/Follow-up Flow) och Naming Dictionary.
- `Quality Gate` / scorecard: Översikt (kvalitetsmål) + Evals (automatiskt
  `Quality Result.scorecard` och det separata manuella scorecardet).
- Follow-up-versionering: LLM Engine / Follow-up Flow + Engine Runs.
- `section_add`-render-gapet: synliggjort som **känd brist** (inte feature) i
  Översikt, med pekare till `docs/known-issues.md` och
  `docs/gaps/GAP-followup-prompt-content-passthrough.md`.
