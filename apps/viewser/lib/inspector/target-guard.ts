import net from "node:net";

/**
 * SSRF-guard för inspector-mål.
 *
 * Porterad från sajtmaskins inspector-worker med EN medveten avvikelse:
 * loopback (localhost/127.0.0.1/::1) är TILLÅTET här. Viewser är en
 * localhost-only operator-prototyp (routes skyddas av assertLocalhost) och
 * dess primära preview-runtime är `local-next` som serverar previewn på
 * `http://localhost:<port>` — exakt det mål inspektorn ska kartlägga.
 * Övriga privata nät (10.x, 192.168.x, link-local, *.internal, ...)
 * blockeras precis som i originalet så att en inspector-request aldrig kan
 * användas för att proba operatörens LAN eller moln-metadata-endpoints.
 *
 * Obs: en extern inspector-worker (docker) har kvar sin EGNA guard som även
 * blockerar loopback — för localhost-previews är den lokala
 * Playwright-fallbacken därför rätt motor, workern är för publika URL:er.
 */

function normalizeHost(hostname: string): string {
  const lowered = hostname.toLowerCase().trim().replace(/\.$/, "");
  if (lowered.startsWith("[") && lowered.endsWith("]")) {
    return lowered.slice(1, -1);
  }
  return lowered;
}

function isLoopbackHost(host: string): boolean {
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (host === "::1") return true;
  const ipVersion = net.isIP(host);
  if (ipVersion === 4) return host.split(".")[0] === "127";
  return false;
}

function isPrivateIpv4(host: string): boolean {
  const parts = host.split(".").map((part) => Number(part));
  if (
    parts.length !== 4 ||
    parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)
  ) {
    return true;
  }

  const [a, b] = parts;
  if (a === 10) return true;
  if (a === 0) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 100 && b >= 64 && b <= 127) return true;
  if (a === 198 && (b === 18 || b === 19)) return true;
  return false;
}

function isPrivateIpv6(host: string): boolean {
  const normalized = host.toLowerCase();
  if (normalized.startsWith("fc") || normalized.startsWith("fd")) return true;
  if (normalized.startsWith("fe80:")) return true;
  return false;
}

/** True när hosten varken är loopback eller ett publikt namn/IP. */
function isDisallowedHost(hostname: string): boolean {
  const host = normalizeHost(hostname);
  if (!host) return true;
  if (isLoopbackHost(host)) return false;

  if (
    host === "0.0.0.0" ||
    host.endsWith(".local") ||
    host.endsWith(".internal")
  ) {
    return true;
  }

  const ipVersion = net.isIP(host);
  if (ipVersion === 4) return isPrivateIpv4(host);
  if (ipVersion === 6) return isPrivateIpv6(host);
  return false;
}

export type InspectorTargetCheck =
  | { ok: true; url: URL }
  | { ok: false; status: number; error: string };

/**
 * Validera ett inspector-mål (URL:en Playwright ska navigera till).
 * Returnerar parsad URL vid OK, annars status + svensk operatörstext.
 */
export function checkInspectorTarget(rawUrl: string): InspectorTargetCheck {
  let target: URL;
  try {
    target = new URL(rawUrl);
  } catch {
    return { ok: false, status: 400, error: "Ogiltig URL." };
  }

  if (!["http:", "https:"].includes(target.protocol)) {
    return { ok: false, status: 400, error: "Endast http/https stöds." };
  }
  if (isDisallowedHost(target.hostname)) {
    return {
      ok: false,
      status: 403,
      error:
        "Otillåten host för inspektion (privata nät blockeras; localhost-previews är OK).",
    };
  }
  return { ok: true, url: target };
}

/** True när målet är loopback — då kan en extern worker inte nå det. */
export function isLoopbackTarget(url: URL): boolean {
  return isLoopbackHost(normalizeHost(url.hostname));
}
