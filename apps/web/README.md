# apps/web

`apps/web` är den publika UI:n för Sajtbyggaren. Den är en import av UI/UX-arbetet
från `Jakeminator123/sajtmaskin` (branch `frontend/christopher`) och innehåller:

- Design-system (`components/ui/`) — shadcn 4 i `radix-vega`-style
- Layout-shell (`components/layout/`) — header, footer, nav, JSON-LD, cookie banner
- Landing-v2-komponenter (`components/landing-v2/`)
- Marknadssidor (om, priser, faq, terms, privacy, kostnadsfri, hemsida-for, alternativ-till, ai-hemsida, blogg, category)
- SEO-byggblock (sitemap, robots, opengraph)

## Vad apps/web INTE är

- **Inte en builder.** Site-generation drivs av `backend.py` + `packages/generation/` enligt operator-flödet i [`/README.md`](../../README.md).
- **Inte en operator-prototyp.** Det är `apps/viewser/`.
- **Inte ansluten till databas eller auth.** Drizzle, API-routes, OpenClaw, payments
  m.m. som fanns i `Sajtmaskin_Genberg` är **inte** med i denna import. De krockar
  med nya repots governance-drivna pipeline.

## Stack

- Next.js 16 + React 19 + Tailwind 4 + shadcn 4 (radix-vega)
- Radix UI + Base UI (shadcn-komponenterna kommer från Sajtmaskin som redan är på
  Tailwind 4)

## Setup

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Öppna [http://localhost:3001](http://localhost:3001) (`apps/viewser` kör på `:3000`).

## Scope-beslut vid import

Se [`governance/decisions/0013-apps-web-import.md`](../../governance/decisions/0013-apps-web-import.md)
för varför vissa delar av Sajtmaskin **inte** togs med (builder, admin, openclaw,
api, drizzle, auth, payments).
