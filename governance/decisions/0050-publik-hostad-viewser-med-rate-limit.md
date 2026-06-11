# ADR 0050 — Publik hostad viewser: rate-limit per ip i stället för auth (v1)

**Status:** Accepted
**Datum:** 2026-06-10 (operatörsbeslut, Jakob)
**Beroenden:** ADR 0035 (auth/billing parkerat), ADR 0048, ADR 0049. Avviker
medvetet från G4-rekommendationen i
[`docs/vercel-sandbox-migration/01-arkitekturval.md`](../../docs/vercel-sandbox-migration/01-arkitekturval.md)
(riktig auth) — dokumenterat här som ett uttryckligt operatörsval.
Referens: [`apps/viewser/lib/rate-limit.ts`](../../apps/viewser/lib/rate-limit.ts).

## Kontext

Migrationsplanens G4 föreslår riktig auth (clerk m.fl.) innan hostade
användarflöden öppnas. Operatören har 2026-06-10 uttryckligen valt att
produktions-deployen ska vara publik utan inloggning i v1, så att vem som
helst kan testa att skapa en sajt. Utan skydd vore det en öppen relä för
openai-anrop och sandbox-kostnad (samma risk som parkerade PR #156).

## Beslut

Publik v1 med kostnadsskydd i stället för auth:

- Fixed-window rate-limit per ip via kv-store (ADR 0049):
  `enforceRateLimit(request, scope, { limit, windowSeconds })`.
- Scopes och defaults: chat 20/min, generate-image 5/min, preview-start
  6/min, prompt-build 3 per 5 min. Override per scope via
  `VIEWSER_RATE_LIMIT_<SCOPE>` (0 = av).
- Fail-open: kv-fel får aldrig fälla tjänsten, bara släppa igenom.
- Sandbox-TTL är kostnadstaket per bygge; rate-limiten är taket per ip.
- `VIEWSER_ALLOW_NON_LOCALHOST=true` ligger kvar i produktion — det är
  medvetet: localhost-låset är inte säkerhetsmekanismen hostat, det är
  rate-limiten plus sandbox-isoleringen.

Riktig auth + tenant-isolering (G4/ADR 0035) är fortsatt nästa steg när
produkten ska ha konton, kvoter per användare och delning.

## Termer

Scope-begreppet (namngiven kvot-yta per endpoint: chat, generate-image,
preview-start, prompt-build) är canonical i naming-dictionary v34 som
rate-limit-scope, med env-override-konventionen dokumenterad där.

## Konsekvenser

- Plus: noll friktion för testanvändare; kostnadsexponeringen är kapad per
  ip och per bygge; ingen auth-kod att underhålla i v1.
- Minus: per-ip-limit kan kringgås med många ip:n (acceptabel risk i v1 —
  bevakas via vercel-loggar); ingen tenant-isolering: alla sajter är
  tekniskt nåbara för alla som kan gissa siteId.
