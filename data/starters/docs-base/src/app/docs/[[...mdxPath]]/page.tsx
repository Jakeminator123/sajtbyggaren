import { generateStaticParamsFor, importPage } from "nextra/pages";

type PageProps = {
  params: Promise<{
    mdxPath?: string[];
  }>;
};

export const generateStaticParams = generateStaticParamsFor("mdxPath");

export async function generateMetadata({ params }: PageProps) {
  const { mdxPath } = await params;
  const { metadata } = await importPage(mdxPath);

  return metadata;
}

export default async function Page(props: PageProps) {
  const params = await props.params;
  const { default: MDXContent } = await importPage(params.mdxPath);

  return (
    <article
      className="mx-auto max-w-3xl px-6 py-12"
      data-docs-content
      data-pagefind-body
    >
      <MDXContent {...props} params={params} />
    </article>
  );
}
