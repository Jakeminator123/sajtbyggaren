# Lane A — Docs/governance honesty-cleanup (Steward, cloud)

> **FÖRBEREDD LANE — starta manuellt.** Klistra in hela detta meddelande som
> första prompt i en Cursor Cloud Agent. Agenten klonar repot, jobbar i sin
> Ubuntu-VM, pushar till `origin/jakob-be` och slutar. Disjunkt write-set mot
> lane B (UI) och det lokala backend-arbetet (`packages/generation/**`).
>
> **Off-limits för OpenClaw-agentens filer (annan agent äger dem):**
> `scripts/fetch_openclaw_docs.py`, hela `openclaw-docs/`, och `.cursor/mcp.json`.
> Rör dem inte. För OpenClaw-*docs* (workspace/conductor) — se "koordinera"
> nedan, ändra inte blint.

---

Du arbetar i `Jakeminator123/sajtbyggaren` på branch **`jakob-be`**.

Setup (Ubuntu cloud-VM) — **egen feature-branch så lanes kan köra parallellt**:
```bash
git switch jakob-be && git pull origin jakob-be
git switch -c cursor/lane-a-docs-cleanup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
Stoppa direkt med felmeddelande till operatören om setup misslyckas — workaroundfixa inte.

**Roll:** Steward. **Scope:** docs/governance honesty-cleanup. Bara docs +
governance + EN ny valfri checker-script-fil. **Ingen runtime-kod.**
Princip genomgående: **flytta, radera inte.** Inget historiskt dokument raderas
— det flyttas till arkiv med en kort status-not.

Läs först: `AGENTS.md`, `docs/current-focus.md`, `docs/handoff.md` (topp-blocket),
`governance/rules/current-focus-hygiene.md`, `docs/glossary.md`.

## 1. Direkta fel (de tre enklaste är REDAN gjorda lokalt — verifiera, gör inte om)
REDAN FIXAT på `jakob-be` (kontrollera bara att de sitter):
- `handoff.md` header skiljer nu PR #212-squash `b49d1f7` från current main `16278c1`.
- `glossary.md` Preview Runtime: `StackBlitzRuntime` är pausad, INTE default;
  default = `local-next`, `vercel-sandbox` = opt-in primär.
- `glossary.md` Env Contract: "hybrid/hard" → "hard" (ADR 0012 tog bort hybrid).

KVAR att fixa (architecture-docs — uppdatera ELLER markera `historical`):
- `docs/architecture/preview-runtime.md` — säger StackBlitz primary/default.
  Ska spegla `local-next` default + `vercel-sandbox` primär/opt-in (ADR 0033),
  StackBlitz pausad.
- `docs/architecture/viewser.md` — beskriver Viewer som StackBlitz-embed / att
  Viewser ersätts av StackBlitzRuntime. Uppdatera till dagens Viewser
  (operator-UI) + preview-runtime/vercel-sandbox-läge.
- `docs/architecture/llm-flow.md` — säger att follow-up är utelämnat tills init
  är stabilt. Fel nu: follow-up är centralt. Uppdatera eller markera `historical`.
- `docs/architecture/scaffold-dossier-model.md` — nämner `hybrid` Dossier.
  Använd `soft`/`hard` (ADR 0012).

## 2. Flytta historik till `docs/archive/2026-06/` (skapa mappen)
Flytta dessa (lägg `status: historical` + kort "superseded av X"-rad i toppen
på varje flyttad fil):
- `docs/migration-plan.md` (säger själv superseded)
- `docs/handoff-pr-117-merge.md`
- `docs/handoff-viewser-ui-overhaul-2026-06-03.md`
- `docs/path-b-backend-scout.md`
- `docs/scaffold-runtime-extension-needed.md` (säger själv KLAR/HISTORIK)
- `docs/section-design-treatments-scout.md`
- `docs/diagnosis-and-handoff-2026-06-08.md` (bra historik men farlig som aktiv diagnos)
- `docs/codeowners-proposal.md` (om inget aktivt CODEOWNERS-arbete pågår)

`docs/open_claw.txt` nämndes av reviewern men **finns inte** i repot — hoppa över.

## 3. Gaps — verifiera status mot koden, supersede/flytta om lösta
- `docs/gaps/GAP-followup-prompt-content-passthrough.md` (`status: queued` men
  stora delar lösta) och `docs/gaps/GAP-windows-safe-rebuild-pipeline.md`
  (`status: queued` men immutable build/current.json verkar landat). Verifiera
  mot koden; om lösta → `status: superseded` + flytta till `docs/gaps/archive/`.
  Behåll `docs/gaps/gap-template.md` och befintligt `docs/gaps/archive/`.

## 4. Arkivera/markera historical (reports/spikes/integrations/dossiers)
Flytta till respektive `*/archive/` eller lägg `status: historical-reference`:
- gamla engångsprompter i `docs/agent-prompts/` (grep:a först att inget script
  länkar dem; behåll `sprintvakt.md`, `morning-fresh-start.md` och denna
  cloud-grind-yta)
- `docs/reports/*`, `docs/spikes/*`, `docs/health-checks/*`
- `docs/dossiers/sajtmaskin-import-readiness.md`
- `docs/integrations/stackblitz-research.md` + `webcontainers-notes.md` (pausad referens)

## 5. OpenClaw-docs — KOORDINERA, ändra inte blint
En annan agent arbetar med OpenClaw-implementation/MCP. Dessa fas-nyans-fixar är
RÄTT men måste stämmas av med den agenten/operatören innan edit (rör samma yta):
- `docs/heavy-llm-flow/openclaw-2.0-conductor.md`: ordna faser tydligt — Fas 1 =
  in-process registry-runtime FÖRST; Fas 2 = extern Docker/Gateway SENARE. Peka
  runtime-status till `action-registry.json`, hävda den inte i prosan.
- `docs/openclaw-workspace/README.md` + `TOOLS.md`: "ingen extern daemon/gateway"
  → fas-nyans "inte i fas 0-1 / inte nu" (annars krockar det med framtida Fas 2).
- `action-registry.json`/statusord: överlova inte `section_add` som synlig —
  `supported-mount-only`/`partial` + `mountOnly`. (Mycket av detta är redan gjort.)
Om OpenClaw-agenten redan äger en öppen ändring här: lämna det till hen, notera i rapporten.

## 6. Arkivregler + frontmatter
- Skapa/komplettera `docs/archive/README.md` (och `docs/archive/2026-06/README.md`):
  "arkiverade filer är historik, inte sanningskälla; `current-focus.md` +
  `handoff.md` toppblock är sanningskälla; arkiv får inte användas som aktuell köplan."
- Lägg frontmatter på stora aktiva docs:
  ```
  status: active | active-plan | historical | superseded
  owner: backend | ui | governance | infra
  truth_level: source | summary | historical-reference
  last_verified_commit: <sha eller unknown>
  ```

## 7. (Valfritt, lägre säkerhet) docs-checker
Ny `scripts/docs_check.py` (read-only) som flaggar: gammal SHA nära toppen av
current-focus/handoff, "jakob-be före main" kvar efter sync,
`examples/<siteId>.project-input.json` använt som runtime-path (runtime =
`data/prompt-inputs/`; `examples/` är korrekt för committade exempel), och
`section_add` + "synlig i preview". Liten `tests/test_docs_check.py`. **Lägg INTE
in den i den blockerande guard-sviten** utan operatörs-OK.

## Rör INTE (utan separat kontroll av vilka scripts som läser dem)
`docs/known-issues.md`, `docs/workboard.json` (kan vara maskinläst —
`sprintvakt_check.py`/tooling), `docs/agent-inbox.jsonl` (loggdata). Plus all
runtime-kod, `governance/policies/` (utöver minimal term-coverage-justering),
direkt-redigering av `.cursor/rules/` (kör `python scripts/rules_sync.py`), och
OpenClaw-agentens filer (`scripts/fetch_openclaw_docs.py`, `openclaw-docs/`,
`.cursor/mcp.json`). Öppna ingen PR.

## Verifiering (alla gröna före push)
```bash
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python -m pytest tests/test_docs_freshness.py tests/test_no_legacy_terms.py -q
python -m ruff check .
```

## Stoppa om
Working tree är smutsig av okända ändringar, en check failar och felet inte är
förstått, en flytt skulle bryta ett script som läser filen, eller
`origin/jakob-be` har rört sig.

## Leverans (parallell-säker — egen branch + PR mot `jakob-be`)
```bash
git push -u origin cursor/lane-a-docs-cleanup
gh pr create --base jakob-be --head cursor/lane-a-docs-cleanup \
  --title "docs(steward): docs honesty-cleanup (lane A)" \
  --body "<sammanfattning + LISTA ALLA ÄNDRADE/FLYTTADE FILER>"
```
PR-base är `jakob-be` (INTE main — main saknar jakob-be:s osynkade commits).
Lista alla ändrade/flyttade filer i PR-body (BUGBOT-disciplin: olistade filer =
scope-läckage). Operatören mergar PR:en; sync `jakob-be -> main` är ett separat
operatörsbeslut.

## Slutrapport (exakt format)
```
PR öppnad: cursor/lane-a-docs-cleanup -> jakob-be (#<nr>). Guards alla gröna:
ruff 0, governance 19/19, rules_sync OK, term-coverage --strict OK, pytest grön.
Flyttade: <lista>. Uppdaterade: <lista>. Lämnat till OpenClaw-agenten: <lista>.
Klar — vänta operatörens nästa instruktion.
```
