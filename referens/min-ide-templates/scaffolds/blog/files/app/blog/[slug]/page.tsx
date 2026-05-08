import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { notFound } from "next/navigation";

const posts: Record<string, { title: string; excerpt: string; date: string; author: string; category: string; body: string }> = {
  "getting-started-with-content": {
    title: "Getting started with content-first design",
    excerpt: "How to structure a blog for readability and engagement.",
    date: "2026-03-10",
    author: "Alex",
    category: "Design",
    body: "This is a placeholder for the full article body. Replace with real content. The scaffold provides a structure for metadata (date, author, category), a main heading, and a prose area for the article body.",
  },
  "typography-for-readers": {
    title: "Typography choices that make readers stay",
    excerpt: "Font sizes, line heights, and spacing for long-form content.",
    date: "2026-03-08",
    author: "Alex",
    category: "Design",
    body: "Placeholder content. Use this layout to structure your post: title, metadata, and a readable body. Add prose classes for typography.",
  },
  "building-a-blog": {
    title: "Building a blog from scratch",
    excerpt: "A step-by-step guide to setting up a modern blog.",
    date: "2026-03-05",
    author: "Alex",
    category: "Tutorial",
    body: "Placeholder. Replace with your article content. Keep the metadata structure and layout.",
  },
};

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = posts[slug];

  if (!post) {
    notFound();
  }

  return (
    <article className="px-6 py-16 sm:px-8 sm:py-20">
      <div className="mx-auto max-w-2xl space-y-8">
        <div className="space-y-4">
          <Link
            href="/blog"
            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to blog
          </Link>
          <Badge variant="secondary" className="rounded-full">{post.category}</Badge>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{post.title}</h1>
          <p className="text-muted-foreground">
            {post.date} · {post.author}
          </p>
        </div>

        <div className="space-y-4 rounded-3xl border bg-card/60 p-6">
          <p className="text-lg leading-8">{post.body}</p>
        </div>
      </div>
    </article>
  );
}
