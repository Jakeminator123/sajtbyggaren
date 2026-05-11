import Link from "next/link";

export function MinimalFooter() {
  return (
    <footer className="border-t border-border/30 bg-background">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <Link href="/" className="text-sm font-medium text-foreground/80 transition-colors hover:text-foreground">
          Sajtmaskin
        </Link>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <Link href="/landningssidor" className="transition-colors hover:text-foreground">
            Sajtkarta
          </Link>
          <Link href="/privacy" className="transition-colors hover:text-foreground">
            Integritet
          </Link>
          <Link href="/terms" className="transition-colors hover:text-foreground">
            Villkor
          </Link>
          <span className="text-muted-foreground/50">
            &copy; {new Date().getFullYear()} Pretty Good AB
          </span>
        </div>
      </div>
    </footer>
  );
}
