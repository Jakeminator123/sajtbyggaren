/**
 * hosted-run-artefacts — klientsidans hjälpare för det hostade
 * "run-artefakter finns inte"-läget.
 *
 * Hostat (Vercel, VERCEL=1) svarar /api/runs/[runId]/{artifacts,trace,files}
 * med en MEDVETEN 404 vars body bär `hostedNotice` — run-artefakterna ligger
 * på operatörens lokala disk (data/runs/), inte i den hostade runtimen (se
 * route-filerna under apps/viewser/app/api/runs/[runId]/). Det är en ärlig
 * degradering, inget fel. UI-komponenter ska därför behandla det svaret som
 * ett lugnt "otillgängligt hostat"-läge med notisens text — aldrig som
 * fel-state, retry-loop eller console-brus.
 *
 * Två mekanismer, båda svarsformsbaserade (ingen egen env-läsning klientsidigt):
 *
 *   1. `hostedRunNoticeFromResponse(status, body)` — detekterar den medvetna
 *      404+hostedNotice-formen och returnerar notisen (annars null, så
 *      riktiga fel förblir fel).
 *   2. En modul-latch som minns notisen för resten av sidvisningen
 *      (hosted-läget kan inte ändras under en session). page.tsx armar den
 *      tidigt via /api/runs-svaret (hostedNotice på en 200), och varje
 *      detekterad 404-form armar den också. Komponenter kan då hoppa över
 *      anropet helt nästa gång — det tystar även browserns automatiska
 *      "Failed to load resource: 404"-rad i konsolen, som inte går att
 *      undertrycka från JS när requesten väl skickats.
 *
 * Lokalt är latchen alltid null och alla kodvägar är oförändrade.
 */

let sessionHostedNotice: string | null = null;

/** Minns hosted-notisen för resten av sidvisningen (no-op för null/tomt). */
export function rememberHostedRunNotice(
  notice: string | null | undefined,
): void {
  if (typeof notice === "string" && notice.trim().length > 0) {
    sessionHostedNotice = notice;
  }
}

/** Den kända hosted-notisen, eller null lokalt/innan första svaret setts. */
export function knownHostedRunNotice(): string | null {
  return sessionHostedNotice;
}

/**
 * Svarsformsbaserad detektering: 404 + strängen `hostedNotice` i bodyn är
 * den medvetna hostade degraderingen från run-artefakt-endpointsen.
 * Returnerar notisen (och armar latchen) — eller null för alla andra svar,
 * så att en riktig 404/500 lokalt fortfarande hanteras som fel.
 */
export function hostedRunNoticeFromResponse(
  status: number,
  body: unknown,
): string | null {
  if (status !== 404 || body === null || typeof body !== "object") {
    return null;
  }
  const notice = (body as { hostedNotice?: unknown }).hostedNotice;
  if (typeof notice === "string" && notice.trim().length > 0) {
    rememberHostedRunNotice(notice);
    return notice;
  }
  return null;
}

/**
 * Hämtar en run-artefakt-bundle hostat-medvetet från
 * `/api/runs/[runId]/artifacts`. Samlar latch-skip + svarsforms-detektering
 * + defensiv shape-validering på ett ställe så ytor som behöver en rå bundle
 * (versions-tab:ens compare-diff m.fl.) slipper duplicera logiken.
 *
 *   - Latch-skip: är hosted-läget redan känt skippas anropet helt och
 *     notisens text kastas som Error (hostat är versionslistan tom så hit når
 *     vi i praktiken aldrig; grinden är belt-and-braces mot framtida vägar).
 *   - Svarsform: armar latchen om svaret visar sig vara den hostade 404-formen
 *     (error-fältet bär då samma notis-sträng som kastas nedan).
 *   - Shape: ett malformat svar fångas med ett tydligt fel i stället för att
 *     låta diff-vyn rendera tomma sektioner (speglar run-details-panel.tsx).
 *
 * Kastar Error vid hostat/HTTP-fel/malformat svar. Returnerar den validerade
 * bundeln som ett objekt; caller castar till sin egen bundle-typ.
 */
export async function fetchHostedAwareArtefactBundle(
  runId: string,
): Promise<Record<string, unknown>> {
  const known = knownHostedRunNotice();
  if (known) {
    throw new Error(known);
  }
  const response = await fetch(`/api/runs/${runId}/artifacts`);
  const raw = (await response.json()) as unknown;
  hostedRunNoticeFromResponse(response.status, raw);
  const errorField =
    raw && typeof raw === "object" && "error" in raw
      ? (raw as { error: unknown }).error
      : null;
  if (!response.ok || typeof errorField === "string") {
    throw new Error(
      typeof errorField === "string" ? errorField : `HTTP ${response.status}`,
    );
  }
  if (!raw || typeof raw !== "object" || !("runId" in raw)) {
    throw new Error(
      "Artefakt-svar saknar förväntat shape (runId/buildResult/sitePlan).",
    );
  }
  const bundle = raw as Record<string, unknown>;
  if (typeof bundle.runId !== "string" || bundle.runId.length === 0) {
    throw new Error("Artefakt-svar har ogiltigt runId.");
  }
  return bundle;
}
