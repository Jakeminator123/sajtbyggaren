/**
 * sandbox-build-runner — HOSTAD prompt→bygg→preview-loop i EN Vercel Sandbox.
 *
 * Skillnad mot ``vercel-sandbox-runner.ts``: den runnern tar en REDAN-byggd
 * sajt från lokal disk och serverar den. Den HÄR runnern kör hela
 * generation-pipen (Python) plus ``next build`` + ``next start`` INUTI
 * sandboxen, så ingen lokal Python eller lokal disk behövs. Det är vägen som
 * gör att loopen funkar när Viewser körs hostat på Vercel (där ``VERCEL=1``
 * annars degraderar ``/api/prompt`` till ``hostedPythonRuntimeUnavailable``).
 *
 * Arkitektur (anpassad efter serverless-verkligheten):
 *   - ``startLiveBuild`` / ``followupLiveBuild`` skapar/återansluter en sandbox
 *     (deterministiskt namn per ``siteId``), laddar upp ett bygg-skript och
 *     kör det DETACHED. Funktionen returnerar direkt (några sekunder) — det
 *     tunga bygget (~3–5 min kallt) lever vidare i microVM:en oberoende av
 *     serverless-funktionens livslängd.
 *   - Bygg-skriptet skriver fas-status till ``state/status.json`` i sandboxen.
 *   - ``getLiveStatus`` återansluter via ``Sandbox.get({ name })`` och läser
 *     status-filen, så klienten kan polla fram till ``ready`` (eller ``failed``).
 *
 * Sessionen är DB-fri: ``siteId`` är hela nyckeln, sandbox-namnet härleds
 * deterministiskt, och ``Sandbox.get({ name })`` återansluter över
 * serverless-instansbyten. TTL städar sandboxen (Hobby-tak 45 min).
 *
 * Säkerhet: routerna bakom denna runner är AVSIKTLIGT inte localhost-låsta
 * (de ska funka hostat). De gate:as i stället av ``VIEWSER_ENABLE_LIVE`` så
 * funktionen är enkel att stänga av (operatörens uttryckliga "släck ned
 * efteråt"-krav). Hemligheter (OPENAI_API_KEY, GITHUB_TOKEN) skickas som env
 * till det detachade kommandot och hamnar bara i den efemära, isolerade VM:en.
 */

import { resolveSandboxCredentials } from "./vercel-sandbox-runner";

const SANDBOX_RUNTIME = "node24";
const PREVIEW_PORT = 3000;
/** Hobby-tak är 45 min; vi tar max så en demo hinner byggas + bedömas. */
const TTL_MS = 45 * 60_000;
const STATE_DIR = "/vercel/sandbox/state";
const SCRIPT_PATH = "/vercel/sandbox/run-build.sh";

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

export type LivePhase =
  | "pending"
  | "cloning"
  | "installing"
  | "generating"
  | "building"
  | "starting"
  | "ready"
  | "failed"
  | "expired"
  | "unknown";

export interface LiveStartResult {
  status: "building" | "failed";
  siteId?: string;
  /** Publik ``…vercel.run``-URL (känd direkt vid create; svarar först när ready). */
  url?: string;
  error?: string;
  logs?: string[];
}

export interface LiveStatus {
  siteId: string;
  phase: LivePhase;
  detail?: string;
  url?: string;
  error?: string;
  /** Svans av bygg-loggen för felsökning i UI:t. */
  log?: string;
}

/** Deterministiskt sandbox-namn så reconnect funkar utan extern state. */
function sandboxName(siteId: string): string {
  return `sajtbyggaren-live-${siteId}`;
}

/** Härled ett giltigt siteId ur prompten (slug + kort slump för unikhet). */
export function makeSiteId(prompt: string): string {
  const base =
    prompt
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 32)
      .replace(/-+$/g, "") || "sajt";
  const rand = Math.random().toString(36).slice(2, 7);
  const id = `${base}-${rand}`.replace(/-+/g, "-").replace(/^-+|-+$/g, "");
  return id.slice(0, 60);
}

export function isValidSiteId(siteId: string): boolean {
  return (
    !!siteId &&
    siteId.length <= 64 &&
    SITE_ID_PATTERN.test(siteId)
  );
}

/** Dynamisk import så en saknad ``@vercel/sandbox`` degraderar ärligt. */
async function loadSandboxSdk(): Promise<
  typeof import("@vercel/sandbox") | null
> {
  try {
    return await import("@vercel/sandbox");
  } catch {
    return null;
  }
}

/**
 * Env som det detachade bygg-skriptet ärver. Hemligheter läses ur den
 * körande funktionens ``process.env`` (hostat: Vercel-projektets env-vars;
 * lokalt: apps/viewser/.env.local) och hamnar bara i den isolerade VM:en.
 * ``SANDBOX_OPENAI_MODEL`` tvingar en känd modell så vi inte ärver ett
 * ev. ogiltigt ``OPENAI_MODEL`` (root-.env har en placeholder).
 */
function buildEnv(): Record<string, string> {
  return {
    OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
    SANDBOX_OPENAI_MODEL:
      process.env.SANDBOX_OPENAI_MODEL ?? "gpt-4o-mini",
    GITHUB_TOKEN: process.env.GITHUB_TOKEN ?? "",
    SAJTBYGGAREN_BUILD_REF: process.env.SAJTBYGGAREN_BUILD_REF ?? "jakob-be",
  };
}

/**
 * Bygg-skriptet som körs detached i sandboxen. Skrivet som en array av
 * NORMALA JS-strängar (inte template literals) så shell-``$``/backticks blir
 * literala — bara inbäddade ``"`` escapas. Skriptet är idempotent nog för
 * både init (klona + installera + generera + bygg + servera) och followup
 * (generera ny version + bygg + starta om next på samma port/URL).
 */
function buildScriptContent(): string {
  return [
    "#!/usr/bin/env bash",
    "set -uo pipefail",
    "",
    'MODE="${1:-init}"',
    'PROMPT_B64="${2:-}"',
    'SITEID="${3:-site}"',
    "",
    "STATE=/vercel/sandbox/state",
    "REPO=/vercel/sandbox/repo",
    "OUT=/vercel/sandbox/out/.generated",
    "VENV=/vercel/sandbox/venv",
    'PY="$VENV/bin/python"',
    'REF="${SAJTBYGGAREN_BUILD_REF:-jakob-be}"',
    "",
    'mkdir -p "$STATE"',
    ': > "$STATE/build.log"',
    "",
    'log() { echo "[$(date +%H:%M:%S)] $*" >> "$STATE/build.log"; }',
    "status() {",
    "  printf '{\"phase\":\"%s\",\"detail\":\"%s\",\"ts\":%s}\\n' \"$1\" \"$2\" \"$(date +%s)\" > \"$STATE/status.json\"",
    '  log "phase=$1 $2"',
    "}",
    "fail() {",
    "  printf '{\"phase\":\"failed\",\"detail\":\"%s\",\"ts\":%s}\\n' \"$1\" \"$(date +%s)\" > \"$STATE/status.json\"",
    '  log "FAILED: $1"',
    "  exit 1",
    "}",
    "",
    'PROMPT="$(printf %s "$PROMPT_B64" | base64 -d)"',
    "",
    'export SAJTBYGGAREN_GENERATED_DIR="$OUT"',
    "export SAJTBYGGAREN_EVALS_DIR=/vercel/sandbox/out/.evals",
    'export OPENAI_MODEL="${SANDBOX_OPENAI_MODEL:-${OPENAI_MODEL:-gpt-4o-mini}}"',
    "",
    "ensure_base() {",
    '  command -v git >/dev/null 2>&1 || sudo dnf install -y -q git >> "$STATE/build.log" 2>&1',
    '  command -v curl >/dev/null 2>&1 || sudo dnf install -y -q curl >> "$STATE/build.log" 2>&1',
    "}",
    "",
    "# AL2023:s system-python3 är 3.9 men repo-koden kräver 3.11+",
    "# (``from datetime import UTC``). Installera 3.12 (fallback 3.11) och kör",
    "# pipen i en venv så vi slipper PEP 668 / gammal pip helt.",
    "ensure_python_env() {",
    '  [ -x "$PY" ] && return 0',
    "  if ! command -v python3.12 >/dev/null 2>&1 && ! command -v python3.11 >/dev/null 2>&1; then",
    '    sudo dnf install -y -q python3.12 >> "$STATE/build.log" 2>&1 || true',
    '    command -v python3.12 >/dev/null 2>&1 || sudo dnf install -y -q python3.11 >> "$STATE/build.log" 2>&1 || true',
    "  fi",
    '  PYBIN=""',
    '  for c in python3.12 python3.11; do command -v "$c" >/dev/null 2>&1 && { PYBIN="$c"; break; }; done',
    '  [ -n "$PYBIN" ] || fail "kunde inte installera python3.11/3.12"',
    '  "$PYBIN" -m venv "$VENV" >> "$STATE/build.log" 2>&1 || fail "kunde inte skapa venv"',
    '  "$PY" -m pip install --quiet --disable-pip-version-check --upgrade pip >> "$STATE/build.log" 2>&1 || true',
    '  "$PY" -m pip install --quiet --disable-pip-version-check openai pydantic jsonschema pillow requests beautifulsoup4 >> "$STATE/build.log" 2>&1 || fail "pip install misslyckades"',
    "}",
    "",
    'if [ "$MODE" = "init" ]; then',
    '  status cloning "Hamtar byggmotorn"',
    "  ensure_base",
    '  if [ -n "${GITHUB_TOKEN:-}" ]; then',
    "    git config --global credential.helper store",
    "    printf 'https://x-access-token:%s@github.com\\n' \"$GITHUB_TOKEN\" > \"$HOME/.git-credentials\"",
    "  fi",
    '  rm -rf "$REPO"',
    '  git clone --depth 1 --branch "$REF" https://github.com/Jakeminator123/sajtbyggaren.git "$REPO" >> "$STATE/build.log" 2>&1 || fail "git clone misslyckades"',
    '  status installing "Installerar beroenden"',
    "  ensure_python_env",
    "fi",
    "",
    'cd "$REPO" || fail "repo saknas - kor init forst"',
    "ensure_python_env",
    "",
    'if [ "$MODE" = "init" ]; then',
    '  status generating "Skapar din sajt"',
    '  "$PY" scripts/prompt_to_project_input.py --site-id "$SITEID" -- "$PROMPT" > "$STATE/p1.out" 2>> "$STATE/build.log" || fail "prompt-steget misslyckades"',
    "else",
    '  status generating "Uppdaterar din sajt"',
    '  "$PY" scripts/prompt_to_project_input.py --followup-site-id "$SITEID" -- "$PROMPT" > "$STATE/p1.out" 2>> "$STATE/build.log" || fail "uppdateringen misslyckades"',
    "fi",
    "",
    "DOSSIER=\"$(grep '^dossierPath:' \"$STATE/p1.out\" | head -n1 | sed 's/^dossierPath:[[:space:]]*//')\"",
    '[ -n "$DOSSIER" ] || fail "hittade ingen dossierPath"',
    "",
    'status building "Bygger sajten"',
    '"$PY" scripts/build_site.py --dossier "$DOSSIER" > "$STATE/p2.out" 2>> "$STATE/build.log" || fail "bygget misslyckades"',
    "",
    "TARGET=\"$(grep '^Generated site at ' \"$STATE/p2.out\" | head -n1 | sed 's/^Generated site at //')\"",
    '[ -n "$TARGET" ] && [ -d "$TARGET" ] || fail "hittade ingen byggd sajt"',
    'echo "$TARGET" > "$STATE/target.txt"',
    "",
    'status starting "Startar forhandsvisning"',
    '  pkill -f "next start" >/dev/null 2>&1 || true',
    "  sleep 1",
    'cd "$TARGET" || fail "byggkatalogen saknas"',
    'nohup node_modules/.bin/next start -p 3000 >> "$STATE/next.log" 2>&1 &',
    "",
    "for i in $(seq 1 90); do",
    "  if curl -fsS http://localhost:3000 >/dev/null 2>&1; then",
    '    status ready "Klar"',
    "    exit 0",
    "  fi",
    "  sleep 2",
    "done",
    'fail "next start svarade inte i tid"',
    "",
  ].join("\n");
}

/**
 * Starta en helt ny live-build. Skapar en sandbox, laddar upp bygg-skriptet
 * och kör det detached i ``init``-läge. Returnerar direkt med ``siteId`` +
 * den publika URL:en (som svarar först när bygget når ``ready``).
 */
export async function startLiveBuild(prompt: string): Promise<LiveStartResult> {
  const trimmed = prompt.trim();
  if (!trimmed) return { status: "failed", error: "Prompt får inte vara tom." };

  const credentials = resolveSandboxCredentials();
  if (!credentials) {
    return {
      status: "failed",
      error:
        "Vercel-credentials saknas (VERCEL_OIDC_TOKEN eller VERCEL_TOKEN + " +
        "VERCEL_TEAM_ID + VERCEL_PROJECT_ID). Hostat sätts OIDC automatiskt.",
    };
  }

  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return { status: "failed", error: "@vercel/sandbox är inte installerad." };
  }

  const siteId = makeSiteId(trimmed);
  const logs: string[] = [];

  try {
    const sandbox = await sdk.Sandbox.create({
      ...credentials,
      name: sandboxName(siteId),
      runtime: SANDBOX_RUNTIME,
      ports: [PREVIEW_PORT],
      timeout: TTL_MS,
      persistent: false,
    });
    logs.push(`Sandbox skapad (${sandbox.name}).`);

    await sandbox.writeFiles([
      { path: "run-build.sh", content: Buffer.from(buildScriptContent(), "utf-8") },
    ]);

    await runDetachedBuild(sandbox, "init", trimmed, siteId);

    return {
      status: "building",
      siteId,
      url: sandbox.domain(PREVIEW_PORT),
      logs,
    };
  } catch (error) {
    return { status: "failed", siteId, error: messageFromError(error), logs };
  }
}

/**
 * Kör en followup mot en levande session: återanslut, generera ny version
 * och bygg om. Samma sandbox/URL återanvänds (next startas om på port 3000).
 */
export async function followupLiveBuild(
  siteId: string,
  prompt: string,
): Promise<LiveStartResult> {
  const trimmed = prompt.trim();
  if (!isValidSiteId(siteId)) {
    return { status: "failed", error: "Ogiltigt siteId." };
  }
  if (!trimmed) return { status: "failed", error: "Prompt får inte vara tom." };

  const credentials = resolveSandboxCredentials();
  if (!credentials) {
    return { status: "failed", error: "Vercel-credentials saknas." };
  }
  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return { status: "failed", error: "@vercel/sandbox är inte installerad." };
  }

  try {
    const sandbox = await sdk.Sandbox.get({
      ...credentials,
      name: sandboxName(siteId),
    });
    // Skriptet kan ha fallit bort om VM:en bytts ut; skriv alltid om det.
    await sandbox.writeFiles([
      { path: "run-build.sh", content: Buffer.from(buildScriptContent(), "utf-8") },
    ]);
    await runDetachedBuild(sandbox, "followup", trimmed, siteId);
    return { status: "building", siteId, url: sandbox.domain(PREVIEW_PORT) };
  } catch (error) {
    return {
      status: "failed",
      siteId,
      error:
        "Sessionen kunde inte återupptas (sandboxen kan ha gått ut). " +
        `Starta en ny sajt. Detalj: ${messageFromError(error)}`,
    };
  }
}

/** Läs aktuell fas-status för en session. */
export async function getLiveStatus(siteId: string): Promise<LiveStatus> {
  if (!isValidSiteId(siteId)) {
    return { siteId, phase: "failed", error: "Ogiltigt siteId." };
  }
  const credentials = resolveSandboxCredentials();
  if (!credentials) {
    return { siteId, phase: "failed", error: "Vercel-credentials saknas." };
  }
  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return { siteId, phase: "failed", error: "@vercel/sandbox saknas." };
  }

  let sandbox: Awaited<ReturnType<typeof sdk.Sandbox.get>>;
  try {
    sandbox = await sdk.Sandbox.get({ ...credentials, name: sandboxName(siteId) });
  } catch {
    return {
      siteId,
      phase: "expired",
      error: "Sessionen finns inte längre (sandboxen har gått ut).",
    };
  }

  const statusRaw = await readSandboxFile(sandbox, `${STATE_DIR}/status.json`);
  const parsed = safeParseStatus(statusRaw);
  const phase: LivePhase = parsed?.phase ?? "pending";
  const log = await readSandboxFile(
    sandbox,
    "",
    `tail -n 40 ${STATE_DIR}/build.log 2>/dev/null || true`,
  );

  return {
    siteId,
    phase,
    detail: parsed?.detail,
    url: phase === "ready" ? sandbox.domain(PREVIEW_PORT) : undefined,
    error: phase === "failed" ? parsed?.detail : undefined,
    log: log?.trim() || undefined,
  };
}

interface RunnableSandbox {
  runCommand: (...args: unknown[]) => Promise<{ stdout: () => Promise<string> }>;
  writeFiles: (files: { path: string; content: Buffer }[]) => Promise<unknown>;
  domain: (port: number) => string;
  name: string;
}

/** Kör bygg-skriptet detached med hemligheter i env (bara i VM:en). */
async function runDetachedBuild(
  sandbox: unknown,
  mode: "init" | "followup",
  prompt: string,
  siteId: string,
): Promise<void> {
  const promptB64 = Buffer.from(prompt, "utf-8").toString("base64");
  const s = sandbox as {
    runCommand: (opts: Record<string, unknown>) => Promise<unknown>;
  };
  await s.runCommand({
    cmd: "bash",
    args: [SCRIPT_PATH, mode, promptB64, siteId],
    env: buildEnv(),
    detached: true,
  });
}

/**
 * Läs en fil ur sandboxen via ``cat`` (eller ett valfritt ``shellOverride``-
 * kommando). Icke-kastande: returnerar ``null`` om kommandot failar.
 */
async function readSandboxFile(
  sandbox: unknown,
  filePath: string,
  shellOverride?: string,
): Promise<string | null> {
  const s = sandbox as RunnableSandbox;
  try {
    const result = shellOverride
      ? await s.runCommand("sh", ["-c", shellOverride])
      : await s.runCommand("cat", [filePath]);
    return await result.stdout();
  } catch {
    return null;
  }
}

function safeParseStatus(
  raw: string | null,
): { phase: LivePhase; detail?: string } | null {
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw.trim());
    if (obj && typeof obj.phase === "string") {
      return { phase: obj.phase as LivePhase, detail: obj.detail };
    }
  } catch {
    // ofullständig/halvskriven fil — behandla som pending
  }
  return null;
}

function messageFromError(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Okänt fel i sandbox-build-runnern.";
}
