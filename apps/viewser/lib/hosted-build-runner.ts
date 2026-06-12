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
 * Run-state för följdprompter (B194): lokalt härleder
 * prompt_to_project_input.py föregående version ur
 * ``data/prompt-inputs/<siteId>.{project-input,meta}.json`` — filer som aldrig
 * fanns i en färsk sandbox, så hostade följdprompter failade ärligt. Nu
 * persisterar varje lyckat hostat bygge det färska PI/meta-paret till blob
 * under ``run-state/<siteId>/v<N>/`` (versions-scopat så ett halvlyckat
 * upload-par aldrig kan refereras — pekaren flyttas först när BÅDA filerna
 * är uppe) och sätter den durabla KV-pekaren
 * ``viewser:site:<siteId>:run-state``. Vid followup läser ``startHostedBuild``
 * pekaren pre-flight (saknas den failar den ärligt med byggråd) och sandboxen
 * curlar ner paret till data/prompt-inputs/ innan followup-kommandot körs.
 *
 * Ingår INTE här (hanteras separat): auth/tenant (G4), kvoter/kostnadsstyrning
 * (G7), --base-run-id-följdprompter hostat (kräver versionerade snapshots,
 * run-state-lagret ovan är förberett för det via v<N>-layouten).
 */

import { randomUUID } from "node:crypto";

import { isHostedVercelRuntime } from "./hosted-python-runtime";
import { getKvStore, kvGetJson, kvSetJson } from "./kv-store";
import { upstashRestToken, upstashRestUrl } from "./kv-store/upstash-redis";
import { sanitizedAssetSetIntent, sanitizedMarkedSections } from "./prompt-runner";
import {
  ensureFreshOidcTokenBeforeCreate,
  resolveCredentials,
} from "./vercel-sandbox-runner";
import { stopSandboxSessionForSite } from "./vercel-sandbox-sessions";

export interface HostedBuildRequest {
  /** siteId för sajten som ska byggas (samma mönster som /api/preview). */
  siteId: string;
  /** Operatörens/användarens prompt. */
  prompt: string;
  /** True för följdprompt mot en befintlig sajt (se begränsning i JSDoc ovan). */
  followup?: boolean;
  /**
   * Strukturerat verktygs-intent (task A) — samma kontrakt som
   * ``PromptHelperOptions.toolIntent`` lokalt. Bara ``asset_set``
   * forwardas, sanerat genom SAMMA ``sanitizedAssetSetIntent`` som den
   * lokala spawn-vägen, och bara i följdläge. Når sandboxen som env
   * ``TOOL_INTENT_JSON`` (aldrig interpolerad i bash-kod) och blir
   * ``--tool-intent`` till prompt_to_project_input.py. Hostat finns
   * ingen lokal manifest-fallback, men UI:t skickar hela AssetRef-
   * metadatan i params så Python-sidan inte behöver disken.
   */
  toolIntent?: { tool: string; params: Record<string, unknown> };
  /**
   * Commit 3 (request-paritet): iterera från en specifik historisk run i
   * stället för senaste. Redan Zod-validerad i /api/prompt (RUN_ID_PATTERN,
   * followup-only). Re-valideras defense-in-depth här (env quotar inte) och
   * når sandboxen som ``BASE_RUN_ID`` → ``--base-run-id`` på BÅDE OpenClaw
   * apply-anropet och legacy-PI-anropet. v1-begränsning: bara senaste
   * versionens artefakter hydreras (B199), så en historisk baseRunId vars
   * version ≠ senaste kör mot senaste artefakter.
   */
  baseRunId?: string;
  /**
   * Commit 3 (request-paritet): operatörens preview-markeringar (ADR 0046).
   * Redan Zod-validerad i /api/prompt (max 5, slug-grammatik, followup-only).
   * Saneras med SAMMA ``sanitizedMarkedSections`` som den lokala spawn-vägen
   * och når sandboxen som ``MARKED_SECTIONS_JSON`` → ``--marked-sections`` på
   * legacy-PI-anropet (run_openclaw_followup.py har ingen --marked-sections-
   * flagga, exakt som lokala apply-vägen inte heller forwardar den).
   */
  markedSections?: { routeId: string; sectionId: string; note?: string }[];
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

/**
 * Commit 3 (response-paritet): det rika followup-resultat sandboxen producerar
 * och POST:ar in i KV-statusdoken (TS-runtimen kan inte läsa sandboxens
 * data/runs/). ``runHostedPromptFlow`` läser det på ``done`` och bygger ett
 * svar som speglar den lokala kontraktsformen. Alla fält är valfria/nullbara —
 * en saknad/äldre sandbox utan ``result`` degraderar ärligt till det gamla
 * tunna svaret. ``engine`` skiljer OpenClaw-apply från legacy/answer-only så
 * attributionen aldrig kan maskeras.
 */
export interface HostedFollowupResult {
  engine: "openclaw" | "legacy" | "answer-only";
  /** build_site-runId (data/runs/<runId>/); null för answer-only. */
  runId: string | null;
  version: number | null;
  buildStatus: string | null;
  /** Parsad build-result.json (eller {} när den saknas). */
  buildResult: Record<string, unknown>;
  /** ``directives.copyDirectives`` ur PI-snapshotet (eller []). */
  appliedCopyDirectives: unknown[];
  /** OpenClaw-beslutet (model_dump) eller null på legacy/parse-fel. */
  openClawDecision: Record<string, unknown> | null;
  /** Bridge-utfallet {status, applied, previewShouldRefresh} eller null. */
  bridge: Record<string, unknown> | null;
  /** conversation-metadata (conversationKind/role/expectsAnswer) eller null. */
  conversation: Record<string, unknown> | null;
}

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
  /** Commit 3: rikt followup-resultat (svars-paritet). Satt av sandboxen. */
  result?: HostedFollowupResult;
}

const HOSTED_RUN_KEY_PREFIX = "viewser:hosted-run:";
const BUILD_CONTEXT_URL_KEY = "viewser:build-context:url";
const BUILD_CONTEXT_URL_ENV = "VIEWSER_BUILD_CONTEXT_URL";

/**
 * Durabel KV-pekare till senast persisterade run-state-paret för en sajt
 * (B194). Skrivs av orkestrerings-skriptet EFTER att både PI- och meta-blobben
 * laddats upp; läses pre-flight av ``startHostedBuild`` vid followup. Ingen
 * TTL — som ``viewser:site:<siteId>:current`` lever den tills nästa lyckade
 * bygge skriver över den.
 */
export function hostedRunStateKey(siteId: string): string {
  return `viewser:site:${siteId}:run-state`;
}

/** JSON-formen under ``viewser:site:<siteId>:run-state``. */
export interface HostedRunStatePointer {
  /** PI-versionen paret representerar (meta.version efter bygget). */
  version: number;
  /** Publik blob-URL till run-state/<siteId>/v<N>/project-input.json. */
  projectInputUrl: string;
  /** Publik blob-URL till run-state/<siteId>/v<N>/meta.json. */
  metaUrl: string;
  updatedAt: string;
  buildId?: string;
  /**
   * B199 v2: build-result.json-status för pekarens version ("ok"/"degraded").
   * Additivt — äldre pekare saknar fältet och rapporteras "unknown" i den
   * hostade run-historiken.
   */
  buildStatus?: string;
  /**
   * B199: ``build_site.py``-stdout-runId för DENNA versions run-katalog
   * (``data/runs/<runId>/``). Skilt från orkestreringens KV-UUID
   * (``viewser:hosted-run:<uuid>``) — det här är den kanoniska
   * artefakt-run-iden som ``run_followup_chain`` /
   * ``assemble_context("artifacts_plus_sections")`` läser. Sätts bara när
   * artefakt-tarballen (nedan) publicerats.
   */
  runId?: string;
  /**
   * B199: publik blob-URL till artefakt-tarballen
   * (``run-artifacts/<siteId>/v<N>/run-artifacts.tar.gz``) som innehåller
   * ``data/runs/<runId>/`` med de kanoniska artefakterna (input/site-brief/
   * site-plan/generation-package/build-result/quality-result). Vid followup
   * curlas + extraheras den tillbaka i sandboxen så OpenClaw apply-sömmen
   * (commit 2) och ``--base-run-id`` (commit 3) har artefakter att läsa.
   * Begränsning (v1, ärligt dokumenterad): pekaren spårar SENASTE versionen,
   * så en historisk baseRunId vars version ≠ senaste saknar hydrerade
   * artefakter — per-run-blob-historik är framtida arbete (B199).
   */
  runArtifactsUrl?: string;
}

/**
 * B199 v2 — durabelt hostat run-index. Två KV-nyckelfamiljer skrivna av
 * orkestrerings-skriptet efter varje lyckat hostat bygge (utöver run-state-
 * pekaren som bara spårar SENASTE versionen):
 *
 *   - ``viewser:site:<siteId>:run:v<N>`` — per-versions-posten för en sajt.
 *     Listas av den hostade run-historiken (siteId är capability-nyckeln,
 *     samma åtkomstmodell som B196:s siteId-bundna status-route).
 *   - ``viewser:run:<runId>`` — kanonisk build_site-runId → samma post.
 *     Löser /api/runs/[runId]/{artifacts,trace} hostat och låter
 *     ``startHostedBuild`` hydrera en HISTORISK baseRunId:s artefakter
 *     (stänger #307:s "bara senaste versionen"-begränsning).
 *
 * Båda är durabla (ingen TTL) — samma livscykel som
 * ``viewser:site:<siteId>:current``; prune-strategin är ett spårat
 * operatörsbeslut tillsammans med blob-prune för ``generated/``.
 */
export function hostedRunIndexKey(runId: string): string {
  return `viewser:run:${runId}`;
}

/** KV-nyckel för per-versions-posten i den hostade run-historiken. */
export function hostedRunVersionKey(siteId: string, version: number): string {
  return `viewser:site:${siteId}:run:v${version}`;
}

/** JSON-formen under ``viewser:run:<runId>`` och ``viewser:site:<siteId>:run:v<N>``. */
export interface HostedRunIndexEntry {
  /** Kanonisk build_site-runId (data/runs/<runId>/), INTE orkestrerings-UUID:t. */
  runId: string;
  siteId: string;
  version: number | null;
  buildId?: string;
  /** build-result.json-status ("ok"/"degraded"); saknas → "unknown" i UI. */
  buildStatus?: string;
  updatedAt: string;
  /** Publik blob-URL till versionens run-artifacts.tar.gz (B199). */
  runArtifactsUrl?: string;
}

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
 *     (lib/generated-blob-source.ts listar per-fil-blobbar — det är den
 *     ärliga fallback-källan), med samma skip-kataloger och .env-skydd som
 *     snapshot-site-to-blob.mjs.
 *   - Sist publiceras ``generated/<siteId>/.manifest.json`` med byggets exakta
 *     fil-set (B195): serveringen visar bara manifest-listade filer, så stale
 *     blobbar från ett tidigare bygge mot samma siteId aldrig syns i previewen.
 *   - G2 (ADR 0058): efter manifestet paketeras SAMMA fil-set som EN
 *     preview-bundle-tarball under
 *     ``preview-bundles/<siteId>/<buildId>/preview-bundle.tar.gz`` så
 *     preview-sandboxen kan skapas med source { type: "tarball" } (1 fetch +
 *     extraktion i sandboxen) i stället för hundratals enskilda blob-fetchar.
 *     Best-effort: ett bundle-fel faller aldrig bygget — pekaren får då inget
 *     previewBundleUrl-fält och preview-sidan tar fil-för-fil-vägen.
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
REPO_DIR="$(pwd)"
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
# Commit 3 (svars-paritet): baka in det rika followup-resultatet pa done.
# write_hosted_result() skrev /tmp/hosted-result.json fore den sista
# post_status done; TS-sidan laser doc["result"] och bygger ett svar som
# speglar lokala kontraktsformen. Saknas filen (init / aldre sandbox) faller
# TS arligt tillbaka pa det tunna svaret.
if os.environ["PHASE"] == "done":
    try:
        with open("/tmp/hosted-result.json", encoding="utf-8") as _rf:
            doc["result"] = json.load(_rf)
    except (OSError, ValueError):
        pass
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

# write_hosted_result <engine> — bygg det rika followup-resultatet (commit 3,
# svars-paritet) och skriv /tmp/hosted-result.json. post_status bakar in det i
# KV-doken pa done. TS-runtimen kan inte lasa sandboxens data/runs/, sa
# sandboxen producerar falten: version/buildStatus/buildResult/
# appliedCopyDirectives ur data/runs/<runId>/ + PI-snapshotet, samt
# openClawDecision/bridge/conversation ur OPENCLAW_BRIDGE_JSON-outputen.
# Honesty-gate speglar route.ts (legacyPathAppliedVisibleChange): pa en
# applicerad andring nollas openClawDecision sa "action bridge saknas" aldrig
# visas over en landad andring. answerText genereras TS-side (atervinner
# generateConversationAnswer/generateAppliedConfirmation).
write_hosted_result() {
  ENGINE="$1" ART_RUN_ID="\${RUN_ARTIFACT_RUN_ID:-}" ART_VERSION="\${RUN_STATE_VERSION:-}" REPO_DIR="$REPO_DIR" SITE_ID="$SITE_ID" python3 - > /tmp/hosted-result.json <<'PY'
import json, os

def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None

repo = os.environ.get("REPO_DIR") or "."
site_id = os.environ.get("SITE_ID", "")
engine = os.environ.get("ENGINE", "legacy")
run_id = os.environ.get("ART_RUN_ID") or ""
version_raw = os.environ.get("ART_VERSION") or ""
version = int(version_raw) if version_raw.isdigit() else None

build_result = {}
build_status = None
applied_visible = False
applied_directive_kinds = []
if run_id:
    br = read_json(os.path.join(repo, "data", "runs", run_id, "build-result.json"))
    if isinstance(br, dict):
        build_result = br
        build_status = br.get("status") if isinstance(br.get("status"), str) else None
        applied_visible = br.get("appliedVisibleEffect") is True
        # 1a honesty signal (site-3e7d71ad): which executor-owned edits this
        # follow-up actually applied. The legacy honesty-gate below requires
        # CONCRETE directives, never just appliedVisibleEffect.
        raw_kinds = br.get("appliedFollowupDirectiveKinds")
        if isinstance(raw_kinds, list):
            applied_directive_kinds = [k for k in raw_kinds if isinstance(k, str)]

# appliedCopyDirectives ur PI-snapshotet (samma falt readAppliedCopyDirectives
# laser TS-side; lat validering — schemat har redan validerat pa write-sidan).
copy_directives = []
pi = read_json(os.path.join(repo, "data", "prompt-inputs", site_id + ".project-input.json"))
if isinstance(pi, dict) and isinstance(pi.get("directives"), dict):
    raw = pi["directives"].get("copyDirectives")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            t, op, pl = item.get("target"), item.get("operation"), item.get("payload")
            if not (isinstance(t, str) and isinstance(op, str) and isinstance(pl, str) and pl):
                continue
            entry = {"target": t, "operation": op, "payload": pl}
            if isinstance(item.get("targetRef"), str) and item["targetRef"].strip():
                entry["targetRef"] = item["targetRef"]
            if isinstance(item.get("source"), str):
                entry["source"] = item["source"]
            copy_directives.append(entry)
            if len(copy_directives) >= 8:
                break

# OpenClaw-beslut + bridge ur apply-outputen (sentinel-kontrakt).
decision = None
bridge = None
conversation = None
SENT = "OPENCLAW_BRIDGE_JSON:"
try:
    text = open("/tmp/openclaw-apply.out", encoding="utf-8", errors="replace").read()
except OSError:
    text = ""
for line in reversed(text.splitlines()):
    s = line.strip()
    if not s.startswith(SENT):
        continue
    try:
        obj = json.loads(s[len(SENT):].strip())
    except ValueError:
        continue
    if isinstance(obj, dict) and isinstance(obj.get("decision"), dict):
        decision = obj["decision"]
        b = obj.get("bridge")
        if isinstance(b, dict):
            bridge = {
                "status": b.get("status"),
                "applied": b.get("applied") is True,
                "previewShouldRefresh": b.get("previewShouldRefresh") is True,
            }
            chain = b.get("chain")
            if isinstance(chain, dict):
                bridge["chain"] = {
                    "editKind": chain.get("editKind"),
                    "version": chain.get("version"),
                    "changedRoutes": chain.get("changedRoutes"),
                    "runId": chain.get("runId"),
                }
        conv = decision.get("conversation")
        if isinstance(conv, dict):
            conversation = conv
        break

# Honesty-gate (speglar route.ts legacyPathAppliedVisibleChange + applied-vagen).
if engine == "answer-only":
    open_claw_decision = decision
    run_id, version, build_status, build_result, copy_directives = "", None, None, {}, []
elif engine == "openclaw":
    open_claw_decision = None  # applied -> bridge staller, beslutet nollas (som lokalt)
else:  # legacy
    # 1c (site-3e7d71ad): require CONCRETE applied directives (copy directives
    # OR a non-empty appliedFollowupDirectiveKinds) before nulling the honest
    # OpenClaw decision — never just appliedVisibleEffect, which a brief
    # paraphrase byte diff could flip. Mirrors route.ts legacyPathAppliedVisibleChange.
    legacy_visible = bool(copy_directives) or bool(applied_directive_kinds)
    open_claw_decision = None if legacy_visible else decision

result = {
    "engine": engine,
    "runId": run_id or None,
    "version": version,
    "buildStatus": build_status,
    "buildResult": build_result,
    "appliedCopyDirectives": copy_directives,
    "openClawDecision": open_claw_decision,
    "bridge": bridge,
    "conversation": conversation,
}
print(json.dumps(result, ensure_ascii=False))
PY
}

# Fas 1: Python-runtime + beroenden. node24-imagens default-python3 ar 3.9,
# men pipen kraver >= 3.11 (bl.a. "from datetime import UTC"). Valj basta
# tillgangliga moderna python, annars installera via dnf (AL2023-basen har
# python3.11-paketet). Status-heredocs nedan ar medvetet 3.9-kompatibla och
# kor plain python3.
post_status "installing" "" ""
PYTHON_BIN=""
for cand in python3.13 python3.12 python3.11; do
  if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
done
if [ -z "$PYTHON_BIN" ]; then
  if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON_BIN="python3"
  fi
fi
if [ -z "$PYTHON_BIN" ]; then
  sudo dnf install -y python3.11 >/dev/null 2>&1 \\
    || dnf install -y python3.11 >/dev/null 2>&1 \\
    || true
  command -v python3.11 >/dev/null 2>&1 && PYTHON_BIN="python3.11"
fi
if [ -z "$PYTHON_BIN" ]; then
  fail "Ingen python >= 3.11 i sandboxen (python3 ar $(python3 --version 2>&1))."
fi
echo "hosted-build: anvander $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))."
"$PYTHON_BIN" -m pip --version >/dev/null 2>&1 \\
  || "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 \\
  || true
"$PYTHON_BIN" -m pip install --quiet -r requirements.txt \\
  || "$PYTHON_BIN" -m pip install --quiet --user -r requirements.txt \\
  || fail "pip install -r requirements.txt misslyckades i sandboxen."

# Fas 2: prompt -> Project Input. Foljdlage hamtar forst run-state-paret
# (B194): prompt_to_project_input.py harleder foregaende version ur
# data/prompt-inputs/<siteId>.{project-input,meta}.json — lokalt finns de pa
# disk, hostat curlas de fran blob-URL:erna som TS-sidan laste ur KV-pekaren
# viewser:site:<siteId>:run-state och skickade som env. Saknas pekaren har
# startHostedBuild redan failat arligt fore sandbox-start.
fetch_run_state() {
  url="$1"
  dest="$2"
  attempt=1
  while [ "$attempt" -le 3 ]; do
    http_code=$(curl -s -o "$dest" -w "%{http_code}" "$url" || echo "000")
    case "$http_code" in
      2*) return 0 ;;
    esac
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
  return 1
}

post_status "project-input" "" ""
# OpenClaw apply-grenens flaggor (set -u-sakra defaults; satts i followup-grenen).
OPENCLAW_APPLIED=0
RUN_STATE_VERSION_OVERRIDE=""
if [ "$FOLLOWUP_MODE" = "1" ]; then
  if [ -z "\${RUN_STATE_PI_URL:-}" ] || [ -z "\${RUN_STATE_META_URL:-}" ]; then
    fail "Foljdprompt utan run-state-URL:er — kor forst ett initialt hostat bygge for siteId $SITE_ID."
  fi
  mkdir -p "$REPO_DIR/data/prompt-inputs"
  fetch_run_state "$RUN_STATE_PI_URL" "$REPO_DIR/data/prompt-inputs/$SITE_ID.project-input.json" \\
    || fail "Kunde inte hamta persisterad project-input fran blob (run-state, B194)."
  fetch_run_state "$RUN_STATE_META_URL" "$REPO_DIR/data/prompt-inputs/$SITE_ID.meta.json" \\
    || fail "Kunde inte hamta persisterad meta fran blob (run-state, B194)."
  # B199 — hydrera de kanoniska run-artefakterna (data/runs/<runId>/) tillbaka
  # i sandboxen. Lokalt ligger de pa disk; hostat curlas tarballen som TS-sidan
  # laste ur pekarens runArtifactsUrl och extraheras sa
  # run_followup_chain / assemble_context("artifacts_plus_sections") och
  # prompt_to_project_input --base-run-id har artefakter att lasa. En aldre
  # pekare (fore B199) eller misslyckad nedladdning ar INTE fatalt har: apply-
  # somen (commit 2) degraderar da arligt till legacy-vagen, som bara behover
  # PI/meta-paret ovan. Tom URL = ingen hydrering (set -u-sakert).
  if [ -n "\${RUN_ARTIFACTS_URL:-}" ] && [ -n "\${RUN_ARTIFACTS_RUN_ID:-}" ]; then
    mkdir -p "$REPO_DIR/data/runs"
    if fetch_run_state "$RUN_ARTIFACTS_URL" /tmp/run-artifacts.tar.gz; then
      if tar -xzf /tmp/run-artifacts.tar.gz -C "$REPO_DIR/data/runs" 2>/dev/null; then
        echo "hosted-build: run-artefakter hydrerade (B199, runId $RUN_ARTIFACTS_RUN_ID)."
      else
        echo "hosted-build: VARNING — run-artefakt-tarballen kunde inte extraheras; apply degraderar till legacy." >&2
      fi
    else
      echo "hosted-build: VARNING — run-artefakt-tarballen kunde inte hamtas; apply degraderar till legacy." >&2
    fi
  fi
  # Commit 2 — OpenClaw apply-som: kor dirigenten FORST i followup-laget, exakt
  # som den lokala runPromptBuildOnce-grenordningen (applied -> answer-only ->
  # legacy). SAJTBYGGAREN_GENERATED_DIR exporteras sa run_followup_chain:s build
  # (som inte tar --generated-dir via CLI:t) landar i sandboxens generated-dir;
  # RUNS_DIR ar default = $REPO_DIR/data/runs (= cwd) sa den nya run-katalogen
  # hamnar dar hydreringen + uploaden vantar den.
  export SAJTBYGGAREN_GENERATED_DIR="$GENERATED_DIR"
  # --base-run-id-arrayen fylls i commit 3 (BASE_RUN_ID); tom = ingen flagga
  # (set -u-saker expansion).
  BASE_RUN_ID_ARGS=()
  if [ -n "\${BASE_RUN_ID:-}" ]; then
    BASE_RUN_ID_ARGS=(--base-run-id "$BASE_RUN_ID")
  fi
  # PROMPT_TEXT nar bash enbart som quotad env-expansion — aldrig interpolerad.
  APPLY_OUT=$("$PYTHON_BIN" scripts/run_openclaw_followup.py --apply --site-id "$SITE_ID" \${BASE_RUN_ID_ARGS[@]+"\${BASE_RUN_ID_ARGS[@]}"} -- "$PROMPT_TEXT" 2>&1) || true
  printf '%s' "$APPLY_OUT" > /tmp/openclaw-apply.out
  # Parsa sista OPENCLAW_BRIDGE_JSON-raden (samma sentinel-kontrakt som
  # openclaw-runner.ts). Skriver BARA kontrollerade enum/id-falt
  # (kind/runId/version/buildStatus) till env-filen sa source:n ar saker —
  # prompt/answerText/decision rors aldrig har.
  python3 - > /tmp/openclaw-apply.env <<'PY'
import json, re
SENT = "OPENCLAW_BRIDGE_JSON:"
try:
    text = open("/tmp/openclaw-apply.out", encoding="utf-8", errors="replace").read()
except OSError:
    text = ""
payload = None
for line in reversed(text.splitlines()):
    s = line.strip()
    if not s.startswith(SENT):
        continue
    try:
        obj = json.loads(s[len(SENT):].strip())
    except ValueError:
        continue
    if isinstance(obj, dict) and isinstance(obj.get("decision"), dict):
        payload = obj
        break
ANSWER_KINDS = {"small_talk", "site_opinion", "question"}
kind, run_id, version, build_status = "fallback", "", "", ""
if payload is not None:
    decision = payload.get("decision") or {}
    bridge = payload.get("bridge") or {}
    conv = decision.get("conversation") or {}
    chain = bridge.get("chain") or {}
    applied = bridge.get("applied") is True
    conv_kind = conv.get("conversationKind")
    expects = conv.get("expectsAnswer") is True
    bs = chain.get("buildStatus")
    if (not applied) and (conv_kind in ANSWER_KINDS or expects):
        kind = "answer_only"
    elif applied and bs in ("ok", "degraded"):
        kind = "applied"
        rid = chain.get("runId")
        run_id = rid if isinstance(rid, str) and re.fullmatch(r"[A-Za-z0-9._-]+", rid) else ""
        ver = chain.get("version")
        version = str(ver) if isinstance(ver, int) else ""
        build_status = bs
    elif applied:
        kind = "applied_failed"
        build_status = bs if isinstance(bs, str) else "failed"
    # else: fallback (no-op / unmapped edit / ren copy-andring) -> legacy nedan.
print("APPLY_KIND='%s'" % kind)
print("APPLY_RUN_ID='%s'" % run_id)
print("APPLY_VERSION='%s'" % version)
print("APPLY_BUILD_STATUS='%s'" % build_status)
PY
  APPLY_KIND="fallback"; APPLY_RUN_ID=""; APPLY_VERSION=""; APPLY_BUILD_STATUS=""
  . /tmp/openclaw-apply.env 2>/dev/null || true
  case "$APPLY_KIND" in
    answer_only)
      # Answer-only/conversation: starta INGET bygge. Det rika resultatet
      # (engine=answer-only + beslut/conversation) skrivs sa TS-sidan kan
      # generera answerText och returnera runId:null + bridge.applied:false.
      echo "hosted-build: OpenClaw answer-only — ingen build."
      write_hosted_result "answer-only"
      post_status "done" "" ""
      exit 0
      ;;
    applied)
      # OpenClaw byggde en ny version och current.json swappades (ok/degraded).
      RUN_ARTIFACT_RUN_ID="$APPLY_RUN_ID"
      RUN_STATE_VERSION_OVERRIDE="$APPLY_VERSION"
      OPENCLAW_APPLIED=1
      echo "hosted-build: OpenClaw apply landade v$APPLY_VERSION (runId $APPLY_RUN_ID, status $APPLY_BUILD_STATUS)."
      ;;
    applied_failed)
      # En ny version applicerades men bygget misslyckades — maskera ALDRIG som
      # lyckat och fall INTE till legacy (skulle dubbel-bygga). Arlig fail.
      fail "OpenClaw apply skrev en ny version men bygget misslyckades (status $APPLY_BUILD_STATUS)."
      ;;
    *)
      # applied=false icke-conversation (ren copy-andring / omappad edit) ELLER
      # parse-fel: fall tillbaka till den FUNGERANDE legacy-vagen, exakt som
      # lokalt. Attributeras arligt nedan (aldrig fejkad bridge.applied=true).
      echo "hosted-build: OpenClaw gav ingen applicerbar capability-andring — legacy-vagen tar over (arlig fallback)."
      ;;
  esac
fi

if [ "\${OPENCLAW_APPLIED:-0}" != "1" ]; then
  # Legacy/init-vagen (oforandrad sedan B194): init bygger alltid har; en
  # followup landar har nar OpenClaw inte applicerade (copy-andring/no-op/
  # parse-fel). Bevarar dagens fungerande hostade copy-direktivvag.
  if [ "$FOLLOWUP_MODE" = "1" ]; then
    # asset_set-forwarding: TOOL_INTENT_JSON ar redan sanerad TS-side
    # (sanitizedAssetSetIntent) och nar bash enbart som quotad env-expansion
    # — aldrig interpolerad i skriptkoden. Tom strang = ingen flagga.
    TOOL_INTENT_ARGS=()
    if [ -n "\${TOOL_INTENT_JSON:-}" ]; then
      TOOL_INTENT_ARGS=(--tool-intent "$TOOL_INTENT_JSON")
    fi
    # Commit 3 (request-paritet): --base-run-id + --marked-sections forwardas
    # till legacy-PI:n (samma flaggor som lokala prompt-runner.ts). Tomma
    # env-varden = ingen flagga (set -u-saker array-expansion). runId/JSON nar
    # CLI:t bara som quotad env-expansion — aldrig interpolerade i bash.
    LEGACY_BASE_RUN_ID_ARGS=()
    if [ -n "\${BASE_RUN_ID:-}" ]; then
      LEGACY_BASE_RUN_ID_ARGS=(--base-run-id "$BASE_RUN_ID")
    fi
    MARKED_SECTIONS_ARGS=()
    if [ -n "\${MARKED_SECTIONS_JSON:-}" ]; then
      MARKED_SECTIONS_ARGS=(--marked-sections "$MARKED_SECTIONS_JSON")
    fi
    PI_OUT=$("$PYTHON_BIN" scripts/prompt_to_project_input.py "$PROMPT_TEXT" --followup-site-id "$SITE_ID" \${TOOL_INTENT_ARGS[@]+"\${TOOL_INTENT_ARGS[@]}"} \${LEGACY_BASE_RUN_ID_ARGS[@]+"\${LEGACY_BASE_RUN_ID_ARGS[@]}"} \${MARKED_SECTIONS_ARGS[@]+"\${MARKED_SECTIONS_ARGS[@]}"} 2>&1) \\
      || fail "prompt_to_project_input (followup) misslyckades: $(printf '%s' "$PI_OUT" | tail -c 600)"
  else
    PI_OUT=$("$PYTHON_BIN" scripts/prompt_to_project_input.py "$PROMPT_TEXT" --site-id "$SITE_ID" 2>&1) \\
      || fail "prompt_to_project_input misslyckades: $(printf '%s' "$PI_OUT" | tail -c 600)"
  fi
  DOSSIER_PATH=$(printf '%s\\n' "$PI_OUT" | sed -n 's/^dossierPath: //p' | head -n 1)
  if [ -z "$DOSSIER_PATH" ]; then
    fail "dossierPath saknas i prompt_to_project_input-output."
  fi

  # Fas 3: deterministiska byggaren (npm install + next build kors dar inne av
  # build_site.py sjalv — Quality Gate far riktiga build-status-signaler).
  post_status "building" "" ""
  BUILD_OUT=$("$PYTHON_BIN" scripts/build_site.py --dossier "$DOSSIER_PATH" --generated-dir "$GENERATED_DIR" 2>&1) \\
    || fail "build_site.py misslyckades: $(printf '%s' "$BUILD_OUT" | tail -c 600)"
  # B199 — den kanoniska artefakt-run-iden (data/runs/<runId>/) som build_site.py
  # skrev. SKILD fran orkestreringens KV-UUID ($RUN_ID): build_site.py-stdout-
  # runId ("runId: <id>") som run-artefakt-persistensen nedan tarballar.
  RUN_ARTIFACT_RUN_ID=$(printf '%s\\n' "$BUILD_OUT" | sed -n 's/^runId: //p' | head -n 1)
fi

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
#
# Robusthet (lardom fran forsta publika felet "Blob-upload misslyckades."):
#   - Varje path-segment URL-kodas via python3 — genererade sajter kan ha
#     filnamn med mellanslag/akzenter som annars ger trasiga PUT-requests.
#   - 3 forsok per fil med backoff — enstaka 429/5xx fran blob-api:t far
#     inte falla hela bygget.
#   - Vid slutgiltigt fel skrivs HTTP-kod + fil + svarskropp till
#     /tmp/blob-upload-error.txt och tas med i KV-statusen sa nasta fel
#     ar diagnosbart i stallet for generiskt.
post_status "uploading" "" "$ACTIVE_BUILD_ID"
BUILD_DIR="$GENERATED_DIR/$SITE_ID/builds/$ACTIVE_BUILD_ID"
cd "$BUILD_DIR" || fail "Build-katalogen saknas: $BUILD_DIR"

upload_file() {
  rel="$1"
  encoded=$(REL="$rel" python3 -c 'import os, urllib.parse; print("/".join(urllib.parse.quote(seg, safe="") for seg in os.environ["REL"].split("/")))')
  attempt=1
  while [ "$attempt" -le 3 ]; do
    http_code=$(curl -s -o /tmp/blob-upload-body -w "%{http_code}" -X PUT "$BLOB_API/generated/$SITE_ID/$encoded" \\
      -H "Authorization: Bearer $BLOB_READ_WRITE_TOKEN" \\
      -H "x-api-version: 7" \\
      -H "x-add-random-suffix: 0" \\
      --data-binary "@$rel" || echo "000")
    case "$http_code" in
      2*) return 0 ;;
    esac
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
  printf 'HTTP %s for "%s": %s' "$http_code" "$rel" "$(tail -c 300 /tmp/blob-upload-body 2>/dev/null)" > /tmp/blob-upload-error.txt
  return 1
}

# Fil-listan gar via en manifest-fil i stallet for processsubstitution —
# "< <(lista)" ar inte palitlig i sandboxens icke-interaktiva bash, och utan
# set -e blev en trasig redirect ett TYST noll-varvs-loop med falsk "done"
# (rotorsaken till site-a7cd97e7: done-status men 0 blobbar). Varje led
# verifieras nu hart: listningen, att listan inte ar tom, och att minst en
# fil faktiskt laddades upp.
#
# Pre-built preview (2026-06-12): rot-nivans fardiga .next/ INKLUDERAS i
# uploaden sa preview-sandboxen kan kora npm install --omit=dev + next start
# utan eget next build (kallstart minuter -> sekunder). Skip-logiken speglar
# exakt collectSource(includeBuiltNext) i vercel-sandbox-runner.ts:
#   - .next/cache prunas (webpack-cache, ~95 % av .next-bytes, aldrig last
#     av next start),
#   - .next/trace prunas (build-telemetri; har Linux-paths men behovs aldrig),
#   - NASTLADE .next (i undermappar) prunas som forr — bara rot-nivans slapps.
# Bygget sker Linux->Linux sa Windows-path-portabilitetsfallan (B3-noten i
# collectSource) ar inte relevant har. B195-manifestet listar fortsatt exakt
# det uppladdade fil-setet (upload-loopen nedan ar oforandrad), och
# generated-blob-source.ts filtrerar .next nar pre-built inte ska anvandas.
find . \\( -name node_modules -o -name .git -o -name .turbo -o -name .vercel -o -name .cache -o -name out \\) -prune -o -path ./.next/cache -prune -o -path ./.next/trace -prune -o \\( -name .next ! -path ./.next \\) -prune -o -type f -print | sed 's|^\\./||' > /tmp/upload-manifest.txt \\
  || fail "Kunde inte lista build-filerna for blob-upload."
[ -s /tmp/upload-manifest.txt ] || fail "Fil-listan for blob-upload ar tom — build-katalogen ser tom ut."

uploaded=0
rm -f /tmp/blob-upload-error.txt /tmp/served-manifest.txt
: > /tmp/served-manifest.txt
while IFS= read -r rel; do
  base=$(basename "$rel")
  case "$base" in
    .env.example) ;;
    .env*) continue ;;
  esac
  upload_file "$rel" || fail "Blob-upload misslyckades: $(cat /tmp/blob-upload-error.txt 2>/dev/null)"
  printf '%s\\n' "$rel" >> /tmp/served-manifest.txt
  uploaded=$((uploaded + 1))
done < /tmp/upload-manifest.txt
[ "$uploaded" -gt 0 ] || fail "0 filer laddades upp till blob — inget att publicera."
echo "hosted-build: $uploaded filer uppladdade till blob."

# B195 — stale-blob-cleanup: publicera SIST ett manifest (.manifest.json) med
# EXAKT det fil-set bygget laddade upp. lib/generated-blob-source.ts serverar
# bara filer som star i manifestet, sa blobbar som ligger kvar fran ett tidigare
# bygge mot samma siteId (overwrite-upload raderar dem aldrig — en borttagen
# route/asset blir annars en stale fil i previewen) ignoreras. Skrivs sist, EFTER
# att alla filer lyckats, sa manifestet aldrig pekar pa en saknad blob.
SERVED_LIST=/tmp/served-manifest.txt BUILD_ID="$ACTIVE_BUILD_ID" python3 - > "$BUILD_DIR/.manifest.json" <<'PY'
import json, os
with open(os.environ["SERVED_LIST"], encoding="utf-8") as fh:
    files = [line for line in fh.read().splitlines() if line]
print(json.dumps({"buildId": os.environ.get("BUILD_ID", ""), "files": files}, ensure_ascii=False))
PY
upload_file ".manifest.json" || fail "Manifest-upload misslyckades: $(cat /tmp/blob-upload-error.txt 2>/dev/null)"
echo "hosted-build: manifest publicerat ($uploaded filer)."

# G2 (ADR 0058) — preview-bundle: paketera EXAKT det publicerade fil-setet
# (served-manifest, .env-skyddet och skip-katalogerna ar redan applicerade i
# upload-loopen ovan) som EN tar.gz och publicera den versions-scopat under
# preview-bundles/<siteId>/<buildId>/preview-bundle.tar.gz. Preview-starten
# skapar da sandboxen direkt fran tarballen (1 blob-fetch + extraktion i
# sandbox-infran) i stallet for att lista + ladda ner hundratals enskilda
# blobbar (prod-incidenten 2026-06-12: 6-7 min kallinhamtning).
#
# Arlighetsregler:
#   - Taken speglar MAX_FILES/MAX_TOTAL_BYTES i generated-blob-source.ts
#     (4000 filer / 64 MB okomprimerat) — samma fil-set, samma tak. En bundle
#     over taket publiceras ALDRIG (fil-for-fil-vagens nedladdningsvakt
#     hade stoppat samma trad).
#   - Bundlen publiceras BARA nar fil-setet bar en komplett next-build
#     (.next/BUILD_ID) — da kan preview-sidan lita pa att bundle => pre-built.
#   - Best-effort: ett bundle-fel faller ALDRIG bygget (fil-for-fil-kallan
#     ar redan publicerad och forblir den arliga fallbacken). Pekaren far
#     previewBundleUrl ENBART nar uploaden bevisligen lyckades.
# tarfile (python3 stdlib, 3.9-kompatibel) i stallet for GNU tar-flaggor:
# hanterar mellanslag/specialtecken i filnamn utan --verbatim-files-from.
PREVIEW_BUNDLE_PUBLISHED=""
PB_STATUS="skipped"; PB_REASON="unknown"; PB_FILES="0"; PB_BYTES="0"
python3 - > /tmp/preview-bundle.env <<'PY'
import os, tarfile
MAX_FILES = 4000
MAX_TOTAL_BYTES = 64 * 1024 * 1024
status, reason = "skipped", "unknown"
files = []
total = 0
try:
    with open("/tmp/served-manifest.txt", encoding="utf-8") as fh:
        files = [line for line in fh.read().splitlines() if line]
    for rel in files:
        total += os.path.getsize(rel)
except OSError:
    status, reason = "skipped", "unreadable-fileset"
else:
    if not files:
        reason = "empty-fileset"
    elif ".next/BUILD_ID" not in files:
        reason = "no-prebuilt-next"
    elif len(files) > MAX_FILES or total > MAX_TOTAL_BYTES:
        reason = "size-guard"
    else:
        try:
            with tarfile.open("/tmp/preview-bundle.tar.gz", "w:gz") as tf:
                for rel in files:
                    tf.add(rel, arcname=rel, recursive=False)
            status, reason = "ok", ""
        except (OSError, tarfile.TarError):
            status, reason = "skipped", "tar-failed"
print("PB_STATUS='%s'" % status)
print("PB_REASON='%s'" % reason)
print("PB_FILES='%d'" % len(files))
print("PB_BYTES='%d'" % total)
PY
. /tmp/preview-bundle.env 2>/dev/null || true

upload_preview_bundle() {
  src="$1"
  attempt=1
  while [ "$attempt" -le 3 ]; do
    http_code=$(curl -s -o /tmp/preview-bundle-resp -w "%{http_code}" -X PUT "$BLOB_API/preview-bundles/$SITE_ID/$ACTIVE_BUILD_ID/preview-bundle.tar.gz" \\
      -H "Authorization: Bearer $BLOB_READ_WRITE_TOKEN" \\
      -H "x-api-version: 7" \\
      -H "x-add-random-suffix: 0" \\
      --data-binary "@$src" || echo "000")
    case "$http_code" in
      2*)
        PREVIEW_BUNDLE_LAST_URL=$(python3 -c 'import json; print(json.load(open("/tmp/preview-bundle-resp")).get("url", ""))' 2>/dev/null)
        [ -n "$PREVIEW_BUNDLE_LAST_URL" ] && return 0
        ;;
    esac
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
  return 1
}

if [ "$PB_STATUS" = "ok" ]; then
  if upload_preview_bundle /tmp/preview-bundle.tar.gz; then
    PREVIEW_BUNDLE_PUBLISHED="$PREVIEW_BUNDLE_LAST_URL"
    echo "hosted-build: preview-bundle publicerad ($PB_FILES filer, $PB_BYTES byte okomprimerat)."
  else
    echo "hosted-build: VARNING — preview-bundlen kunde inte publiceras; preview tar fil-for-fil-vagen." >&2
  fi
else
  echo "hosted-build: preview-bundle hoppades over ($PB_REASON) — preview tar fil-for-fil-vagen." >&2
fi

# Hostad current.json-motsvarighet: viewser:site:<siteId>:current (ingen TTL —
# pekaren ar durabel tills nasta lyckade bygge skriver over den). G2: pekaren
# bar aven preview-bundlens URL + storlek nar den publicerades (utelamnas
# annars sa preview-sidan arligt faller tillbaka till fil-for-fil).
CURRENT_PAYLOAD=$(BUILD_ID="$ACTIVE_BUILD_ID" BUNDLE_URL="$PREVIEW_BUNDLE_PUBLISHED" BUNDLE_BYTES="$PB_BYTES" BUNDLE_FILES="$PB_FILES" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
doc = {
    "buildId": os.environ["BUILD_ID"],
    "blobPrefix": "generated/" + os.environ["SITE_ID"] + "/",
    "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
bundle_url = os.environ.get("BUNDLE_URL") or ""
if bundle_url.startswith("https://"):
    doc["previewBundleUrl"] = bundle_url
    if (os.environ.get("BUNDLE_BYTES") or "").isdigit():
        doc["previewBundleBytes"] = int(os.environ["BUNDLE_BYTES"])
    if (os.environ.get("BUNDLE_FILES") or "").isdigit():
        doc["previewBundleFileCount"] = int(os.environ["BUNDLE_FILES"])
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

# B194 — persistera run-state for nasta foljdprompt: det farska PI/meta-paret
# laddas upp versions-scopat under run-state/<siteId>/v<N>/ (immutabelt: ett
# halvlyckat par kan aldrig refereras eftersom KV-pekaren flyttas forst nar
# BADA filerna ar uppe; den gamla pekaren pekar pa ett intakt aldre par).
# Fel har faller INTE bygget — sajten ar redan publicerad — men pekaren
# lamnas ororda sa nasta foljdprompt utgar fran senast KONSISTENTA paret.
# Versionen: fran OpenClaw-bridgen (apply-vagen) eller prompt_to_project_input-
# stdouten (legacy/init-vagen). PI_OUT ar osatt pa apply-vagen (set -u), darfor
# grenen.
if [ "$OPENCLAW_APPLIED" = "1" ]; then
  RUN_STATE_VERSION="$RUN_STATE_VERSION_OVERRIDE"
else
  RUN_STATE_VERSION=$(printf '%s\\n' "$PI_OUT" | sed -n 's/^version: //p' | head -n 1)
fi
PI_SNAPSHOT="$REPO_DIR/data/prompt-inputs/$SITE_ID.project-input.json"
META_SNAPSHOT="$REPO_DIR/data/prompt-inputs/$SITE_ID.meta.json"

upload_run_state() {
  src="$1"
  name="$2"
  attempt=1
  while [ "$attempt" -le 3 ]; do
    http_code=$(curl -s -o /tmp/run-state-resp -w "%{http_code}" -X PUT "$BLOB_API/run-state/$SITE_ID/v$RUN_STATE_VERSION/$name" \\
      -H "Authorization: Bearer $BLOB_READ_WRITE_TOKEN" \\
      -H "x-api-version: 7" \\
      -H "x-add-random-suffix: 0" \\
      --data-binary "@$src" || echo "000")
    case "$http_code" in
      2*)
        RUN_STATE_LAST_URL=$(python3 -c 'import json; print(json.load(open("/tmp/run-state-resp")).get("url", ""))' 2>/dev/null)
        [ -n "$RUN_STATE_LAST_URL" ] && return 0
        ;;
    esac
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
  return 1
}

# B199 — ladda upp de kanoniska run-artefakterna som EN tarball (1 PUT i
# stallet for sex separata) versions-scopat under
# run-artifacts/<siteId>/v<N>/run-artifacts.tar.gz. Tarballens topp-katalog AR
# runId, sa nasta followup extraherar den rakt tillbaka till data/runs/<runId>/.
# Best-effort: ett fel lamnar RUN_ARTIFACTS_PUBLISHED tom — pekaren far da
# fortfarande PI/meta (B194) men ingen artefakt-URL, och nasta followup
# degraderar arligt till legacy. Samma robusthet som upload_run_state.
upload_run_artifacts() {
  src="$1"
  attempt=1
  while [ "$attempt" -le 3 ]; do
    http_code=$(curl -s -o /tmp/run-artifacts-resp -w "%{http_code}" -X PUT "$BLOB_API/run-artifacts/$SITE_ID/v$RUN_STATE_VERSION/run-artifacts.tar.gz" \\
      -H "Authorization: Bearer $BLOB_READ_WRITE_TOKEN" \\
      -H "x-api-version: 7" \\
      -H "x-add-random-suffix: 0" \\
      --data-binary "@$src" || echo "000")
    case "$http_code" in
      2*)
        RUN_ARTIFACTS_LAST_URL=$(python3 -c 'import json; print(json.load(open("/tmp/run-artifacts-resp")).get("url", ""))' 2>/dev/null)
        [ -n "$RUN_ARTIFACTS_LAST_URL" ] && return 0
        ;;
    esac
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
  return 1
}

if [ -n "$RUN_STATE_VERSION" ] && [ -f "$PI_SNAPSHOT" ] && [ -f "$META_SNAPSHOT" ]; then
  RUN_STATE_PI_PUBLISHED=""
  RUN_STATE_META_PUBLISHED=""
  if upload_run_state "$PI_SNAPSHOT" "project-input.json"; then
    RUN_STATE_PI_PUBLISHED="$RUN_STATE_LAST_URL"
    if upload_run_state "$META_SNAPSHOT" "meta.json"; then
      RUN_STATE_META_PUBLISHED="$RUN_STATE_LAST_URL"
    fi
  fi
  # B199 — tarballa + ladda upp data/runs/<runId>/ (best-effort, oberoende av
  # PI/meta-utfallet ovan men trastas in i samma pekare nedan).
  RUN_ARTIFACTS_PUBLISHED=""
  if [ -n "\${RUN_ARTIFACT_RUN_ID:-}" ] && [ -d "$REPO_DIR/data/runs/$RUN_ARTIFACT_RUN_ID" ]; then
    if tar -czf /tmp/run-artifacts.tar.gz -C "$REPO_DIR/data/runs" "$RUN_ARTIFACT_RUN_ID" 2>/dev/null; then
      if upload_run_artifacts /tmp/run-artifacts.tar.gz; then
        RUN_ARTIFACTS_PUBLISHED="$RUN_ARTIFACTS_LAST_URL"
      else
        echo "hosted-build: VARNING — run-artefakt-tarballen kunde inte publiceras (B199); followups degraderar till legacy." >&2
      fi
    else
      echo "hosted-build: VARNING — run-artefakt-tarballen kunde inte skapas (B199)." >&2
    fi
  fi
  if [ -n "$RUN_STATE_PI_PUBLISHED" ] && [ -n "$RUN_STATE_META_PUBLISHED" ]; then
    RUN_STATE_PAYLOAD=$(PI_URL="$RUN_STATE_PI_PUBLISHED" META_URL="$RUN_STATE_META_PUBLISHED" RS_VERSION="$RUN_STATE_VERSION" BUILD_ID="$ACTIVE_BUILD_ID" ARTIFACTS_URL="$RUN_ARTIFACTS_PUBLISHED" ARTIFACT_RUN_ID="\${RUN_ARTIFACT_RUN_ID:-}" REPO_DIR="$REPO_DIR" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
doc = {
    "version": int(os.environ["RS_VERSION"]),
    "projectInputUrl": os.environ["PI_URL"],
    "metaUrl": os.environ["META_URL"],
    "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "buildId": os.environ["BUILD_ID"],
}
# B199: bara med pekaren nar tarballen faktiskt publicerades — annars far
# nasta followup arligt veta att artefakter saknas (tom URL = ingen hydrering).
artifacts_url = os.environ.get("ARTIFACTS_URL") or ""
artifact_run_id = os.environ.get("ARTIFACT_RUN_ID") or ""
if artifacts_url and artifact_run_id:
    doc["runId"] = artifact_run_id
    doc["runArtifactsUrl"] = artifacts_url
# B199 v2: arlig build-status i pekaren (ok/degraded) sa den hostade
# run-historiken slipper gissa. Saknad/olasbar fil -> faltet utelamnas.
if artifact_run_id:
    try:
        with open(
            os.path.join(os.environ.get("REPO_DIR") or ".", "data", "runs", artifact_run_id, "build-result.json"),
            encoding="utf-8",
        ) as _bf:
            _status = json.load(_bf).get("status")
        if isinstance(_status, str) and _status:
            doc["buildStatus"] = _status
    except (OSError, ValueError):
        pass
key = "viewser:site:" + os.environ["SITE_ID"] + ":run-state"
print(json.dumps(["SET", key, json.dumps(doc, ensure_ascii=False)]))
PY
)
    if [ -n "$KV_REST_URL" ] && [ -n "$KV_REST_TOKEN" ]; then
      curl -s -X POST "$KV_REST_URL" \\
        -H "Authorization: Bearer $KV_REST_TOKEN" \\
        -H "Content-Type: application/json" \\
        -d "$RUN_STATE_PAYLOAD" >/dev/null || true
    fi
    if [ -n "$RUN_ARTIFACTS_PUBLISHED" ]; then
      echo "hosted-build: run-state v$RUN_STATE_VERSION persisterad (B194) + run-artefakter (B199, runId $RUN_ARTIFACT_RUN_ID)."
    else
      echo "hosted-build: run-state v$RUN_STATE_VERSION persisterad (B194); run-artefakter saknas — followups degraderar till legacy." >&2
    fi
  else
    echo "hosted-build: VARNING — run-state-paret kunde inte publiceras; foljdprompter utgar fran foregaende version." >&2
  fi
  # B199 v2 — durabelt run-index sa hostad run-historik/artefakt-lasning och
  # historisk baseRunId-hydrering fungerar: per-versions-posten
  # viewser:site:<siteId>:run:v<N> + runId-indexet viewser:run:<runId>.
  # Skrivs oberoende av PI/meta-utfallet (historiken ar byggets sanning) och
  # best-effort: ett index-fel faller aldrig ett redan publicerat bygge.
  if [ -n "\${RUN_ARTIFACT_RUN_ID:-}" ]; then
    RUN_INDEX_PAYLOAD=$(ARTIFACT_RUN_ID="$RUN_ARTIFACT_RUN_ID" RS_VERSION="$RUN_STATE_VERSION" BUILD_ID="$ACTIVE_BUILD_ID" ARTIFACTS_URL="\${RUN_ARTIFACTS_PUBLISHED:-}" REPO_DIR="$REPO_DIR" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
run_id = os.environ["ARTIFACT_RUN_ID"]
site_id = os.environ["SITE_ID"]
version_raw = os.environ.get("RS_VERSION") or ""
build_status = ""
try:
    with open(
        os.path.join(os.environ.get("REPO_DIR") or ".", "data", "runs", run_id, "build-result.json"),
        encoding="utf-8",
    ) as fh:
        _status = json.load(fh).get("status")
    if isinstance(_status, str):
        build_status = _status
except (OSError, ValueError):
    pass
entry = {
    "runId": run_id,
    "siteId": site_id,
    "version": int(version_raw) if version_raw.isdigit() else None,
    "buildId": os.environ.get("BUILD_ID") or "",
    "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
if build_status:
    entry["buildStatus"] = build_status
artifacts_url = os.environ.get("ARTIFACTS_URL") or ""
if artifacts_url:
    entry["runArtifactsUrl"] = artifacts_url
doc = json.dumps(entry, ensure_ascii=False)
commands = [["SET", "viewser:run:" + run_id, doc]]
if version_raw.isdigit():
    commands.append(["SET", "viewser:site:" + site_id + ":run:v" + version_raw, doc])
print(json.dumps(commands))
PY
)
    if [ -n "$KV_REST_URL" ] && [ -n "$KV_REST_TOKEN" ]; then
      curl -s -X POST "$KV_REST_URL/pipeline" \\
        -H "Authorization: Bearer $KV_REST_TOKEN" \\
        -H "Content-Type: application/json" \\
        -d "$RUN_INDEX_PAYLOAD" >/dev/null || true
    fi
    echo "hosted-build: run-index publicerat (B199 v2, runId $RUN_ARTIFACT_RUN_ID)."
  fi
else
  echo "hosted-build: VARNING — run-state-snapshot saknas pa disk; foljdprompter forblir oforandrade." >&2
fi

# Commit 3 (svars-paritet): bygg det rika resultatet fore done.
# engine=openclaw nar OpenClaw apply landade, annars legacy (arlig attribution).
# B199 v2 — init-paritet: aven initialbygget skriver result-blocket sa
# TS-svaret bar den KANONISKA build_site-runIden (samma id som den hostade
# run-historiken listar), inte orkestrerings-UUID:t. Init gar alltid den
# deterministiska vagen -> arligt engine=legacy.
if [ "$FOLLOWUP_MODE" = "1" ] && [ "$OPENCLAW_APPLIED" = "1" ]; then
  write_hosted_result "openclaw"
else
  write_hosted_result "legacy"
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

  // KV-preflight (review-fynd #284, fynd 1): hostat (VERCEL=1) MÅSTE en riktig
  // kv-store finnas FÖRE Sandbox.create. Utan Upstash-env får sandboxen tomma
  // KV_REST_URL/KV_REST_TOKEN, orkestrerings-skriptet hoppar ärligt över alla
  // status-POST:ar och klientens status-pollning hänger till timeout i stället
  // för att fela direkt. Lokalt (utan VERCEL=1) blockeras inget: memory-drivern
  // i samma process är fortfarande ett ärligt dev-läge.
  if (isHostedVercelRuntime() && !(upstashRestUrl() && upstashRestToken())) {
    return failRun(
      "Hostat bygge kräver kv-store (Upstash-integrationens KV_REST_API_URL/" +
        "KV_REST_API_TOKEN saknas) — utan den kan sandboxen aldrig rapportera " +
        "status eller publicera bygg-pekaren. Koppla Upstash-integrationen i " +
        "Vercel-projektet eller sätt VIEWSER_KV_REST_URL/VIEWSER_KV_REST_TOKEN.",
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

  // Run-state-preflight (B194): en hostad följdprompt kan bara härleda
  // föregående version ur det persisterade PI/meta-paret. Saknas pekaren har
  // sajten aldrig byggts hostat (eller byggdes före B194) — faila ärligt HÄR
  // i stället för att låta sandboxen starta och dö på samma sak dyrare.
  let runState: HostedRunStatePointer | null = null;
  if (req.followup) {
    runState = await kvGetJson<HostedRunStatePointer>(
      store,
      hostedRunStateKey(req.siteId),
    );
    const validRunState =
      runState &&
      typeof runState.projectInputUrl === "string" &&
      runState.projectInputUrl.startsWith("https://") &&
      typeof runState.metaUrl === "string" &&
      runState.metaUrl.startsWith("https://");
    if (!validRunState) {
      return failRun(
        `Hostad följdprompt kräver persisterad run-state för siteId "${req.siteId}" ` +
          "men KV-pekaren saknas eller är ogiltig. Kör först ett initialt hostat " +
          "bygge (run-state persisteras automatiskt efter varje lyckat bygge, B194).",
      );
    }
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

  // Livscykel/kostnad (paritet med lokala build-runner.ts): ett hostat
  // bygge/följdprompt stoppar en ev. aktiv preview-sandbox för samma siteId
  // så den inte serverar stale innehåll under/efter bygget (och kostar ören
  // tills TTL). Detta är den PRIMÄRA livscykelmekanismen; buildId-
  // invalideringen i tryReuseSandboxPreview (vercel-sandbox-runner.ts) är
  // backstoppen som fångar previews startade EFTER detta stopp men FÖRE
  // byggets pekar-swap. Best-effort: ett stopp-fel får ALDRIG falla bygget.
  try {
    await stopSandboxSessionForSite(req.siteId);
  } catch {
    // Idempotent best-effort — sessionsregistret kan vara tomt/otillgängligt.
  }

  // asset_set-forwarding (hostad halva av task A): samma sanering som den
  // lokala spawn-vägen. Ogiltigt/icke-asset_set-intent blir tom sträng —
  // skriptet skickar då ingen --tool-intent-flagga (ärlig prompt-only).
  const safeToolIntent =
    req.followup && req.toolIntent
      ? sanitizedAssetSetIntent(req.toolIntent)
      : null;

  // Commit 3 (request-paritet): baseRunId + markedSections. baseRunId är redan
  // Zod-validerad i /api/prompt men env quotar inte — re-validera mot run-id-
  // grammatiken (samma defense-in-depth som prompt-runner.ts). markedSections
  // saneras med SAMMA delade sanitizedMarkedSections som den lokala vägen.
  // Bara i followup-läge (init har ingen yta för dem).
  const safeBaseRunId =
    req.followup && req.baseRunId && /^[a-zA-Z0-9._-]+$/.test(req.baseRunId)
      ? req.baseRunId
      : "";
  const safeMarkedSections = req.followup
    ? sanitizedMarkedSections(req.markedSections)
    : [];

  // B199 v2 — historisk baseRunId: hydrera DEN versionens artefakter i
  // stället för pekarens senaste, via det durabla runId-indexet
  // (viewser:run:<runId>). siteId-bindningen stoppar artefakt-läckage över
  // sajtgränser via en stulen runId (samma princip som B196). Saknas
  // indexet (bygge före B199 v2) behålls pekarens senaste artefakter och
  // apply-sömmen degraderar exakt som förut — aldrig ett hårt fel.
  if (req.followup && runState && safeBaseRunId) {
    const baseEntry = await kvGetJson<HostedRunIndexEntry>(
      store,
      hostedRunIndexKey(safeBaseRunId),
    );
    if (
      baseEntry &&
      baseEntry.siteId === req.siteId &&
      typeof baseEntry.runId === "string" &&
      baseEntry.runId.length > 0 &&
      typeof baseEntry.runArtifactsUrl === "string" &&
      baseEntry.runArtifactsUrl.startsWith("https://")
    ) {
      runState = {
        ...runState,
        runId: baseEntry.runId,
        runArtifactsUrl: baseEntry.runArtifactsUrl,
      };
    }
  }

  const sandboxEnv: Record<string, string> = {
    RUN_ID: runId,
    SITE_ID: req.siteId,
    PROMPT_TEXT: req.prompt,
    FOLLOWUP_MODE: req.followup ? "1" : "0",
    TOOL_INTENT_JSON: safeToolIntent ? JSON.stringify(safeToolIntent) : "",
    // B194: run-state-paret för followup-härledning. Tomt vid initialbygge;
    // i followup-läge är pekaren redan preflight-validerad ovan.
    RUN_STATE_PI_URL: runState?.projectInputUrl ?? "",
    RUN_STATE_META_URL: runState?.metaUrl ?? "",
    // B199: kanoniska run-artefakter (data/runs/<runId>/) för followup-
    // hydrering. Tomma strängar vid initialbygge / äldre pekare utan
    // artefakt-tarball (set -u-säkert) — skriptet hoppar då ärligt över
    // hydreringen och apply-sömmen degraderar till legacy (som bara behöver
    // PI/meta). Sätts bara när followup-pekaren bär dem.
    RUN_ARTIFACTS_URL: runState?.runArtifactsUrl ?? "",
    RUN_ARTIFACTS_RUN_ID: runState?.runId ?? "",
    // Commit 3 (request-paritet): tomma strängar = ingen flagga (set -u-säkert).
    // BASE_RUN_ID → --base-run-id på BÅDE apply- och legacy-PI-anropet;
    // MARKED_SECTIONS_JSON → --marked-sections på legacy-PI-anropet.
    BASE_RUN_ID: safeBaseRunId,
    MARKED_SECTIONS_JSON: safeMarkedSections.length
      ? JSON.stringify(safeMarkedSections)
      : "",
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
