import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CustomMDX } from "@/components/mdx";
import { formatDate, getCaseStudies } from "@/lib/content/case-studies";
import { siteMetadata, siteUrl } from "@/lib/site";

type PageProps = {
  params: Promise<{
    slug: string;
  }>;
};

function getOgImage(title: string, image?: string): string {
  if (image) {
    return image.startsWith("http") ? image : `${siteUrl}${image}`;
  }

  return `${siteUrl}/og?title=${encodeURIComponent(title)}`;
}

export function generateStaticParams() {
  return getCaseStudies().map((entry) => ({
    slug: entry.slug,
  }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const entry = getCaseStudies().find((caseStudy) => caseStudy.slug === slug);

  if (!entry) {
    return {};
  }

  const { title, publishedAt, summary, image } = entry.metadata;
  const ogImage = getOgImage(title, image);

  return {
    title,
    description: summary,
    openGraph: {
      title,
      description: summary,
      type: "article",
      publishedTime: publishedAt,
      url: `${siteUrl}/case-studies/${entry.slug}`,
      images: [
        {
          url: ogImage,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description: summary,
      images: [ogImage],
    },
  };
}

export default async function CaseStudyPage({ params }: PageProps) {
  const { slug } = await params;
  const entry = getCaseStudies().find((caseStudy) => caseStudy.slug === slug);

  if (!entry) {
    notFound();
  }

  const ogImage = getOgImage(entry.metadata.title, entry.metadata.image);

  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "CreativeWork",
            headline: entry.metadata.title,
            datePublished: entry.metadata.publishedAt,
            dateModified: entry.metadata.publishedAt,
            description: entry.metadata.summary,
            image: ogImage,
            url: `${siteUrl}/case-studies/${entry.slug}`,
            author: {
              "@type": "Organization",
              name: siteMetadata.title,
            },
          }),
        }}
      />
      <article className="prose">
        <header className="mb-8">
          <h1 className="title text-3xl font-semibold tracking-tight">
            {entry.metadata.title}
          </h1>
          <p className="text-muted-foreground mt-2 text-sm">
            {formatDate(entry.metadata.publishedAt)}
          </p>
        </header>
        <CustomMDX source={entry.content} />
      </article>
    </main>
  );
}
