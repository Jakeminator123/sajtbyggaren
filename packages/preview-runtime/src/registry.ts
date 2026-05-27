/**
 * Preview Runtime — registry/factory.
 *
 * En enda entry-point för att resolva en `PreviewRuntime`-adapter från
 * `PreviewRuntimeKind`-värde eller från `VIEWSER_PREVIEW_MODE`-env-var.
 * Konsumenter ska aldrig importera adaptrar direkt — gå alltid via
 * `resolveRuntime()` så adapter-tillägg/-byten kan göras på en plats.
 *
 * Env-mappning (bakåtkompatibel mot dev.mjs:VALID_MODES):
 *   - "local-next" → "local"      (canonical-kind per naming-dictionary v17)
 *   - "local"      → "local"
 *   - "stackblitz" → "stackblitz"
 *   - "fly"        → "fly"
 *   - "auto"       → "local"      (auto resolveras till local som default)
 *
 * Env-värdet `local-next` finns kvar i `apps/viewser/.env.example`,
 * `apps/viewser/scripts/dev.mjs:VALID_MODES` och
 * `apps/viewser/components/viewer-panel.tsx:IS_LOCAL_NEXT_MODE`. Vi byter
 * INTE namnet i Bite A — det är onödig churn. Adapter-typunionen är
 * canonical (`local`); env-värdet är input som normaliseras hit.
 */

import type { PreviewRuntime, PreviewRuntimeKind } from "./types";
import { flyRuntime, localRuntime, stackblitzRuntime } from "./adapters";

const ADAPTERS: Record<PreviewRuntimeKind, PreviewRuntime> = {
  local: localRuntime,
  stackblitz: stackblitzRuntime,
  fly: flyRuntime,
};

export function listRuntimes(): PreviewRuntime[] {
  return Object.values(ADAPTERS);
}

export function resolveRuntime(kind: PreviewRuntimeKind): PreviewRuntime {
  const runtime = ADAPTERS[kind];
  if (!runtime) {
    throw new Error(
      `Okänt PreviewRuntimeKind: '${kind}'. Giltiga: ${Object.keys(
        ADAPTERS,
      ).join(", ")}.`,
    );
  }
  return runtime;
}

/**
 * Normalisera ett raw env-värde till en `PreviewRuntimeKind`. Returnerar
 * `null` för okända värden — caller får bestämma fallback (default eller
 * pedagogiskt fel).
 */
export function normalizePreviewMode(raw: string | undefined): PreviewRuntimeKind | null {
  if (!raw) return null;
  const lower = raw.trim().toLowerCase();
  switch (lower) {
    case "local":
    case "local-next":
    case "auto":
      return "local";
    case "stackblitz":
      return "stackblitz";
    case "fly":
      return "fly";
    default:
      return null;
  }
}

/**
 * Hämta nuvarande `PreviewRuntimeKind` från `VIEWSER_PREVIEW_MODE`.
 *
 * Failure-modell:
 *   - Tomt eller osatt env → `"local"` (default per `apps/viewser/.env.example`).
 *   - Explicit men okänt värde (typo som `stackblitzz`) → kastar `Error` med
 *     vägledning. Tyst fallback till `local` skulle dölja misskonfiguration —
 *     adapter-abstraktionen ska göra preview-mode mer explicit, inte
 *     enklare att gissa fel på.
 *
 * Konsumenter som vill ha tyst fallback ska anropa `normalizePreviewMode()`
 * direkt och hantera `null`-utfallet själva.
 */
export function currentKind(env: NodeJS.ProcessEnv = process.env): PreviewRuntimeKind {
  const raw = env.VIEWSER_PREVIEW_MODE?.trim();
  if (!raw) {
    return "local";
  }
  const normalized = normalizePreviewMode(raw);
  if (normalized === null) {
    throw new Error(
      `Okänt VIEWSER_PREVIEW_MODE: '${raw}'. Giltiga värden: local, ` +
        `local-next, stackblitz, fly, auto. Kontrollera .env eller ` +
        `process.env.VIEWSER_PREVIEW_MODE.`,
    );
  }
  return normalized;
}

/**
 * Bekvämlighet: resolva nuvarande adapter i ett anrop.
 */
export function currentRuntime(env: NodeJS.ProcessEnv = process.env): PreviewRuntime {
  return resolveRuntime(currentKind(env));
}
