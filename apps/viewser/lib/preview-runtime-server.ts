import {
  configurePreviewRuntimeHandlers,
  type PreviewFile,
  type PreviewRuntimeConfig,
} from "@preview-runtime";

import { startPreviewServer, stopPreviewServer } from "./local-preview-server";
import { readRunFilesForStackblitz } from "./stackblitz-files";

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

export function installViewserPreviewRuntimeHandlers(): void {
  configurePreviewRuntimeHandlers({
    local: {
      start: (config) => startPreviewServer(requireSiteId(config)),
      stop: async (sessionId) => {
        stopPreviewServer(sessionId);
      },
    },
    stackblitz: {
      readFiles: async (config) =>
        filesFromConfig(config) ?? readRunFilesForStackblitz(requireRunId(config)),
    },
  });
}
