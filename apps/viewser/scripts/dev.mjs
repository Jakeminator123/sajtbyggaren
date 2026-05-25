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
// Den här dispatchern är AVSIKTLIGT dev-only. Production-pathen går genom
// `next build` + `next start` (npm-scripten `build`/`start`), aldrig genom
// `npm run dev`, och därmed aldrig genom den här filen. Det är därför
// dispatchern inte behöver känna till `NODE_ENV` — säkerhetsgaten som
// promotar `local-next` → `stackblitz`-headers i produktion sitter i
// `next.config.ts` (där den ändå är auktoritativ för COEP/COOP-utfallet).
// Att lägga gaten även här skulle bara duplicera regeln och riskera att de
// går i otakt vid framtida refaktorering.
//
// Build-pathen (`next build`, `start`) påverkas inte. Den genererade sajten
// är vanlig Next.js oavsett preview-mode. StackBlitz-specifik patchning av
// payloaden (`--webpack`, global-error override, lockfile) i
// `lib/stackblitz-files.ts` triggas bara när runtime-fallbacken faktiskt
// går till StackBlitz, så `local-next` betalar aldrig den kostnaden.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const VIEWSER_ROOT = resolve(__dirname, "..");
const IS_WINDOWS = process.platform === "win32";

const VALID_MODES = new Set(["local-next", "stackblitz", "auto"]);
const DEFAULT_MODE = "local-next";

// Tiny inline .env-parser. Avsiktligt minimal: ingen multiline. Hanterar
// dock de vanliga POSIX-shell / dotenv-formerna som `next dev` självt
// accepterar, så dispatchern inte rejectar en rad som next.js skulle ha
// läst utan problem (Codex P2-fynd på parkerade PR #85: `export VAR=val`
// och trailing `# comment` rejectades tidigare som "Okänt
// VIEWSER_PREVIEW_MODE"; Bugbot Medium på PR #88: en literal som
// `VAR="local-next" # note` matchade tidigare varken quoted-grenen
// (kräver att värdet både börjar OCH slutar med citat — men `e` ≠ `"`)
// eller unquoted-comment-strippningen, vilket gav `"local-next"` med
// citat kvar och därmed false-reject mot mode-validatorn).
//
// Dotenv-expansion av `$VAR` / `${VAR}`-referenser sker INTE här utan
// vid use-site i `expandEnvRefs` nedan — vi expanderar bara den enda
// variabel dispatchern faktiskt konsumerar, inte hela env-mappen.
function parseEnvFile(path) {
  if (!existsSync(path)) return {};
  const out = {};
  const text = readFileSync(path, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    let line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    // Strip optional POSIX-shell `export ` prefix (dotenv accepterar det).
    if (line.startsWith("export ")) {
      line = line.slice(7).trimStart();
    }
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    // Quoted-grenen: matcha första citat, tolerera optional trailing
    // whitespace + `# comment` EFTER stängande citat. Non-greedy `*?`
    // så `"a"x"b"` stoppar vid första matchande quote (matchar dotenv-
    // beteende — escapes hanteras inte, men en escapad `\\"` räknas som
    // litteralt par i pattern och bryter inte den naive matchningen).
    // Whitespace-kravet före `#` är medvetet utelämnat efter stängande
    // citat eftersom citaten redan terminerar värdet, så `"v"#x` är
    // entydigt en kommentar.
    const quotedMatch = value.match(/^(['"])((?:[^\\]|\\.)*?)\1\s*(?:#.*)?$/);
    if (quotedMatch) {
      value = quotedMatch[2];
    } else {
      // Oquoterat värde: strippa trailing inline-kommentar (` # ...`).
      // Vi kräver whitespace före `#` så URL-fragments som
      // `https://x.com#frag` inte mangslås — bara dotenv-stil
      // `VAR=val # note` triggar strippningen.
      const commentMatch = value.match(/\s+#.*$/);
      if (commentMatch) {
        value = value.slice(0, commentMatch.index).trimEnd();
      }
    }
    if (key) out[key] = value;
  }
  return out;
}

// expandEnvRefs: enkel dotenv-expand-replikering för `$VAR` och `${VAR}`-
// referenser i ETT värde mot en redan-mergad env-map. Avsiktligt enkel:
//
//   - Single-pass (ingen rekursiv resolve). Räcker för dispatcherns
//     enda konsument (VIEWSER_PREVIEW_MODE) och undviker risken för
//     kedje-loops på uttryck som `A=$B` / `B=$A`.
//   - Stödjer både `${VAR}` (braced) och `$VAR` (bare). dotenv-expand
//     stödjer båda; att stödja bara en av dem skapar ett
//     beteendeglapp mot vad `next dev` ser i samma .env-fil.
//   - `\\$` (escapad dollar) → litteralt `$`. Matchar dotenv-expand.
//   - Okända referenser → tom sträng. Matchar dotenv-expand och är
//     säkrare än att lämna kvar `$VAR` som en literal som sedan
//     reggar fel mot mode-validatorn.
//
// Codex P2 på PR #88 motiverar detta: en `.env*`-fil med
// `VIEWSER_PREVIEW_MODE=$PREVIEW_DEFAULT` skulle utan expansion
// gått igenom verbatim och failat validatorn med "Okänt VIEWSER_PREVIEW_MODE:
// '$PREVIEW_DEFAULT'", även om next dev självt (via @next/env's
// dotenv-expand) skulle ha löst referensen och accepterat värdet.
function expandEnvRefs(value, env) {
  return value.replace(
    /\\\$|\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)/g,
    (match, braced, bare) => {
      if (match === "\\$") return "$";
      const name = braced ?? bare;
      return env[name] ?? "";
    },
  );
}

// Precedensordning matchar Next.js egen dotenv-ordning för dev — högst
// prioritet först (process.env > .env.development.local > .env.local >
// .env.development > .env). Vi laddar i OMVÄND ordning så att senare
// spreads vinner, och spreader process.env sist så shell-overrides
// aldrig blir överskrivna. Se
// https://nextjs.org/docs/app/guides/environment-variables#environment-variable-load-order
const fileEnvBase = parseEnvFile(resolve(VIEWSER_ROOT, ".env"));
const fileEnvDev = parseEnvFile(resolve(VIEWSER_ROOT, ".env.development"));
const fileEnvLocal = parseEnvFile(resolve(VIEWSER_ROOT, ".env.local"));
const fileEnvDevLocal = parseEnvFile(resolve(VIEWSER_ROOT, ".env.development.local"));
const mergedEnv = {
  ...fileEnvBase,
  ...fileEnvDev,
  ...fileEnvLocal,
  ...fileEnvDevLocal,
  ...process.env,
};

// Expandera `$VAR` / `${VAR}`-referenser i den hämtade rå-strängen
// (`VIEWSER_PREVIEW_MODE=$PREVIEW_DEFAULT` är giltig dotenv-form). Vi
// kör expansionen mot `mergedEnv` (samma env som validatorn ser) så
// referenser från process.env och dotenv-filer båda är synliga.
const rawMode = expandEnvRefs(mergedEnv.VIEWSER_PREVIEW_MODE ?? DEFAULT_MODE, mergedEnv)
  .trim()
  .toLowerCase();

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
//
// `detached: !IS_WINDOWS` gör child:en till en egen process group leader
// på Unix så vi vid shutdown kan signala HELA trädet (shell + npx + next-
// dev) via `process.kill(-pid, signal)` istället för bara shell-wrappern.
// På Windows hanteras tree-kill via `taskkill /T /F` i `killTree()`
// nedan (detached på Windows skapar bara en ny process group, vilket
// inte räcker — vi behöver det dedikerade tree-kill-anropet).
// Utan detta dör shell:et men `next dev`-processen lever vidare och
// håller port 3000 låst, vilket bryter nästa `npm run dev` — exakt
// det Codex P1-fyndet på parkerade PR #85 beskrev.
const child = spawn("npx", nextArgs, {
  cwd: VIEWSER_ROOT,
  stdio: "inherit",
  shell: true,
  detached: !IS_WINDOWS,
  env: {
    ...process.env,
    VIEWSER_PREVIEW_MODE: mode,
  },
});

// killTree: skicka signal till hela process-trädet under `child`, inte
// bara shell-wrappern. Plattforms-specifik:
//
//   - Windows: `taskkill /pid <child.pid> /T /F` (T = tree, F = force).
//     Vi kör synkront via spawnSync så vi blockerar tills children är
//     döda innan watchdogen process.exit:ar.
//   - Unix: `process.kill(-child.pid, signal)`. Negativ PID = PGID, så
//     hela process-gruppen får signalen (möjligt tack vare
//     `detached: true` ovan).
//
// Båda branscherna fall-tillbakar tyst till `child.kill(signal)` om
// tree-kill failar (t.ex. process redan död), så vi aldrig kastar
// uppåt och hänger event-loopen.
function killTree(signal) {
  if (IS_WINDOWS) {
    try {
      spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
      });
      return;
    } catch {
      // Faller igenom till plain child.kill nedan
    }
  } else {
    try {
      process.kill(-child.pid, signal);
      return;
    } catch {
      // Faller igenom till plain child.kill nedan
    }
  }
  try {
    child.kill(signal);
  } catch {
    // child redan borta — ingen åtgärd
  }
}

// Signal- och shutdown-hantering.
// ---------------------------------------------------------------------------
// Tidigare implementation (`process.kill(process.pid, signal)` i child.exit)
// kunde re-triggra vår egen handler eller hänga utan att returnera ett
// deterministiskt exit-code till skalet. Bugbot på den parkerade PR #85
// flaggade detta som "dispatchern hänger efter Ctrl-C när child:en dog via
// signal". Den här blocket implementerar standard-paternen:
//
//   1. Vi installerar SIGINT- och SIGTERM-handlers EN GÅNG (process.once)
//      så att en andra signal under shutdown inte återkallar samma
//      cleanup-loop.
//   2. Vid signal forwardar vi den till child via `child.kill(signal)` och
//      startar en watchdog-timer (~5s). Hinner child:en inte avsluta sig
//      själv inom det fönstret eskalerar vi till SIGKILL och avslutar
//      parent med det POSIX-vanliga signal-exit-codet (130 för SIGINT,
//      143 för SIGTERM).
//   3. När child:en faktiskt exitar rensar vi watchdogen och översätter
//      exit-orsaken: `signal` (signal-orsakad exit) → `128 + signalnummer`,
//      annars `code ?? 0`. Det är POSIX-konventionen och det signal-shells
//      som bash/PowerShell förväntar sig från child-processer.
//
// Mappningen signalnamn → nummer är hårdkodad eftersom Node inte exponerar
// någon `os.constants.signals[signal]`-helper för exit-code-skydd, och vi
// vill inte importera `os` bara för fyra konstanter.
const SIGNAL_EXIT_CODES = { SIGINT: 130, SIGTERM: 143 };
const SIGNAL_NUMBERS = { SIGHUP: 1, SIGINT: 2, SIGQUIT: 3, SIGTERM: 15, SIGKILL: 9 };
const SHUTDOWN_WATCHDOG_MS = 5000;

let shuttingDown = false;
let watchdogTimer = null;

function clearWatchdog() {
  if (watchdogTimer !== null) {
    clearTimeout(watchdogTimer);
    watchdogTimer = null;
  }
}

function handleParentSignal(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  if (child.exitCode === null && child.signalCode === null) {
    killTree(signal);
  }
  // SIGKILL-watchdog: om child:en inte exitar inom fönstret eskalerar vi.
  // unref:ar timern så den inte själv håller event-loopen vid liv om allt
  // redan stängts ner snyggt. OBS: vi kontrollerar `exitCode === null &&
  // signalCode === null` istället för `!child.killed` här. `child.killed`
  // sätts av Node DIREKT efter att signalen SKICKATS (inte när processen
  // dött), så vid den här tidpunkten är den alltid true och en naiv
  // `!child.killed`-check gör SIGKILL-grenen till dead code — exakt det
  // hängar-scenariot watchdogen finns för att skydda mot (Bugbot/Codex
  // P1 på parkerade PR #85).
  watchdogTimer = setTimeout(() => {
    if (child.exitCode === null && child.signalCode === null) {
      try {
        killTree("SIGKILL");
      } catch {
        // ignorera; child redan borta
      }
    }
    process.exit(SIGNAL_EXIT_CODES[signal] ?? 1);
  }, SHUTDOWN_WATCHDOG_MS);
  if (typeof watchdogTimer.unref === "function") {
    watchdogTimer.unref();
  }
}

process.once("SIGINT", () => handleParentSignal("SIGINT"));
process.once("SIGTERM", () => handleParentSignal("SIGTERM"));

child.on("exit", (code, signal) => {
  clearWatchdog();
  if (signal) {
    const sigNum = SIGNAL_NUMBERS[signal];
    const exitCode = typeof sigNum === "number" ? 128 + sigNum : (SIGNAL_EXIT_CODES[signal] ?? 1);
    process.exit(exitCode);
    return;
  }
  process.exit(code ?? 0);
});

child.on("error", (err) => {
  clearWatchdog();
  process.stderr.write(`Viewser dev-dispatcher kunde inte starta next: ${err.message}\n`);
  process.exit(1);
});
