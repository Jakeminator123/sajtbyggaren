import Link from "next/link";

export default function IndexPage() {
  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col justify-center px-6 py-24 text-center">
      <p className="text-muted-foreground text-sm font-medium tracking-wide uppercase">
        docs-base
      </p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-balance md:text-5xl">
        Neutral foundation for course documentation
      </h1>
      <p className="text-muted-foreground mt-6 text-lg leading-8 text-balance">
        A Nextra starter with markdown content, sidebar navigation, search, and
        light or dark mode ready for scaffold injection.
      </p>
      <div className="mt-8">
        <Link
          href="/docs"
          className="border-border bg-background text-foreground hover:bg-muted inline-flex items-center rounded-md border px-4 py-2 text-sm font-medium transition-colors"
        >
          Open documentation
        </Link>
      </div>
    </main>
  );
}
