import type { PreviewFile, PreviewRuntimeConfig } from "./types";

interface localPreviewStartResult {
  siteId: string;
  url: string;
  status: "starting" | "ready";
  port?: number;
  uptimeMs?: number;
}

interface localPreviewRuntimeHandlers {
  isAvailable?: () => boolean | Promise<boolean>;
  start: (config: PreviewRuntimeConfig) => Promise<localPreviewStartResult>;
  stop?: (sessionId: string) => Promise<void> | void;
}

type stackblitzFilePayload = PreviewFile[] | Record<string, string>;

interface stackblitzPreviewRuntimeHandlers {
  isAvailable?: () => boolean | Promise<boolean>;
  readFiles: (config: PreviewRuntimeConfig) => Promise<stackblitzFilePayload>;
}

interface previewRuntimeHandlers {
  local?: localPreviewRuntimeHandlers;
  stackblitz?: stackblitzPreviewRuntimeHandlers;
}

const runtimeHandlers: previewRuntimeHandlers = {};

export function configurePreviewRuntimeHandlers(handlers: previewRuntimeHandlers): void {
  if (handlers.local !== undefined) {
    runtimeHandlers.local = handlers.local;
  }
  if (handlers.stackblitz !== undefined) {
    runtimeHandlers.stackblitz = handlers.stackblitz;
  }
}

export function getPreviewRuntimeHandlers(): previewRuntimeHandlers {
  return runtimeHandlers;
}
