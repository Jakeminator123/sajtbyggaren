# ADR 0035 — auth/billing/Stripe-scopet (PR #150) parkeras bakom en villkorlig merge-grind

**Status:** Accepted (operatörsbeslut, Jakob, 2026-06-02)
**Datum:** 2026-06-02
**Beroenden:** [`docs/product-operating-context.md`](../../docs/product-operating-context.md)
(scope-guarden "Tidigt scope"), [`governance/rules/team-workflow.md`](../rules/team-workflow.md),
ADR 0034 (follow-up prompt content passthrough), PR #150, PR #153.

## Kontext

PR #150 (`christopher-ui -> main`) är en stor UI-lane-batch (134 filer, ~110
commits): eget auth-stack (scrypt + HMAC-cookies + sqlite-store), billing
(Stripe checkout/portal/webhook + krediter), starters-banan, kärnloop-UX
(FloatingChat-hint, claim-site-feedback), Bite C (preview-route mot
PreviewRuntime-kontraktet) och pre-push-härdning.

Den smala backend-leveransen i PR #153 (copyDirective-modulutbrytning +
P2-grounding + kontakt-ärlighet) är redan mergad till `main`. Det gjorde att
#150 fick en konflikt — men endast i `docs/current-focus.md` (en docs-fil,
ingen kodkonflikt). Den tekniska merge-risken är alltså låg.

Det verkliga beslutet är inte "går det att merga" utan "vill vi ta in en
auth/billing/Stripe-yta i `main` nu". Projektets egen scope-guard i
[`docs/product-operating-context.md`](../../docs/product-operating-context.md)
listar uttryckligen auth, billing och credits samt Stripe/Supabase/Shopify som
saker att **vänta** med "om inte operatören uttryckligen säger annat", tills
kärnflödet `prompt -> företagshemsida -> preview -> följdprompt -> ny version`
är stabilt. En grön CI upphäver inte den ordningen: billing/webhook/claim är
produktionskänsliga ytor där "grönt test" inte räcker som trygghet (webhooks
levereras asynkront, kan retryas och komma i annan ordning; sqlite på serverless
är ett dokumenterat durability-riskområde).

## Beslut

auth/billing/Stripe-scopet i PR #150 **parkeras** och mergas inte enbart för att
konflikten är liten eller för att CI är grön. Merge-beslutet fattas först efter en
scope-rapport (se nedan) och kräver operatörens uttryckliga OK, i linje med
scope-guarden.

Webhook-race-fixen (atomisk event-claim före sidoeffekter, släpp vid fel,
fallibla anrop före kreditering, källlås-test) bedöms som ett seriöst hanterat
positivt tillskott och påverkas inte av denna parkering.

## Villkorlig merge-grind

Beslutet är inte ett permanent nej. Efter re-sync och scope-rapport gäller:

- **Kan tas in (kontrollerad risk):** om #150 endast lägger grund, tester,
  UI-lane och billing/webhook-kod bakom tydliga spärrar (feature flag, dev-only
  eller inaktiv väg), och inget av claim/billing/auth är användbart i det skarpa
  kundflödet. Då är det en isolerad lane som tryggt kan ligga i `main`, och
  operatören kan vara offensiv.
- **Parkeras eller smalnas av:** om #150 gör claim/billing/auth användbart i
  verkligt flöde redan nu. Då drar det projektet in i konto-/betalningsarkitektur
  före kärnflödet är stabilt, och scopet ska vänta tills auth/billing är vald
  sprint.

## Granskningschecklista innan merge

Efter Christophers re-sync (endast `docs/current-focus.md`, ingen produktkod) ska
en read-only granskning bekräfta:

1. Inga secrets eller `.env`-filer har hamnat i git.
2. Stripe webhook-signatur verifieras innan någon sidoeffekt körs.
3. Webhook-claim/idempotens är atomisk (ingen dubbel-kreditering vid parallella
   leveranser).
4. Inga öppna redirects i login/registrering.
5. claim/site-squatting går inte att utnyttja i ett exponerat flöde.
6. sqlite/serverless-begränsningen är dokumenterad om den finns kvar.
7. #150 ändrar inte generatorns huvudflöde `prompt -> företagshemsida ->
   preview -> följdprompt -> ny version`.

## Konsekvenser

- Christopher re-syncar #150 mot nya `main` (löser bara docs-konflikten, plockar
  upp modulutbrytningen automatiskt) och rapporterar om auth/billing/Stripe/claim
  exponeras för faktisk användning eller ligger bakom spärr/feature flag.
- Ingen av de ej byggda punkterna (krediter vid claim, Postgres/Neon-migration,
  HMAC-claim-token) byggs förrän scopet är prioriterat — meningslöst arbete om
  #150 inte mergas.
- Framtida orchestrator/Builder ska behandla denna ADR som aktiv regel: öppna
  inte auth/billing/Stripe i `main` utan operatörens uttryckliga scope-OK, även
  om en PR är mergebar och grön.
