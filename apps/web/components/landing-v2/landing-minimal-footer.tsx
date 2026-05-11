import Link from "next/link"

export function LandingMinimalFooter() {
  return (
    <footer className="border-t border-border/40 bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-5 py-6 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-6 sm:py-5">
        <p className="text-[11px] text-muted-foreground">
          &copy; {new Date().getFullYear()} Pretty Good AB
        </p>
        <nav
          className="flex flex-wrap gap-x-6 gap-y-2 text-[11px] text-muted-foreground"
          aria-label="Sidfot"
        >
          <Link
            href="/landningssidor"
            className="inline-flex min-h-11 items-center rounded-md underline-offset-4 transition-colors duration-200 ease-out hover:text-foreground motion-reduce:transition-none"
          >
            Sajtkarta
          </Link>
          <Link
            href="/privacy"
            className="inline-flex min-h-11 items-center rounded-md underline-offset-4 transition-colors duration-200 ease-out hover:text-foreground motion-reduce:transition-none"
          >
            Integritet
          </Link>
          <Link
            href="/terms"
            className="inline-flex min-h-11 items-center rounded-md underline-offset-4 transition-colors duration-200 ease-out hover:text-foreground motion-reduce:transition-none"
          >
            Villkor
          </Link>
        </nav>
      </div>
    </footer>
  )
}
