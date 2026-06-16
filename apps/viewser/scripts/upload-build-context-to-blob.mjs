#!/usr/bin/env node
/**
 * upload-build-context-to-blob — icke-publik operatör-CLI (P2, hosted build).
 *
 * Paketerar den MINIMALA build-kontext som Python-genereringspipen behöver
 * (scripts/, packages/, governance/, data/starters/, requirements.txt,
 * pyproject.toml) som en tar.gz och laddar upp den till blob-lagring på
 * pathname "build-context/current.tar.gz". Den hostade bygg-runnern
 * (apps/viewser/lib/hosted-build-runner.ts) skapar sedan sin Vercel Sandbox
 * med source { type: "tarball", url: <denna URL> } så pipen kan köras hostat
 * utan lokal Python (migrationsplanens P2, G1 alternativ A).
 *
 * Varför just dessa kataloger (verifierat mot vad pipen faktiskt läser):
 *   - scripts/                 prompt_to_project_input.py + build_site.py (CLI:erna)
 *   - packages/                packages.generation.* (hela pipen importerar härifrån,
 *                              inkl. orchestration/scaffolds + dossiers)
 *   - governance/              policies/ (llm-models, capability-map, starter-registry,
 *                              scaffold-contract m.fl.) + schemas/ (project-input m.fl.)
 *   - data/starters/           copy_starter() kopierar starter-mallen härifrån.
 *                              OBS: data/ exkluderas i övrigt (runs/, prompt-inputs/,
 *                              uploads/, evals/ är lokal historik, inte build-kontext).
 *   - requirements.txt         full pip-lista (lokalt/CI + fallback i sandboxen).
 *   - requirements-build.txt   slim pip-lista som den hostade bygg-sandboxen
 *                              föredrar (utelämnar streamlit/openai-agents/
 *                              pytest*/ruff = färre tunga wheels i kall sandbox).
 *   - pyproject.toml           liten, ofarlig, håller verktygskontext komplett.
 *   - (repo-roten har ingen config/-katalog — pipens konfiguration ligger i
 *     governance/policies/, som följer med ovan.)
 *
 * Exkluderas alltid: node_modules, .venv, .git, .next, __pycache__, *.pyc
 * (och .env* följer aldrig med eftersom inkluderingslistan inte täcker dem).
 *
 * Windows-kompatibilitet: tar-ningen görs med systemets tar (bsdtar ingår i
 * Windows 10+ som C:\Windows\System32\tar.exe; GNU tar på Linux/macOS). Båda
 * stödjer -czf + --exclude och -C <dir> med relativa paths, så ingen ny
 * npm-dependency behövs. Detta valdes före PowerShell-zip eftersom sandboxens
 * tarball-source kräver just tar.gz.
 *
 * Användning (från repo-roten eller apps/viewser):
 *
 *   node apps/viewser/scripts/upload-build-context-to-blob.mjs
 *
 * Token-upplösning (samma mönster som snapshot-site-to-blob.mjs):
 * process.env.BLOB_READ_WRITE_TOKEN vinner; annars repo-rotens .env, sist
 * apps/viewser/.env.vercel.local. Den publika URL:en skrivs till stdout
 * (loggar går till stderr så stdout kan pipas). Finns KV-env (samma namn som
 * lib/kv-store/upstash-redis.ts) sparas URL:en även i KV under
 * "viewser:build-context:url" och aktuell git-SHA i
 * "viewser:build-context:sha" — annars hoppas det steget över med en notis.
 * Om arbetsträdet har ocommittade ändringar i build-kontext-ytorna varnar
 * CLI:t mjukt och sparar även "viewser:build-context:dirty" = true/false i KV.
 */

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, statSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BLOB_PATHNAME = "build-context/current.tar.gz";
const KV_URL_KEY = "viewser:build-context:url";
const KV_SHA_KEY = "viewser:build-context:sha";
const KV_DIRTY_KEY = "viewser:build-context:dirty";

/** Topp-nivå-poster (relativt repo-roten) som ingår i build-kontexten. */
const INCLUDE_ENTRIES = [
  "scripts",
  "packages",
  "governance",
  "data/starters",
  "requirements.txt",
  "requirements-build.txt",
  "pyproject.toml",
];

/** Mönster som aldrig får följa med i tarballen. */
const EXCLUDE_PATTERNS = [
  "node_modules",
  ".venv",
  ".git",
  ".next",
  "__pycache__",
  "*.pyc",
  ".pytest_cache",
  ".ruff_cache",
];

function repoRoot() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  // apps/viewser/scripts/<fil> -> tre nivåer upp = repo-roten.
  return path.resolve(scriptDir, "..", "..", "..");
}

/** Läs en enskild nyckel ur en .env-fil (dependency-fritt, samma subset som
 * snapshot-site-to-blob.mjs:readRepoEnvVar). */
function readEnvFileVar(envPath, name) {
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

/** process.env vinner; fall tillbaka på repo-rotens .env och sist
 * apps/viewser/.env.vercel.local (filen `vercel env pull` skriver). */
function resolveEnvVar(name) {
  const fromProcess = process.env[name]?.trim();
  if (fromProcess) return fromProcess;
  const root = repoRoot();
  const fromRootEnv = readEnvFileVar(path.join(root, ".env"), name)?.trim();
  if (fromRootEnv) return fromRootEnv;
  return readEnvFileVar(
    path.join(root, "apps", "viewser", ".env.vercel.local"),
    name,
  )?.trim();
}

/** KV-env med samma namnordning som lib/kv-store/upstash-redis.ts. */
function resolveKvRestUrl() {
  return (
    resolveEnvVar("VIEWSER_KV_REST_URL") ||
    resolveEnvVar("KV_REST_API_URL") ||
    resolveEnvVar("UPSTASH_REDIS_REST_URL")
  );
}

function resolveKvRestToken() {
  return (
    resolveEnvVar("VIEWSER_KV_REST_TOKEN") ||
    resolveEnvVar("KV_REST_API_TOKEN") ||
    resolveEnvVar("UPSTASH_REDIS_REST_TOKEN")
  );
}

function createTarball(root) {
  const missing = INCLUDE_ENTRIES.filter(
    (entry) => !existsSync(path.join(root, ...entry.split("/"))),
  );
  if (missing.length > 0) {
    throw new Error(
      `Build-kontexten är ofullständig — saknade poster under ${root}: ` +
        `${missing.join(", ")}. Kör CLI:t från Sajtbyggaren-repot.`,
    );
  }

  const tarballPath = path.join(
    tmpdir(),
    `sajtbyggaren-build-context-${Date.now()}.tar.gz`,
  );
  const args = ["-czf", tarballPath];
  for (const pattern of EXCLUDE_PATTERNS) {
    args.push("--exclude", pattern);
  }
  // -C <repo-rot> + relativa paths ger ett tarball-innehåll som extraheras
  // platt i sandboxens /vercel/sandbox (scripts/, packages/, ... i roten).
  args.push("-C", root, ...INCLUDE_ENTRIES);

  // spawnSync utan shell: inga glob-expansioner av *.pyc, och paths med
  // mellanslag (Windows-hemkataloger) hanteras korrekt.
  const result = spawnSync("tar", args, { stdio: ["ignore", "inherit", "inherit"] });
  if (result.error) {
    throw new Error(
      `Kunde inte starta tar (${result.error.message}). Windows 10+ har ` +
        "tar.exe inbyggt; kontrollera att C:\\Windows\\System32 ligger i PATH.",
    );
  }
  if (result.status !== 0) {
    throw new Error(`tar avslutades med exit-kod ${result.status}.`);
  }
  return tarballPath;
}

function runGit(root, args) {
  const result = spawnSync("git", args, {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.error) {
    throw new Error(`Kunde inte starta git (${result.error.message}).`);
  }
  if (result.status !== 0) {
    const stderr = result.stderr.trim();
    throw new Error(
      `git ${args.join(" ")} avslutades med exit-kod ${result.status}` +
        (stderr ? `: ${stderr}` : "."),
    );
  }
  return result.stdout.trim();
}

function currentGitSha(root) {
  return runGit(root, ["rev-parse", "HEAD"]);
}

function dirtyBuildContextPaths(root) {
  const output = runGit(root, [
    "status",
    "--porcelain",
    "--untracked-files=all",
    "--",
    ...INCLUDE_ENTRIES,
  ]);
  if (!output) return [];
  return output
    .split(/\r?\n/)
    .map((line) => line.slice(3).trim())
    .filter(Boolean);
}

function warnIfDirty(paths) {
  if (paths.length === 0) return;
  const shown = paths.slice(0, 20);
  const extra = paths.length - shown.length;
  console.error(
    "VARNING: build-kontexten laddas upp från ett arbetsträd med " +
      "ocommittade ändringar i ytorna som följer med tarballen. Den sparade " +
      "git-SHA:n beskriver inte exakt tarballens innehåll.",
  );
  for (const filePath of shown) {
    console.error(`  - ${filePath}`);
  }
  if (extra > 0) {
    console.error(`  ...och ${extra} till.`);
  }
}

async function saveMetadataToKv(url, sha, dirty) {
  const kvUrl = resolveKvRestUrl();
  const kvToken = resolveKvRestToken();
  if (!kvUrl || !kvToken) {
    console.error(
      "Notis: KV-env saknas (KV_REST_API_URL/KV_REST_API_TOKEN m.fl.) — " +
        `hoppar över KV-skrivningen av ${KV_URL_KEY}, ${KV_SHA_KEY} och ` +
        `${KV_DIRTY_KEY}. Sätt ` +
        "VIEWSER_BUILD_CONTEXT_URL i den hostade miljön i stället.",
    );
    return;
  }
  // Samma REST-mönster som lib/kv-store/upstash-redis.ts: rått Redis-kommando
  // som JSON-array mot Upstash REST-endpointen.
  const response = await fetch(kvUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${kvToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify([
      "MSET",
      KV_URL_KEY,
      url,
      KV_SHA_KEY,
      sha,
      KV_DIRTY_KEY,
      dirty ? "true" : "false",
    ]),
  });
  if (!response.ok) {
    throw new Error(`KV-skrivning misslyckades (HTTP ${response.status}).`);
  }
  const payload = await response.json();
  if (payload?.error) {
    throw new Error(`KV-skrivning misslyckades: ${payload.error}`);
  }
  console.error(
    `Build-kontext-metadata sparad i KV under ${KV_URL_KEY}, ` +
      `${KV_SHA_KEY} och ${KV_DIRTY_KEY}.`,
  );
}

async function main() {
  const token = resolveEnvVar("BLOB_READ_WRITE_TOKEN");
  if (!token) {
    console.error(
      "BLOB_READ_WRITE_TOKEN saknas (process.env, repo-rotens .env och " +
        "apps/viewser/.env.vercel.local kontrollerades). Hämta den från " +
        "Vercel-projektets blob-store (`vercel env pull`) och kör igen.",
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

  const root = repoRoot();
  const sha = currentGitSha(root);
  const dirtyPaths = dirtyBuildContextPaths(root);
  warnIfDirty(dirtyPaths);
  console.error(`Paketerar build-kontext från ${root} ...`);
  const tarballPath = createTarball(root);

  try {
    const sizeMb = (statSync(tarballPath).size / 1024 / 1024).toFixed(1);
    console.error(`Tarball klar (${sizeMb} MB). Laddar upp till blob ...`);

    const blob = await blobSdk.put(BLOB_PATHNAME, readFileSync(tarballPath), {
      access: "public",
      token,
      addRandomSuffix: false,
      allowOverwrite: true,
    });

    console.error(`Uppladdad till blob-pathname ${BLOB_PATHNAME}.`);
    // Endast URL:en på stdout så den kan pipas vidare.
    console.log(blob.url);

    await saveMetadataToKv(blob.url, sha, dirtyPaths.length > 0);
  } finally {
    try {
      unlinkSync(tarballPath);
    } catch {
      // Best-effort temp-städning — aldrig fatalt.
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
