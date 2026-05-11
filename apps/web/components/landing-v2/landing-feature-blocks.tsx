"use client"

import { ArrowRight, X } from "lucide-react"
import {
  useCallback,
  type MouseEvent as ReactMouseEvent,
} from "react"
import { features } from "@/components/landing-v2/landing-chat-data"
import { useInView, usePrefersReducedMotion } from "@/components/landing-v2/landing-hooks"
import { modalParticles, renderMiniShape, WireframeShape } from "@/components/landing-v2/landing-wireframe-shapes"

export type LandingFeatureItem = (typeof features)[number]

export function FeatureCard({
  feature,
  onClick,
  index = 0,
}: {
  feature: LandingFeatureItem
  onClick: () => void
  index?: number
}) {
  const { ref: scrollRef, visible: scrollVisible } = useInView(0.15)
  const Icon = feature.icon

  const handleMouse = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const rect = el.getBoundingClientRect()
    el.style.setProperty("--glow-x", `${e.clientX - rect.left}px`)
    el.style.setProperty("--glow-y", `${e.clientY - rect.top}px`)
  }, [])

  return (
    <div
      ref={scrollRef}
      className={`card-3d group relative bg-card/50 backdrop-blur-sm rounded-2xl border border-border/20 p-6 flex flex-col gap-4 hover:border-primary/20 cursor-pointer overflow-hidden transition-all duration-200 ${scrollVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}`}
      style={{ transitionDelay: `${index * 100}ms` }}
      onClick={onClick}
      onMouseMove={handleMouse}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          onClick()
          return
        }
        if (e.key === " ") {
          e.preventDefault()
          onClick()
        }
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 z-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{
          background:
            "radial-gradient(250px circle at var(--glow-x, 50%) var(--glow-y, 50%), hsl(var(--primary) / 0.07) 0%, transparent 70%)",
        }}
      />

      <div
        className="absolute -top-1 -right-1 opacity-[0.08] group-hover:opacity-[0.25] transition-opacity duration-200 pointer-events-none"
        style={{ width: 80, height: 80, perspective: 400 }}
      >
        {renderMiniShape(feature.shape)}
      </div>

      <div className="relative z-10 w-11 h-11 rounded-xl bg-primary/8 border border-primary/15 flex items-center justify-center group-hover:bg-primary/12 group-hover:border-primary/25 transition-colors">
        <Icon className="w-5 h-5 text-primary" />
      </div>
      <h3 className="relative z-10 text-base text-foreground font-(--font-heading)">
        {feature.title}
      </h3>
      <p className="relative z-10 text-sm text-muted-foreground leading-relaxed">
        {feature.description}
      </p>
      <span className="relative z-10 text-xs text-primary/60 group-hover:text-primary transition-colors mt-auto flex items-center gap-1">
        L&auml;s mer <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
      </span>

      <div className="absolute bottom-0 left-[10%] right-[10%] h-px bg-linear-to-r from-transparent via-primary/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
    </div>
  )
}

export function FeatureModal({
  feature,
  onClose,
}: {
  feature: LandingFeatureItem | null
  onClose: () => void
}) {
  const reducedMotion = usePrefersReducedMotion()
  if (!feature) return null

  const Icon = feature.icon

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-xl modal-backdrop-enter" />

      <div
        className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-card/95 backdrop-blur-2xl border border-border/30 rounded-3xl shadow-2xl modal-content-enter"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 z-30 w-9 h-9 rounded-xl bg-secondary/60 hover:bg-secondary border border-border/30 flex items-center justify-center text-muted-foreground hover:text-foreground transition-all cursor-pointer"
          aria-label="Stäng"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="relative h-52 md:h-64 overflow-hidden rounded-t-3xl bg-linear-to-b from-secondary/40 to-transparent border-b border-border/20">
          <div className="absolute inset-0 grid-background opacity-[0.15]" />
          <div className="modal-scan-line" />
          <div className="absolute inset-0 flex items-center justify-center">
            <WireframeShape variant={feature.shape} />
          </div>
          {modalParticles.map((p, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-primary/40"
              style={{
                left: `${p.x}%`,
                top: `${p.y}%`,
                ...(reducedMotion
                  ? {}
                  : {
                      animation: `float-particle-kf ${p.dur}s ease-in-out infinite`,
                      animationDelay: `${p.delay}s`,
                    }),
              }}
            />
          ))}
          <div className="absolute bottom-0 left-0 right-0 h-24 bg-linear-to-t from-card/95 to-transparent" />
        </div>

        <div className="px-7 md:px-8 pb-8 -mt-8 relative z-10">
          <div className="flex items-center gap-4 mb-5">
            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center shadow-lg shadow-primary/5">
              <Icon className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-(--font-heading) text-foreground">{feature.title}</h3>
              <p className="text-sm text-primary/70">{feature.modalSubtitle}</p>
            </div>
          </div>

          <p className="text-sm text-muted-foreground leading-relaxed mb-7">
            {feature.modalDescription}
          </p>

          <div className="space-y-3 mb-7">
            {feature.highlights.map((h, i) => (
              <div key={i} className="flex items-start gap-3 group/h">
                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-[7px] shrink-0 group-hover/h:scale-150 transition-transform" />
                <span className="text-sm text-foreground/80 leading-relaxed">{h}</span>
              </div>
            ))}
          </div>

          <div className="bg-secondary/30 border border-border/20 rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border/15">
              <div className="w-2.5 h-2.5 rounded-full bg-destructive/60" />
              <div className="w-2.5 h-2.5 rounded-full bg-chart-4/60" />
              <div className="w-2.5 h-2.5 rounded-full bg-primary/60" />
              <span className="ml-2 text-xs text-muted-foreground font-mono">{feature.codeFile}</span>
            </div>
            <pre className="p-4 text-[11px] md:text-xs font-mono text-muted-foreground leading-relaxed overflow-x-auto">
              <code>{feature.codeSnippet}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
