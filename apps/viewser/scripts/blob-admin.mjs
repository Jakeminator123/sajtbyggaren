#!/usr/bin/env node
/**
 * blob-admin — operatör-CLI för att inspektera och städa den HOSTADE lagringen
 * (Vercel Blob + Upstash KV) per genererad sajt.
 *
 * All raderings-/listnings-/prune-logik bor i den DELADE modulen
 * ``apps/viewser/lib/blob-prune.mjs`` så att cron-routen
 * (``app/api/cron/prune-blob/route.ts``) och det här CLI:t använder EXAKT
 * samma kod (ingen duplicering). build-context/ rörs ALDRIG.
 *
 * Subkommandon (skriver ENDAST JSON till stdout; loggar går till stderr så
 * backoffice kan parsa stdout rakt av):
 *
 *   audit                 -> { totalObjects, totalBytes, byPrefix }
 *   list-sites            -> { count, sites: [{ siteId, totalObjects, totalBytes,
 *                              prefixes: { "generated/": {objects,bytes}, ... },
 *                              newestUploadedAt }] }
 *   delete-site <siteId>  -> raderar ALLA blob-objekt under generated/<siteId>/,
 *                            run-artifacts/<siteId>/, run-state/<siteId>/ och
 *                            preview-bundles/<siteId>/ PLUS KV-nycklarna
 *                            viewser:site:<siteId>:* , viewser:run:<runId> (per
 *                            version) och viewser:sandbox-session:<siteId>.
 *                            -> { siteId, deletedBlobs, deletedBytes,
 *                                 kvKeysDeleted, kvKeys, kvError? }
 *   prune [--apply] [--retention-days N]
 *                         -> auto-prune av sajter äldre än retention (default
 *                            14 dagar, eller env RETENTION_DAYS). DRY-RUN som
 *                            standard; --apply raderar på riktigt. Samma
 *                            staleness-/raderingslogik som cron-routen.
 *                            -> { dryRun, retentionDays, prunedSites, keptSites,
 *                                 freedBytes, deleted, ... }
 */

import {
  auditBlobs,
  deleteSite,
  DEFAULT_RETENTION_DAYS,
  listSites,
  pruneBlob,
  resolveEnvVar,
  resolveRetentionDays,
} from "../lib/blob-prune.mjs";

function parsePruneFlags(args) {
  let apply = false;
  let retentionDays = resolveRetentionDays(resolveEnvVar("RETENTION_DAYS"));
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--apply") {
      apply = true;
    } else if (arg === "--retention-days") {
      retentionDays = resolveRetentionDays(args[++i]);
    } else if (arg.startsWith("--retention-days=")) {
      retentionDays = resolveRetentionDays(arg.split("=", 2)[1]);
    }
  }
  return { apply, retentionDays };
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  const token = resolveEnvVar("BLOB_READ_WRITE_TOKEN");
  if (!token) {
    console.error(
      "BLOB_READ_WRITE_TOKEN saknas (process.env / .env / .env.vercel.local).",
    );
    process.exitCode = 2;
    return;
  }

  let result;
  if (command === "audit") {
    result = await auditBlobs(token);
  } else if (command === "list-sites") {
    result = await listSites(token);
  } else if (command === "delete-site") {
    result = await deleteSite(token, rest[0]);
  } else if (command === "prune") {
    const { apply, retentionDays } = parsePruneFlags(rest);
    result = await pruneBlob({ token, retentionDays, dryRun: !apply });
  } else {
    console.error(
      "Användning: blob-admin.mjs <audit|list-sites|delete-site <siteId>|" +
        `prune [--apply] [--retention-days N (default ${DEFAULT_RETENTION_DAYS})]>`,
    );
    process.exitCode = 2;
    return;
  }
  console.log(JSON.stringify(result));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
