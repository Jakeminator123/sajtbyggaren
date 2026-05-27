import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { promises as fs } from "node:fs";
import path from "node:path";

import { assertProjectInputExists } from "@/lib/project-inputs";
import { readBuildResult, runDirFromId, runsDir } from "@/lib/runs";

// Första bygget i en helt ny `.generated/<siteId>/` involverar:
//   - npm install från noll (typiskt 60–120 sek beroende på cache),
//   - Next.js 16 webpack-build (30–120 sek beroende på sajtens storlek),
//   - operator-asset-copy + sajt-rendering.
// 3 min är därför för snålt — vi tappar perfekt rimliga byggen halvvägs.
// 10 min ger gott om utrymme även för kalla cacher utan att vara orimligt.
const BUILD_TIMEOUT_MS = 600_000;
const RUN_ID_PATTERN = /runId:\s*([a-zA-Z0-9._-]+)/;
const TEST_PROMPT_INPUTS_ENV = "VIEWSER_PROMPT_INPUTS_DIR";
const TEST_ENV_ACTIVE =
  process.env.NODE_ENV === "test" || process.env.SAJTBYGGAREN_TEST === "1";

// Per-siteId mutex för att serialisera byggen mot SAMMA sajt utan att
// blockera byggen mot ANDRA sajter. Tidigare implementation hade en
// enda global ``inFlight: Promise | null`` som tvingade alla byggen
// att vänta på varandra — ett segt/hängande bygge på ``cafe-bistro``
// blockerade en helt orelaterad ``painter-palma``-build i samma
// Viewser-process. Reviewer-fynd 2026-05-25 (Round 2 #5).
//
// Map<siteId, Promise> queue:ar byggen per sajt. ``runBuild(siteId)``
// väntar bara på pending build för EXAKT samma siteId; två siteIds
// kan köra parallellt. ``finally``-grenen rensar entry:t bara om
// promise:n fortfarande är den aktiva — så en följdbygge som hunnit
// skriva en ny entry inte oavsiktligt nukas.
//
// Den per-siteId-låsen är fortsatt nödvändig för att inte få två
// build_site.py-processer som samtidigt skriver till
// ``.generated/<siteId>/``-mappen + ``data/runs/<runId>/``-snapshot.
// Det skulle ge halvskrivna artefakter och korrupta run-snapshots.
const inFlight = new Map<string, Promise<unknown>>();

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

// Allow callers (the prompt-driven flow in particular) to pass a fully
// resolved Project Input path that lives outside `examples/`. Whitelist
// the two repo-local roots we trust so a crafted `dossierPath` from the
// API surface cannot point build_site.py at an arbitrary file on disk.
const ALLOWED_DOSSIER_ROOTS = ["examples", path.join("data", "prompt-inputs")];

async function assertDossierPathAllowed(absoluteDossierPath: string): Promise<void> {
  const root = repoRoot();
  const resolved = await fs.realpath(path.resolve(absoluteDossierPath));
  // Test-only isolation: set SAJTBYGGAREN_TEST=1 (or NODE_ENV=test) with
  // VIEWSER_PROMPT_INPUTS_DIR to whitelist tmp Project Inputs.
  const testPromptRoot = process.env[TEST_PROMPT_INPUTS_ENV]?.trim();
  const roots =
    testPromptRoot && TEST_ENV_ACTIVE
      ? [...ALLOWED_DOSSIER_ROOTS, path.resolve(root, testPromptRoot)]
      : ALLOWED_DOSSIER_ROOTS;
  for (const subdir of roots) {
    const allowed = await fs.realpath(path.resolve(root, subdir)).catch(() => null);
    if (!allowed) continue;
    const relative = path.relative(allowed, resolved);
    if (
      (relative === "" || relative) &&
      !relative.startsWith("..") &&
      !path.isAbsolute(relative)
    ) {
      return;
    }
  }
  throw new Error(
    `Dossier-path ligger utanför tillåtna rötter (${roots.join(", ")}): ${absoluteDossierPath}`,
  );
}

async function detectLatestRunIdByMtime(): Promise<string | null> {
  const root = runsDir();
  let entries;
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }
    throw error;
  }
  const dirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  if (!dirs.length) return null;

  const stats = await Promise.all(
    dirs.map(async (name) => {
      try {
        const stat = await fs.stat(path.join(root, name));
        return { name, mtimeMs: stat.mtimeMs };
      } catch {
        return null;
      }
    }),
  );
  const live = stats.filter((entry): entry is { name: string; mtimeMs: number } => entry !== null);
  if (!live.length) return null;
  live.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return live[0].name;
}

async function runBuildOnce(
  siteId: string,
  dossierPathOverride?: string,
): Promise<{
  runId: string;
  buildResult: Record<string, unknown>;
  stderr: string;
}> {
  // The default flow validates that examples/<siteId>.project-input.json
  // exists. The prompt-driven flow already wrote the Project Input to
  // data/prompt-inputs/<siteId>.project-input.json via the Python helper
  // and passes that absolute path here; we only re-check that the path
  // sits under one of the allowed roots so a crafted API payload cannot
  // point build_site.py at /etc/passwd.
  let dossierPath: string;
  if (dossierPathOverride) {
    await assertDossierPathAllowed(dossierPathOverride);
    await fs.access(dossierPathOverride);
    dossierPath = dossierPathOverride;
  } else {
    dossierPath = await assertProjectInputExists(siteId);
  }
  const scriptPath = path.join(repoRoot(), "scripts", "build_site.py");
  const args = [scriptPath, "--dossier", dossierPath];
  // Test-only runs isolation: set SAJTBYGGAREN_TEST=1 and VIEWSER_RUNS_DIR.
  const testRunsDir = TEST_ENV_ACTIVE ? process.env.VIEWSER_RUNS_DIR?.trim() : "";
  if (testRunsDir) args.push("--runs-dir", path.resolve(repoRoot(), testRunsDir));

  const child = spawn(
    pythonCommand(),
    args,
    {
      cwd: repoRoot(),
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  const stdoutChunks: string[] = [];
  const stderrChunks: string[] = [];
  let totalStdoutBytes = 0;
  let totalStderrBytes = 0;
  const MAX_STREAM_BYTES = 256 * 1024;

  child.stdout.on("data", (chunk: Buffer) => {
    if (totalStdoutBytes >= MAX_STREAM_BYTES) return;
    totalStdoutBytes += chunk.byteLength;
    stdoutChunks.push(chunk.toString("utf-8"));
  });
  child.stderr.on("data", (chunk: Buffer) => {
    if (totalStderrBytes >= MAX_STREAM_BYTES) return;
    totalStderrBytes += chunk.byteLength;
    stderrChunks.push(chunk.toString("utf-8"));
  });

  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    child.kill();
    setTimeout(() => {
      if (!child.killed) {
        try {
          child.kill("SIGKILL");
        } catch {
          // ignore
        }
      }
    }, 5_000).unref?.();
  }, BUILD_TIMEOUT_MS);

  const exitCode = await new Promise<number>((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code) => resolve(code ?? 1));
  });
  clearTimeout(timeout);

  const stdout = stdoutChunks.join("");
  const stderr = stderrChunks.join("");
  if (timedOut) {
    throw new Error(
      `build_site.py överskred ${BUILD_TIMEOUT_MS}ms och avbröts. stderr=${stderr.slice(-500)}`,
    );
  }

  // Builder MVP contract (docs/architecture/builder-mvp.md "Builder-
  // guards"): when npm install / npm run build fails, build_site.py
  // STILL writes the canonical artefakter (build-result.json with
  // status=failed, plus quality-result.json + repair-result.json + the
  // generated-files/ snapshot) and exits 1. The dev wrapper used to
  // throw on any non-zero exit, which dropped the runId on the floor
  // and forced /api/build to return 500 with no way for the UI to
  // surface a failed run. Treat the structured-failure path as a
  // pedagogical result instead: if THIS process printed `runId: ...`
  // to stdout AND build-result.json exists on disk, return it so the
  // Run History entry shows up with status=failed and the
  // RunDetailsPanel can render the four artefakter for diagnosis.
  //
  // B42 (post-review-2): the previous version fell back to
  // detectLatestRunIdByMtime() in the failure path too. That meant a
  // crash BEFORE build_site.py printed `runId:` (e.g. KeyError on the
  // Project Input load, FileNotFoundError on scaffold lookup) would
  // pick the PRIOR run-dir on disk and return it as the current
  // build's "structured failure". The wrapper now only honors the
  // mtime-fallback on the success-path (where build_site.py must have
  // completed, so the latest run-dir IS this build's) and STRICTLY
  // requires the printed runId in the failure-path.
  const runIdFromStdout = stdout.match(RUN_ID_PATTERN)?.[1] ?? null;

  if (exitCode !== 0) {
    if (runIdFromStdout) {
      try {
        await runDirFromId(runIdFromStdout);
        const buildResult = await readBuildResult(runIdFromStdout);
        return { runId: runIdFromStdout, buildResult, stderr };
      } catch {
        // runId printed but artefakter incomplete - fall through.
      }
    }
    throw new Error(
      `build_site.py misslyckades (${exitCode}) utan strukturerad output.\n${stderr || stdout}`.slice(
        0,
        4000,
      ),
    );
  }

  // Success path: mtime-fallback is safe because exitCode === 0 means
  // build_site.py wrote the run-dir successfully even if the stdout
  // buffer was truncated mid-line.
  const runId = runIdFromStdout ?? (await detectLatestRunIdByMtime());
  if (!runId) {
    throw new Error("Kunde inte hitta runId från build-resultatet.");
  }

  await runDirFromId(runId);
  const buildResult = await readBuildResult(runId);
  return { runId, buildResult, stderr };
}

/**
 * Run build_site.py for a given siteId. Concurrent invocations are serialized
 * with a single in-flight promise so two parallel POSTs do not race over the
 * same generated preview directory (by default
 * `../sajtbyggaren-output/.generated/<siteId>/`) or confuse the "latest run"
 * fallback.
 *
 * `dossierPathOverride` is the bridge for the prompt-driven flow: the
 * Python helper writes the Project Input to `data/prompt-inputs/` (NOT
 * to `examples/`, which apps/viewser is forbidden to write to per
 * repo-boundaries.v1.json) and passes the resulting absolute path here
 * so build_site.py reads from the scratch directory instead of the
 * curated examples set.
 */
export async function runBuild(
  siteId: string,
  dossierPathOverride?: string,
): Promise<{
  runId: string;
  buildResult: Record<string, unknown>;
  stderr: string;
}> {
  // Vänta på pending build för EXAKT denna siteId — andra siteIds
  // får köra parallellt. Loop:en hanterar fallet att en följdbygge
  // skrivit en ny entry medan vi väntade på den föregående: vi
  // måste läsa Map:en igen efter varje await för att inte missa
  // den nya pending.
  while (inFlight.has(siteId)) {
    try {
      await inFlight.get(siteId);
    } catch {
      // previous build failed; that's fine, fall through and start a new one
    }
  }

  const promise = runBuildOnce(siteId, dossierPathOverride);
  inFlight.set(siteId, promise);
  try {
    return await promise;
  } finally {
    // Rensa entry:t bara om promise:n FORTFARANDE är den aktiva.
    // Om en samtidig caller redan skrivit en ny pending nukar vi
    // inte hennes. Speglar samma försiktiga rensning som den
    // tidigare globala ``if (inFlight === promise)``-grenen.
    if (inFlight.get(siteId) === promise) {
      inFlight.delete(siteId);
    }
  }
}
