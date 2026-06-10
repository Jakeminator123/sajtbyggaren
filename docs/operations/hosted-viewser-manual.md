# Operatörsmanual — hostad viewser (fusklapp)

Det här är fusklappen för dig som driftar den hostade viewser-deployen på
`sajtbyggaren-viewser.vercel.app`. Den förklarar hur lokal och hostad drift
hänger ihop, var varje konfigurationsbit bor och varför, samt var du tittar
när något strular. Djupare bakgrund: `docs/hosted-viewser-deploy.md`,
ADR 0048–0050 och migrationsplanen i `docs/vercel-sandbox-migration/`.

## 1. Arkitekturen på en minut

Två vägar, samma kod:

- **lokalt** (din maskin): `npm run dev` i `apps/viewser`. Bygget kör
  python direkt på disken, output hamnar i `../sajtbyggaren-output/.generated/`,
  preview spawnar `next start` lokalt eller en vercel-sandbox. Delad state
  (sessioner, räknare) ligger i minnet i processen.
- **hostat** (produktion): samma routes, men `/api/prompt` startar i stället
  en bygg-sandbox från build-context-tarballen i blob, kör python-pipen där,
  och publicerar resultatet till blob. Delad state ligger i redis (upstash).

Allt leverantörsspecifikt sitter bakom adaptrar med driver-val via env —
samma filosofi rakt igenom (ADR 0030, 0048, 0049):

| Yta | Kontrakt | Drivers | Väljs via |
| --- | --- | --- | --- |
| preview-runtime | adapterregistret | local-next, vercel-sandbox, stackblitz | `VIEWSER_PREVIEW_MODE` |
| asset-store | `lib/asset-store` | local (disk), vercel-blob | `ASSET_STORE_DRIVER` |
| kv-store | `lib/kv-store` | memory, upstash-redis | `VIEWSER_KV_DRIVER` (eller auto) |

Tumregeln: lokalt behöver ingenting konfigureras (disk + minne är default);
hostat byter env-variablerna driver, inte koden.

## 2. Env-kedjan — vad bor var och varför

Tre lager, i prioritetsordning (senare vinner):

1. **Repo-rotens `.env`** — single source för allt delat: `OPENAI_API_KEY`,
   modellval, `SAJTBYGGAREN_GENERATED_DIR` m.m. Både python-pipen och viewser
   läser härifrån (viewser via dev-skriptets root-env-gap-fill och
   `readRepoEnvVar`-fallbacken).
2. **`apps/viewser/.env.local`** — endast viewser-specifika overrides:
   `VIEWSER_PREVIEW_MODE`, `VIEWSER_MAX_CHAT_TOKENS`, sandbox-flaggor.
   Duplicera aldrig nycklar som bor i roten (då uppstår drift mellan kopior).
3. **Vercel-projektets env** (dashboard eller `vercel env`) — allt som den
   hostade driften behöver: `OPENAI_API_KEY`, blob-tokens (auto-injicerade),
   redis-nycklarna (auto-injicerade av marketplace-integrationen),
   `VIEWSER_ENABLE_HOSTED_BUILD`, `VIEWSER_ENABLE_HOSTED_SANDBOX`,
   `VIEWSER_ALLOW_NON_LOCALHOST`, `VIEWSER_BUILD_CONTEXT_URL`,
   `VIEWSER_PREVIEW_MODE` + `NEXT_PUBLIC_VIEWSER_PREVIEW_MODE`.

Specialfilen `apps/viewser/.env.vercel.local` skrivs av `vercel env pull`
(dev-skriptet gör det automatiskt i sandbox-läge) och innehåller den
kortlivade oidc-tokenen lokalt. Redigera den aldrig för hand.

Viktiga icke-regler: sätt aldrig `VERCEL_OIDC_TOKEN` som statisk variabel i
Vercel-projektet (se avsnitt 5), och lägg aldrig `GITHUB_TOKEN`,
`CURSOR_API_KEY` eller lokala disk-paths (`SAJTBYGGAREN_GENERATED_DIR` m.fl.)
i Vercel-env — de gör ingenting där eller är säkerhetsrisker.

## 3. Redis/kv-store — vad som lagras var

Upstash-resursen `sajtbyggaren-kv` är kopplad till Vercel-projektet och
injicerar `KV_REST_API_URL` + `KV_REST_API_TOKEN` i alla miljöer.
Adaptern auto-detekterar dem; lokalt utan dem används minnesdrivern.

Nycklarna (alla prefixade `viewser:`):

| Nyckel | Innehåll | TTL |
| --- | --- | --- |
| `viewser:hosted-run:<runId>` | status-JSON för ett hostat bygge (fas, fel, buildId) | 24 h |
| `viewser:site:<siteId>:current` | hostad bygg-pekare { buildId, blobPrefix, updatedAt } | ingen |
| `viewser:sandbox-session:<siteId>` | aktiv preview-sandbox { sandboxId, url, createdAt } | 45 min |
| `viewser:build-context:url` | URL till build-context-tarballen i blob | ingen |
| `viewser:rate:<scope>:<ip>` | rate-limit-räknare | fönsterlängden |

Vill du inspektera: upstash-konsolen (via Vercel-dashboardens storage-flik)
har en data-browser, eller curl:a rest-api:t med token.

## 4. Blob — tre olika saker bor där

1. **Asset-store** (`ASSET_STORE_DRIVER=vercel-blob` hostat): operatörs-
   uppladdade bilder/videor.
2. **genererade sajter**: `generated/<siteId>/<relPath>` — den aktiva builden
   fil-för-fil. Skrivs av hostade byggen (och av snapshot-CLI:t för lokalt
   byggda sajter: `node apps/viewser/scripts/snapshot-site-to-blob.mjs <siteId>`).
   Hostad preview läser exakt detta layout.
3. **Build-kontexten**: `build-context/current.tar.gz` — python-pipens kod
   (scripts/, packages/, governance/, data/starters/, requirements.txt).

**Kom ihåg-regeln:** ändrar du något i pipen (scripts/, packages/generation/,
governance/policies eller schemas, data/starters/, requirements.txt) måste du
köra om

```bash
node apps/viewser/scripts/upload-build-context-to-blob.mjs
```

— annars bygger hostade byggen vidare på den gamla kodversionen. CLI:t
skriver nya URL:en till kv-nyckeln ovan; env-fallbacken
`VIEWSER_BUILD_CONTEXT_URL` behöver bara uppdateras om kv-skrivningen inte
gick (CLI:t säger till i så fall).

## 5. Auth-kedjan: oidc lokalt kontra hostat

Sandbox-skapande (både preview och bygge) kräver Vercel-auth. Två lägen:

- **lokalt**: dev-skriptet kör `vercel env pull` till
  `apps/viewser/.env.vercel.local` och håller tokenen färsk (refresh när
  mindre än en timme återstår). Kräver `vercel login` + `vercel link` en gång.
- **hostat**: plattformen levererar tokenen per request via
  request-kontexten (headern `x-vercel-oidc-token`) — INTE som env-var.
  `resolveCredentials` i `lib/vercel-sandbox-runner.ts` adopterar den
  automatiskt. Lägg därför aldrig en statisk `VERCEL_OIDC_TOKEN` i
  Vercel-env: den dör efter ~12 h och skuggar den färska (det var exakt
  så det gamla sandbox-strulet uppstod).

Fallback om oidc inte funkar: trion `VERCEL_TOKEN` + `VERCEL_TEAM_ID` +
`VERCEL_PROJECT_ID` (bor i repo-rotens `.env` för lokal användning).

## 6. Rate-limits — kostnadsskyddet för publik drift

Produktionen är publik utan inloggning (operatörsbeslut, ADR 0050).
Skyddet är per-ip-kvoter via kv-store:

| Scope | Default | Env-override |
| --- | --- | --- |
| chat | 20/min | `VIEWSER_RATE_LIMIT_CHAT` |
| generate-image | 5/min | `VIEWSER_RATE_LIMIT_GENERATE_IMAGE` |
| preview-start | 6/min | `VIEWSER_RATE_LIMIT_PREVIEW_START` |
| prompt-build | 3 per 5 min | `VIEWSER_RATE_LIMIT_PROMPT_BUILD` |

Justera genom att sätta variabeln i Vercel-env (heltal; `0` stänger av
scopet) och redeploya. Kvoterna är ett kostnadstak, inte en säkerhetsgräns —
sandboxens 15-minuters-TTL är taket per enskilt bygge. Håll ett öga på
openai-förbrukningen och vercel-fakturan första veckorna.

## 7. Deploy-flödet

Normalvägen:

1. Jobba på egen branch, öppna PR (CI kör guards).
2. Merge till `jakob-be` (integrationsbranch) efter granskning.
3. Merge/promotion till `main` — Vercel bygger och deployar produktion
   automatiskt (git-koppling, production-branch är `main`).

Undantaget (som användes vid P2-lanseringen): `vercel deploy --prod --yes
--archive=tgz` från `apps/viewser` deployar arbetsträdet direkt, utbi
git-flödet. Använd det bara för akuta lägen eller verifiering — och se till
att samma kod också landar via PR så git och produktion inte glider isär.
Flaggan `--archive=tgz` behövs: monorepots filantal överskrider annars
upload-gränsen.

Preview-deploys: `vercel deploy --yes --archive=tgz`. Obs att vercel.json
stänger av git-auto-deploys för `feat/*`-brancher, så preview från en
feature-branch görs via CLI. Preview-url:er ligger bakom Vercels
deployment-skydd; använd `vercel curl <url>` för att testa dem.

## 8. Felsökning — var du tittar

| Symptom | Kolla först |
| --- | --- |
| 501 "stöds bara i lokal viewser" på prompt | `VIEWSER_ENABLE_HOSTED_BUILD=1` saknas i Vercel-env, eller gammal deploy |
| "Vercel-credentials saknas" | statisk `VERCEL_OIDC_TOKEN` i env skuggar kontext-tokenen — ta bort den; eller äldre deploy utan kontext-adoptionen |
| Bygget hänger i en fas / streamen tog slut | `curl https://…/api/hosted-build/<runId>` — statusnyckeln säger var den dog; sandbox-TTL (15 min) kan ha kapat den |
| "Build-kontext-URL saknas" | kör upload-build-context-CLI:t (avsnitt 4) |
| Python-fel i sandboxen | bygg-skriptet kräver python 3.11+; läs feltexten i status-JSON (sista 600 tecknen av pip/python-outputen följer med) |
| 429-svar | rate-limit — höj scopets env-variabel eller vänta ut fönstret |
| Preview visar gammal sajt | blob skrivs över utan delete; kolla `viewser:site:<siteId>:current` mot blob-innehållet |
| Allt annat hostat | vercel-loggarna: `vercel logs <deployment-url>` eller dashboardens logs-flik; runtime-loggen visar rate-limit- och kv-varningar (fail-open loggar i stället för att kasta) |

Snabbkontroll att produktionen lever:

```bash
curl -s -o /dev/null -w "%{http_code}" https://sajtbyggaren-viewser.vercel.app
curl -s https://sajtbyggaren-viewser.vercel.app/api/hosted-build/ping-test
```

(Det andra anropet ska ge 404-JSON med svensk förklaring — det bevisar att
route + kv-koppling fungerar utan att starta något.)

## 9. Vad som INTE fungerar ännu (ärlig lista)

- **Följdprompter hostat**: kräver run-historik som inte persisteras hostat
  ännu — sandboxen failar ärligt med förklaring i status-JSON. Lokalt
  fungerar följdprompter som vanligt. (P3 i migrationsplanen.)
- **Run-historiken i UI:t hostat**: `/api/runs` ger tom lista + notis
  (ingen beständig disk).
- **snabb uppstart**: kallt hostat bygge tar ~2 min (pip + npm install +
  next build i sandboxen); snapshots/warm-pool är P3/G5.
- **Auth och tenant-isolering**: publik v1 — alla som kan gissa ett siteId
  kan förhandsvisa det. Riktig auth är G4/ADR 0035 när produkten ska ha
  konton.
- **Wizard-direktiv hostat**: discovery-svaren följer med i master-prompten
  (texten), men de strukturerade direktiven skickas inte in i hostade byggen
  ännu — wizardens resultat blir därför något mindre styrt hostat än lokalt.
