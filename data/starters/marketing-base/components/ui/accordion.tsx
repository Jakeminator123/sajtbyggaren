import * as React from "react"

import { cn } from "@/lib/utils"

// Native <details>/<summary> accordion: zero JS runtime, full keyboard
// accessibility, works without hydration. Mirrors the faq-accordion soft
// dossier pattern. Adds NO new dependency (react + cn only).
//
// Upgraded 2026-06-12 (Component Catalog lager 3, ADR 0040/0054 pilot): curated
// from the shadcn intake candidate in data/component-candidates/accordion/.
// The chevron is now an inline SVG (matching the base-nova shadcn accordion)
// instead of an HTML entity, and the trigger uses the refined ring-2/offset
// focus-visible treatment. The component API (Accordion / AccordionItem /
// AccordionTrigger / AccordionContent) is unchanged and stays zero-dependency.

function Accordion({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="accordion"
      className={cn("divide-y divide-border overflow-hidden rounded-lg border", className)}
      {...props}
    />
  )
}

function AccordionItem({ className, ...props }: React.ComponentProps<"details">) {
  return (
    <details
      data-slot="accordion-item"
      className={cn("group border-b last:border-b-0", className)}
      {...props}
    />
  )
}

function AccordionTrigger({
  className,
  children,
  ...props
}: React.ComponentProps<"summary">) {
  return (
    <summary
      data-slot="accordion-trigger"
      className={cn(
        "flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-left text-sm font-medium outline-none transition-colors hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 [&::-webkit-details-marker]:hidden",
        className
      )}
      {...props}
    >
      {children}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-180"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </summary>
  )
}

function AccordionContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="accordion-content"
      className={cn("px-4 pb-3 text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
