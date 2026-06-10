import { NextRequest, NextResponse } from "next/server";

import {
  hostedFeatureUnavailable,
  isHostedSandboxPreviewEnabled,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import { assertLocalhost } from "@/lib/localhost-guard";
import {
  getPreviewServer,
  startPreviewServer,
  stopPreviewServer,
} from "@/lib/local-preview-server";
import { currentViewserRuntime } from "@/lib/preview-runtime-server";
import {
  getSandboxSession,
  stopSandboxSessionForSite,
} from "@/lib/vercel-sandbox-sessions";
import type {
  PreviewResult,
  PreviewRuntimeKind,
  PreviewTimings,
} from "@preview-runtime";

/**
 * /api/preview/[siteId] — hanterar preview för en genererad sajt så
 * ViewerPanel kan rendera den i en iframe.
 *
 * Routen är runtime-agnostisk: den resolvar den env-styrda adaptern via
 * ``currentViewserRuntime()`` (DI, ADR 0028/0030/0033) i stället för att
 * hårdkoda en specifik preview-väg.
 *
 *   - ``local`` (``VIEWSER_PREVIEW_MODE=local-next``, default) — spawnar
 *     ``next start -p <4100-4199>`` lokalt och iframe:ar
 *     ``http://localhost:<port>`` (OFÖRÄNDRAT beteende, byte-identisk path).
 *   - ``vercel-sandbox`` (``VIEWSER_PREVIEW_MODE=vercel-sandbox``, ADR 0033) —
 *     kör en isolerad kopia i en Vercel Sandbox och iframe:ar den publika
 *     ``…vercel.run``-URL:en. Cold-start ~28 s (POST:en blockar tills URL
 *     svarar). Degraderar ärligt (``vercel_auth``) utan token.
 *
 * Endpoints:
 *
 *   - GET  → returnera nuvarande status (eller 404 om ingen preview lever).
 *   - POST → starta previewn (idempotent för local; vercel-sandbox stoppar en
 *            ev. gammal sandbox för samma siteId och skapar en ny).
 *   - DELETE → stoppa previewn.
 *
 * Endast tillgänglig på localhost (assertLocalhost). Vi spawnar
 * ``next start`` (eller drar igång en sandbox) som ärver viewser:s env — en
 * utomstående som når routen via tunnel skulle kunna trigga spawn av processer
 * eller kostsamma sandbox-körningar.
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
 * kan kasta, plus ``vercel_auth``/``sandbox_failed`` för vercel-sandbox-
 * adapterns ärliga degradering. ``unknown`` är fall-back när ett oväntat fel
 * uppstår; det är bättre att UI visar "okänt fel" än att tyst route:a vidare
 * och dölja problemet.
 */

export type PreviewErrorCode =
  | "validation_error"
  | "not_built"
  | "missing_artifacts"
  | "port_pool_full"
  | "spawn_failed"
  | "not_running"
  // Vercel Sandbox-adaptern (ADR 0033) degraderar ärligt:
  | "vercel_auth" // saknad/utgången VERCEL_OIDC_TOKEN (eller token-trio)
  | "sandbox_failed" // sandboxen byggde/startade inte (npm install/next build/timeout)
  | "unknown";

interface PreviewErrorBody {
  error: string;
  code: PreviewErrorCode;
  hint?: string;
}

// Hostad preview-start kör ``npm install`` + ``next build`` + ``next start`` i en
// Vercel Sandbox och blockar POST:en tills den publika URL:en svarar (~28 s+
// kallstart). En default-serverless-funktion (10 s) hinner inte. Vi höjer taket
// till 300 s (Pro-plan; Hobby är hårt kapat till 60 s — se
// docs/hosted-viewser-deploy.md för den ärliga begränsningen). Påverkar inte
// lokal drift där samma route bara spawnar en lokal ``next start``.
export const runtime = "nodejs";
export const maxDuration = 300;

interface PreviewStartOk {
  siteId: string;
  /** Iframe:bar URL — lokal http eller publik vercel.run https. */
  url: string;
  status: "ready";
  kind: PreviewRuntimeKind;
  /** Hållbar handle (sandbox.name) när adaptern äger en stoppbar resurs. */
  sessionId?: string;
  /**
   * Fas-timing (ms) från adapterns cold-start-mätning (B6-light, additivt
   * fält): createMs/uploadMs/installMs/buildMs/readyMs/totalMs. Bara satt
   * när adaptern mäter (idag vercel-sandbox); local-next-svaret är oförändrat.
   */
  timings?: PreviewTimings;
}

const VERCEL_AUTH_HINT =
  "Kör `vercel env pull apps/viewser/.env.vercel.local` för en färsk " +
  "OIDC-token (gäller ~12 h) och starta om npm run dev.";

/** True om felet beror på saknad/utgången Vercel-auth (för ``vercel_auth``). */
function isVercelAuthError(message: string): boolean {
  return /credentials saknas|VERCEL_OIDC_TOKEN|Vercel-credentials/i.test(message);
}

/**
 * Klassificera ett ``failed``/``unsupported`` ``PreviewResult`` från en
 * icke-lokal adapter (idag bara ``vercel-sandbox``) till en strukturerad
 * felshape. Saknad token → ``vercel_auth`` så UI:t kan visa ett pedagogiskt
 * inloggningsfel i stället för en tyst fallback.
 */
function classifyRuntimeError(
  kind: PreviewRuntimeKind,
  result: PreviewResult,
): PreviewErrorBody {
  const message =
    result.error ??
    `Preview-läget '${kind}' returnerade ingen URL att visa i iframen.`;
  if (isVercelAuthError(message)) {
    return { error: message, code: "vercel_auth", hint: VERCEL_AUTH_HINT };
  }
  return {
    error: message,
    code: "sandbox_failed",
    hint:
      kind === "vercel-sandbox"
        ? "Sandbox-bygget misslyckades. Se viewser-loggen för npm install/next build-loggar, eller försök igen."
        : undefined,
  };
}

/** HTTP-status för de adapter-specifika felkoderna (icke-lokala adaptrar). */
function statusForRuntimeError(code: PreviewErrorCode): number {
  if (code === "vercel_auth") return 503; // preview-backend inte konfigurerad
  if (code === "sandbox_failed") return 502; // upstream sandbox-fel
  return 500;
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

  const runtime = currentViewserRuntime();

  // Non-local adaptrar (vercel-sandbox): rapportera den spårade sessionen om
  // en finns. local-next-grenen nedan är OFÖRÄNDRAD.
  if (runtime.kind !== "local") {
    if (runtime.kind === "vercel-sandbox") {
      const session = getSandboxSession(siteId);
      if (session) {
        const body: PreviewStartOk = {
          siteId,
          url: session.url,
          status: "ready",
          kind: "vercel-sandbox",
          sessionId: session.sandboxId,
        };
        return NextResponse.json(body);
      }
    }
    const body: PreviewErrorBody = {
      error: "Ingen preview körs för denna sajt.",
      code: "not_running",
      hint: "Anropa POST /api/preview/<siteId> för att starta en.",
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

  // Hosted honesty + #156 guard: POST starts a build-like preview (local
  // `next start`, or a Vercel Sandbox that runs `npm install` + `next build`).
  // A public, unauthenticated POST that can spawn sandboxes is exactly the
  // open-relay risk that parked PR #156. So on hosted Vercel the endpoint is
  // gated 501 unless the operator has explicitly opted in
  // (`VIEWSER_ENABLE_HOSTED_SANDBOX=1`) AND the deployment is protected
  // (platform-level Vercel Deployment Protection — see the hosted deploy guide
  // docs/hosted-viewser-deploy.md). The local-spawn path can never work hosted
  // (no repo disk, no `next start` host process), so even when opted in we only
  // allow the non-local (Vercel Sandbox) adapter hosted.
  if (isHostedVercelRuntime()) {
    if (!isHostedSandboxPreviewEnabled()) {
      return hostedFeatureUnavailable(
        "preview-start",
        "Förhandsvisning startas lokalt i denna version. Den hostade " +
          "sandbox-previewen är avstängd som standard (en publik bygg-/" +
          "sandbox-endpoint utan auth tillåts inte). Operatören kan aktivera " +
          "den bakom Vercel Deployment Protection via " +
          "VIEWSER_ENABLE_HOSTED_SANDBOX=1.",
      );
    }
    if (currentViewserRuntime().kind === "local") {
      return hostedFeatureUnavailable(
        "preview-start",
        "Lokal preview (next start) kan inte köras på en hostad Vercel-" +
          "funktion. Sätt VIEWSER_PREVIEW_MODE till Vercel Sandbox-läget för " +
          "hostad förhandsvisning.",
      );
    }
  }

  const runtime = currentViewserRuntime();

  // Non-local adaptrar (vercel-sandbox m.fl.): gå via den resolvade adaptern
  // och iframe:a den returnerade publika URL:en. local-next-grenen nedan är
  // OFÖRÄNDRAD (byte-identisk path).
  if (runtime.kind !== "local") {
    // ``runtime.start`` kapslar själv alla fel i ett ``PreviewResult`` (den
    // kastar inte), men vi vaktar ändå mot oväntade kast så routen aldrig
    // returnerar en otydlig 500 utan ``code``.
    let result: PreviewResult;
    try {
      result = await runtime.start({
        kind: runtime.kind,
        projectName: siteId,
        siteId,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Okänt fel i preview-runtimen.";
      const body = classifyRuntimeError(runtime.kind, { status: "failed", error: message });
      return NextResponse.json(body, { status: statusForRuntimeError(body.code) });
    }

    if (result.status === "ready" && result.previewUrl) {
      const body: PreviewStartOk = {
        siteId,
        url: result.previewUrl,
        status: "ready",
        kind: runtime.kind,
        sessionId: result.previewSession?.id,
        timings: result.timings,
      };
      return NextResponse.json(body);
    }

    const body = classifyRuntimeError(runtime.kind, result);
    return NextResponse.json(body, { status: statusForRuntimeError(body.code) });
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

  const runtime = currentViewserRuntime();

  // Livscykel/kostnad (ADR 0033): i vercel-sandbox-läge stoppar vi den spårade
  // sandboxen för siteId (TTL ~15 min + kostar ören — läck den inte). local-next
  // behåller exakt sitt gamla beteende (stoppa lokal next start).
  if (runtime.kind === "vercel-sandbox") {
    const stopped = await stopSandboxSessionForSite(siteId);
    return NextResponse.json({ stopped });
  }

  const stopped = stopPreviewServer(siteId);
  return NextResponse.json({ stopped });
}
