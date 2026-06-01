/**
 * StackBlitzRuntime adapter.
 *
 * Roll (ADR 0028 §2): användarnära browser/WebContainer-fallback när
 * delbar preview behövs. Faktisk filspayload byggs idag av
 * `apps/viewser/lib/stackblitz-files.ts` och embeddas via @stackblitz/sdk
 * i `apps/viewser/components/viewer-panel.tsx`. Embedded WebContainer
 * fungerar bara i Chromium-browsers (B125 — Safari/Firefox-fallback är
 * parkerad, se ADR 0025 + matrix-rapport 2026-05-25).
 *
 * Filpayload byggs av injicerad app-logik. Browser-detection
 * (`getBrowserKind` + `supportsStackBlitzEmbed`) och SDK-embed stannar i
 * UI-lagret eftersom de behöver browser APIs.
 */

import { getPreviewRuntimeHandlers } from "../handlers";
import type {
  PreviewFile,
  PreviewRuntime,
  PreviewRuntimeConfig,
  PreviewResult,
} from "../types";

function filesFromPayload(payload: PreviewFile[] | Record<string, string>): PreviewFile[] {
  if (Array.isArray(payload)) return payload;
  return Object.entries(payload)
    .map(([path, content]) => ({ path, content }))
    .sort((left, right) => left.path.localeCompare(right.path));
}

function sessionId(config: PreviewRuntimeConfig): string {
  return config.runId ?? config.projectName ?? "stackblitz-preview";
}

function messageFromError(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Okänt fel vid StackBlitz-filpayload.";
}

export const stackblitzRuntime: PreviewRuntime = {
  kind: "stackblitz",
  label: "StackBlitzRuntime (@stackblitz/sdk + WebContainer)",

  async isAvailable() {
    const handler = getPreviewRuntimeHandlers().stackblitz;
    if (!handler) return false;
    return handler.isAvailable ? await handler.isAvailable() : true;
  },

  async start(config: PreviewRuntimeConfig): Promise<PreviewResult> {
    const handler = getPreviewRuntimeHandlers().stackblitz;
    if (!handler) {
      return {
        status: "unsupported",
        error:
          "StackBlitzRuntime saknar injicerad handler. UI-embedet ligger kvar " +
          "utanför preview-runtime-paketet.",
      };
    }
    if (!config.runId && !config.files) {
      return {
        status: "failed",
        error: "StackBlitzRuntime kräver `runId` eller `files` för att bygga payload.",
      };
    }

    try {
      const files = filesFromPayload(await handler.readFiles(config));
      return {
        status: "ready",
        previewSession: {
          id: sessionId(config),
          url: "about:blank",
          kind: "stackblitz",
          createdAt: new Date().toISOString(),
        },
        files,
        logs: [`StackBlitzRuntime byggde ${files.length} preview-filer via DI.`],
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
};
