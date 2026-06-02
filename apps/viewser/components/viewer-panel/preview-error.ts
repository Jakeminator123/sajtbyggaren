/**
 * Preview-fel-mappning för ViewerPanel.
 *
 * Bröts ut ur ``viewer-panel.tsx`` (Bite C) för att hålla huvudkomponenten
 * under radspärren och samla all översättning ``PreviewErrorBody`` →
 * operatörsvänlig ``UnavailableInfo`` på ett ställe. Logiken är oförändrad;
 * Bite C lade till koderna ``runtime_misconfigured``, ``unsupported`` och
 * ``no_preview_url`` samt vidarebefordran av runtime-``logs``.
 */

/**
 * Strukturerad info-shape som banner-renderaren visar istället för en
 * hårdkodad sträng. Tillåter att olika misslyckanden (sajten inte byggd,
 * port-pool full, runtime felkonfigurerad, etc.) får specifik copy med
 * titel, beskrivning, hint och valfria startup-loggar.
 */
export type UnavailableInfo = {
  title?: string;
  message: string;
  hint?: string;
  /** Strukturerade startup-loggar från runtimen (visas vid failed). */
  logs?: string[];
};

/**
 * Felshape som ``/api/preview/<siteId>`` returnerar (4xx/5xx). Synkad mot
 * ``apps/viewser/app/api/preview/[siteId]/route.ts:PreviewErrorBody``. Vi
 * kopierar typen istället för att importera den eftersom ViewerPanel kör i
 * klienten och en import från en server-route-fil skulle dra in onödiga
 * server-bara beroenden.
 */
export type PreviewApiError = {
  error: string;
  code?:
    | "validation_error"
    | "not_built"
    | "missing_artifacts"
    | "port_pool_full"
    | "spawn_failed"
    | "not_running"
    | "unsupported"
    | "runtime_misconfigured"
    | "no_preview_url"
    | "unknown";
  hint?: string;
  logs?: string[];
};

export function unavailableForPreviewError(
  payload: PreviewApiError | null,
): UnavailableInfo {
  const code = payload?.code ?? "unknown";
  const errMsg = payload?.error;
  const errHint = payload?.hint;
  const logs = payload?.logs;
  if (code === "not_built" || code === "missing_artifacts") {
    return {
      title: "Sajten är inte byggd än",
      message:
        errMsg ??
        "Lokal preview-server kunde inte starta — den genererade sajten finns inte på disk.",
      hint:
        errHint ?? "Kör python scripts/build_site.py för att bygga sajten först.",
      logs,
    };
  }
  if (code === "port_pool_full") {
    return {
      title: "Inga lediga preview-portar",
      message: errMsg ?? "Port-poolen 4100-4199 är full.",
      hint:
        errHint ??
        "Stäng några äldre preview-servrar via DELETE /api/preview/<siteId>.",
      logs,
    };
  }
  if (code === "spawn_failed") {
    return {
      title: "Lokal preview-server kraschade",
      message: errMsg ?? "next start startade inte korrekt.",
      hint: errHint ?? "Kontrollera viewser-loggen för stderr-tail från next start.",
      logs,
    };
  }
  if (code === "runtime_misconfigured") {
    return {
      title: "Preview-runtime felkonfigurerad",
      message: errMsg ?? "VIEWSER_PREVIEW_MODE är satt till ett okänt värde.",
      hint: errHint ?? "Kontrollera VIEWSER_PREVIEW_MODE i apps/viewser/.env.local.",
      logs,
    };
  }
  if (code === "unsupported") {
    return {
      title: "Runtime stödjer inte preview",
      message:
        errMsg ?? "Den valda preview-runtimen kan inte rendera den här sajten.",
      hint: errHint ?? "Byt VIEWSER_PREVIEW_MODE till local-next för lokal preview.",
      logs,
    };
  }
  if (code === "no_preview_url") {
    return {
      title: "Preview saknar URL",
      message:
        errMsg ??
        "Runtimen rapporterade klar preview men utan en URL att rendera.",
      hint: errHint,
      logs,
    };
  }
  return {
    title: "Preview kunde inte starta",
    message: errMsg ?? "Okänt fel från /api/preview/<siteId>.",
    hint: errHint,
    logs,
  };
}
