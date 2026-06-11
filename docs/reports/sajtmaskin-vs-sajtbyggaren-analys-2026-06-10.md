---
status: active
owner: orchestrator
truth_level: analysis-snapshot
snapshot_date: 2026-06-10
---

# Sajtmaskin vs Sajtbyggaren — jämförande analys & lessons learned

> **Syfte:** Det här dokumentet är skrivet för att andra agenter (och operatören)
> ska förstå (1) vad som faktiskt är BRA i `sajtmaskin` och värt att porta,
> (2) styrkor/svagheter i båda repona, (3) en opartisk bedömning av vilket repo
> som är "bäst" och vilket som har mest potential, samt (4) konkreta riktningar
> för Sajtbyggaren framåt. Portar loggas i [`docs/migration/import-log.md`](../migration/import-log.md)
> enligt befintlig procedur — **inga commits cherry-pickas från sajtmaskin.**
>
> **Källor:** Djupgranskning av `C:\Users\jakem\dev\projects\sajtmaskin` (read-only)
> och `C:\Users\jakem\Desktop\sajtbyggaren`, 2026-06-10. Sajtmaskin är och förblir
> strikt read-only-referens enligt `AGENTS.md`.

---

## 1. Executive summary (TL;DR)

| Fråga | Svar |
|---|---|
| Vilket repo har den **bästa produkten idag**? | **Sajtmaskin** — hela loopen prompt → LLM-codegen → autofix → preview → Vercel-deploy fungerar end-to-end, inkl. betalning, domäner, auth. |
| Vilket repo har den **bästa kodbasen/grunden**? | **Sajtbyggaren** — governance-som-kod, termdisciplin, ~174 testfiler, CI-grindar, tydliga paketgränser, deterministisk pipeline med quality gate. |
| Vilket har **mest potential**? | **Sajtbyggaren**, förutsatt att den portar in sajtmaskins generations-kärna i kontrollerad takt. Sajtmaskin har nått sitt komplexitetstak (139 API-routes, dubbla datamodeller, v0-arv); varje ny feature blir dyrare. Sajtbyggaren har motsatt problem: stark grund men saknar kund-app, hostad backend och bred codegen. |
| Opartisk slutsats | Behåll Sajtbyggaren som huvudspår. Behandla sajtmaskin som ett **bibliotek av beprövade lösningar** att skörda ur — inte som ett alternativ att vidareutveckla. Den enskilt största risken för Sajtbyggaren är inte teknik utan **takt**: governance-apparaten får inte bli så tung att produktytan (apps/web, hostad backend, deploy) aldrig byggs. |

**Enradare:** Sajtmaskin bevisade *vad* som ska byggas. Sajtbyggaren är *hur* det ska byggas. Jobbet nu är att flytta beviset in i strukturen.

---

## 2. Reposammanfattningar

### 2.1 Sajtmaskin (`C:\Users\jakem\dev\projects\sajtmaskin`)

- **Stack:** Next.js 16 (App Router, React 19, TS 5.9), Postgres + Drizzle (29 tabeller), Vercel AI SDK (OpenAI + Anthropic), Redis/Upstash, Vercel Blob, Stripe, Resend, Streamlit-backoffice (Python), preview-host på Fly.io.
- **Arkitektur:** Ett enda Next.js-repo (inte monorepo) med satelliter: `preview-host/` (Fly-tjänst), `services/inspector-worker/`, `backoffice/` (Streamlit), `config/` (prompt/modell-konfig som data), `infra/`.
- **Kärnflöde (fungerar end-to-end):** prompt → orkestrering (`src/lib/gen/orchestrate.ts`) → LLM-streaming (`src/lib/gen/engine.ts`) → finalize-pipeline med ~20 mekaniska autofix-regler + LLM-repair → version i Postgres (`engine_versions.files_json`) → tier-2-preview (riktig `npm run dev` på Fly) → Vercel-deploy.
- **Omfattning:** ~139 API-routes, ~436 filer bara i `src/lib/gen/`, ~275 vitest-filer, ~106 docs-md, 9 runtime-scaffolds, 19 dossierer, 3 separata eval-system.

### 2.2 Sajtbyggaren (`C:\Users\jakem\Desktop\sajtbyggaren`)

- **Stack:** Python 3.11 = "hjärnan" (generation, governance, backoffice via Streamlit), Next.js 16/React 19/Tailwind 4 = "skalet" (`apps/viewser` operatörs-UI + genererade kundsajter från `data/starters/`). TS-preview-adapters i `packages/preview-runtime/` (local-next, vercel-sandbox, stackblitz, fly).
- **Arkitektur:** Governance-först monorepo. `governance/` (21 policies, JSON-scheman, 44 ADR:er) är sanningskälla; kod härleds. Låst 8-stegskedja (ADR 0012): Init Prompt → Project Input → Starter → Scaffold → Variant → Dossier → Generation Package → Build.
- **Kärnflöde (fungerar internt):** 3-fas-motor (Understand → Plan → Build) med schema-validerade artefakter per run (`data/runs/<runId>/`), deterministisk byggare + quality gate (typecheck, route-scan, policy-compliance) + repair-loop, follow-up-kedja via OpenClaw-conductor (router → context → patch → apply). Golden Path-eval: **8.2/10** (2026-06-10).
- **Omfattning:** ~174 testfiler, 6 scaffolds, 13 soft-dossierer (0 hard), 4 starters med kod, 1 app (`apps/viewser`, localhost-only). Ingen `apps/web`, ingen auth/billing (parkerad, ADR 0035), hostade build-API:er svarar 501.

---

## 3. Styrkor & svagheter

### 3.1 Sajtmaskin

#### Styrkor

1. **Bevisad end-to-end-produkt.** Hela kedjan inkl. deploy, betalning (Stripe-credits), domänköp och auth fungerar. Detta är ovärderligt som facit: vi *vet* att flödet går att bygga och ungefär hur dyrt varje steg är.
2. **Generations-kärnan är ovanligt mogen** (`src/lib/gen/`): en orkestrerings-SSOT, BuildSpec med token-budgetar, statisk+dynamisk systemprompt (cache-vänlig), capability-inferens → dossier-injektion, route-plan, scaffold-matchning med embeddings.
3. **Autofix/repair i produktionsklass:** ~20 mekaniska fixer-regler + varm typecheck + LLM-repair-grind, med dumpbart fixer-register och dokumenterade "lanes" (`docs/architecture/fixer-lanes.md`). Detta är hundratals timmar av inlärda LLM-felmönster, kodifierade.
4. **Tre fungerande eval-system** med baseline-regression och CI-koppling (codegen-eval 18 prompts, scaffold-eval 10 prompts, billig follow-up-context-eval utan LLM-kostnad).
5. **Preview-host som riktig produkt-feature:** isolerad Fly-tjänst som kör äkta `npm run dev` + verify-lane. Medvetet byggd för att kunna lyftas ut.
6. **Konfiguration som versionerad data:** `config/prompt-core/*.md`, `config/ai_models/manifest.json`, `config/domain-rules.json` m.m. med paritets-tester mot koden.
7. **Rik observability:** event-bus, generationsloggar, prompt-to-done-metrik, error-log-RAG, backoffice-telemetri.

#### Svagheter

1. **Dubbel datamodell (hög allvarlighet):** legacy v0-tabeller (`projects`, `chats`, `versions` med `v0_*`-kolumner) lever parallellt med engine-tabellerna; deploy-vägen bryggar fortfarande båda. Namnskulden "v0" finns i routes, scripts, kolumner och mappar.
2. **API-svällning:** ~139 route-handlers mot bara 17 sidor. Audit-funnel, kostnadsfri-sidor, D-ID-avatar, inspector, Figma, Unsplash, OpenClaw-widget, domänköp m.m. delar repo med kärnloopen → omöjligt att resonera om "bara sajtbyggaren".
3. **Gudsfiler:** `useBuilderPageController.ts` ~1548 rader, `chat-message-stream-post.ts` ~1150, `generation-log-writer.ts` ~2011, `autofix/pipeline.ts` ~1194. Refaktorkostnaden är inbakad i varje ändring.
4. **Env/konfig-spretighet:** 80+ env-variabler dokumenterade över tre källor (`src/lib/env.ts`, `config/env-policy.json`, `docs/ENV.md`); backoffice är nästan ett krav för att förstå pipelinens hälsa.
5. **Strukturellt rörigt:** `blandat/`, `test_förslag_templates_blob/`, lösa root-anteckningar, tre eval-mappar, två Streamlit-appar, blandade språk utan tydlig gräns.
6. **Test-luckor:** 6 kända failande route-tester, e2e täcker inte builder-UI:t, full LLM-eval körs inte per PR.

### 3.2 Sajtbyggaren

#### Styrkor

1. **Governance-som-kod på riktigt:** policies driver arkitekturen (ADR 0001), termdisciplin via `naming-dictionary.v1.json` + `check_term_coverage.py --strict`, repo-boundaries, regelsynk till `.cursor/rules/`, ADR-disciplin (44 st). Detta är exakt motgiftet mot hur sajtmaskin blev rörigt.
2. **Deterministisk-först-byggare med quality gate:** typecheck + route-scan + policy-compliance + repair-sandwich. Kvalitet kommer från kontrakt (`page-quality-traits.v1.json`), inte prompt-hackande. "LLM som exekutör, inte arkitekt."
3. **Schema-validerade artefakter per run** (`engine-run.v1.json`): input, brief, plan, generation-package, quality-result, trace.ndjson — reproducerbart och granskbart på ett sätt sajtmaskin aldrig var.
4. **Test- och CI-kultur:** ~174 testfiler med markörfiler (core/slow/e2e/requires_node), ruff-baseline 0 fynd, builder-smoke-E2E i CI, steward-auto-bump av fokus-dokument, AI-bugg-review på PR:er.
5. **Vokabulär-komprimering (ADR 0012):** 8-stegskedjan + soft/hard-dossierer är en medveten förenkling av sajtmaskins begreppssvärm — den viktigaste enskilda lärdomen, redan implementerad.
6. **OpenClaw som conductor, inte motor:** klassificerar konversation, routar till roller, föreslår sanktionerade actions genom den deterministiska apply-kedjan. Ingen fri filpatchning. Detta löser "agent förstör bygget"-problemet strukturellt.
7. **Medveten import-disciplin:** `docs/migration/import-log.md` + read-only-gräns mot sajtmaskin förhindrar mekaniskt arv av skulden.

#### Svagheter

1. **Ingen kundprodukt:** `apps/web` finns inte; `apps/viewser` är localhost-only operatörs-UI; hostad Vercel-deploy svarar 501 på build/prompt (ingen hostad Python-backend); ingen publicerings-/deploy-pipeline för slutkund; auth/billing parkerad.
2. **Codegen är ännu smal:** mestadels deterministisk rendering + begränsade LLM-roller. Inte i närheten av sajtmaskins fria filemission — vilket är både styrkan (kontroll) och taket (uttryckskraft). Golden Path 8.2/10 med `contact` som genomgående svaghet.
3. **Policy/verklighets-drift:** `repo-boundaries.v1.json` pekar ut `packages/policies/`, `packages/shared/`, `packages/builder/` som inte finns på disk; `packages/generation/engine/` är tom (.gitkeep); `docs/heavy-llm-flow/README.md` säger "allt implementerat" medan `current-focus.md` listar kvarvarande wiring. Förvirrande för nya agenter.
4. **Egen megafil:** `scripts/build_site.py` ~3 600+ rader (erkänd i `docs/refactor/megafiles-plan.md`). Varning: samma mönster som sänkte sajtmaskin.
5. **Preview-bräcklighet:** StackBlitz-embed-problem (B59), Safari/Firefox-luckor (B125), fyra parallella preview-lägen som operatören måste förstå.
6. **Dokumentationsyta växer:** stort `docs/archive/`, lång `known-issues.md`, heavy-llm-flow-spår parallellt med sprint-historik. Hanterat, men kognitiv last.
7. **Tunna byggklossar:** 6/14 scaffolds, 0 hard-dossierer, `saas-base` är placeholder, embeddings-baserad selektion uppskjuten (ADR 0026).

---

## 4. Opartisk bedömning: vilket repo är bäst?

Betygsskala: 1–5 (5 = bäst i klassen för ett indie-/tvåmannaprojekt).

| Dimension | Sajtmaskin | Sajtbyggaren | Kommentar |
|---|:---:|:---:|---|
| Fungerande produkt idag | **5** | 2 | Sajtmaskin: hela kedjan inkl. deploy/betalning. Sajtbyggaren: internt operatörsflöde. |
| Generations-/codegen-djup | **5** | 2,5 | Sajtmaskins `src/lib/gen` är kronjuvelen. Sajtbyggarens codegen är medvetet smal ännu. |
| Kodkvalitet & arkitekturdisciplin | 2,5 | **5** | Governance, termdisciplin, boundaries vs gudsfiler och v0-arv. |
| Datamodell | 2 | **4** | Dubbel v0/engine-modell vs schema-validerade run-artefakter. (Sajtbyggaren saknar dock persistent DB-lager för kunddata än.) |
| Testning & eval | 4 | **4,5** | Båda starka. Sajtmaskin har dyrare/bredare LLM-evals; Sajtbyggaren har bättre CI-grindar och markördisciplin. |
| Skalbarhet för nya features | 1,5 | **4,5** | Detta är hela poängen med Sajtbyggaren. Varje ny feature i sajtmaskin betalar "rörighetsskatt". |
| Operatörstooling | **4,5** | 4 | Båda har Streamlit-backoffice; sajtmaskins är bredare, sajtbyggarens är register-låst och renare. |
| Dokumentation som styrmedel | 3 | **4,5** | Sajtmaskin: mycket docs, hög driftrisk. Sajtbyggaren: current-focus/handoff/ADR-kedja med steward-automation. |
| Time-to-market härifrån | **4** | 3 | Sajtmaskin ÄR på marknaden tekniskt. Men dess marginalkostnad per feature stiger; Sajtbyggarens sjunker. |
| **Potential 12 månader framåt** | 2,5 | **5** | Sajtmaskin har nått komplexitetstaket. Sajtbyggaren + skördade delar = bäst av båda. |

**Slutsats (unbiased):**

- Om frågan är *"vilket repo skulle jag lansera från imorgon?"* → **Sajtmaskin.**
- Om frågan är *"vilket repo bygger jag företaget på?"* → **Sajtbyggaren**, utan tvekan. Sajtmaskins begränsning är inte att koden är dålig — kärnan är utmärkt — utan att repots *struktur* gör vidareutveckling allt dyrare (139 routes, dubbla modeller, gudsfiler, env-sprawl). Det är klassisk "framgångsrik prototyp som blev produktion".
- **Risken med Sajtbyggaren** är spegelvänd: att governance-arbetet blir självändamål och att kundprodukten (`apps/web`, hostad backend, deploy) skjuts framåt i evighet. Mätetalet som avgör om Sajtbyggaren lyckas är inte fler policies — det är **tid till första externt deployade kundsajt**.

---

## 5. Skördelista: de BRA delarna i sajtmaskin (klassade)

Klassning: **A = porta (hög prioritet)**, **B = porta selektivt/efter behov**, **C = använd som referens, porta inte koden**, **D = porta INTE**.

### Klass A — porta (kärnvärde, relativt låg koppling)

| # | Del | Källa (sajtmaskin) | Vad det är / varför bra | Mål i Sajtbyggaren | Porteringsnot |
|---|---|---|---|---|---|
| A1 | **Autofix-regelbiblioteket** | `src/lib/gen/autofix/rules/*.ts` (~20 regler + tester), `autofix/pipeline.ts` | Kodifierade LLM-felmönster: imports, JSX, Tailwind, fonts, SDK-guards. Hundratals timmars inlärning. | `packages/generation/repair/` (utöka dagens `ensure-default-export`-fix till ett regelregister) | Porta **regel för regel** med regressionstest per regel. Skriv om till Python eller kör som TS-steg i quality gate — beslut behövs (förslag: börja med de 5 vanligaste reglerna enligt sajtmaskins fixer-register, `npm run fixers:dump`). |
| A2 | **Systemprompt-arkitekturen** (statisk kärna + dynamiska block + token-budget) | `config/prompt-core/*.md`, `src/lib/gen/system-prompt/` (`build-dynamic-context.ts`, `budget.ts`), `config/codegen-core-manifest.json` | Cache-vänlig statisk prefix + budgeterade dynamiska block. Direkt tillämpbar när `codegenModel` växer till riktig filemission. | `packages/generation/codegen/` + prompts som governance-data (ny policy, t.ex. `prompt-core.v1`) | Porta *mönstret* och prompt-texterna; registrera termer först. Sajtbyggarens "policies as source of truth" passar perfekt för detta. |
| A3 | **Eval-baseline-mönstret med regressions-grind** | `src/lib/gen/eval/` (runner, `eval-baseline.json`, `baseline.ts`), veckovis CI-workflow | Baseline-jämförelse med regressionsregler + billig no-LLM-eval för kontextpaketering. | Utöka `scripts/run_golden_path_eval.py` / `scripts/run_eval_suite.py` med committad baseline + regressionsregler i CI | Sajtbyggaren har eval-körningar men (ännu) inte sajtmaskins baseline-grind-disciplin. Lägg även in en billig follow-up-context-eval (ingen LLM-kostnad) för OpenClaw-kedjan. |
| A4 | **Dossier-innehållet (hard)** | `data/dossiers/hard/` + inspektionsmaterialet (se `docs/dossiers/sajtmaskin-import-readiness.md`) | 8 hard-paket: stripe-checkout, resend-contact-form, clerk-auth, mailchimp, openai-chat, plausible/vercel-analytics, sentry. | `packages/generation/orchestration/dossiers/hard/` | Pipeline finns redan beslutad: candidate → reviewed → verified → enabled. **Första kandidat: resend-contact-form** — den stänger samtidigt `contact`-svagheten från Golden Path-evalen (8.2/10-rapporten). Kräver schema v2-ADR. |
| A5 | **Scaffold-bredden** | `src/lib/gen/scaffolds/` (9 manifests: base-nextjs, landing-page, portfolio, blog, dashboard, ecommerce, saas-landing, auth-pages, app-shell) | Validerade startträd med protected paths + SEO-defaults. | `packages/generation/orchestration/scaffolds/<id>/` (6 finns; mappningen rymmer 14) | Porta innehåll/idéer, inte filträden rakt av — harmonisera mot Sajtbyggarens starter-modell (`data/starters/`). Prioritera de som stänger `saas-base`-placeholdern. |
| A6 | **Preview-session-livscykeln (kontraktet)** | `docs/schemas/preview-session-contract.md`, `src/lib/gen/preview/preview-session.ts`, routes `preview-{session,status,heartbeat,hibernate,destroy}` | Beprövad TTL/heartbeat/hibernate-modell för dyra previews. | `packages/preview-runtime/` + `apps/viewser/lib/preview-runtime-server.ts` | Porta *kontraktet* (tillstånd, TTL, heartbeat), inte Fly-implementationen — Sajtbyggaren har redan valt vercel-sandbox som primär (ADR 0033). Löser delar av B125-fallback-frågan. |

### Klass B — porta selektivt, när motsvarande fas startar

| # | Del | Källa | Varför / när | Mål |
|---|---|---|---|---|
| B1 | **Deploy-pipelinen till Vercel** | `src/app/api/v0/deployments/route.ts`, `src/lib/vercelDeploy.ts`, `src/lib/deploy/`, pre-deploy-autofix | Den enda färdiga "publicera kundsajt"-implementationen vi har. Porta när publicering produktifieras. | Nytt `packages/deploy/` + governance-policy. Skala bort v0-bryggan helt. |
| B2 | **Engine-DB-schemat (engine-delen, ej v0)** | `src/lib/db/schema.ts`: `engine_chats`, `engine_messages`, `engine_versions` (lifecycle_stage, parent_version_id, verification_state), `generation_telemetry` + schema-drift-test | Genomtänkt versions-/livscykelmodell för genererade sajter. Behövs när Sajtbyggaren får persistent kunddata (idag fil-baserade runs). | Ny policy + datamodell-ADR först. Porta *fältmodellen*, inte Drizzle-koden. Ta INTE med v0-tabellerna. |
| B3 | **SSE-streaming-kontraktet** | `src/lib/providers/own-engine/generation-stream.ts`, stream-format-tester | När hostad backend byggs och byggen ska streamas till UI. Redan utpekad i `docs/migration/import-log.md` (commits `29971fb`, `9eccc75`). | Hostad backend-slice + `apps/viewser`/`apps/web` API. |
| B4 | **Verifier/repair-loopen (LLM-grindad)** | `src/lib/gen/verify/` (`verifier-pass.ts`, `repair-loop.ts`, `preview-quality-gate.ts`) | Komplement till A1 när codegen blir friare: mekanisk fix först, LLM-repair som sista utväg, med grind. | `packages/generation/quality_gate/` + `repair/` |
| B5 | **Capability-inferens → dossier-brygga** | `src/lib/gen/capability-inference.ts`, `capability-dossier-bridge.ts`, `dossiers/select.ts` | Automatisk aktivering av soft-dossierer från brief-signaler. Sajtbyggaren har `capability-map.v1.json` — bryggan är den saknade biten. | `packages/generation/orchestration/` (respektera soft/hard-trösklarna i `dossier-contract.v1.json`) |
| B6 | **Observability-mönstren** | `src/lib/logging/` (event-bus, prompt-to-done-metrik), error-log-RAG (`src/lib/gen/rag/error-log-retriever.ts`) | Prompt-to-done-metrik och fel-RAG är guld för drift. Porta mönstret — INTE den 2011-raders log-writern. | `packages/generation/` + backoffice-vy (via view-registry-låset) |
| B7 | **Auth/credits-flödet** | `users`, `transactions`, `guest_usage`-modellen + Stripe-integration | Referens när ADR 0035-parkering hävs. Befintlig `christopher-ui`-branch ska också vägas in. | Framtida `apps/web` — kräver operatörsbeslut + scope-rapport först. |
| B8 | **Embeddings-baserad scaffold-matchning** | `src/lib/gen/scaffolds/matcher.ts`, `scripts/embeddings/` | Uppskjuten i Sajtbyggaren (ADR 0026). Sajtmaskins matcher är facit när den återupptas. | `packages/generation/planning/` |

### Klass C — referens/inspiration, porta inte koden

| Del | Källa | Lärdom |
|---|---|---|
| Backoffice-sidorna | `backoffice/` (20+ Streamlit-sidor) | Idéerna (fixer-register-vy, pipeline-hälsa, orkestrerings-inspektion) är bra; Sajtbyggarens backoffice har bättre disciplin (view-registry-lås). Bygg vyerna nya vid behov. |
| BuildSpec/tier-modellen (F2/F3) | `src/lib/gen/build-spec/` | Idén "policy-styrd kontext per byggnivå" är bra; F2/F3-terminologin är dock del av namnskulden. Sajtbyggarens 8-stegskedja täcker redan behovet — sno token-budget-tänket (A2), inte tier-modellen. |
| Builder-UI-flödet | `src/app/builder/`, `src/components/builder/` | UX-facit för framtida `apps/web` (entry-parsing, version-historik, preview-panel). Koden är monolitisk (1500+-radershooks) — designa om, kopiera inte. |
| Domänköps-flödet | GoDaddy/Loopia-scripts, `domain_orders` | Bevis på att flödet går att bygga; produktbeslut om det ens ska finnas i v1 saknas. |
| Wizard/brief-generering | `src/lib/builder/site-brief-generation.ts`, Deep Brief | Sajtbyggarens discovery-wizard + SNI-profiler (ADR 0045) är redan en bättre version av samma idé. Jämför endast. |

### Klass D — porta INTE (anti-lärdomar)

| Del | Varför inte |
|---|---|
| Allt med "v0" i namnet (routes, tabeller, `templates_v0/`, scripts) | Namnskuld från tidigare extern motor. Sajtbyggarens naming-dictionary förbjuder detta med rätta. |
| Den dubbla datamodellen (legacy + engine parallellt) | Den dyraste enskilda skulden i sajtmaskin. Sajtbyggaren: EN modell, schema-först, migrera hellre än brygga. |
| Sidoprodukterna: audit-funnel, kostnadsfri-sidor, D-ID-avatar, inspector-worker, Figma/Unsplash-integrationer | Scope creep som gjorde sajtmaskin oregerligt. Allt sådant kräver ADR + capability-registrering INNAN kod i Sajtbyggaren. |
| Extern OpenClaw Docker-gateway (`infra/openclaw/`) | Strider mot beslutad riktning: OpenClaw är conductor på in-repo-motorn, inte extern daemon (`docs/heavy-llm-flow/openclaw-2.0-conductor.md`). |
| Gudsfilerna som helhet (`useBuilderPageController`, `chat-message-stream-post`, `generation-log-writer`) | Funktionaliteten portas styckevis (B3, B6); filerna själva är varnande exempel. |
| Env-hanteringen (80+ env-vars över tre sanningskällor) | Sajtbyggaren: env-nycklar in i policy (`llm-models.v1.json`-mönstret) + `.env.example`, en källa. |

---

## 6. Lessons learned (det viktigaste avsnittet)

Det här är de destillerade lärdomarna från sajtmaskins resa, formulerade som regler för Sajtbyggaren. Flera är redan kodifierade i governance — de markeras ✅. De omarkerade är **nya riktningar** att aktivt vakta.

### L1. Två motorer/modeller parallellt = repots dyraste misstag ✅ (delvis)
Sajtmaskin lät v0-arvet leva kvar bredvid egen-motorn "tills vidare" — resultatet blev dubbla tabeller, dubbla routes och en deploy-väg som bryggar båda, flera år senare. **Regel:** när Sajtbyggaren byter implementation (t.ex. deterministisk renderer → friare codegen), migrera och radera. Aldrig "compat-läge" utan utgångsdatum i en ADR.

### L2. Mekanisk fix före LLM-fix — och kodifiera varje felmönster
Sajtmaskins enskilt mest värdefulla operativa insikt: LLM-utdata felar i *förutsägbara mönster*, och ett växande bibliotek av deterministiska fixer-regler (med tester) är billigare, snabbare och stabilare än att be LLM:en fixa om. Sajtbyggaren har 1 regel; sajtmaskin har ~20. **Riktning:** varje gång quality gate fäller ett bygge av ett skäl som kan fixas mekaniskt → ny regel + regressionstest, inte promptjustering. (Se A1.)

### L3. Prompts är versionerade artefakter, inte strängar i koden
Sajtmaskins `config/prompt-core/` + manifest + paritets-tester fungerade. Det som INTE fungerade var att resten av konfigen spreds över tre källor. **Riktning:** när Sajtbyggarens codegen växer, lägg promptkärnan som governance-data med schema + term-koppling från dag ett. (Se A2.)

### L4. Eval-baseline med regressions-grind, annars är evals teater
Sajtmaskins committade `eval-baseline.json` + regler för vad som räknas som regression gjorde att promptändringar kunde gå/stoppas på data. Sajtbyggaren mäter (8.2/10) men grindar inte ännu. **Riktning:** committad baseline + "eval före promptändring"-regel i CI. Komplettera med billiga no-LLM-evals för kontextpaketering. (Se A3.)

### L5. Preview är en produkt-feature med livscykel, inte en dev-detalj
TTL, heartbeat, hibernate, cold-boot-tider, kostnad per timme — sajtmaskin lärde sig detta i produktion (2–5 min första boot, ~$60–70/mån på Fly). Sajtbyggarens sandbox-spår (pre-built `.next`, ~20 s) är redan ett bättre svar, men saknar livscykelkontraktet. (Se A6.)

### L6. API-ytan ska vara proportionerlig mot produktytan
139 routes / 17 sidor är diagnosen på sajtmaskins scope creep. **Riktning:** varje ny API-route i Sajtbyggaren ska kunna pekas på en kapacitet i `capability-map` eller en vy i view-registryt. Kan den inte det — ingen route.

### L7. Operatörstooling är en multiplikator — men låst till register ✅
Båda repona bevisar att Streamlit-backoffice är rätt för enmans-drift. Sajtbyggarens view-registry-lås är förbättringen som ska behållas; sajtmaskins fria sidvildvuxenhet (1789-raders operator-sida) är varningen.

### L8. Gudsfiler är en process-bugg, inte en kodstil-fråga
Varje gudsfil i sajtmaskin började som "vi lägger det här så länge". Sajtbyggaren har redan en egen (`build_site.py`, ~3 600 rader) och en erkänd plan (`docs/refactor/megafiles-plan.md`). **Riktning:** sätt en hård radgräns (förslag: 800 rader för Python-moduler) som CI-check, inte bara en plan. Det är billigare att splitta vid 800 än vid 3 600.

### L9. Dokument som inte har en ägare och en bump-mekanism driftar ✅ (delvis)
Sajtmaskins ~106 docs-filer med aktiva/parkerade/avklarade planer kräver arkeologi. Sajtbyggarens current-focus + steward-auto-bump + arkiv-README är rätt svar — men "heavy-llm-flow säger klart / current-focus säger inte klart"-konflikten visar att även Sajtbyggaren driftar. **Riktning:** truth_level-frontmatter (som denna fil har) på alla docs utanför arkivet; motstridiga dokument arkiveras samma dag de motsägs.

### L10. Determinism och LLM-frihet är en ratt, inte ett val
Sajtmaskin valde maximal LLM-frihet och betalade med autofix/verify/repair-apparaten. Sajtbyggaren valde maximal determinism och betalar med 8.2/10-tak och tunn uttryckskraft. **Riktning:** flytta ratten stegvis — deterministisk stomme (routes, layout, tokens) + LLM-frihet inom sektioner, alltid bakom quality gate. Sajtmaskins BuildSpec-token-budgetar visar hur man budgeterar friheten.

### L11. Policy utan kod bakom = drift åt andra hållet
Sajtbyggarens `repo-boundaries` pekar på paket som inte finns; `engine/` är tom. Det är spegelbilden av sajtmaskins kod-utan-policy. **Riktning:** boundaries-filen ska valideras mot disk i CI (finns katalogen? har den kod?) — annars uppstår "aspirational architecture" som förvirrar varje ny agent.

### L12. Tid-till-kundsajt är nordstjärnan
Sajtmaskin sköt produkten först och städade aldrig. Sajtbyggaren städar först — och har efter ~1 månad ingen kundyta. Båda extremerna är fel. **Riktning:** definiera "första externa kundsajt deployad via Sajtbyggaren" som explicit milstolpe och låt den styra portningsordningen (avsnitt 7).

---

## 7. Rekommenderad riktning & portningsordning för Sajtbyggaren

Ordningen är vald för att (a) stänga kända svagheter först, (b) följa repots egen kompass (`docs/current-focus.md`, `docs/product-operating-context.md`), och (c) korta vägen till första kundsajt.

1. **Stäng `contact`-svagheten + första hard-dossier.** Porta `resend-contact-form` via candidate→reviewed→verified→enabled-pipelinen (kräver schema v2-ADR, redan förutsedd i `docs/dossiers/sajtmaskin-import-readiness.md`). Detta angriper Golden Path-evalens dominanta brist och etablerar hard-dossier-flödet i samma drag. *(A4)*
2. **Autofix-regelregister.** Porta de 5 vanligaste fixer-reglerna från sajtmaskin till `packages/generation/repair/`, en PR per regel med regressionstest. *(A1, L2)*
3. **Eval-baseline-grind i CI.** Committad baseline + regressionsregler + billig no-LLM-context-eval. *(A3, L4)*
4. **Hostad backend-slice.** Lös 501-gapet för `/api/prompt`/build på hostad Viewser (Python-backend som tjänst). Utan detta finns ingen väg till kundprodukt. SSE-kontraktet från sajtmaskin portas här. *(B3)*
5. **Preview-livscykelkontrakt.** TTL/heartbeat/hibernate ovanpå vercel-sandbox-adaptern; stänger B125-fallback-frågan strukturellt. *(A6, L5)*
6. **Scaffold/starter-expansion.** Fyll `saas-base`, porta 2–3 scaffolds från sajtmaskins nio (prioritera efter målgruppen företagshemsidor: saas-landing, ecommerce-light). *(A5)*
7. **Systemprompt-arkitektur + friare sektion-codegen.** När 1–6 är på plats: porta prompt-core-mönstret och öppna LLM-frihet inom sektioner bakom quality gate. *(A2, L10)*
8. **`apps/web` (kundskal).** Tunt skal ovanpå paketen — UX-referens från sajtmaskins builder, men ny komponentarkitektur. Auth/billing-beslut (ADR 0035 + `christopher-ui`-scope-rapport) tas här. *(C, B7)*
9. **Deploy/publicering.** Nytt `packages/deploy/` med sajtmaskins Vercel-flöde som referens, utan v0-bryggan. Detta är milstolpen "första externa kundsajt". *(B1, L12)*

**Parallellt (hygien, ingen portning):** radgräns-CI för megafiler (L8), boundaries-mot-disk-validering (L11), truth_level-frontmatter på aktiva docs (L9).

---

## 8. Snabbreferens för agenter

- **Innan du portar något:** läs `docs/migration/import-log.md` (procedur + mall) och registrera nya termer i `governance/policies/naming-dictionary.v1.json` FÖRST.
- **Sajtmaskin är read-only.** Inga commits därifrån i git-historiken. Porta = skriv om i Sajtbyggarens stil + regressionstest + logg-post.
- Nyckelfiler i sajtmaskin (för den som ska skörda):
  - Orkestrering: `src/lib/gen/orchestrate.ts`
  - Autofix: `src/lib/gen/autofix/` (regler under `rules/`)
  - Systemprompt: `config/prompt-core/` + `src/lib/gen/system-prompt/`
  - Eval: `src/lib/gen/eval/README.md`
  - Preview-kontrakt: `docs/schemas/preview-session-contract.md`
  - Deploy: `src/lib/deploy/`, `src/lib/vercelDeploy.ts`
  - DB-schema (engine-delen): `src/lib/db/schema.ts`
  - Arkitektur-docs: `docs/architecture/fas2-orchestration-and-build.md`, `fas3-preview-and-deploy.md`
- **Nyckeldokument i Sajtbyggaren:** `docs/current-focus.md` (läs först), `docs/product-operating-context.md`, `governance/policies/repo-boundaries.v1.json`, `docs/dossiers/sajtmaskin-import-readiness.md`, `docs/migration-plan.md`.

---

*Dokumentet är en ögonblicksbild 2026-06-10. När portar genomförs: uppdatera import-loggen, inte detta dokument. Om bedömningarna i avsnitt 4 motsägs av nya fakta — arkivera detta dokument enligt arkivrutinen och skriv en ny rapport.*
