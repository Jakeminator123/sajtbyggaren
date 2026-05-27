# Handoff: LLM Golden Path v1

Detta dokument är handoff-noteringen för en framtida agent som tar vid där
LLM Golden Path v1-sprinten slutar. Det kompletterar den tekniska
[runbooken](llm-golden-path-runbook.md) genom att förklara *varför* arbetet
ser ut som det gör och *vad* nästa naturliga steg är.

Läs `AGENTS.md`, `docs/product-operating-context.md`, `docs/current-focus.md`
och [runbooken](llm-golden-path-runbook.md) först. Den här filen antar att
du har den kontexten.

## Var vi är just nu

LLM Golden Path v1 är **låst i kod**, inte byggd från noll. Hela kedjan
prompt → företagshemsida → preview → följdprompt → ny version fanns redan
wired i repo:t innan denna sprint. Sprinten lägger till:

- en namngiven smoke-test som låser init- och follow-up-kontraktet,
- ett multi-intent-chain-test (v1 → v2 → v3 → v4) som låser att
  följdpromptar inte regredderar versionsprovenance över flera steg,
- ett real-build-test som kör `do_build=True` och bevisar att
  `npm install` + `next build` faktiskt fungerar end-to-end,
- en operator-runbook som beskriver hur flödet körs.

Inga nya canonical namn introduceras. Sprinten ändrar inte
generation-koden eller governance-modellen. Den lägger bara skydd kring
det som redan finns så nästa agent inte bygger om det i onödan.

## Vad smoke-tester och runbook låser

Per Engine Run skrivs åtta canonical artefakter (`input.json`,
`site-brief.json`, `site-plan.json`, `generation-package.json`,
`quality-result.json`, `repair-result.json`, `build-result.json`,
`trace.ndjson`) plus en `generated-files/app/page.tsx`-snapshot.

För kedjan v1 → vN:

- `projectId` är stabil över alla versioner.
- `version` bumpas med exakt ett steg per follow-up.
- `previousVersion` pekar tillbaka korrekt.
- `followUpPrompt` registreras per steg.
- `projectDna.followUpIntent.id` matchar det intent som
  `classify_followup_intent` deterministisk klassificerar prompten som.
- `build-result.engineMode` är `init` för v1 och `followup` för v2…vN.
- Varje build får distinkt run-katalog.

Real-build-testet pinnar dessutom att `build-result.status == "ok"`,
att alla `npmSteps` lyckas, att `quality-result.status == "ok"` när de
blockerande typecheck- och build-status-checkarna verkligen körs, och
att Next.js skriver en `.next/`-katalog under dev-preview-mappen.

## Vad som inte ingår i denna v1-låsning

Följande är medvetet utanför scope. Bygg inte vidare på dessa under
samma PR/branch som v1-låsningen:

- Real codegenModel-LLM-anrop (Sprint 3B / ADR 0017). Pipelinen är
  wired; bara LLM-grenen i codegen-steget är stubbad. Det finns redan
  vissa mekaniska repair-fixes (se `packages/generation/repair/fixes/`).
- HTTP route smoke-test för `/api/prompt`. Skulle dra in zod, Node och
  mockning av Next.js-rutten — separat sprint.
- StackBlitz, PreviewRuntime, local-preview-server och preview-route.
  B125 (Safari/Firefox-fallback) är parkerad i ADR 0025.
- Lane 2 LLM contract propagation (B137–B141). Lever på separat
  WIP-branch `cursor/jakob-be-llm-contract-propagation`.
- Path B / section-driven renderer. Kräver eget arbete på
  `scripts/build_site.py`.
- clinic-healthcare runtime-aktivering. Planner-aktiv idag, runtime
  väntar på Path B.
- Allt utanför kärnflödet: auth, billing, Supabase, Stripe, Shopify,
  custom domains, deploy, marketplace, Sajtagent 2.0.

## Längre vision: föreslagen LLM-flöde-arkitektur

En extern LLM-coach gav en grundlig review av kärnflödet under
sprintens planering. Den fulla föreslagna arkitekturen är värd att ha i
ryggen även om vi medvetet bara implementerade smoke-testet och
runbooken i denna sprint. Två huvudpoänger:

1. Användarupplevelsen ska kännas som en rak v0/Lovable-liknande linje.
   Internt är det en pipeline med tydliga artefakter och deterministiska
   beslut där reproducerbarhet behövs.
2. Olika ingångar (fri prompt, wizard, starter-val, scaffold-val,
   variant-val, dossier-val, follow-up, asset-upload, scrape) ska
   alla mata in i samma pipeline, samma artefakter, samma versionering,
   samma preview. Inte separata motorer.

Föreslagen pipeline-ordning (lokal beskrivning, inte canonical namn):

```text
1. request intake      (normalisera input)
2. context assembler   (avgör hur mycket kontext LLM får)
3. discovery resolver  (deterministisk mappning till scaffold/variant/starter)
4. project input       (kundens data + valda byggblock)
5. site brief          (LLM-tolkad strategi)
6. site plan           (sid- och sektionsstruktur)
7. dossier/capability assembly
8. generation package  (komplett arbetsorder)
9. file generation / patch application
10. quality gate + repair
11. preview snapshot
12. version/run history
```

Repo:t har redan motsvarigheter till de flesta av dessa steg. Det
viktiga är att vi *inte* introducerar nya canonical namn för dem.
Coachen föreslog namn som *request envelope*, *generation context*,
*patch plan*, *project version*, *preview snapshot* — alla rejekta då
de skulle dubblera befintliga `ProjectInput` + meta-sidecar,
`FollowupIntent` + semantic merge, immutable `.vN`-snapshots under
`data/prompt-inputs/` och run-kataloger under `data/runs/`.

Roller för olika LLM-anrop som föreslogs och som matchar repo:ts
faktiska riktning (inte alla behöver vara separata API-anrop dag ett,
men de ska vara separata kontrakt):

- `briefModel` — tolkar företag, erbjudande, målgrupp, ton, lokal kontext.
- `contentModel` — konkret copy för hero, sektioner, tjänster, CTA, metadata.
- `followupIntentModel` — klassificerar följdprompt. Idag deterministisk i
  `classify_followup_intent`; LLM-version är framtida ev. uppgradering.
- `patchPlanModel` — föreslår vilka artefakter och filer som ska ändras
  vid en follow-up. Idag deterministisk semantic merge.
- `repairModel` — fixar quality/build/content-problem inom tydlig ram.
- `qualityCriticModel` — bedömer output mot quality traits.

Saker som *inte* ska vara LLM-roll i första hand:

- scaffold-resolver, starter-resolver, variant-validering
- capability-map-validering, dossier-montering
- versionering, run-identitet
- file-path-säkerhet, governance-checks

## Nästa naturliga steg

Om operatören väljer att fortsätta utveckla kärnflödet bör nästa bites
prioriteras ungefär så här. Varje bite ska gå som egen PR mot `main`
(inte staplas på samma branch).

### Bite 1: Sprint 3B real codegenModel (ADR 0017)

Real LLM-call i codegen-steget plus utbyggd mechanical-fix-svit i
`packages/generation/repair/fixes/`. Pipelinen är wired; det här är
att aktivera LLM-grenen där den idag är stubbad. Tydligt scope:
`packages/generation/codegen/codegen.py` + `packages/generation/repair/`
+ tester. Stor sprint, kräver egen plan.

### Bite 2: HTTP route smoke-test för /api/prompt

Bevisar att Node↔Python-plumbingen fungerar end-to-end. Bör hålla sig
under ~100 rader och skippa gracefully om Node saknas. Kan kräva en
liten test-rot-whitelist i `apps/viewser/lib/build-runner.ts` så
testet kan köra mot tmp-paths.

### Bite 3: Quality Gate-checkar för kontakt-CTA och placeholder-copy

Utvidga `packages/generation/quality_gate/checks/` med:

- kontakt-CTA finns på minst hero och kontaktsida,
- inga uppenbara placeholder-fraser ("Lorem ipsum", "TBD",
  "PLATSHÅLLARE") läcker till output.

Sprint 3B + Quality Gate-utbyggnaden lyfter kvaliteten på faktiska
sajter, vilket är det som drar nästa demonstrerbara produktsteg.

### Bite 4: Lane 2 LLM contract propagation (B137–B141)

Brief→render-signalpropagering (tagline, pageCount, tone,
`brand.primaryColorHex`, site-brief-ref). WIP finns redan på
`cursor/jakob-be-llm-contract-propagation`. Rebasa mot nytt `main`,
slutför regression-suiten, öppna PR.

### Bite 5: Path B / section-driven renderer

Aktiverar clinic-healthcare och liknande scaffolds runtime, inte bara
i planning. Större arbete på `scripts/build_site.py`. Kräver att Lane 2
är inne först (delar fil-territorium).

## Watch-outs och risker

- **Naming-disciplin.** Repo:t har en canonical naming-dictionary i
  `governance/policies/naming-dictionary.v1.json` och en strikt
  term-coverage-check. Inför inte nya PascalCase-koncept utan ADR.
  De föreslagna namnen från coach-LLM:en (request envelope,
  patch plan, project version, preview snapshot) ska behandlas som
  mental modell, inte som ny kod.
- **Filosofi B (jakob-be vs main).** Permanent backend-arbetsbranch är
  `jakob-be`. Tillfälliga feature-branches PR:ar direkt till `main`.
  Större backend-batchar går via `jakob-be → main` sync-PRs. Se
  `docs/ownership-map.md` och `governance/rules/branch-discipline.md`.
- **Crosstalk med jakob-be-agent.** En lokal agent på `jakob-be` jobbar
  parallellt. Branch-agenter ska hålla sig i sin lane och inte modifiera
  varandras filer eller branches. Operatören är slutreviewer.
- **`do_build=True` är långsam.** Real-build-testet tar 60–120 sekunder.
  Markerat `@pytest.mark.slow` och skippas om `npm` saknas. Använd
  `pytest -m "not slow"` lokalt för snabb iteration.
- **Mock-fallback är default utan `OPENAI_API_KEY`.** Det är en feature,
  inte en bugg — det gör smoke-tester deterministiska och körbara i CI
  utan secrets. Om `briefSource=mock-no-key` syns i artefakter är det
  förväntat i tester och i operatör-runbookens default-flöde.

## Hur man kommer igång som ny agent

1. Läs `AGENTS.md`, `docs/product-operating-context.md`,
   `docs/current-focus.md`, `docs/handoff.md`, denna fil och
   [runbooken](llm-golden-path-runbook.md).
2. Kör pre-flight: `git status --short --branch`, `git fetch origin`,
   `python scripts/focus_check.py` om den finns.
3. Validera att smoke-suiten är grön mot ditt utgångsläge:
   `python -m pytest tests/test_llm_golden_path_smoke.py -v`
   och `python -m pytest tests/test_followup_versioning_regression.py -v`.
4. Välj ett av Bite 1–5 ovan (eller annan tydlig sprint som operatören
   redan godkänt) och starta en egen branch + PR mot `main`.
5. När du är klar: kör ruff-check (baseline 0 findings), pytest-scoped
   tester, öppna draft-PR med fil-lista i body per
   `.cursor/BUGBOT.md`-disciplinen.
6. Steward uppdaterar `docs/current-focus.md` och `docs/handoff.md`
   post-merge — inte under sprinten.

## Referensmaterial (rådata, inte canonical)

För agenter som vill djupdyka i underliggande resonemang finns tre
primärkällor under [`llm-golden-path-references/`](llm-golden-path-references/):

- [`scout-audit.md`](llm-golden-path-references/scout-audit.md) — den
  read-only Scout-audit som bestämde att sprinten skulle bli en
  låsning av befintligt flöde, inte ny pipeline. Innehåller fullständig
  filkartläggning och risklistor.
- [`coach-architecture-notes.md`](llm-golden-path-references/coach-architecture-notes.md)
  — en extern coach-LLM:s 12-stegs-pipeline-skiss och rekommenderade
  LLM-roller. Mental modell, inte canonical. Innehåller mappning från
  coachens föreslagna namn till befintliga begrepp i repo:t.
- [`reviewer-feedback.md`](llm-golden-path-references/reviewer-feedback.md)
  — extern reviewer-feedback på PR #124, inklusive branch-disciplin-
  rekommendation och wording-nits som åtgärdats.

Dessa filer är **primärkällor**, inte beslut. Operatören har redan
filtrerat dem genom Scout, handoff-doc:en och PR-besluten. Använd dem
om du behöver kontext för nästa större beslut, inte som löpande
referens.

## Sprintens leverans i en mening

LLM Golden Path v1 är låst i tre testfunktioner, en multi-step
chain-test och en real Next.js build-test plus en runbook och en
handoff-doc — så att hela kedjan från fri prompt till versionerad
follow-up är bevisbart körbar, deterministisk utan OpenAI-key, och
dokumenterad för nästa agent.
