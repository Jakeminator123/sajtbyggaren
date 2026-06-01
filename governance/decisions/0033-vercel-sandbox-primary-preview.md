# ADR 0033 — Vercel Sandbox är primär preview-runtime (local-next fallback, stackblitz pausad)

**Status:** Accepted
**Datum:** 2026-06-01 (operatörsbeslut, Jakob)
**Beroenden:** ADR 0003 (Preview Runtime-abstraktion), ADR 0025 (browser-fallback-
preview), ADR 0028 (Runtime Ladder), ADR 0030 (Preview-Provider Portability),
[`docs/spikes/vercel-sandbox-spike.md`](../../docs/spikes/vercel-sandbox-spike.md),
[`docs/product-operating-context.md`](../../docs/product-operating-context.md).

## Kontext

Spike #146 bevisade **live** att en redan-genererad Next.js-sajt kan köras
isolerat i en Vercel Sandbox och visas via en publik URL: `painter-palma`
startade `ready`, cold-start ~29 s (install 18 s + build 9 s), full sajt
renderade i både desktop (1280×800) och mobil (390×844, responsiv) utan
konsolfel, `stop()`+`delete()` städade rent, och faktisk kostnad var ~52 s
active CPU + ~155 MB ingress (≈ ett par ören). Spiken är mergad till `jakob-be`
som bevis (flag-gated bakom `VIEWSER_SANDBOX_SPIKE=1`, inte produktintegration).

ADR 0028 (Runtime Ladder) och `docs/product-operating-context.md` pekade
tidigare ut `stackblitz` som "första användarnära preview-yta". Det är nu
inaktuellt: StackBlitz kräver Chromium-isolation (Safari/Firefox kan inte ladda
embeddet, se ADR 0025/B125) och har lång init-tid, medan Vercel Sandbox ger en
publik HTTPS-URL som fungerar i alla browsers utan att belasta operatörens
maskin. Operatören beslutar därför att flytta upp `vercel-sandbox` från
"framtida adapter" (ADR 0030 adapter #4) till **primärt förstahandsval** för
riktig produkt-preview — vilket är det som driver v0/Lovable-känslan i
kärnflödet `prompt -> företagshemsida -> preview -> följdprompt -> ny version`.

## Beslut

**Vercel Sandbox är den primära preview-runtimen. Den körs som en
`PreviewRuntime`-adapter bakom `VIEWSER_PREVIEW_MODE`, aldrig som hårdkodad
specialväg.** Ny prioordning bland runtimes:

| Runtime | Roll efter detta beslut |
| ------- | ----------------------- |
| `vercel-sandbox` | **Primär** — förstahandsval för användarpreview (publik URL i iframe, alla browsers) |
| `local-next` | Lokal dev, felsökning och fallback om sandbox inte är tillgänglig |
| `static-export` | Framtida enkel fallback |
| `fly` / annan VM | Framtida server-runtime-fallback |
| `stackblitz` | **Pausad/degraderad** — får finnas kvar men ska inte blockera, inte vara default, och inte vara ett krav i tester |

### Detta ändrar INTE ADR 0030:s hårda regler

ADR 0033 höjer Vercel Sandbox till primärval men upphäver inte
portabilitetsskyddet. Följande gäller fortsatt:

1. **Generated output förblir vanlig Next.js.** En genererad sajt ska kunna
   `npm install && npm run build && npm run start` på vilken Node.js-värd som
   helst. Inga `@vercel/*`-beroenden i `packages/generation/` eller
   `data/starters/*`.
2. **En non-Vercel-fallback måste alltid vara inwirad.** `local-next` är den
   garanterade fallbacken; byte till `fly`/annan provider ska vara "ny
   adapter-fil + env-flagga", inte en omskrivning.
3. **Sajtbyggaren äger sanningen.** `data/runs/<runId>` (project-input,
   build-result, generated-files-snapshot, version) är källan. Vercel Sandbox
   kör bara en **ephemeral kopia** och returnerar en `previewSession.url`.
   Vercel är aldrig projekt-/datalager.
4. **Allt går via `PreviewRuntime`-kontraktet.** Leverantörsberoenden (t.ex.
   `@vercel/sandbox`) bor bara i `packages/preview-runtime/` (eller app-lagrets
   server-only DI), aldrig i generation/starters. Begrepp som URL-format läcker
   inte genom abstraktionsgränsen.

### Förnyelse efter följdprompt (nivå 1 först)

Första implementationen håller det enkelt: en följdprompt skapar en ny
version/run, bygger ny generated output, startar en **ny** preview-session, och
iframen byter URL. Att återanvända/snapshotta sandbox för snabbare start (nivå
2) eller LLM-patcha filer live i VM:n och diffa tillbaka (nivå 3) är senare
nivåer, inte nu.

## Vad ADR 0033 INTE gör (staging — kräver separat operatörs-OK)

Detta är ett **beslut + dokumentationsslice**, inte implementationen. Följande
landar i en separat adapter-slice (nästa PR mot `jakob-be`), efter operatörens
OK, eftersom de är mekaniskt kopplade till kod och policy + cross-policy-tester:

- Naming-bump (`naming-dictionary.v1.json` v18 → v19): `previewRuntimeKind`-
  definitionen utökas med `vercel-sandbox`.
- `PreviewRuntimeKind`-utökning i `packages/preview-runtime/src/types.ts` +
  registry-mappning så `VIEWSER_PREVIEW_MODE=vercel-sandbox` väljer adaptern.
- `packages/preview-runtime/src/adapters/vercel-sandbox.ts` (konkret adapter som
  delegerar till en server-only runner; degraderar `unsupported`/`failed` utan
  auth, kraschar aldrig).
- Ev. justering av `preview-runtime-policy.v1.json` så
  `test_preview_runtime_forbidden_terms_are_in_globally_forbidden` förblir grön.
- Default `VIEWSER_PREVIEW_MODE` i kod ändras INTE förrän adaptern finns och är
  verifierad (förblir `local-next` tills dess; dev-dispatchern kastar fortfarande
  på okänt env-värde).
- Bite C (flippa produktions-routen `app/api/preview/[siteId]` till
  `currentViewserRuntime()`) är Christophers UI-lane.

## Konsekvenser

Positiva:

- Publik preview-URL som fungerar i alla browsers (löser B125 Safari/Firefox)
  utan att belasta operatörens maskin — rätt grund för v0/Lovable-känslan.
- Isolerad körning av genererad kod i Firecracker-microVM (säkrare än lokal
  process; ingen WinError-5-klass som `local-next` på Windows).
- Fortsatt utbytbart: prishöjning, drift eller lock-in löses genom att byta
  adapter, inte genom att röra `packages/generation/` eller renderer-output.

Negativa:

- Vercel-kostnad per preview-session (active CPU + provisioned memory + data
  transfer). Mätt i spiken till ~ett par ören per körning; TTL + `stop()`/
  `delete()` håller kostnaden i schack.
- Kräver Vercel-auth (OIDC via `VERCEL_OIDC_TOKEN`, eller access-token-trion).
  Utan auth degraderar adaptern till `unsupported`/`failed` (per ADR 0030).
- Sandbox är idag bara i regionen `iad1` → högre latens från Sverige än en
  EU-host. Påverkar upplevd snabbhet, inte korrekthet.

## Referenser

- [ADR 0028 — Runtime Ladder](0028-runtime-ladder.md)
- [ADR 0030 — Preview-Provider Portability](0030-preview-provider-portability.md)
- [`docs/spikes/vercel-sandbox-spike.md`](../../docs/spikes/vercel-sandbox-spike.md)
- [`packages/preview-runtime/src/types.ts`](../../packages/preview-runtime/src/types.ts)
- [`docs/product-operating-context.md`](../../docs/product-operating-context.md)
