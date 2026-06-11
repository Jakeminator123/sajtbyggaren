/**
 * vercel-oidc-refresh — delad OIDC-token-hållbarhet (B1a).
 *
 * EN implementation av "håll VERCEL_OIDC_TOKEN färsk" med två konsumenter:
 *
 *   1. `scripts/dev.mjs` — dispatchern hämtar en färsk token vid `npm run dev`
 *      i vercel-sandbox-läge (predev-auth, som tidigare bodde inline där).
 *   2. `lib/vercel-sandbox-runner.ts` — runnern anropar samma logik FÖRE
 *      `Sandbox.create` när OIDC-vägen används och tokenens JWT-exp har
 *      < 1 h kvar, så en lång viewser-session inte dör mitt i på en
 *      ~12 h-token utan omstart av dev-servern.
 *
 * Filen är medvetet en `.mjs` (inte `.ts`): dev.mjs är ett rent ESM-script
 * som körs direkt av node utan TS-kompilering, och apps/viewser har
 * `allowJs: true` + bundler-resolution så runnern (TS) kan importera samma
 * modul utan extra build-steg — minsta friktion för en delad implementation.
 *
 * ALLTID best-effort: saknad vercel-CLI, olänkat repo eller misslyckad pull
 * kastar aldrig — konsumenterna degraderar ärligt ("Vercel-inloggning
 * saknas") tills en token finns.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_DIR = dirname(fileURLToPath(import.meta.url));
/** apps/viewser-roten (modulen bor i apps/viewser/lib/). */
const VIEWSER_ROOT = resolve(MODULE_DIR, "..");
const REPO_ROOT = resolve(VIEWSER_ROOT, "..", "..");

/**
 * Filen `vercel env pull` default-skriver OIDC-token till (gitignored,
 * ~12 h TTL lokalt). Next auto-laddar den INTE — runnern läser den själv.
 */
export const VERCEL_OIDC_ENV_FILE = resolve(VIEWSER_ROOT, ".env.vercel.local");

/** Hämta ny token när mindre än så här återstår av JWT-exp (< 1 h). */
export const OIDC_REFRESH_MARGIN_SECONDS = 60 * 60;

/**
 * Decoda `exp`-claimen (sekunder sedan epoch) ur en JWT utan verifiering.
 * Icke-kastande: oläsbar/saknad token → `null`.
 *
 * @param {string | null | undefined} token
 * @returns {number | null}
 */
export function decodeJwtExpirySeconds(token) {
  try {
    if (!token) return null;
    const payload = token.split(".")[1];
    if (!payload) return null;
    const decoded = Buffer.from(
      payload.replace(/-/g, "+").replace(/_/g, "/"),
      "base64",
    ).toString("utf8");
    const claims = JSON.parse(decoded);
    return typeof claims.exp === "number" ? claims.exp : null;
  } catch {
    return null;
  }
}

/**
 * Läs VERCEL_OIDC_TOKEN-värdet ur en env-fil (default `.env.vercel.local`).
 * Tål omslutande citat (`vercel env pull` quotar token-strängen).
 * Icke-kastande: saknad fil/nyckel → `null`.
 *
 * @param {string} [envFile]
 * @returns {string | null}
 */
export function readVercelOidcTokenFromFile(envFile = VERCEL_OIDC_ENV_FILE) {
  try {
    const raw = readFileSync(envFile, "utf8");
    const match = raw.match(/^\s*VERCEL_OIDC_TOKEN\s*=\s*(.+)$/m);
    if (!match) return null;
    const token = match[1].trim().replace(/^["']|["']$/g, "");
    return token || null;
  } catch {
    return null;
  }
}

/**
 * JWT-exp (sekunder sedan epoch) för token i env-filen, eller `null`.
 *
 * @param {string} [envFile]
 * @returns {number | null}
 */
export function vercelOidcExpirySeconds(envFile = VERCEL_OIDC_ENV_FILE) {
  return decodeJwtExpirySeconds(readVercelOidcTokenFromFile(envFile));
}

/**
 * Hämta en färsk VERCEL_OIDC_TOKEN till env-filen via vercel-CLI:n — men
 * bara när det behövs (token saknas, oläsbar exp, eller < margin kvar).
 *
 * @param {{
 *   log?: (message: string) => void,
 *   warn?: (message: string) => void,
 *   envFile?: string,
 * }} [options] `log`/`warn` får RÅA meddelanden — konsumenten äger sin
 *   prefix-stil ("Viewser dev → ..." i dispatchern, logs-array i runnern).
 * @returns {{ ok: boolean, refreshed: boolean, expiresInSeconds: number | null }}
 *   `expiresInSeconds` speglar tokenens kvarvarande livstid EFTER försöket
 *   (negativ/`null` = utgången/oläsbar).
 */
export function ensureFreshVercelOidcToken(options = {}) {
  const log = options.log ?? (() => {});
  const warn = options.warn ?? (() => {});
  const envFile = options.envFile ?? VERCEL_OIDC_ENV_FILE;

  const nowSeconds = Math.floor(Date.now() / 1000);
  const exp = vercelOidcExpirySeconds(envFile);
  if (exp !== null && exp - nowSeconds > OIDC_REFRESH_MARGIN_SECONDS) {
    const minutesLeft = Math.round((exp - nowSeconds) / 60);
    log(`VERCEL_OIDC_TOKEN giltig ~${minutesLeft} min till — hoppar över pull.`);
    return { ok: true, refreshed: false, expiresInSeconds: exp - nowSeconds };
  }
  log("hämtar färsk VERCEL_OIDC_TOKEN (vercel env pull)…");
  try {
    // DEP0190 / säkerhet: spawna SHELL-FRITT (shell: false) med args som array,
    // så ingen shell-sträng byggs (ingen injektionsyta, ingen
    // args+shell:true-deprecation). På Windows vägrar Node 24 spawna en `.cmd`
    // direkt med shell:false (EINVAL, CVE-2024-27980-härdningen) — kör därför
    // `cmd.exe /c vercel …`: cmd.exe är en riktig .exe (ingen EINVAL) och
    // shell:false behålls (ingen DEP0190). Övriga plattformar kör `vercel`
    // direkt. Saknas binären returnerar spawnSync ett fel (status != 0 / kast)
    // som fångas nedan → ärlig degrade (best-effort token-pull).
    const isWindows = process.platform === "win32";
    const command = isWindows ? "cmd.exe" : "vercel";
    const args = isWindows
      ? ["/c", "vercel", "env", "pull", envFile, "--environment=development", "--yes"]
      : ["env", "pull", envFile, "--environment=development", "--yes"];
    const result = spawnSync(command, args, {
      cwd: REPO_ROOT,
      stdio: "ignore",
      shell: false,
      timeout: 60_000,
    });
    if (result.status === 0) {
      log("OIDC-token uppdaterad.");
      const freshExp = vercelOidcExpirySeconds(envFile);
      return {
        ok: true,
        refreshed: true,
        expiresInSeconds: freshExp === null ? null : freshExp - nowSeconds,
      };
    }
    warn(
      "kunde inte hämta OIDC-token (är vercel-CLI installerad och repot " +
        "länkat via `vercel link`?). Sandbox-preview degraderar ärligt tills " +
        "`vercel env pull apps/viewser/.env.vercel.local` körts.",
    );
  } catch (error) {
    warn(
      `kunde inte starta vercel env pull: ${error.message}. Fortsätter ändå.`,
    );
  }
  return {
    ok: false,
    refreshed: false,
    expiresInSeconds: exp === null ? null : exp - nowSeconds,
  };
}
