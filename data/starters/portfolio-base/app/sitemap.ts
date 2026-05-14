import type { MetadataRoute } from "next";

import { getCaseStudies } from "@/lib/content/case-studies";
import { siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const caseStudies = getCaseStudies().map((entry) => ({
    url: `${siteUrl}/case-studies/${entry.slug}`,
    lastModified: entry.metadata.publishedAt,
  }));

  const staticRoutes = ["", "/portfolio", "/case-studies", "/about"].map(
    (route) => ({
      url: `${siteUrl}${route}`,
      lastModified: new Date().toISOString().split("T")[0],
    }),
  );

  return [...staticRoutes, ...caseStudies];
}
