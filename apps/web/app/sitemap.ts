import type { MetadataRoute } from "next";
import { URLS } from "@/lib/config";

const BASE_URL = URLS.baseUrl;

/**
 * Sitemap för apps/web (publik UI).
 *
 * Bara statiska marknads-/juridiksidor som faktiskt finns i denna app.
 * Sajtmaskins fulla sitemap inkluderade SEO-landningar via
 * `collectAllSeoLandings()` + `category/[type]` — de kräver `lib/seo/`
 * och `content/seo-landings/` (385 JSON-filer) som inte är portade. Lägg
 * till dem när motsvarande sidor importeras.
 */
const STATIC_SITEMAP_REL_PATHS = [
  "",
  "/faq",
  "/om",
  "/blogg",
  "/priser",
  "/terms",
  "/privacy",
] as const;

const PRIORITIES: Record<string, number> = {
  "": 1.0,
  "/faq": 0.5,
  "/om": 0.45,
  "/blogg": 0.45,
  "/priser": 0.7,
  "/terms": 0.3,
  "/privacy": 0.3,
};

const FREQUENCIES: Record<string, "weekly" | "monthly" | "yearly"> = {
  "": "weekly",
  "/faq": "monthly",
  "/om": "monthly",
  "/blogg": "weekly",
  "/priser": "monthly",
  "/terms": "yearly",
  "/privacy": "yearly",
};

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return STATIC_SITEMAP_REL_PATHS.map((relPath) => ({
    url: relPath === "" ? BASE_URL : `${BASE_URL}${relPath}`,
    lastModified: now,
    changeFrequency: FREQUENCIES[relPath] ?? "monthly",
    priority: PRIORITIES[relPath] ?? 0.5,
  }));
}
