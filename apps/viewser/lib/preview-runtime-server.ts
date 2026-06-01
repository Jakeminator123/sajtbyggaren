import {
  configurePreviewRuntimeHandlers,
  currentRuntime,
  resolveRuntime,
  type PreviewFile,
  type PreviewRuntime,
  type PreviewRuntimeConfig,
  type PreviewRuntimeKind,
} from "@preview-runtime";

import { startPreviewServer, stopPreviewServer } from "./local-preview-server";
import { readRunFilesForStackblitz } from "./stackblitz-files";

/**
 * Server-side DI-wiring för Preview Runtime.
 *
 * `packages/preview-runtime` är app-agnostiskt och importerar aldrig
 * `apps/viewser` (paket→app-lager-regel, ADR 0030). Den konkreta kopplingen
 * sker här i app-lagret: Viewser injicerar sina existerande server-helpers
 * (`startPreviewServer`/`stopPreviewServer` + `readRunFilesForStackblitz`)
 * IN i adaptrarna via `configurePreviewRuntimeHandlers`.
 *
 * Använd `currentViewserRuntime()` / `resolveViewserRuntime()` som enda
 * entry-point från app-lagret — de garanterar att handlers är installerade
 * innan adaptern resolvas, så `localRuntime`/`stackblitzRuntime` aldrig
 * faller tillbaka på sina "saknar handler"-grenar.
 */

function requireSiteId(config: PreviewRuntimeConfig): string {
  if (!config.siteId) {
    throw new Error("LocalRuntime kräver siteId.");
  }
  return config.siteId;
}

function requireRunId(config: PreviewRuntimeConfig): string {
  if (!config.runId) {
    throw new Error("StackBlitzRuntime kräver runId.");
  }
  return config.runId;
}

function filesFromConfig(config: PreviewRuntimeConfig): PreviewFile[] | undefined {
  return config.files?.map((file) => ({ path: file.path, content: file.content }));
}

let handlersInstalled = false;

export function installViewserPreviewRuntimeHandlers(): void {
  configurePreviewRuntimeHandlers({
    local: {
      // LocalRuntime körs alltid på samma Node-host som Viewser, så
      // adaptern är tillgänglig så snart wiringen är installerad.
      isAvailable: () => true,
      start: (config) => startPreviewServer(requireSiteId(config)),
      stop: async (sessionId) => {
        stopPreviewServer(sessionId);
      },
    },
    stackblitz: {
      // Filpayload-bygget är server-side och alltid möjligt när wiringen
      // finns. Browser-/Chromium-gatingen för själva SDK-embedet ligger
      // kvar i UI-lagret (B125), inte i adaptern.
      isAvailable: () => true,
      readFiles: async (config) =>
        filesFromConfig(config) ?? readRunFilesForStackblitz(requireRunId(config)),
    },
  });
  handlersInstalled = true;
}

/**
 * Idempotent: installera Viewser-handlers exakt en gång per process. Säker
 * att anropa på varje request — sätter bara om handlers inte redan är aktiva.
 */
export function ensureViewserPreviewRuntimeHandlers(): void {
  if (!handlersInstalled) {
    installViewserPreviewRuntimeHandlers();
  }
}

/**
 * Resolva den env-styrda adaptern (`VIEWSER_PREVIEW_MODE`) med Viewser-
 * handlers garanterat installerade. Detta är app-lagrets enda entry-point
 * för "vilken Preview Runtime gäller just nu?".
 */
export function currentViewserRuntime(
  env: NodeJS.ProcessEnv = process.env,
): PreviewRuntime {
  ensureViewserPreviewRuntimeHandlers();
  return currentRuntime(env);
}

/**
 * Resolva en specifik adapter via `PreviewRuntimeKind` med Viewser-handlers
 * garanterat installerade.
 */
export function resolveViewserRuntime(kind: PreviewRuntimeKind): PreviewRuntime {
  ensureViewserPreviewRuntimeHandlers();
  return resolveRuntime(kind);
}
