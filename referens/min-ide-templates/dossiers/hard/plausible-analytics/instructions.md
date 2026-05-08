# When to use

Use this dossier when the brief explicitly asks for **Plausible Analytics** or for a **privacy-friendly / cookieless** analytics solution. Triggers (Swedish + English): `plausible`, `cookieless analytics`, `privacy.?friendly analytics`, `gdpr.?safe analytics`, `cookielös analys`, `integritetsvänlig statistik`.

Best fit:

- Sites that want page-view + referrer + UTM tracking without a cookie banner.
- Brand sites where the team already uses the Plausible dashboard.
- EU-hosted projects that prefer Plausible's GDPR posture over Vercel Analytics.

Do not use for:

- Generic "add analytics"-prompts on a Vercel-hosted project — `vercel-analytics` is the default and needs zero env config there.
- Funnel/event-based analytics that need custom event tracking — Plausible supports it but the dossier ships the basic page-view script only; extend in a follow-up.
- Heatmaps / session-replay — Plausible does not provide them.

Both this dossier and `vercel-analytics` target the `analytics` capability. The codegen picks `vercel-analytics` by default (it has `defaultForCapability: true`); set `defaultForCapability: true` here only if you fork the project to make Plausible the canonical choice.

# How to integrate

Mount `<PlausibleAnalytics />` once in `app/layout.tsx` so the script runs on every route. The component is a client component but contains no hooks — it renders a single `next/script` tag with deferred loading.

```tsx
// app/layout.tsx
import type { Metadata } from "next";
import { PlausibleAnalytics } from "@/components/plausible-analytics";

export const metadata: Metadata = { title: "Bönan & Boken" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv">
      <body>
        {children}
        <PlausibleAnalytics />
      </body>
    </html>
  );
}
```

The component reads `process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN` at build time (Next.js inlines it into the client bundle because of the `NEXT_PUBLIC_` prefix). When the value is empty or whitespace the component renders `null` so missing config never breaks the build or pollutes dev consoles.

# API contract

```tsx
/**
 * Renders the Plausible tracking script. No props — configuration is
 * environment-driven so the same component works across dev / preview /
 * production without per-environment branching in the consumer.
 *
 * Behavior:
 *  - NEXT_PUBLIC_PLAUSIBLE_DOMAIN unset → renders null (script omitted).
 *  - NEXT_PUBLIC_PLAUSIBLE_API_HOST unset → uses https://plausible.io.
 *  - Always async (Script strategy "afterInteractive") so it never blocks
 *    LCP on the host site.
 */
declare function PlausibleAnalytics(): JSX.Element | null;
```

# Composition rules (the LLM should follow these without being asked)

- Mount **once** in the root layout. Do not duplicate per route — Plausible auto-tracks SPA-style route changes when mounted at the root.
- Do not wrap in `Suspense` — the script tag carries no async children and `Suspense` adds no value here.
- Do not add `<noscript>` fallbacks — Plausible's no-script tracking endpoint exists but is opt-in and outside the scope of this dossier.
- Do not gate behind a cookie consent banner — the entire selling point of Plausible is that no banner is needed.

# Env contract (do not break this)

| Key | Required | Why it lives in the public env (NEXT_PUBLIC_*) |
|---|---|---|
| `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` | yes | The script tag's `data-domain` attribute is read client-side; the value is non-secret by design (Plausible's dashboard auth is separate). |
| `NEXT_PUBLIC_PLAUSIBLE_API_HOST` | no | Optional override for self-hosted instances. Defaults to `https://plausible.io`. Same non-secret reasoning. |

The placeholder system in `config/ai_models/40-harmless-placeholders.env.txt` should treat both keys as **harmless** (they are public-facing strings, not secrets) so F2 preview boots without configuration. F3 ("Bygg integrationer") still requires `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` to be a real domain before deployment.

# Verification checklist (per `lastVerified`)

- [ ] Build a sample site that includes `PlausibleAnalytics` in the root layout.
- [ ] Confirm `NEXT_PUBLIC_PLAUSIBLE_DOMAIN=""` produces no `<script>` tag in the rendered HTML and emits no console errors.
- [ ] Confirm a real domain produces a single `<script async defer src="https://plausible.io/js/script.js" data-domain="…">` with no duplication on client navigation.
- [ ] Confirm `NEXT_PUBLIC_PLAUSIBLE_API_HOST=https://analytics.example.com` swaps the script host but keeps the same `data-domain` attribute.
