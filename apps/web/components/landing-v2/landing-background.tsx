"use client"

import type { LandingController } from "@/components/landing-v2/use-landing-controller"
import { isTemplateEntryMode } from "@/lib/builder/build-intent"

export type LandingBackgroundProps = Pick<
  LandingController,
  "selectedCategory" | "isAuditMode" | "activeCategory"
>

const NOISE_BG = `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`

/** Maps hero input mode to background tint (ids from `landing-chat-data` `categories`). */
export function landingBackgroundSemanticMode(
  selectedCategory: string | null,
  isAuditMode: boolean,
  activeCategory: LandingController["activeCategory"],
): "fritext" | "template" | "audit" | "analyserad" {
  const id = selectedCategory ?? activeCategory?.id ?? "fritext"
  if (isAuditMode || id === "audit") return "audit"
  if (isTemplateEntryMode(id)) return "template"
  if (id === "analyserad") return "analyserad"
  return "fritext"
}

export function LandingBackground({
  selectedCategory,
  isAuditMode,
  activeCategory,
}: LandingBackgroundProps) {
  const mode = landingBackgroundSemanticMode(selectedCategory, isAuditMode, activeCategory)

  return (
    <div className="landing-chat-bg pointer-events-none absolute inset-0 z-0" aria-hidden>
      <div className="absolute inset-0 bg-background" />
      <div
        className="absolute inset-0 overflow-hidden opacity-90 motion-reduce:opacity-95"
        data-landing-bg={mode}
      >
        <div className="shader-orb shader-orb-1" />
        <div className="shader-orb shader-orb-2" />
        <div className="shader-orb shader-orb-3" />
      </div>
      <div className="landing-chat-bg-grid grid-background absolute inset-0 opacity-[0.05] motion-reduce:opacity-[0.035]" />
      <div
        className="landing-chat-bg-noise absolute inset-0 opacity-[0.03] mix-blend-soft-light pointer-events-none"
        style={{ backgroundImage: NOISE_BG }}
      />
    </div>
  )
}
