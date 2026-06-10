/**
 * Preview Runtime — public API.
 *
 * Konsumenter (apps/viewser, framtida deploy-check, framtida CLI) ska
 * importera härifrån — aldrig från `./adapters/*` direkt. Det håller
 * registry:n som enda växel mellan adapter-implementationer.
 */

export type {
  PreviewFile,
  PreviewResult,
  PreviewRuntime,
  PreviewRuntimeConfig,
  PreviewRuntimeKind,
  PreviewSession,
  PreviewTimings,
} from "./types";

export {
  currentKind,
  currentRuntime,
  listRuntimes,
  normalizePreviewMode,
  resolveRuntime,
} from "./registry";

export type { PreviewRuntimeDescriptor } from "./descriptor";
export { resolvePreviewRuntimeDescriptor } from "./descriptor";

export { configurePreviewRuntimeHandlers } from "./handlers";
