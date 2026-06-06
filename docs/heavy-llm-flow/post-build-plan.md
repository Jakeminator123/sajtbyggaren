# Post-build-plan — när hela kör-sekvensen är implementerad

> **Syfte:** Ett varaktigt, följbart dokument för nästa fas. När
> `docs/heavy-llm-flow/`-kör-sekvensen väl är byggd (alla kort mergade,
> `jakob-be` @ `54055fc`, 2026-06-04) är nästa arbete **inkoppling + härdning +
> eval** — inte fler kör-kort. Det här dokumentet säger i vilken ordning, varför,
> och hur vi vet att vi är "i synk". Vilken LLM/agent som helst ska kunna plocka
> upp det och fortsätta. Läs `docs/current-focus.md` först (den pekar hit).

## Nordstjärna (oförändrad)

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

Allt nedan mäts mot den loopen. Intern städning får inte vinna över produktflödet
om den inte hjälper loopen direkt.

---

## Var vi står (verifierat i kod 2026-06-04)

- **Bygget: klart.** Alla kör-kort är mergade i `jakob-be`:
  0/1a/1b/1c/2/3a/3b/4a/4b/5/6a/6b/7a/7b/7c/7d/STAB/o1/o2.
- **CLI/build-vägen:** follow-up-kedjan (router → context → patch → apply →
  targeted render) + deterministisk + verifierModel-critic körs i build-vägen
  (#186). Längst fram.
- **Viewser-produktloopen:** ligger efter. `apps/viewser/app/api/prompt/route.ts`
  kör fortfarande bara `runPromptToProjectInput` → `runBuild`. Ingen
  `routerDecision`, ingen follow-up-kedja, ingen OpenClaw.
- **kor-5 repair:** mergat (#185) men *dormant* — aktiveras först när en
  rerender-callback injiceras.
- **Hostad körning:** `/api/prompt` ger `501` på Vercel; den lokala Python-kedjan
  saknar backend-runtime i den hostade vyn (eget spår, `hosted-sandbox-mvp`).

---

## Planen (prioriterad, fas för fas)

Varje fas = en eller flera dispatchbara agentuppgifter. Behåll builderprofilen
(`04-builder-profil.md`) och scope-baserade checks. **Princip: ingen ny LLM-slice
utan inkopplingsplan.**

> **Status 2026-06-05 (nattsession):** Fas 0 är **klar** — router/OpenClaw-sömmarna
> härdade i tre skivor på `jakob-be`: `d8ef7ea` (KÖR-6b-fallback i CLI-followup +
> RouterDecision cross-field-clamp), `bb94445` (reference-gating + action-bridge-label +
> validate_assignment-immutability + base_run_id→apply) och `d149f23` (#187 npm
> packageManager-check + EN-docstring, policy v2). Punkt 1–8 nedan + #187 npm-pin gjorda.
> **Kvar inom #187:** lockfile-check + hårt core-deps-krav (rör step-4/policy-schema).
> Full pytest + governance/rules_sync/term_coverage gröna. **Nästa: Fas 1.**

### Fas 0 — Härda router/OpenClaw-sömmarna (FÖRE wiring)

Latenta söm-fel verifierade i koden. De blockerar inget idag (OpenClaw Core är
read-only/dormant), men ska fixas innan de wiras så de inte börjar bete sig fel i
en användarväg. Rör i första hand
`packages/generation/orchestration/router/llm_fallback.py`,
`.../openclaw/core.py`, `.../openclaw/models.py`, `scripts/build_site.py` + tester.

1. `run_followup_chain` ska använda `classify_message_with_llm_fallback` när
   `OPENAI_API_KEY` finns — behåll no-key-paritet. (Idag används `classify_message`
   rakt av; fallbacken i `llm_fallback.py:226` är oanvänd i den vägen.)
2. Normalisera LLM-routerbeslut så att non-edit `messageKind` aldrig kan starta
   build/preview via `targeted_rebuild` (cross-field-validering: t.ex.
   `answer_only`/`component_discovery`/`site_review`/`unclear` → endast `none`).
3. `OpenClaw.orchestrate()` ska skicka `router.reference.url` vidare till
   `assemble_context(url=...)`, annars blir extern-referens-context tom.
4. `OpenClaw._multi_intent()` ska respektera `reference`/`risk="do_not_copy_exact"`/
   `plan_only` och inte gå till `patch_plan_request` när referensanalys krävs.
5. Byt stale `blockedBy="kor-7c"` i `PatchPlanRequest` (kor-7c/7d är mergade) →
   en sann etikett, t.ex. `action_bridge_missing` / `blockedBy="openclaw-action-bridge"`.
6. `OpenClawDecision`/`ToolCall` görs immutable / `validate_assignment`-säkra så
   `appliedVisibleEffect`/`requiresApproval` inte kan muteras efter konstruktion.
7. `run_followup_chain` ska skicka `base_run_id` vidare till `apply_patch_plan`
   (annars kan context läsas från en run men apply utgå från senaste version).
8. Regressionstester för alla ovan.

Plus **#187 platform-härdning** (separat liten slice innan UI-bibliotek): kolla
`package-lock.json` när den finns, kräv core-deps (`next`/`react`/`react-dom`) i
viewser + starters, validera npm-pin (`packageManager`/engines), översätt svenska
kod-kommentarer i `check_platform_baseline.py` till engelska. Möjliggör shadcn/lucide
kontrollerat.

**Checks:** `pytest` på rörda router/openclaw/followup-tester, `ruff` på rörda
moduler, `governance_validate` om policies/schemas rörs.

### Fas 1 — Gör heavy-flow verklig för användaren

> **Status 2026-06-06 (`main = 496d605`):** Delvis inne.
> - `routerDecision` är wirad i `/api/prompt` (#192) och OpenClaw-beslut visas
>   ärligt i FloatingChat (#199, **read-only** — `/api/prompt` rutar INTE
>   följdprompter genom `--apply` än).
> - OpenClaw action-bridge finns (`run_openclaw_followup.py --apply`, #196) och en
>   **visual_style-restyle materialiseras nu hela vägen genom apply-kedjan** (#207,
>   CLI-bevisat: `"ändra färgen till rosa"` → ny version med `brand.primaryColorHex`).
> - **Kvar i Fas 1 (största hävstången):** Christopher (apps/viewser-lane) wirar
>   `openclaw-runner --apply` + `/api/prompt`-routing + FloatingChat så heavy-flow
>   syns i UI:t. Backend-kontraktet `{decision, bridge}` är klart.
> - rerender-wiring (kor-5) landade i #195 (skiva 1c); kvar: buggranskningens
>   trust-blockerare #1 (stale preview efter repair) + #2 (patchad
>   `generation-package` sparas ej). Se `docs/handoff.md` (överst).

1. **Wira `routerDecision` + follow-up-kedjan i `/api/prompt`** så Viewser-UI:t får
   heavy-flow-vinsten. `/api/prompt` returnerar `routerDecision`; FloatingChat visar
   ärligt vad som hände (#177 slutar vara no-op). `shouldStartPreview` förblir
   **deterministiskt**, inte LLM-styrt. Ingen ny modellroll i denna slice.
2. **Rerender-wiring** så kor-5 repair blir verklig (injicera rerender-callback;
   post-repair-critic skrivs till trace före `critic.evaluated`; per-entry `success`
   blir `false`/ej-materialiserad när rerender failar).

### Fas 2 — Mät innan nästa stora investering

- **Baseline-eval:** 4 prompter genom riktig preview (vercel-sandbox). Avgör om det
  upplevda gapet är **copy/trust/kontakt** eller **visuellt/designsystem**. Detta
  styr Fas 3 — gissa inte.

### Fas 3 — Bygg på sanningen (villkorat av evalen)

- **Om visuellt:** design-system-ADR + `next-shadcn-tailwind`-starter (gated på #187).
- **Om copy/trust:** branschnära story/tagline/service-mallar
  (`prompt_to_project_input.py`) + trust/kontakt-ärlighet.
- **Steward (parallellt):** realign Backoffice "Follow-up Flow" → en Kontrollplan
  som visar `routerDecision`/OpenClaw-beslut/critic/`blueprintRepairs` och märker
  tydligt "CLI/build wired, Viewser ej fullt wired". (Se review-syntes nedan.)

### Fas 4 — Hosting (eget spår, ej blocker)

- Lös `/api/prompt 501` på Vercel: Python-kedjan behöver en riktig backend-runtime
  (sandbox/host) eller portas. Drivs på `hosted-sandbox-mvp`. Separat från Fas 1:s
  lokala wiring.

---

## Syntes av review-dokumenten (3 av 4)

Tre externa reviews + en bevisdump. Alla tre reviews pekar åt samma håll och är
konsekventa med repots egna guardrails. Stämde av deras kodpåståenden mot koden:
6 av 6 spot-checks stämde.

### A. Teknisk review (hård, 7,6/10)

- **Riktning:** rätt — deterministisk grund + LLM ovanpå; LLM som exekutor, inte
  arkitekt. OpenClaw som dirigent, inte ny motor.
- **Största gapet:** `/api/prompt` är inte wirad → användaren ser inte heavy-flow.
  (Bekräftat i kod + av 501-dumpen.)
- **Rekommenderad ordning:** post-merge-härdning → wira `routerDecision`/`/api/prompt`
  → #187 platform → steward realign → kor-4b/verifier (klar, #190) → rerender-wiring
  → baseline-eval. (Matchar Fas 0–3 ovan.)
- **Nyans (vår bedömning):** de 8 härdningspunkterna är *latenta söm-fel*, inte
  live-buggar, eftersom OpenClaw Core är dormant. Fixa före wiring — men de blockerar
  inget idag.

### B. Governance/Backoffice-review (operator-yta / "Kontrollplan")

- **Bygg inget nytt stort "Christoffer-lager" och ändra inte governance tungt.**
  Gör en smal konsolidering: Backoffice blir operator-/granskningsytan som **visar**
  och **förklarar** generatorns beslut, med ev. begränsad policy-edit.
- **Backoffice får visa** kedjorna category → target/active/fallback scaffold,
  scaffold → expected starter, default variant, requested capabilities,
  candidate dossiers, supportStatus, fallbackWarnings, operatorReviewRequired,
  per-run-trace wizard/brief/DiscoveryDecision → finalProjectInput.
- **Backoffice får INTE** automatiskt montera dossiers, promota variants, skapa nya
  scaffold-familjer eller skriva om gamla Project Inputs. Inte bli en andra generator.
- **OpenClaw = dispatcher, inte diktator.** Router = vad vill användaren; Discovery
  Resolver = scaffold/variant/starter/capabilities; Planning = validering;
  Model Roles = smala uppgifter; OpenClaw Core = vad systemet gör härnäst.
- **Minimal governance-ändring:** ev. ett kort `docs/operator-surfaces.md`,
  uppdatera naming-dictionary om nya begrepp införs, ADR bara om Backoffice ska få
  *skriva* policyfält. Börja med en read-only Scout/Steward-inventering av ytorna.

### C. Bevisdump (hosted)

- Inte en åsikt: `/api/prompt 501` + JS-init-fel på den hostade Vercel-vyn.
  Bekräftar hosting-gapet (Fas 4).

### Christopher/UI-lane-koordinering (det reviewerna kallar "uppdatera Christoffer")

UI-lanen (`christopher-ui`, `apps/viewser/**`) berörs av:
- `routerDecision` i `/api/prompt` (#177) — FloatingChat speglar beslutet ärligt.
- Backoffice/Kontrollplan-realign (visa router/OpenClaw/critic/repairs).
- #187 steg 4 (platform-pins i `apps/viewser/package.json`) — kräver operatörs-OK +
  inbox-notis till `christopher-ui` innan propagering.

---

## "Allt i synk" — checklista innan ny featureutveckling

- [ ] README-banner + det här dokumentet committat i `jakob-be`.
- [ ] `current-focus.md` pekar hit och speglar HEAD.
- [ ] `MIN_IDE/` raderad lokalt (gitignorerad, 0 trackade filer — ingen git-effekt).
- [ ] `referens/`-städ-PR öppnad/mergad (git rm + README/paths.py/repo-boundaries/
      doc-länkar rensade).
- [ ] Guards gröna: `governance_validate`, `rules_sync --check`,
      `check_term_coverage --strict`.
- [ ] (Operatörsbeslut) `jakob-be → main`-sync.

---

## Arkiveringsplan (smart, tidsstyrd)

**Princip:** arkivera (flytta till `docs/archive/`), radera inte design-historik.
Behåll en spec så länge det kvarvarande arbetet behöver den.

| Vad | Beslut | När |
|-----|--------|-----|
| Kör-korten i `docs/heavy-llm-flow/` (`kor-*.md` + 00–04 + README) | **Behåll nu.** De är spec-basen för Fas 0–2 (rerender-wiring ↔ kor-5; `/api/prompt`-wiring ↔ kor-6a/6b/7a–7d/o1/o2; härdning ↔ router/openclaw-doc). README-bannern märker dem redan som implementerade. | Arkivera hela `docs/heavy-llm-flow/` → `docs/archive/heavy-llm-flow-<datum>/` när Fas 0–2 (härdning + wiring + eval) är landade. |
| `references/raw/` (coach-transkript, icke-canonical) | Behåll — små, citeras som källa av README. | Med heavy-llm-flow-arkiveringen ovan. |
| `referens/` (135 trackade filer på GitHub) | **Städ-PR nu** (operatörsbeslut taget). Provenance (`preview-runtime/konversation.txt`) försvinner ur arbetsträdet men finns i git-historiken; doc-länkar uppdateras. | Nu. |
| `MIN_IDE/` (gitignorerad, operatörslokal) | Radera lokalt nu (operatörsbeslut taget). Ingen git-effekt; snapshot-doc gör dossier-inventeringen reproducerbar utan den. | Nu. |
| `openclaw-mvp/` (gitignorerad spike, 29 filer) | **Behåll.** Fortfarande referens för OpenClaw action-bridge-arbetet (Fas 0 punkt 5 + framtida wiring). | Arkivera/radera när OpenClaw-action-bridge är byggd. |
| `övrigt/` (gitignorerad, 30 filer scratch) | **Operatörsgranskning.** Innehåller egna anteckningar/zip:ar — agenten nukar inte detta. | Operatören rensar selektivt. |

---

## Snabb startprompt för nästa agent (Fas 0)

> Du är Builder för `Jakeminator123/sajtbyggaren` på `jakob-be`. Hela
> heavy-llm-flow-kör-sekvensen är implementerad — **bygg inga nya kör-kort.**
> Gör Fas 0-härdningen i `docs/heavy-llm-flow/post-build-plan.md` (de 8 router/
> OpenClaw-punkterna + #187 platform-härdning). En slice i taget, scope-baserade
> checks, behåll no-key-paritet, ingen ny modellroll. Leverera ändrade filer +
> tester + checks. Uppdatera `current-focus.md` efter merge.
