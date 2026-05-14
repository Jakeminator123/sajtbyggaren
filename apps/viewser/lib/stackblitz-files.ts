import { promises as fs } from "node:fs";
import path from "node:path";

import { readBuildResult, runDirFromId, runsDir } from "@/lib/runs";

const MAX_FILE_BYTES = 250_000;
const MAX_TOTAL_BYTES = 5_000_000;
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

const FILES_TO_SKIP = new Set(["package-lock.json"]);

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
  const lower = basename.toLowerCase();
  if (!lower.startsWith(".env")) return false;
  if (lower === ".env.example") return false;
  return true;
}

function ensureWebpackFlag(command: string): string {
  const trimmed = command.trim();
  if (!trimmed) return "next dev --webpack";
  if (trimmed.includes("--webpack")) return trimmed;
  if (!/\bnext\s+dev\b/.test(trimmed)) return trimmed;
  return `${trimmed} --webpack`;
}

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
  packageJson.scripts = scripts;

  const currentStackblitz = packageJson.stackblitz;
  const stackblitz =
    currentStackblitz &&
    typeof currentStackblitz === "object" &&
    !Array.isArray(currentStackblitz)
      ? { ...(currentStackblitz as Record<string, unknown>) }
      : {};
  stackblitz.installDependencies = true;
  stackblitz.startCommand = "npm run dev";
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

export async function readRunFilesForStackblitz(runId: string): Promise<StackblitzFileMap> {
  const sourceDir = await resolveSourceDir(runId);
  const files = await walk(sourceDir, sourceDir);
  files.sort();

  const projectFiles: StackblitzFileMap = {};
  let totalBytes = 0;

  for (const filePath of files) {
    const ext = path.extname(filePath).toLowerCase();
    const base = path.basename(filePath);
    if (FILES_TO_SKIP.has(base) || BINARY_EXTENSIONS.has(ext)) continue;
    if (isDotenvFile(base)) continue;

    const stats = await fs.stat(filePath);
    if (stats.size > MAX_FILE_BYTES) continue;
    if (totalBytes + stats.size > MAX_TOTAL_BYTES) break;

    const relPath = path.relative(sourceDir, filePath).split(path.sep).join("/");
    const content = await fs.readFile(filePath, "utf-8");
    const patchedContent =
      relPath === "package.json" ? patchPackageJsonForStackblitz(content) : content;
    projectFiles[relPath] = patchedContent;
    totalBytes += Buffer.byteLength(patchedContent, "utf-8");
  }

  return projectFiles;
}
