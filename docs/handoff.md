# Handoff – Sajtbyggaren

**Datum:** 2026-06-15 ~13:30 UTC+2 — synk-/städrunda: `main = jakob-be =
7ab65132` (#325 + #326 mergade). Model routing v13 prod-verifierad (real-key
gpt-5.5-smoke), build-context omladdad, ADR 0059 slice 1 (`pricing` synlig
`/priser`-route) landad. Nästa riktiga produktspår: route/nav-mutation V1 (ta
bort sida + nav + interna länkar). Detaljerad köplan:
[`docs/current-focus.md`](current-focus.md).

## PASS 2026-06-15 ~14:30 — ROUTE/NAV MUTATION V1 SLICE A IMPLEMENTERAD (AUKTORITATIVT BLOCK)

> **Detta är det ENDA auktoritativa blocket. Allt nedan är historik — verifiera
> alltid mot git/koden.**
>
> **Status:** Route/Nav Mutation V1 Slice A implementerad lokalt på
> `jakob-be` (EJ committad/mergad än — operatören beslutar commit/PR).
> route_remove går nu hela vägen följdprompt → ny version utan sidan/nav.
>
> **Vad som landade (Slice A, ADR 0060):**
> 1. Ny router-`EditKind` `route_remove` (+ router-decision-schema). `classify.py`
>    klassar "ta bort sidan X / radera X-sidan / ta bort Kontakt" som route_remove
>    FÖRE component_remove och resolverar best-effort routeId ur sid-etiketten;
>    "ta bort knappen"/"ta bort recensionerna" förblir component_remove.
> 2. Nytt direktiv `directives.disabledRoutes` i project-input-schemat — STICKY
>    (apply union:ar med basversionen, så en borttagen sida inte återuppstår vid
>    en senare orelaterad följdprompt).
> 3. Ny `route_editor`-roll (roles.py, status supported, skill
>    `skills/route-remove/SKILL.md`) — korsvaliderad mot action-registret.
> 4. Ny `packages/generation/followup/route_directives.py` (resolver: validerar
>    routeId mot DENNA sajts scaffold + required-vakten; refused-skäl för okänd/
>    obligatorisk sida). Scaffold-agnostisk (alla starters).
> 5. `apply_patch_plan(disabled_routes=...)` skriver `directives.disabledRoutes`
>    (sticky union). `run_followup_chain` steg 3e trådar resolvern + ärlig no-op
>    (`route_remove_unsupported`). `build()` filtrerar `activeRoutes = scaffold
>    defaultRoutes − disabledRoutes` i EN punkt (nav + write_pages + guards);
>    required-route droppas aldrig (defense-in-depth → `_pick_contact_route`
>    kraschar aldrig).
>
> **Grönt:** ruff 0; `verify_openclaw` 6/6; governance_validate (21)/rules_sync/
> term-coverage --strict; riktade sviter (router classify/schema, route_directives,
> openclaw roles/registry, wizard-route-emission, section_directives, patch_apply,
> followup chain restyle/unapplied, route_remove E2E, docs-freshness/hygiene).
> naming-dictionary bumpad till v42 (Disabled Route).
>
> **NÄSTA — Slice B (route/nav forts.):** ta bort `contact` (required) + CTA-
> retarget. Gör `_pick_contact_route` tolerant (None i st.f. SystemExit), retargeta
> varje kontakt-CTA till `mailto:`→`tel:`→utelämna ärligt, och lägg en Quality
> Gate-länkscan som failar på dinglande intern `href` mot disabled route.
> Resolvern har redan `allow_required`-sömmen. SCOUT-INVENTERING (read-only, denna
> session) av kontakt-CTA-/intern-länk-ytan: contact_path är EN chokepoint som
> trådas från `write_pages` → varje renderer; ~12 emissionsplatser; två fällor:
> (a) `_pick_contact_route` raise SystemExit, (b) `_route_href` avvisar
> mailto:/tel:. Hårdkodade icke-kontakt-länkar att vitlista i länkscanen: `/`,
> `/spel`, `/faq`, `/arbeten`. Detalj: se denna sessions scout-rapport.
>
> **Öppen fråga (operatör):** backoffice-yta för "editor-actions/mutationer"
> (route_remove m.fl.) skild från dossiers — liten separat följd, ej byggd.

## PASS 2026-06-15 ~13:30 — SYNK + PROD-VERIFIERING + PRICING-SLICE + ROUTE/NAV NÄSTA (HISTORIK)

> **Historik (var auktoritativt 2026-06-15 ~13:30; ersatt av Route/Nav-passet
> ovan). Verifiera alltid mot git/koden.**
>
> **Mandat:** operatören (Jakob) gav full agens + admin ("göra allt och ta oss
> vidare"). Git-mutationer mot `main` + `jakob-be` (commit/push/PR/`--admin`-
> merge) uttryckligen godkända. Arbetsbranchen är `jakob-be`.
>
> **Git nu:** `main = jakob-be = origin/main = origin/jakob-be = 7ab65132`,
> working tree rent. Sessionen mergade #325 (review-fixes #318/#322,
> directive_leak-kritiker, novel-intent + katalog-medvetet plan, model routing
> v13) och #326 (ADR 0059 slice 1 pricing + `.cursorignore`-chore) till `main`.
>
> **Vad sessionen levererade (komplett, så ingen tror det "bara var en pricing-grej"):**
> 1. #318 additiv-vakt (`6062928c`): två citat muterar aldrig befintlig copy.
> 2. #322-härdning (`d7dea188`): droppar directive-formade tjänste-kort +
>    engelska craft-termer via den delade signalen.
> 3. directive_leak-kritiker (`07ed6939`): `_looks_like_directive` lyft till en
>    delad signal (`packages/shared/directive_signal.py`) som BÅDE planning
>    (prevention) och quality_gate (detektion) delar — single source.
> 4. Novel-intent planeringssvar + katalog-medvetet plan i OpenClaw Core V0
>    `decide` (`9d749486`/`64800d12`): en okänd-men-tydlig ändring får ett
>    grundat, ärligt planeringssvar i stället för stum action_bridge_missing.
> 5. Model routing v13 (`d49d1ab8`): planning/router/verifier → gpt-5.5 (high),
>    rerank → gpt-5.4-mini, brief → medium; centralt i `llm-models.v1.json`.
>    Real-key-smoke körd: gpt-5.5 + gpt-5.4-mini + gpt-5.4 svarar OK mot
>    prod-nyckeln → prod-säker.
> 6. ADR 0059 slice 1 (`c1198e32`): `pricing` synlig `/priser`-route (samma
>    faq/team-mönster; grundat-innehåll-grind kräver ≥1 service, annars
>    mount-only). "lägg till en prissektion / priser / prislista" ger nu en
>    synlig ändring, inte bara mount.
> 7. Build-context-tarballen omladdad (stabil blob-URL + KV) från `7ab65132` →
>    hostad prod kör den nya Python-koden.
>
> **Grönt:** ruff (0), 154 riktade tester (section_directives/apply/render/
> route-emission), `verify_openclaw.py` 6/6, governance_validate (21 policies),
> rules_sync, check_term_coverage --strict.
>
> **Öppna PR (Christophers viewser-lane, EJ mergade):** #324 (UI/UX-putts) +
> #320 (bygg-progress). Kräver operatörens visuella browser-check; #324 bör
> retargetas mot `jakob-be` + baseras efter #320 (annars drift).
>
> **Nästa riktiga spår — route/nav-mutation V1 (coach + operatör 2026-06-15):**
> Glappet som gör flödet "mekaniskt": OpenClaw kan inte ens TA BORT en sida.
> "ta bort Kontakt" → `component_remove`/`action_bridge_missing`. Routern saknar
> `route_remove`/`page_remove`. Bygg minsta säkra kontraktet (INGEN fri filpatch):
> ny editKind `route_remove` i router-modell + schema; klassificera "ta bort
> sidan X / radera kontaktsidan / ta bort Kontakt ur menyn"; svensk label→route-
> map (Kontakt→contact `/kontakt`, Om oss→about `/om-oss`, Tjänster→services
> `/tjanster`); `directives.disabledRoutes` i Project Input; `activeRoutes =
> defaultRoutes − disabledRoutes` i write_pages/render_layout; nav byggd från
> activeRoutes (inte råa defaults); contact disabled → inga `href="/kontakt"`,
> CTA retargetas till mailto/tel om verklig data finns, annars utelämnas ärligt;
> route/link-scan mot aktiva routes (faila vid länk till disabled route).
> Acceptans: "ta bort sidan Om oss + länken i headern" / "ta bort Kontakt +
> länkar dit" → ny version utan sidan/nav/länkar; okänd sida → ärlig no-op.
> Läs: `router/models.py`, `router/classify.py`, `openclaw/core.py`,
> `build/renderers.py`, `build/render_helpers.py`, scaffold `routes.json`,
> `tests/test_builder_route_emission.py` + route/follow-up-tester.
>
> **Ärliga fynd att INTE missförstå:**
> - Tema "Casual Café → grått": INTE en `_TONE_COLOR_TOKENS`-breddning. Ett låst
>   paritetstest befäster att `tone` styr typografi, bara explicita färgord/hex
>   styr paletten (`cafe-bistro`/`varm` blir inte grått). Riktig fix =
>   variant-palett/-val (estetiskt, kräver operatörens riktning).
> - reviews/trust synlig render: `render_section_reviews` är en medveten stub
>   (returnerar ""); `render_section_trust_proof` ligger redan i `render_home`s
>   default-komposition. Båda är riktiga render-jobb, inte placement-rader (0059).
> - "OpenClaw ser inte filerna": by design — OpenClaw Core V0 `decide` är en REN
>   funktion (ingen disk-I/O/build/preview/shell/network). Selected-file-context
>   (läsa manifest/route-map/genererade filer) är coachens Nivå 2, ett medvetet
>   nästa lager — inte en bugg. Per-run-filträdet hostat är en separat B199-lucka
>   (Christophers lane, ej schemalagd).

## PASS 2026-06-14 ~22:00 — PROD-E2E BEVISAD + DIREKTIV-LÄCKAGE-FIX (KUNDKOPIAN) + DOCS-STÄDNING (HISTORIK)

> **Historik (var auktoritativt 2026-06-14; ersatt av 2026-06-15-passet ovan).**
>
> **Mandat:** operatören (Jakob) gav full mandat att avsluta och skeppa denna
> session: validera kärnloopen live på hostad prod, fixa den observerade
> "Om oss"-buggen, städa docs och leverera via en riktig PR mot `main` med
> efterföljande synk av alla fyra referenser. Git-mutationer (commit/push/PR/
> merge mot `main` + `jakob-be`) är uttryckligen godkända.
>
> **Git:** alla fyra referenserna stod på `41a24d77` (#319 B204) vid rundans
> start. Denna runda levererar via PR `fix/directive-copy-leak` → `main`
> (squash), varefter `jakob-be` ff-synkas så att
> `main = jakob-be = origin/main = origin/jakob-be`. Production deployar från
> `main`.
>
> **1. Kärnloopen live-validerad på hostad prod** (https://sajtbyggaren-viewser.vercel.app):
> tre nyligen mergade ändringar bekräftades landa hostat — #316 (restyle/
> omfärgning via tema-utföraren), #318 (citerad "Om oss"-copy syns ärligt) och
> B204 (#319, UTF-8-säker prompt/meddelande-transport över viewser→CLI-
> gränsen, dvs. svenska tecken transporteras rätt). Hostad prod-E2E (Vercel
> Sandbox-bygge + preview) är därmed bevisad end-to-end, inte bara lokalt.
>
> **2. Preview-arkitekturen klargjord (inget felkonfigurerat):**
> `*.vercel.app` = den långlivade Viewser-appen (operatörs-UI:t på `/studio`).
> `*.vercel.run` = den efemära per-bygge-previewen i Vercel Sandbox, som
> **mintas om vid varje bygge** och bäddas in i `/studio` via en cross-origin-
> iframe. Att preview-URL:en byts per bygge och ligger på en annan origin är
> alltså by design, inte en bugg.
>
> **3. Vercel-env konsekvent:** `VIEWSER_SANDBOX_REUSE` är nu satt (`=1`) på
> Production, Preview **och** Development. Preview-värdet lades 2026-06-14 via
> Vercel REST API eftersom CLI:n loopar på `git_branch_required` för
> alla-Preview-grenar-vägen. Kvarstående (Vercel-sidan, INGEN repo-ändring):
> Production lagrar varianten som `sensitive` medan Dev/Preview är `encrypted`
> — värdena matchar, så `vercel env pull production` visar bara raden blank.
> Se ADR `governance/decisions/0055-hostad-preview-standardisering.md`
> (daterad uppdatering) + de tidigare ADR-blocken nedan (nu med
> "Uppdatering 2026-06-14"-noteringar; de gamla "lämna osatt"-domarna är
> inaktuella).
>
> **4. Direktiv-läckage-fix för kundkopian ("Om oss"-buggen) — denna PR:** den
> riktiga `briefModel` filade ibland META/INSTRUKTIONSTEXT i positioning-/
> contentStrategy-fälten i stället för kundfärdig vinkel-copy (live på en café-
> brief: `localAngle` = "Göteborg ... bör synas tydligt i copy och
> kontaktsektion", `differentiator` = "Lyft Kafé Solrosen som ..."). Den texten
> renderades sedan ordagrant som synlig "Om oss"-text och hero-copy. Fixen är
> en deterministisk, hög-precisions-grind `_looks_like_directive` i
> `packages/generation/planning/blueprint.py` som DROPPAR direktiv-formade
> strängar (tre signaler: craft-/meta-term som "kontaktsektion"/"subheadline",
> imperativt ledverb som "Lyft"/"Framhäv", eller "`<modal>` ... `<copy-craft-
> verb>`"-konstruktion) ur kandidaterna till hero/story/FAQ — den skriver
> aldrig om och hittar aldrig på (samma ärlighet-genom-konstruktion som
> `_drop_offer_tagline_services` och offerStrategy-undantaget i `derive_story`).
> De fyra deterministiska mock-baslinjerna är byte-identiska (grinden är no-op
> på den ärliga vägen). `packages/generation/brief/extract.py` får dessutom en
> system-instruktion till `briefModel` att skriva dessa fält som färdig,
> visningsbar copy — aldrig som en instruktion om copyn. Lås: 6 nya tester i
> `tests/test_planning_blueprint.py`. Riktad svit grön (35 passed, 1 E2E
> skip), `ruff check .` = 0.
>
> **5. Docs-städning:** inaktuella Preview-påståenden i denna fil korrigerade
> (de gamla "`VIEWSER_SANDBOX_REUSE` disk-only/lämna osatt"-domarna är märkta
> som inaktuella) och en daterad uppdatering tillagd i ADR 0055.
>
> **Resulterande läge:** PR `fix/directive-copy-leak` squash-mergad till
> `main`, `jakob-be` ff-synkad, alla fyra referenserna identiska, rent träd.
> Hostad prod är bevisat fungerande för kärnloopen; nästa hostade bygge kör
> direktiv-fixen så fort build-context-tarballen speglar den nya `main`-tippen
> (`node apps/viewser/scripts/upload-build-context-to-blob.mjs` — fixen rörde
> `packages/generation/`, inte `apps/viewser`-frontend, så ingen ny Vercel-
> frontend-deploy behövs).
>
> **Rekommenderade nästa steg (prioriterat, ärlig bedömning):**
>
> 1. **(c) `directive_leak`-check i `packages/generation/quality_gate/critic.py`
>    (snabb kvalitetsvinst, hög prio):** lyft samma signal som
>    `_looks_like_directive` till en Quality Gate-kritiker så att direktivtext
>    som ändå slinker igenom (eller dyker upp i en ny copy-väg) fångas och
>    rapporteras i stället för att tyst renderas. Försvar på djupet ovanpå
>    denna PR; litet och välavgränsat.
> 2. **(a) Fritext övertolkas till påhittade "service"-kort (snabb–medel
>    kvalitetsvinst, hög prio):** fri prompttext blir ibland stray
>    tjänste-kort som kunden aldrig bett om. Samma ärlighets-tema som denna
>    fix (hellre utelämna än hitta på); avgränsa till grundade tjänster.
> 3. **(b) Tema-trohet — "Casual Café" renderas grått (medel, kundnära):**
>    #316 landade omfärgning via tema-utföraren, men en namngiven tema-cue som
>    "Casual Café" mappar i dag till grått. Höj tema-mappningens täckning så
>    den valda stämningen syns. Kundnära fidelity-glapp.
> 4. **(e) B197 — hostad discovery-paritet (medelstort roadmap-steg, nu
>    UPPLÅST):** den hostade byggvägen trådar bara prompttext, inte wizardens
>    strukturerade discovery-payload. Hölls tidigare tills prod-E2E var grön —
>    det är den nu, så detta är nästa substantiella byggsteg. Koordinera med
>    Christophers spår (`hosted-build-runner.ts`, msg-0085).
> 5. **(e) Konduktör "Steg 1" — montera katalog-komponenter (större roadmap-
>    program, M):** låt `component_builder` gå partial→supported mount för
>    komponenter som redan finns i katalogen/capability-map (samma apply/mount-
>    maskineri som FAQ/contact-form), ärligt mot #313. Kräver ADR-utökning av
>    0057. Underlag: `docs/heavy-llm-flow/conductor-vision-roadmap.md`.
> 6. **(d) Normalisera `VIEWSER_SANDBOX_REUSE`-typ på Vercel
>    (`sensitive`→`encrypted`) (trivialt, lägst prio):** rent kosmetiskt
>    Vercel-sidan; värdena matchar redan och funktionen påverkas inte. Gör
>    opportunistiskt.

## PASS 2026-06-14 ~17:00 — TAKEOVER-PREP: #316 NOTERAD, DAGENS LEVERANSER #310–#316, KONDUKTÖR-ROADMAP (HISTORIK)

> **Historik (ersatt av 22:00-blocket ovan).** Verifiera alltid mot git/koden.
>
> **Mandat:** operatören (Jakob) gav full mandat för en takeover-prep-runda:
> verifiera git/PR-läget, hantera ev. öppen PR, och skriv en färsk handoff +
> current-focus så en annan agent kan ta över exakt där vi står. Blockera bara
> vid verkliga fel.
>
> **Git:** `main = jakob-be = origin/main = origin/jakob-be = 8005be92`
> (#316 färgfixen, rent träd) vid rundans start. Denna runda lägger EN
> docs-commit ovanpå på `jakob-be` och ff-synkar `main` till samma tip
> (samma mönster som föregående docs-runda). Production deployar från `main`.
> Ingen PR mergades denna runda.
>
> **#316 (`8005be92`) — internt "Spår A", OBS skilt från uppgift A/#310:**
> #316 är färgfixen (internt "Spår A"), inte dossier-deps (uppgift A/#310). En
> restyle-följdprompt ("gör sajten blå", "snyggare typsnitt") var tidigare en
> tyst no-op och landar nu via tema-utföraren: `run_followup_chain` fick en
> stylist-LLM-fallback bakom en delad eligibilitetsgrind
> (`theme_directive_llm_eligible`, identisk för legacy-prompt-vägen
> `prompt_to_project_input` och OpenClaw-kedjan — ett lockstep-test låser
> identiteten). Den deterministiska färg-/font-extraktorn
> (`packages/generation/followup/theme_directives.py`) är primär; stylist-
> modellen konsulteras bara när extraktorn missar OCH prompten bär en visuell/
> stil-cue, och varje returnerat fält re-valideras (hex måste vara hex, vibe en
> känd nyckel). Sätter bara `brand.primaryColorHex`/`brand.accentColorHex` +
> `tone.primary` (redan i schemat, ingen ny render-väg). Svaret bär en ärlig
> `visual_style`-target-summary (inte contentBlocks-mislabel), och "effekter"/
> animationer förblir ärligt oapplicerat. Rörde
> `packages/generation/followup/` + `scripts/` + tester, INTE
> `apps/viewser`-frontend.
>
> **Dagens leveranser (alla mergade till `jakob-be` + `main`, tip `8005be92`):**
>
> 1. **#310 (uppgift A) — dossier-dependencies (ADR 0056):** dossierer
>    deklarerar pinnade npm-paket som buildern bakar in i genererad
>    `package.json` (npm ci → install-fallback).
> 2. **#311 — projektinnehåll/composition-panel:** site-composition-API +
>    panel i ConsoleDrawer som visar sidor/dossiers/komponenter/paket ur
>    befintliga run-artefakter (lokalt + hostat).
> 3. **#312 (uppgift E) — komponentintag v1:** kurerad shadcn-intake-CLI
>    (`scripts/component_intake.py`, ADR 0054), `component_builder`-
>    rollkontrakt (ADR 0057, partial/mount-only), zero-dep accordion-pilot,
>    naming v40, pip-dep `openai-agents==0.17.5`.
> 4. **#313 (uppgift D+F) — ärlighetsfix:** `appliedFollowupDirectiveKinds`-
>    signal + `intent_not_executable` (byte-diff bevisar inte längre framgång),
>    honesty-gates kräver konkreta direktiv, `generateFollowupOutcomeSummary`
>    (ärlig LLM-`answerText` på följdprompter).
> 5. **#314 (uppgift G, ADR 0058) — snabb chat + preview-bundle:** answer-only
>    utan sandbox för rena frågor (`apps/viewser/lib/hosted-answer-only.ts`,
>    kortslutning före `startHostedBuild`) + preview-bundle-tarball
>    (`source=preview-bundle`, ärlig fil-för-fil-fallback). Stänger B200/B201.
> 6. **#315 (uppgift H) — restpost-svep:** dedikerad `intent_not_executable`-
>    rad (no-key, ärlig "saknar byggförmåga") + rolletiketten
>    `component_builder` → "komponenter".
> 7. **#316 (internt "Spår A", `8005be92`) — färgfixen:** se blocket ovan.
>
> **Kö framåt (prioriterad):**
>
> 1. **Operatörens prod-E2E på `main`** (Jakobs nästa steg — agenter ska INTE
>    förekomma testet): konkret restyle ("gör sajten blå") ska byta färg
>    hostat; ren fråga svarar utan sandbox; andra previewn använder
>    `source=preview-bundle` (lågt `sourceMs`); no-op ger ärlig rad (ingen
>    falsk "Klart!"). #316 rörde inte `apps/viewser`-frontend → ingen ny
>    Vercel-frontend-deploy skapas; produktändringen når den hostade pipen via
>    build-context-tarballen (se nästa stycke).
> 2. **B197 — discovery-paritet hostat** (HÅLLS tills prod-E2E grön): den
>    hostade byggvägen trådar bara prompttext, inte wizardens strukturerade
>    discovery-payload. Nästa byggsteg ("uppgift I"). Koordinera med
>    Christophers spår (msg-0085 begärde tidig rebase på
>    `hosted-build-runner.ts`).
> 3. **Steg 1 mot konduktör-visionen (rekommenderad första byggskiva, M):**
>    låt `component_builder` gå partial→supported mount för komponenter som
>    redan finns i katalogen/capability-map (samma apply/mount-maskineri som
>    faq/contact-form), ärligt mot #313. Kräver ADR-utökning av 0057. Underlag:
>    `docs/heavy-llm-flow/conductor-vision-roadmap.md`.
>
> **Build-context-tarballen + #316 (viktig verifieringspunkt):** #316 rörde
> `packages/generation/` + `scripts/`, så den hostade sandbox-byggvägen kör
> #316:s kod FÖRST när build-context-tarballen laddats om
> (`node apps/viewser/scripts/upload-build-context-to-blob.mjs`). Föregående
> docs-commit (`a58b3276`) ligger FÖRE #316, så ingen omladdning är bokförd
> efter `8005be92`. Bekräfta att blob-tarballen speglar `8005be92` innan den
> hostade restyle-E2E:n litas på; ladda annars om. (#316 rörde inte frontend,
> så ingen Vercel-frontend-deploy behövs.)
>
> **Konduktör-roadmap (operatörens vision, read-only underlag):** en roadmap
> togs fram denna session för visionen fri kreativ prompt → analys → npm →
> generativ komponent → montering → ny version (t.ex. "3D-pizza ovanför
> headern"). Slutsats: visionen är arkitekturellt förankrad (openclaw-2.0-
> conductor, fas 3 = extern Docker-konduktor) men ej byggd. Dagens konduktor är
> en ärlig regelbaserad router till fyra begränsade roller (router/
> section_builder/stylist/copy) + en partial `component_builder`; en
> pizza-prompt dör i `classify_message` som unclear, eller senare som
> plan_rejected / apply_unmapped. Stegtrappa: Steg 1 katalog-mount (M) →
> Steg 2 kuraterat 3D-recept (L) → Steg 3 novel-intent planeringssvar (M) →
> Steg 4 prompt→dossier-inferens (L) → Steg 5 generativ komponent-agent (XL) →
> Steg 6 extern Docker-konduktor (L). Full pizza-vision = arkitekturprogram
> (månader). Kärnpunkter + stegtrappa:
> `docs/heavy-llm-flow/conductor-vision-roadmap.md`.
>
> **Modell-/budget-läge (beslutsunderlag för takeover-agenten):** motor-
> rollerna (`briefModel`/`planningModel`/`routerModel`/`copyDirectiveModel`/
> `styleDirectiveModel`/`codegenModel` m.fl.) kör alla `gpt-5.4` i
> `governance/policies/llm-models.v1.json`; Viewser-chatten kör `gpt-5.5` via
> `.env` (`OPENAI_MODEL`) och följer inte policyn. reasoningEffort per roll:
> planning=medium, copy=low, router=low, brief=low, style=none, codegen=medium;
> maxOutputTokens varierar (brief/plan 6000, övriga 2000–4000; chatt 1500).
> Öppen operatörsfråga (ej beslutad): höja reasoning på copy+router (+ev.
> planning) och/eller byta motorn till `gpt-5.5`. Backoffice kan byta modell
> per roll (Dirigentpulten) + hela policyn via governance-JSON-editorn;
> kontextbudgetar (tecken-tak i `budgets.py`) kräver kodändring; chattmodellen
> styrs via `.env`.
>
> **Kända punkter bokförda i `docs/known-issues.md` (B202/B203, fixa EJ nu):**
> B202 (låg) — Turbopack output-file-tracing över-inkluderar för
> `/api/discovery-options` ("traced the whole project unintentionally"):
> `next.config.ts` breddar `outputFileTracingRoot` till repo-roten + routens
> runtime-`fs`-läsningar (dynamisk `repoRoot()` + `readdir` över
> scaffold-varianter) gör att tracern inte kan avgränsas → uppblåst
> funktionsbunt/kallstart. B203 (låg) — runtime-varning
> `webpsave_buffer: no property named 'smart_deblock'` (sharp/libvips-
> versionsglapp i bild-/webp-vägen), kosmetiskt.
>
> **Öppen PR — #317 (draft, MERGAD EJ av agent):** auto-genererad Cloud Agent
> env-setup-PR (Jakeminator123 + cursoragent), bas `main`, head
> `cursor/setup-dev-environment-3a91`. Enda kodändring: 6 rader in / 3 rader ut
> i `AGENTS.md` som dokumenterar att `sudo apt-get update` måste köras före
> venv-paketet på en färsk VM. CI helt grön (governance/eval-baseline/
> builder-smoke/ai-bug-review/GitGuardian/Vercel) och mergeable. Avstod ändå
> för att den är (a) en draft, (b) siktar `main` direkt förbi `jakob-be`, och
> (c) inte hör till #310–#316-tåget. Operatören beslutar: markera ready + välj
> bas (sannolikt `jakob-be`) om innehållet ska in — ändringen i sak är ofarlig
> och korrekt.

## PASS 2026-06-12 ~18:45 — KVÄLLSRUNDA: #314 + #315 MERGADE, SLUTLIG MAIN-SYNC (HISTORIK)

> Historiskt block (ersatt av takeover-prep-rundan ovan) — verifiera alltid
> mot git/koden.
>
> **Mandat:** operatören (Jakob) gav före frånvaro fullt mandat för
> kvällsrundan: merge av #315 efter granskning, docs-avslutning och den
> slutliga `jakob-be` → `main`-synken.
>
> **Kvällens två mergar (squash till `jakob-be`):**
>
> 1. **#314 — uppgift G (`de04e8f6`, stänger B200/B201, ADR 0058):**
>    - **G1 hostad answer-only:** en följdprompt som pre-klassificeras som
>      ren fråga med hög konfidens besvaras på sekunder, grundat i sajtens
>      hostade kontext (composition + site-brief via KV/blob) — ingen
>      sandbox spinner upp. Kortslutningen ligger FÖRE `startHostedBuild`;
>      alla felvägar/no-key/låg konfidens tar byggvägen som förr.
>      Modul: `apps/viewser/lib/hosted-answer-only.ts`.
>    - **G2 preview-bundle-tarball:** bygget paketerar det publicerade
>      fil-setet som EN tarball i blob; preview-sandboxen skapas direkt
>      från tarballen (inga per-fil-fetchar). Pekaren
>      `viewser:site:<siteId>:current` bär `previewBundleUrl` m.fl. additivt;
>      ärlig fil-för-fil-fallback för sajter byggda före G2, död blob eller
>      för stor tarball. `sourceMs` + `source`
>      (`preview-bundle`|`blob-files`|`disk`) i loggraden
>      `sandbox-preview-start` är verifieringen. Naming v41.
>    - **Tarball-omladdningen efter #314 är GJORD** (#314 rörde
>      `scripts/check_term_coverage.py` + `governance/`): blob-uploadedAt
>      17:51:48 UTC+2, 27 s efter mergen — build-kontexten speglar
>      `de04e8f6`.
> 2. **#315 — uppgift H, restpost-svep (`54de9b9c`):** två deferred-poster
>    från #312/#313:
>    - Dedikerad deterministisk gren i `summarizeBuildResult` för
>      `effect.reason === "intent_not_executable"` (no-key-/LLM-timeout-
>      fallbacken): ärlig svensk rad om att önskemålet inte kunde kopplas
>      till någon känd byggförmåga — aldrig "ange exakt rubrik/text"-rådet.
>      Variant "info", unapplied-svansen kvar, `honestAnswer` från #313
>      vinner fortsatt. Lås:
>      `test_floating_chat_dedicated_intent_not_executable_row`.
>    - `CONVERSATION_ROLE_LABELS` får `component_builder` → "komponenter"
>      (ADR 0057; stavning speglar `roles.py`/`action-registry.json`).
>    - **CI-rundan krävde en hygientak-split:** PR:ens +46 testrader
>      tippade `test_viewser_floating_chat.py` till 1221 rader (tak 1200 i
>      `test_test_hygiene.py`). Copy-directive-/change-set-låsen (9 tester,
>      oförändrat innehåll) flyttades till nya
>      `tests/test_viewser_copy_change_set.py` — samma mönster som
>      `test_viewser_builder_dialogs.py`/`test_viewser_openclaw_slice3.py`.
>      Ingen tarball-omladdning för #315 (endast `apps/viewser/` +
>      `tests/`). Röktest efter merge: 62 riktade tester gröna
>      (floating-chat/b155-låsen, copy-change-set, openclaw slice 3,
>      hosted-followup-parity, hygien).
>
> **Git-läget:** `jakob-be` == `main` efter denna rundas slutsynk (ff-only).
> Production deployar från `main`. Inga öppna PR mot `jakob-be`.
>
> **NÄSTA steg är operatörens produktions-E2E på `main`** (görs separat av
> operatören, inte av agenter). Konkreta verifieringspunkter:
>
> 1. **Ren fråga i chatten** (t.ex. "Vad tycker du om sajten?") ska svara
>    på sekunder UTAN att en sandbox spinner upp (G1; loggraden
>    `hosted-answer-only-preclassified`).
> 2. **Första hostade bygget efter merge skapar första preview-bundlen** —
>    andra previewn därefter ska starta på sekunder. Kolla `sourceMs` +
>    `source=preview-bundle` i runtime-loggarna. Äldre sajter (byggda före
>    G2) tar fil-för-fil-fallbacken tills de byggs om — väntat, inte fel.
> 3. **No-op-följdprompt** ska ge ärlig no-op-rad (info), aldrig grön
>    "Klart!" (#313/#315-beteendet, inkl. den nya
>    intent_not_executable-raden utan nyckel).
>
> Därefter är **uppgift I** nästa byggsteg i kön: **B197 discovery-paritet
> hostat** — idag skickas endast prompttexten in i sandboxen;
> discovery-svar/konversationskontext trådas inte. (Koordinera med
> Christophers spår — msg-0085 begärde tidig rebase,
> `hosted-build-runner.ts` är ändrad IGEN av #314.)
>
> **Backlog/deferred (ej blockers):** dossierfälten componentSource/
> mountRules/qualityGate från E (kräver design/ADR först — ej entydigt
> specade i ADR 0054/0057, medvetet HOPPADE i #315); targeted-apply-
> trådning av `appliedFollowupDirectiveKinds` (ej gjord enligt direktiv);
> blob-prune-skulden + G2:s dubbellagring av källan per bygge (per-fil +
> bundle) tills bundle-vägen är prod-bevisad (ADR 0058); G1:s medvetna
> klassificeringslatens (~1–3 s, 8 s tak) på byggvägen; `changeSet` hostat;
> Preview-miljöns reuse-flagga; Safari/Firefox-E2E för B125.

## PASS 2026-06-12 ~16:00 — AVSLUTNINGSRUNDA: DAGENS MERGAR + MAIN-SYNC FÖR PRODUKTIONSTEST (HISTORIK)

> Historiskt block (ersatt av kvällsrundan ovan) — verifiera alltid mot
> git/koden.
>
> **Mandat:** operatören (Jakob) gav före frånvaro mandat för hela
> avslutningsrundan: städning av worktrees/branches, dokumentstädning,
> handoff/focus-uppdatering och `jakob-be` → `main`-sync.
>
> **Dagens fyra eftermiddagsmergar (squash till `jakob-be`):**
>
> 1. **#310 — ADR 0056 dossier-dependencies:** dossierer deklarerar pinnade
>    npm-paket som buildern bakar in i genererad `package.json`
>    (npm ci → install-fallback).
> 2. **#311 — Projektinnehåll-panelen (`f642b1a5`):** site-composition-API
>    (`GET /api/site/[siteId]/composition`) + panel i ConsoleDrawer som
>    visar sidor/dossiers/komponenter/paket ur befintliga run-artefakter.
> 3. **#312 — uppgift E, komponentintag v1 (`0fe94617`):** kurerad
>    shadcn-intake-CLI (`scripts/component_intake.py`, ADR 0054),
>    component_builder-rollkontrakt (ADR 0057), zero-dep accordion-pilot
>    synlig på FAQ, naming v40, repo-boundaries v13, pip-dep
>    `openai-agents==0.17.5`.
> 4. **#313 — del F+D ärlighetsfix (`56dc754f`):**
>    `appliedFollowupDirectiveKinds`-signal + `intent_not_executable`
>    (byte-diff kan inte längre bevisa framgång), ärlig okänd-slug i
>    `unappliedFollowupIntents`, honesty-gates kräver konkreta direktiv,
>    `generateFollowupOutcomeSummary` ger ärlig LLM-svarsrad på varje
>    följdprompt. B155-slicen dokumenterad i known-issues.
>
> Tidigare under dagen (se historikblocken nedan): B199 v2 hostad parity,
> ADR 0055 preview-standardisering, tre hotfixar (parallella
> blob-downloads, ärlig submit-gate i FloatingChat, fail-open
> `ignoreCommand`). Build-context-tarballen är omladdad till blob efter
> #313 (`56dc754f`).
>
> **Städat i denna runda:** lokala branchen `feat/project-composition`
> (mergad som #311) borttagen; elva remote-branches för mergade/stängda
> PRs + verifierade dubbletter borttagna (bl.a. fyra cloud-sessionsbranches
> för #309/#310/#312/#313, dubbletterna `cloud/komponentintag-v1` =
> #312-head och `feat/hosted-followup-parity` = #307-head, samt fyra
> stängda PR-branches #156/#158/#177/#281). Inga överblivna worktrees
> fanns. known-issues: B195 flyttad till Stängda (#287 mergad 2026-06-11),
> B155 fick #313-slicen. B197 (discovery-paritet hostat) är FORTSATT öppen
> — den hostade byggvägen skickar fortfarande bara `PROMPT_TEXT`.
>
> **NÄSTA steg är operatörens produktions-E2E på `main`** (görs separat av
> operatören, inte av agenter): hela `/studio`-flödet i produktion med
> dagens mergar. Därefter är **uppgift G** nästa byggsteg i kön: snabb chat
> utan sandbox-spinn för rena frågor + tarball-bundling för förbyggda
> previews.
>
> **Backlog/deferred (ej blockers):** componentSource/mountRules/
> qualityGate-dossierfälten från E; viewser-rolletikett för
> component_builder; deterministisk intent_not_executable-rad för
> no-key-fallet (F+D); B197; blob-/KV-prune; `changeSet` hostat;
> Preview-miljöns reuse-flagga; Safari/Firefox-E2E för B125.

## PASS 2026-06-12 ~12:00 — HOSTAD PREVIEW-STANDARDISERING: ADR 0055 (HISTORIK)

> Historiskt block (ersatt av avslutningsrundan ovan) — verifiera alltid
> mot git/koden.

**Tillägg ~12:45:** PR #308 (docs(heavy-llm-flow) ärlighetspass mot verifierad
kod) squash-mergad till `jakob-be` + ff till `main` efter rebase och fyra
review-fixar (arkivets local-next-rad, readiness-frontmatter historisk,
känt-gap-förbehåll i README + kor-o1-noten; vinkelparentes-platshållarna
visade sig redan vara intakta i råfilerna). Docs-only — Vercel avbryter
prod-rebuild via ignoreCommand, väntat.

**Tillägg ~13:30 (hotfix-pass):** prod-E2E-incidentutredningen 2026-06-12
ledde till tre fixar direkt på `jakob-be` + ff `main` (operatörsmandat):
(1) `collectSourceFromBlob` laddar nu blob-filerna med begränsad samtidighet
(16 parallella via nya `downloadBlobEntries`; MAX_FILES-/byte-vakter och
fel-semantik bevarade, enhetstester utökade i `generated-blob-source.test.ts`)
— den seriella en-fetch-per-fil-loopen var rotorsaken till långsam hostad
preview-POST; (2) FloatingChat:s submit-vakter är inte längre tysta:
`console.warn` per vakt, statusrads-hint "Vänta — ett bygge/svar pågår
redan." vid upptagen, ärligt fel i chatten vid saknad siteId (vakterna
oförändrade i styrka, summarizeBuildResult-regionen orörd); (3) lyckad
sandbox-preview-start loggar EN server-side JSON-rad (fas-timings + siteId +
prebuilt/reused) via chokepoint-wrapper i `vercel-sandbox-runner.ts` —
runtime-loggarna kan nu besvara "var tog tiden vägen" utan klient.
Uppföljning i samma pass: första prod-deployen av hotfixen ERRORade i
`ignoreCommand` ("fatal: bad object" — `VERCEL_GIT_PREVIOUS_SHA` pekade på en
deploy ~12 commits bak som saknades i Vercels grunda klon, och exit 128 ≠
0/1 fäller hela deployen). `apps/viewser/vercel.json` är nu fail-open:
`git cat-file -e "$BASE" || exit 1` före diffen, så saknad bas → bygg i
stället för ERROR (verifierat i riktig bash).

**Tillägg ~14:10:** PR #311 (feat(viewser) Projektinnehåll-panel) squash-
mergad till `jakob-be` (`f642b1a5`) + ff till `main`. Ny panel i
konsol-lådan på `/studio` (ConsoleDrawer, mellan run-väljaren och
RunDetailsPanel) som visar vad sajt-projektet består av: sidor (routes),
funktioner (dossiers), monterade komponenter och npm-paket — med
dossier-tillagda paket (ADR 0056) som egen kategori. Deriveras via
`GET /api/site/[siteId]/composition` ur befintliga run-artefakter (lokalt
disk, hostat B199-kedjan), ingen ny lagring. Tarball-omladdning gjord
direkt efter mergen (#311 rörde `scripts/check_term_coverage.py`).

> **Mandat:** operatörsbeslut (Jakob, bekräftat 2026-06-12 ~11:00): Vercel
> Sandbox + Blob ska vara standardlösningen för previews av användarsajter,
> streamade in i Viewser-iframen genom OpenClaw-flödet. StackBlitz-adaptern
> AVVECKLAS INTE — pausad (ADR 0033), orörd. B197/discovery är fortsatt
> Christophers — `hosted-build-runner.ts` + `vercel-sandbox-runner.ts` är
> ändrade IGEN, tidig rebase begärd (msg-0085).
>
> **Vad som landade (commit-kedja på jakob-be → main, i stegordning):**
>
> 1. **Docs-sanering** (`6fe80cb3`): B194-/run-historik-texterna rättade i
>    deploy-guiden, prompt-routens JSDoc, `.env.example`,
>    `preview-runtime.md` (+ färsk last_verified_commit) och en
>    rättelsenot i ADR 0033 (SDK:n bor i app-lagret, parentes-tillåtet).
> 2. **Preview-refresh-gate** (`890afba9`): lyckad follow-up utan synlig
>    effekt (visibleEffect `none`/`registered` per FollowupVisibleEffect-
>    semantiken) river INTE preview-sandboxen. Mekanism: separat
>    `previewRunId`-state i studio-sidan driver ViewerPanel;
>    `selectedRunId` (historik/builder) flyttas alltid. FloatingChat trådar
>    signalen som tredje `onBuildDone`-arg via EXPORTERADE
>    `readFollowupVisibleEffect` (delad med dialogerna). Osäker/saknad
>    signal = refresh. Init-byggen oförändrade. Lås:
>    `tests/test_viewser_preview_refresh_gate.py` (7 st). Dessutom
>    `2236621c`: pre-existerande eslint-fel i `industry-search.tsx` lagat
>    (microtask-defer, react-hooks/set-state-in-effect).
> 3. **byggstart stoppar previewn** (`8b1573fe`): `startHostedBuild`
>    anropar `stopSandboxSessionForSite` efter preflights, före
>    `Sandbox.create` — best-effort i try/catch, kan aldrig falla bygget.
>    Paritet med lokala `build-runner.ts`. Primärmekanismen i
>    livscykelvalet (se punkt 6).
> 4. **Pre-built hostat** (`d6cd2c74`, ADR 0055 §1): orkestrerings-skriptets
>    find-upload inkluderar rot-`.next/` minus `cache`/`trace` (+ nästlade
>    `.next` prunas som förr; find-uttrycket verifierat i riktig bash).
>    `generated-blob-source.ts` fick `filterPrebuiltRelPaths` +
>    `hasPrebuiltNextRelPath` (BUILD_ID-kontraktet); runnern tar
>    pre-built-grenen (`npm install --omit=dev` + `next start`) när
>    blob-källan bär komplett `.next`, ärlig en-gångs-fallback annars —
>    fallbacken laddar inte ner `.next` alls. Storleksvakterna (4000/64MB)
>    MEDVETET kvar = disk-vägens (dokumenterat i koden).
> 5. **Default-flippen** (`3515bf59`): tomt/osatt `VIEWSER_PREVIEW_MODE` →
>    `vercel-sandbox` i `registry.currentKind`, policy v4
>    (`default: vercel-sandbox`), `next.config.ts`, `dev.mjs`
>    (DEFAULT_MODE), viewer-panel-descriptorn. `.env.example`-mallen sätter
>    `local-next` EXPLICIT (lokala utvecklar-rekommendationen). OBS
>    AVVIKELSE från uppdragspremissen: Jakobs `apps/viewser/.env.local`
>    hade redan EXPLICIT `vercel-sandbox` (inte local-next som uppdraget
>    antog) — den lämnades ORÖRD (flippen ändrar inget för honom; att
>    skriva local-next hade ÄNDRAT hans nuvarande beteende). Lås
>    uppdaterade: cross-policy (default==vercel-sandbox), viewer-panel
>    (?? "vercel-sandbox"). Docs: preview-runtime.md, viewser.md, glossary,
>    B125-notens status, ADR 0033-uppdateringsnot.
> 6. **Reuse i prod med invalidering** (`6b6d6627`, ADR 0055 §2):
>    `SandboxSession` bär `buildId` (läst FÖRE källinsamling);
>    `tryReuseSessionPreview` återanvänder bara vid buildId-match + levande
>    URL (probe), annars stoppas sessionen (invalidering) → full väg.
>    Mekanismval (EN koherent livscykel): byggstart-stoppet är primärt,
>    invalideringen är backstopp för previews startade under bygget.
>    Hostade sandboxar får alltid tidsstämplade namn (reconnect-by-name är
>    disk-only) — ingen create-krock mot asynkront raderad sandbox.
>    `VIEWSER_SANDBOX_REUSE=1` SATT i Vercel-projektet för Production +
>    Development via CLI; **Preview-miljön gick INTE att sätta
>    non-interaktivt** (CLI-bugg: `env add ... preview --value 1 --yes`
>    svarar git_branch_required trots sin egen hint) — sätt den manuellt i
>    dashboarden om branch-previews ska ha reuse. **Uppdatering
>    2026-06-14:** Preview-värdet är nu satt (=1) via Vercel REST API, så
>    `VIEWSER_SANDBOX_REUSE` är konsekvent över Production/Preview/Development;
>    den tidigare blockeringen (`git_branch_required` på CLI:n) är löst.
>    Kvarstår: Production lagras som `sensitive`, Dev/Preview som `encrypted`
>    — samma värde, därför visar `vercel env pull production` raden blank.
>    Lås: 4 nya i `tests/test_viewser_sandbox_reuse.py`.
>
> **Effekt:** hostad preview-kallstart minuter → `npm install --omit=dev` +
> `next start`; oförändrad sajt med varm session svarar på sekunder
> (sessions-snabbvägen, ingen SDK-rundtur); no-op-followups behåller
> iframen. ADR 0055 skriven (0054 fortsatt reserverad).
>
> **Kvarvarande ärliga gap:** Preview-miljöns reuse-flagga (ovan — löst
> 2026-06-14, se uppdateringen ovan);
> Safari/Firefox-E2E för B125-stängning; blob-prune ännu mer angeläget
> (`.next` växer `generated/`-prefixet); `changeSet` hostat; filträd per
> run hostat.
>
> **Nästa pass börjar här:** (1) E2E i produktion på `/studio`: init →
> pre-built-preview (kolla `timings.prebuilt`) → no-op-följdprompt (iframe
> kvar) → edit-följdprompt (invalidering → ny sandbox) → re-POST
> (`reused:true`). (2) B197-review med tidig rebase (msg-0085). (3)
> Blob-/KV-prune-beslutet. ADR-liggare: nästa lediga **0056** (0054
> reserverad). naming-dictionary **v39** (ingen bump detta pass),
> llm-models **v12**.

## PASS 2026-06-12 ~07:30 — B199 V2: HOSTAD RUN-HISTORIK + ARTEFAKT-LÄSNING + OMLADDNINGS-ÅTERSTÄLLNING (HISTORIK)

> Historiskt block (ersatt av ADR 0055-passet ovan) — verifiera alltid mot
> git/koden.
>
> **Mandat:** operatören beordrade explicit (efter bannerfrågan på
> `/studio`) att hela hostade gapet fixas nu, inklusive omladdnings-delen
> som låg nära Christophers spår. B197 (discovery-payload-forwarding till
> sandboxen) är INTE rörd — den är fortfarande Christophers; be om tidig
> rebase, `hosted-build-runner.ts` är ändrad IGEN av detta pass.
>
> **Vad som landade (B199 v2, en commit-kedja på jakob-be → main):**
>
> 1. **Skriv-sidan** (`hosted-build-runner.ts`): orkestrerings-skriptet
>    publicerar efter varje lyckat bygge ett durabelt KV-index —
>    `HostedRunIndexEntry` (naming-dictionary **v39**) under
>    `viewser:run:<runId>` + `viewser:site:<siteId>:run:v<N>` (en
>    pipeline-POST), med ärlig `buildStatus` (även på run-state-pekaren).
>    Init-byggen skriver nu också result-blocket (engine=legacy) så svaret
>    bär den KANONISKA build_site-runIden, inte orkestrerings-UUID:t.
>    Historisk `baseRunId` hydrerar SIN versions artefakter via indexet
>    (siteId-bundet) — #307:s "bara senaste versionen"-gräns är stängd.
> 2. **Läs-sidan** (ny `lib/hosted-run-history.ts`): listar sajtens runs ur
>    KV (RunMeta-paritet, pekar-fallback för pre-v2-sajter), packar upp
>    run-artifacts-tarballen i minnet (gunzip + minimal ustar-läsare,
>    cache per immutabel URL) och serverar samma bundle-/trace-former som
>    lokalt. `/api/runs?siteId=` är hostade ingången — **siteId är
>    capability-nyckeln** (B196-modellen): utan siteId listas INGET
>    (ingen global publik enumeration). artifacts/trace serveras hostat;
>    olösbar run = VANLIG 404 utan `hostedNotice`.
> 3. **Klient-sidan** (`studio/page.tsx` m.fl.): builder-valet persisteras
>    i sessionStorage och återställs efter hård omladdning (validerat mot
>    hämtade listan; hostat via per-sajt-fetch). Bannern flyttade till eget
>    fält `hostedBanner` och **armar ALDRIG 404-latchen** — latchen
>    (lib/hosted-run-artefacts.ts) är nu enbart belt-and-braces för
>    riktiga 404+hostedNotice-former, som ingen run-route längre skickar.
>    Banner-texten omskriven till nya läget. files-routens hostade 404
>    bär inte längre `hostedNotice` (skulle döda fungerande ytor).
> 4. **Tester/governance:** `tests/test_viewser_hosted_run_history.py`
>    (14 källkods-lås), uppdaterad hydrerings-docstring, naming-dictionary
>    v39 (`HostedRunIndexEntry`), B199 STÄNGD i known-issues (16 aktiva,
>    170 stängda). tsc + eslint gröna; prettier-avvikelser är
>    pre-existerande CRLF-status-quo på Windows-checkouten (ej gateat).
>
> **Kvarvarande ärliga gap (ej blockers):** filträdet per run
> (StackBlitz-fallback) serveras inte hostat; `changeSet` är `null` i
> hostade followup-svar; runs byggda FÖRE detta deploy har bara senaste
> versionen i historiken (pekar-fallback) och UUID-valda gamla flikar
> löses via 24h-statusdoken. KV-/blob-prune är fortsatt ett öppet
> operatörsbeslut (samma liggare som `generated/`-prune).
>
> **Nästa pass börjar här:** (1) E2E-verifiera i produktion på `/studio`:
> init → historik/inspector synliga → omladdning → builder-läget kvar →
> edit-följdprompt (OpenClaw apply) → ren fråga (answer-only), kolla
> `engine`-attribution. (2) B197-review (Christophers) — kräv tidig rebase
> mot nya `hosted-build-runner.ts`. (3) Blob/KV-prune-beslutet + Token
> Meter-priser + Christophers lokala blob-store `3xqg…`. ADR-liggare:
> nästa lediga **0055** (0054 reserverad). naming-dictionary **v39**,
> llm-models **v12**.

## PASS 2026-06-12 ~05:45 — GRYNINGSSTÄNGNING: #306 + #307 MERGADE OCH LIVE (HISTORIK)

> Historiskt block (ersatt av B199 v2-passet ovan) — verifiera alltid mot
> git/koden.
>
> **Git:** `main = jakob-be = origin/main = origin/jakob-be = a67a25b0`
> (rent träd, CI grön på båda grenarna, produktionsdeploy READY).
> Kedjan ovanpå nattpassets `575af63b`: docs-checkpoint (`a06ba1dc`-serien)
> → `64aaeea4` (lagade två röda källkods-lås: run-details-panel
> clear-before-fetch + versions-tab 1313→1278 rader, regression från
> `691bd835`; CI var RÖD på lane i ~1,5 h innan detta) → `d1a1b98d`
> (**#306** squash: B198 del b) → `a67a25b0` (**#307** squash: hostad
> follow-up-paritet). Build-context-tarballen omladdad EFTER `a67a25b0`
> (1,4 MB → `build-context/current.tar.gz`, KV-URL uppdaterad) — hostade
> sandbox-byggen kör samma kod som `main`.
>
> **#306 — B198 del b** (`d1a1b98d`): contact-form surfas som synlig
> section-route mot BEFINTLIGA kontakt-routen på ecommerce-lite, gated på
> att `resend-contact-form` är monterad i `selectedDossiers.required`
> (mailto förblir ärligt mount-only). `appliedVisibleEffect=true` +
> `affectedRoutes=["contact"]` E2E-bevisat i PR:ens tester. known-issues:
> B198 flyttad till Stängda (17 aktiva, 169 stängda).
>
> **#307 — hostad follow-up-paritet** (`a67a25b0`), tre ordnade delar:
> (1) **B199-hydrering** — efter lyckat hostat bygge tarballas
> `data/runs/<runId>/` (input/site-brief/site-plan/generation-package/
> build-result/quality-result) till blob `run-artifacts/<siteId>/v<N>/`;
> pekaren får `runId` + `runArtifactsUrl`; vid followup curlas + extraheras
> tarballen i sandboxen FÖRE apply/PI. (2) **OpenClaw apply-söm** —
> `run_openclaw_followup.py --apply` körs i sandboxen som grind framför
> legacy (samma grenordning som lokala `runPromptBuildOnce`: applied →
> answer-only → legacy); answer-only startar INGET bygge; ärlig
> `engine`-attribution ("openclaw"/"legacy"/"answer-only"), aldrig fejkad
> apply-success. (3) **Request/response-paritet** — `baseRunId` +
> `markedSections` forwardas (sanerade TS-side; markedSections enbart till
> legacy-PI, exakt som lokalt), och sandboxen POST:ar ett rikt result-block
> till KV som TS-sidan bygger lokala svarskontraktet av
> (version/buildResult/appliedCopyDirectives/openClawDecision/bridge/
> conversation/answerText). Sex nya regressionstester
> (`tests/test_viewser_hosted_followup_parity.py` m.fl.).
> **v1-begränsningar (ärligt dokumenterade):** artefakt-pekaren spårar
> SENASTE versionen (historisk `baseRunId` hydreras inte), `changeSet` är
> `null` hostat.
>
> **Process-lärdom (inskriven efter CI-incidenten):** riktade tester räckte
> inte — `691bd835` mergades med två trasiga källkods-lås som full svit
> hade fångat. Full svit (`python -m pytest tests/ -q -n auto`) före
> lane-push är nu praxis, och cloud-prompter ska kräva det explicit.
>
> **Env-läget för hostad testning:** INGET nytt behövs på Vercel. Flaggorna
> (`VIEWSER_ENABLE_HOSTED_BUILD=1`, `VIEWSER_ENABLE_HOSTED_SANDBOX=1`) är
> redan på, `OPENAI_API_KEY` forwardas till sandboxen, och
> `OPENCLAW_ROUTER_LLM_FALLBACK` är osatt = default PÅ (LLM-routing aktiv i
> sandboxens apply-söm — önskat läge). `VIEWSER_SANDBOX_REUSE` lämnas osatt
> (disk-only, ingen effekt hostat). **Uppdatering 2026-06-14:** inaktuellt —
> reuse är effektivt hostat sedan ADR 0055 (sessions-snabbvägen) och
> `VIEWSER_SANDBOX_REUSE=1` är nu satt på Production/Preview/Development
> (Preview via Vercel REST API; CLI blockerad av `git_branch_required`).
> Kvarstår: Production `sensitive`, Dev/Preview `encrypted`.
>
> **Nästa pass börjar här:** (1) E2E-verifiera #307 i produktion på
> `/studio` — init-bygge, edit-följdprompt (förvänta OpenClaw apply när
> artefakter finns), ren fråga (förvänta answer-only utan bygge), kolla
> `engine`-attribution. (2) B197-review när Christophers PR kommer — OBS
> `hosted-build-runner.ts` kraftigt omskriven av #307, be om tidig rebase.
> (3) B199 v2 (per-run-historik + `changeSet` hostat), blob-prune för
> `generated/`, operatörsbesluten (Token Meter-priser, Christophers lokala
> store `3xqg…`). Inbox: msg-0081 till christopher med synk-uppmaning.
> ADR-liggare: nästa lediga **0055** (0054 reserverad). naming-dictionary
> **v38**, llm-models **v12**.

## PASS 2026-06-12 ~03:30 — NATTPASS: HOSTAD BUILDER-PARITET SHIPPAD + TVÅ CLOUD-PROMPTER KÖADE (HISTORIK)

> Historiskt block (ersatt av gryningsstängningen ovan) — verifiera alltid
> mot git/koden.
>
> **Git:** `main = jakob-be` (rent träd, local == origin). Nattens
> commit-kedja ovanpå midnattens `5109cc1f`-checkpoint: `4162a14a`
> (banner-ärlighet) → `74dc9218` (`ignoreCommand` mot
> `VERCEL_GIT_PREVIOUS_SHA`, fallback `HEAD^`) → `60319439` (ruleset-notis)
> → `bc074edb` (flagg-medveten hostad notis) → `cdd6785d` + `b4f6e2d2`
> (hostad builder-paritet) → `691bd835` (404-tystnad + B199) → `15ea0fda`
> (readiness-poll) → `ed0a2039` + `42a54945` + `575af63b`
> (canvas-rättningar). Senaste icke-docs-commit `575af63b`; detta docs-pass
> ligger ovanpå. Production (`sajtbyggaren-viewser.vercel.app`) kör senaste
> app-bygget; rena docs-pushar skippar prod-rebuild med flit, så prod kan
> peka på senaste app-ändringen snarare än main-HEAD (väntat
> monorepo-beteende).
>
> **Nattens fixar (alla på jakob-be):** banner-/notis-ärlighet (`4162a14a`,
> `bc074edb`) — "lokalt" = operatörens lokala miljö, och med
> `VIEWSER_ENABLE_HOSTED_BUILD=1` säger bannern att byggen kör i Vercel
> Sandbox. Hostad builder-paritet (`cdd6785d`, `b4f6e2d2`): FloatingChat
> tänds när ett bygge slutförts i sessionen även med tom `/api/runs`, och
> följdprompt-byggen registreras i sessionskartan via selectedSiteId-fallback
> så FloatingChat överlever rebuild hostat. Hostade
> `/api/runs/[runId]`-artefakt-404:or (artifacts/trace/files) tystade i UI:t
> (lugn notis + session-latch i stället för rött fel och meningslös polling)
> + B199 dokumenterar blob-utredningen (`691bd835`). Härdad preview
> readiness-poll (`15ea0fda`): 502/503/429 räknas inte som "klar", så hostad
> preview inte visar sandbox-uppstart som fel. Canvas-rättningar (`ed0a2039`,
> `42a54945`, `575af63b`): `OPENAI_MODEL` är `gpt-5.4` i prod, autogen-facts
> regenererad (llmModelsVersion 12, hard-dossier 1) och env/fallback-callout
> rättad.
>
> **E2E-bevis för hostad paritet:** hostade följdprompter aktiverar nu
> builder-läget och FloatingChat live på `sajtbyggaren-viewser.vercel.app` —
> ett bygge slutfört i sessionen tänder builder-UI:t och en följdprompt
> överlever en hostad rebuild. Återställning av builder-läget efter en hård
> omladdning är kvar (kräver hostad artefakt-hydrering, B199).
>
> **Env-domar (lämna osatta på Vercel):** `OPENCLAW_ROUTER_LLM_FALLBACK` är
> no-op i den hostade vägen och `VIEWSER_SANDBOX_REUSE` är disk-only (ingen
> effekt hostat). **Uppdatering 2026-06-14:** `VIEWSER_SANDBOX_REUSE`-domen är
> inaktuell — reuse är effektivt hostat sedan ADR 0055 och flaggan är nu satt
> (=1) på Production/Preview/Development (Preview via Vercel REST API; CLI
> blockerad av `git_branch_required`; Production `sensitive`, Dev/Preview
> `encrypted`). Avlivade sammanblandningar: pipen är hybrid (`gpt-5.4` för
> brief/plan/copy, deterministisk codegen — inte "rent mekaniskt"); det finns
> ingen automatisk `gpt-5.4` → `gpt-5.5`-modellfallback (kod-fallbacken
> `gpt-5.5` träffar bara när env-nyckeln saknas). Extern review verifierad:
> hostat KÖR-7-paritetsgapet är PARTIELLT, inte total avsaknad — legacy-vägen
> kör copy-directives.
>
> **Två köade cloud-prompter (PR:as mot jakob-be):** (1) hostad
> follow-up-paritet i tre ordnade commits — B199-hydrering → sandbox
> apply-seam → request/response-paritet, root-cause-ledd, körs först;
> (2) B198 del b contact-form-render, oberoende spår. Vår action: reviewa
> inkommande cloud-PR:ar snabbt (lane review-SLA).
>
> **Tre öppna issues:** B199 (hostad artefakt-hydrering — förutsättning för
> hostad KÖR-7), B197 (discovery-paritet hostat), B198 del b
> (contact-form-render; fungerar redan hostat via legacy-vägen). ADR-liggare:
> nästa lediga **0055** (0054 reserverad). naming-dictionary **v38**,
> llm-models **v12**.

## PASS 2026-06-12 ~00:30 — MIDNATTSSTÄNGNING: B194 LIVE + MAIN-SYNK KLAR (HISTORIK)
>
> **Git:** `main = jakob-be = origin/main = origin/jakob-be` (tom diff, rent
> träd). Sista kodcommit `5109cc1f` (CI-actions v6); detta docs-pass ligger
> ovanpå. Production deployar från `main` och kör B194-koden (deploy READY
> från `main@78417aae`, app-identisk med tippen). Backup av för-sync-main:
> `backup-main-2026-06-11-pre-evening-sync-cb0f6a5`.
>
> **Mergat efter 22:55-checkpointen:** **#305** Vercel Web Analytics
> (Vercel-agentens PR, retargetad main→jakob-be, `<Analytics />` i
> layout.tsx). **#292** hostad asset_set-forwarding (Christophers, ren
> 1-commit-rebase). **#304** B194 — hostad run-state persisteras till blob
> (`run-state/<siteId>/v<N>/`, immutabelt par) + KV-pekare; krävde basmerge
> `57ceec9c` + naming-dictionary **v38** (`HostedRunStatePointer`,
> term-coverage-grinden fångade oregistrerad term). `5109cc1f` bumpar
> GitHub Actions till v6 (Node 20-deprecationsvarningarna borta).
>
> **HOSTADE FÖLJDPROMPTER ÄR LIVE OCH E2E-BEVISADE** mot
> `sajtbyggaren-viewser.vercel.app`: init-bygge (`site-e342ef7b`, ok, ~141 s)
> → run-state v1 i blob → följdprompt (ok, ~110 s) → v2 skapad (v1 orörd),
> ändringen verifierad i v2-PI:n. **Build-context-tarballen omuppladdad**
> (`build-context/current.tar.gz` var från 06-10 och saknade kvällens Python
> — utan omuppladdningen hade hostade byggen kraschat på okänd CLI-flagga).
> Kom ihåg att ladda om tarballen efter merges som rör
> `scripts/`/`packages/`/`governance/`/`data/starters/`:
> `node apps/viewser/scripts/upload-build-context-to-blob.mjs`.
>
> **Ny MÅSTE-regel för christopher-lanen** (operatörsbeslut, i
> `governance/rules/04-branch-and-team.md`): auto-synk vid passtart, hela
> grinden före varje push (inkl. term-coverage), nya identifierare
> registreras i samma commit, auto-rebase av öppna PR:ar när basen flyttar
> sig, jakob-be-lanen får slutföra stale gröna PR:ar via basmerge. Motkrav
> på vår lane: kort review-SLA på små gröna PR:ar. Christopher har
> kvitterat (msg-c-0084), synkat lanen till `5109cc1f` och påbörjat B197
> (hostad discovery-paritet) — ingenting blockerar någon lane just nu.
>
> **Vercel-noteringar:** (1) `ignoreCommand`-fällan: en main-push vars SISTA
> commit är docs-only får sitt prod-bygge cancelat — pusha appkods-commit
> sist (tvåstegspush) eller promota manuellt. (2) Dashboard-bannern
> "Revoke Token" på blob-storen får INTE klickas — hostade pipelinen
> använder `BLOB_READ_WRITE_TOKEN` direkt (sandbox-env + run-state-uploads).
> (3) OIDC-tokenen auto-refreshas vid dev-start + före varje Sandbox.create
> (`lib/vercel-oidc-refresh.mjs`) — inget manuellt underhåll. (4) Christophers
> lokala `.env.local` pekar på en ANNAN blob-store (`3xqg…`) än projektets
> (`vxfg…`) — lokal/hostad delar inte asset-bibliotek; operatörsbeslut om
> unifiering står öppet (msg-c-0083).
>
> **Kvarvarande öppet:** B198 del b (synlig contact-form-render), ADR
> 0052-städ + eslint-fyndet i `industry-search.tsx:298`, Token Meter-priser
> (står på 0), B155/B197 (Christophers pågående). ADR-liggare: nästa lediga
> **0055** (0054 reserverad). naming-dictionary **v38**, llm-models **v11**.

## PASS 2026-06-11 ~22:55 — OPENCLAW-SMARTNESS + /KORT + STÄDNING (HISTORIK)
>
> **Git:** `origin/jakob-be = 6d740fcc` (rent träd, local == origin). Lokal
> `main`-pekare fast-forwardad till `origin/main = cb0f6a5d` (ren bokmärkesflytt).
> Lokala branches kvar: `christopher`, `jakob-be`, `main` — de tre mergade
> `backup_*`/`backup-160-BRA` raderade lokalt (finns kvar på origin). Inga extra
> worktrees. Prod deployas från `main`.
>
> **Main-sync-status (UPPDATERAD ~23:55 samma kväll):** main-syncen är KLAR
> (operatörsbekräftad). `main` = `jakob-be` på GitHub igen, production deployar
> från `main`. Efter checkpointen mergades dessutom **#305** (Vercel Web
> Analytics, Vercel-agentens PR, retargetad mot jakob-be), **#292** (hostad
> asset_set-forwarding) och **#304** (B194 — hostad run-state-persistens, inkl.
> naming-dictionary v38 `HostedRunStatePointer`), så hostade följdprompter är
> live. Build-context-tarballen omuppladdad från färska trädet (den gamla från
> 2026-06-10 saknade kvällens Python-ändringar). Backup av för-sync-main:
> `backup-main-2026-06-11-pre-evening-sync-cb0f6a5`. OBS `ignoreCommand`-
> beteendet: en main-push vars SISTA commit är docs-only får sitt Vercel-bygge
> cancelat (HEAD^-diffen ser bara pushens sista commit) — toppa med en
> appkods-commit eller promota manuellt.
>
> **Kvällens merges (till jakob-be):** **#297** KÖR-6b i bryggan (routerModel-
> fallback för tvetydiga följdprompter, kill-switch `OPENCLAW_ROUTER_LLM_FALLBACK`,
> EN klassificering per anrop). **#298** dirigent-bekräftelse i chatten efter
> synligt applicerad ändring (grundad i fakta, tidsboxad). **#301** B198 del a
> (namngiven dossier "resend" monterar `resend-contact-form` i stället för
> mailto-default). **#302** fallback-toggle i Dirigentpulten. **#303** hardening
> efter extern riskmatris. **#299/#300** (parallellspår) env-dok + ignoreCommand,
> kompletterad med `docs/openclaw-workspace` i `2ef8f116`. **#269** Christophers
> Verktyg-omgörning fas 1–3 mergad efter godkänd review. Plus `/kort`-regeln
> (`6d740fcc`): operatören skriver `/kort` → ultrakort svar/matris.
>
> **Vercel-env verifierad:** 22 variabler, identiska i Production/Preview/
> Development (14 app-ägda + 8 integrationsägda Upstash/Blob). Ingen statisk
> `VERCEL_OIDC_TOKEN` hostat. `vercel link` körs FRÅN REPO-ROTEN (monorepo-länk
> `.vercel/repo.json` → `apps/viewser`); `vercel env pull` likaså från roten.
>
> **Nästa prioriteringar (se current-focus för full lista):** (1) review-kedjan
> #292 → #304 (B194-stängning, Christophers lane). (2) main-sync-uppföljning.
> (3) B198 del b — synlig contact-form-render på ecommerce-lite. (4) ADR 0052-
> städ (död `gpt-5.4`-default + design-tooling-trådning). ADR-liggare: nästa
> lediga **0055** (0054 reserverad för MCP-intagsgrinden).
>
> **Notisen om `fix/kvallsbatch-hardening`:** utredd och ofarlig — den branchen
> bytte tillfälligt din huvud-checkout under parallellspåret men rördes inte;
> innehållet ligger nu i #303 och branchen är borta. `git fetch --prune` rensar
> bara remote-tracking-pekare för redan-mergade brancher, aldrig lokalt arbete.

---

## PASS 2026-06-11 ~13:30 — PUBLIK HOSTAD DRIFT LIVE + #288/#289/#290 (HISTORIK)

> **Detta är det ENDA auktoritativa blocket. Allt äldre är historik —
> verifiera alltid mot git/koden.**
>
> **Git:** `origin/jakob-be = origin/main = a314fe5a` (tom diff, rent träd).
> Backuper: `backup-main-2026-06-11-pre-sync` (= `26b2464`), äldre
> `backup-170-BRA`/`backup-160-BRA`. Produktionen deployas från `main` och
> kör HEAD (verifierad Ready efter syncen).
>
> **DRIFTLÄGE (operatörsbeslut 2026-06-11): publik hostad Viewser är PÅ.**
> Den tidigare driftspärren är HÄVD (known-issues uppdaterad + inbox
> msg-0071): `VIEWSER_ENABLE_HOSTED_BUILD=1` + `VIEWSER_ALLOW_NON_LOCALHOST=true`
> i alla Vercel-miljöer. Vem som helst kan skapa en sajt på
> `sajtbyggaren-viewser.vercel.app` (~2 min/bygge). Skydd: rate-limit per IP
> (ADR 0050; chat 20/min, bild 5/min, preview 6/min, bygge 3/5 min),
> sandbox-TTL 15 min, B195 manifest-servering, B196 siteId-bunden statusroute.
> Sätt INTE flaggorna till av utan nytt operatörsbeslut.
>
> **Eftermiddagens merges:** **#288** review-sweep — B196 stängd
> (`GET /api/hosted-build/<runId>` kräver `?siteId=`, ingen orakel-läcka),
> KV-preflight före `Sandbox.create` (hostat failar ärligt utan Upstash-env),
> hostad icke-stream-väg väntar in done/failed server-side (202-buggen där
> floating-chat/use-followup-build rapporterade "klart" under pågående bygge
> är eliminerad — klientkontraktet är åter identiskt med lokalt), #283-fyndens
> tre fixar (sektionsmedveten bastext i `section_base_text`, tom-bas no-op i
> editPlan, hero-pin-paritet i apply), deploy-dokumentet omskrivet för publik
> v1, B197 trackad (discovery-paritet hostat, P3). **#289** guard-snabbning
> (operatörsbeslut): riktade tester är lokal default; full svit = CI:s ansvar
> på PR; lokalt heltest med pytest-xdist `-n auto` (uppmätt 291 s mot ~13 min
> seriellt). Regelkälla: `governance/rules/04-branch-and-team.md` guard 5.
> **#290** analysrapporten `docs/reports/sajtmaskin-vs-sajtbyggaren-analys-2026-06-10.md`
> landad (form-only term-disciplin; GoDaddy → COMMON_WORDS, legacy-citat via
> testets EXCLUDE_FILES) — term-coverage helt grön för alla agenter igen.
>
> **Förmiddagens merges (samma dag):** #284 (hostat bygge, ADR 0048/0049/0050),
> #286 (env-konsolidering: 22 rader All Environments, manual i
> `docs/operations/hosted-viewser-manual.md`), #287 (B195). Prod-buggen
> "Blob-upload misslyckades" (tyst noll-varvs-loop i upload-skriptet) fixad +
> live-verifierad (`fa268c5`, `0494e7f`).
>
> **Christopher-koordinering:** klartecken för lane-rebasen skickat
> (msg-0072): #269 + Verktyg fas 1–3 + bildbyte-guarden (`0f3f243`) + #285
> (retargetad mot jakob-be) konsolideras mot HEAD; route.ts-threading läggs
> OVANPÅ hostade grenen/rate-limiten; naming-dictionary tar v35 (v34 orörd).
> Christopher-lanen använder msg-c-*-prefix framåt. Deras lane äger
> `use-followup-build.ts` + dialogerna + inspector (B192 deferrad dit).
>
> **Riktning efter analysrapporten (operatörens kritiska gallring — rapporten
> är uppslagsbok, inte backlog):** antaget: resend-contact-form som första
> hard-dossier (stänger contact-svagheten, 8.2/10-evalen), eval-baseline-grind,
> autofix som arbetsregel. Avvisat/parkerat: radgräns-CI, truth_level-svep,
> scaffold-expansion, apps/web, deploy-paket.
>
> **ADR-nummerliggare:** 0047 (mergad #283), 0048/0049/0050 (mergade #284),
> **0046 hålls av öppna #285**. Nästa lediga: **0051** (contact-dossierns
> schema v2-ADR är första kandidat).
>
> **Kvarvarande öppet:** B192 (deferrad bakom #269-rebasen), B194/B197
> (P3-spår), B155 (kvarvarande targets), #156 (parkerad referens — kan
> stängas, ersatt av P2-leveransen). Token Meter-priser i Vercel-env står
> på 0 (operatörsval att sätta riktiga).
>
> Kön + detaljer: `docs/current-focus.md` (alltid först).

## PASS 2026-06-11 ~11:20 — #287 + #286 MERGADE + MAIN-SYNC (HISTORIK)
>
> **Git:** `origin/jakob-be = origin/main = 758d8dd` (efter denna sync). #287
> (`8377868`, B195-fix / manifest-servering + known-issues-format) och #286
> (`758d8dd`, Vercel-env-konsolidering, docs/example-only) mergade till jakob-be;
> `main` fast-forwardad till `jakob-be` → tom diff. Pre-sync-backup av föregående
> main (`2e13aa3`): `backup-170-BRA`. Tidigare pre-ship-backup: `backup-160-BRA`
> (= `70e5e36`, jakob-be före #284). Rent träd.
>
> **#287 + #286 (2026-06-11):** #287 stänger B195:s stale-blob-gap via
> manifest-baserad servering (`08575a0`) + korrigerar B194/B196-format i
> known-issues (`60cdfa3`); #286 speglar den konsoliderade Vercel-env-målbilden
> i `.env.example`-mallarna + hosted-viewser-manualen (`ANTHROPIC_API_KEY`
> borttagen — ingen provider-rad i `llm-models`). Ingen ny ADR (liggaren
> oförändrad, nästa lediga `0051`).
>
> **#284 MERGAD (`9cd8624`) — hostat bygge i Vercel-sandbox + KV-store-adapter
> + publik rate-limit (ADR 0048/0049/0050).** Granskad av subagent (GO-med-
> fixar). Blockerande säkerhetsbugg fixad FÖRE merge (`e44dcbb`): rate-limitens
> klient-IP litade på första `x-forwarded-for` (klient-spoofbar på Vercel) →
> hela kostnadsskyddet kringgicks; nu `x-real-ip` först, annars sista
> XFF-entryt. + självläkande KV-TTL (TTL sätts om på varje incr så en tappad
> expiry inte permanent-blockar en IP). Hostat läge default AV
> (`VIEWSER_ENABLE_HOSTED_BUILD` + Redis-driver krävs).
>
> **⚠️ DRIFTSPÄRR — publik hostad deploy ska vara AV** tills B196 fixad (B195
> åtgärdad via #287): `VIEWSER_ENABLE_HOSTED_BUILD` får INTE sättas och `VIEWSER_ALLOW_NON_LOCALHOST`
> får INTE vara `true` i prod. (Vercel-agent/operatör: aktivera inte hostat
> bygge publikt än.)
>
> **Spårade #284-uppföljningar (registrerade i known-issues, ej jakob-be-
> blockerare — hostat är default AV/localhost-grindat):**
> **B194** (P3) hostad followup failar ärligt utan persisterad run-historik —
> kräver state-persistens innan hosted followups funkar. **B195** (publik-
> deploy-defekt) blob-upload raderade aldrig stale filer (borttagen route/asset
> kvar i preview vid ombygge mot samma siteId); en påbörjad upload-loop-
> härdning landade via `fa268c5`, och stale-radering är nu ÅTGÄRDAD via #287
> (manifest-baserad servering, `08575a0`) — known-issues-raden ej flippad än. **B196**
> (publik-deploy-härdning) `GET /api/hosted-build/<runId>` saknar site-binding/
> auth i publikt läge.
>
> **ADR-nummerliggare:** 0044 SOUL (mergad), 0045 SNI (mergad #280), **0046
> TAGEN av öppna #285** (Christophers section-marking — VÄNTAR REBASE mot
> jakob-be, INTE mergad av oss), 0047 generativ omskrivning (mergad #283),
> **0048/0049/0050 mergade via #284** (hostat bygge / KV-store / publik rate-
> limit). Nästa lediga ADR-nummer: **0051**.
>
> **Öppet/pågående:** #285 (ADR 0046 section-marking, Christophers — siktar på
> `main`, HÖG konfliktrisk mot jakob-be på `route.ts` + naming-dictionary;
> SKA rebasas av Christopher mot jakob-be, inte mergas av oss), #269 (enbart
> inspector-lanen, väntar Christophers rebase — överlappar #285:s inspector-
> grund, koordinera så lanen landar EN gång), #156 (parkerad, säkerhet).
> B192 öppen (answer-only rött i dialog-vägen, deferrad bakom #269).
>
> Kön + detaljer: `docs/current-focus.md` (alltid först).

## DAGPASSET 2026-06-10 ~17:00 — ÖVERLÄMNING (HISTORIK)

> **Detta är det ENDA auktoritativa blocket. Allt äldre (inkl. nattens
> closing-round nedan) är historik — verifiera alltid mot git/koden.**
>
> **Git:** `main = jakob-be` (tom diff, hålls i sync löpande i dag; två
> formella main-syncar + direkta docs-pushar). Pre-sync-backup:
> `backup_150_BRA`. Rent träd, inga worktrees, alla mergade brancher städade.
>
> **Dagens facit (10 PR:ar + direkta commits):** #270 slice 3-delar
> (B177 fonter via `<link>`, B178 ärlig fri-text, answer-only i dialoger),
> #271 backoffice Arrow-fix, #272 delade canvases (Steward-ägda),
> #273 B183–B185, #274 F1 slice 3 roll-dispatch (+`expectsAnswer`+roll-rad),
> #275 komponentkatalog lager 1+2 (ADR 0040), #276 Tier 2 sandbox-reuse
> (ADR 0041, opt-in `VIEWSER_SANDBOX_REUSE`), #277 toolIntent-pilot UI
> (Christophers utbrytning), #278 ADR 0043 sektionstext-utföraren
> ("ändra texten i hero-sektionen till X" ger nu synlig ändring),
> #279 ADR 0044 SOUL i runtime + Backoffice-identitetsvy. Direkta commits:
> extern granskning processad (B186–B191 fixade), B193 roll-minne i chatten,
> B187 frågeformade edits, Steward-pass (0 misplaced), manuella
> klick-checkar pensionerade till källås, komponentkatalog-design-not
> (alla 4 beslutspunkter avgjorda).
>
> **ADR-nummerliggare (kollisionsrisk vid parallella agenter!):** 0040
> komponentkatalog (mergad), 0041 Tier 2 (mergad), 0042 RESERVERAD lager 3
> (ev. i cloud), 0043 sektionstext (mergad), 0044 SOUL (mergad), 0045
> SNI-branschberedskap (mergad #280), 0046 RESERVERAD model-tuning,
> 0047 generativ sektionsomskrivning (MERGAD via #283 ~19:20). Nästa lediga
> ADR-nummer: **0048**.
>
> **Kväll ~19:20 — två cloud-PR:ar GRANSKADE + MERGADE (`df25e34`):**
> #282 compound-prompt-ärlighet (B155-uppföljning, ingen ADR — ägarlösa/
> omaterialiserade KÖR-7-subtasks rapporteras via befintliga
> `unappliedFollowupIntents`; ren observer `openclaw/unapplied.py`) och
> #283 ADR 0047 generativ sektionsomskrivning (omskrivnings-instruktion utan
> värde → copyDirectiveModel editPlan på vitlistade sektionsfält, enbart via
> ADR 0043:s `sectionContentOverrides`, samma guards, mock-paritet). Båda
> rörde `apply.py` i disjunkta regioner → mergade i följd utan konflikt,
> sanity-guard på sammanslagna trädet grön. `main = jakob-be` tom diff.
> PR-brancher städade.
>
> **Öppet/pågående:** #269 (numera enbart inspector-lanen, väntar
> Christophers rebase — HANS action), #156 (parkerad, säkerhet).
> Ev. cloud-agenter i flykt: lager 3 (ADR 0042), model-tuning (0046).
> B192 öppen (answer-only rött i dialog-vägen, deferrad bakom #269).
>
> **Operatörens kvarvarande manuella:** dev-server-omstart; live-test av
> sektionstext-ändring + SOUL-chatt med riktig nyckel; Tier 2-mätning
> (`VIEWSER_SANDBOX_REUSE=1`, kolla `reused: true`).
>
> Kön + detaljer: `docs/current-focus.md` (alltid först).

## Föregående checkpoint (natten 2026-06-10 ~06:00) — HISTORIK

> Nattens closing-round, ersatt av dagblocket ovan.
>
> **Git-läge:** `origin/jakob-be = 9a7c9f6`, rent träd, lokal = origin.
> `main = 7486145`. `jakob-be` ligger 16 PRs före `main` — **main-sync är
> nästa naturliga leveransfönster (operatörsbeslut; efter sync sätter
> Vercel-agenten prod-env med Deployment Protection-villkoret)**.
> Enda öppna PR: **#156** (parkerad arkitektur-referens; Vercel-botens
> accepterade fixar ligger ofarligt på branchen — lärdomen
> `Sandbox.get({resume:false})` är värdefull för Tier 2).
> ALLA mergade PR-brancher städade lokalt+remote (inkl. cursor-speglar och
> docs-dedupe-branchen). `rescue/openclaw-f1-d76ad9c` RADERAD efter
> verifiering (innehållet landade via #259+#260). Kvarvarande lokala
> brancher: `jakob-be`, `main`, `backup_100_BRA`, `feat/live-preview`.
> Inga aktiva worktrees. Operatörens otrackade `.cursor/rules`-fil lämnad
> (personlig regel; flytta till governance/rules om den ska bli permanent).
>
> **Nattens slutfacit: 16 PRs mergade (#252, #254–#267 utom stängda #253),
> 13 buggar stängda (B163–B175).** Sen runda 2-blocket skrevs landade
> dessutom: #261 (B155-slice okvoterad literal replace), #262 (F1 slice 2 —
> SMARTA CHATTEN LIVE: skämt/omdöme/fråga → ärligt svar utan bygge),
> #263 (sandbox Tier 1: pre-built .next ~20 s/preview + OIDC-autorefresh +
> timings; + Scout-R1 trace-katalog-härdning `472e150` direkt på jakob-be),
> #264 (B173 hero-H1-pinning i BÅDA seams — Scout fångade apply-gapet),
> #265 (B174 falska QG-varningen: sentinel-kontrakt för bridge-JSON),
> #266 (prune-on-dev-start: npm run dev städar gamla byggen säkert),
> #267 (B175 first-run-recovery med mtime-färskhet).
>
> **Arbetssätt som fungerade i natt (rekommenderas):** Builder-agenter i
> EGNA git-worktrees (aldrig branch-byte i delade huvudträdet) → PR mot
> jakob-be → READ-ONLY Scout-granskning per PR → merge vid go + grön CI.
> Scout-grinden fångade skarpa fel i 4 av 9 granskningar — behåll den.

### Vad som landade i natt (per tema)

**Bug-sweep round 1 (#254, 6 buggar):** B163 stale preview efter ny version,
B165 apex↔www-crawl, B167 prune-guardens portar, B168/B170/B171
OpenAI-env-kedjan (nyckelhantering/Token Meter/cache).

**Wizard (#256):** B166 — Hämta-knappen gör nested merge så scrape-fält inte
skriver över operatörens ifyllda fält. Prioriterad direkt av eval-rundans
dominanta `contact`-problem.

**Hostad Viewser (#257, FAS 2A+2B):** ärlig 2A-degradering (hostad läge utan
Python-vägar svarar ärligt i stället för att låtsas), gatad 2B
sandbox-preview med blob-source (`generated-blob-source.ts`,
snapshot-CLI). VIKTIGT: sandbox-flaggan får ALDRIG sättas i Vercel-projektet
utan Deployment Protection (Vercels åtkomstskydd) aktiv.

**OpenClaw F1 slice 1 (#259):** rollkontrakt i
`packages/generation/orchestration/openclaw/roles.py` + `ConversationKind`
(conductor-klassning småprat/omdöme/edit; messageKind-låsningen på 8 intakt),
58 tester.

**Följdprompt-robusthet (#260):** B164 dubbelbygge-recovery (ingen tyst
legacy-fallback ovanpå redan skriven chain-version), B169 per-site-mutex i
`/api/prompt` (site A blockerar inte site B), B172 siteId-filtrerad
runId-detektion i `build-runner.ts`.

**Backoffice-grinden (#258, cloud-lane):** governance-lås för vy-registret
(`governance/policies/backoffice-views.v1.json` + schema), Idag-landningsvy
med färskhetsbrickor, Loop-bevis-vy som bygger sajt deterministiskt.
Mergad strax efter tåget (HEAD `3674475`).

**Eval (styrde prioriteringen):** real-LLM Golden Path 2026-06-10 = 8.2/10
totalt, alla 4 case pass, gate go; deterministisk baseline 7.75. Dominant
problem `contact` i alla case → B166 togs först.

### Lösa trådar (för nästa orchestrator, prioriterat)

1. **Main-sync-beslut (operatören):** 16 PRs verifierade och gröna —
   bra fönster. Efter sync: be Vercel-agenten sätta prod-env
   (`VIEWSER_ALLOWED_HOSTS` = `sajtbyggaren-viewser.vercel.app`;
   `VIEWSER_ENABLE_HOSTED_SANDBOX` ENDAST bakom Deployment Protection).
   Hosted preview är redan live på jakob-be-previewen bakom SSO
   (dokumenterat i #257-tråden).
2. **F1 slice 3 — section_builder-dispatch:** rollvalet styr skill/prompt
   i kedjan (idag bara metadata), ärlig roll-rad i FloatingChat,
   dialog-vägens konversationshantering (use-followup-build),
   `expectsAnswer`-signal (Scout-fynd #262). Plan + stylist-scope-
   beslutsunderlag: `docs/heavy-llm-flow/openclaw-2.0-conductor.md`.
3. **Sandbox-mätning + Tier 2:** mät #263:s verkliga vinst (`timings`
   med/utan `VIEWSER_SANDBOX_UPLOAD_BUILT=0` på painter-palma); därefter
   bas-snapshot (P3) + sandbox-återanvändning (liten ADR; kom ihåg
   `Sandbox.get({resume:false})`-lärdomen från #156-boten).
4. **Operatörens kvarvarande klick-checkar:** #228 Ändra→steg-hopp,
   modul-dialogen (#245/#249) visuellt, manuell 1–10-score i Backoffice
   (Idag-vyn). Öppettider-checken GODKÄND i natt; mörkblå-checken gav
   stylist-scope-frågan (punkt 2). OBS: operatören bör STARTA OM sin
   dev-server så nattens fixar (B163/B164/B174 + prune-on-dev-start) gäller.
5. **Starter-hygien-slice (kräver operatörs-OK, plattform-pins):**
   `engines`-fält i starters, `allowScripts` för sharp, transitiv
   msw-spårning, beslut om docs-base/portfolio-base ska runtime-mappas
   (idag medvetet omappade — aktivering = governance-slice i
   scaffold-kontraktet, inte bara filer på disk).
6. **#156 hosted `/live`** — parkerad (säkerhet), arkitektur-referens; görs om
   på färsk bas med auth/rate-limit när runtime-spåret väljs aktivt.
7. **Branch-rester för operatörsbeslut:** `cursor/gap-3a-offer-service-guard`,
   `cursor/dossier-intake-v11-review-895d`, `feat/kor-5-repair-pass` (ingen
   PR, ej bevisat mergade), `cursor/preview-runtime-adapters` (avsiktlig
   snapshot), Christophers stängda `feat/viewser-ui-overhaul`/
   `feat/viewser-router-decision-readiness`. (`rescue/openclaw-f1-d76ad9c`
   är raderad efter verifiering.)
8. **Christopher-koordinering:** msg-0060 (B166) + msg-0061 (#262 rörde
   FloatingChat, heads-up B173/Tier 1, sandbox-primär, main-sync-avisering
   kommer) väntar på kvittens. B169-uppföljning i hans lane noterad.
9. **Delade canvases (nytt, Steward-ägt):** `docs/canvases/` innehåller
   begreppskartan + openclaw-flödet som interaktiva canvases, delade via
   git. Spegla lokalt med `python scripts/sync_canvases.py`; fakta-blocket
   hålls i synk med `python scripts/update_canvas_facts.py --check` (körs
   även automatiskt post-merge på `main` via steward-auto-bump). Rutin och
   ägarskap: `docs/canvases/README.md` + orchestrator-playbookens
   Steward-avsnitt.

### Kända småsaker (inte buggar)

- `C:\Users\jakem\Desktop\sb-wt-hygiene` — tom kvarlåst worktree-katalog
  (fil-lås av process); git-registret är prunat. Försvinner vid omstart eller
  manuell radering. Ofarlig.
- Döda regel-länkar efter regelkonsolideringen 29→12 (#218) är fixade i alla
  AKTIVA docs 2026-06-10 (`branch-discipline.md` → `04-branch-and-team.md`,
  `reply-style.md` → `01-language-and-reply.md`). Arkiv + ADR:er behåller
  medvetet sina historiska stavningar — markdown-varningar därifrån kan
  ignoreras.
- Två gamla filer med blandade radslut (CRLF+LF): `docs/archive/current-focus-
  history-2026-05-26.md`, `governance/policies/scaffold-contract.v1.json` —
  harmlöst, medvetet orört.

## Historik

Allt äldre än toppblocket ovan är flyttat till
[`docs/archive/2026-06/handoff-history-2026-06-09.md`](archive/2026-06/handoff-history-2026-06-09.md)
(arkiv = historik, inte sanningskälla — verifiera mot git). Hela
versionshistoriken finns kvar via `git log --follow docs/handoff.md`.

## Föregående checkpoint

### 2026-06-10 UTC — handoff.md före `3674475`

**Datum:** 2026-06-10 natt (UTC+2), efter PR #252-main-syncen. Verifierad
`main` = `jakob-be` = `e6a06a5` (ren övertagning av merge-tåget #238-#251 +
#225, tom diff verifierad, CI grönt). Post-merge-sanity: governance 19/19,
rules_sync OK, ruff 0, term-coverage --strict OK, riktade sviter gröna.

Nya PRs sedan dess checkpoint: PR #252 (sync jakob-be→main). Därefter kom
nattens runda 2 (#254/#256/#257/#259/#260 på `jakob-be`, #255 på `main`) —
se toppblocket.
