import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowRight, BookOpen } from "lucide-react";
import { BlogCard } from "@/components/blog-card";
import Link from "next/link";

const featured = [
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
];

const recent = [
  {
    slug: "building-a-blog",
    title: "Building a blog from scratch",
    excerpt: "A step-by-step guide to setting up a modern blog.",
    date: "2026-03-05",
    author: "Alex",
    category: "Tutorial",
  },
];

export default function HomePage() {
  return (
    <div className="px-6 py-16 sm:px-8 sm:py-20">
      <div className="mx-auto max-w-6xl space-y-16">
        <section className="space-y-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="space-y-3">
              <Badge className="rounded-full px-3 py-1">Blog starter</Badge>
              <h1 className="max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
                A blog with clear structure for articles and reading
              </h1>
              <p className="max-w-xl text-lg text-muted-foreground">
                This scaffold gives you a home page with featured posts, an article list, and a post detail layout.
                Adapt the content and categories to your topic.
              </p>
            </div>
            <Button asChild size="lg" className="rounded-full px-6">
              <Link href="/blog">
                View all posts <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {featured.map((post) => (
              <BlogCard key={post.slug} {...post} featured />
            ))}
          </div>
        </section>

        <section className="space-y-6">
          <div className="flex items-center gap-3">
            <BookOpen className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-semibold tracking-tight">Recent posts</h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((post) => (
              <BlogCard key={post.slug} {...post} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
