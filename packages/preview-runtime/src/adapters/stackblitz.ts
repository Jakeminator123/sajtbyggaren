/**
 * StackBlitzRuntime adapter — skelett.
 *
 * Roll (ADR 0028 §2): användarnära browser/WebContainer-fallback när
 * delbar preview behövs. Faktisk filspayload byggs idag av
 * `apps/viewser/lib/stackblitz-files.ts` och embeddas via @stackblitz/sdk
 * i `apps/viewser/components/viewer-panel.tsx`. Embedded WebContainer
 * fungerar bara i Chromium-browsers (B125 — Safari/Firefox-fallback är
 * parkerad, se ADR 0025 + matrix-rapport 2026-05-25).
 *
 * Bite B wirear denna adapter mot stackblitz-files.ts utan att duplicera
 * logik. Browser-detection (`getBrowserKind` + `supportsStackBlitzEmbed`)
 * stannar i UI-lagret eftersom den behöver `navigator`.
 */

import type {
  PreviewRuntime,
  PreviewRuntimeConfig,
  PreviewResult,
} from "../types";

export const stackblitzRuntime: PreviewRuntime = {
  kind: "stackblitz",
  label: "StackBlitzRuntime (@stackblitz/sdk + WebContainer)",

  isAvailable() {
    return true;
  },

  async start(_config: PreviewRuntimeConfig): Promise<PreviewResult> {
    return {
      status: "unsupported",
      error:
        "StackBlitzRuntime-adaptern är inte wirad än. Bite B kommer att " +
        "delegera till apps/viewser/lib/stackblitz-files.ts + sdk-embed. Sätt " +
        "VIEWSER_PREVIEW_MODE=stackblitz och använd den befintliga UI-flödet " +
        "tills wiringen landar.",
    };
  },
};
