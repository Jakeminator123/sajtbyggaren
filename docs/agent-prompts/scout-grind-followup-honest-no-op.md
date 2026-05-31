# Scout-prompt: Followup "ärlig först" no-op-detektion (ADR 0034 / B155)

## Roll och mål

Du är en **read-only Scout-agent**. Du gör inga kod- eller doc-ändringar. Ditt enda mål är att producera **EN gedigen Builder-prompt** som en cloud-agent (grind-mode) kan klistra in och köra autonomt mot en egen branch som PR:as till `jakob-be`.

## Bakgrund

Operatör (Jakob) har 2026-05-27 + 2026-05-28 reproducerat att **fri-text follow-up-prompts blir no-op**: en ny version skapas men inget syns ändras på sajten. Promptar som "Lägg till mycket mer info om snus", "Allt mycket ljusare", "Ändra X till Y på hemsidan", "Inkludera TEST-JAKOB i hero" passerar utan visuell effekt.

ADR 0034 (proposed, ej accepted) föreslår en **tvådelad lösning**:

- **A (egen sprint, kräver Christopher):** strukturerat `copyDirectives[]`-fält i Site Brief + Project Input. Smal start: `target` + `operation` + `payload`. Större arbete.
- **B "ärlig först" (denna scout-prompt):** detektera no-op och **signalera ärligt** till UI:n att "ingen synlig ändring fångades" istället för att tyst bekräfta lyckad version. Operatören vet då direkt att hen ska prova en mer specifik prompt.

Denna scout-prompt täcker **bara backend-delen av B**. UI-delen (FloatingChat-rad som visar `applied: false`-signalen) är Christophers lane och tas separat.

Bug-IDn: `B155` (registrerad). GAP-spec: `docs/gaps/GAP-followup-prompt-content-passthrough.md`. ADR: `governance/decisions/0034-followup-prompt-content-passthrough.md`.

## Pre-flight (läs i denna ordning)

1. `AGENTS.md` — projekt-kontekst, env-setup, kommando-konventioner.
2. `docs/current-focus.md` — verifiera att uppgiften fortfarande är aktuell. Om någon har implementerat B sedan denna prompt skrevs, avbryt och rapportera "redan löst".
3. `docs/known-issues.md` — sök efter "B155" och "no-op" för aktuell bug-status.
4. `docs/gaps/GAP-followup-prompt-content-passthrough.md` — kärnspec. Innehåller reproduktion + lösningsförslag A + B + parkerad C.
5. `governance/decisions/0034-followup-prompt-content-passthrough.md` — ADR-resonemanget. Status `proposed` när scout körs.
6. `scripts/prompt_to_project_input.py` — runt `classify_followup_intent` (rad ~2042 i nuvarande HEAD). Här klassificeras prompten som `no-semantic-change | tagline-update | story-emphasize | positioning-shift | tone-shift`.
7. `scripts/build_site.py` — runt `build-result.json`-skrivning (rad 3656-ish), `input.json` (rad 3413-ish), och snapshot-skrivning till run-katalogen. Förstå var output-artefakter genereras.
8. `packages/generation/repair/` + `packages/generation/quality_gate/` — om snapshot-diff redan finns där, kanske detektionen kan piggybacka.
9. `apps/viewser/app/api/runs/[runId]/trace/route.ts` (commit `74a355b`/`fe7a9e4`) — trace-event-kontraktet UI:n läser. Kolla format så ärlig-signalen kan emitteras som ett trace-event.

## Verifiera innan prompt skrivs

- Är detektionen redan implementerad? Sök efter `applied: false`, `appliedVisibleEffect`, `noOpDetected` i `scripts/`, `packages/generation/`, `apps/viewser/lib/`. Om ja → avbryt + rapportera.
- Vilken artefakt är BÄST plats för signalen? Kandidater (lista med pros/cons):
  - `build-result.json` (per Engine Run) — naturlig plats för per-build-flagga.
  - `trace.ndjson` (event-stream) — UI:n läser redan denna live.
  - Ny dedikerad fil som `followup-effect.json` — separation of concerns men extra kontrakt.
- Vilken detektor-strategi är minst hallucinations-känslig?
  - **Strategi 1 (pre-build, klassificerar-baserad):** `followUpIntent.id == "no-semantic-change"` AND `directives.copyDirectives` saknas (eller är tom) AND inga andra strukturerade fält ändrade i Project Input v_n vs v_n_minus_1 → flagga `expectedVisibleEffect: false`.
  - **Strategi 2 (post-build, snapshot-diff):** jämför `generated-files/app/page.tsx` (+ ev. andra renderade route-filer) v_n vs v_n_minus_1. Om byte-identiska → `appliedVisibleEffect: false`. Mer robust men kräver att v_n_minus_1-snapshot finns tillgänglig.
  - **Hybrid:** strategi 1 ger pre-build-prediktion (kan visas i UI redan vid prompt-submit), strategi 2 ger post-build-bevis (auktoritativt).
- Hur upptäcks "no other structured changes in Project Input"? Lista alla diffbara fält. Operator-uppladdade media (`media.logo`, `media.heroImage`, `media.gallery`) ändras genom upload-flow, inte follow-up-prompt — men de KAN ha bumpats i samma session.

## Vad cloud-agent-prompten ska innehålla

Producera EN markdown-formatterad prompt som täcker följande. Klar att klistras in i en Cursor-agent eller cloud-grind.

### Cloud-agent-prompten ska säga

1. **Roll:** "Du är en Builder-agent i grind-mode på Cloud Agent VM."

2. **Branch-strategi:**
   - Skapa egen branch från `jakob-be`: `git fetch origin && git checkout -b cursor/grind-b155-honest-no-op origin/jakob-be`.
   - PR:a mot `jakob-be` (INTE main). Operatör mergear vid uppvaknande.

3. **Off-limits-paths (HÅRDA):**
   - `apps/viewser/components/**` (Christophers lane — UI-delen av "ärlig först" är hans).
   - `apps/viewser/app/**/*.tsx` + `apps/viewser/app/**/*.css` + `apps/viewser/public/**` (Christophers lane).
   - `governance/decisions/0034-*` (ADR ändras inte i denna grind — det är operatör-beslut att flippa till `accepted`).
   - `governance/policies/naming-dictionary.v1.json` om inga nya canonical-namn introduceras (vilket är hela poängen — vi använder `appliedVisibleEffect: boolean` som artefakt-fält, inte ett nytt domänbegrepp).
   - **VIKTIGT:** rör inte tree-kill-fixen i `apps/viewser/lib/local-preview-server.ts` (B157 round 3, redan landat).

4. **Allowed paths:**
   - `scripts/build_site.py` (skriv ärlig-signal till `build-result.json` + ev. trace-event).
   - `scripts/prompt_to_project_input.py` (om strategi 1 valt — pre-build-prediktion).
   - `packages/generation/repair/` eller liknande paket (om snapshot-diff hör hemma där per repo-boundaries-policy).
   - Eventuell ny test-fil: `tests/test_followup_honest_no_op.py` (eller liknande).
   - `docs/known-issues.md` (uppdatera B155 — "akut backend-del klar, UI-del väntar Christopher").
   - `docs/gaps/GAP-followup-prompt-content-passthrough.md` (markera del-progress).
   - `apps/viewser/app/api/runs/[runId]/trace/route.ts` är OK ATT LÄSA men inte ändra; trace-event ska bara emitteras från Python-sidan så UI:n får den via redan-existerande trace-stream.

5. **Acceptance criteria:**
   - **AC1:** När follow-up-build är klar finns ett nytt fält i `build-result.json`: `appliedVisibleEffect: boolean` (eller motsvarande, scout föreslår exakt namn). Värdet är `false` om antingen (a) `followUpIntent.id == "no-semantic-change"` OCH inga `copyDirectives[]` ELLER (b) `generated-files/app/page.tsx` är byte-identisk med v_n_minus_1-snapshot.
   - **AC2:** Strukturerat trace-event emitteras under build (t.ex. `event: "followup.no_op_detected", reason: "intent_no_semantic_change"`). UI:n kan plocka upp det utan att läsa `build-result.json` direkt.
   - **AC3:** För INIT-builds (mode: `init`) är fältet `null` eller saknas helt — det är ett follow-up-only-koncept.
   - **AC4:** Om båda strategierna säger `applied: true` (intent var t.ex. `tone-shift` OCH page.tsx skiljer sig) → fältet är `true`.
   - **AC5:** Regression-test som reproducerar Jakobs case "Lägg till mycket mer info om surdegsbröd" → `appliedVisibleEffect: false` med rimlig reason-string.
   - **AC6:** Inga regressioner i golden-path-evals: `python -m pytest tests/test_llm_golden_path_smoke.py tests/test_followup_versioning_regression.py -v` ska vara grönt.

6. **Pre-push-guards (alla MÅSTE vara gröna):**
   - `python scripts/governance_validate.py`
   - `python scripts/rules_sync.py --check`
   - `python scripts/check_term_coverage.py --strict` (om nya termer introduceras, lägg till i COMMON_WORDS i `scripts/check_term_coverage.py` — eller ADR-bump om det är canonical-namn, vilket vi vill undvika i denna grind).
   - `python -m ruff check .`
   - `python -m pytest tests/test_followup_honest_no_op.py tests/test_llm_golden_path_smoke.py tests/test_followup_versioning_regression.py -v`
   - `python scripts/sprintvakt_check.py`

7. **Commit-format:**
   - `feat(builder): close B155 backend — applied-effect-detektion + trace-event för fri follow-up`
   - Body: kort förklaring av no-op-detektion + att UI-delen är separat (Christopher) + lista relevanta tester.

8. **PR-format mot `jakob-be`:**
   - Title: `feat(builder): close B155 backend — applied-effect-detektion + trace-event för fri follow-up`
   - Body:
     - Scope-rad: ("rör BARA `scripts/build_site.py` + ev. `scripts/prompt_to_project_input.py` + 1 ny test + docs-bump").
     - Sammanfattning: 3-5 punkter.
     - Reproduktion: PR-grid med "Innan: prompten 'mer text om surdeg' → ny version, ingen signal. Efter: ny version + `appliedVisibleEffect: false` + trace-event."
     - BugBot-self-review checklist (5-6 punkter): t.ex. "snapshot-diff hanterar saknad v_n_minus_1 graceful", "trace-event emitteras före build-result skrivs så UI ser den live".
     - Länk till `docs/gaps/GAP-followup-prompt-content-passthrough.md` + `governance/decisions/0034-*`.

9. **Stop-villkor:**
   - Om Project Input-snapshot från v_n_minus_1 inte är trivialt åtkomligt → stoppa, kräver operator-OK för annan strategi.
   - Om scope växer till mer än 3 ändrade Python-filer → stoppa, kräver operator-OK.
   - Om ADR 0034 fortfarande är `proposed` när du börjar → OK att fortsätta (B-delen är fristående och kräver inte att ADR är accepted), men commit-meddelandet ska säga "ADR 0034 proposed, B-del implementerad fristående".
   - Om Cloud Agent VM saknar python3-venv → kör `sudo apt-get install -y python3-venv` per `AGENTS.md`-not.
   - Om regression-tester (golden-path-smoke + followup-versioning) failar → STOPPA och rapportera. Du har sannolikt brutit en kontraktstest.

## Scout-rapportens format

Skriv en kort rapport (max ~200 rader) i markdown. Sektioner:

1. **TL;DR** (3-5 rader): vilken strategi du föreslår + var det landar i koden + estimerad tid för cloud-agent.
2. **Verifiering** — vad du fann i `prompt_to_project_input.py`, `build_site.py`, `trace/route.ts`, snapshot-strukturen. Konkreta filsökvägar + radnummer.
3. **Strategi-val + motivering** — strategi 1 vs 2 vs hybrid, med pros/cons. Beslut + motivering.
4. **Cloud-agent-prompt** — den faktiska prompten cloud-agenten ska få. Klar att klistras in.
5. **Risker / öppna frågor** — om något är otydligt eller kräver operator-beslut, flagga separat.

## Vad du INTE ska göra

- Inga kod-ändringar. Du är read-only.
- Ingen PR. Cloud-agent gör det själv.
- Ingen UI-ändring eller UI-prompt — det är Christophers lane och separat sprint.
- Ingen ADR-flippning från `proposed` till `accepted` — det är operatör-beslut.
- Ingen `copyDirectives[]`-implementering. Det är **lösning A** i ADR 0034 och en separat sprint som kräver naming-dictionary-bump + Christopher-koord.
- Inget extra scope. Om du upptäcker andra follow-up-buggar (t.ex. `mode: followup` med fel `previousVersion`), skriv en SEPARAT scout-rapport.
- Inga ändringar i `apps/viewser/lib/local-preview-server.ts` eller `apps/viewser/lib/build-runner.ts` — B157 round 3 är just landat och rör inte denna grind.
