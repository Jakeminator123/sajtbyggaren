"use client";

import {
  ChevronDown,
  Image as ImageIcon,
  MapPin,
  Quote,
  ShieldCheck,
  Star,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * ModuleMockup — wireframe-miniatyrer av section_add-modulerna.
 * Används av PreviewInspectorOverlay i drag-läget (operatörskrav
 * 2026-06-10): i stället för en etikett-bricka ska ghost:en som följer
 * pekaren visa UNGEFÄR hur sektionen kommer se ut, och efter släpp
 * dockas mockupen i full bredd vid insättningslinjen som en
 * förhandsvisning på plats.
 *
 * MEDVETET generiska gråskale-wireframes (bg-muted-tonerna): mockupen
 * lovar layoutens FORM, inte sajtens färger/typografi/innehåll — det
 * exakta utseendet bestäms av sajtens tema först när bygget kört.
 * Nycklarna speglar MODULE_CATALOG-id:na i add-module-dialog.tsx; okänt
 * id faller tillbaka till en neutral sektionsskiss så nya moduler
 * aldrig kraschar ghost-rendreringen.
 */

/** Skeleton-textrad. */
function Bar({ className }: { className?: string }) {
  return (
    <div
      className={cn("bg-muted-foreground/25 h-1.5 rounded-full", className)}
    />
  );
}

/** Skeleton-yta (bild/kort/input). */
function Box({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "bg-muted-foreground/15 flex items-center justify-center rounded",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Centrerad sektionsrubrik-skeleton. */
function Heading() {
  return (
    <div className="mb-2 flex flex-col items-center gap-1">
      <Bar className="h-2 w-1/3" />
      <Bar className="w-1/2 opacity-60" />
    </div>
  );
}

function GalleryMockup() {
  return (
    <div>
      <Heading />
      <div className="grid grid-cols-3 gap-1.5">
        {Array.from({ length: 6 }).map((_, i) => (
          <Box key={i} className="aspect-[4/3]">
            <ImageIcon
              className="text-muted-foreground/50 h-3.5 w-3.5"
              aria-hidden
            />
          </Box>
        ))}
      </div>
    </div>
  );
}

function ContactFormMockup() {
  return (
    <div>
      <Heading />
      <div className="flex flex-col gap-1.5">
        <div className="grid grid-cols-2 gap-1.5">
          <Box className="h-5" />
          <Box className="h-5" />
        </div>
        <Box className="h-10" />
        <div className="bg-foreground/70 mt-0.5 ml-auto h-5 w-16 rounded" />
      </div>
    </div>
  );
}

function FaqMockup() {
  return (
    <div>
      <Heading />
      <div className="flex flex-col gap-1.5">
        {["w-3/4", "w-2/3", "w-4/5"].map((w, i) => (
          <div
            key={i}
            className="border-border/60 flex items-center justify-between rounded border px-2 py-1.5"
          >
            <Bar className={w} />
            <ChevronDown
              className="text-muted-foreground/60 h-3 w-3 shrink-0"
              aria-hidden
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function TestimonialsMockup() {
  return (
    <div>
      <Heading />
      <div className="grid grid-cols-2 gap-1.5">
        {Array.from({ length: 2 }).map((_, i) => (
          <div
            key={i}
            className="border-border/60 flex flex-col gap-1.5 rounded border p-2"
          >
            <Quote
              className="text-muted-foreground/50 h-3 w-3"
              aria-hidden
            />
            <Bar className="w-full" />
            <Bar className="w-5/6" />
            <div className="mt-0.5 flex items-center gap-1.5">
              <div className="bg-muted-foreground/25 h-3.5 w-3.5 shrink-0 rounded-full" />
              <Bar className="w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PricingMockup() {
  return (
    <div>
      <Heading />
      <div className="grid grid-cols-3 gap-1.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "flex flex-col items-center gap-1.5 rounded border p-2",
              i === 1 ? "border-foreground/40" : "border-border/60",
            )}
          >
            <Bar className="w-2/3" />
            <Bar className="h-2.5 w-1/2" />
            <Bar className="w-full opacity-60" />
            <Bar className="w-5/6 opacity-60" />
            <div className="bg-foreground/70 mt-0.5 h-4 w-full rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

function MapMockup() {
  return (
    <div>
      <Heading />
      <Box className="h-20">
        <MapPin className="text-muted-foreground/60 h-5 w-5" aria-hidden />
      </Box>
      <div className="mt-1.5 flex justify-center">
        <Bar className="w-1/2" />
      </div>
    </div>
  );
}

function OpeningHoursMockup() {
  return (
    <div>
      <Heading />
      <div className="flex flex-col gap-1.5">
        {["w-16", "w-14", "w-16", "w-12"].map((w, i) => (
          <div key={i} className="flex items-center justify-between">
            <Bar className={w} />
            <Bar className="w-20 opacity-60" />
          </div>
        ))}
      </div>
    </div>
  );
}

function TeamMockup() {
  return (
    <div>
      <Heading />
      <div className="grid grid-cols-3 gap-1.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div className="bg-muted-foreground/20 h-8 w-8 rounded-full" />
            <Bar className="w-3/4" />
            <Bar className="w-1/2 opacity-60" />
          </div>
        ))}
      </div>
    </div>
  );
}

function TrustBadgesMockup() {
  return (
    <div>
      <Heading />
      <div className="flex items-start justify-center gap-3">
        {[ShieldCheck, Star, ShieldCheck, Star].map((Icon, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div className="border-border/60 flex h-8 w-8 items-center justify-center rounded-full border">
              <Icon
                className="text-muted-foreground/60 h-3.5 w-3.5"
                aria-hidden
              />
            </div>
            <Bar className="w-8" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Neutral fallback för okända modul-id:n. */
function GenericSectionMockup() {
  return (
    <div>
      <Heading />
      <div className="flex flex-col gap-1.5">
        <Bar className="w-full" />
        <Bar className="w-5/6" />
        <Bar className="w-2/3" />
      </div>
    </div>
  );
}

const MOCKUPS: Record<string, () => React.ReactElement> = {
  gallery: GalleryMockup,
  "contact-form": ContactFormMockup,
  faq: FaqMockup,
  testimonials: TestimonialsMockup,
  pricing: PricingMockup,
  map: MapMockup,
  "opening-hours": OpeningHoursMockup,
  team: TeamMockup,
  "trust-badges": TrustBadgesMockup,
};

export function ModuleMockup({
  moduleId,
  className,
}: {
  moduleId: string;
  className?: string;
}) {
  const Body = MOCKUPS[moduleId] ?? GenericSectionMockup;
  return (
    <div
      aria-hidden
      className={cn(
        "border-border/70 bg-background rounded-lg border p-3 shadow-xl",
        className,
      )}
    >
      <Body />
    </div>
  );
}
