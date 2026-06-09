// Single source of truth for "where build_site.py wrote the generated site".
//
// Both the local preview server and the Vercel-sandbox runner previously
// re-implemented this resolution with subtly different logic:
//   - local-preview-server.ts derived the repo root from process.cwd() (breaks
//     if Viewser is launched from another directory),
//   - both resolved a RELATIVE SAJTBYGGAREN_GENERATED_DIR against process.cwd(),
//     while the Python builder (scripts/build_site.py:resolve_generated_dir)
//     resolves it against the REPO ROOT.
// That divergence meant a relative override made the builder WRITE one place
// and the preview READ another. This module is the one canonical resolver so
// the Node preview side and the Python builder always agree.
//
// It also lets the repo-root `.env` act as a single source of truth: when the
// value is not already in process.env (e.g. it was only set in the repo-root
// `.env`, which Next does not load for apps/viewser), it is read directly from
// `<repo>/.env`. Mirrors the dependency-free parser in
// apps/viewser/scripts/dev.mjs so both read the same file the same way.

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Repo root derived from THIS module's location (cwd-INDEPENDENT). The file
 * lives at `<repo>/apps/viewser/lib/generated-dir.ts`, so three levels up from
 * `lib/` is the repo root.
 */
export function repoRoot(): string {
  const moduleDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(moduleDir, "..", "..", "..");
}

/**
 * Read a single key from the repo-root `.env` without any dependency. Handles
 * the common dotenv forms `KEY=value`, an optional `export ` prefix, quoted
 * values and a trailing ` # comment` — the same subset `dev.mjs` accepts.
 * Returns `undefined` when the file or key is absent.
 */
export function readRepoEnvVar(name: string): string | undefined {
  const envPath = path.join(repoRoot(), ".env");
  if (!existsSync(envPath)) return undefined;
  let text: string;
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

/**
 * Resolve the directory `build_site.py` writes generated sites into.
 *
 * Precedence (mirrors scripts/build_site.py:resolve_generated_dir):
 *   1. `process.env.SAJTBYGGAREN_GENERATED_DIR` (shell / Next-loaded .env*),
 *   2. repo-root `.env` `SAJTBYGGAREN_GENERATED_DIR` (the single-source file),
 *   3. default `../sajtbyggaren-output/.generated` relative to the repo root.
 *
 * A RELATIVE value resolves against the REPO ROOT (not `process.cwd()`), so the
 * preview side and the builder land on the exact same absolute directory.
 */
export function resolveGeneratedDir(): string {
  const fromProcess = process.env.SAJTBYGGAREN_GENERATED_DIR?.trim();
  const raw = fromProcess || readRepoEnvVar("SAJTBYGGAREN_GENERATED_DIR")?.trim();
  const root = repoRoot();
  if (raw) {
    return path.isAbsolute(raw) ? path.resolve(raw) : path.resolve(root, raw);
  }
  return path.join(root, "..", "sajtbyggaren-output", ".generated");
}
