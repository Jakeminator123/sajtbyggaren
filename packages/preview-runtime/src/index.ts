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
} from "./types";

export {
  currentKind,
  currentRuntime,
  listRuntimes,
  normalizePreviewMode,
  resolveRuntime,
} from "./registry";
