import * as React from "react"

import { cn } from "@/lib/utils"

// Native <details>/<summary> accordion: zero JS runtime, full keyboard
// accessibility, works without hydration. Mirrors the faq-accordion soft
// dossier pattern. Adds NO new dependency (react + cn only).

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
        "flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-left text-sm font-medium outline-none transition-colors hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-details-marker]:hidden",
        className
      )}
      {...props}
    >
      {children}
      <span
        aria-hidden="true"
        className="text-muted-foreground transition-transform duration-200 group-open:rotate-180"
      >
        &#9662;
      </span>
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
