/**
 * VercelSandboxRuntime adapter.
 *
 * Roll (ADR 0033): primärt förstahandsval för användarnära preview. Kör en
 * redan-genererad Next.js-sajt i en isolerad Vercel Sandbox och returnerar en
 * publik preview-URL som fungerar i alla browsers. `local-next` är fallback,
 * `stackblitz` är pausad.
 *
 * Den konkreta `@vercel/sandbox`-körningen injiceras från app-lagret via
 * `configurePreviewRuntimeHandlers` (server-only runner i
 * `apps/viewser/lib/`). Adaptern äger bara mappningen till `PreviewResult` och
 * importerar aldrig `apps/viewser` eller `@vercel/sandbox` (paket→app-lager-
 * regel + ADR 0030: leverantörs-SDK läcker inte in i `packages/preview-runtime`).
 *
 * VercelSandboxRuntime är en implementerad adapter — den returnerar `ready`/
 * `failed`, aldrig `unsupported`. Saknad auth/handler degraderar ärligt till
 * `failed` med pedagogisk text (samma mönster som `local.ts:missingHandler`),
 * kraschar aldrig. Endast `fly` är reserverad stub.
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
      "VercelSandboxRuntime saknar injicerad handler. Anropa Viewser:s " +
      "`installViewserPreviewRuntimeHandlers()` " +
      "(apps/viewser/lib/preview-runtime-server.ts) innan adaptern används. " +
      "Detta är en konfigurationsmiss, inte en oimplementerad runtime.",
  };
}

function messageFromError(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Okänt fel vid Vercel Sandbox-preview.";
}

export const vercelSandboxRuntime: PreviewRuntime = {
  kind: "vercel-sandbox",
  label: "VercelSandboxRuntime (isolated Vercel Sandbox, public preview URL)",

  async isAvailable() {
    const handler = getPreviewRuntimeHandlers().vercelSandbox;
    if (!handler) return false;
    return handler.isAvailable ? await handler.isAvailable() : true;
  },

  async start(config: PreviewRuntimeConfig): Promise<PreviewResult> {
    const handler = getPreviewRuntimeHandlers().vercelSandbox;
    if (!handler) return missingHandler();
    if (!config.siteId) {
      return {
        status: "failed",
        error: "VercelSandboxRuntime kräver `siteId` för att starta en preview.",
      };
    }

    try {
      const info = await handler.start(config);
      if (info.status !== "ready" || !info.url) {
        return {
          status: "failed",
          error:
            info.error ??
            "Vercel Sandbox returnerade ingen URL (saknade auth eller bygget " +
              "misslyckades). Degraderar ärligt — använd `local-next` som fallback.",
          logs: info.logs,
        };
      }
      return {
        status: "ready",
        previewSession: {
          id: info.sessionId ?? config.siteId,
          url: info.url,
          kind: "vercel-sandbox",
          createdAt: new Date().toISOString(),
        },
        previewUrl: info.url,
        logs: info.logs,
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
    await getPreviewRuntimeHandlers().vercelSandbox?.stop?.(sessionId);
  },
};
