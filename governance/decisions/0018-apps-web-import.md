# ADR 0018 - apps/web import från Sajtmaskin (Christopher's UI)

**Status:** proposed
**Datum:** 2026-05-11
**Beroenden:** ADR 0001 (policies as source of truth), ADR 0004 (migration from
sajtmaskin baseline), ADR 0006 (term discipline), ADR 0012 (vocabulary
compression).

## Kontext

`Jakeminator123/sajtbyggaren` är en kontrollerad ombyggnad av
`Jakeminator123/sajtmaskin`. Roadmapen säger att `apps/` är "användar-UI som
byggs sist". Idag finns bara `apps/viewser/` — en localhost-only
operator-prototyp som explicit *inte* är platsen för den publika UI:n.

Christopher har under flera veckor byggt UI/UX i sajtmaskin (branch
`frontend/christopher`): Apple-inspirerad design, brandbook-token-system,
55 shadcn-primitiver, layout-shell (Navbar/Footer/CookieBanner/JSON-LD),
landing-v2-komponenter, marknadssidor (om/priser/faq/terms/privacy/blogg)
och 385 SEO-landningssidor. Detta arbete riskerade att gå förlorat när
sajtbyggaren-roadmapen lade `apps/` sist.

Den här ADR:n låser placeringen och scopet för en första import.

## Beslut

### 1) Christopher's UI lever i en NY `apps/web/`

Inte i `apps/viewser/` — viewser är en localhost-only operator-prototyp,
inte en publik produkt (ADR-aligned med viewsers egen README).
Inte i `packages/preview-runtime/` — det är en runtime-package, inte en
användar-app.

`apps/web/` har:

- Egen `package.json` med Next 16 + React 19 + Tailwind 4 + shadcn 4
  (radix-vega-style, slate base) — matchar viewser-stacken.
- Dev-port `3001` (viewser har `3000`).
- Egen `tsconfig.json` med `paths: { "@/*": ["./*"] }` — ingen
  monorepo-tsconfig-kedja.

### 2) Vad importen INNEHÅLLER

Från `Jakeminator123/sajtmaskin` branch `frontend/christopher`:

- `src/components/ui/*` (55 shadcn-primitiver) → `apps/web/components/ui/`
- `src/components/layout/*` → `apps/web/components/layout/`
- `src/components/landing-v2/*` → `apps/web/components/landing-v2/`
- `src/components/forms/voice-recorder.*` → `apps/web/components/forms/`
- `src/styles/landing-v2.css` → `apps/web/styles/`
- `src/app/{globals.css,layout.tsx,error.tsx,not-found.tsx,global-error.tsx}`
  → `apps/web/app/`
- `src/app/{om,faq,terms,privacy,blogg}/page.tsx` (statiska marknadssidor)
- `src/app/{robots.ts,opengraph-image.tsx}` (oförändrade förutom
  brand-byte Sajtmaskin → Sajtbyggaren).
- `src/app/sitemap.ts` (omskrivet — inga SEO-landings än).
- `src/lib/{utils,app-url,project-client}.ts` + minimal `lib/config.ts`.
- `src/lib/builder/build-intent.ts` (typsäker utility utan beroenden).
- `src/lib/hooks/use-mobile.ts`.
- `src/types/audit.ts`.
- `src/content/seo/{config,types}.ts` (för Footer-länkar).
- `tailwind.config.cjs` + `postcss.config.mjs`.
- `public/*` (förutom `public/video/` — 48 MB hero-video).
- En **omskriven** `app/page.tsx` — en lugn statisk landningssida som
  använder Navbar + Footer, *inte* hela builder-flödet.
- En **omskriven** `app/priser/page.tsx` — statisk pris-sida som ersätter
  redirect-till-`/buy-credits`-logiken.

### 3) Vad importen INTE INNEHÅLLER

Detta krockar med pipelinen som drivs av `backend.py` +
`packages/generation/` (operator-flödet i [README.md](../../README.md)) och
ska INTE klistras in:

- `src/app/{builder,new,skapa-hemsida}/` — site-generation drivs av
  `backend.py` + `packages/generation/`.
- `src/app/{admin,log,logg,projects,buy-credits,avatar}/` — operator/admin-
  surfaces hör inte hit.
- `src/app/api/` — REST-routes är inte del av apps/web. När apps/web behöver
  data ska den anropa partner-API:t som sajtbyggaren bygger separat.
- `src/components/{builder,auth,openclaw,audit,modals,ai-elements,templates,kostnadsfri}/`.
- `drizzle/`, `drizzle.config.ts`, `services/`, `templates_v0/`, `evals/`,
  `e2e/`, `tests/`, `frontend/`, `output/`, `reviews/`, `audit-reports/`,
  `master-integration-plans/`, `preview-host/`.
- `vercel.json`, `.vercel/` — sajtbyggaren har egen deploy-strategi.
- 385 SEO-landningar under `src/content/seo-landings/{ai,city,city-usecase,compare,industry,usecase}/*.json` + tillhörande `src/lib/seo/{load-landing,render-seo-page,json-ld}.ts`. Och routerna `ai-hemsida/[variant]`, `alternativ-till/[konkurrent]`, `hemsida-for/[bransch]`, `kostnadsfri/[slug]`, `category/[type]`, `templates/`, `landningssidor/` som konsumerar dem. Dessa kommer i en uppföljnings-ADR när vi bestämt vart content ska ligga (apps/web/content/ vs governance/content/) och om det fortfarande ska genereras från sajtmaskin-pipelinen.

### 4) Stubs istället för full backend

Komponenter som `navbar.tsx`, `header-actions.tsx` och `site-audit-section.tsx`
importerar `useAuth`, `AUDIT_COSTS` och `createProject`. För att bevara
deras render-shape utan att dra in Drizzle/Stripe/OAuth har vi:

- `apps/web/lib/auth/auth-store.ts` — stub som returnerar
  `isAuthenticated: false`, `diamonds: 0`, no-op `logout`/`fetchUser`.
- `apps/web/lib/credits/pricing.ts` — bara konstanten `AUDIT_COSTS`.
- `apps/web/lib/project-client.ts` — fulla fetch-funktioner som kommer
  fela snyggt mot `/api/*` tills apps/web får en backend.
- `apps/web/components/layout/shader-background.tsx` — gradient-fallback
  som ersätter `@paper-design/shaders-react` (~30 MB shader-bibliotek).

När apps/web får riktig auth/pricing/project-API ersätts dessa filer
1:1 utan att UI-koden behöver röras.

### 5) Brand-konvergens

Importen byter "Sajtmaskin" → "Sajtbyggaren" i:

- `metadata.title.default` + `metadata.title.template` i `app/layout.tsx`.
- `siteName` i openGraph.
- `<noscript>`-fallback.
- `og-image`-text.

`Pretty Good AB` står kvar som operator-företag enligt README.

## Konsekvenser

- `apps/viewser/` påverkas inte. Den fortsätter köra på `:3000`.
- `governance/policies/` påverkas inte. apps/web är konsument av
  policies, inte källa.
- Sajtbyggaren får en publik landningsyta i samma takt som
  `packages/generation/` mognar — inte efteråt.
- Christopher's UI-arbete är bevarat och versionshanterat på branchen
  `frontend/christopher-import` (i sajtbyggaren) plus säkerhetsbranchen
  `backup/frontend-christopher-pre-migrate-2026-05-11` (i sajtmaskin).

## Vad detta INTE är

- **Inte en migration av builder-pipelinen.** `apps/web` har ingen builder.
- **Inte en migration av databas eller auth.** Drizzle, OAuth, Stripe,
  OpenClaw är inte med.
- **Inte ersättning av `apps/viewser`.** Viewser är operator-prototyp;
  apps/web är publik UI. De har olika syften.
- **Inte komplett SEO-landningsmotor.** 385 JSON-content-filer + lib/seo
  väntar på uppföljnings-ADR.

## Term-coverage

`scripts/check_term_coverage.py` (utan `--strict`) rapporterar ~500 nya
kandidater under `apps/web/components/ui/` och `apps/web/components/
landing-v2/`. Nästan samtliga är shadcn-/Radix-implementation-symboler
(`AccordionContent`, `AvatarImage`, `BreadcrumbList` etc.) — samma princip
som tidigare hanterats för `apps/viewser`-symboler i `COMMON_WORDS`.

Skriptets docstring säger uttryckligen att det är "ett diagnosverktyg,
inte en hård gate. Hård gate kommer först när ordlistan är stabilare."
För att slå på `--strict` lägger en uppföljnings-PR in en
`COMMON_WORDS`-utvidgning analog med viewser-blocket eller
exkluderar `apps/web/components/ui/` direkt i `iter_files()`. Inom
`frontend/christopher-import` ändras inte `check_term_coverage.py`.

## Verifiering

`apps/web` anses levererad när:

- `cd apps/web && npm install && npm run dev -p 3001` startar utan fel.
- Alla importerade sidor (`/`, `/om`, `/priser`, `/faq`, `/blogg`,
  `/terms`, `/privacy`) renderas utan runtime-fel.
- `apps/viewser` är fortfarande oförändrad (`cd apps/viewser && npm run dev`
  på `:3000`).
- `python scripts/governance_validate.py` är grön.
- `python scripts/check_term_coverage.py` är grön (eller termer som
  introduceras har registrerats där det krävs).
