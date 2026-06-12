/**
 * hosted-preview-bundle — preview-sidans läsare av preview-bundle-tarballen
 * (G2, ADR 0058).
 *
 * Det hostade bygget (hosted-build-runner.ts, orkestrerings-skriptet)
 * paketerar det publicerade fil-setet som EN tar.gz under
 * ``preview-bundles/<siteId>/<buildId>/preview-bundle.tar.gz`` och skriver
 * URL:en i den hostade current-pekaren (``viewser:site:<siteId>:current``,
 * fältet ``previewBundleUrl``). Den här modulen är läs-sidan: sandbox-runnern
 * frågar ``resolvePreviewBundleSource`` före fil-för-fil-vägen och skapar vid
 * träff preview-sandboxen direkt från tarballen
 * (``Sandbox.create({ source: { type: "tarball", url } })`` — samma mönster
 * som build-kontext-tarballen i hosted-build-runner.ts).
 *
 * Ärlighetsregler (speglar incident-lärdomen 2026-06-12):
 *   - Bundlen är en SNABBVÄG, aldrig ett krav: saknad pekare, saknat fält,
 *     ogiltig URL, död blob eller för stor tarball → ``null`` med tydlig
 *     logg-rad, och callern tar dagens fil-för-fil-väg (bakåtkompat för
 *     sajter byggda före G2).
 *   - Storleksvakt i MAX_TOTAL_BYTES-anda: bygget publicerar aldrig en bundle
 *     vars OKOMPRIMERADE fil-set överstiger 64 MB; här vaktas dessutom den
 *     KOMPRIMERADE tarballen (Content-Length från HEAD-proben) mot samma tak
 *     som belt-and-braces — en gzip är alltid mindre än sitt innehåll.
 *   - Modulen LÄSER bara (KV GET + HTTP HEAD) — den skriver aldrig pekare
 *     eller artefakter.
 *
 * KV-nyckeln dubbleras medvetet här (samma literal som
 * vercel-sandbox-sessions.ts:hostedSiteCurrentKey och orkestrerings-skriptet
 * skriver): sessions-modulen importerar sandbox-runnern, som importerar denna
 * modul — en import åt andra hållet vore en cykel. Literal-pariteten låses av
 * tests/test_viewser_preview_bundle.py.
 */

import { getKvStore, kvGetJson } from "./kv-store";

/**
 * Den hostade current-pekarens JSON-form (skriven av orkestrerings-skriptet
 * i hosted-build-runner.ts). ``previewBundle*``-fälten är additiva (G2):
 * pekare skrivna före G2 saknar dem och preview-sidan degraderar ärligt.
 */
export interface HostedSiteCurrentPointer {
  buildId?: string;
  blobPrefix?: string;
  updatedAt?: string;
  /** Publik blob-URL till preview-bundle-tarballen (G2, ADR 0058). */
  previewBundleUrl?: string;
  /** Okomprimerad totalstorlek (byte) för bundlens fil-set. */
  previewBundleBytes?: number;
  /** Antal filer i bundlen. */
  previewBundleFileCount?: number;
}

/** En upplöst, HEAD-verifierad bundle-källa redo för Sandbox.create. */
export interface PreviewBundleSource {
  url: string;
  /** Okomprimerade byte enligt pekaren (null när fältet saknas). */
  totalBytes: number | null;
  /** Antal filer enligt pekaren (null när fältet saknas). */
  fileCount: number | null;
  /** Komprimerad tarball-storlek enligt HEAD Content-Length (null när okänd). */
  compressedBytes: number | null;
}

/**
 * Storlekstak för den KOMPRIMERADE tarballen — samma 64 MB som
 * MAX_TOTAL_BYTES i generated-blob-source.ts / vercel-sandbox-runner.ts.
 * Bygg-sidan vaktar det okomprimerade fil-setet mot samma tak före publicering,
 * så detta är belt-and-braces mot en främmande/trasig blob. Höjs taken ska det
 * ske på alla ställen samtidigt (samma regel som blob-källans tak).
 */
export const PREVIEW_BUNDLE_MAX_COMPRESSED_BYTES = 64 * 1024 * 1024;

/** Timeout för HEAD-proben mot blob (snabbvägen får aldrig bli en hängväg). */
const BUNDLE_HEAD_TIMEOUT_MS = 5_000;

/**
 * Coerce:a en rå KV-payload till en validerad pekare. Ren funktion utan I/O
 * (enhetstestad i hosted-preview-bundle.test.ts): fel typ/form → null;
 * ``previewBundleUrl`` accepteras bara som https-URL; storleks-/antalsfält
 * bara som icke-negativa heltal (annars utelämnas de — aldrig ett kast).
 */
export function parseHostedSiteCurrentPointer(
  raw: unknown,
): HostedSiteCurrentPointer | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const obj = raw as Record<string, unknown>;
  const pointer: HostedSiteCurrentPointer = {};
  if (typeof obj.buildId === "string" && obj.buildId) {
    pointer.buildId = obj.buildId;
  }
  if (typeof obj.blobPrefix === "string" && obj.blobPrefix) {
    pointer.blobPrefix = obj.blobPrefix;
  }
  if (typeof obj.updatedAt === "string" && obj.updatedAt) {
    pointer.updatedAt = obj.updatedAt;
  }
  if (
    typeof obj.previewBundleUrl === "string" &&
    obj.previewBundleUrl.startsWith("https://")
  ) {
    pointer.previewBundleUrl = obj.previewBundleUrl;
    if (
      typeof obj.previewBundleBytes === "number" &&
      Number.isInteger(obj.previewBundleBytes) &&
      obj.previewBundleBytes >= 0
    ) {
      pointer.previewBundleBytes = obj.previewBundleBytes;
    }
    if (
      typeof obj.previewBundleFileCount === "number" &&
      Number.isInteger(obj.previewBundleFileCount) &&
      obj.previewBundleFileCount >= 0
    ) {
      pointer.previewBundleFileCount = obj.previewBundleFileCount;
    }
  }
  return pointer;
}

/**
 * Läs den hostade current-pekaren för ``siteId``. Icke-kastande: KV-fel,
 * saknad pekare eller fel form → null (preview-flödet faller då ärligt
 * tillbaka till fil-för-fil-vägen).
 */
export async function getHostedCurrentPointer(
  siteId: string,
): Promise<HostedSiteCurrentPointer | null> {
  try {
    const raw = await kvGetJson<unknown>(
      getKvStore(),
      // Samma literal som vercel-sandbox-sessions.ts:hostedSiteCurrentKey —
      // se cykel-motiveringen i modul-JSDoc:en. Låst av source-lock-test.
      `viewser:site:${siteId}:current`,
    );
    return parseHostedSiteCurrentPointer(raw);
  } catch {
    return null;
  }
}

/**
 * Lös upp en användbar preview-bundle-källa för ``siteId`` eller ``null``
 * (→ fil-för-fil-fallback). Varje fallback-orsak loggas i ``logs`` så det
 * alltid syns VILKEN väg preview-starten tog och varför.
 *
 *   1. Pekare saknas / saknar previewBundleUrl → null (sajt byggd före G2).
 *   2. HEAD-proben svarar inte 2xx → null (raderad/trasig blob).
 *   3. Content-Length över taket → null (vakt i MAX_TOTAL_BYTES-anda).
 */
export async function resolvePreviewBundleSource(
  siteId: string,
  logs: string[],
): Promise<PreviewBundleSource | null> {
  const pointer = await getHostedCurrentPointer(siteId);
  if (!pointer?.previewBundleUrl) {
    logs.push(
      "Preview-bundle saknas i current-pekaren (sajt byggd före G2?) — " +
        "fil-för-fil-fallback.",
    );
    return null;
  }
  let compressedBytes: number | null = null;
  try {
    const head = await fetch(pointer.previewBundleUrl, {
      method: "HEAD",
      signal: AbortSignal.timeout(BUNDLE_HEAD_TIMEOUT_MS),
      redirect: "follow",
    });
    if (!head.ok) {
      logs.push(
        `Preview-bundle-blobben svarade HTTP ${head.status} på HEAD — ` +
          "fil-för-fil-fallback.",
      );
      return null;
    }
    const contentLength = Number(head.headers.get("content-length"));
    if (Number.isFinite(contentLength) && contentLength > 0) {
      compressedBytes = contentLength;
    }
  } catch {
    logs.push(
      "Preview-bundle-blobben kunde inte HEAD-probas (nätfel/timeout) — " +
        "fil-för-fil-fallback.",
    );
    return null;
  }
  if (
    compressedBytes !== null &&
    compressedBytes > PREVIEW_BUNDLE_MAX_COMPRESSED_BYTES
  ) {
    logs.push(
      `Preview-bundlen är orimligt stor (${compressedBytes} byte komprimerat ` +
        `> ${PREVIEW_BUNDLE_MAX_COMPRESSED_BYTES}) — fil-för-fil-fallback.`,
    );
    return null;
  }
  return {
    url: pointer.previewBundleUrl,
    totalBytes: pointer.previewBundleBytes ?? null,
    fileCount: pointer.previewBundleFileCount ?? null,
    compressedBytes,
  };
}
