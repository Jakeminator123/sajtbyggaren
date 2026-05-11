"use client"

import { useId, useMemo } from "react"
import type { ComparisonMethod, ComparisonParameter, ComparisonScenario } from "@/components/landing-v2/landing-chat-data"
import { useInView } from "@/components/landing-v2/landing-hooks"

const RADAR_CX = 150
const RADAR_CY = 150
const RADAR_MAX_R = 105
const RADAR_RINGS = [25, 50, 75, 100]

function radarPoint(index: number, score: number, n: number) {
  const angle = (2 * Math.PI * index) / n - Math.PI / 2
  const r = (score / 100) * RADAR_MAX_R
  return {
    x: Math.round((RADAR_CX + r * Math.cos(angle)) * 10) / 10,
    y: Math.round((RADAR_CY + r * Math.sin(angle)) * 10) / 10,
  }
}

function buildRadarPath(m: ComparisonMethod, params: ComparisonParameter[], n: number) {
  return (
    params
      .map((p, i) => {
        const pt = radarPoint(i, m.scores[p.key], n)
        return `${i === 0 ? "M" : "L"}${pt.x},${pt.y}`
      })
      .join("") + "Z"
  )
}

const radarCenterPath = Array.from({ length: 10 })
  .map((_, i) => `${i === 0 ? "M" : "L"}${RADAR_CX},${RADAR_CY}`)
  .join("") + "Z"

export function ComparisonRadarChart({
  method,
  wpMethod,
  parameters,
  scenario,
}: {
  method: ComparisonMethod
  wpMethod: ComparisonMethod
  parameters: ComparisonParameter[]
  scenario: ComparisonScenario
}) {
  const rawId = useId()
  const gradId = rawId.replace(/:/g, "")
  const methodFillId = `radar-method-fill-${gradId}`
  const wpFillId = `radar-wp-fill-${gradId}`

  const { ref, visible } = useInView(0.15)
  const n = parameters.length

  const methodPath = useMemo(() => buildRadarPath(method, parameters, n), [method, parameters, n])
  const wpPath = useMemo(() => buildRadarPath(wpMethod, parameters, n), [wpMethod, parameters, n])

  const labelPositions = useMemo(
    () =>
      parameters.map((_, i) => {
        const angle = (2 * Math.PI * i) / n - Math.PI / 2
        const labelR = RADAR_MAX_R + 22
        const x = Math.round((RADAR_CX + labelR * Math.cos(angle)) * 10) / 10
        const y = Math.round((RADAR_CY + labelR * Math.sin(angle)) * 10) / 10
        const cos = Math.cos(angle)
        const anchor: "start" | "middle" | "end" =
          Math.abs(cos) < 0.15 ? "middle" : cos > 0 ? "start" : "end"
        return { x, y, anchor }
      }),
    [parameters, n],
  )

  const transition = "0.8s cubic-bezier(0.4,0,0.2,1)"

  return (
    <div ref={ref} className="relative">
      <div
        className="transition-all duration-700"
        style={{ opacity: visible ? 1 : 0, transform: visible ? "scale(1)" : "scale(0.85)" }}
      >
        <svg viewBox="0 0 300 300" className="w-full max-w-[380px] mx-auto" overflow="visible">
          <defs>
            <radialGradient id={methodFillId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="oklch(0.72 0.15 192 / 0.22)" />
              <stop offset="100%" stopColor="oklch(0.72 0.15 192 / 0.06)" />
            </radialGradient>
            <radialGradient id={wpFillId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="oklch(0.5 0 0 / 0.1)" />
              <stop offset="100%" stopColor="oklch(0.5 0 0 / 0.03)" />
            </radialGradient>
          </defs>

          {RADAR_RINGS.map((pct) => (
            <circle
              key={pct}
              cx={RADAR_CX}
              cy={RADAR_CY}
              r={Math.round((pct / 100) * RADAR_MAX_R * 10) / 10}
              fill="none"
              stroke="oklch(0.25 0 0)"
              strokeWidth={pct === 100 ? "0.7" : "0.35"}
              strokeDasharray={pct < 100 ? "2 4" : undefined}
            />
          ))}

          {parameters.map((_, i) => {
            const pt = radarPoint(i, 100, n)
            return <line key={i} x1={RADAR_CX} y1={RADAR_CY} x2={pt.x} y2={pt.y} stroke="oklch(0.25 0 0)" strokeWidth="0.35" />
          })}

          <path
            d={visible ? wpPath : radarCenterPath}
            fill={`url(#${wpFillId})`}
            stroke="oklch(0.5 0 0 / 0.3)"
            strokeWidth="1"
            style={{ transition: `d ${transition}` }}
          />
          <path
            d={visible ? methodPath : radarCenterPath}
            fill={`url(#${methodFillId})`}
            stroke="oklch(0.72 0.15 192 / 0.7)"
            strokeWidth="1.5"
            style={{ transition: `d ${transition}` }}
          />

          {parameters.map((p, i) => {
            const pt = visible ? radarPoint(i, method.scores[p.key], n) : { x: RADAR_CX, y: RADAR_CY }
            return (
              <circle
                key={p.key}
                cx={pt.x}
                cy={pt.y}
                r="2.5"
                fill="oklch(0.72 0.15 192)"
                stroke="oklch(0.08 0 0)"
                strokeWidth="1.2"
                style={{ transition: `cx ${transition}, cy ${transition}` }}
              />
            )
          })}

          {parameters.map((p, i) => {
            const pos = labelPositions[i]
            const weight = scenario.weights[p.key]
            return (
              <text key={p.key} x={pos.x} y={pos.y} textAnchor={pos.anchor} dominantBaseline="middle" style={{ fontSize: "7.5px" }}>
                <tspan className="fill-muted-foreground/70">{p.label}</tspan>
                <tspan className="fill-muted-foreground/35" dx="3" style={{ fontSize: "6px" }}>
                  ×{weight}
                </tspan>
              </text>
            )
          })}

        </svg>
      </div>
    </div>
  )
}
