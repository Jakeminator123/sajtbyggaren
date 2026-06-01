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

interface vercelSandboxStartResult {
  status: "ready" | "failed";
  /** Publik preview-URL när `status === "ready"`. */
  url?: string;
  /** Hållbar handle för stop/cleanup (= sandbox-namnet). */
  sessionId?: string;
  /** Pedagogisk text när `status === "failed"`. */
  error?: string;
  logs?: string[];
}

interface vercelSandboxPreviewRuntimeHandlers {
  isAvailable?: () => boolean | Promise<boolean>;
  start: (config: PreviewRuntimeConfig) => Promise<vercelSandboxStartResult>;
  stop?: (sessionId: string) => Promise<void> | void;
}

interface previewRuntimeHandlers {
  local?: localPreviewRuntimeHandlers;
  stackblitz?: stackblitzPreviewRuntimeHandlers;
  vercelSandbox?: vercelSandboxPreviewRuntimeHandlers;
}

const runtimeHandlers: previewRuntimeHandlers = {};

export function configurePreviewRuntimeHandlers(handlers: previewRuntimeHandlers): void {
  if (handlers.local !== undefined) {
    runtimeHandlers.local = handlers.local;
  }
  if (handlers.stackblitz !== undefined) {
    runtimeHandlers.stackblitz = handlers.stackblitz;
  }
  if (handlers.vercelSandbox !== undefined) {
    runtimeHandlers.vercelSandbox = handlers.vercelSandbox;
  }
}

export function getPreviewRuntimeHandlers(): previewRuntimeHandlers {
  return runtimeHandlers;
}
