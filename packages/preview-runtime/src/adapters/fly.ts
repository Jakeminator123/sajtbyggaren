/**
 * FlyRuntime adapter — skelett.
 *
 * Roll (ADR 0028 §3): production-/deploy-check för sajter som kräver
 * riktig build (Stripe, DB, hard-Dossier-SDK:er) eller ska smoketestas
 * mot produktionslika krav. Ingen implementation finns idag — adaptern
 * är reserverad i `previewRuntimeKind`-typunionen för senare.
 *
 * ADR 0030 §"Vad ADR 0030 INTE beslutar" lämnar tidpunkten för faktisk
 * Fly-implementation öppen. En framtida ADR krävs innan kod skrivs;
 * preview-runtime-matrix-2026-05-25 listar 6 alternativ för B125-
 * fallback varav alternativ C ("VM next dev per kund") är besläktat.
 */

import type {
  PreviewRuntime,
  PreviewRuntimeConfig,
  PreviewResult,
} from "../types";

export const flyRuntime: PreviewRuntime = {
  kind: "fly",
  label: "FlyRuntime (production-like deploy-check, not implemented)",

  isAvailable() {
    return false;
  },

  async start(_config: PreviewRuntimeConfig): Promise<PreviewResult> {
    return {
      status: "unsupported",
      error:
        "FlyRuntime är reserverad i typunionen men har ingen implementation. " +
        "En framtida ADR krävs innan kod skrivs (se ADR 0030 §'Vad ADR 0030 " +
        "INTE beslutar' + preview-runtime-matrix-2026-05-25).",
    };
  },
};
