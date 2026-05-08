# When to use

Use this dossier when the brief declares the `analytics` capability and the site will be deployed on Vercel. Vercel Analytics is the lowest-effort way to capture page views and Core Web Vitals without configuring a third-party tracker.

Best fit:

- Marketing sites and landings deployed on Vercel where the team wants page-view counts and LCP/FID/CLS without setting up Google Analytics.
- Early-stage SaaS where Web Vitals matter for SEO and the team has not yet picked a behavioural analytics tool.
- Replacing legacy Google Tag Manager for sites where the only metric being read is page views.

Do not use it for:

- Behavioural analytics with funnels, cohorts, session recording (use PostHog or Amplitude — separate dossier).
- Server-side conversion tracking (use a backend integration with the actual ad network).
- Sites deployed outside Vercel (the auto-injection of the project token only works on Vercel infrastructure; on other hosts the script silently no-ops).

# How to integrate

1. Mount `<AnalyticsProviders />` once, inside the root `app/layout.tsx`, **inside `<body>`** but typically as the last child so it does not affect SSR painting.
2. No env vars are needed — Vercel injects `VERCEL_ANALYTICS_ID` at runtime when the project is deployed.
3. Locally (`next dev`) and on non-Vercel hosts the components self-disable; nothing to switch off manually.
4. View metrics in the Vercel dashboard under the project → Analytics + Speed Insights tabs.

# UX rules

- Do not surface analytics presence in the UI. Tracking should be invisible to the user.
- Respect Do Not Track / `prefers-reduced-data` if the brief calls for strict privacy. If so, swap to a self-hosted analytics dossier instead — Vercel Analytics does not honour DNT.
- For the cookie banner question: Vercel Analytics is **cookieless** by design, so EU consent banners are not required for it alone. (If the site later adds a tracker that does need consent, gate this component behind the same consent flag for consistency.)

# Avoid

- Do not paraphrase `components/analytics-providers.tsx`. The `<Analytics />` and `<SpeedInsights />` imports + the `"use client"` directive must stay byte-exact for the bundler to treeshake correctly and for Vercel to detect the integration.
- Do not mount `<AnalyticsProviders />` inside individual pages — it must live in the root layout once. Multiple mounts double-count page views.
- Do not wrap it in a Suspense boundary; the components are already lazy on the client side.
- Do not pass any props — the API surface is intentionally empty.

# Verification

- Build the site locally with `npm run build` and confirm no errors from `@vercel/analytics` / `@vercel/speed-insights`.
- Deploy to a Vercel preview and visit a page — the Network tab shows a request to `/_vercel/insights/view` (or similar).
- Wait ~30 seconds and refresh the project's Vercel Analytics dashboard — the page view appears.
- In the browser console, no errors mentioning Vercel Analytics should appear in either dev or production.
