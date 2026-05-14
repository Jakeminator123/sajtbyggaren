import Link from "next/link";

import {
  formatDate,
  getCaseStudies,
  sortByPublishedAt,
} from "@/lib/content/case-studies";

export function CaseStudyList() {
  const caseStudies = sortByPublishedAt(getCaseStudies());

  if (caseStudies.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {caseStudies.map((entry) => (
        <Link
          key={entry.slug}
          className="border-border hover:bg-muted block rounded-lg border p-4 transition-colors"
          href={`/case-studies/${entry.slug}`}
        >
          <div className="flex flex-col gap-1">
            <p className="text-muted-foreground text-sm">
              {formatDate(entry.metadata.publishedAt)}
            </p>
            <h2 className="text-lg font-medium tracking-tight">
              {entry.metadata.title}
            </h2>
            <p className="text-muted-foreground text-sm">
              {entry.metadata.summary}
            </p>
          </div>
        </Link>
      ))}
    </div>
  );
}
