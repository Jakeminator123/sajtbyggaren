import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Textarea — wrappar `<textarea>` med projektets default-styling.
 *
 * `ref` destruktureras explicit och vidarebefordras till underliggande
 * `<textarea>` så callers kan flytta DOM-focus programmatiskt (t.ex.
 * `composerRef` i FloatingChat som auto-fokuserar fältet när panelen
 * expanderas från minimerat läge). I React 19 är `ref` en vanlig prop
 * för funktionskomponenter, men att förlita sig på att `{...props}`-
 * spread implicit propsar `ref` är fragilt — framtida React-uppgraderingar
 * eller refaktorer av `React.ComponentProps`-typningen kan tysta bryta
 * ref-vidarebefordran. Explicit destruktur + bindning eliminerar tvivlet.
 */
function Textarea({
  className,
  ref,
  ...props
}: React.ComponentProps<"textarea">) {
  return (
    <textarea
      ref={ref}
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-lg border border-input bg-card px-2.5 py-2 text-base transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
