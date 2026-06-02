# Handoff: christopher-ui → Jakob (2026-06-02)

**Branch:** `christopher-ui`
**HEAD:** `50fa063` (pushad till `origin/christopher-ui`)
**Mot `origin/main` (= `origin/jakob-be`, båda `b027b70`):** 102 commits före, 2 efter.

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
   `addCredits`/Stripe-retry kunde tappa krediter. Fix: markera EFTER lyckad
   `handleEvent` + `INSERT OR IGNORE`; handler-fel → 500 så Stripe gör retry.

---

## 3. Kvarvarande fynd jag MEDVETET INTE fixade (deploy/design — din kallelse)

Dessa är inte push-blockerare för en dev-branch men bör hanteras före prod:

- **[P0 deploy] SQLite-auth på serverless.** `lib/auth/db.ts` skriver till
  `data/auth/auth.db`. På Vercel/ephemeral nollställs den per instans →
  konton/sessioner/krediter/ägarskap persisterar inte. Kräver durable store
  (Postgres/Neon) eller en uttalad "single-node only"-deploy. Designbeslut.
- **[P1 design] Site-squatting.** Vilken inloggad användare som helst kan
  `claim`:a vilket känt `siteId` som helst (först-till-kvarn). Bör knytas till
  build-bevis (run-metadata/signerad handoff). Designbeslut.
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

> christopher-ui är pushad (`50fa063`), 102 före / 2 efter main. Dagens batch:
> eget auth (scrypt + HMAC-cookies + SQLite, proxy grindar /konto), Stripe
> billing, starters-banan, synliggjord kärnloop (FloatingChat-hint + auth-medveten
> claim-toast), Bite C (preview-route mot PreviewRuntime) och UI-gap-fixen
> (run-change-set). Inga packages/- eller build_site.py-ändringar. Pre-push:
> alla gates gröna (enda pytest-fail = offline Google Fonts, miljö ej kod) + 4
> bug-scout-fixar (ärlig claim-site, AUTH_SECRET prod-guard, öppen-redirect-skydd,
> Stripe-webhook-idempotens). Kvar för dig att besluta före prod: SQLite på
> serverless (durable store?) + site-squatting-skydd. De 2 commits vi ligger
> efter = PR #149 (copyDirectives) — backend redan i huvudsak inne hos oss via
> merge; minimal merge-konflikt väntad. Öppna PR christopher-ui→main med dig som
> reviewer; merga inte direkt till main.
