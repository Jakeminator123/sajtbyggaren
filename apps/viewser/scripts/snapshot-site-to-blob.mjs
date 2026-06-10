#!/usr/bin/env node
/**
 * snapshot-site-to-blob — icke-publik operatör-CLI (FAS 2B).
 *
 * Laddar upp generated-files för en redan byggd sajt till blob-lagring så att
 * den HOSTADE sandbox-previewen kan läsa dem (det finns ingen beständig
 * repo-disk hostat på Vercel). Detta är MEDVETET en lokal CLI och INTE en
 * API-route: en publik upload-endpoint utan auth är just den risk som parkerade
 * PR #156. Operatören kör den här lokalt med en blob-token i miljön.
 *
 * Användning (från repo-roten eller apps/viewser):
 *
 *   BLOB_READ_WRITE_TOKEN=... node apps/viewser/scripts/snapshot-site-to-blob.mjs <siteId>
 *   # valfritt: --generated-dir <path>  (annars SAJTBYGGAREN_GENERATED_DIR / default)
 *
 * Blob-layout: generated/<siteId>/<relPath> (matchar lib/generated-blob-source.ts
 * och sandbox-runnern). access=public + addRandomSuffix=false ger
 * deterministiska, läsbara pathnamn. Källfiler för en publik marknadssajt är
 * ändå tänkta att serveras publikt; .env*-filer laddas ALDRIG upp.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SKIP_DIRS = new Set([
  "node_modules",
  ".next",
  ".git",
  ".turbo",
  ".vercel",
  ".cache",
  "out",
]);

const MAX_FILES = 4_000;
const MAX_TOTAL_BYTES = 64 * 1024 * 1024;
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;
const BUILD_ID_RE = /^\d{8}T\d{6}Z(?:-\d{2,})?$/;

function repoRoot() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  // apps/viewser/scripts/<fil> -> tre nivåer upp = repo-roten.
  return path.resolve(scriptDir, "..", "..", "..");
}

/** Läs en enskild nyckel ur repo-rotens .env (dependency-fritt, samma subset
 * som lib/generated-dir.ts:readRepoEnvVar). */
function readRepoEnvVar(name) {
  const envPath = path.join(repoRoot(), ".env");
  if (!existsSync(envPath)) return undefined;
  let text;
  try {
    text = readFileSync(envPath, "utf8");
  } catch {
    return undefined;
  }
  for (const rawLine of text.split(/\r?\n/)) {
    let line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice(7).trimStart();
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    if (line.slice(0, eq).trim() !== name) continue;
    let value = line.slice(eq + 1).trim();
    const quoted = value.match(/^(['"])((?:[^\\]|\\.)*?)\1\s*(?:#.*)?$/);
    if (quoted) return quoted[2];
    const comment = value.match(/\s+#.*$/);
    if (comment) value = value.slice(0, comment.index).trimEnd();
    return value;
  }
  return undefined;
}

function expandHome(value) {
  const home = process.env.HOME || process.env.USERPROFILE || "";
  if (value === "~") return home;
  if (value.startsWith("~/") || value.startsWith("~\\")) {
    return path.join(home, value.slice(2));
  }
  return value;
}

/** Spegel av lib/generated-dir.ts:resolveGeneratedDir + scripts/build_site.py. */
function resolveGeneratedDir(override) {
  const raw =
    override ||
    process.env.SAJTBYGGAREN_GENERATED_DIR?.trim() ||
    readRepoEnvVar("SAJTBYGGAREN_GENERATED_DIR")?.trim();
  const root = repoRoot();
  if (raw) {
    const expanded = expandHome(raw);
    return path.isAbsolute(expanded)
      ? path.resolve(expanded)
      : path.resolve(root, expanded);
  }
  return path.join(root, "..", "sajtbyggaren-output", ".generated");
}

/** Aktiv immutable build via current.json, annars flat layout (spegel av runnern). */
function resolveSourceDir(generatedRoot, siteId) {
  const siteRoot = path.resolve(generatedRoot, siteId);
  const rel = path.relative(generatedRoot, siteRoot);
  if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) return null;
  if (!existsSync(siteRoot)) return null;

  const pointerPath = path.join(siteRoot, "current.json");
  if (existsSync(pointerPath)) {
    try {
      const payload = JSON.parse(readFileSync(pointerPath, "utf-8"));
      const activeBuildId = payload?.activeBuildId;
      if (typeof activeBuildId === "string" && BUILD_ID_RE.test(activeBuildId)) {
        const buildDir = path.join(siteRoot, "builds", activeBuildId);
        if (existsSync(path.join(buildDir, "package.json"))) return buildDir;
      }
    } catch {
      // korrupt pekare -> fall tillbaka på flat layout
    }
  }
  if (existsSync(path.join(siteRoot, "package.json"))) return siteRoot;
  return null;
}

function collectFiles(rootDir) {
  const files = [];
  let totalBytes = 0;
  const walk = (absDir) => {
    for (const entry of readdirSync(absDir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (SKIP_DIRS.has(entry.name)) continue;
        walk(path.join(absDir, entry.name));
        continue;
      }
      if (!entry.isFile()) continue;
      const lowerName = entry.name.toLowerCase();
      if (lowerName.startsWith(".env") && lowerName !== ".env.example") continue;
      const absPath = path.join(absDir, entry.name);
      const relPath = path.relative(rootDir, absPath).split(path.sep).join("/");
      const size = statSync(absPath).size;
      totalBytes += size;
      if (files.length >= MAX_FILES || totalBytes > MAX_TOTAL_BYTES) {
        throw new Error(
          `Käll-trädet är orimligt stort (>${MAX_FILES} filer eller ` +
            `>${Math.round(MAX_TOTAL_BYTES / 1024 / 1024)} MB). ` +
            "Kontrollera att node_modules/.next exkluderades.",
        );
      }
      files.push({ relPath, absPath });
    }
  };
  walk(rootDir);
  return files;
}

function parseArgs(argv) {
  const args = { siteId: null, generatedDir: null };
  for (let i = 0; i < argv.length; i += 1) {
    const value = argv[i];
    if (value === "--generated-dir") {
      args.generatedDir = argv[i + 1];
      i += 1;
    } else if (!value.startsWith("-") && !args.siteId) {
      args.siteId = value;
    }
  }
  return args;
}

async function main() {
  const { siteId, generatedDir } = parseArgs(process.argv.slice(2));

  if (!siteId || !SITE_ID_PATTERN.test(siteId)) {
    console.error(
      "Användning: BLOB_READ_WRITE_TOKEN=... node apps/viewser/scripts/" +
        "snapshot-site-to-blob.mjs <siteId> [--generated-dir <path>]\n" +
        "siteId måste matcha [a-z0-9-] (a-z, 0-9, bindestreck).",
    );
    process.exitCode = 2;
    return;
  }

  const token = process.env.BLOB_READ_WRITE_TOKEN?.trim();
  if (!token) {
    console.error(
      "BLOB_READ_WRITE_TOKEN saknas i miljön. Hämta den från Vercel-projektets " +
        "blob-store (`vercel env pull`) och kör igen.",
    );
    process.exitCode = 2;
    return;
  }

  let blobSdk;
  try {
    blobSdk = await import("@vercel/blob");
  } catch {
    console.error(
      "@vercel/blob är inte installerad. Kör `cd apps/viewser && npm install`.",
    );
    process.exitCode = 2;
    return;
  }

  const generatedRoot = resolveGeneratedDir(generatedDir);
  const sourceDir = resolveSourceDir(generatedRoot, siteId);
  if (!sourceDir) {
    console.error(
      `Hittade ingen byggd sajt för siteId="${siteId}" under ${generatedRoot}. ` +
        "Kör scripts/build_site.py först.",
    );
    process.exitCode = 1;
    return;
  }

  const files = collectFiles(sourceDir);
  if (files.length === 0) {
    console.error(`Inga filer att ladda upp för ${siteId} (källan är tom).`);
    process.exitCode = 1;
    return;
  }

  const prefix = `generated/${siteId}/`;
  console.log(
    `Snapshotar ${files.length} filer från ${sourceDir}\n  -> blob ${prefix}*`,
  );

  let uploaded = 0;
  for (const file of files) {
    const body = readFileSync(file.absPath);
    await blobSdk.put(`${prefix}${file.relPath}`, body, {
      access: "public",
      token,
      addRandomSuffix: false,
      allowOverwrite: true,
    });
    uploaded += 1;
    if (uploaded % 25 === 0 || uploaded === files.length) {
      console.log(`  ...${uploaded}/${files.length}`);
    }
  }

  console.log(
    `Klart: ${uploaded} filer uppladdade till blob under ${prefix}. ` +
      "Den hostade sandbox-previewen kan nu förhandsvisa sajten.",
  );
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
