import type { MetadataRoute } from "next";

// PWA-webbmanifest. Saknades helt → mobilwebbläsare fick ingen app-titel,
// installbarhet eller temafärg. Färgerna speglar --background-token (varm
// off-white). Ikonerna ligger statiskt i public/ (genererade ur samma
// "S"-monogram som favicon/OG) så manifestet kan referera dem direkt.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Sajtbyggaren",
    short_name: "Sajtbyggaren",
    description:
      "Beskriv din verksamhet — Sajtbyggaren bygger en färdig företagshemsida åt dig med AI.",
    start_url: "/",
    display: "standalone",
    lang: "sv",
    background_color: "#f7f6f2",
    theme_color: "#f7f6f2",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
