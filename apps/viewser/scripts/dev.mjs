// Viewser dev-dispatcher (ADR 0028 — Runtime Ladder).
// ---------------------------------------------------------------------------
// `npm run dev` pekar på den här filen. Operatören sätter EN miljövariabel —
// `VIEWSER_PREVIEW_MODE` i `apps/viewser/.env.local` — och allt som behöver
// växla mellan local-next-iframen och StackBlitz-embeddet växlas konsekvent.
//
// Effekter av läget:
//
//   local-next   →  npx next dev                       (http, COEP off)
//   stackblitz   →  npx next dev --experimental-https  (https, COEP on)
//   auto         →  npx next dev --experimental-https  (https, COEP on)
//
// `local-next` är default. http krävs för att den lokala preview-iframen
// (port 4100-4199, http) inte ska blockas som mixed content av en https-
// host. `stackblitz` och `auto` betalar https-/COEP-kostnaden up-front
// så StackBlitz-embeddet (eller runtime-fallbacken till det) fungerar.
//
// COEP/COOP-headers själva sätts i `next.config.ts`, som läser samma env-
// variabel. Den här filen säkerställer bara att child-processen ärver
// rätt värde och att transport-laget (http vs https) matchar.
//
// Build-pathen (`next build`, `start`) påverkas inte. Den genererade sajten
// är vanlig Next.js oavsett preview-mode. StackBlitz-specifik patchning av
// payloaden (`--webpack`, global-error override, lockfile) i
// `lib/stackblitz-files.ts` triggas bara när runtime-fallbacken faktiskt
// går till StackBlitz, så `local-next` betalar aldrig den kostnaden.

import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const VIEWSER_ROOT = resolve(__dirname, "..");

const VALID_MODES = new Set(["local-next", "stackblitz", "auto"]);
const DEFAULT_MODE = "local-next";

// Tiny inline .env-parser. Avsiktligt minimal: ingen escape-hantering,
// ingen interpolation, ingen multiline. Räcker för vår enda nyckel
// (`VIEWSER_PREVIEW_MODE`) och är ofarlig för övriga rader. Vi vill inte
// dra in `dotenv` som dep bara för det.
function parseEnvFile(path) {
  if (!existsSync(path)) return {};
  const out = {};
  const text = readFileSync(path, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    // Strip surrounding single or double quotes if present.
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) out[key] = value;
  }
  return out;
}

// Precedensordning (lägst → högst): apps/viewser/.env, apps/viewser/.env.local,
// process.env. Det matchar Next.js egen ordning för dev (`.env.local` vinner
// över `.env`) och låter operatören fortfarande overrida via shell.
const fileEnvBase = parseEnvFile(resolve(VIEWSER_ROOT, ".env"));
const fileEnvLocal = parseEnvFile(resolve(VIEWSER_ROOT, ".env.local"));
const mergedEnv = { ...fileEnvBase, ...fileEnvLocal, ...process.env };

const rawMode = (mergedEnv.VIEWSER_PREVIEW_MODE ?? DEFAULT_MODE).trim().toLowerCase();

if (!VALID_MODES.has(rawMode)) {
  process.stderr.write(
    `Okänt VIEWSER_PREVIEW_MODE: '${rawMode}'. ` +
      `Använd local-next, stackblitz, eller auto.\n`,
  );
  process.exit(1);
}

const mode = rawMode;
const useHttps = mode !== "local-next";

const banner =
  mode === "local-next"
    ? "Viewser dev → mode=local-next (http, COEP off, local-preview iframe enabled)"
    : mode === "stackblitz"
      ? "Viewser dev → mode=stackblitz (https, COEP credentialless + COOP same-origin, StackBlitz embed enabled)"
      : "Viewser dev → mode=auto (https, COEP credentialless + COOP same-origin, runtime-fallback redo för StackBlitz)";
process.stdout.write(`${banner}\n`);

// Pass through extra argv (allt efter scriptnamnet). Tillåter t.ex.
// `npm run dev -- --port 3001`.
const passthroughArgs = process.argv.slice(2);
const nextArgs = ["next", "dev", ...(useHttps ? ["--experimental-https"] : []), ...passthroughArgs];

// Använd shell:true så att `npx` löser sig till `npx.cmd` på Windows utan
// att vi behöver hardkoda extension-uppslagning. stdio: "inherit" så
// next.js egen TTY-output (ANSI-färger, ✓ Ready, etc.) går igenom orört.
const child = spawn("npx", nextArgs, {
  cwd: VIEWSER_ROOT,
  stdio: "inherit",
  shell: true,
  env: {
    ...process.env,
    VIEWSER_PREVIEW_MODE: mode,
  },
});

// Forwarda Ctrl-C / SIGTERM till child så servern stannar snyggt när
// operatören dödar dispatchern.
const forwardSignal = (signal) => {
  if (!child.killed) {
    child.kill(signal);
  }
};
process.on("SIGINT", () => forwardSignal("SIGINT"));
process.on("SIGTERM", () => forwardSignal("SIGTERM"));

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});

child.on("error", (err) => {
  process.stderr.write(`Viewser dev-dispatcher kunde inte starta next: ${err.message}\n`);
  process.exit(1);
});
