# 00 — Målbild och lager

Referensdokument. Beskriver **vart** vi ska och **vad** som redan finns att bygga på.
Inga implementationssteg här (de ligger i `kor-N-*.md`).

---

## 1. De två motorerna

Sajtbyggaren har redan en stark **deterministisk grund**. Det tunga LLM-flödet är ett
**lager ovanpå**, inte en ersättare.

| | Deterministic Foundation (finns) | LLM Orchestrator (byggs) |
|---|---|---|
| Roll | Bygger giltig sajt utan att krascha | Avgör vilken sajt användaren borde få |
| Äger | scaffolds, variants, dossiers, starters, routes, renderers, Quality Gate, repair-mekanik, versioner, preview | förståelse, positionering, copy, struktur-intent, designriktning, intent-routing, self-critique |
| Beslut | reproducerbara, testbara | kreativa, smakfulla |
| Kod | `packages/generation/**`, `scripts/build_site.py` | nya/utökade roller i `llm-models.v1.json` |

Varför inte bara "låt en LLM skriva hela Next.js-projektet"? För att det ger
hallucinerade claims, konstiga routes, trasig build, olika output varje gång, svårt
att testa och svårt att versionera. Grunden är våra **rails**.

---

## 2. Nuvarande flöde (vad som faktiskt händer idag)

Operatörsflödet (åtta steg, låst i ADR 0012) och Engine Run (8 artefakter):

```text
Init Prompt
  -> Project Input (Deep Brief)   examples/<siteId>.project-input.json
  -> Starter                      data/starters/<starterId>/
  -> Scaffold                     packages/generation/orchestration/scaffolds/<id>/
  -> Variant                      .../scaffolds/<id>/variants/<variantId>.json
  -> Dossier (soft|hard)          packages/generation/orchestration/dossiers/<class>/<id>/
  -> Generation Package
  -> Build                        ../sajtbyggaren-output/.generated/<siteId>/  +  data/runs/<runId>/
```

```text
data/runs/<runId>/
  input.json
  site-brief.json          (fas 1 Understand  — briefModel)
  site-plan.json           (fas 2 Plan        — planningModel)
  generation-package.json  (fas 2 Plan)
  generated-files/         (fas 3 Build       — deterministisk render)
  quality-result.json      (fas 3 Build       — Quality Gate)
  repair-result.json       (fas 3 Build       — mekanisk repair)
  build-result.json        (fas 3 Build)
  trace.ndjson             (Engine Events, append-only)
```

### Var LLM:en är tunn idag

| Roll | Vad den får göra idag | Vad som är deterministiskt |
|------|------------------------|-----------------------------|
| `briefModel` | **Substantiellt:** strukturerad företagsbrief (`packages/generation/brief/extract.py`) | — |
| `planningModel` | **Medel:** väljer `scaffoldId`/`variantId`/`selectedDossiers` inom registry (`PlanningChoice`) | routes, `starterId`, `buildSpec`. Builder-vägen är dessutom oftast **pinned** → inget planning-anrop |
| `codegenModel` | **Extremt tunt:** bara `rationale` + `riskNotes`, och bara för `marketing-base`. Får inte injicera filer | **alla** filer renderas deterministiskt |
| `copyDirectiveModel` | follow-up copyDirectives (company-name/tagline/about-text/services) | resten av follow-up är heuristik/whitelist |
| `verifierModel`, `repairModel`, `rerankModel` | **roller finns i `llm-models.v1.json` men anropas inte** | — |

> Det är därför upplevelsen är "LLM hjälper till runt kanterna, men den kreativa
> hemsidebyggaren är inte inkopplad". Golden-path-eval på disk säger ~7,7/10 men mäter
> struktur/nyckelord — upplevd finish ligger närmare coachens 4–5/10. Svagast:
> `copySpecificity`, kontakt-äkthet, generisk story/tagline/FAQ.

---

## 3. Målflödet (vad vi bygger mot)

### 3.1 Init

```text
Fri prompt / wizard
  -> (OpenClaw intake: är detta init?)
  -> business facts extraction        (briefModel, "Fact Extractor")
  -> positioning / vinkel             (briefModel/planningModel, "Brand Strategist")
  -> scaffold/variant/dossier-beslut  (planningModel + resolver-rails)
  -> content strategy + content blocks (briefModel/planningModel, "Copywriter")
  -> visual direction                 (planningModel, "Art Director")
  -> Generation Package v2 (blueprint)
  -> deterministisk build             (renderers, oförändrat säkra)
  -> Quality Critic                   (verifierModel)
  -> Repair pass                      (repairModel, bara blueprint-fält)
  -> preview                          (vercel-sandbox)
```

### 3.2 Follow-up

```text
user message
  -> OpenClaw Router            (är detta ens en ändring? fråga/edit/discovery/referens/bug/multi?)
  -> contextLevel-beslut        (Context Assembler: none|artifacts|sections|manifest|files|preview|reference)
  -> target resolution          (route/section/komponent)
  -> Artifact Patch Plan        (patch mot Site Brief / Site Plan / Generation Package / Project Input)
  -> targeted rebuild           (bara påverkade routes/filer)
  -> visible-effect verifier
  -> preview-uppdatering endast om något ändrades
```

### 3.3 De nio rollerna (konceptuellt — samma modell, olika systemprompter går bra)

| # | Roll | Output (utökar befintlig artefakt) | Syfte |
|---|------|-------------------------------------|-------|
| 1 | Fact Extractor | `site-brief` business facts + `unknowns` | skilja fakta från antaganden |
| 2 | Brand / Positioning Strategist | `site-brief.positioning` | ge sidan själ |
| 3 | Site Architect | `site-plan.routePlan` + `sectionPlan` | struktur från tillåtna section-typer |
| 4 | Conversion Planner | `site-brief.conversion` / `contentStrategy` | CTA-logik som följer ärlighetsregler |
| 5 | Copywriter | `generation-package.contentBlocks` | branschspecifik, grundad copy |
| 6 | Art Director | `generation-package.visualDirection` | designintentioner → tokens/varianter |
| 7 | Component Mapper | (deterministisk) blueprint → renderers/scaffolds | bron LLM↔stabilitet |
| 8 | Critic / Quality Verifier | `quality-result` issues + score | reparerbara fynd, inte bara siffra |
| 9 | Repair Agent | patch på blueprint-fält | förbättra svagheter, inte göra om allt |

Roll 7 (Component Mapper) är medvetet **inte** en LLM — det är den deterministiska
översättningen från blueprint till faktiska renderers/variants/dossiers.

---

## 4. Språket: scaffold / variant / dossier / starter

Det som gör Sajtbyggaren starkare än både ren mallmotor och fri kodagent är att LLM:en
får resonera över **deklarativa JSON-artefakter** den inte kan förstöra.

| Begrepp | "Betyder" | Var (sajtbyggaren) | Deklarativt? |
|---------|-----------|---------------------|--------------|
| **Scaffold** | vad sajten **får vara** | `packages/generation/orchestration/scaffolds/<id>/` (`scaffold.json`, `routes.json`, `sections.json`, `selection-profile.json`, `compatible-dossiers.json`, `quality-contract.json`) | Ja |
| **Variant** | hur den **får kännas** | `.../scaffolds/<id>/variants/<variantId>.json` (`tokens`: color/typography/radius/spacing/motion, `tone.vibe`) | Ja |
| **Dossier** | vilka **extra förmågor** den får ha | `.../dossiers/{soft,hard}/<id>/` (`manifest.json` + `instructions.md`) via `capability-map.v1.json` | Ja |
| **Section** | vilka **byggblock** en route kan använda | scaffoldens `sections.json` (`requiredSections`/`optionalSections`) | Ja |
| **Starter** | körbar **startpunkt** (eget Next.js-repo) | `data/starters/<id>/` (`marketing-base`, `commerce-base`, …) via `starter-registry.v1.json` + `SCAFFOLD_TO_STARTER` | JSON + Python-tabell |
| **Project Input** | vad kunden **sagt/valt** | `data/prompt-inputs/<siteId>.v<N>.project-input.json` | Ja |
| **Site Brief** | vad LLM **förstår** om kunden | `data/runs/<runId>/site-brief.json` | Ja |
| **Site Plan** | hur sajten ska **struktureras** | `data/runs/<runId>/site-plan.json` | Ja |
| **Generation Package** | **arbetsordern** till generatorn | `data/runs/<runId>/generation-package.json` | Ja (men tunn idag) |

### Vad som finns på disk just nu

- **Scaffolds (6):** `agency-studio`, `clinic-healthcare`, `ecommerce-lite`,
  `local-service-business`, `professional-services`, `restaurant-hospitality`
  (8 till i policy utan `scaffold.json` ännu).
- **Variants (27):** t.ex. `nordic-trust`, `warm-craft`, `clean-store`,
  `legal-classic`, `studio-monochrome`, `warm-bistro`.
- **Dossiers (11 soft, 0 hard):** `mailto-contact-form`, `menu-display`,
  `booking-cta`, `image-gallery`, `opening-hours`, `reviews-display`, `map-embed`,
  `pricing-table`, `faq-accordion`, `video-hero`, `interactive-game-loop`. Alla är
  `instructions-only` (`files: []`, `codeFidelity: rewritable`). Hard dossiers
  (t.ex. `stripe-checkout`) är planerade men inte byggda.
- **Starters:** `marketing-base` (5 scaffolds), `commerce-base` (`ecommerce-lite`),
  `portfolio-base`/`docs-base`/`saas-base` (inte runtime-mappade ännu).

> **Starters = "egna repos".** Det är detta operatören menar med "en eller ett par
> starters inkopplade i form av egna repos": körbara Next.js-startpunkter som builder
> kopierar och scaffold/variant/dossier sedan bygger ovanpå (ADR 0011). LLM:en får
> **välja** starter via scaffold, men aldrig byta starter utan resolver eller hitta på
> en ny.

### Embeddings = parkerade (ADR 0026)

`selection-profile.json` har `embeddingText` redo, men ingen vektor-index körs.
Selektion sker idag via nyckelord/heuristik + LLM-klassning över `selection-profile`-
text i planning-prompten. Golden-path bekräftar att rätt scaffold/variant väljs varje
gång (`industryFit` 10) → **selektion är inte gapet**. Bygg inte embeddings för att
lyfta kvalitet; gapet är copy/positionering/visual direction/verifiering.

---

## 5. Hur de två systemen kompletterar varandra

LLM:en **får**: välja avsikt, vinkel, copy, prioritet, förslag.
Resolver **validerar**: scaffold/variant/dossier finns och är tillåtna.
Renderer **bygger** säkert. Quality **bedömer**. OpenClaw **håller kontexten** och
väljer nästa steg.

LLM:en får **inte**: skapa ny scaffold, mounta dossier som inte finns, använda
checkout/auth "för att det låter bra", skapa fake-recension, byta starter utan
resolver.

---

## 6. Destillat av sajtmaskin (referens, inte kodbas)

Sajtmaskin gjorde det tunga flödet på riktigt. Lån **idéerna**, inte bredden.

### Starka, återanvändbara idéer

1. **Single orchestration fan-in** — en `prepareGenerationContext()` som samlar
   scaffold + routes + contracts + BuildSpec + dossiers innan dyr promptkomposition.
2. **BuildSpec som policy-bunt** — context-budget, F2/F3, verifieringsnivå,
   change-scope härleds **en gång per tur**.
3. **Statisk/dynamisk promptdelning** med separator + pruning-telemetri.
4. **Orchestration snapshot** + `buildFollowUpBriefFromSnapshot` — follow-up behåller
   capabilities/design utan att köra om Deep Brief. (Motsvarar vår snapshot-brief-idé.)
5. **Follow-up intent-taxonomi** som styr scaffold-unlock, variant-lock, dossier-
   inject/suppress.
6. **QA short-circuit** — rena frågor (`qa-or-score`) spawnar **ingen** codegen.
7. **Post-stream pipeline-kontrakt** med ordnade faser och deep-path-gating för
   verifier.
8. **OpenClaw som sidecar** med nyckelords-tierad kodkontext (none/light/manifest/
   full) — produkt-hjälp utan att röra codegen-state-machine.
9. **Deterministiskt dossier-val** (ingen embedding-roulette) mot brief-capabilities.
10. **F2 vs F3 lifecycle** som separerar design-preview från integrations-build.

### Vad som gjorde sajtmaskin kaotiskt (undvik)

| Fallgrop | Lärdom för Sajtbyggaren |
|----------|--------------------------|
| Parallella brief-vägar (klient, server-auto, snapshot, delta) | **En** brief-väg per läge (init = Deep Brief, follow-up = snapshot) |
| Halv-wirad `requestKind` (klassad men ignorerad) | Wira intent **hela vägen** eller lägg den inte till |
| Två överlappande klassificerare | Håll **en** tydlig intent-yta (se `02`) |
| Många repair-call-sites (samma `runLlmFixer`) | **En** repair-gate (vår repair-pipeline är redan central — håll den så) |
| Token-yta exploderar (structural scaffold + verbatim dossier + 180k full-repo-kontext) | Hårda context-budgetar per nivå; suppress redan-kända filer |
| Scope creep (auth + D-ID + deploy + 9 scaffolds + dossier-pool samtidigt) | En skiva i taget; vänta med integrationer (produktkompassen) |
| Legacy-namn (`v0`, `demoUrl`, `template-library`) | Term-disciplin; `previewUrl`, inte `demoUrl` |

> **OpenClaw-nyansen:** i sajtmaskin var OpenClaw en **sidecar bredvid** codegen, inte
> orchestratorn ovanför. Coachens (och operatörens) önskan är att i Sajtbyggaren låta
> OpenClaw bli **routern ovanpå** init/follow-up — med tool calls — men fortfarande
> utan att kapa pipelinen. Se [`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md).

---

## 7. Sammanfattande målarkitektur

```text
                    +---------------------+
                    |  OpenClaw Router    |
                    |  forsta meddelandet |
                    +----------+----------+
                               |
        +----------------------+----------------------+
        |                      |                      |
   answer only          plan/review only         site change
        |                      |                      |
        v                      v                      v
   svara direkt          visa forslag          Context Assembler
                                                       |
                                                       v
                                              Artifact Patch Plan
                                                       |
                                                       v
                                            Befintlig pipeline
                                       Project Input / Brief / Plan
                                       Generation Package / Build
                                       Quality / Repair / Preview
```

OpenClaw **ersätter inte** pipelinen. Den står ovanför och väljer **hur** pipelinen
ska användas.
