/**
 * LocalRuntime adapter.
 *
 * Roll (ADR 0028 §1): primär dev-preview för operator-bygda sajter,
 * samma maskin, http, fungerar i alla browsers. Den konkreta server-helpern
 * injiceras från app-lagret via `configurePreviewRuntimeHandlers`. Adaptern
 * äger bara mappningen till `PreviewResult` och importerar aldrig
 * `apps/viewser` (paket→app-lager-regel, ADR 0030 adapter-checklista).
 *
 * LocalRuntime är en implementerad adapter — den returnerar `ready`/
 * `starting`/`failed`, aldrig `unsupported`. Endast `fly` är reserverad stub.
 */

import { getPreviewRuntimeHandlers } from "../handlers";
import type {
  PreviewRuntime,
  PreviewRuntimeConfig,
  PreviewResult,
} from "../types";

function missingHandler(): PreviewResult {
  return {
    status: "failed",
    error:
      "LocalRuntime saknar injicerad handler. Anropa Viewser:s " +
      "`installViewserPreviewRuntimeHandlers()` " +
      "(apps/viewser/lib/preview-runtime-server.ts) innan adaptern används. " +
      "Detta är en konfigurationsmiss, inte en oimplementerad runtime.",
  };
}

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Okänt fel vid lokal preview.";
}

export const localRuntime: PreviewRuntime = {
  kind: "local",
  label: "LocalRuntime (next start -p 41xx)",

  async isAvailable() {
    const handler = getPreviewRuntimeHandlers().local;
    if (!handler) return false;
    return handler.isAvailable ? await handler.isAvailable() : true;
  },

  async start(config: PreviewRuntimeConfig): Promise<PreviewResult> {
    const handler = getPreviewRuntimeHandlers().local;
    if (!handler) return missingHandler();
    if (!config.siteId) {
      return {
        status: "failed",
        error: "LocalRuntime kräver `siteId` för att starta lokal preview.",
      };
    }

    try {
      const info = await handler.start(config);
      return {
        status: info.status,
        previewSession: {
          id: info.siteId,
          url: info.url,
          kind: "local",
          createdAt: new Date().toISOString(),
        },
        previewUrl: info.url,
        logs: [
          `LocalRuntime delegerade till lokal preview-server för ${info.siteId}.`,
        ],
      };
    } catch (error) {
      const message = messageFromError(error);
      return {
        status: "failed",
        error: message,
        logs: [message],
      };
    }
  },

  async stop(sessionId: string): Promise<void> {
    await getPreviewRuntimeHandlers().local?.stop?.(sessionId);
  },
};
