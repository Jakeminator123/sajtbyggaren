import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { Head, Search } from "nextra/components";
import "nextra-theme-docs/style.css";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Course documentation starter",
    template: "%s - Course documentation starter",
  },
  description: "Neutral Nextra starter for course and education scaffolds.",
  applicationName: "docs-base",
  generator: "Next.js",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head faviconGlyph="✦" />
      <body className="min-h-screen">
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('docs-base-theme')||((matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light');document.documentElement.classList.toggle('dark',t==='dark');document.documentElement.style.colorScheme=t}catch(e){}",
          }}
        />
        <header className="border-border bg-background/95 supports-[backdrop-filter]:bg-background/75 sticky top-0 z-40 border-b backdrop-blur">
          <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4">
            <Link className="font-semibold tracking-tight" href="/">
              Course documentation
            </Link>
            <nav className="text-muted-foreground hidden items-center gap-4 text-sm md:flex">
              <Link className="hover:text-foreground" href="/docs">
                Docs
              </Link>
            </nav>
            <div className="ml-auto flex items-center gap-3">
              <div className="hidden w-64 md:block">
                <Search placeholder="Search docs…" />
              </div>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <div className="mx-auto grid max-w-7xl grid-cols-1 md:grid-cols-[16rem_minmax(0,1fr)]">
          <aside className="border-border bg-background/80 hidden min-h-[calc(100vh-4rem)] border-r p-6 md:block">
            <nav className="space-y-1 text-sm">
              <p className="text-muted-foreground mb-3 text-xs font-medium tracking-wide uppercase">
                Documentation
              </p>
              <Link
                className="hover:bg-muted block rounded-md px-3 py-2"
                href="/docs"
              >
                Overview
              </Link>
              <Link
                className="hover:bg-muted block rounded-md px-3 py-2"
                href="/docs/course-shell"
              >
                Course shell
              </Link>
              <Link
                className="hover:bg-muted block rounded-md px-3 py-2"
                href="/docs/authoring"
              >
                Authoring
              </Link>
              <Link
                className="hover:bg-muted block rounded-md px-3 py-2"
                href="/docs/scaffold-slots"
              >
                Scaffold slots
              </Link>
            </nav>
          </aside>
          <div className="min-w-0">{children}</div>
        </div>
        <footer className="border-border text-muted-foreground border-t px-4 py-6 text-center text-sm">
          Neutral course documentation starter.
        </footer>
      </body>
    </html>
  );
}
