import { promises as fs } from "node:fs";
import path from "node:path";

import { readBuildResult, runDirFromId, runsDir } from "@/lib/runs";

const MAX_FILE_BYTES = 250_000;
const MAX_TOTAL_BYTES = 5_000_000;
const NPM_LOCKFILE = "package-lock.json";
const BINARY_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".ico",
  ".pdf",
  ".woff",
  ".woff2",
  ".ttf",
  ".eot",
  ".mp4",
  ".mov",
  ".zip",
  ".gz",
  ".tar",
]);

/**
 * B54 + B58: defensive filter against `.env*` leaking into a public
 * StackBlitz preview. Builder's `copy_starter` already blocks `.env*`
 * from landing in `generated-files/` (B4/B5, case-insensitive), but this
 * layer must have its own filter so a future starter, manual operator
 * edit, or drift in the builder cannot bypass the upstream guard.
 * Matches `.env`, `.env.local`, `.env.production`, and case variants
 * like `.ENV` or `.Env.Local`.
 *
 * Allowlist exception: `.env.example` is public placeholder content (it
 * documents which env variables the generated site expects and contains
 * NAMES only, no secrets). It is the only `.env*` file explicitly
 * untracked by `.gitignore` (`!.env.example`). Operators in the
 * StackBlitz preview need to see it so they can copy it to `.env.local`
 * inside the WebContainer to wire up live env-vars. B58 follow-up to B54
 * (reviewer 2026-05-14: blocking `.env.example` was a low-risk
 * functional regression).
 */
function isDotenvFile(basename: string): boolean {
  if (basename === ".env.example") return false;
  const lower = basename.toLowerCase();
  if (!lower.startsWith(".env")) return false;
  return true;
}

function ensureWebpackFlag(command: string): string {
  const trimmed = command.trim();
  if (!trimmed) return "next dev --webpack";
  if (trimmed.includes("--webpack")) return trimmed;
  if (!/\bnext\s+(?:dev|build)\b/.test(trimmed)) return trimmed;
  return `${trimmed} --webpack`;
}

/**
 * StackBlitz/WebContainer Next.js workaround: Next 16 prerenders its built-in
 * `/_global-error` page during `next build`, and that prerender crashes inside
 * the WebContainer WASM runtime with
 * `Invariant: Expected workStore to be initialized`. The same generated site
 * builds green locally; the bug is specific to the WebContainer Node-WASM
 * environment as of Next 16.x.
 *
 * Override the default by injecting a minimal `app/global-error.tsx` into the
 * StackBlitz payload. Next uses our component instead of its default UI when
 * one is present, which sidesteps the broken default prerender path.
 *
 * Only injected into the in-memory StackBlitz file map; never written to disk
 * and never affects the lokal builder, starter, or run-snapshot. Skipped when
 * the generated site already ships its own `app/global-error.tsx`.
 */
const GLOBAL_ERROR_OVERRIDE_PATH = "app/global-error.tsx";
const GLOBAL_ERROR_OVERRIDE_CONTENT = `"use client";

export default function ({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="sv">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          padding: "2rem",
          color: "#111",
          background: "#fff",
        }}
      >
        <h2>Något gick fel</h2>
        <p>{error?.message ?? "Okänt fel"}</p>
        <button
          onClick={() => reset()}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            border: "1px solid #111",
            background: "transparent",
            cursor: "pointer",
          }}
        >
          Försök igen
        </button>
      </body>
    </html>
  );
}
`;

function patchPackageJsonForStackblitz(content: string): string {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return content;
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return content;
  }

  const packageJson = { ...(parsed as Record<string, unknown>) };
  const currentScripts = packageJson.scripts;
  const scripts =
    currentScripts &&
    typeof currentScripts === "object" &&
    !Array.isArray(currentScripts)
      ? { ...(currentScripts as Record<string, unknown>) }
      : {};

  const currentDev = typeof scripts.dev === "string" ? scripts.dev : "next dev";
  scripts.dev = ensureWebpackFlag(currentDev);
  const currentBuild =
    typeof scripts.build === "string" ? scripts.build : "next build";
  scripts.build = ensureWebpackFlag(currentBuild);
  packageJson.scripts = scripts;

  const currentStackblitz = packageJson.stackblitz;
  const stackblitz =
    currentStackblitz &&
    typeof currentStackblitz === "object" &&
    !Array.isArray(currentStackblitz)
      ? { ...(currentStackblitz as Record<string, unknown>) }
      : {};
  stackblitz.installDependencies = true;
  stackblitz.startCommand = "npm run build && npm run start";
  packageJson.stackblitz = stackblitz;

  return `${JSON.stringify(packageJson, null, 2)}\n`;
}

export type StackblitzFileMap = Record<string, string>;

export class RunNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RunNotFoundError";
  }
}

function repoRoot(): string {
  return path.resolve(runsDir(), "..", "..");
}

function resolveRepoRelative(relativeFromRepo: string): string {
  // Repo-relativa paths från build-result.json (POSIX-style separators).
  const normalized = relativeFromRepo.split("/").join(path.sep);
  return path.resolve(repoRoot(), normalized);
}

async function pathIsDirectory(target: string): Promise<boolean> {
  try {
    const stats = await fs.stat(target);
    return stats.isDirectory();
  } catch {
    return false;
  }
}

/**
 * Pick the source directory we should hand to StackBlitz, in this priority:
 *   1. `build-result.generatedFilesDir` (canonical snapshot under data/runs/<runId>/)
 *   2. `data/runs/<runId>/generated-files/` (same path, computed locally)
 *   3. `build-result.devPreviewDir` (legacy fallback, .generated/<siteId>/)
 *
 * This deliberately avoids inventing a new artifact contract; the builder MVP
 * already exposes both fields in `build-result.json`.
 */
async function resolveSourceDir(runId: string): Promise<string> {
  const runDir = await runDirFromId(runId);
  const buildResult = (await readBuildResult(runId)) as {
    generatedFilesDir?: string;
    devPreviewDir?: string;
  };

  const candidates: string[] = [];
  if (buildResult.generatedFilesDir) {
    candidates.push(resolveRepoRelative(buildResult.generatedFilesDir));
  }
  candidates.push(path.join(runDir, "generated-files"));
  if (buildResult.devPreviewDir) {
    candidates.push(resolveRepoRelative(buildResult.devPreviewDir));
  }

  for (const candidate of candidates) {
    if (await pathIsDirectory(candidate)) {
      return candidate;
    }
  }
  throw new RunNotFoundError(
    `Hittade inga preview-filer för run ${runId} (provade ${candidates.length} platser).`,
  );
}

async function walk(root: string, current: string): Promise<string[]> {
  const entries = await fs.readdir(current, { withFileTypes: true });
  const collected: string[] = [];
  for (const entry of entries) {
    const target = path.join(current, entry.name);
    let stat;
    try {
      stat = await fs.lstat(target);
    } catch {
      continue;
    }
    // Refuse symlinks - both directory and file - to avoid escaping the run dir.
    if (stat.isSymbolicLink()) continue;
    if (stat.isDirectory()) {
      collected.push(...(await walk(root, target)));
    } else if (stat.isFile()) {
      collected.push(target);
    }
  }
  return collected;
}

export async function readRunFilesForStackblitz(
  runId: string,
): Promise<StackblitzFileMap> {
  const sourceDir = await resolveSourceDir(runId);
  const files = await walk(sourceDir, sourceDir);
  files.sort();

  const projectFiles: StackblitzFileMap = {};
  let totalBytes = 0;

  for (const filePath of files) {
    const ext = path.extname(filePath).toLowerCase();
    const base = path.basename(filePath);
    if (BINARY_EXTENSIONS.has(ext)) continue;
    if (isDotenvFile(base)) continue;

    const relPath = path
      .relative(sourceDir, filePath)
      .split(path.sep)
      .join("/");
    const stats = await fs.stat(filePath);
    if (stats.size > MAX_FILE_BYTES && relPath !== NPM_LOCKFILE) continue;
    if (totalBytes + stats.size > MAX_TOTAL_BYTES) break;

    const content = await fs.readFile(filePath, "utf-8");
    const patchedContent =
      relPath === "package.json"
        ? patchPackageJsonForStackblitz(content)
        : content;
    projectFiles[relPath] = patchedContent;
    totalBytes += Buffer.byteLength(patchedContent, "utf-8");
  }

  if (!(GLOBAL_ERROR_OVERRIDE_PATH in projectFiles)) {
    projectFiles[GLOBAL_ERROR_OVERRIDE_PATH] = GLOBAL_ERROR_OVERRIDE_CONTENT;
  }

  return projectFiles;
}
