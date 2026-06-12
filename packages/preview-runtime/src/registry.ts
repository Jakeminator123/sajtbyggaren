/**
 * Preview Runtime — registry/factory.
 *
 * En enda entry-point för att resolva en `PreviewRuntime`-adapter från
 * `PreviewRuntimeKind`-värde eller från `VIEWSER_PREVIEW_MODE`-env-var.
 * Konsumenter ska aldrig importera adaptrar direkt — gå alltid via
 * `resolveRuntime()` så adapter-tillägg/-byten kan göras på en plats.
 *
 * Env-mappning (bakåtkompatibel mot dev.mjs:VALID_MODES):
 *   - "local-next"     → "local"          (canonical-kind per naming-dictionary)
 *   - "local"          → "local"
 *   - "stackblitz"     → "stackblitz"
 *   - "vercel-sandbox" → "vercel-sandbox" (default + primärt, ADR 0033)
 *   - "fly"            → "fly"
 *   - "auto"           → "local"          (auto är fortsatt local-familjens token)
 *
 * Default-flippen (operatörsbeslut 2026-06-12): TOMT/osatt env resolvas till
 * `vercel-sandbox` — den primära runtimen per ADR 0033 är nu också faktisk
 * default. Ett EXPLICIT `local-next`/`local`/`auto` ger fortfarande `local`
 * (utvecklarmaskinens snabba väg; Jakobs `.env.local` sätter local-next).
 *
 * Env-värdet `local-next` finns kvar i `apps/viewser/.env.example`,
 * `apps/viewser/scripts/dev.mjs:VALID_MODES` och
 * `apps/viewser/components/viewer-panel.tsx:IS_LOCAL_NEXT_MODE`. Vi byter
 * INTE namnet — det är onödig churn. Adapter-typunionen är canonical
 * (`local`); env-värdet är input som normaliseras hit.
 */

import type { PreviewRuntime, PreviewRuntimeKind } from "./types";
import {
  flyRuntime,
  localRuntime,
  stackblitzRuntime,
  vercelSandboxRuntime,
} from "./adapters";

const ADAPTERS: Record<PreviewRuntimeKind, PreviewRuntime> = {
  "vercel-sandbox": vercelSandboxRuntime,
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
    case "vercel-sandbox":
      return "vercel-sandbox";
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
 *   - Tomt eller osatt env → `"vercel-sandbox"` (default-flippen, operatörs-
 *     beslut 2026-06-12: den primära runtimen per ADR 0033 är nu faktisk
 *     default; `preview-runtime-policy.v1.json:default` speglar samma värde).
 *     Lokal dev väljer `local-next` EXPLICIT via `.env.local` (mallen
 *     `apps/viewser/.env.example` sätter den raden åt utvecklaren).
 *   - Explicit men okänt värde (typo som `stackblitzz`) → kastar `Error` med
 *     vägledning. Tyst fallback skulle dölja misskonfiguration —
 *     adapter-abstraktionen ska göra preview-mode mer explicit, inte
 *     enklare att gissa fel på.
 *
 * Konsumenter som vill ha tyst fallback ska anropa `normalizePreviewMode()`
 * direkt och hantera `null`-utfallet själva.
 */
export function currentKind(env: NodeJS.ProcessEnv = process.env): PreviewRuntimeKind {
  const raw = env.VIEWSER_PREVIEW_MODE?.trim();
  if (!raw) {
    return "vercel-sandbox";
  }
  const normalized = normalizePreviewMode(raw);
  if (normalized === null) {
    throw new Error(
      `Okänt VIEWSER_PREVIEW_MODE: '${raw}'. Giltiga värden: local, ` +
        `local-next, stackblitz, vercel-sandbox, fly, auto. Kontrollera .env ` +
        `eller process.env.VIEWSER_PREVIEW_MODE.`,
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
