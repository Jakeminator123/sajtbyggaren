/**
 * spike_vercel_sandbox — körbara entries för Vercel-sandbox-spiken (PoC).
 *
 * INTE produktionskod. En tunn CLI runt
 * ``apps/viewser/lib/vercel-sandbox-spike.ts`` så operatören kan köra spiken
 * manuellt med tokens satta. Wirear sig INTE in i någon route.
 *
 * Kör (Node 22.18+/24 strippar TS-typer + auto-detekterar ESM, så ingen
 * flagga behövs på modern Node; ``--env-file`` laddar tokens):
 *
 *   # 1) skapa + servera (skriver ut url + sandboxId, auto-loggar i mätloggen)
 *   node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts create <siteId> [runId]
 *
 *   # 1b) lista byggbara siteId:n (om du inte anger någon)
 *   node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts create
 *
 *   # 2) städa upp (stoppar sandboxen)
 *   node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts cleanup <sandboxId>
 *
 * På äldre Node: lägg till ``--experimental-strip-types``. Tokens kan också
 * exporteras i shell:et istället för ``--env-file``. Flaggan
 * ``VIEWSER_SANDBOX_SPIKE=1`` måste vara satt (annars degraderar helpern).
 *
 * Vid lyckad ``create`` skrivs maskinvärdena (datum, siteId, totalMs,
 * installMs, buildMs, sandboxId) automatiskt in i mätlogg-tabellen i
 * ``docs/spikes/vercel-sandbox-spike.md`` — operatören behöver bara kryssa
 * desktop/mobil och klistra ``activeCpuMs`` från cleanup-svaret.
 *
 * ``@vercel/sandbox`` resolveras från ``apps/viewser/node_modules`` eftersom
 * helpern bor där — kör därför ``cd apps/viewser && npm install`` först.
 */

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  createSandboxPreview,
  listGeneratedSiteIds,
  stopSandboxPreview,
  type SandboxPreviewResult,
} from "../apps/viewser/lib/vercel-sandbox-spike.ts";

/** Unik ankarrad i mätlogg-tabellen (9 kolumner) att infoga rader efter. */
const MEASUREMENT_SEPARATOR =
  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |";

/** Sökväg till spike-doc:en, härledd från scriptets plats (cwd-oberoende). */
function measurementDocPath(): string {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const repoRoot = path.resolve(scriptDir, "..");
  return path.join(repoRoot, "docs", "spikes", "vercel-sandbox-spike.md");
}

/**
 * Infoga en förifylld mätlogg-rad (datum, siteId, timings, sandboxId) direkt
 * efter tabell-separatorn. Icke-kastande: om doc:en eller tabellen saknas
 * hoppas skrivningen över med en notis — aldrig en krasch.
 */
function appendMeasurementRow(
  siteId: string,
  result: SandboxPreviewResult,
): void {
  const docPath = measurementDocPath();
  let text: string;
  try {
    text = readFileSync(docPath, "utf-8");
  } catch {
    process.stderr.write("  (kunde inte läsa mätlogg-doc; hoppar auto-skrivning)\n");
    return;
  }
  const sepIdx = text.indexOf(MEASUREMENT_SEPARATOR);
  if (sepIdx < 0) {
    process.stderr.write("  (mätlogg-tabellen hittades inte; hoppar auto-skrivning)\n");
    return;
  }
  const insertAt = text.indexOf("\n", sepIdx);
  if (insertAt < 0) return;
  const date = new Date().toISOString().slice(0, 16).replace("T", " ");
  const t = result.timings ?? {};
  const cell = (v: number | undefined) => (typeof v === "number" ? String(v) : "");
  const row =
    `\n| ${date} | ${siteId} | ${cell(t.totalMs)} | ${cell(t.installMs)} | ` +
    `${cell(t.buildMs)} |  |  |  | sandboxId=${result.sandboxId ?? "?"} |`;
  try {
    writeFileSync(docPath, text.slice(0, insertAt) + row + text.slice(insertAt), "utf-8");
    process.stderr.write(
      `  Mätlogg-rad tillagd i docs/spikes/vercel-sandbox-spike.md ` +
        "(kryssa desktop/mobil + klistra activeCpuMs efter cleanup).\n",
    );
  } catch {
    process.stderr.write("  (kunde inte skriva mätlogg-doc; hoppar auto-skrivning)\n");
  }
}

function printUsage(): void {
  process.stderr.write(
    [
      "Användning:",
      "  node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts create <siteId> [runId]",
      "  node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts cleanup <sandboxId>",
      "",
      "Kräver VIEWSER_SANDBOX_SPIKE=1 + Vercel-credentials (OIDC eller",
      "VERCEL_TOKEN/VERCEL_TEAM_ID/VERCEL_PROJECT_ID).",
      "",
    ].join("\n"),
  );
}

async function runCreate(siteId: string, runId?: string): Promise<number> {
  const result = await createSandboxPreview({ siteId, runId });
  for (const line of result.logs ?? []) {
    process.stderr.write(`  ${line}\n`);
  }
  process.stdout.write(
    JSON.stringify(
      {
        status: result.status,
        url: result.url,
        sandboxId: result.sandboxId,
        ttlMs: result.ttlMs,
        timings: result.timings,
        cost: result.cost,
        error: result.error,
      },
      null,
      2,
    ) + "\n",
  );
  if (result.status === "ready") {
    appendMeasurementRow(siteId, result);
    process.stderr.write(
      `\nÖppna URL:en ovan i mobil/desktop. Städa när du är klar:\n` +
        `  node --env-file apps/viewser/.env.local ` +
        `scripts/spike_vercel_sandbox.ts cleanup ${result.sandboxId}\n`,
    );
    return 0;
  }
  return 1;
}

async function runCleanup(sandboxId: string): Promise<number> {
  const result = await stopSandboxPreview(sandboxId);
  for (const line of result.logs ?? []) {
    process.stderr.write(`  ${line}\n`);
  }
  process.stdout.write(
    JSON.stringify(
      {
        status: result.status,
        sandboxId: result.sandboxId,
        cost: result.cost,
        error: result.error,
      },
      null,
      2,
    ) + "\n",
  );
  if (result.status === "stopped" && typeof result.cost?.activeCpuMs === "number") {
    process.stderr.write(
      `\nKlistra activeCpuMs=${result.cost.activeCpuMs} i mätloggens rad ` +
        `(Kommentar: sandboxId=${sandboxId}) i docs/spikes/vercel-sandbox-spike.md.\n`,
    );
  }
  return result.status === "stopped" ? 0 : 1;
}

async function main(): Promise<number> {
  const [command, arg1, arg2] = process.argv.slice(2);

  if (command === "create") {
    if (!arg1) {
      const ids = listGeneratedSiteIds();
      if (ids.length === 0) {
        process.stderr.write(
          "Inga byggda sajter hittades under generated-roten. " +
            "Kör build_site.py först (eller sätt SAJTBYGGAREN_GENERATED_DIR).\n",
        );
      } else {
        process.stderr.write(
          "Ange ett siteId. Tillgängliga byggbara sajter:\n",
        );
        for (const id of ids) process.stderr.write(`  ${id}\n`);
        process.stderr.write(
          "\nKör sedan:\n  node --env-file apps/viewser/.env.local " +
            "scripts/spike_vercel_sandbox.ts create <siteId>\n",
        );
      }
      return 2;
    }
    return runCreate(arg1, arg2);
  }

  if (command === "cleanup") {
    if (!arg1) {
      printUsage();
      return 2;
    }
    return runCleanup(arg1);
  }

  printUsage();
  return 2;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    process.stderr.write(
      `Oväntat fel: ${error instanceof Error ? error.message : String(error)}\n`,
    );
    process.exitCode = 1;
  });
