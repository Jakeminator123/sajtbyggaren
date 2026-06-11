# Backoffice - översikt och vy-status

Det här är en karta över backoffice (Streamlit-appen `backoffice.py`) och en
ärlig statusbedömning av varje vy. Den finns för att svara på operatörens fråga:
"är backoffice obsolet och hänger den med dagens motor?"

Kort svar: **backoffice är inte obsolet.** Varje sektion mappar mot en levande
governance- eller data-yta, och varje vy statusbedöms mot dagens motor
(`Golden Path`, blueprint-fältgrupperna, follow-up-versionering, de två
scorecard-betydelserna och `section_add`-render-gapet).

Senaste fullständiga audit: **2026-06-11** (alla vyer genomgångna; drift som
hittades var text/framing - Playgrounds gamla "fas 3 placeholder tills
Sprint 3"-text och Follow-up Flows gamla "patch-planerare saknas"-text - och
åtgärdades direkt i stället för att märkas stale).

Påminnelse om gränsen (ADR 0002 + repo-boundaries): backoffice är operatörens
redigerings-/iakttagelseyta. Den ligger **inte** i användarens runtime och får
inte duplicera generation-logik.

## Status per vy

Klassning (samma enum som registret): **aktiv** (speglar dagens motor och läser
en riktig datayta), **diagnostisk** (kör live-checks i stället för att läsa en
lagrad yta), **stale** (fungerar men texten/innehållet har drivit från dagens
modell), eller **legacy/obsolet** (kandidat för att gömmas/arkiveras).

| Sektion / vy | Källa | Status | Kommentar |
| --- | --- | --- | --- |
| Status / Idag | `data/runs`, `data/evals/summaries/golden-path`, `governance/policies` | aktiv | Read-only landningsvy (default): senaste golden-path-eval, senaste körning, Quality Gate-sammandrag, kända brister och en färskhetsbricka per vy driven av registret. Inga subprocesser. |
| Status / Översikt | `governance/policies`, `page-quality-traits.v1.json` | aktiv | Policy-/schema-/regel-/ADR-räknare + kvalitetsmål + snabbåtgärder + read-only golden-status. |
| Status / Golden Path | `data/evals/summaries/golden-path` | aktiv | Read-only status för senaste golden-path-eval (ADR 0039), per-case-tabell + trösklar. |
| Status / System Health | health-checks | diagnostisk | Kör governance-validate, rules-sync, term-coverage, pytest -m governance, API-nyckel-koll (live-checks, ingen lagrad yta). |
| Status / Cross-Policy Status | flera policies | diagnostisk | Realtids-konsistens (samma som `pytest -m governance`), körs live vid rendering. |
| Governance / Policies | `governance/policies` | aktiv | Visa/validera policies. |
| Governance / Naming Dictionary | `naming-dictionary.v1.json` | aktiv | Canonical vokabulär (nu inkl. `Golden Path`). |
| Governance / Page Quality Traits | `page-quality-traits.v1.json` | aktiv | Kvalitetsvikter och gate-trösklar. |
| Governance / Rules | `governance/rules` | aktiv | Mänskliga regler (speglas till `.cursor/rules/`). |
| Governance / ADR | `governance/decisions` | aktiv | Beslutslogg. |
| Identitet / Identitet (SOUL) | `docs/openclaw-workspace/SOUL.md` + `TOOLS.md` | aktiv | Redigerbar dirigent-konstitution (chatt-persona, path-låst till SOUL.md) + read-only sanktionerade actions. Chatt-personan laddar SOUL server-side (ADR 0044). |
| LLM Engine / Mindmap | 7 policies | aktiv | Diagram av hela kedjan (inkl. `project-dna`, embedding). |
| LLM Engine / Init Flow | `engine-run.v1.json` m.fl. | aktiv | Init-flödesdiagram. |
| LLM Engine / Follow-up Flow | `project-dna.v1.json` m.fl. | aktiv | Follow-up/versionerings-flödet (`Project DNA`). Caption uppdaterad 2026-06-11: artifact-patch-kedjan (router -> context -> patch -> apply -> targeted render) finns; fri fil-patch i genererad kod gör det inte. |
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
| Playground / Playground | `scripts/dev_generate.py` | aktiv | Kör en engine run från backoffice (subprocess). Texterna uppdaterade 2026-06-11: fas 3 i dev-drivern är medvetet mock (riktig codegen bor i `scripts/build_site.py`), och follow-up-läget kör kedjan med mode=followup + Project ID i stället för att felaktigt påstås vara avaktiverat. |
| Playground / Loop-bevis | `scripts/run_golden_path_eval.py`, `data/evals/artifacts/playground` | aktiv | Kör golden-path-loopen deterministiskt in-process (`generate` -> `build(do_build=False)`, ingen npm/nyckel) och visar scaffold/variant/starter, routelista, quality per check, brief-/planSource och en `app/page.tsx`-snutt. Plus read-only miljö-/adapter-diagnostik (visar aldrig secret-värden). |
| Evals / Evals och telemetri | `scripts/run_eval_suite.py` + manuellt scorecard | aktiv | Smoke/regression + manuellt 1-10. Se `docs/evals.md`. |
| Underhåll / Cleanup - Säker rensning | retention-helpers | aktiv | Säker rensning av artefakter. |
| Underhåll / Cleanup - Med varning | retention-helpers | aktiv | Rensning med varning. |
| Underhåll / Toggle - Aktivera/inaktivera | scaffold-/dossier-/variant-/starter-registry | aktiv | Slå på/av byggblock. |

**Inga vyer klassas som stale/legacy efter auditen 2026-06-11.** All drift som
hittades var text/framing och åtgärdades direkt (se kommentarerna ovan). Om en
vy i framtiden inte kan hållas ärlig mot motorn ska den märkas legacy/diagnostic
här hellre än att låtsas vara aktuell.

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

- `Golden Path`: egen read-only statusvy (Status / Golden Path) + sammandrag i
  Idag/Översikt (senaste eval-summary) + Evals-vyn.
- Blueprint-fältgrupperna + `Project DNA`: LLM Engine-diagrammen (Mindmap,
  Init/Follow-up Flow) och Naming Dictionary.
- `Quality Gate` / scorecard: Översikt (kvalitetsmål) + Evals (automatiskt
  `Quality Result.scorecard` och det separata manuella scorecardet).
- Follow-up-versionering: LLM Engine / Follow-up Flow + Engine Runs.
- `section_add`-render-gapet: synliggjort som **känd brist** (inte feature) i
  Översikt, med pekare till `docs/known-issues.md` och
  `docs/gaps/GAP-followup-prompt-content-passthrough.md`.
