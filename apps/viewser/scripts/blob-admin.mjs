#!/usr/bin/env node
/**
 * blob-admin — operatör-CLI för att inspektera och städa den HOSTADE lagringen
 * (Vercel Blob + Upstash KV) per genererad sajt.
 *
 * Subkommandon (skriver ENDAST JSON till stdout; loggar går till stderr så
 * backoffice kan parsa stdout rakt av):
 *
 *   audit                 -> { totalObjects, totalBytes, byPrefix }
 *   list-sites            -> { count, sites: [{ siteId, totalObjects, totalBytes,
 *                              prefixes: { "generated/": {objects,bytes}, ... } }] }
 *   delete-site <siteId>  -> raderar ALLA blob-objekt under generated/<siteId>/,
 *                            run-artifacts/<siteId>/, run-state/<siteId>/ och
 *                            preview-bundles/<siteId>/ PLUS KV-nycklarna
 *                            viewser:site:<siteId>:* , viewser:run:<runId> (per
 *                            version) och viewser:sandbox-session:<siteId>.
 *                            -> { siteId, deletedBlobs, deletedBytes,
 *                                 kvKeysDeleted, kvKeys, kvError? }
 *
 * build-context/ rörs ALDRIG (det är Python-motorn, inte en sajt).
 *
 * Token-upplösning (samma mönster som upload-build-context-to-blob.mjs):
 * process.env vinner; annars repo-rotens .env; sist apps/viewser/.env.vercel.local.
 */

import { del, list } from "@vercel/blob";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Topp-prefix som är sajt-scopade som ``<prefix>/<siteId>/...``. */
const SITE_PREFIXES = ["generated/", "run-artifacts/", "run-state/", "preview-bundles/"];
const SITE_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;
const BLOB_DELETE_CHUNK = 100;

function repoRoot() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(scriptDir, "..", "..", "..");
}

function readEnvFileVar(envPath, name) {
  if (!existsSync(envPath)) return undefined;
  let text;
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

function resolveEnvVar(name) {
  const fromProcess = process.env[name]?.trim();
  if (fromProcess) return fromProcess;
  const root = repoRoot();
  const fromRootEnv = readEnvFileVar(path.join(root, ".env"), name)?.trim();
  if (fromRootEnv) return fromRootEnv;
  return readEnvFileVar(
    path.join(root, "apps", "viewser", ".env.vercel.local"),
    name,
  )?.trim();
}

function resolveKvRestUrl() {
  return (
    resolveEnvVar("VIEWSER_KV_REST_URL") ||
    resolveEnvVar("KV_REST_API_URL") ||
    resolveEnvVar("UPSTASH_REDIS_REST_URL")
  );
}

function resolveKvRestToken() {
  return (
    resolveEnvVar("VIEWSER_KV_REST_TOKEN") ||
    resolveEnvVar("KV_REST_API_TOKEN") ||
    resolveEnvVar("UPSTASH_REDIS_REST_TOKEN")
  );
}

async function kvCommand(command) {
  const url = resolveKvRestUrl();
  const token = resolveKvRestToken();
  if (!url || !token) throw new Error("KV-env saknas (KV_REST_API_URL/KV_REST_API_TOKEN).");
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(command),
  });
  if (!res.ok) throw new Error(`KV HTTP ${res.status}`);
  const payload = await res.json();
  if (payload && payload.error) throw new Error(`KV-fel: ${payload.error}`);
  return payload ? payload.result : null;
}

async function kvScan(match) {
  let cursor = "0";
  const keys = [];
  do {
    const res = await kvCommand(["SCAN", cursor, "MATCH", match, "COUNT", "200"]);
    cursor = String(res[0]);
    for (const key of res[1]) keys.push(key);
  } while (cursor !== "0");
  return keys;
}

async function listAllBlobs(token) {
  const blobs = [];
  let cursor;
  do {
    const res = await list({ token, limit: 1000, cursor });
    blobs.push(...res.blobs);
    cursor = res.cursor;
  } while (cursor);
  return blobs;
}

function classify(pathname) {
  const parts = pathname.split("/");
  const prefix = `${parts[0]}/`;
  if (SITE_PREFIXES.includes(prefix) && parts[1]) return { prefix, siteId: parts[1] };
  return { prefix, siteId: null };
}

function chunk(items, size) {
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

async function cmdAudit(token) {
  const blobs = await listAllBlobs(token);
  const byPrefix = {};
  let totalBytes = 0;
  for (const b of blobs) {
    const { prefix } = classify(b.pathname);
    const group = (byPrefix[prefix] ||= { objects: 0, bytes: 0 });
    group.objects += 1;
    group.bytes += b.size || 0;
    totalBytes += b.size || 0;
  }
  return { totalObjects: blobs.length, totalBytes, byPrefix };
}

async function cmdListSites(token) {
  const blobs = await listAllBlobs(token);
  const sites = {};
  for (const b of blobs) {
    const { prefix, siteId } = classify(b.pathname);
    if (!siteId) continue;
    const site = (sites[siteId] ||= {
      siteId,
      totalObjects: 0,
      totalBytes: 0,
      prefixes: {},
    });
    const p = (site.prefixes[prefix] ||= { objects: 0, bytes: 0 });
    p.objects += 1;
    p.bytes += b.size || 0;
    site.totalObjects += 1;
    site.totalBytes += b.size || 0;
  }
  const list = Object.values(sites).sort((a, b) => b.totalBytes - a.totalBytes);
  return { count: list.length, sites: list };
}

async function cmdDeleteSite(token, siteId) {
  if (!siteId || !SITE_ID_PATTERN.test(siteId)) {
    throw new Error(`Ogiltigt siteId: ${JSON.stringify(siteId)}`);
  }
  const blobs = await listAllBlobs(token);
  const targets = blobs.filter((b) => classify(b.pathname).siteId === siteId);
  const urls = targets.map((b) => b.url);
  const deletedBytes = targets.reduce((sum, b) => sum + (b.size || 0), 0);
  for (const part of chunk(urls, BLOB_DELETE_CHUNK)) {
    await del(part, { token });
  }

  let kvKeys = [];
  let kvError;
  try {
    const siteKeys = await kvScan(`viewser:site:${siteId}:*`);
    const runIds = new Set();
    for (const key of siteKeys) {
      if (!/:run:v\d+$/.test(key) && !key.endsWith(":run-state")) continue;
      const value = await kvCommand(["GET", key]);
      if (typeof value === "string" && value) {
        try {
          const doc = JSON.parse(value);
          if (doc && typeof doc.runId === "string" && doc.runId) runIds.add(doc.runId);
        } catch {
          // doc ej JSON — hoppa runId-indexet för den nyckeln
        }
      }
    }
    const toDelete = [
      ...siteKeys,
      `viewser:sandbox-session:${siteId}`,
      ...[...runIds].map((runId) => `viewser:run:${runId}`),
    ];
    if (toDelete.length > 0) {
      await kvCommand(["DEL", ...toDelete]);
      kvKeys = toDelete;
    }
  } catch (error) {
    kvError = error instanceof Error ? error.message : String(error);
  }

  return {
    siteId,
    deletedBlobs: urls.length,
    deletedBytes,
    kvKeysDeleted: kvKeys.length,
    kvKeys,
    ...(kvError ? { kvError } : {}),
  };
}

async function main() {
  const [command, arg] = process.argv.slice(2);
  const token = resolveEnvVar("BLOB_READ_WRITE_TOKEN");
  if (!token) {
    console.error("BLOB_READ_WRITE_TOKEN saknas (process.env / .env / .env.vercel.local).");
    process.exitCode = 2;
    return;
  }

  let result;
  if (command === "audit") {
    result = await cmdAudit(token);
  } else if (command === "list-sites") {
    result = await cmdListSites(token);
  } else if (command === "delete-site") {
    result = await cmdDeleteSite(token, arg);
  } else {
    console.error("Användning: blob-admin.mjs <audit|list-sites|delete-site <siteId>>");
    process.exitCode = 2;
    return;
  }
  console.log(JSON.stringify(result));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
