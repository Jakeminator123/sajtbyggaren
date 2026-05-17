import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const SCRAPE_TIMEOUT_MS = 30_000;

function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

function pythonCommand(): string {
  const venvPython = path.join(
    repoRoot(),
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  if (existsSync(venvPython)) return venvPython;
  return process.platform === "win32" ? "python" : "python3";
}

/**
 * Sanera env mot Next dev-servern på samma sätt som
 * `scripts/build_site.py:_sanitized_npm_env`. Spawnar vi Python från
 * en `next dev`-process ärver child:en `TURBOPACK=1` etc — det stör
 * inte Python själv, men eventuella OpenAI-anrop inifrån scrapen
 * (om `OPENAI_API_KEY` är satt) bör inte få Next-internals i sin
 * kontext. Lika säkert som billigt.
 */
function sanitizedEnv(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (
      key === "TURBOPACK" ||
      key.startsWith("TURBO_") ||
      key === "NEXT_RUNTIME" ||
      key.startsWith("__NEXT_")
    ) {
      delete env[key];
    }
  }
  return env;
}

export type ScrapeResult = {
  ok: boolean;
  data?: Record<string, unknown>;
  meta?: Record<string, unknown>;
  error?: string;
};

export type ScrapeOptions = {
  companyName?: string;
};

/**
 * Spawnar `scripts/scrape_site.py --url <url>` och parserar dess JSON-
 * stdout. Följer samma spawn-mönster som `prompt-runner.ts` /
 * `build-runner.ts` — Viewser shellar alltid ut till Python för att
 * hålla repo-boundaries.v1.json (apps/viewser/ skriver inte mot
 * extern nätverk själv).
 */
export async function runScrapeSite(
  url: string,
  options: ScrapeOptions = {},
): Promise<ScrapeResult> {
  const trimmed = url.trim();
  if (!trimmed) {
    return { ok: false, error: "URL saknas." };
  }

  const scriptPath = path.join(repoRoot(), "scripts", "scrape_site.py");
  if (!existsSync(scriptPath)) {
    return { ok: false, error: `scrape_site.py saknas på disk (${scriptPath}).` };
  }

  const args = [scriptPath, "--url", trimmed];
  if (options.companyName?.trim()) {
    args.push("--company-name", options.companyName.trim());
  }

  const child = spawn(pythonCommand(), args, {
    cwd: repoRoot(),
    env: sanitizedEnv(),
  });

  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf-8");
  child.stderr.setEncoding("utf-8");
  child.stdout.on("data", (chunk: string) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });

  const timer = setTimeout(() => {
    child.kill("SIGTERM");
  }, SCRAPE_TIMEOUT_MS);

  const exitCode: number = await new Promise((resolve) => {
    child.on("close", (code) => resolve(code ?? 1));
  });
  clearTimeout(timer);

  if (exitCode !== 0 && !stdout) {
    return {
      ok: false,
      error: `scrape_site.py exit ${exitCode}: ${stderr.trim().slice(0, 400) || "okänt fel"}`,
    };
  }

  try {
    const parsed = JSON.parse(stdout.trim()) as ScrapeResult;
    if (typeof parsed !== "object" || parsed === null) {
      throw new Error("Ogiltigt JSON-svar från scrape_site.py.");
    }
    return parsed;
  } catch (error) {
    return {
      ok: false,
      error: `Kunde inte tolka scrape-svaret: ${
        error instanceof Error ? error.message : String(error)
      }`,
    };
  }
}
