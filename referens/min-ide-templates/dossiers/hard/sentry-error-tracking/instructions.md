# When to use

Use this dossier when the brief declares the `error-tracking` capability — the site needs production crash reporting + light performance monitoring. Triggers (Swedish + English): `Sentry`, `error tracking`, `crash reporting`, `monitoring`, `observability`, `felrapportering`, `kraschrapporter`, `övervakning`, `know when the site breaks`, `production alerts`.

Best fit:

- A SaaS dashboard or production app where silent failures lose paying users.
- A high-traffic marketing site where a deploy regression should page someone.
- An e-commerce checkout where a single broken render = lost revenue.

Do not use for:

- Pre-launch dev/preview-only sites — leave `NEXT_PUBLIC_SENTRY_DSN` unset and the dossier self-disables.
- Privacy-sensitive sites that cannot send any user-context to a third party (Sentry sends URL, user-agent, and a stack — even with PII scrubbing). For those, prefer a self-hosted alternative.
- Replacement of structured server logs. Sentry is for unexpected exceptions, not for "user clicked button A".

# How to integrate

The dossier ships **four files that mount at the project root** (NOT under `app/` or `components/`). Next.js' instrumentation hook discovers them by file name, so the paths are load-bearing:

| Dossier path | Project path |
|-----|-----|
| `components/sentry.client.config.ts` | `sentry.client.config.ts` |
| `components/sentry.server.config.ts` | `sentry.server.config.ts` |
| `components/sentry.edge.config.ts` | `sentry.edge.config.ts` |
| `components/instrumentation.ts` | `instrumentation.ts` |

All four are `verbatim`. Do not rename, move under `lib/`, or merge them into one file — the Next.js Sentry SDK's auto-discovery breaks if the file names or locations change.

There is no React component to mount. Once the four files are in place, errors thrown in any Server Component, Route Handler, Server Action, or Client Component are captured automatically.

To capture a manually-logged event:

```tsx
import * as Sentry from "@sentry/nextjs";

try {
  await riskyOperation();
} catch (err) {
  Sentry.captureException(err, { tags: { feature: "checkout" } });
  throw err;
}
```

When `NEXT_PUBLIC_SENTRY_DSN` is empty (the default in dev/preview), every `Sentry.init` call no-ops and `captureException` becomes a silent stub. The SDK is still bundled (~30KB gzipped on the client), but no beacons are sent.

# UX rules

- Do not surface raw error messages to end users from anywhere. Render a friendly fallback (`error.tsx` boundary) and let Sentry collect the technical details server-side.
- Set `SENTRY_ENVIRONMENT=preview` in Vercel preview deploys so production dashboards stay clean.
- Keep `tracesSampleRate` low (≤ 0.1) on public marketing pages. Performance traces are quota-heavy.
- For checkout / auth / payment flows, raise sampling temporarily during incidents — but revert before merging back to `main`.
- Add user context only with explicit consent: after sign-in, call `Sentry.setUser({ id })` (never `email` unless your privacy policy covers it).

# Avoid

- Do not put the DSN in a non-`NEXT_PUBLIC_*` env. The client-side init needs it, and the DSN is **not** a secret — it only allows event ingestion, not data read.
- Do not call `Sentry.init` yourself in `app/layout.tsx` or any component. The four config files own initialisation; calling init twice causes duplicate events.
- Do not wrap `next.config.ts` with `withSentryConfig` unless you actually need source-map upload. The wrapper requires `SENTRY_AUTH_TOKEN` + org/project slugs and turns a missing token into a build failure — out of scope for this dossier.
- Do not capture form input or password fields. The default `beforeSend` here strips known sensitive query params, but custom `extra` payloads can still leak — review each `captureException` call.
- Do not enable `replaysSessionSampleRate` without a privacy review. Session Replay records the DOM and can capture inputs unless you mask them explicitly.

# Verification

- Add a temporary `throw new Error("sentry-smoke-test")` to a Server Component, deploy to a Sentry-enabled environment, hit the page → event appears in the Sentry project within ~30 seconds. Remove the throw before merging.
- With `NEXT_PUBLIC_SENTRY_DSN` empty, run `next build && next start` → no network requests to `*.ingest.sentry.io` in DevTools. F3 readiness reports `warn-only` info, not a blocker.
- With a real DSN set, check that `SENTRY_ENVIRONMENT` matches the deploy ring (`production` vs `preview`) in the Sentry event detail.
- Confirm `instrumentation.ts` runs on cold start: server logs include `[sentry] init (server)` once per Node worker boot.
- Open `next.config.ts` — confirm it is NOT wrapped in `withSentryConfig`. Source-map upload is intentionally out of scope here.
