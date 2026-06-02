"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type {
  BusinessFamilyId,
  WizardCategoryId,
} from "@/components/discovery-wizard/wizard-constants";
import { STUDIO_HREF } from "@/lib/auth-config";
import { setWizardSeed } from "@/lib/init-prompt-handoff";

/**
 * "Bygg din sida"-knapp på yrkes-landningssidorna (/for/[yrke]).
 *
 * I stället för att länka rakt till en tom studio lämnar knappen en lätt
 * starter-seed (prompttext + verksamhetsfamilj/kategori) via sessionStorage
 * och navigerar till /studio, som öppnar DiscoveryWizarden FÖRIFYLLD. All
 * kontext besökaren just läst på landningssidan följer alltså med in i
 * bygg-flödet — utan att röra själva byggandet (seed:en är bara hints).
 */
export function StarterCta({
  promptSeed,
  family,
  category,
  label = "Bygg din sida",
  tone = "dark",
}: {
  promptSeed: string;
  family: BusinessFamilyId;
  category: WizardCategoryId;
  label?: string;
  tone?: "dark" | "light";
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  function go() {
    if (busy) return;
    setBusy(true);
    setWizardSeed({ prompt: promptSeed, businessFamily: family, siteType: [category] });
    router.push(STUDIO_HREF);
  }

  const toneClasses =
    tone === "light"
      ? "bg-background text-foreground hover:bg-background/90 focus-visible:ring-background/60"
      : "bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50";

  return (
    <button
      type="button"
      onClick={go}
      disabled={busy}
      className={`inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-70 ${toneClasses}`}
    >
      {label}
    </button>
  );
}
