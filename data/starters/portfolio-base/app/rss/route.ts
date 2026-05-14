import {
  escapeXml,
  getCaseStudies,
  sortByPublishedAt,
} from "@/lib/content/case-studies";
import { siteMetadata, siteUrl } from "@/lib/site";

export function GET() {
  const itemsXml = sortByPublishedAt(getCaseStudies())
    .map((entry) => {
      const title = escapeXml(entry.metadata.title);
      const summary = escapeXml(entry.metadata.summary);
      const url = `${siteUrl}/case-studies/${entry.slug}`;
      const pubDate = new Date(entry.metadata.publishedAt).toUTCString();

      return `<item>
        <title>${title}</title>
        <link>${url}</link>
        <description>${summary}</description>
        <pubDate>${pubDate}</pubDate>
      </item>`;
    })
    .join("\n");

  const rssFeed = `<?xml version="1.0" encoding="UTF-8" ?>
  <rss version="2.0">
    <channel>
      <title>${escapeXml(siteMetadata.title)}</title>
      <link>${siteUrl}</link>
      <description>${escapeXml(siteMetadata.description)}</description>
      ${itemsXml}
    </channel>
  </rss>`;

  return new Response(rssFeed, {
    headers: {
      "Content-Type": "text/xml",
    },
  });
}
