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
const PREVIEW_MODE = (process.env.VIEWSER_PREVIEW_MODE ?? "stackblitz").toLowerCase();

const nextConfig: NextConfig = {
  // Spegla läget till klienten så ViewerPanel kan ta beslut baserat
  // på det (t.ex. skippa StackBlitz-fallbacken när vi vet att vi kör
  // LocalRuntime). NEXT_PUBLIC_-prefixet är vad Next.js kräver för att
  // exponera variabler i browserbundlen.
  env: {
    NEXT_PUBLIC_VIEWSER_PREVIEW_MODE: PREVIEW_MODE,
  },
  async headers() {
    // LocalRuntime-grenen: tom header-lista. COEP credentialless +
    // COOP same-origin skulle annars blockera den cross-origin iframen
    // som pekar på localhost:<4100-4199>.
    if (PREVIEW_MODE === "local-next") {
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
