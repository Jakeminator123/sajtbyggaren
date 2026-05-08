import type { ScaffoldManifest } from "../types";
import { loadScaffoldFiles } from "../load-scaffold-files";

export const blogManifest: ScaffoldManifest = {
  id: "blog",
  label: "Blog",
  description:
    "Content-first blog starter with article list, post layout, author, featured posts, and reading-friendly typography.",
  siteKind: "editorial",
  complexity: "medium",
  structureProfile: "editorial-hub",
  contentProfile: "long-form-content",
  features: ["article-list", "taxonomy", "author-bio"],
  allowedBuildIntents: ["website", "template"],
  tags: [
    "blog",
    "article",
    "post",
    "content",
    "writer",
    "newsletter",
    "magazine",
    "editorial",
  ],
  promptHints: [
    "Use this scaffold for blogs, articles, editorial sites, and content-driven publications.",
    "Keep the blog rhythm: article list, post detail layout, metadata (date, author, tags), and reading-friendly typography.",
    "Modify post content, categories, and author info to fit the user's topic instead of replacing the whole structure.",
  ],
  qualityChecklist: [
    "Archive, article, and reading flow should stay intact instead of collapsing into generic landing-page sections.",
    "Metadata like author, dates, tags, and excerpts should feel editorial and topic-specific.",
    "Typography and spacing should prioritize readability and content hierarchy over decorative UI.",
  ],
  research: {
    upgradeTargets: [
      "Add topic/category filtering with dedicated archive pages and tag navigation.",
      "Add related posts, reading time, and share actions on article pages.",
      "Add newsletter CTA blocks tuned to the publication's actual niche.",
    ],
    referenceTemplates: [
      { id: "blog-notion-powered-next-js-blog", title: "Notion-Powered Next.js Blog", categorySlug: "blog", qualityScore: 94, strengths: ["verified Next.js codebase", "editorial content hierarchy", "CMS integration pattern"] },
      { id: "blog-a-next-js-14-blog-with-server-components", title: "Next.js 14 Blog with Server Components", categorySlug: "blog", qualityScore: 92, strengths: ["verified Next.js codebase", "Server Components pattern", "article layout"] },
      { id: "blog-blog-with-agility-cms-and-next-js", title: "Blog with Agility CMS and Next.js", categorySlug: "blog", qualityScore: 92, strengths: ["verified Next.js codebase", "headless CMS pattern", "blog archive structure"] },
    ],
  },
  files: loadScaffoldFiles("blog"),
};
