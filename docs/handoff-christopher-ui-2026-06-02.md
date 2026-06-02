# Handoff: christopher-ui → Jakob (2026-06-02)

**Branch:** `christopher-ui`
**HEAD:** `d87e905` (pushad till `origin/christopher-ui`; batch-commit var `50fa063`,
sedan merge av `origin/main` `c4c7760` + Jakob-review-fixar nedan).
**Mot `origin/main`:** synkad via merge av `origin/main` (`619454c`, PR #151) →
PR #150 rapporterar nu mergebar (inga konflikter kvar; den ostabila check-statusen
= enbart det medvetet avvisade Vercel-fyndet, se §3).

Detta dokument är en självständig handoff. `docs/current-focus.md` lämnades
medvetet orörd (den är orchestrator-filen och pekar på `jakob-be`-checkpoint
`093b31a`; jag vill inte skapa merge-brus i din lane). Reconcilea den vid merge
som vanligt.

---

## 1. Vad som landade i dagens batch (`50fa063`)

En sammanhållen UI-lane-batch i `apps/viewser/**` + tester + tooling. Allt är
operatörsgodkänt. **Rör inte `packages/` eller `scripts/build_site.py`.**

- **Auth (eget stack, ingen tredjeparts-inlogg):** scrypt-lösenord + HMAC-
  signerade cookie-sessioner (Web Crypto, funkar i både node- och edge-yta) +
  SQLite-store (`lib/auth/*`). `proxy.ts` grindar `/konto` (INTE `/studio`).
  Ytor: `/login`, `/registrera`, `/konto`, auth-medveten header.
- **Billing:** Stripe Checkout + Customer Portal + webhook
  (krediter/abonnemang), `/priser`. Lazy-config: 503 om Stripe-env saknas.
- **Starters-banan:** yrkessidor → förifylld wizard (`WizardSeed`/`StarterCta`),
  hero-chips, studio tom-läge-onboarding (`starter-presets`).
- **Synliggör kärnloopen:** `FloatingChat` första-gångs-hint (följdprompt → ny
  version, "Visa versioner"); auth-medveten `claim-site`-feedback
  ("Sparad till ditt konto" / login-nudge en gång per session).
- **Bite C:** `app/api/preview/[siteId]/route.ts` mot PreviewRuntime-
  kontraktet (`currentViewserRuntime()`), ärliga fel istället för tyst fallback.
- **UI-gap (din flagga):** `prompt/route.ts` exponerar en exakt change-set
  (`run-change-set.ts`) för follow-ups + `appliedCopyDirectives`.

### Bygg-pipeline-filer som rörts (och varför — INTE scope-läckor)

- `lib/build-runner.ts`, `lib/prompt-runner.ts`, `lib/scrape-runner.ts`:
  endast en Turbopack-workaround (`path.resolve` görs opak via spread så
  output-tracern inte panikar på `.venv`-symlänkar med `turbopack.root`). Ren
  runtime, ingen ändrad bygg-semantik.
- `lib/runs.ts`: `readAppliedCopyDirectives` (ADR 0034 väg B, sedan tidigare).
- `next.config.ts`: better-sqlite3 extern + `turbopack.root`.

---

## 2. Pre-push bug-check (kört före push)

Gates gröna: `tsc` 0, `eslint` 0, `ruff` 0, `term-coverage --strict` 0,
governance 18/18, rules-sync OK, sprintvakt OK.
Pytest: **grönt** utom ett test — `test_llm_golden_path_real_build_end_to_end`
failar på `getaddrinfo fonts.googleapis.com` (Next försöker hämta Geist från
Google Fonts vid en riktig npm-build). **Miljö/offline, inte en regression** —
inga font- eller `layout.tsx`-ändringar i denna batch.

En read-only bug-scout kördes på changeseten. Fynd jag **åtgärdade före push**:

1. `claim-site` svarade alltid `{ ok: true }` även om sajten redan ägdes av
   ett annat konto → min nya toast "Sparad till ditt konto" kunde ljuga.
   Fix: `claimSite()` returnerar `claimed | already-own | owned-by-other`;
   routen svarar `{ ok: false, reason: "already-claimed" }` vid owned-by-other.
2. `AUTH_SECRET` föll tyst tillbaka på en publik dev-nyckel → cookies
   förfalskningsbara i prod. Fix: fail-fast `throw` när `NODE_ENV==="production"`
   och secret saknas.
3. Öppen redirect i `/login` + `/registrera` (`next.startsWith("/")` släpper
   igenom `//evil.com`). Fix: delad `isSafeNext()` i `auth-config.ts`.
4. Stripe-webhook markerade event hanterat FÖRE sidoeffekten → en kastande
   `addCredits`/Stripe-retry kunde tappa krediter. Fix (steg 1): markera EFTER
   lyckad `handleEvent` + `INSERT OR IGNORE`; handler-fel → 500 så Stripe gör retry.
   **Uppdaterat efter Jakob-review (2026-06-02, se §3):** steg 1 lämnade ett
   samtidighets-race (två parallella leveranser kunde båda passera dedup-checken
   över `await`-fönstret i `handleEvent` och dubbel-kreditera). Slutlig fix:
   eventet **claimas atomiskt** (`INSERT OR IGNORE` + `changes === 1`) FÖRE
   sidoeffekterna, claimen **släpps** (`releaseEvent`/DELETE) om handlern kastar,
   och `checkout.session.completed` kör det fallibla Stripe-anropet före
   `addCredits` (retry-säkert). Källlås: `test_stripe_webhook_claims_event_atomically_before_side_effects`.

---

## 3. Kvarvarande fynd jag MEDVETET INTE fixade (deploy/design — din kallelse)

Dessa är inte push-blockerare för en dev-branch men bör hanteras före prod.
**Jakob-review 2026-06-02** gick igenom samma yta; verdikt: LLM-flödet ~8/10,
auth/billing-lagret ~5/10 "inte produktionssäkert ännu". Det enda **kodbugg**-
fyndet (Stripe-webhook-racet) är nu **STÄNGT** (se §2.4). Resten är beslut:

> **Operatörsbeslut 2026-06-02 (efter Jakob-review): auth/billing bakom
> feature-flagga, DEFAULT AV.** Hela auth/billing-ytan är nu opt-in bakom
> `NEXT_PUBLIC_AUTH_ENABLED` (default av). Avstängd → `/login`, `/registrera`,
> `/konto`, `/priser` 404:ar, header-entry + Priser-nav döljs, auth/checkout-API
> svarar 404. Det gör #150 till **dormant groundwork** i `main` (Jakobs "går
> troligen att ta in nu, med kontrollerad risk"). De tre punkterna nedan är
> därmed **förutsättningar för att FLIPPA PÅ flaggan**, inte merge-blockers:
> operatören aktiverar när durable store + claim-token + kreditmätningspunkt
> är på plats. Kärnloopen påverkas aldrig (källlås).

- **[BESLUT, ej bugg] Krediter dras inte i `/api/prompt`.** Både Jakob- och
  Vercel-reviewen flaggar detta som 95%/10. Det är ett **medvetet produktbeslut**,
  inte ett kodfel: kärnloopen (`prompt → preview`) ska vara friktionsfri för
  utloggade besökare (produktkompassen), och en inloggnings-/kreditgrind i
  bygg-ingången skulle dessutom **bryta källlåset** `test_build_pipeline_untouched_by_auth`
  (asserterar uttryckligen `"consumeCredits" not in prompt_route` +
  `"auth/session" not in prompt_route`). Den verkliga frågan är ett **operatörsval**:
  (a) behåll fri demo-bygge + mät krediter på något senare/inloggat steg
  (t.ex. publicering/claim eller följdprompt för inloggade), eller (b) tvinga
  inloggning på hela bygget (bryter kärnloopen + kräver omskrivet källlås).
  Min rekommendation: (a). Jag bygger gärna kreditmätning på ett icke-kärnloop-
  steg om du pekar ut vilket.
- **[P0 deploy] SQLite-auth på serverless.** `lib/auth/db.ts` skriver till
  `data/auth/auth.db`. På Vercel/ephemeral nollställs den per instans →
  konton/sessioner/krediter/ägarskap persisterar inte. Kräver durable store
  (Postgres/Neon) eller en uttalad "single-node only"-deploy. Designbeslut.
- **[P1 design] Site-squatting.** Vilken inloggad användare som helst kan
  `claim`:a vilket känt `siteId` som helst (först-till-kvarn). Bör knytas till
  build-bevis. Eftersom bygget är anonymt (ingen inloggning krävs) finns idag
  ingen serverkoppling "vem byggde X". Ren fix som **bevarar den anonyma
  kärnloopen**: bygget utfärdar ett kortlivat **HMAC-signerat claim-token**
  (`siteId` + utgång) till webbläsaren som byggde (befintlig HMAC-infra i
  `lib/auth/tokens.ts`); `claim-site` verifierar signatur + utgång + att sajten
  är oclaim:ad. Binder claim till "den som precis byggde i denna flik" utan att
  tvinga inloggning vid bygge. Jag bygger den om du vill — annars accepterat-
  för-nu (first-come på single-node).
- **[P2] `register`-TOCTOU:** `emailExists`-koll + `createUser` har ett litet
  race-fönster (osannolikt på single-node SQLite); kan stängas med try/catch → 409.
- **[P2] `claim-site` `siteId`-validering:** bara non-empty/`!== "unknown"`;
  kunde charset/längd-valideras som run-id.

---

## 4. Scope-bevis (lane-disciplin)

- Min batch-commit `50fa063` rör **inga** `packages/`- eller
  `scripts/build_site.py`-filer.
- Enda `packages/`-filen i hela rangen mot merge-base är
  `packages/generation/brief/extract.py` — den är **identisk med `origin/main`**
  (`git diff origin/main..christopher-ui -- ...` är tom). Den kom in via en
  tidigare merge av din copyDirectives-backend (`a1e2502`/`a346bd6`/`4d08526`),
  samma arbete som nu ligger i main via PR #149. Alltså nedärvd, inte författad här.

---

## 5. Merge-vägledning (viktigt)

**Operatörens fråga var: "är jakob-be helt icke-uppdaterad, merga då direkt
till main?" — Svar: nej, gör inte det.**

- `jakob-be` är INTE icke-uppdaterad: den är 2 commits före oss (= PR #149,
  copyDirectives 2a/2c/3a + reviewer-härdning) och identisk med `main`.
- Direkt-merge `christopher-ui → main` utan din review är fel väg. Etablerat
  mönster (branch-discipline + PR #139): Christopher öppnar **PR mot main per
  leveransfönster med Jakob som reviewer**. Denna batch (auth + billing + app/api
  + lib + Bite C) behöver definitivt din granskning.
- **Overlap att vara medveten om vid merge:** christopher-ui bär copyDirectives-
  backend-commits (`a1e2502`/`a346bd6`/`4d08526`) som även finns i main via
  PR #149 (andra SHA, samma/identiskt innehåll på `extract.py`). Det vi
  faktiskt SAKNAR från PR #149 är mindre refinements (bl.a.
  `tests/test_followup_copy_directives.py` +118 rader,
  `scripts/prompt_to_project_input.py`-tweaks). Förvänta minimal/clean konflikt
  på backend; eventuella krockar i `prompt_to_project_input.py` är dina att lösa.

**Rekommenderad väg:** öppna PR `christopher-ui → main` (eller `→ jakob-be`),
du reviewar. Säg till om du vill att jag öppnar PR:en.

---

## 6. Kopiera-klistra till Jakob

> christopher-ui är pushad (`d87e905`), synkad mot main → PR #150 mergebar
> (konflikterna lösta via merge av origin/main `c4c7760`; backend-filerna tar
> mains kanoniska PR #149-version = noll netto-diff). Dagens batch: eget auth
> (scrypt + HMAC-cookies + SQLite, proxy grindar /konto), Stripe billing,
> starters-banan, synliggjord kärnloop (FloatingChat-hint + auth-medveten
> claim-toast), Bite C (preview-route mot PreviewRuntime) och UI-gap-fixen
> (run-change-set). Inga packages/- eller build_site.py-ändringar. Gates gröna
> (enda pytest-fail = offline Google Fonts, miljö ej kod). Bug-scout + Jakob-
> review-fixar: ärlig claim-site, AUTH_SECRET prod-guard, öppen-redirect-skydd,
> och Stripe-webhook nu **samtidighetssäker** (atomisk claim före sidoeffekter +
> release vid fel). Kvar = OPERATÖRSBESLUT, inte buggar: (1) kreditmätning av
> bygget — medvetet INTE i `/api/prompt` (skulle bryta kärnloopen + källlåset
> `test_build_pipeline_untouched_by_auth`); välj ett icke-kärnloop-steg om du
> vill mäta. (2) SQLite på serverless → durable store eller uttalad single-node.
> (3) site-squatting → HMAC-claim-token vid bygge (bevarar anonym loop) eller
> accepterat-för-nu. Scope-beslutet (auth/billing in i main) är ditt: säg
> "merga 150".
