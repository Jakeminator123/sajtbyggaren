/**
 * hosted-build-runner — hostad byggorkestrering i Vercel Sandbox (P2, G1-A).
 *
 * Detta är P2 i migrationsplanen (docs/vercel-sandbox-migration/): en
 * användarsajt ska kunna BYGGAS hostat på Vercel utan lokal Python. Vald väg
 * är G1 alternativ A — minst omskrivning: den befintliga deterministiska
 * Python-pipen (scripts/prompt_to_project_input.py + scripts/build_site.py +
 * packages/generation/) körs OFÖRÄNDRAD i en Vercel Sandbox (node24 har
 * python3) i stället för på operatörens maskin.
 *
 * Arkitektur (blob = artefakter, KV = pekare/status, allt leverantörsneutralt):
 *
 *   1. Build-kontexten (scripts/, packages/, governance/, data/starters/,
 *      requirements.txt) ligger som tar.gz i blob under
 *      "build-context/current.tar.gz" — uppladdad av operatörs-CLI:t
 *      apps/viewser/scripts/upload-build-context-to-blob.mjs. URL:en hämtas
 *      från KV ("viewser:build-context:url") eller env VIEWSER_BUILD_CONTEXT_URL.
 *   2. ``startHostedBuild`` skapar en sandbox med source { type: "tarball" }
 *      (samma auth-mönster som vercel-sandbox-runner.ts: OIDC vinner, annars
 *      token-trion), skriver ett bash-orkestrerings-skript via writeFiles och
 *      startar det DETACHED — HTTP-requesten väntar ALDRIG in hela bygget.
 *   3. Skriptet i sandboxen: pip install -> prompt_to_project_input.py ->
 *      build_site.py -> laddar upp den aktiva immutable builden fil-för-fil
 *      till blob under ``generated/<siteId>/<relPath>`` — EXAKT det layout
 *      lib/generated-blob-source.ts redan listar/läser, så den befintliga
 *      hostade sandbox-previewen fungerar direkt på resultatet.
 *   4. Status efter varje fas POST:as till Upstash REST-API:t (rått Redis-SET,
 *      samma kommandoform som lib/kv-store/upstash-redis.ts) under nyckeln
 *      ``viewser:hosted-run:<runId>`` (TTL 24 h) så UI:t kan polla via
 *      GET /api/hosted-build/<runId>. Efter lyckad upload sätts även
 *      ``viewser:site:<siteId>:current`` = { buildId, blobPrefix, updatedAt }
 *      — den hostade motsvarigheten till current.json-pekaren på disk.
 *
 * Varför KV-adaptern (lib/kv-store) för all run-status på TS-sidan:
 * leverantörsneutralitet — koden pratar bara med KvStore-kontraktet; lokalt
 * utan Redis-env blir det memory-drivern (då ser bara samma process statusen,
 * och sandboxens egna status-POST:ar hoppar ärligt över sig själva när
 * KV_REST_URL saknas). Hostat injicerar Marketplace-integrationen KV_REST_API_*
 * och allt fungerar utan kodändring.
 *
 * Ingår INTE här (hanteras separat): auth/tenant (G4), kvoter/kostnadsstyrning
 * (G7), persistens av run-historik för följdprompter hostat.
 */

import { randomUUID } from "node:crypto";

import { getKvStore, kvSetJson } from "./kv-store";
import { upstashRestToken, upstashRestUrl } from "./kv-store/upstash-redis";
import {
  ensureFreshOidcTokenBeforeCreate,
  resolveCredentials,
} from "./vercel-sandbox-runner";

export interface HostedBuildRequest {
  /** siteId för sajten som ska byggas (samma mönster som /api/preview). */
  siteId: string;
  /** Operatörens/användarens prompt. */
  prompt: string;
  /** True för följdprompt mot en befintlig sajt (se begränsning i JSDoc ovan). */
  followup?: boolean;
}

/** Faserna som status-nyckeln i KV rör sig genom. "queued" sätts av runnern;
 * resten av orkestrerings-skriptet i sandboxen. */
export type HostedBuildPhase =
  | "queued"
  | "installing"
  | "project-input"
  | "building"
  | "uploading"
  | "done"
  | "failed";

/** JSON-formen under ``viewser:hosted-run:<runId>`` (TTL 24 h). */
export interface HostedBuildRunStatus {
  runId: string;
  siteId: string;
  phase: HostedBuildPhase;
  startedAt: string;
  updatedAt: string;
  error?: string;
  buildId?: string;
  blobPrefix?: string;
}

const HOSTED_RUN_KEY_PREFIX = "viewser:hosted-run:";
const BUILD_CONTEXT_URL_KEY = "viewser:build-context:url";
const BUILD_CONTEXT_URL_ENV = "VIEWSER_BUILD_CONTEXT_URL";

const SANDBOX_RUNTIME = "node24";
/** Bygg-TTL: pip + npm install + next build ryms gott inom 15 min varma dagar;
 * sandboxen auto-termineras vid TTL så ett hängt bygge aldrig läcker kostnad. */
const HOSTED_BUILD_TTL_MS = 15 * 60_000;
const RUN_STATUS_TTL_SECONDS = 86_400;

/** Samma siteId-regel som vercel-sandbox-runner.ts / /api/preview/[siteId]. */
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/** KV-nyckel för en hostad runs status. Exporterad så status-routen läser
 * exakt samma nyckel. */
export function hostedRunKey(runId: string): string {
  return `${HOSTED_RUN_KEY_PREFIX}${runId}`;
}

/** Dynamisk import så en saknad ``@vercel/sandbox`` degraderar ärligt
 * (samma mönster som vercel-sandbox-runner.ts). */
async function loadSandboxSdk(): Promise<
  typeof import("@vercel/sandbox") | null
> {
  try {
    return await import("@vercel/sandbox");
  } catch {
    return null;
  }
}

function slug(value: string): string {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "site"
  );
}

/**
 * Orkestrerings-skriptet som körs DETACHED i bygg-sandboxen. Helt statiskt —
 * all per-körning-data (runId, siteId, prompt, tokens) kommer via env från
 * ``runCommand`` så ingen prompt-text någonsin interpoleras in i bash-kod.
 *
 * Viktiga kontrakt skriptet upprätthåller:
 *   - Status-JSON ({ runId, siteId, phase, startedAt, updatedAt, error?,
 *     buildId?, blobPrefix? }) SET:as i KV med TTL 86400 efter varje fas.
 *   - Blob-upload sker fil-för-fil under ``generated/<siteId>/<relPath>``
 *     (ingen tarball: lib/generated-blob-source.ts listar per-fil-blobbar),
 *     med samma skip-kataloger och .env-skydd som snapshot-site-to-blob.mjs.
 *   - Vid fel: phase "failed" med feltext, exit != 0.
 */
function buildOrchestrationScript(): string {
  const script = `#!/usr/bin/env bash
# hosted-build.sh — genererad av apps/viewser/lib/hosted-build-runner.ts (P2).
# Kor Python-genereringspipen i sandboxen och publicerar resultatet till blob.
set -u
set -o pipefail

GENERATED_DIR="/vercel/sandbox/.generated-output"
BLOB_API="https://blob.vercel-storage.com"
export STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# post_status <phase> <error> <buildId> — bygger status-JSON sakert via python3
# (enbart stdlib, funkar fore pip install) och POST:ar Redis-kommandot
# ["SET", "viewser:hosted-run:<runId>", "<json>", "EX", "86400"] till Upstash
# REST-API:t. Tyst no-op nar KV-env saknas; statusfel faller aldrig bygget.
post_status() {
  local payload
  payload=$(PHASE="$1" ERROR_TEXT="$2" BUILD_ID="$3" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
doc = {
    "runId": os.environ["RUN_ID"],
    "siteId": os.environ["SITE_ID"],
    "phase": os.environ["PHASE"],
    "startedAt": os.environ.get("STARTED_AT") or now,
    "updatedAt": now,
}
if os.environ.get("ERROR_TEXT"):
    doc["error"] = os.environ["ERROR_TEXT"][:2000]
if os.environ.get("BUILD_ID"):
    doc["buildId"] = os.environ["BUILD_ID"]
    doc["blobPrefix"] = "generated/" + os.environ["SITE_ID"] + "/"
key = "viewser:hosted-run:" + os.environ["RUN_ID"]
print(json.dumps(["SET", key, json.dumps(doc, ensure_ascii=False), "EX", "86400"]))
PY
)
  if [ -n "$KV_REST_URL" ] && [ -n "$KV_REST_TOKEN" ]; then
    curl -s -X POST "$KV_REST_URL" \\
      -H "Authorization: Bearer $KV_REST_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d "$payload" >/dev/null || true
  fi
}

fail() {
  post_status "failed" "$1" ""
  echo "hosted-build: FAILED: $1" >&2
  exit 1
}

# Fas 1: Python-beroenden. ensurepip ar best-effort for minimala images.
post_status "installing" "" ""
python3 -m pip --version >/dev/null 2>&1 \\
  || python3 -m ensurepip --upgrade >/dev/null 2>&1 \\
  || true
python3 -m pip install --quiet -r requirements.txt \\
  || python3 -m pip install --quiet --user -r requirements.txt \\
  || fail "pip install -r requirements.txt misslyckades i sandboxen."

# Fas 2: prompt -> Project Input. Foljdlage kraver tidigare run-state
# (data/prompt-inputs + data/runs) som annu inte persisteras hostat — det
# failar arligt har tills den persistensen landar (separat spar).
post_status "project-input" "" ""
if [ "$FOLLOWUP_MODE" = "1" ]; then
  PI_OUT=$(python3 scripts/prompt_to_project_input.py "$PROMPT_TEXT" --followup-site-id "$SITE_ID" 2>&1) \\
    || fail "prompt_to_project_input (followup) misslyckades: $(printf '%s' "$PI_OUT" | tail -c 600)"
else
  PI_OUT=$(python3 scripts/prompt_to_project_input.py "$PROMPT_TEXT" --site-id "$SITE_ID" 2>&1) \\
    || fail "prompt_to_project_input misslyckades: $(printf '%s' "$PI_OUT" | tail -c 600)"
fi
DOSSIER_PATH=$(printf '%s\\n' "$PI_OUT" | sed -n 's/^dossierPath: //p' | head -n 1)
if [ -z "$DOSSIER_PATH" ]; then
  fail "dossierPath saknas i prompt_to_project_input-output."
fi

# Fas 3: deterministiska byggaren (npm install + next build kors dar inne av
# build_site.py sjalv — Quality Gate far riktiga build-status-signaler).
post_status "building" "" ""
BUILD_OUT=$(python3 scripts/build_site.py --dossier "$DOSSIER_PATH" --generated-dir "$GENERATED_DIR" 2>&1) \\
  || fail "build_site.py misslyckades: $(printf '%s' "$BUILD_OUT" | tail -c 600)"

# Aktiv immutable build via current.json — samma pekar-kontrakt som lokalt.
ACTIVE_BUILD_ID=$(GENERATED_DIR="$GENERATED_DIR" python3 - <<'PY'
import json, os
pointer = os.path.join(os.environ["GENERATED_DIR"], os.environ["SITE_ID"], "current.json")
try:
    with open(pointer, encoding="utf-8") as fh:
        print(json.load(fh).get("activeBuildId") or "")
except (OSError, ValueError):
    print("")
PY
)
if [ -z "$ACTIVE_BUILD_ID" ]; then
  fail "current.json saknar activeBuildId — bygget promotades aldrig (status failed/skipped)."
fi

# Fas 4: publicera builden till blob, fil for fil, under
# generated/<siteId>/<relPath> — EXAKT layoutet lib/generated-blob-source.ts
# listar/laser (darfor ingen tarball har). Samma skip-kataloger och
# .env-skydd som scripts/snapshot-site-to-blob.mjs.
post_status "uploading" "" "$ACTIVE_BUILD_ID"
BUILD_DIR="$GENERATED_DIR/$SITE_ID/builds/$ACTIVE_BUILD_ID"
cd "$BUILD_DIR" || fail "Build-katalogen saknas: $BUILD_DIR"

find . \\( -name node_modules -o -name .next -o -name .git -o -name .turbo -o -name .vercel -o -name .cache -o -name out \\) -prune -o -type f -print | sed 's|^\\./||' | {
  upload_ok=1
  while IFS= read -r rel; do
    base=$(basename "$rel")
    case "$base" in
      .env.example) ;;
      .env*) continue ;;
    esac
    curl -sf -X PUT "$BLOB_API/generated/$SITE_ID/$rel" \\
      -H "Authorization: Bearer $BLOB_READ_WRITE_TOKEN" \\
      -H "x-api-version: 7" \\
      -H "x-add-random-suffix: 0" \\
      --data-binary "@$rel" >/dev/null || { upload_ok=0; break; }
  done
  [ "$upload_ok" = "1" ]
} || fail "Blob-upload misslyckades."

# Hostad current.json-motsvarighet: viewser:site:<siteId>:current (ingen TTL —
# pekaren ar durabel tills nasta lyckade bygge skriver over den).
CURRENT_PAYLOAD=$(BUILD_ID="$ACTIVE_BUILD_ID" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
doc = {
    "buildId": os.environ["BUILD_ID"],
    "blobPrefix": "generated/" + os.environ["SITE_ID"] + "/",
    "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
key = "viewser:site:" + os.environ["SITE_ID"] + ":current"
print(json.dumps(["SET", key, json.dumps(doc, ensure_ascii=False)]))
PY
)
if [ -n "$KV_REST_URL" ] && [ -n "$KV_REST_TOKEN" ]; then
  curl -s -X POST "$KV_REST_URL" \\
    -H "Authorization: Bearer $KV_REST_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d "$CURRENT_PAYLOAD" >/dev/null || true
fi

post_status "done" "" "$ACTIVE_BUILD_ID"
echo "hosted-build: klar (buildId $ACTIVE_BUILD_ID)."
`;
  // Garantera LF: bash tal inte CR (en CRLF-normaliserad kalla skulle annars
  // ge "\r: command not found" i sandboxen).
  return script.split("\r\n").join("\n");
}

/**
 * Starta ett hostat bygge. Skriver "queued"-status till KV, skapar en
 * bygg-sandbox från build-kontext-tarballen och startar orkestreringen
 * DETACHED — returnerar direkt med ``runId`` så HTTP-lagret aldrig väntar in
 * bygget. Vidare status pollas via KV-nyckeln ``viewser:hosted-run:<runId>``.
 *
 * Kastar ``Error`` (efter att ha skrivit phase "failed" till KV) vid
 * pre-flight-fel: ogiltig request, saknad blob-token, saknad Vercel-auth,
 * saknad build-kontext-URL eller misslyckad Sandbox.create.
 */
export async function startHostedBuild(
  req: HostedBuildRequest,
): Promise<{ runId: string }> {
  if (!req.siteId || !SITE_ID_PATTERN.test(req.siteId) || req.siteId.length > 64) {
    throw new Error(
      "Ogiltigt siteId: får bara innehålla a-z, 0-9 och bindestreck (max 64 tecken).",
    );
  }
  if (!req.prompt || !req.prompt.trim()) {
    throw new Error("Prompten är tom — inget att bygga.");
  }

  const runId = randomUUID();
  const store = getKvStore();
  const startedAt = new Date().toISOString();

  const writeStatus = async (
    phase: HostedBuildPhase,
    error?: string,
  ): Promise<void> => {
    const status: HostedBuildRunStatus = {
      runId,
      siteId: req.siteId,
      phase,
      startedAt,
      updatedAt: new Date().toISOString(),
      ...(error ? { error } : {}),
    };
    await kvSetJson(store, hostedRunKey(runId), status, {
      ttlSeconds: RUN_STATUS_TTL_SECONDS,
    });
  };

  // Ärlig fail-hjälpare: statusen i KV uppdateras FÖRST så en pollande klient
  // ser varför, sedan kastas felet till callern.
  const failRun = async (message: string): Promise<never> => {
    await writeStatus("failed", message);
    throw new Error(message);
  };

  await writeStatus("queued");

  const blobToken = process.env.BLOB_READ_WRITE_TOKEN?.trim();
  if (!blobToken) {
    return failRun(
      "BLOB_READ_WRITE_TOKEN saknas — bygg-outputen kan inte publiceras till blob.",
    );
  }

  const credentials = resolveCredentials();
  if (!credentials) {
    return failRun(
      "Vercel-credentials saknas. Sätt VERCEL_OIDC_TOKEN (via `vercel env pull`) " +
        "eller trion VERCEL_TOKEN + VERCEL_TEAM_ID + VERCEL_PROJECT_ID.",
    );
  }

  const contextUrl =
    (await store.get(BUILD_CONTEXT_URL_KEY))?.trim().replace(/^"|"$/g, "") ||
    process.env[BUILD_CONTEXT_URL_ENV]?.trim() ||
    null;
  if (!contextUrl) {
    return failRun(
      "Build-kontext-URL saknas. Kör operatörs-CLI:t " +
        "apps/viewser/scripts/upload-build-context-to-blob.mjs (skriver KV-nyckeln " +
        `"${BUILD_CONTEXT_URL_KEY}") eller sätt env ${BUILD_CONTEXT_URL_ENV}.`,
    );
  }

  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return failRun(
      "@vercel/sandbox är inte installerad i apps/viewser. Kör `cd apps/viewser && npm install`.",
    );
  }

  // B1a-guarden från preview-runnern återanvänds: håll OIDC-token färsk före
  // Sandbox.create (no-op hostat där plattformen roterar token automatiskt).
  if (credentials.mode === "oidc") {
    const logs: string[] = [];
    const oidcGuard = ensureFreshOidcTokenBeforeCreate(logs);
    if (!oidcGuard.ok) {
      return failRun(oidcGuard.error);
    }
  }

  const sandboxEnv: Record<string, string> = {
    RUN_ID: runId,
    SITE_ID: req.siteId,
    PROMPT_TEXT: req.prompt,
    FOLLOWUP_MODE: req.followup ? "1" : "0",
    BLOB_READ_WRITE_TOKEN: blobToken,
    // Samma env-upplösning som kv-store/upstash-redis.ts; tomma strängar når
    // skriptet, som då hoppar över status-POST:arna ärligt (set -u-säkert).
    KV_REST_URL: upstashRestUrl() ?? "",
    KV_REST_TOKEN: upstashRestToken() ?? "",
    OPENAI_API_KEY: process.env.OPENAI_API_KEY?.trim() ?? "",
  };
  const openaiModel = process.env.OPENAI_MODEL?.trim();
  if (openaiModel) sandboxEnv.OPENAI_MODEL = openaiModel;

  let sandbox: Awaited<ReturnType<typeof sdk.Sandbox.create>> | null = null;
  try {
    sandbox = await sdk.Sandbox.create({
      ...credentials.create,
      name: `sajtbyggaren-hosted-build-${slug(req.siteId)}-${Date.now()}`,
      runtime: SANDBOX_RUNTIME,
      timeout: HOSTED_BUILD_TTL_MS,
      // Build-kontexten extraheras till /vercel/sandbox (scripts/, packages/,
      // governance/, data/starters/, requirements.txt i roten).
      source: { type: "tarball", url: contextUrl },
    });

    await sandbox.writeFiles([
      {
        path: "hosted-build.sh",
        content: Buffer.from(buildOrchestrationScript(), "utf-8"),
      },
    ]);

    // DETACHED: requesten väntar inte in bygget. Sandboxens TTL är taket;
    // skriptet rapporterar själv done/failed till KV.
    await sandbox.runCommand({
      cmd: "bash",
      args: ["hosted-build.sh"],
      env: sandboxEnv,
      detached: true,
    });
  } catch (error) {
    if (sandbox) {
      try {
        await sandbox.stop();
      } catch {
        // Best-effort cleanup — ursprungsfelet får aldrig maskeras.
      }
    }
    const message =
      error instanceof Error ? error.message : "Okänt fel vid sandbox-start.";
    return failRun(`Hostat bygge kunde inte startas: ${message}`);
  }

  return { runId };
}
