import { NextRequest, NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";
import {
  getPreviewServer,
  startPreviewServer,
  stopPreviewServer,
} from "@/lib/local-preview-server";

/**
 * /api/preview/[siteId] — hanterar lokal preview-server för en
 * genererad sajt så ViewerPanel kan rendera den i en iframe direkt
 * mot ``http://localhost:<port>`` utan att gå via StackBlitz.
 *
 * Endpoints:
 *
 *   - GET  → returnera nuvarande status (eller 404 om ingen server lever).
 *   - POST → starta servern (idempotent — återanvänder existerande).
 *   - DELETE → stoppa servern.
 *
 * Endast tillgänglig på localhost (assertLocalhost). Vi spawnar
 * ``next start`` som ärvtsen viewser:s env — en utomstående som når
 * routen via tunnel skulle kunna trigga spawn av processer på vår
 * maskin.
 *
 * Felshape (alla 4xx/5xx-svar har ``code`` så ViewerPanel kan visa rätt copy
 * istället för att tyst falla tillbaka till StackBlitz; fixar gren A av
 * "CORS"-tjafset där en saknad lokal build maskerades som ett mystiskt
 * Chrome-COEP-fel):
 *
 *   {
 *     error: string,           // human-readable
 *     code: PreviewErrorCode,  // maskinläsbar
 *     hint?: string            // optional next-step för operatören
 *   }
 *
 * Codes mappar till specifika rotorsaker som ``local-preview-server.ts``
 * kan kasta. ``unknown`` är fall-back när ett oväntat fel uppstår; det
 * är bättre att UI visar "okänt fel" än att tyst route:a vidare och
 * dölja problemet.
 */

export type PreviewErrorCode =
  | "validation_error"
  | "not_built"
  | "missing_artifacts"
  | "port_pool_full"
  | "spawn_failed"
  | "not_running"
  | "unknown";

interface PreviewErrorBody {
  error: string;
  code: PreviewErrorCode;
  hint?: string;
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
 * Klassificera ett fel från ``startPreviewServer`` till en strukturerad
 * felshape. Vi matchar på error-message-prefix eftersom
 * ``local-preview-server.ts`` redan kastar deterministiska, mänskligt
 * läsbara meddelanden — vi bara annoterar dem för UI-grening utan att
 * ändra existerande felmeddelanden (bakåtkompatibelt med tester som
 * kontrollerar message-strängen).
 */
function classifyStartError(error: unknown): PreviewErrorBody {
  const message =
    error instanceof Error
      ? error.message
      : "Okänt fel vid start av preview-server.";

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

  const info = getPreviewServer(siteId);
  if (!info) {
    const body: PreviewErrorBody = {
      error: "Ingen preview-server körs för denna sajt.",
      code: "not_running",
      hint: "Anropa POST /api/preview/<siteId> för att starta en.",
    };
    return NextResponse.json(body, { status: 404 });
  }
  return NextResponse.json(info);
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

  try {
    const info = await startPreviewServer(siteId);
    return NextResponse.json(info);
  } catch (error) {
    const body = classifyStartError(error);
    // 404 för "inte byggd än" så ViewerPanel kan visa en mjuk
    // "kör build_site.py först"-prompt istället för en hård
    // 5xx-felindikator. Övriga fel går som 500/503.
    const status =
      body.code === "not_built" || body.code === "missing_artifacts"
        ? 404
        : body.code === "port_pool_full"
          ? 503
          : 500;
    return NextResponse.json(body, { status });
  }
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

  const stopped = stopPreviewServer(siteId);
  return NextResponse.json({ stopped });
}
