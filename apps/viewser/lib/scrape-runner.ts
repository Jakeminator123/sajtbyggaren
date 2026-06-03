import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

// scripts/scrape_site.py crawlar upp till 5 sidor + ev. LLM-syntes.
// På riktigt seg infrastruktur (eller stora sajter) kan det ta 60-90s
// innan stdout flushas. Tidigare 30s slog ut helt rimliga scraper
// halvvägs och returnerade "exit 1: okänt fel" eftersom SIGTERM
// dödade processen innan den hann printa något.
const SCRAPE_TIMEOUT_MS = 120_000;

function repoRoot(): string {
  // ``...up`` (spread av variabel-array) gör resultatet opakt för Turbopacks
  // statiska analys, så repo-rot-baserade path.join() (t.ex. python-spawn mot
  // ``.venv/bin/python``) inte viks ihop till fil/dir-asset-referenser. Med
  // ``turbopack.root`` = repo-roten (krävs för att resolva ``@preview-runtime``)
  // skulle annars output-tracern panika på ``.venv``-symlänkar som pekar ut ur
  // repo-roten. Detta är rent runtime-logik, aldrig en modul.
  const up = ["..", ".."];
  return path.resolve(process.cwd(), ...up);
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

  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    child.kill();
    // SIGTERM kan ignoreras av en hängd Python-process som väntar på
    // en långsam socket eller har en C-extension i busy loop. Build-
    // och prompt-runnern har sedan länge en 5s SIGKILL-fallback för
    // att garantera att processen försvinner — scrape-runnern fick
    // bara `SIGTERM` när den skrevs och kunde därför läcka hängda
    // python-processer i bakgrunden. `.unref()` så Node:s event loop
    // inte hålls igång enbart av denna inner-timer.
    setTimeout(() => {
      if (!child.killed) {
        try {
          child.kill("SIGKILL");
        } catch {
          // ignore
        }
      }
    }, 5_000).unref?.();
  }, SCRAPE_TIMEOUT_MS);

  const { exitCode, signal } = await new Promise<{
    exitCode: number | null;
    signal: NodeJS.Signals | null;
  }>((resolve) => {
    child.on("close", (code, sig) => resolve({ exitCode: code, signal: sig }));
  });
  clearTimeout(timer);

  if (timedOut) {
    return {
      ok: false,
      error: `Skrapning timeout efter ${Math.round(
        SCRAPE_TIMEOUT_MS / 1000,
      )} sekunder. Sajten kanske är väldigt långsam eller har för mycket innehåll.`,
    };
  }

  if (exitCode !== 0 && !stdout) {
    const reason =
      stderr.trim().slice(0, 400) ||
      (signal ? `dödad av signal ${signal}` : "okänt fel");
    return {
      ok: false,
      error: `scrape_site.py exit ${exitCode ?? "null"}: ${reason}`,
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
