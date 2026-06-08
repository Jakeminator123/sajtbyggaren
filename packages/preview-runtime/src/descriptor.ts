/**
 * Preview Runtime — client-safe descriptor (Bite C unblock, 2026-06-08).
 *
 * The canonical `PreviewRuntimeKind` collapses `local-next` + `auto` + `local`
 * into `"local"`, which is LOSSY for the client's COEP / cross-origin-isolation
 * decision:
 *   - `local-next` → COEP off → a StackBlitz embed is INVALID (Chrome blocks it
 *     because WebContainer needs SharedArrayBuffer → cross-origin isolation).
 *   - `auto`       → COEP on  → a StackBlitz embed is a LEGITIMATE fallback.
 * So the client (viewer-panel) cannot drive that decision off `kind` alone — it
 * has to keep `auto` distinct from `local-next`. That is exactly why the client
 * reads the raw env value today; this descriptor lets it stop doing that.
 *
 * This is a PURE function with no `fs` / `child_process` / adapter / handler
 * import at module-eval, so it tree-shakes into a Next.js client bundle. Drive
 * it from `NEXT_PUBLIC_VIEWSER_PREVIEW_MODE` on the client (the server-only
 * `VIEWSER_PREVIEW_MODE` is not present in the browser runtime), e.g.
 * `resolvePreviewRuntimeDescriptor(process.env.NEXT_PUBLIC_VIEWSER_PREVIEW_MODE)`.
 *
 * The COEP table mirrors `apps/viewser/scripts/dev.mjs:HTTP_COEP_OFF_MODES`
 * (`local-next` + `vercel-sandbox` = http / COEP off) so the host transport and
 * this client descriptor agree on cross-origin isolation. A parity test locks
 * `descriptor.kind` against `registry.normalizePreviewMode` so the two mode
 * normalisers can never drift.
 */

import type { PreviewRuntimeKind } from "./types";

export interface PreviewRuntimeDescriptor {
  /** Canonical adapter kind (`auto`/`local-next`/`local` all collapse to `"local"`). */
  kind: PreviewRuntimeKind;
  /**
   * Normalised raw mode token (trimmed + lower-cased). KEEPS `auto` distinct
   * from `local-next` — the distinction `kind` drops but the COEP decision
   * depends on.
   */
  rawMode: string;
  /**
   * True when the host serves COEP/COOP headers (cross-origin isolation /
   * `SharedArrayBuffer` enabled). Only `stackblitz` + `auto` run COEP-on.
   */
  prefersCoep: boolean;
  /**
   * True when a StackBlitz/WebContainer embed is a legitimate fallback. Requires
   * COEP, so it tracks `prefersCoep` — a COEP-off mode (`local-next`/`local`/
   * `vercel-sandbox`/`fly`) can never validly fall back to a StackBlitz embed.
   */
  canFallbackToStackblitz: boolean;
}

/**
 * Canonical kind for a raw mode token. Intentionally mirrors
 * `registry.normalizePreviewMode`'s mapping but is inlined here (no adapter
 * import) to keep the descriptor client-safe; the parity test guards drift.
 */
function descriptorKind(rawMode: string): PreviewRuntimeKind {
  switch (rawMode) {
    case "stackblitz":
      return "stackblitz";
    case "vercel-sandbox":
      return "vercel-sandbox";
    case "fly":
      return "fly";
    // `local` + `local-next` + `auto` (+ empty/unknown) collapse to canonical `local`.
    default:
      return "local";
  }
}

/**
 * Resolve a raw preview-mode value into a client-safe descriptor that preserves
 * the COEP/fallback intent the lossy `PreviewRuntimeKind` drops. Empty/unknown
 * input is treated as the conservative `local` default (COEP off, no StackBlitz
 * fallback) so a misconfigured client never wrongly enables a StackBlitz embed.
 */
export function resolvePreviewRuntimeDescriptor(
  raw: string | undefined,
): PreviewRuntimeDescriptor {
  const rawMode = (raw ?? "").trim().toLowerCase() || "local";
  // COEP / cross-origin isolation is ON only for `stackblitz` + `auto`; that is
  // the single signal that makes a StackBlitz embed valid. `local-next`,
  // `local`, `vercel-sandbox` and `fly` run COEP-off, so a StackBlitz embed
  // there would be blocked by the browser.
  const prefersCoep = rawMode === "stackblitz" || rawMode === "auto";
  return {
    kind: descriptorKind(rawMode),
    rawMode,
    prefersCoep,
    canFallbackToStackblitz: prefersCoep,
  };
}
