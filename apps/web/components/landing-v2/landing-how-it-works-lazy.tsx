"use client"

import { useRef } from "react"
import type { landingJourneySteps } from "@/components/landing-v2/landing-chat-data"
import { HowItWorksFallback } from "@/components/landing-v2/landing-how-it-works-fallback"

type Steps = typeof landingJourneySteps

/**
 * apps/web tar inte med Three.js (`@react-three/fiber`, `three`).
 * Originalets lazy-laddade WebGL-scen ersätts av den statiska fallbacken
 * tills vi väljer att inkludera 3D-stack i apps/web.
 */
export function HowItWorksLazy({ steps }: { steps: Steps }) {
  const ref = useRef<HTMLDivElement>(null)
  // steps consumed by HowItWorksFallback via direct import; arg accepted
  // here for API parity with originalet.
  void steps;
  return (
    <div ref={ref}>
      <HowItWorksFallback />
    </div>
  )
}
