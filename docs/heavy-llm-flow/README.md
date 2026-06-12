# Heavy LLM Flow — kördokument för agenter

> ## ✅ Status 2026-06-12: kör-sekvensen är implementerad, wiring är ikapp
>
> Alla kördokument nedan har landat som mergad kod i `jakob-be`
> (HEAD `54055fc`): kör 0/1a/1b/1c/2/3a/3b/4a/4b/5/6a/6b/7a/7b/7c/7d/STAB/o1/o2.
> **Dispatcha alltså inte en agent på "bygg ett nytt kör-kort" — den fasen är klar.**
>
> Det gamla statusblocket från 2026-06-04 listade fyra återstående punkter. Mot
> `jakob-be` HEAD `d234941` är läget:
>
> | Punkt | Verifierad status |
> |---|---|
> | `rerender-wiring` | Klar. `scripts/build_site.py` injicerar `_rerender_after_repair` i `run_phase3_quality_and_repair` (runt raderna 3172–3199); levererat i `cc7ddc8`. |
> | `/api/prompt` + `routerDecision` | Klar lokalt och hostat. `apps/viewser/app/api/prompt/route.ts` kör `runOpenClawFollowupApply` före legacy-bygget; `scripts/run_openclaw_followup.py --apply` kör `run_followup_chain`. Huvudbevis: `3373206`, `7391a28`, `597c2ce`, `a67a25b`. |
> | baseline-eval | Fortfarande öppen: kör de fyra baseline-prompterna i riktig preview och använd resultatet för nästa copy/trust/kontakt- eller designsystembeslut. |
> | hostad körning / 501-gap | I praktiken stängd för bygg, följdprompt och run-historik: `apps/viewser/lib/hosted-build-runner.ts` kör Python-kedjan i Vercel Sandbox, persisterar run-state/artefakter i blob och KV; `apps/viewser/lib/hosted-run-history.ts` och `/api/runs`-routes läser historik, artefakter och trace tillbaka. Huvudbevis: `1258e8d`, `a67a25b`, `261f0c6`. |
>
> Router-LLM-fallbacken från `kor-6b` är också live: `scripts/run_openclaw_followup.py`
> har den på som default och `OPENCLAW_ROUTER_LLM_FALLBACK=0` som kill-switch.
> Det kvarvarande arbetet är alltså inte fler kör-kort, utan ärlig eval och
> fortsatt breddning där evalen visar störst produktgap.

Den här mappen är en **byggplan** för att lyfta Sajtbyggaren från en kontrollerad
mall-/scaffold-generator med LLM-hjälp till en **riktig AI-hemsidebyggare** i v0-/
Lovable-/sajtmaskin-klass — utan att kasta den bra deterministiska grund som redan
finns.

Den skrevs så att en **Cursor-agent med builderprofil** kunde plocka **ett**
kördokument (`kor-*.md`), läsa de få referensdokumenten det pekar på, och bygga en
avgränsad, testbar skiva av det tunga LLM-flödet. Den rollen är nu historisk:
använd filerna som spec-/spårbarhetsunderlag, inte som en ny dispatch-kö.

> **Källa:** Destillerad från coach-konversationen i
> [`references/raw/real_llm-flow.txt`](references/raw/real_llm-flow.txt) (+ review-
> transkript i [`references/raw/`](references/raw/README.md)) + en read-only-kartläggning av både
> `sajtbyggaren` (nuvarande grund) och `sajtmaskin` (referens/baslinje), och därefter
> reviderad efter coachens dispatchbarhets-feedback (slankare checks, mindre
> överdefensiv, stora kort uppdelade). Allt här är **design och köplan** — ingen
> runtime-kod ändras av dessa dokument.

---

## Nordstjärnan (oförändrad)

Kärnflödet i [`docs/product-operating-context.md`](../product-operating-context.md)
gäller fortfarande:

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

Det tunga LLM-flödet ska göra varje steg i den loopen **avsiktligt** istället för
generiskt. Det ändrar inte målet; det fyller grunden med intelligenta beslut.

## Den enda meningen som förklarar hela mappen

> Det som saknades var **inte** mer UI och **inte** fler mallar, utan ett
> **blueprint-baserat LLM-orchestrator-lager** mellan prompten och den deterministiska
> generatorn — och en **OpenClaw-orchestrator** ovanpå som vet när den ska svara,
> planera, patcha, bygga, verifiera eller fråga vidare. Det lagret är nu delvis
> inkopplat; baseline-eval avgör var nästa kvalitetslyft behövs.

## Två lager (mental modell)

| Lager | Äger | Får aldrig |
|-------|------|------------|
| **Deterministic Foundation** (finns) | Scaffolds, variants, dossiers, starters, routes, renderers, Quality Gate, versioner, preview | — |
| **LLM Orchestrator** (byggs ut här) | Förståelse, positionering, copy, struktur-intent, designriktning, intent-routing, reparation | Skriva fria filer, hitta på claims, mounta dossiers som inte finns, byta starter utan resolver |

```text
Deterministisk grund:  "Jag vet hur man bygger en giltig sajt utan att krascha."
LLM-orchestrator:      "Jag vet vilken sajt just den här användaren borde få."
```

---

## Läsordning

1. **Detta README** — varför, lagermodell, sprintsekvens, guardrails.
2. [`00-malbild-och-lager.md`](00-malbild-och-lager.md) — målarkitektur, fullt
   init- + follow-up-flöde, "språket" (scaffold/variant/dossier/starter), var LLM:en
   är tunn idag vs ska bli smart, destillat av sajtmaskins styrkor + fallgropar.
3. [`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md) — den
   viktigaste arkitekturförändringen: **utöka** Site Brief / Site Plan / Generation
   Package till ett blueprint, **inte** uppfinna nya canonical-typer.
4. [`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md) — OpenClaw-
   routern: meddelande-/intent-klassning, `buildRequirement`, kontextnivåer,
   tool-yta, strukturerad output, klock-exemplen.
5. [`03-preview-data-och-versioner.md`](03-preview-data-och-versioner.md) —
   Vercel Sandbox som förstahandsval, adaptrar, datamodell (siteId/projectId/
   version), versionsväxling, follow-up → ny version → ny preview.
6. [`04-builder-profil.md`](04-builder-profil.md) — driftkontraktet varje
   builder-agent följer. **Scope-baserade checks** (inte alla grindar varje gång),
   ordregel (förbjud canonicalisering, inte ord), när ADR faktiskt krävs.

Kördokumenten nedan är nu främst historik/spec-bas. Dispatcha inte en ny agent
för att bygga dem igen; använd dem när du behöver förstå varför dagens kod ser
ut som den gör.
Råmaterial (coach-transkript, **icke-canonical**) ligger i
[`references/raw/`](references/raw/README.md) — läs det inte som instruktioner.

---

## Sprintsekvens (kördokumenten, historisk byggordning)

Stora kort delades upp i mindre, dispatchbara skivor. **Huvudsekvensen** nedan är den
historiska byggordningen, inte dagens aktiva kö. Varje rad var **ett** kördokument =
**en** agentuppgift.

| # | Kördokument | Levererar | Beror på |
|---|-------------|-----------|----------|
| 0 | [`kor-0-preflight.md`](kor-0-preflight.md) | Preflight: verifiera `current.json`/immutable-build i kod, current-focus/handoff, råtranskript. Levererar en kort rapport + ev. blockerflagga för `kor-7d`. **Kör först.** | — |
| 1 | [`kor-6a-router-deterministisk.md`](kor-6a-router-deterministisk.md) | Deterministisk OpenClaw Router: `messageKind`/`buildRequirement`/`contextLevel`. Ingen build på rena frågor. Klock-exemplen gröna. **Ingen LLM.** | — (parallellt) |
| 2 | [`kor-1a-blueprint-schema-skelett.md`](kor-1a-blueprint-schema-skelett.md) | Optional blueprint-fält i Site Brief/Plan/Generation Package + validators + mock-fixtures. | — |
| 3 | [`kor-1b-brief-blueprint.md`](kor-1b-brief-blueprint.md) | `briefModel` fyller `businessFacts`/`positioning`/`contentStrategy`/`conversion`. | 1b←1a |
| 4 | [`kor-1c-generationpackage-blueprint.md`](kor-1c-generationpackage-blueprint.md) | planning fyller `sectionPlan`/`contentBlocks`/`visualDirection`/`qualityRisks`. | 1a |
| 5 | [`kor-2-renderer-konsumerar-blueprint.md`](kor-2-renderer-konsumerar-blueprint.md) | Renderern läser `contentBlocks`/`visualDirection` för hero/services/story/FAQ/CTA. | 1c |
| 6 | [`kor-4a-deterministic-critic.md`](kor-4a-deterministic-critic.md) | Deterministisk Quality Critic (issues + score), icke-blockerande. **Ingen LLM.** | 1c, 2 |
| 7 | [`kor-3a-section-treatments-json.md`](kor-3a-section-treatments-json.md) | Section-treatments Python→JSON, byte-paritet. Ren refaktor. | — (efter 2) |
| 8 | [`kor-3b-visual-direction-pick.md`](kor-3b-visual-direction-pick.md) | `visualDirection` väljer treatment från JSON. | 3a, 1c |
| 9 | [`kor-5-repair-pass.md`](kor-5-repair-pass.md) | `repairModel` patchar **bara blueprint-fält** vid high-severity issues → re-render. | 1c, 4a |
| 10 | [`kor-7a-context-assembler.md`](kor-7a-context-assembler.md) | Context Assembler (kontextnivåer + budgetar), read-only. | 1a, 6a |
| 11 | [`kor-7b-patch-planner-dry-run.md`](kor-7b-patch-planner-dry-run.md) | Patch Planner dry-run (förslag + validering, applicerar inget). | 7a, 1c |
| 12 | [`kor-7c-artifact-apply-version.md`](kor-7c-artifact-apply-version.md) | Applicera validerad patch → ny Project Input-version. | 7b |
| 13 | [`kor-7d-targeted-rebuild.md`](kor-7d-targeted-rebuild.md) | Bygg om bara påverkad route + uppdatera preview. | 7c, 2 |

**Påbyggnader (LLM ovanpå deterministisk bas — historisk planstatus):**

| Kördokument | Levererar | Beror på |
|-------------|-----------|----------|
| [`kor-4b-verifier-model-critic.md`](kor-4b-verifier-model-critic.md) | `verifierModel` smak-critic ovanpå den deterministiska. | Klar i kod via `packages/generation/quality_gate/verifier.py` (`029f652`). |
| [`kor-6b-router-llm-fallback.md`](kor-6b-router-llm-fallback.md) | LLM-fallback för tvetydiga router-meddelanden. | Klar och default på i `scripts/run_openclaw_followup.py` (`2b1805d`, `729b7bd`). |
| [`kor-o1-openclaw-core-contract.md`](kor-o1-openclaw-core-contract.md) | OpenClaw Core-kontrakt (design): `OpenClawDecision` + tool-yta + capability-plan. | V0/action bridge/F1-rollmetadata har följt upp kontraktet i kod; se statusnot i filen. |

> **Var börja idag?** Läs statusblocket högst upp och kör inte om kör-korten.
> Nästa produktbevis är baseline-eval i riktig preview, följt av den smalaste
> kvalitetsinvestering som evalen pekar ut.

---

## Globala guardrails (gäller alla kördokument)

Dessa kommer från [`product-operating-context.md`](../product-operating-context.md),
coach-konversationen och kartläggningen. Detaljer + scope-baserade checks i
[`04-builder-profil.md`](04-builder-profil.md).

- **Manual/wizard-vägen är en förstaklassväg, inte en fallback.** Det tunga LLM-flödet
  ersätter inte den deterministiska genereringen — en användare ska fortsatt kunna skapa
  en helt eller semi-deterministisk startsajt via wizard/UI-val (välja eller härleda
  scaffold, variant, starter, dossiers). **Alla ingångar** (fri prompt, wizard, starter-/
  scaffold-/variant-/dossier-val, follow-up, asset-upload, scrape) matar in i **samma**
  kedja: Project Input → Site Brief → Site Plan → Generation Package → renderer/`build_site`.
  LLM-flödet får berika, reparera och personalisera samma artefaktkedja — aldrig kringgå
  eller dubblera den (ingen parallell engine, ingen ny canonical-fil).
- **LLM:en är exekutor, inte arkitekt.** Den tolkar, skriver, prioriterar, föreslår
  och förbättrar. Resolver, planning, validering, versionering och Quality Gate äger
  alla beslut som måste vara reproducerbara.
- **Förbjud canonicalisering, inte ord.** "blueprint", "patch plan" och "OpenClaw
  Router" är tillåtna som pedagogiska/transienta arbetsnamn. Det som kräver beslut är
  att göra dem till **nya sparade canonical-artefakter, typer eller runtime-kontrakt**.
  Utöka hellre Site Brief / Site Plan / Generation Package / Project Input.
- **Generated output förblir vanlig Next.js.** Inga leverantörslås i den genererade
  sajten; sådant stannar i preview-runtime-lagret (ADR 0030).
- **Rör inte preview-runtime/adaptern eller `current.json`-kontraktet** i blueprint-/
  codegen-skivorna. Preview körs via `PreviewRuntime`-adaptrar; `vercel-sandbox` är
  förstahandsval (ADR 0033).
- **Inga påhittade claims.** Ingen fake-certifiering, ingen placeholder-kontakt i
  kundcopy, ingen påhittad recension. Skilj alltid fakta från antaganden.
- **Bevara version/DNA.** Follow-up fryser scaffold/variant och bevarar `projectId`/
  `siteId`; en följdprompt skapar en ny version, inte en ny sajt.
- **Checks är scope-baserade.** Targeted test/ruff för små skivor; full femguards bara
  inför större merge/sync. ADR bara vid ny canonical artefakt/term, runtime-kontrakt,
  mappgräns eller flerlagersbeslut.
- **Vänta med** auth, billing/credits, Stripe/Supabase/Shopify, custom domains,
  booking, marknadsplats och fler initieringsvägar tills operatören uttryckligen
  säger annat.
- **Språk:** kod/JSON-fält på engelska, operatörsytor (dessa docs, UI-text) på
  svenska.

## Hur en agent dispatchas mot ett kördokument

1. Ge agenten **builderprofilen** ([`04-builder-profil.md`](04-builder-profil.md))
   som operating contract.
2. Peka den på **ett** `kor-*.md` + de referensdokument det listar under "Läs först".
3. Agenten levererar den skivan med scope-relevanta checks gröna och uppdaterar inget
   utanför sitt scope.

Detaljerad terminologi och nuvarande kodläge finns i de fem referensdokumenten ovan —
upprepa dem inte; hänvisa till dem.
