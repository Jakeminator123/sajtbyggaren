import type { NextConfig } from "next";

// Cross-origin isolation headers krävs av WebContainers (som driver
// StackBlitz-embeddet i ViewerPanel via `template: "node"`). Utan dem
// får iframen inte tillgång till SharedArrayBuffer, vilket gör att
// StackBlitz visar "Unable to run Embedded Project — Looks like this
// project is being embedded without proper isolation headers" istället
// för en faktisk preview.
//
// `credentialless` används istället för `require-corp` eftersom vi
// embeddar tredjepartsiframe (stackblitz.com) vars resurser vi inte
// kan styra `Cross-Origin-Resource-Policy` på. `credentialless` är
// den nyare cross-origin-isolation-modellen som tillåter just det här
// fallet och dokumenteras av StackBlitz som det rätta värdet för
// "embedding arbitrary resources" — se
// https://developer.stackblitz.com/platform/webcontainers/browser-support#embedding.
//
// Krav speglas också i:
//   - docs/integrations/webcontainers-notes.md (host-miljö-krav)
//   - docs/architecture/preview-runtime.md (StackBlitz-implementationen)
//   - docs/integrations/stackblitz-research.md (browser-baseline + headers)
//
// Embedded WebContainers fungerar officiellt bara i Chromium-baserade
// browsers (Chrome, Edge, Brave, Vivaldi). Firefox/Safari rendrar
// samma fel även med headers korrekt satta — StackBlitz egen browser-
// support-tabell säger detta uttryckligen.
const nextConfig: NextConfig = {
  async headers() {
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
