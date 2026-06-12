# ADR 0055 — Hostad preview-standardisering: pre-built blob-artefakter + sessions-reuse med buildId-invalidering

**Status:** Accepted
**Datum:** 2026-06-12 (operatörsbeslut, Jakob, bekräftat ~11:00)
**Beroenden:** ADR 0033 (Vercel Sandbox primär preview-runtime; default-flippen
genomförd 2026-06-12, se uppdateringsnoten där), ADR 0041 (Tier 2
warm-sandbox-reuse), ADR 0048 (hostad byggväg i sandbox), ADR 0049
(kv-store-adapter), B195 (manifest-baserad blob-servering).
**Implementering:** 2026-06-12, samma pass som default-flippen — se
commit-kedjan på `jakob-be` (pre-built-upload, sessions-snabbväg,
invalidering, default-flip, refresh-gate).

## Kontext

Operatörsbeslutet 2026-06-12: **Vercel Sandbox + Blob är standardlösningen för
previews av användarsajter**, streamade in i Viewser-iframen genom
OpenClaw-flödet. StackBlitz-adaptern avvecklas INTE — den ligger kvar pausad
(ADR 0033) och rörs inte.

Två gap gjorde den hostade standardvägen långsam respektive okorrekt:

1. **Långsam preview-kallstart:** det hostade bygget laddade upp källfiler
   (utan `.next/`) till blob under `generated/<siteId>/`, så varje
   preview-sandbox körde full `npm install` + `next build` (~flera minuter)
   trots att bygget NYSS producerat exakt den `.next` som behövs. Lokalt
   fanns redan en pre-built-väg (Tier 1, #263) — men den var disk-only.
2. **Reuse utan sanning:** Tier 2-återanvändningen (ADR 0041,
   `VIEWSER_SANDBOX_REUSE`) återanvände en varm sandbox utan att veta om
   blob-innehållet ändrats sedan sandboxen startade — hostat var den dessutom
   i praktiken död kod (reconnect-vägen krävde disk-källa) och kunde ge
   namnkrockar i `Sandbox.create`.

## Beslut

### 1. Pre-built artefakter följer med till blob

Det hostade bygget laddar upp rot-nivåns färdiga `.next/` (minus
`.next/cache` — webpack-cachen, ~95 % av bytes — och `.next/trace`,
build-telemetri) till `generated/<siteId>/`, med exakt samma skip-logik som
den lokala Tier 1-vägens `collectSource(includeBuiltNext)`. Bygget sker
Linux→Linux så Windows-portabilitetsfallan i B3-noten är inte relevant.
B195-manifestet listar fortsatt exakt det uppladdade fil-setet.

Preview-sandboxen (`vercel-sandbox-runner.ts`) tar pre-built-grenen när
blob-källan bär en komplett `.next` (`BUILD_ID` finns — samma
readiness-kontrakt som disk): `npm install --omit=dev` + `next start`, inget
eget `next build`. Saknad/inkomplett `.next` (bygge före detta beslut, trasig
upload) → ärlig fallback till fulla vägen, EN gång, ingen loop — och
fallbacken laddar inte ner `.next`-filerna alls
(`generated-blob-source.ts:filterPrebuiltRelPaths`).

Storleksvakterna i blob-källan (4 000 filer / 64 MB) hålls MEDVETET identiska
med disk-vägens — Tier 1 har skeppat inom samma tak. Höjs de ska det ske på
båda ställena samtidigt.

### 2. Sessions-reuse i prod med buildId-invalidering

`SandboxSession` (KV `viewser:sandbox-session:<siteId>`) bär nu byggets
identitet: `buildId` från den hostade pekaren `viewser:site:<siteId>:current`,
läst EN gång FÖRE källinsamlingen (annars kan ett bygge som blir klart mitt
under preview-starten märka sessionen med fel id).

Vid preview-POST i reuse-läge (`VIEWSER_SANDBOX_REUSE=1`, nu satt i
Vercel-projektet) gäller sessions-snabbvägen
(`vercel-sandbox-sessions.ts:tryReuseSessionPreview`):

- session-`buildId` == pekarens `buildId` OCH sessionens URL svarar
  (liveness-probe, samma acceptans som `waitForPublicUrl`) → återanvänd
  URL:en direkt, ingen SDK-rundtur, ingen upload (`timings.reused=true`).
- mismatch / okänt `buildId` / död URL → sessionen STOPPAS (invalidering)
  och fulla vägen bygger nytt. En preview kan aldrig fastna på ett gammalt
  bygge.
- ingen hostad pekare (lokalt disk-läge) → snabbvägen är en no-op och den
  lokala reconnect-vägen (`tryReuseSandboxPreview`, re-upload mot varm
  sandbox) gäller oförändrad.

**en koherent livscykel** (dokumenterad i koden): det hostade bygget stoppar
preview-sessionen vid BYGGSTART (`startHostedBuild` →
`stopSandboxSessionForSite`, paritet med lokala `build-runner.ts`) som
primärmekanism; buildId-invalideringen vid preview-POST är backstoppen som
fångar sessioner startade efter byggstart-stoppet men före pekar-swappen.
Hostade sandboxar får alltid TIDSSTÄMPLADE namn (reconnect-by-name används
aldrig hostat) så `Sandbox.create` inte krockar med en nyss invaliderad,
asynkront raderad sandbox.

### 3. Kringbeslut i samma pass

- Default-flippen `local-next` → `vercel-sandbox` (dokumenterad i ADR 0033:s
  uppdateringsnot + `preview-runtime-policy.v1.json` v4).
- Preview-refresh-gaten i Viewser: en follow-up med explicit
  `previewShouldRefresh=false`-semantik (visibleEffect `none`/`registered`)
  river inte preview-sandboxen — iframen behålls. Osäker/saknad signal =
  refresh (ärligt default).

## Konsekvenser

Positiva:

- Hostad preview-kallstart går från minuter (install + build) till
  install-omit-dev + start; en oförändrad sajt med varm session svarar på
  sekunder (sessions-snabbvägen).
- Reuse i prod är säkert: sandboxen kan aldrig servera ett annat bygge än
  pekaren utan att invalideras.
- No-op-/mount-only-followups kostar inte längre en sandbox-rivning.

Negativa/medvetna kostnader:

- Fler blob-PUT:ar per hostat bygge (`.next`-filerna laddas upp,
  sekventiellt) — byggtiden ökar något; previewn (UX-kritiska vägen) vinner
  mer.
- `generated/<siteId>/` i blob växer med `.next`-innehåll →
  blob-prune-beslutet (redan spårat) blir mer angeläget.
- Sessions-snabbvägen litar på liveness-proben; en sandbox som dör mellan
  probe och iframe-load kräver en operatör-retry (samma som idag).

## Referenser

- [ADR 0033 — Vercel Sandbox primär preview](0033-vercel-sandbox-primary-preview.md)
- [ADR 0041 — Tier 2 warm-sandbox-reuse](0041-vercel-sandbox-warm-reuse.md)
- [ADR 0048 — Hostad byggväg i sandbox](0048-hosted-build-python-i-sandbox.md)
- `apps/viewser/lib/hosted-build-runner.ts`, `vercel-sandbox-runner.ts`,
  `generated-blob-source.ts`, `vercel-sandbox-sessions.ts`,
  `preview-runtime-server.ts`
- Källkods-lås: `tests/test_viewser_hosted_blob_cleanup.py`,
  `tests/test_viewser_sandbox_reuse.py`,
  `tests/test_viewser_preview_refresh_gate.py`,
  `tests/test_viewser_hosted_followup_parity.py`
