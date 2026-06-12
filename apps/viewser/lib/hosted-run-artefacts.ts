/**
 * hosted-run-artefacts — klientsidans hjälpare för det hostade
 * "run-artefakter finns inte"-läget.
 *
 * HISTORIK/NULÄGE (B199 v2): före B199 v2 svarade
 * /api/runs/[runId]/{artifacts,trace,files} hostat med en MEDVETEN 404 vars
 * body bar `hostedNotice` ("hela förmågan saknas hostat"), och latchen nedan
 * armades tidigt så komponenter kunde hoppa över dömda anrop. Sedan B199 v2
 * serveras artefakter + trace hostat ur KV/blob, /api/runs bär en ren
 * info-banner i fältet `hostedBanner` (ALDRIG `hostedNotice`), och en run
 * som inte kan lösas svarar en VANLIG 404 utan `hostedNotice` — den ska
 * behandlas som ett per-run-fel, inte som "förmågan saknas".
 *
 * Latchen behålls som belt-and-braces: den armar ENBART på den medvetna
 * 404+hostedNotice-svarsformen, som idag ingen run-route returnerar. Skulle
 * en framtida route återinföra en hel-förmåga-degradering fungerar de lugna
 * UI-lägena i konsumenterna direkt igen.
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
