"use client"

import { landingJourneySteps } from "@/components/landing-v2/landing-chat-data"
import { usePrefersReducedMotion } from "@/components/landing-v2/landing-hooks"

export function HowItWorksFallback() {
  const reduceMotion = usePrefersReducedMotion()
  const pulse = reduceMotion ? "" : "animate-pulse"

  return (
    <div className="rounded-[32px] border border-border/20 bg-card/30 p-5 md:p-6 shadow-[0_24px_80px_rgba(6,10,20,0.28)]">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,420px)]">
        <div className="relative overflow-hidden rounded-[28px] border border-border/20 bg-secondary/20 min-h-[420px]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,hsl(var(--primary)/0.12),transparent_55%)]" />
          <div className="absolute inset-x-10 bottom-16 h-px bg-linear-to-r from-transparent via-primary/35 to-transparent" />
          <div className={`absolute left-[14%] top-[26%] h-28 w-28 rounded-4xl border border-primary/20 bg-primary/5 ${pulse}`} />
          <div className={`absolute left-[34%] top-[18%] h-20 w-24 rounded-3xl border border-border/20 bg-background/30 ${pulse}`} />
          <div className={`absolute left-[52%] top-[24%] h-24 w-24 rounded-full border border-primary/15 bg-primary/5 ${pulse}`} />
          <div className={`absolute right-[14%] top-[20%] h-24 w-20 rounded-3xl border border-border/20 bg-background/30 ${pulse}`} />
          <div className={`absolute right-[8%] bottom-[22%] h-24 w-28 rounded-[1.75rem] border border-primary/20 bg-primary/5 ${pulse}`} />
        </div>

        <div className="space-y-3">
          {landingJourneySteps.map((step) => (
            <div key={step.number} className="rounded-2xl border border-border/15 bg-secondary/20 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-sm font-(--font-heading) text-primary">
                  {step.number}
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-(--font-heading) text-foreground">{step.title}</p>
                  <p className="text-xs text-muted-foreground">{step.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
