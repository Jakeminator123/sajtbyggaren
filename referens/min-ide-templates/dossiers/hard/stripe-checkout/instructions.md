# When to use

Use this dossier when the brief declares the `payments` capability and the site needs to accept money for products, subscriptions, or one-off services.

Best fit:

- A landing page with a "Buy now" / "Get started" CTA that should lead to a paid checkout.
- A SaaS pricing page where each tier needs its own checkout flow.
- A simple product or service shop that does not need a full ecommerce backend.

Do not use it for:

- Free signup flows (use the `auth` capability instead).
- In-app purchases on iOS/Android (different SDK).
- Marketplaces with split payments (needs Stripe Connect — separate dossier).

# How to integrate

1. Place `CheckoutButton` on the page where the user should pay (pricing card CTA, hero CTA, etc.).
2. Pass `priceId` (a `price_…` id from the Stripe dashboard) and a `label`.
3. The button POSTs to `/api/checkout-session`, which creates a Stripe Checkout Session and returns a redirect URL.
4. Stripe handles the actual payment UI, then redirects the user back to `success_url` (default: `/payment-success`) or `cancel_url` (default: `/`).

If `STRIPE_SECRET_KEY` is missing in `process.env` the dossier is selected but **unconfigured**. Render the button in a disabled state with a "Configure Stripe to enable payments" tooltip, so the page still builds.

# UX rules

- Show clear pricing next to the button (currency + interval, e.g. `$29 / month`).
- Use action-oriented labels: `Choose Pro`, `Buy now`, `Subscribe`. Never just `Submit`.
- Show a loading spinner while the API call is in flight.
- After successful payment, the success page should confirm what the user got and what happens next (email receipt, account access, etc.).

# Avoid

- Do not collect card details directly — always redirect to Stripe Checkout.
- Do not call the API route from a Server Component; it requires a client click handler.
- Do not paraphrase `components/api/checkout-session/route.ts`. The Stripe SDK init pattern and `mode` field handling must stay byte-exact.
- Do not put the secret key in any `NEXT_PUBLIC_*` variable.

# Verification

- Click the button — browser navigates to `https://checkout.stripe.com/...`.
- In Stripe test mode, use card `4242 4242 4242 4242`, any future date, any CVC.
- Server logs show `[POST] /api/checkout-session 200`.
- After payment, the user lands on the success page.
