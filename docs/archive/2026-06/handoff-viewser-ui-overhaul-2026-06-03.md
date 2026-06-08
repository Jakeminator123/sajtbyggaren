---
status: historical
owner: ui
truth_level: historical-reference
last_verified_commit: f56ac30
---

# Handoff: Viewser UI (utan auth/billing) → main

> **Arkivnot (lane A, 2026-06):** Historisk handoff. Flyttad från
> `docs/handoff-viewser-ui-overhaul-2026-06-03.md`. Superseded av
> `docs/current-focus.md` + `docs/handoff.md` (toppblock). Arkiv = historik,
> inte sanningskälla — se `docs/archive/README.md`.

Datum: 2026-06-03
Lane: Christopher (UI)
Branch: `feat/viewser-ui-overhaul` (off `main` @ `1d6e069`)
Ersätter: PR #150 (`christopher-ui`), som stängs.

## Varför den här PR:en finns

PR #150 visade sig vara en sammanhållen helrenovering av hela Viewser-UI:t
(126 filer, ~7000 rader), inte fyra fristående småfeatures. Feature-slicarna
satt ovanpå en gemensam ombyggd grund (builder + marknadssajt) som bara
fanns som buntade commits, så en ren C1/C2/C3/C4-split var inte möjlig utan
hög risk för icke-byggande mellan-PR:er.

Den enda rena separationsaxeln var **auth/billing vs resten av UI:t**. Den
här PR:en tar därför med hela UI-framsteget men **parkerar auth/billing** helt
(ingen auth-kod alls på branchen). Auth/billing lever kvar på
`christopher-ui` och återkommer som en egen PR när operatören slår på den
ytan (durable store + claim-token + kreditmätningspunkt).

## Vad som ingår (auth-fritt)

- Publik marknadssajt: route-split `(marketing)`/`(console)`, hero med
  prompt-form, bildvägg (`ProfessionGrid`), per-yrke-landningssidor, om-oss,
  produkt, kontakt, legal-sidor, cookie-consent, sitemap/robots.
- Builder- och wizard-överhalning: `FloatingChat` med första-gångs-hint som
  förklarar kärnloopen (följdprompt → ny version) + djuplänk till versioner,
  verktygsmeny, inspector, viewer-panel.
- Kärnloops-ux: prompt-route exponerar exakt change-set (`run-change-set`)
  + `appliedCopyDirectives`; `FloatingChat` visar bekräftade ändringar i
  stället för prompt-heuristik; ärlig "ingen synlig effekt"-rad.
- Preview-runtime (bite C): `app/api/preview/[siteId]/route.ts` mot
  runtime-kontraktet med ärliga fel i stället för tyst fallback.
- Starters-banan: yrkessidor + hero-chips + studio-onboarding som
  förifyller wizarden via en lätt seed.
- Robusthet: error-boundary, toast-system, retry-card, skeleton-states.

## Vad som är parkerat (ej på branchen)

Hela auth/billing-ytan: `app/(auth)/*`, `konto`, `priser`, `app/api/auth/*`,
`app/api/checkout/*`, `app/api/stripe/*`, `claim-site`, `lib/auth/*`,
`lib/billing/*`, `auth-config`, `proxy.ts`, samt `better-sqlite3`/`stripe`-
deps. De delade filerna (`marketing-header`, `prompt-builder`, layout, deps,
`.env.example`) är de-authade: ingen kvarvarande auth-import, ingen död länk
till parkerade routes.

`STUDIO_HREF` flyttades från `auth-config` till en ny auth-fri
`lib/routes.ts`.

## Källlås / tester

- Auth-specifika source-lock-tester borttagna; UI-tester anpassade till den
  auth-fria verkligheten (header utan login/Priser, sitemap utan `/priser`).
- Konsol-guarden (`test_viewser_prompt_primary`) pekar nu på
  `(console)/studio/page.tsx` (konsolen flyttad dit; `(marketing)` äger "/").
- Ny framåtriktad spärr `test_build_pipeline_has_no_auth_or_credit_imports`
  säkrar att bygg-ingångarna aldrig importerar auth/billing.
- `check_term_coverage.py` fick de nya UI-symbolerna allowlistade (auth-
  symbolerna medvetet utelämnade — parkerade).

## Verifiering (lokalt, 2026-06-03)

- `tsc --noEmit` 0, `eslint` 0, `ruff check` 0, `ruff format --check` rent
- `check_term_coverage.py --strict` OK
- `governance_validate` 18/18, `rules_sync --check` i synk
- Hela `pytest tests/` grön (3 skips: nätverk/E2E/slow-build)

Full `next build` av Viewser kördes inte lokalt (nätverk nere; Google Fonts-
hämtning kräver uppkoppling). tsc + eslint + source-lock-sviten täcker
kontrakten; verifiera bygget i CI.
