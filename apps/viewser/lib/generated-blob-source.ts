/**
 * generated-blob-source — hostad artefaktkälla för sandbox-previewen.
 *
 * Lokalt läser sandbox-runnern (``lib/[sandbox]-runner.ts``) den genererade
 * sajten från disk (``resolveGeneratedDir()`` → ``.generated/<siteId>/``).
 * Hostat på Vercel finns
 * ingen beständig repo-disk, så den vägen ger ingenting. Den här modulen är den
 * minsta hederliga artefaktkällan hostat (FAS 2B, migrationsplanens G2): en
 * redan byggd sajt snapshottas till blob-lagring lokalt via en icke-publik
 * operatör-CLI (``scripts/snapshot-site-to-blob.mjs`` — ingen publik
 * upload-endpoint, #156), och den här modulen läser tillbaka filerna hostat så
 * sandbox-runnern kan ladda upp dem i en sandbox precis som disk-vägen.
 *
 * Layout i blob: ``generated/<siteId>/<relPath>`` där ``relPath`` är POSIX-
 * relativ mot den byggda sajtens rot (samma form som ``collectSource`` ger på
 * disk). Modulen är ärligt degraderande: saknad blob-store, saknad token eller
 * tomt prefix → ``null`` (runnern rapporterar då "ingen byggd sajt hittad").
 *
 * ``@vercel/blob`` importeras dynamiskt så en saknad dependency degraderar i
 * stället för att krascha. SDK:n läser ``BLOB_READ_WRITE_TOKEN`` från miljön;
 * vi skickar den explicit när den finns.
 */

const BLOB_PREFIX_ROOT = "generated";

/** Skydd så vi aldrig drar ner ett orimligt stort blob-träd (spegel av runnern). */
const MAX_FILES = 4_000;
const MAX_TOTAL_BYTES = 64 * 1024 * 1024;

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

export interface CollectedBlobSource {
  files: { relPath: string; content: Buffer }[];
  dirs: string[];
  totalBytes: number;
}

/** Blob-prefix för en sajts snapshot. Exporteras så CLI:t använder samma form. */
export function blobPrefixForSite(siteId: string): string {
  return `${BLOB_PREFIX_ROOT}/${siteId}/`;
}

/** True om en blob-token finns konfigurerad (annars kan vi inte läsa). */
export function hasBlobToken(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN?.trim());
}

interface BlobSdkListItem {
  url: string;
  pathname: string;
  size?: number;
}

/** Dynamisk import så en saknad ``@vercel/blob`` degraderar ärligt. */
async function loadBlobSdk(): Promise<typeof import("@vercel/blob") | null> {
  try {
    return await import("@vercel/blob");
  } catch {
    return null;
  }
}

/**
 * Läs alla snapshot-filer för ``siteId`` från blob och returnera dem i samma
 * deskriptor-form som ``collectSource`` på disk. Returnerar ``null`` när ingen
 * snapshot finns (eller token/SDK saknas) så callern kan degradera ärligt.
 * Kastar bara på den hårda säkerhetsgränsen (orimligt stort träd) — samma
 * kontrakt som disk-vägens ``collectSource``.
 */
export async function collectSourceFromBlob(
  siteId: string,
): Promise<CollectedBlobSource | null> {
  if (!siteId || !SITE_ID_PATTERN.test(siteId)) return null;
  if (!hasBlobToken()) return null;

  const sdk = await loadBlobSdk();
  if (!sdk) return null;

  const token = process.env.BLOB_READ_WRITE_TOKEN?.trim();
  const prefix = blobPrefixForSite(siteId);

  // Paginera igenom alla blobbar under prefixet.
  const items: BlobSdkListItem[] = [];
  let cursor: string | undefined;
  do {
    const page = await sdk.list({ prefix, cursor, token, limit: 1000 });
    for (const blob of page.blobs) {
      items.push({ url: blob.url, pathname: blob.pathname, size: blob.size });
    }
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);

  if (items.length === 0) return null;

  const files: { relPath: string; content: Buffer }[] = [];
  const dirSet = new Set<string>();
  let totalBytes = 0;

  for (const item of items) {
    // ``pathname`` är ``generated/<siteId>/<relPath>`` → ta bort prefixet.
    if (!item.pathname.startsWith(prefix)) continue;
    const relPath = item.pathname.slice(prefix.length);
    if (!relPath || relPath.endsWith("/")) continue;
    // Säkerhet: ladda aldrig upp ``.env*`` (utom ``.env.example``) till den
    // publika sandboxen — spegel av disk-vägens B54/B58-skydd.
    const baseName = relPath.split("/").pop() ?? "";
    const lowerName = baseName.toLowerCase();
    if (lowerName.startsWith(".env") && lowerName !== ".env.example") continue;

    if (files.length >= MAX_FILES || totalBytes > MAX_TOTAL_BYTES) {
      throw new Error(
        `Blob-snapshotet för ${siteId} är orimligt stort (>${MAX_FILES} filer ` +
          `eller >${Math.round(MAX_TOTAL_BYTES / 1024 / 1024)} MB). Kontrollera ` +
          "att node_modules/.next exkluderades innan snapshot.",
      );
    }

    const res = await fetch(item.url);
    if (!res.ok) {
      throw new Error(
        `Kunde inte hämta blob ${item.pathname} (HTTP ${res.status}).`,
      );
    }
    const content = Buffer.from(await res.arrayBuffer());
    totalBytes += content.byteLength;

    const dir = relPath.includes("/")
      ? relPath.slice(0, relPath.lastIndexOf("/"))
      : "";
    if (dir) dirSet.add(dir);
    files.push({ relPath, content });
  }

  if (files.length === 0) return null;
  return { files, dirs: Array.from(dirSet).sort(), totalBytes };
}
