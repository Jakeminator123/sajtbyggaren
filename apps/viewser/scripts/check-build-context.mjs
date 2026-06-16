#!/usr/bin/env node
/**
 * check-build-context — operator guard for hosted Python build context.
 *
 * The hosted build runner executes the tarball uploaded by
 * upload-build-context-to-blob.mjs, not the live repository checkout. This
 * script compares the git SHA saved during the latest upload with the current
 * checkout, limited to the same entries that are packaged into that tarball.
 * It never uploads automatically; stale context is an operator action.
 */

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const KV_SHA_KEY = "viewser:build-context:sha";
const KV_DIRTY_KEY = "viewser:build-context:dirty";
const FULL_SHA_RE = /^[0-9a-f]{40}$/i;

/** Top-level entries that are included in build-context/current.tar.gz. */
const WATCHED_ENTRIES = [
  "scripts",
  "packages",
  "governance",
  "data/starters",
  "requirements.txt",
  "requirements-build.txt",
  "pyproject.toml",
];

function repoRoot() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(scriptDir, "..", "..", "..");
}

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

function runGit(root, args) {
  const result = spawnSync("git", args, {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.error) {
    throw new Error(`Could not start git (${result.error.message}).`);
  }
  if (result.status !== 0) {
    const stderr = result.stderr.trim();
    throw new Error(
      `git ${args.join(" ")} exited with code ${result.status}` +
        (stderr ? `: ${stderr}` : "."),
    );
  }
  return result.stdout.trim();
}

function currentGitSha(root) {
  return runGit(root, ["rev-parse", "HEAD"]);
}

function parseStatusPaths(output) {
  if (!output) return [];
  return output
    .split(/\r?\n/)
    .map((line) => line.slice(3).trim())
    .filter(Boolean);
}

function dirtyBuildContextPaths(root) {
  return parseStatusPaths(
    runGit(root, [
      "status",
      "--porcelain",
      "--untracked-files=all",
      "--",
      ...WATCHED_ENTRIES,
    ]),
  );
}

function changedBuildContextPaths(root, savedSha) {
  const output = runGit(root, [
    "diff",
    "--name-only",
    savedSha,
    "HEAD",
    "--",
    ...WATCHED_ENTRIES,
  ]);
  if (!output) return [];
  return output.split(/\r?\n/).filter(Boolean);
}

function assertCommitExists(root, sha) {
  runGit(root, ["cat-file", "-e", `${sha}^{commit}`]);
}

async function kvGet(key) {
  const kvUrl = resolveKvRestUrl();
  const kvToken = resolveKvRestToken();
  if (!kvUrl || !kvToken) {
    throw new Error(
      "KV-env saknas (KV_REST_API_URL/KV_REST_API_TOKEN m.fl.). " +
        "Kan inte kontrollera senaste build-context-SHA.",
    );
  }
  const response = await fetch(kvUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${kvToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(["GET", key]),
  });
  if (!response.ok) {
    throw new Error(`KV-läsning misslyckades för ${key} (HTTP ${response.status}).`);
  }
  const payload = await response.json();
  if (payload?.error) {
    throw new Error(`KV-läsning misslyckades för ${key}: ${payload.error}`);
  }
  return payload?.result === null || payload?.result === undefined
    ? null
    : String(payload.result).trim().replace(/^"|"$/g, "");
}

function printPaths(title, paths) {
  if (paths.length === 0) return;
  const shown = paths.slice(0, 40);
  const extra = paths.length - shown.length;
  console.error(title);
  for (const filePath of shown) {
    console.error(`  - ${filePath}`);
  }
  if (extra > 0) {
    console.error(`  ...och ${extra} till.`);
  }
}

function uploadHint() {
  return (
    "Kör efter merge av Python/generation/OpenClaw-ändringar:\n" +
    "  cd apps/viewser && npm run build-context:upload"
  );
}

async function main() {
  const root = repoRoot();
  const [savedSha, savedDirtyRaw] = await Promise.all([
    kvGet(KV_SHA_KEY),
    kvGet(KV_DIRTY_KEY),
  ]);
  const currentSha = currentGitSha(root);
  const savedDirty = savedDirtyRaw === "true";

  if (!savedSha) {
    console.error(
      `Build-context-SHA saknas i KV (${KV_SHA_KEY}). Senaste upload är ` +
        "antingen gammal eller ofullständigt registrerad.",
    );
    console.error(uploadHint());
    process.exitCode = 1;
    return;
  }

  if (!FULL_SHA_RE.test(savedSha)) {
    console.error(
      `Build-context-SHA i KV (${KV_SHA_KEY}) är ogiltig: ${savedSha}.`,
    );
    console.error(uploadHint());
    process.exitCode = 1;
    return;
  }

  try {
    assertCommitExists(root, savedSha);
  } catch {
    console.error(
      `Build-context-SHA ${savedSha} finns inte i denna git-clone. ` +
        "Kontrollen kan därför inte jämföra tarballen mot aktuell checkout.",
    );
    console.error(uploadHint());
    process.exitCode = 1;
    return;
  }

  const changedPaths = changedBuildContextPaths(root, savedSha);
  const dirtyPaths = dirtyBuildContextPaths(root);

  if (!savedDirty && changedPaths.length === 0 && dirtyPaths.length === 0) {
    console.log(
      `Build-kontexten är aktuell: ${savedSha} matchar HEAD ${currentSha} ` +
        "för watched entries.",
    );
    return;
  }

  console.error("VARNING: hostad build-kontext kan vara gammal eller dirty.");
  console.error(`  KV-SHA: ${savedSha}`);
  console.error(`  HEAD:   ${currentSha}`);
  if (savedDirty) {
    console.error(
      `  Senaste upload markerades som dirty i KV (${KV_DIRTY_KEY}=true). ` +
        "Tarballen kan alltså innehålla ocommittade ändringar som inte " +
        "representeras av SHA:n ovan.",
    );
  }
  printPaths("Ändrat sedan senaste build-context-upload:", changedPaths);
  printPaths("Ocommittade ändringar i watched entries just nu:", dirtyPaths);
  console.error(uploadHint());
  process.exitCode = 1;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 2;
});
