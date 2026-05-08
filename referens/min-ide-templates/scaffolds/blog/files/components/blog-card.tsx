import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

type BlogCardProps = {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  author: string;
  category: string;
  featured?: boolean;
};

export function BlogCard({ slug, title, excerpt, date, author, category, featured }: BlogCardProps) {
  return (
    <Link href={`/blog/${slug}`}>
      <Card
        className={`overflow-hidden transition-all hover:border-primary/30 hover:shadow-md ${featured ? "rounded-2xl" : "rounded-xl"}`}
      >
        <CardContent className={`space-y-4 ${featured ? "p-6" : "p-5"}`}>
          <div className="flex items-center justify-between gap-3">
            <Badge variant="secondary" className="rounded-full">{category}</Badge>
            <span className="text-xs text-muted-foreground">{date}</span>
          </div>
          <div className="space-y-2">
            <h2 className={`font-semibold tracking-tight ${featured ? "text-xl" : "text-lg"}`}>
              {title}
            </h2>
            <p className="text-sm text-muted-foreground line-clamp-2">{excerpt}</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{author}</span>
            <ArrowUpRight className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
