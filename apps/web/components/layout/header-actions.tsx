"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SiteNavMenu } from "./site-nav-menu";

/**
 * Header-actions för apps/web.
 *
 * apps/web är ren marknadsföring/UI utan auth eller builder-flöde
 * (se governance/decisions/0018-apps-web-import.md). Tidigare versioner
 * av denna komponent renderade "Logga in" och "Kom igång gratis" som
 * triggade auth-modaler — dessa hooks finns inte i apps/web. Knapparna
 * pekar därför mot publika sidor istället.
 */
export function HeaderActions() {
  return (
    <div className="flex items-center gap-2">
      <Button
        asChild
        variant="outline"
        size="sm"
        className="border-primary/30 text-primary hover:bg-primary/10 hover:text-primary"
      >
        <Link href="/priser">Se priser</Link>
      </Button>
      <SiteNavMenu />
    </div>
  );
}
