import type { NextConfig } from "next";

// Preview-runtime-läge (ADR 0028 — Runtime Ladder).
// ------------------------------------------------------------------
// Viewser har två sätt att rendera den genererade sajten i preview-
// iframen, och de behöver MOTSATTA header-konfigurationer:
//
//   1. `local-next`  — LocalRuntime, första rungen i runtime-stegen.
//                      `lib/local-preview-server.ts` spawnar
//                      `npx next start -p <4100-4199>` mot
//                      `../sajtbyggaren-output/.generated/<siteId>/`
//                      och ViewerPanel embeddar det via en plain
//                      cross-origin (annan port) <iframe>. Då FÅR vi
//                      INTE sätta Cross-Origin-Embedder-Policy /
//                      Cross-Origin-Opener-Policy — credentialless +
//                      same-origin blockerar cross-origin iframes som
//                      inte själva bär `credentialless`-attributet.
//
//   2. `stackblitz`  — Bakåtkompatibel WebContainer-väg. StackBlitz-
//                      embeddet kräver SharedArrayBuffer, vilket bara
//                      är tillgängligt på cross-origin-isolerade
//                      dokument. Då MÅSTE vi sätta
//                      `Cross-Origin-Embedder-Policy: credentialless`
//                      och `Cross-Origin-Opener-Policy: same-origin`,
//                      annars visar StackBlitz "Unable to run Embedded
//                      Project — Looks like this project is being
//                      embedded without proper isolation headers".
//
//   3. `auto`        — Reserverat för framtida heuristik (välj
//                      LocalRuntime när bygget finns, annars
//                      StackBlitz). Idag mappar `auto` på StackBlitz-
//                      headers för säker bakåtkompatibilitet.
//
// `credentialless` används i StackBlitz-grenen istället för
// `require-corp` eftersom vi embeddar tredjepartsiframe (stackblitz.com)
// vars resurser vi inte kan styra `Cross-Origin-Resource-Policy` på.
// `credentialless` är den nyare cross-origin-isolation-modellen som
// tillåter just det här fallet och dokumenteras av StackBlitz som det
// rätta värdet för "embedding arbitrary resources" — se
// https://developer.stackblitz.com/platform/webcontainers/browser-support#embedding.
//
// Krav speglas också i:
//   - docs/adr/0028-runtime-ladder.md (LocalRuntime som första rung)
//   - docs/integrations/webcontainers-notes.md (host-miljö-krav)
//   - docs/architecture/preview-runtime.md (StackBlitz-implementationen)
//   - docs/integrations/stackblitz-research.md (browser-baseline + headers)
//
// Embedded WebContainers fungerar officiellt bara i Chromium-baserade
// browsers (Chrome, Edge, Brave, Vivaldi). Firefox/Safari rendrar
// samma fel även med headers korrekt satta — StackBlitz egen browser-
// support-tabell säger detta uttryckligen.
//
// Default-värdet är `local-next` eftersom 99% av anropen kommer från en
// utvecklarmaskin där LocalRuntime är snabbaste vägen till en levande
// preview. Hosted/CI-deploys promotas automatiskt till StackBlitz-
// headerläget av production-gaten nedan — så defaulten är säker även
// om operatören glömt att sätta variabeln i en hosted miljö.
const PREVIEW_MODE = (process.env.VIEWSER_PREVIEW_MODE ?? "local-next").toLowerCase();

// Production safety gate.
// ------------------------------------------------------------------
// `local-next` är medvetet "isolation off" — det är det enda sättet
// att låta en cross-origin (annan port) localhost-iframe rendras
// utan att blockas av `Cross-Origin-Embedder-Policy: credentialless`.
// Det är RÄTT i dev-miljö (lokal preview-server på 4100-4199), men
// FARLIGT i produktion av två orsaker:
//
//   a) Den hostade StackBlitz-vägen (fallback när LocalRuntime inte
//      finns) tappar tyst SharedArrayBuffer och rendrar "Unable to
//      run Embedded Project" istället för en tydlig 4xx — d.v.s.
//      misslyckandet maskeras som en pseudo-renderad preview.
//   b) Alla framtida features som beror på cross-origin isolation
//      (OPFS, högupplösta perf-counters, vissa wasm-paths) regressar
//      tyst i exakt samma miljö där vi minst märker det.
//
// Därför "befordrar" vi `local-next` → `stackblitz` (för header-
// utvärderingens skull) när `NODE_ENV === "production"`. Operatören
// kan opta ur via `VIEWSER_ALLOW_NO_ISOLATION=1` — namnet är
// avsiktligt brusigt eftersom variabeln säger vad den kostar. Det
// ska kräva ett medvetet beslut att stänga av cross-origin
// isolation i produktion, inte ett slip av tangentbordet i en CI-
// config. Spegla värdet i NEXT_PUBLIC-spegeln nedan så ViewerPanel
// får samma vy som server-render och inte spawnar en LocalRuntime-
// klient som ändå skulle blockas av headers.
const IS_PRODUCTION = process.env.NODE_ENV === "production";
const ALLOW_NO_ISOLATION = process.env.VIEWSER_ALLOW_NO_ISOLATION === "1";
const effectiveMode =
  IS_PRODUCTION && PREVIEW_MODE === "local-next" && !ALLOW_NO_ISOLATION
    ? "stackblitz"
    : PREVIEW_MODE;

const nextConfig: NextConfig = {
  // Spegla läget till klienten så ViewerPanel kan ta beslut baserat
  // på det (t.ex. skippa StackBlitz-fallbacken när vi vet att vi kör
  // LocalRuntime). NEXT_PUBLIC_-prefixet är vad Next.js kräver för att
  // exponera variabler i browserbundlen.
  //
  // Vi exponerar RAW `PREVIEW_MODE` (operatörens uttryckta intent),
  // INTE `effectiveMode` (server-headers-utfallet efter production-
  // gaten). Skälet: gaten är medvetet en server-side säkerhets-rail
  // för cross-origin isolation, inte en omtolkning av operatörens
  // runtime-val. Att smitta klient-runtime-besluten med gate-utfallet
  // skulle göra production-läget oförutsägbart för en operator som
  // explicit valt local-next (AI Bug Review-fynd 84% på PR #88). En
  // framtida ViewerPanel-konsument kan självständigt välja att
  // korsreferera mot fetch:ade headers om den behöver veta vad servern
  // ACT settle:ade på.
  env: {
    NEXT_PUBLIC_VIEWSER_PREVIEW_MODE: PREVIEW_MODE,
  },
  async headers() {
    // LocalRuntime-grenen: tom header-lista. COEP credentialless +
    // COOP same-origin skulle annars blockera den cross-origin iframen
    // som pekar på localhost:<4100-4199>. Notera: `effectiveMode`, inte
    // `PREVIEW_MODE` — production-gaten ovanför ser till att vi aldrig
    // når den här grenen oavsiktligt i `NODE_ENV=production`.
    if (effectiveMode === "local-next") {
      return [];
    }

    // StackBlitz-grenen (och `auto` / okänt värde): behåll de
    // cross-origin-isolation-headers som WebContainers kräver.
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Cross-Origin-Embedder-Policy", value: "credentialless" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
