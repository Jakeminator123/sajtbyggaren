"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ChevronRight, Menu } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

type NavLink = { href: string; label: string };

type NavGroup = {
  title: string;
  links: NavLink[];
};

const navGroups: NavGroup[] = [
  {
    title: "Bygg",
    links: [
      { href: "/", label: "Skapa" },
      { href: "/templates", label: "Mallar" },
    ],
  },
  {
    title: "Utforska",
    links: [
      { href: "/#funktioner", label: "Funktioner" },
      { href: "/#teknik", label: "Teknik" },
    ],
  },
  {
    title: "Hjälp & info",
    links: [
      { href: "/buy-credits", label: "Priser" },
      { href: "/faq", label: "FAQ" },
      { href: "/om", label: "Om oss" },
    ],
  },
  {
    title: "Juridik",
    links: [
      { href: "/privacy", label: "Integritet" },
      { href: "/terms", label: "Villkor" },
    ],
  },
];

function NavSection({
  group,
  pathname,
  onNavigate,
}: {
  group: NavGroup;
  pathname: string;
  onNavigate: () => void;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70 transition-colors hover:text-foreground"
      >
        {group.title}
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-200",
            expanded && "rotate-90",
          )}
        />
      </button>

      {expanded && (
        <div className="flex flex-col gap-0.5 pb-1">
          {group.links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={onNavigate}
              className={cn(
                "rounded-md px-3 py-2 pl-6 text-sm transition-colors",
                pathname === link.href
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground",
              )}
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function SiteNavMenu() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="text-foreground/70 hover:text-foreground"
          aria-label="Meny"
        >
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-72 border-border bg-card">
        <SheetHeader className="pb-4">
          <SheetTitle className="text-left text-sm font-medium text-foreground">
            Meny
          </SheetTitle>
        </SheetHeader>
        <nav className="flex flex-col gap-1">
          {navGroups.map((group) => (
            <NavSection
              key={group.title}
              group={group}
              pathname={pathname}
              onNavigate={() => setOpen(false)}
            />
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
