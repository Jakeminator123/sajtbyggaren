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
 *   # 1) skapa + servera (skriver ut url + sandboxId)
 *   node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts create <siteId> [runId]
 *
 *   # 2) städa upp (stoppar sandboxen)
 *   node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts cleanup <sandboxId>
 *
 * På äldre Node: lägg till ``--experimental-strip-types``. Tokens kan också
 * exporteras i shell:et istället för ``--env-file``. Flaggan
 * ``VIEWSER_SANDBOX_SPIKE=1`` måste vara satt (annars degraderar helpern).
 *
 * ``@vercel/sandbox`` resolveras från ``apps/viewser/node_modules`` eftersom
 * helpern bor där — kör därför ``cd apps/viewser && npm install`` först.
 */

import {
  createSandboxPreview,
  stopSandboxPreview,
} from "../apps/viewser/lib/vercel-sandbox-spike.ts";

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
  return result.status === "stopped" ? 0 : 1;
}

async function main(): Promise<number> {
  const [command, arg1, arg2] = process.argv.slice(2);

  if (command === "create") {
    if (!arg1) {
      printUsage();
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
