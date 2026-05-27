/**
 * LocalRuntime adapter — skelett.
 *
 * Roll (ADR 0028 §1): primär dev-preview för operator-bygda sajter,
 * samma maskin, http, fungerar i alla browsers. Faktisk implementation
 * lever idag i `apps/viewser/lib/local-preview-server.ts` (spawnar
 * `next start -p 41xx`). Bite B wirear denna adapter mot den befintliga
 * server-helpern utan att duplicera logik.
 */

import type {
  PreviewRuntime,
  PreviewRuntimeConfig,
  PreviewResult,
} from "../types";

export const localRuntime: PreviewRuntime = {
  kind: "local",
  label: "LocalRuntime (next start -p 41xx)",

  isAvailable() {
    return true;
  },

  async start(_config: PreviewRuntimeConfig): Promise<PreviewResult> {
    return {
      status: "unsupported",
      error:
        "LocalRuntime-adaptern är inte wirad än. Bite B kommer att delegera " +
        "till apps/viewser/lib/local-preview-server.ts. Sätt VIEWSER_PREVIEW_MODE=" +
        "local-next och använd det befintliga POST /api/preview/<siteId>-anropet " +
        "tills wiringen landar.",
    };
  },
};
