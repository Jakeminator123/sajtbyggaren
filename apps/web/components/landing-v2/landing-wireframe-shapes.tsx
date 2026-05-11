"use client"

import type { ReactNode } from "react"
import type { ShapeVariant } from "@/components/landing-v2/landing-chat-data"

export const modalParticles = [
  { x: 22, y: 28, dur: 4.2, delay: -1.3 },
  { x: 72, y: 18, dur: 3.7, delay: -0.5 },
  { x: 38, y: 72, dur: 5.1, delay: -2.4 },
  { x: 58, y: 35, dur: 3.9, delay: -1.8 },
  { x: 28, y: 58, dur: 4.5, delay: -3.1 },
  { x: 78, y: 62, dur: 3.3, delay: -0.9 },
  { x: 48, y: 22, dur: 4.8, delay: -2.7 },
  { x: 65, y: 78, dur: 3.6, delay: -1.6 },
]

type MeshProps = { size: number; className: string; borderOpacity?: number }

function CubeMesh({ size, className, borderOpacity = 0.2 }: MeshProps) {
  const half = size / 2
  const face = (transform: string) => ({
    position: "absolute" as const,
    width: size,
    height: size,
    border: `1px solid oklch(0.72 0.15 192 / ${borderOpacity})`,
    background: `oklch(0.72 0.15 192 / 0.02)`,
    transform,
  })
  return (
    <div
      className={className}
      style={{
        width: size, height: size,
        transformStyle: "preserve-3d" as const,
        position: "absolute" as const,
        left: "50%", top: "50%",
        marginLeft: -half, marginTop: -half,
      }}
    >
      <div style={face(`translateZ(${half}px)`)} />
      <div style={face(`rotateY(180deg) translateZ(${half}px)`)} />
      <div style={face(`rotateY(90deg) translateZ(${half}px)`)} />
      <div style={face(`rotateY(-90deg) translateZ(${half}px)`)} />
      <div style={face(`rotateX(90deg) translateZ(${half}px)`)} />
      <div style={face(`rotateX(-90deg) translateZ(${half}px)`)} />
    </div>
  )
}

function SphereMesh({ size, className, borderOpacity = 0.2 }: MeshProps) {
  const half = size / 2
  const ring = (ry: number, rx = 0) => ({
    position: "absolute" as const,
    width: size, height: size,
    borderRadius: "50%",
    border: `1px solid oklch(0.72 0.15 192 / ${borderOpacity})`,
    transform: `rotateY(${ry}deg) rotateX(${rx}deg)`,
  })
  return (
    <div
      className={className}
      style={{
        width: size, height: size,
        transformStyle: "preserve-3d" as const,
        position: "absolute" as const,
        left: "50%", top: "50%",
        marginLeft: -half, marginTop: -half,
      }}
    >
      <div style={ring(0)} />
      <div style={ring(60)} />
      <div style={ring(120)} />
      <div style={ring(0, 90)} />
    </div>
  )
}

function PyramidMesh({ size, className, borderOpacity = 0.2 }: MeshProps) {
  const half = size / 2
  const tri = (ry: number) => ({
    position: "absolute" as const,
    width: size, height: size,
    clipPath: "polygon(50% 8%, 8% 92%, 92% 92%)",
    background: `linear-gradient(to bottom, oklch(0.72 0.15 192 / ${borderOpacity * 0.6}), oklch(0.72 0.15 192 / ${borderOpacity * 0.08}))`,
    transform: `rotateY(${ry}deg)`,
  })
  return (
    <div
      className={className}
      style={{
        width: size, height: size,
        transformStyle: "preserve-3d" as const,
        position: "absolute" as const,
        left: "50%", top: "50%",
        marginLeft: -half, marginTop: -half,
      }}
    >
      <div style={tri(0)} />
      <div style={tri(60)} />
      <div style={tri(120)} />
    </div>
  )
}

function OctaMesh({ size, className, borderOpacity = 0.2 }: MeshProps) {
  const half = size / 2
  const diamond = (ry: number) => ({
    position: "absolute" as const,
    width: size, height: size,
    clipPath: "polygon(50% 5%, 95% 50%, 50% 95%, 5% 50%)",
    background: `linear-gradient(135deg, oklch(0.72 0.15 192 / ${borderOpacity * 0.5}), oklch(0.72 0.15 192 / ${borderOpacity * 0.08}))`,
    transform: `rotateY(${ry}deg)`,
  })
  return (
    <div
      className={className}
      style={{
        width: size, height: size,
        transformStyle: "preserve-3d" as const,
        position: "absolute" as const,
        left: "50%", top: "50%",
        marginLeft: -half, marginTop: -half,
      }}
    >
      <div style={diamond(0)} />
      <div style={diamond(60)} />
      <div style={diamond(120)} />
    </div>
  )
}

function RingMesh({ size, className, borderOpacity = 0.2 }: MeshProps) {
  const half = size / 2
  const s = size * 0.85
  const pad = (size - s) / 2
  const ring = (ry: number, rx: number) => ({
    position: "absolute" as const,
    width: s, height: s,
    left: pad, top: pad,
    borderRadius: "50%",
    border: `1.5px solid oklch(0.72 0.15 192 / ${borderOpacity})`,
    transform: `rotateY(${ry}deg) rotateX(${rx}deg)`,
  })
  return (
    <div
      className={className}
      style={{
        width: size, height: size,
        transformStyle: "preserve-3d" as const,
        position: "absolute" as const,
        left: "50%", top: "50%",
        marginLeft: -half, marginTop: -half,
      }}
    >
      <div style={ring(0, 65)} />
      <div style={ring(60, 65)} />
      <div style={ring(120, 65)} />
    </div>
  )
}

function HexMesh({ size, className, borderOpacity = 0.2 }: MeshProps) {
  const half = size / 2
  const s = size * 0.85
  const pad = (size - s) / 2
  const hex = (z: number) => ({
    position: "absolute" as const,
    width: s, height: s,
    left: pad, top: pad,
    clipPath: "polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)",
    background: `linear-gradient(135deg, oklch(0.72 0.15 192 / ${borderOpacity * 0.25}), oklch(0.72 0.15 192 / ${borderOpacity * 0.06}))`,
    transform: `translateZ(${z}px)`,
  })
  return (
    <div
      className={className}
      style={{
        width: size, height: size,
        transformStyle: "preserve-3d" as const,
        position: "absolute" as const,
        left: "50%", top: "50%",
        marginLeft: -half, marginTop: -half,
      }}
    >
      <div style={hex(size * 0.22)} />
      <div style={hex(0)} />
      <div style={hex(-size * 0.22)} />
    </div>
  )
}

export function renderMiniShape(variant: ShapeVariant) {
  switch (variant) {
    case "double": return <CubeMesh size={44} className="wf-spin-slow" borderOpacity={0.8} />
    case "diamond": return <SphereMesh size={50} className="wf-spin-slow" borderOpacity={0.6} />
    case "grid": return <HexMesh size={48} className="wf-spin-slow" borderOpacity={0.7} />
    case "triple": return <PyramidMesh size={50} className="wf-spin-slow" borderOpacity={0.7} />
    case "fast": return <OctaMesh size={46} className="wf-spin-slow" borderOpacity={0.8} />
    case "pulse": return <RingMesh size={50} className="wf-spin-slow" borderOpacity={0.6} />
  }
}

export function WireframeShape({ variant }: { variant: ShapeVariant }) {
  const configs: Record<ShapeVariant, ReactNode> = {
    double: (
      <>
        <CubeMesh size={120} className="wf-spin" borderOpacity={0.2} />
        <CubeMesh size={68} className="wf-spin-reverse" borderOpacity={0.12} />
      </>
    ),
    diamond: (
      <>
        <SphereMesh size={120} className="wf-spin-slow" borderOpacity={0.22} />
        <SphereMesh size={70} className="wf-spin-reverse" borderOpacity={0.12} />
      </>
    ),
    grid: (
      <>
        <HexMesh size={120} className="wf-spin-slow" borderOpacity={0.3} />
        <HexMesh size={72} className="wf-spin-slow-offset" borderOpacity={0.15} />
      </>
    ),
    triple: (
      <>
        <PyramidMesh size={130} className="wf-spin" borderOpacity={0.28} />
        <PyramidMesh size={75} className="wf-spin-reverse" borderOpacity={0.15} />
      </>
    ),
    fast: (
      <>
        <OctaMesh size={120} className="wf-spin-fast" borderOpacity={0.3} />
        <OctaMesh size={65} className="wf-spin-reverse" borderOpacity={0.15} />
      </>
    ),
    pulse: (
      <>
        <RingMesh size={120} className="wf-spin-pulse" borderOpacity={0.25} />
        <RingMesh size={70} className="wf-spin-reverse" borderOpacity={0.12} />
      </>
    ),
  }

  return (
    <div className="relative" style={{ width: 200, height: 200, perspective: 800 }}>
      {configs[variant]}
      <div className="absolute inset-0 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
    </div>
  )
}
