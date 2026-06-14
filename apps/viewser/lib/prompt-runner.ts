import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

import { writeTextArgFile } from "./text-arg-file";

const PROMPT_TIMEOUT_MS = 90_000;
const TEST_PROMPT_INPUTS_ENV = "VIEWSER_PROMPT_INPUTS_DIR";

const SITE_ID_LINE = /^siteId:\s*(.+)$/m;
const PROJECT_ID_LINE = /^projectId:\s*(.+)$/m;
const DOSSIER_PATH_LINE = /^dossierPath:\s*(.+)$/m;
const META_PATH_LINE = /^metaPath:\s*(.+)$/m;
const VERSION_LINE = /^version:\s*(.+)$/m;
const BRIEF_SOURCE_LINE = /^briefSource:\s*(.+)$/m;

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

function testPromptInputsDir(): string | null {
  // Test-only isolation: set SAJTBYGGAREN_TEST=1 (or NODE_ENV=test)
  // together with VIEWSER_PROMPT_INPUTS_DIR to keep smoke-test writes
  // out of repo-local data/prompt-inputs/. Production ignores the env.
  const raw = process.env[TEST_PROMPT_INPUTS_ENV]?.trim();
  if (!raw || (process.env.NODE_ENV !== "test" && process.env.SAJTBYGGAREN_TEST !== "1")) {
    return null;
  }
  return path.resolve(repoRoot(), raw);
}

export type PromptHelperResult = {
  siteId: string;
  projectId: string;
  dossierPath: string;
  metaPath: string;
  version: number | null;
  briefSource: string | null;
  stderr: string;
};

export type PromptHelperOptions = {
  mode?: "init" | "followup";
  siteId?: string;
  /**
   * Iterera från en specifik historisk run istället för senaste. När satt
   * skickas ``--base-run-id`` till `scripts/prompt_to_project_input.py`
   * vilket läser PI-snapshotet från ``data/prompt-inputs/<siteId>.v<N>.*``
   * där ``N`` matchar runens version. Bakåt-kompatibel: utan baseRunId
   * läser helpern senaste PI som idag.
   */
  baseRunId?: string;
  /**
   * Discovery-payload från `apps/viewser/components/discovery-wizard`.
   * Skrivs till en tempfil och skickas till
   * `prompt_to_project_input.py --discovery <path>` så wizardens
   * deterministiska svar patchar Project Input efter LLM-extraktion.
   *
   * Kontraktet följer `DiscoveryPayload` i `wizard-payload.ts`.
   */
  discovery?: unknown;
  /**
   * ADR 0046: operatörens preview-markeringar ("Markera modul").
   * Skickas som `--marked-sections <json>` till Python-helpern, som
   * validerar varje markering mot base-runens emittedSections-facit.
   * Endast giltig i follow-up-läge. Mjuk prioriteringssignal — triggar
   * aldrig ensam en build.
   */
  markedSections?: { routeId: string; sectionId: string; note?: string }[];
  /**
   * Specialist-dispatch steg 2 (task A): strukturerat verktygs-intent
   * från builder-dialogerna. Bara ``asset_set`` forwardas som
   * ``--tool-intent <json>`` (övriga tools konsumeras i sina egna
   * sömmar). Params saneras fält för fält före spawn — Python-helpern
   * re-validerar dessutom allt mot AssetRef-schemat innan refen landar
   * i Project Input. Endast giltig i follow-up-läge.
   */
  toolIntent?: { tool: string; params: Record<string, unknown> };
};

// Samma slug-grammatik som /api/prompt-schemats SECTION_REF_PATTERN och
// Python-sidans parse_marked_sections — defense-in-depth eftersom spawn()
// inte quotar argument.
const SECTION_REF_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

// asset_set-sanering: speglar _ASSET_ID_PATTERN/_FILENAME_PATTERN i
// packages/generation/followup/asset_intent.py. Inga path-tecken i
// filename (refereras som /uploads/<filename> + läses från disk i
// manifest-fallbacken på Python-sidan).
const ASSET_ID_PATTERN = /^[a-zA-Z0-9_-]{1,128}$/;
const ASSET_FILENAME_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$/;
const ASSET_ROLES = new Set(["logo", "hero", "gallery"]);

/**
 * Bygg den sanerade ``--tool-intent``-payloaden eller null när intentet
 * inte ska forwardas (annat tool än asset_set, eller ogiltiga
 * obligatoriska fält). Optionella fält släpps bara igenom när de har
 * rätt typ — Python-helpern är auktoritativ validering, det här är
 * defense-in-depth före spawn.
 *
 * Exporterad så den hostade byggvägen (hosted-build-runner.ts) kör
 * EXAKT samma sanering före env-injektionen i sandboxen — en
 * saneringskälla, två spawn-sömmar.
 */
export function sanitizedAssetSetIntent(
  toolIntent: NonNullable<PromptHelperOptions["toolIntent"]>,
): { tool: "asset_set"; params: Record<string, unknown> } | null {
  if (toolIntent.tool !== "asset_set") return null;
  const params = toolIntent.params ?? {};
  const role = typeof params.role === "string" ? params.role : "";
  const assetId = typeof params.assetId === "string" ? params.assetId : "";
  const filename = typeof params.filename === "string" ? params.filename : "";
  if (
    !ASSET_ROLES.has(role) ||
    !ASSET_ID_PATTERN.test(assetId) ||
    !ASSET_FILENAME_PATTERN.test(filename)
  ) {
    return null;
  }
  const safeParams: Record<string, unknown> = { role, assetId, filename };
  for (const key of ["mimeType", "alt", "hint", "placement", "sourceUrl"] as const) {
    const value = params[key];
    if (typeof value === "string" && value.trim()) {
      safeParams[key] = value.trim().slice(0, 500);
    }
  }
  for (const key of ["sizeBytes", "width", "height"] as const) {
    const value = params[key];
    if (typeof value === "number" && Number.isInteger(value) && value > 0) {
      safeParams[key] = value;
    }
  }
  return { tool: "asset_set", params: safeParams };
}

/**
 * Re-validera + kapa preview-markeringarna (ADR 0046) till den sanerade
 * ``--marked-sections``-formen, eller [] när inget giltigt återstår.
 * Speglar Python-sidans ``parse_marked_sections`` (slug-grammatik, max 5,
 * note ≤ 200 tecken) — defense-in-depth eftersom varken spawn() eller env
 * quotar argument. Ogiltiga poster filtreras bort i stället för att fälla
 * hela follow-upen (Python-sidan droppar ändå okända markeringar med varning).
 *
 * Exporterad så den hostade byggvägen (hosted-build-runner.ts) kör EXAKT
 * samma sanering före env-injektionen i sandboxen — en saneringskälla, två
 * spawn-sömmar (samma mönster som ``sanitizedAssetSetIntent``).
 */
export function sanitizedMarkedSections(
  markedSections:
    | { routeId: string; sectionId: string; note?: string }[]
    | undefined,
): { routeId: string; sectionId: string; note?: string }[] {
  if (!markedSections?.length) return [];
  return markedSections
    .filter(
      (entry) =>
        SECTION_REF_PATTERN.test(entry.routeId) &&
        SECTION_REF_PATTERN.test(entry.sectionId),
    )
    .slice(0, 5)
    .map((entry) => ({
      routeId: entry.routeId,
      sectionId: entry.sectionId,
      ...(entry.note ? { note: entry.note.slice(0, 200) } : {}),
    }));
}

/**
 * Spawn `scripts/prompt_to_project_input.py` and parse its stdout.
 *
 * Mirrors the spawn pattern in build-runner.ts (we already shell out to
 * Python for build_site.py) so the two tools share one mental model:
 * apps/viewser/ never writes to data/ or examples/ itself per
 * repo-boundaries.v1.json - the Python script in scripts/ does the
 * writing on viewser's behalf, exactly the same way build_site.py does
 * for `data/runs/` + `.generated/`.
 *
 * Concurrency control lives one layer up in build-runner.ts: this
 * helper deliberately stays single-purpose so it can be unit-tested
 * without the build mutex.
 */
export async function runPromptToProjectInput(
  prompt: string,
  options: PromptHelperOptions = {},
): Promise<PromptHelperResult> {
  const trimmed = prompt.trim();
  if (!trimmed) {
    throw new Error("Prompt får inte vara tom.");
  }

  const scriptPath = path.join(repoRoot(), "scripts", "prompt_to_project_input.py");
  const args = [scriptPath];
  const outputDir = testPromptInputsDir();
  if (outputDir) args.push("--output-dir", outputDir);
  if (options.mode === "followup") {
    if (!options.siteId) {
      throw new Error("Följdprompt kräver ett valt siteId.");
    }
    args.push("--followup-site-id", options.siteId);
    if (options.baseRunId) {
      // Validation already happened in /api/prompt route via the regex
      // (RUN_ID_PATTERN). We re-assert here as a defense-in-depth check
      // because spawn() does not quote args — a malicious value with
      // spaces/quotes could otherwise still affect downstream parsing.
      if (!/^[a-zA-Z0-9._-]+$/.test(options.baseRunId)) {
        throw new Error(`Ogiltigt baseRunId: ${options.baseRunId}`);
      }
      args.push("--base-run-id", options.baseRunId);
    }
    if (options.markedSections?.length) {
      // ADR 0046: re-validera id-grammatiken före spawn (zod-laget har
      // redan validerat, men spawn() quotar inte argument). En saneringskälla
      // delad med den hostade vägen (sanitizedMarkedSections).
      const safeMarkings = sanitizedMarkedSections(options.markedSections);
      if (safeMarkings.length) {
        args.push("--marked-sections", JSON.stringify(safeMarkings));
      }
    }
    if (options.toolIntent) {
      const safeIntent = sanitizedAssetSetIntent(options.toolIntent);
      if (safeIntent) {
        args.push("--tool-intent", JSON.stringify(safeIntent));
      }
    }
  } else if (options.baseRunId) {
    // Defense-in-depth: schema-laget förbjuder redan baseRunId i init-läge,
    // men om helpern någonsin anropas direkt så låter vi felet bubbla.
    throw new Error("baseRunId kan bara anges i follow-up-läge.");
  }

  // Discovery-payload: skriv till tempdir så Python kan läsa den.
  // Tempfilen rensas efter spawn:n oavsett utfall för att inte läcka
  // operatörens svar på disk längre än nödvändigt. Discovery accepteras
  // bara i init-läge — follow-up återanvänder befintlig PI.
  let discoveryTempDir: string | null = null;
  if (options.discovery !== undefined && options.mode !== "followup") {
    discoveryTempDir = mkdtempSync(path.join(os.tmpdir(), "sb-discovery-"));
    const discoveryFile = path.join(discoveryTempDir, "discovery.json");
    writeFileSync(discoveryFile, JSON.stringify(options.discovery), "utf-8");
    args.push("--discovery", discoveryFile);
  }

  // B204: route the operator prompt through a UTF-8 temp file instead of
  // passing it as a process argument. On some Windows consoles a non-ASCII
  // LEADING character in argv is mangled on the Node→OS→Python hop (operator
  // finding: "Ändra …" was stored as "*ndra …"); a UTF-8 file read back with
  // encoding="utf-8" round-trips every Swedish char intact. Same defensive
  // transport the discovery payload already uses above. ``--prompt-file`` also
  // makes the old ``--`` dash-guard unnecessary — a prompt that happens to
  // start with `-`/`--` (a pasted bullet list) never reaches argv anymore.
  const promptArg = writeTextArgFile(trimmed, "sb-prompt-");
  args.push("--prompt-file", promptArg.path);

  const child = spawn(pythonCommand(), args, {
    cwd: repoRoot(),
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

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
  }, PROMPT_TIMEOUT_MS);

  let exitCode: number;
  try {
    exitCode = await new Promise<number>((resolve, reject) => {
      child.once("error", reject);
      child.once("close", (code) => resolve(code ?? 1));
    });
  } finally {
    clearTimeout(timeout);
    // Drop the operator's prompt + discovery answers from disk regardless of
    // outcome (success, non-zero exit, or a spawn "error" rejection) so the
    // free text never lingers longer than the single CLI invocation.
    promptArg.cleanup();
    if (discoveryTempDir) {
      try {
        rmSync(discoveryTempDir, { recursive: true, force: true });
      } catch {
        // best-effort cleanup — tmp-dir städas av OS:n vid omstart om vi missar
      }
    }
  }

  const stdout = stdoutChunks.join("");
  const stderr = stderrChunks.join("");

  if (timedOut) {
    throw new Error(
      `prompt_to_project_input.py överskred ${PROMPT_TIMEOUT_MS}ms och avbröts. stderr=${stderr.slice(-500)}`,
    );
  }
  if (exitCode !== 0) {
    throw new Error(
      `prompt_to_project_input.py misslyckades (exit ${exitCode}).\n${(stderr || stdout).slice(-2000)}`,
    );
  }

  const siteId = stdout.match(SITE_ID_LINE)?.[1]?.trim();
  const projectId = stdout.match(PROJECT_ID_LINE)?.[1]?.trim();
  const dossierPath = stdout.match(DOSSIER_PATH_LINE)?.[1]?.trim();
  const metaPath = stdout.match(META_PATH_LINE)?.[1]?.trim();
  const versionRaw = stdout.match(VERSION_LINE)?.[1]?.trim();
  const parsedVersion = versionRaw ? Number.parseInt(versionRaw, 10) : null;
  const briefSource = stdout.match(BRIEF_SOURCE_LINE)?.[1]?.trim() ?? null;

  if (!siteId || !projectId || !dossierPath || !metaPath) {
    throw new Error(
      `prompt_to_project_input.py output saknar siteId/projectId/dossierPath/metaPath:\n${stdout.slice(0, 1000)}`,
    );
  }

  return {
    siteId,
    projectId,
    dossierPath,
    metaPath,
    version:
      parsedVersion === null || Number.isNaN(parsedVersion)
        ? null
        : parsedVersion,
    briefSource: briefSource === "None" ? null : briefSource,
    stderr,
  };
}
