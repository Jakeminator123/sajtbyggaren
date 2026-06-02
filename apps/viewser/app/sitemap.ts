import type { MetadataRoute } from "next";

import { PROFESSIONS } from "@/lib/professions";

// Publik sitemap för marknadssajten. Konsolen (/studio) + /api utelämnas
// medvetet (noindex/localhost-bunden). SITE_URL speglar metadataBase i
// app/layout.tsx. Statiska sidor + 20 SSG per-yrke-landningssidor.
const SITE_URL = "https://sajtbyggaren.se";

const STATIC_PATHS: ReadonlyArray<string> = [
  "",
  "/produkt",
  "/priser",
  "/om-oss",
  "/kontakt",
  "/cookies",
  "/integritetspolicy",
  "/anvandarvillkor",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  const staticEntries = STATIC_PATHS.map((path) => ({
    url: `${SITE_URL}${path}`,
    lastModified,
    changeFrequency: "monthly" as const,
    priority: path === "" ? 1 : 0.6,
  }));

  const professionEntries = PROFESSIONS.map((p) => ({
    url: `${SITE_URL}/for/${p.slug}`,
    lastModified,
    changeFrequency: "monthly" as const,
    priority: 0.5,
  }));

  return [...staticEntries, ...professionEntries];
}
