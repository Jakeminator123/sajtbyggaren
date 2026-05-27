# Reviewer Feedback: PR #124

Detta är rå-/referensmaterial, inte canonical kontrakt. Canonical läge är
`docs/current-focus.md`, `docs/llm-golden-path-handoff.md` och befintliga
policies/ADR.

> Feedback från en extern reviewer-LLM som operatören konsulterade
> efter att PR #124 öppnades som draft. Sammanfattar den externa
> bedömningen av PR-scope, branch-disciplin och eventuella små nits.

---

## Sammanfattande bedömning

> "PR #124 är rätt första steg, och jag skulle inte bygga mer LLM-flöde
> innan den här är inne."

Approve i sak. Inga blockers hittade.

PR:en gör exakt det Scout föreslog: den låser befintligt
init/follow-up-flöde med en smoke-test och en runbook, utan att införa
nya canonical names eller ny pipeline. PR:en var öppen som draft,
mergeable, från `feature/llm-golden-path-v1` mot `main`.

## Runbook-bedömning

Runbooken beskriver rätt huvudflöde:

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

och mappar det internt till `generate`, project-input/meta-sidecar,
`build_site`, `generate_followup`, v2 snapshot och ny Engine Run med
`engineMode=followup`. Det är precis rätt nivå för att hindra nästa
agent från att "uppfinna" en parallell LLM-pipeline.

## Smoke-test-bedömning

Smoke-testet är rätt konstruerat:

- Kör de verkliga helpers som spelar roll: `generate`,
  `generate_followup` och `build`.
- Använder `do_build=False`, utan `OPENAI_API_KEY`, med deterministisk
  mock fallback.
- Använder `tmp_path` så ingen `data/runs`-fil pollueras.
- Kör init + follow-up.
- Verifierar att v1 och v2 får separata run-kataloger.
- Låser `projectId`, `version` 1 -> 2, `previousVersion`,
  `followUpPrompt` och `engineMode`.

## CI-läge vid review-tillfället

- GitHub Actions: Governance success.
- Vercel-previewen: ready.
- AI Bug Review: "No high-signal bug findings in this diff."

Reviewerns notering: kör en sista mänsklig kontroll av PR-checkarna i
GitHub innan merge.

## Små nits (inte blockers)

Två wording-justeringar identifierades i runbooken:

1. **"åtta JSON-filer plus snapshot":** listan innehåller
   `trace.ndjson`, som inte är en vanlig JSON-fil. Föreslagen
   formulering:

   > åtta canonical run-artefakter plus en generated-files-snapshot

   Fixad i `400b894` (commit `docs(llm-golden-path): tighten runbook
   wording per reviewer nits`).

2. **"riktiga codegenModel-anrop och mekaniska repair-fixes är
   Sprint 3B":** om repo:t redan har vissa mekaniska repair-fixes blir
   meningen för grov. Föreslagen formulering:

   > Riktiga codegenModel-anrop och full Sprint 3B-codegen/repair-gren
   > ligger utanför denna låsning.

   Fixad i samma commit (`400b894`).

Inga av dessa motiverar att blocka merge.

## Branch-target: main eller jakob-be?

**För PR #124 specifikt: låt den gå mot `main`.**

Skälet är att PR #123 nyss var en sync från `jakob-be` till `main` och
mergades 2026-05-27. PR #124 är dessutom rebased på `origin/main`
efter PR #123 och var 1 commit före `main`. Det finns inget större
värde i att retargeta till `jakob-be` nu.

## Branch-disciplin som framtida regel

Reviewern rekommenderar inte att göra "alla feature-branches direkt
mot main" till standard. Den uppdaterade branch-disciplinen säger i
praktiken:

- Jakob defaultar på `jakob-be`.
- Christopher defaultar på `christopher-ui`.
- `main` är canonical.
- PR mot `main` när en officiell version/fas/batch ska in.
- Efter merge resetas arbetsbranchen till `origin/main`.
- Direkt-push till `main` är undantag; produktkod/tester/scripts/
  packages ska gå via PR-flöde.

Reglerna sammanfattat:

| Situation | Target |
|---|---|
| Featurebranch från aktuell `main`, ska bli officiell direkt | PR mot `main` |
| Featurebranch som bygger vidare på pågående Jakob/backend/generation-spår | PR mot `jakob-be` |
| Samlad batch/fas från `jakob-be` | PR `jakob-be -> main` |
| Efter merge till `main` | Resetta `jakob-be` till `origin/main`, inte pulla/mergea tillbaka |

## Reviewerns exakta nästa-steg-rekommendation

1. Lämna PR #124 mot `main`.
2. Fixa wording-niten "åtta JSON-filer" -> "åtta canonical
   run-artefakter".
3. Markera PR:en som ready for review när du är nöjd.
4. Kontrollera att GitHub-checkarna är gröna.
5. Squash-merge.
6. Kör Steward efter merge för `docs/current-focus.md` /
   `docs/handoff.md`.
7. Synca `jakob-be` till nya `origin/main` enligt branch-disciplinen.

Reviewerns slutsats: mergea PR #124 till `main` när draft-/check-status
är klar. Detta är rätt första låsning av LLM Golden Path v1.

## Andra reviewer-passet (efter konsolidering)

Efter att v1.5-commits konsoliderats in i PR #124 (multi-intent
chain-test + real-build smoke + handoff doc), gjordes ett andra
reviewer-pass. Den bekräftade:

- PR är rimligt konsoliderad: test-/runbook-/handoff-PR, inte
  produktionskod.
- Filsetup: `tests/test_llm_golden_path_smoke.py`,
  `docs/llm-golden-path-runbook.md`,
  `docs/llm-golden-path-handoff.md`, `pyproject.toml` slow-marker.
- PR #126 stängd/superseded; arbetet inbakat i PR #124.
- Stale wording i PR-bodyn fixad: skip-build-smoke accepterar nu `ok`
  + `degraded` (inte `ok` + `skipped` som tidigare beskrivning sade).
  PR-bodyn uppdaterades; den separata commit `f728372` ändrade testet
  till accept-list `ok` + `degraded`.
- Status: Draft (ja), Mergeable (ja), Governance success,
  builder-smoke success, AI Bug Review success, Vercel/GitGuardian
  success.

## Governance/policy-bedömning

Reviewern noterar att ingen schema-/policyändring behövs för PR #124
eftersom den inte introducerar nya runtime-kontrakt eller
canonical-namn.

Den viktigaste framtida governance-risken är om någon börjar
implementera namn som *request envelope*, *patch plan* eller
*project version*. Då krävs ADR/policy eller så ska de mappas till
befintliga begrepp (Project Input, meta-sidecar, immutable
.vN-snapshots, Engine Run-katalog under `data/runs/`).

## Nästa beslut efter merge

Reviewern noterade att inget mer råmaterial behövs för att förstå
PR #124. Råmaterial behövs först när nästa implementation efter
PR #124 ska väljas, särskilt mellan:

- Sprint 3B real codegenModel
- HTTP route smoke för `/api/prompt`
- Quality Gate-utbyggnad
- Lane 2 LLM contract propagation
- Path B / section-driven renderer

Det blir ett prioriteringsbeslut, inte en dokumentationsuppgift.
