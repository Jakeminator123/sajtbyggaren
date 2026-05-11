"use client"

import {
  useCallback,
  type MouseEvent as ReactMouseEvent,
} from "react"
import type { IntegrationItem, TechStackItem } from "@/components/landing-v2/landing-chat-data"
import { use3DTilt, useInView, usePrefersReducedMotion } from "@/components/landing-v2/landing-hooks"

export function TechStackCard({ tech, index }: { tech: TechStackItem; index: number }) {
  const { ref: tiltRef, handleMove, handleLeave } = use3DTilt(8)
  const { ref: viewRef, visible } = useInView(0.15)
  const Icon = tech.icon

  const setRefs = useCallback(
    (node: HTMLDivElement | null) => {
      tiltRef.current = node
      viewRef.current = node
    },
    [tiltRef, viewRef],
  )

  const handleMouseMove = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      const el = e.currentTarget
      const rect = el.getBoundingClientRect()
      el.style.setProperty("--glow-x", `${e.clientX - rect.left}px`)
      el.style.setProperty("--glow-y", `${e.clientY - rect.top}px`)
      handleMove(e)
    },
    [handleMove],
  )

  return (
    <div
      ref={setRefs}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleLeave}
      className={`group relative overflow-hidden rounded-2xl border border-border/20 bg-card/45 px-4 py-4 transition-all duration-700 ${
        visible ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
      }`}
      style={{
        transitionDelay: `${index * 60}ms`,
        boxShadow: visible ? "0 20px 60px hsl(var(--brand-navy) / 0.22)" : "none",
        ["--glow-x" as string]: "120px",
        ["--glow-y" as string]: "60px",
      }}
    >
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-[linear-gradient(135deg,hsl(var(--foreground)/0.04),transparent_40%,hsl(var(--primary)/0.05)_100%)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: `radial-gradient(220px circle at var(--glow-x, 120px) var(--glow-y, 60px), ${tech.glow} 0%, transparent 72%)`,
        }}
      />
      <div className="pointer-events-none absolute inset-x-6 bottom-0 h-px bg-linear-to-r from-transparent via-primary/30 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />

      <div className="relative z-10 flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-primary/15 bg-primary/8 text-primary shadow-lg shadow-primary/5 transition-all duration-300 group-hover:scale-105 group-hover:border-primary/30 group-hover:bg-primary/12">
          <Icon className="h-5 w-5" />
        </div>
        <span className="rounded-full border border-border/20 bg-background/45 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80">
          {tech.category}
        </span>
      </div>

      <div className="relative z-10 mt-5 space-y-1.5">
        <h3 className="text-sm font-(--font-heading) text-foreground transition-colors duration-300 group-hover:text-primary">
          {tech.name}
        </h3>
        <p className="text-xs leading-relaxed text-muted-foreground">{tech.detail}</p>
      </div>
    </div>
  )
}

export function IntegrationCard({ item, index }: { item: IntegrationItem; index: number }) {
  const { ref: tiltRef, handleMove, handleLeave } = use3DTilt(6)
  const { ref: viewRef, visible } = useInView(0.15)
  const reducedMotion = usePrefersReducedMotion()
  const Icon = item.icon

  const setRefs = useCallback(
    (node: HTMLDivElement | null) => {
      tiltRef.current = node
      viewRef.current = node
    },
    [tiltRef, viewRef],
  )

  const handleMouseMove = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      const el = e.currentTarget
      const rect = el.getBoundingClientRect()
      el.style.setProperty("--glow-x", `${e.clientX - rect.left}px`)
      el.style.setProperty("--glow-y", `${e.clientY - rect.top}px`)
      handleMove(e)
    },
    [handleMove],
  )

  return (
    <div
      ref={setRefs}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleLeave}
      className={`group relative overflow-hidden rounded-2xl border border-border/20 bg-card/40 p-4 transition-all duration-700 motion-reduce:transition-none ${
        visible ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
      }`}
      style={{
        transitionDelay: reducedMotion ? "0ms" : `${index * 70}ms`,
        ...(reducedMotion
          ? {}
          : { animation: `float-particle-kf ${6 + index * 0.35}s ease-in-out infinite` }),
        ["--glow-x" as string]: "120px",
        ["--glow-y" as string]: "40px",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: `radial-gradient(220px circle at var(--glow-x, 120px) var(--glow-y, 40px), ${item.glow} 0%, transparent 72%)`,
        }}
      />
      <div className="relative z-10 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-primary/15 bg-primary/8 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-(--font-heading) text-foreground">{item.name}</p>
          <p className="text-xs text-muted-foreground">{item.detail}</p>
        </div>
      </div>
    </div>
  )
}
