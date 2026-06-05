# Körschema — agent-prompter

Sekvens: P0 -> P1 -> ... Varje prompt är självbärande (agenten ser inte den här
kontexten). Kör en i taget, läs av leveransen, gå vidare. Alla prompter ärver
spelreglerna i `README.md`.

Beroenden: P0 (beslut) först. P1 (deploy-skal) och P2 (bygg-worker) kan delvis
parallelliseras efter P0. P3 kräver P2. P4 kräver P1 och P3. P5 löpande.

---

## P0 — Discovery och ADR:er (skriver bara ADR/docs)
```
Du är arkitekt-agent i repot Sajtbyggaren (monorepo: Python-governance och -builder
plus apps/viewser i Next.js). Mål för hela spåret: gå från dagens LOKALA
operatörsverktyg till en HOSTAD produkt där användarens sajter byggs och
förhandsvisas i sandboxar (v0- eller Lovable-likt, iframe med chatt). DENNA uppgift
är bara discovery och beslut — skriv ingen feature-kod, bara ADR:er och docs.

Läs först: hela docs/vercel-sandbox-migration/, docs/handoff.md (översta blocken),
AGENTS.md, docs/product-operating-context.md, governance/decisions/0028/0030/0033/0034,
samt apps/viewser/lib/{vercel-sandbox-runner,vercel-sandbox-sessions,
preview-runtime-server,build-runner,hosted-python-runtime,localhost-guard}.ts och
apps/viewser/app/api/{prompt,preview/[siteId]}/route.ts.

Uppgift: skriv en ADR per gap G1-G7 (se 01-arkitekturval.md) under
governance/decisions/ (nästa lediga nummer). Varje ADR: kontext, alternativ, beslut,
konsekvenser. Välj en konkret väg (rekommendationerna i 01-arkitekturval.md är
utgångspunkt, inte facit). Uppdatera 01-arkitekturval.md med valda nummer.

Leverabler: ADR-filer plus uppdaterad 01-arkitekturval.md. Ingen kod.
Acceptans: governance_validate, rules_sync --check och check_term_coverage --strict
gröna; varje ADR har ett tydligt beslut.
Spelregler: se README.md. Egen branch, PR, ej merge till main. Rör ej heavy-llm-flow.
```

## P1 — Deploya viewser-skalet bakom auth
```
Du är deploy-agent. Mål: deploya operatörsappen apps/viewser till Vercel bakom auth,
UTAN att flytta byggorkestreringen än (den lever vidare lokalt och feature-flaggad
tills P2).

Läs först: docs/vercel-sandbox-migration/00-nulage-och-mal.md och 01-arkitekturval.md
(G4), ADR:n för auth-och-tenant (från P0), apps/viewser/lib/{localhost-guard,
hosted-python-runtime}.ts, apps/viewser/app/api/*/route.ts, apps/viewser/next.config.ts,
apps/viewser/.env.example. Plugin-skillarna auth och vercel-cli är relevanta.

Uppgift:
1. Inför auth (enligt ADR) i middleware; scope:a preview och prompt per användare.
2. Gör localhost-låset till ett env-läge: hostat kräver auth, lokalt kör som idag.
3. Se till att de Python-beroende routerna degraderar tydligt hostat
   (hostedPythonRuntimeUnavailable) tills P2 är klar — feature-flagga bygg/preview.
4. Wire env: OIDC är automatiskt på Vercel; sätt blob- och databas-env via projektet.
5. Gör en preview-deploy och verifiera att UI:t laddar och att auth fungerar.

Leverabler: kod på branch plus en kort docs-uppdatering här om vad som deployats och
vad som är feature-flaggat.
Acceptans: tsc, eslint, ruff, pytest, governance, rules_sync, term-coverage gröna;
preview-deploy laddar bakom auth; localhost-läget oförändrat.
Spelregler: README.md. Egen branch, PR, ej merge. Rör ej heavy-llm-flow.
```

## P2 — Bygg-worker i sandbox plus blob-output
```
Du är bygg-runtime-agent. Mål: en användarsajt kan BYGGAS utan lokal Python — kör
generation-pipen i en sandbox och skriv output till blob-lagring (enligt ADR för
bygg-runtime och artifact-store från P0).

Läs först: 01-arkitekturval.md (G1 och G2), ADR:erna för bygg-runtime och
artifact-store, scripts/build_site.py, scripts/prompt_to_project_input.py,
packages/generation/, apps/viewser/lib/{build-runner,vercel-sandbox-runner}.ts.
Plugin-skillarna vercel-sandbox (SDK-mönster: skapa sandbox, runCommand, snapshot)
och vercel-storage (blob) är relevanta.

Uppgift:
1. Paketera generation-pipen så den kör i en sandbox (node24 har python3). Ladda upp
   nödvändiga paket och scripts, kör build_site.py i sandboxen.
2. Skriv bygg-output (den färdiga builden plus artefakter) till blob-lagring, inte
   lokal disk. Ersätt lokal-disk-antagandena i bygg- och preview-vägen för hostat.
3. Behåll lokal disk som fallback-läge (env-flagga) så lokal utveckling funkar.
4. Överväg att slå ihop bygg och preview i samma sandbox (B i G1) om ADR:n valde det.

Leverabler: kod på branch plus docs-uppdatering här.
Acceptans: en hostad bygg-körning producerar en preview-bar build i blob-lagring;
lokal väg oförändrad; alla guards gröna.
Spelregler: README.md. Egen branch, PR, ej merge. Rör ej heavy-llm-flow.
```

## P3 — Durabelt sessionsregister, snapshots och livscykel
```
Du är preview-livscykel-agent. Mål: gör previewen durabel och snabb.

Läs först: 01-arkitekturval.md (G3, G5, G7), ADR:erna för session-store,
sandbox-snapshots och sandbox-lifecycle, apps/viewser/lib/{vercel-sandbox-sessions,
vercel-sandbox-runner,preview-runtime-server}.ts. Plugin-skillarna vercel-sandbox
(snapshot-avsnittet) och vercel-storage (nyckel-värde-lagring).

Uppgift:
1. Ersätt minnes-sessionsregistret med ett delat lager (siteId eller userId till
   sandbox-id, url, ttl) som överlever instansbyten; återanslut via sandbox-namnet.
2. Inför snapshots: en bas-snapshot med förinstallerade beroenden så previewen bootar
   på under en sekund i stället för ~30 s. Dokumentera hur snapshoten byggs om.
3. Livscykel: idle-stop, ttl-städning, kvoter per användare, kostnadsloggning från
   stopp-signalerna.

Leverabler: kod på branch plus docs-uppdatering här (inkl. hur snapshot återskapas).
Acceptans: preview överlever en serverless-kallstart; mätt uppstart under några
sekunder med snapshot; sandboxar läcker inte (ttl och idle-stop verifierad). Guards gröna.
Spelregler: README.md. Egen branch, PR, ej merge. Rör ej heavy-llm-flow.
```

## P4 — Modern preview-yta (v0- eller Lovable-känsla)
```
Du är preview-yt-agent. Mål: höj previewen till v0- eller Lovable-känsla.

Läs först: 01-arkitekturval.md (G6), ADR:n för preview-ux, apps/viewser/components/
{viewer-panel,builder/floating-chat}.tsx, apps/viewser/components/error-boundary.tsx.

Uppgift (välj delmängd enligt ADR, leverera inkrementellt):
1. Streaming av byggloggar i UI:t under bygget (inte bara en spinner).
2. Element-inspektor och klicka-för-att-redigera via postMessage mot iframe:n
   (kopplar till det site-inspector-spår som redan finns i koden).
3. Versionshistorik plus delbara länkar till en specifik version eller preview.
4. Tydlig "ingen synlig ändring kunde appliceras"-signal (appliedVisibleEffect false)
   så följdprompter aldrig ljuger om resultatet.

Leverabler: kod på branch plus docs-uppdatering här.
Acceptans: previewen visar live-loggar plus minst en redigerings- eller
inspektionsinteraktion; no-op-följdprompter visar en ärlig signal; tsc och eslint
rena; alla guards gröna.
Spelregler: README.md. Egen branch, PR, ej merge. Rör ej heavy-llm-flow.
```

## P5 — Hårdning, buggar och kostnad
```
Du är hårdnings-agent. Mål: stäng de två kvarvarande buggarna plus kostnadsskydd.

Läs först: docs/handoff.md (bugg A och B), 01-arkitekturval.md (G8),
scripts/build_site.py, packages/generation/{repair,quality_gate,codegen,followup}/,
apps/viewser/lib/build-runner.ts.

Uppgift:
1. Bugg A: garantera att en avbruten eller hård-killad körning antingen skriver
   build-result.json (status failed) eller markeras failed i run-historiken — så den
   aldrig hänger pending eller grå för evigt; säkerställ att current.json bara
   promotas på ok.
2. Bugg B: implementera riktig layout-codegen (sprint 3B) för de vanligaste intenten
   (centrera hero, lägg till gallery) så följdprompten ger en synlig ändring.
3. Den lilla copy-buggen: instruktionsordet "exakt:" läcker in i copy-texten via
   copy-direktiv-extraktionen i packages/generation/followup/copy_directives.py — fixa.
4. Kostnad och observability: kvoter per användare plus loggning.

Leverabler: kod och tester på branch plus docs-uppdatering här.
Acceptans: avbrutna byggen hänger inte längre; en layout-följdprompt ger en
verifierbar synlig ändring; copy-läckan borta; nya tester gröna; alla guards gröna.
Spelregler: README.md. Egen branch, PR, ej merge. Rör ej heavy-llm-flow.
```
