# When to use

Use this dossier when the brief declares the `auth` capability — the site needs real user accounts (login, signup, password reset, gated content). Triggers (Swedish + English): `auth`, `login`, `sign in`, `sign up`, `register`, `account`, `inloggning`, `registrering`, `logga in`, `konto`, `medlem`, `medlemssida`, `gated`, `protected route`, `dashboard requires login`.

Best fit:

- A SaaS landing page with a "Sign in" / "Get started" CTA that opens Clerk's hosted modal.
- A protected `/dashboard` (or `/app`) area that requires an authenticated user.
- A community / membership site where the public landing is open but `/medlem` is gated.

Do not use for:

- A pure marketing site with no logged-in surface (do not mount `<ClerkProvider>` "just in case" — it adds ~50KB to the client bundle).
- Custom OAuth flows where you control the IdP yourself (use `next-auth` / Auth.js with the `credentials` provider instead).
- B2B SSO with self-served SAML config (Clerk supports it but the setup is multi-step and beyond a generic dossier).

# How to integrate

The dossier ships three files. Drop each one in unchanged unless explicitly overridden:

1. **`components/middleware.ts` → `middleware.ts` at the project root** (verbatim). Clerk's middleware must live at the project root, not under `app/`, and the `matcher` syntax is load-bearing — paraphrasing the regex breaks session resolution on dynamic routes.
2. **`components/clerk-provider-shell.tsx` → `components/clerk-provider-shell.tsx`** (verbatim). Wrap the entire `<body>…</body>` of `app/layout.tsx` in `<ClerkProviderShell>`. The shell adds an unconfigured-state fallback so the app does not crash when keys are missing in development.
3. **`components/auth-buttons.tsx` → `components/auth-buttons.tsx`** (rewritable). Use `<AuthButtons />` in the site header / nav. You may restyle freely — change text, swap buttons for icon-only avatars, add a dropdown — but keep the `<SignedIn>` / `<SignedOut>` boundaries intact.

Minimal `app/layout.tsx`:

```tsx
import { ClerkProviderShell } from "@/components/clerk-provider-shell";
import { AuthButtons } from "@/components/auth-buttons";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv">
      <body>
        <ClerkProviderShell>
          <header className="flex items-center justify-between border-b px-4 py-3">
            <a href="/" className="font-semibold">Min sajt</a>
            <AuthButtons />
          </header>
          {children}
        </ClerkProviderShell>
      </body>
    </html>
  );
}
```

To gate a route (e.g. `/dashboard`), redirect unauthenticated users from the server component:

```tsx
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");
  return <main className="p-6">Welcome, {userId}.</main>;
}
```

# UX rules

- Render `<SignInButton mode="modal">` for the primary CTA — modal mode keeps the user on-page and converts better than redirecting to `/sign-in`. Use redirect mode only when you need a deep-linked sign-in URL.
- Show `<UserButton afterSignOutUrl="/" />` (avatar + dropdown) in the top-right when signed in. It handles account management, switch-org, and sign-out without you writing menu code.
- Always pair `<SignedIn>` and `<SignedOut>` so the header does not flash the wrong state on first paint.
- For protected pages, do the redirect in a Server Component (`auth()` + `redirect()`) — never in a `useEffect`. Client-side redirects flash the gated content for ~1 frame and leak it to scrapers.
- Localize Clerk's UI when the brief is Swedish: pass `localization={svSE}` to `<ClerkProvider>` (`import { svSE } from "@clerk/localizations"` — adds a small bundle). The shell already exposes a `localization` prop for this.

# Avoid

- Do not put `CLERK_SECRET_KEY` in a `NEXT_PUBLIC_*` variable. The secret key grants full backend access to your Clerk instance — exposing it in the client bundle is a critical leak.
- Do not move `middleware.ts` inside `app/`. Next.js only picks up the file at the project root.
- Do not call `auth()` inside a Client Component — it only works in Server Components, Route Handlers, and middleware. From the client, use the `useUser()` / `useAuth()` hooks instead.
- Do not wrap `<ClerkProvider>` around individual pages. Mount it once in the root layout; mounting per-page resets the session on every navigation.
- Do not invent your own "remember me" or "session refresh" logic. Clerk handles token refresh transparently via the middleware.

# Verification

- Visit `/sign-in` — Clerk's hosted form renders.
- Sign up with a throwaway email → land back on `/` with the avatar visible in the header.
- Reload the page — still signed in (session cookie survives).
- Visit a protected route (e.g. `/dashboard`) signed-out → redirected to `/sign-in`.
- Remove `CLERK_SECRET_KEY` from `.env.local` and restart `next dev` — the page renders an "Auth not configured" placeholder banner instead of a blank screen / 500.
- Open the Network tab and confirm no request includes a `sk_…` token (the secret key must never reach the client).
