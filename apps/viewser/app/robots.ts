import type { MetadataRoute } from "next";

// Robots-policy: indexera marknadssajten, men håll konsolen (/studio) och
// alla /api-routes utanför sökmotorer (localhost-bundna, 403:ar i produktion).
const SITE_URL = "https://sajtbyggaren.se";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/studio", "/api/"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
