import { Badge } from "@/components/ui/badge";
import { BlogCard } from "@/components/blog-card";
import Link from "next/link";

const posts = [
  {
    slug: "getting-started-with-content",
    title: "Getting started with content-first design",
    excerpt: "How to structure a blog for readability and engagement.",
    date: "2026-03-10",
    author: "Alex",
    category: "Design",
  },
  {
    slug: "typography-for-readers",
    title: "Typography choices that make readers stay",
    excerpt: "Font sizes, line heights, and spacing for long-form content.",
    date: "2026-03-08",
    author: "Alex",
    category: "Design",
  },
  {
    slug: "building-a-blog",
    title: "Building a blog from scratch",
    excerpt: "A step-by-step guide to setting up a modern blog.",
    date: "2026-03-05",
    author: "Alex",
    category: "Tutorial",
  },
];

export default function BlogPage() {
  return (
    <div className="px-6 py-16 sm:px-8 sm:py-20">
      <div className="mx-auto max-w-4xl space-y-12">
        <div className="space-y-3">
          <Badge variant="secondary" className="rounded-full">All posts</Badge>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Blog</h1>
          <p className="text-muted-foreground">
            Articles, updates, and thoughts. Replace the placeholder content with your own posts.
          </p>
        </div>

        <div className="space-y-4">
          {posts.map((post) => (
            <BlogCard key={post.slug} {...post} />
          ))}
        </div>

        <div className="flex justify-center">
          <Link
            href="/"
            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
