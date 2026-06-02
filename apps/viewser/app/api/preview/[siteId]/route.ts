import { NextRequest, NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";
import { getPreviewServer, stopPreviewServer } from "@/lib/local-preview-server";
import { currentViewserRuntime } from "@/lib/preview-runtime-server";

import type { PreviewResult } from "@preview-runtime";

/**
 * /api/preview/[siteId] — driver Preview Runtime för en genererad sajt så
 * ViewerPanel kan rendera den i en iframe.
 *
 * Bite C (ADR 0028/0030/0033): routen går via ``currentViewserRuntime()``
 * istället för att hårdkoda ``local-preview-server``. ``VIEWSER_PREVIEW_MODE``
 * avgör vilken adapter som körs (``local-next`` default, ``vercel-sandbox``
 * opt-in, ``stackblitz`` pausad). Adaptern returnerar ett generiskt
 * ``PreviewResult`` som vi mappar till routens HTTP-kontrakt.
 *
 * Endpoints:
 *
 *   - GET  → status för local-runtime (404 om ingen server lever; övriga
 *            runtimes saknar billig status-lookup → 404 med vägledning).
 *   - POST → starta preview via aktiv runtime (idempotent för local).
 *   - DELETE → stoppa preview via aktiv runtime.
 *
 * Endast tillgänglig på localhost (assertLocalhost). Vi kan spawna processer
 * (local) eller skapa moln-sandboxes (vercel-sandbox) — en utomstående som
 * når routen via tunnel skulle annars kunna trigga det.
 *
 * Felshape (alla 4xx/5xx-svar har ``code`` så ViewerPanel kan visa rätt copy
 * istället för att tyst falla tillbaka). ``logs`` bifogas när runtimen
 * returnerar strukturerade startup-loggar. Ingen tyst fallback: ett
 * ``failed``/``unsupported`` från runtimen route:as som ett ärligt fel — vi
 * faller aldrig tillbaka till en annan runtime bakom ryggen på operatören.
 *
 *   {
 *     error: string,           // human-readable
 *     code: PreviewErrorCode,  // maskinläsbar
 *     hint?: string,           // optional next-step för operatören
 *     logs?: string[]          // optional startup-loggar från runtimen
 *   }
 */

export type PreviewErrorCode =
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

interface PreviewErrorBody {
  error: string;
  code: PreviewErrorCode;
  hint?: string;
  logs?: string[];
}

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

function validateSiteId(siteId: string): string | null {
  if (!siteId) return "siteId saknas.";
  if (siteId.length > 64) return "siteId är för långt (max 64 tecken).";
  if (!SITE_ID_PATTERN.test(siteId)) {
    return "siteId får bara innehålla a-z, 0-9 och bindestreck.";
  }
  return null;
}

/**
 * Klassificera ett runtime-fel (``PreviewResult.error``) till en strukturerad
 * felshape. Vi matchar på meddelande-prefix eftersom ``local-preview-server.ts``
 * redan kastar deterministiska, mänskligt läsbara meddelanden — adaptern
 * bär dem oförändrade vidare i ``result.error``. Vercel-sandbox-fel som inte
 * matchar ett känt prefix landar som ``code: "unknown"`` (ärligt "okänt fel"
 * istället för tyst omdirigering).
 */
function classifyRuntimeError(message: string): PreviewErrorBody {
  if (message.startsWith("Genererad sajt saknas")) {
    return {
      error: message,
      code: "not_built",
      hint: "Kör python scripts/build_site.py för att bygga sajten innan preview.",
    };
  }
  if (message.startsWith("Build-artefakter saknas")) {
    return {
      error: message,
      code: "missing_artifacts",
      hint: "Site-mappen finns men .next/ saknas. Kör npm run build i sajtkatalogen, eller bygg om med build_site.py utan --skip-build.",
    };
  }
  if (message.startsWith("Inga lediga preview-portar")) {
    return {
      error: message,
      code: "port_pool_full",
      hint: "Stäng några äldre preview-servrar via DELETE /api/preview/<siteId>.",
    };
  }
  if (
    message.startsWith("Preview-servern på port") ||
    message.includes("svarade inte inom")
  ) {
    return {
      error: message,
      code: "spawn_failed",
      hint: "next start kraschade eller hängde. Kontrollera viewser-loggen för stderr-tail.",
    };
  }
  return {
    error: message,
    code: "unknown",
  };
}

/**
 * HTTP-status för en strukturerad felkod. "Inte byggd än" går som 404 så
 * ViewerPanel kan visa en mjuk "kör build_site.py först"-prompt; port-pool
 * är 503; ``unsupported`` (t.ex. fly-stub eller runtime utan stöd) är 501.
 */
function statusForErrorCode(code: PreviewErrorCode): number {
  switch (code) {
    case "not_built":
    case "missing_artifacts":
    case "not_running":
      return 404;
    case "port_pool_full":
      return 503;
    case "unsupported":
      return 501;
    case "runtime_misconfigured":
      return 500;
    default:
      return 500;
  }
}

/**
 * Resolva aktiv runtime. ``currentViewserRuntime()`` kastar om
 * ``VIEWSER_PREVIEW_MODE`` är satt till ett okänt värde (ingen tyst gissning).
 * Vi fångar det och returnerar ett ärligt konfigurationsfel istället för en
 * naken 500.
 */
function resolveRuntimeOrError():
  | { runtime: ReturnType<typeof currentViewserRuntime>; error?: never }
  | { runtime?: never; error: PreviewErrorBody } {
  try {
    return { runtime: currentViewserRuntime() };
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Kunde inte resolva Preview Runtime.";
    return {
      error: {
        error: message,
        code: "runtime_misconfigured",
        hint: "Kontrollera VIEWSER_PREVIEW_MODE i apps/viewser/.env.local.",
      },
    };
  }
}

/**
 * Plocka en iframe-URL ur ett ``PreviewResult``. ViewerPanel läser ``url``;
 * vi föredrar en explicit ``embedUrl`` om adaptern satt en, annars
 * ``previewSession.url`` och sist top-level ``previewUrl``.
 */
function previewUrlFromResult(result: PreviewResult): string | undefined {
  return (
    result.previewSession?.embedUrl ??
    result.previewSession?.url ??
    result.previewUrl
  );
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ siteId: string }> },
) {
  const localhostError = assertLocalhost(request);
  if (localhostError) return localhostError;

  const { siteId } = await context.params;
  const validation = validateSiteId(siteId);
  if (validation) {
    const body: PreviewErrorBody = {
      error: validation,
      code: "validation_error",
    };
    return NextResponse.json(body, { status: 400 });
  }

  const resolved = resolveRuntimeOrError();
  if (resolved.error) {
    return NextResponse.json(resolved.error, {
      status: statusForErrorCode(resolved.error.code),
    });
  }

  // Status-lookup finns idag bara för local-runtime (in-memory server-Map).
  // Övriga runtimes (vercel-sandbox m.fl.) saknar billig status-API i
  // kontraktet — vi gissar inte, utan svarar 404 med vägledning.
  if (resolved.runtime.kind !== "local") {
    const body: PreviewErrorBody = {
      error: `Status-GET stöds inte för runtime '${resolved.runtime.kind}'.`,
      code: "not_running",
      hint: "Använd POST /api/preview/<siteId> för att starta en preview-session.",
    };
    return NextResponse.json(body, { status: 404 });
  }

  const info = getPreviewServer(siteId);
  if (!info) {
    const body: PreviewErrorBody = {
      error: "Ingen preview-server körs för denna sajt.",
      code: "not_running",
      hint: "Anropa POST /api/preview/<siteId> för att starta en.",
    };
    return NextResponse.json(body, { status: 404 });
  }
  return NextResponse.json({ ...info, kind: "local" });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ siteId: string }> },
) {
  const localhostError = assertLocalhost(request);
  if (localhostError) return localhostError;

  const { siteId } = await context.params;
  const validation = validateSiteId(siteId);
  if (validation) {
    const body: PreviewErrorBody = {
      error: validation,
      code: "validation_error",
    };
    return NextResponse.json(body, { status: 400 });
  }

  const resolved = resolveRuntimeOrError();
  if (resolved.error) {
    return NextResponse.json(resolved.error, {
      status: statusForErrorCode(resolved.error.code),
    });
  }

  const { runtime } = resolved;

  // Additiva spårbarhets-fält (runId/versionId) får skickas via query utan
  // att bryta nuvarande ViewerPanel-kontrakt (som bara POST:ar med siteId).
  const runId = request.nextUrl.searchParams.get("runId") ?? undefined;
  const versionId =
    request.nextUrl.searchParams.get("versionId") ?? undefined;

  // Adaptrarna fångar sina egna fel och returnerar { status: "failed", ... }.
  // Ett kast här är därför oväntat (programmeringsfel) snarare än ett
  // förväntat preview-fel — vi mappar ändå till en ärlig 500.
  let result: PreviewResult;
  try {
    result = await runtime.start({
      kind: runtime.kind,
      projectName: siteId,
      siteId,
      runId,
      versionId,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid start av preview.";
    const body = classifyRuntimeError(message);
    return NextResponse.json(body, { status: statusForErrorCode(body.code) });
  }

  if (result.status === "ready" || result.status === "starting") {
    const url = previewUrlFromResult(result);
    if (!url) {
      // Runtimen rapporterar success men utan URL — det är inte användbart
      // för en iframe. Visa ärligt fel istället för en tom preview.
      const body: PreviewErrorBody = {
        error:
          "Preview-runtimen returnerade en session utan URL. Det går inte att rendera iframen.",
        code: "no_preview_url",
        logs: result.logs,
      };
      return NextResponse.json(body, { status: 502 });
    }
    return NextResponse.json({
      // Bakåtkompatibelt fält som ViewerPanel läser idag.
      url,
      status: result.status,
      siteId,
      kind: runtime.kind,
      previewSession: result.previewSession,
      previewUrl: result.previewUrl ?? url,
      logs: result.logs,
    });
  }

  // status === "failed" | "unsupported" → ärligt fel, ingen tyst fallback.
  const message =
    result.error ??
    (result.status === "unsupported"
      ? `Runtime '${runtime.kind}' stödjer inte preview.`
      : "Preview-runtimen misslyckades utan felmeddelande.");
  const body: PreviewErrorBody =
    result.status === "unsupported"
      ? { error: message, code: "unsupported" }
      : classifyRuntimeError(message);
  body.logs = result.logs;
  return NextResponse.json(body, { status: statusForErrorCode(body.code) });
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ siteId: string }> },
) {
  const localhostError = assertLocalhost(request);
  if (localhostError) return localhostError;

  const { siteId } = await context.params;
  const validation = validateSiteId(siteId);
  if (validation) {
    const body: PreviewErrorBody = {
      error: validation,
      code: "validation_error",
    };
    return NextResponse.json(body, { status: 400 });
  }

  const resolved = resolveRuntimeOrError();
  if (resolved.error) {
    return NextResponse.json(resolved.error, {
      status: statusForErrorCode(resolved.error.code),
    });
  }

  const { runtime } = resolved;
  // Stateful runtimes identifierar sessionen olika: local nycklar på siteId,
  // vercel-sandbox på previewSession.id (sandbox-namn). Klienten kan skicka
  // ?sessionId= för icke-local; annars faller vi tillbaka på siteId.
  const sessionId =
    request.nextUrl.searchParams.get("sessionId") ?? siteId;

  // För local kan vi rapportera ett exakt boolean-resultat (servern fanns
  // eller ej). Övriga runtimes saknar billig "fanns den?"-lookup — vi
  // delegerar stoppet via runtime-kontraktet och rapporterar stopped:true.
  if (runtime.kind === "local") {
    const stopped = stopPreviewServer(sessionId);
    return NextResponse.json({ stopped, sessionId });
  }

  await runtime.stop?.(sessionId);
  return NextResponse.json({ stopped: true, sessionId });
}
