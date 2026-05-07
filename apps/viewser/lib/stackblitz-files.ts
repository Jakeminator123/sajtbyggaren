import { promises as fs } from "node:fs";
import path from "node:path";

import { runDirFromId } from "@/lib/runs";

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

export type StackblitzFileMap = Record<string, string>;

async function walk(dir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map(async (entry) => {
      const target = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        return walk(target);
      }
      return [target];
    }),
  );
  return nested.flat();
}

export async function readRunFilesForStackblitz(runId: string): Promise<StackblitzFileMap> {
  const runDir = await runDirFromId(runId);
  const generatedDir = path.join(runDir, "generated-files");

  const files = await walk(generatedDir);
  const projectFiles: StackblitzFileMap = {};
  let totalBytes = 0;

  for (const filePath of files) {
    const ext = path.extname(filePath).toLowerCase();
    const base = path.basename(filePath);
    if (FILES_TO_SKIP.has(base) || BINARY_EXTENSIONS.has(ext)) {
      continue;
    }

    const stats = await fs.stat(filePath);
    if (stats.size > MAX_FILE_BYTES) {
      continue;
    }
    if (totalBytes + stats.size > MAX_TOTAL_BYTES) {
      break;
    }

    const relPath = path.relative(generatedDir, filePath).replaceAll("\\", "/");
    const content = await fs.readFile(filePath, "utf-8");
    projectFiles[relPath] = content;
    totalBytes += stats.size;
  }

  return projectFiles;
}
