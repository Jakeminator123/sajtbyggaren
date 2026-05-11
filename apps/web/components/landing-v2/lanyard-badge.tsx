"use client";

import { Code2, Globe, Sparkles, Zap } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { useInView, usePrefersReducedMotion } from "@/components/landing-v2/landing-hooks";

interface Phys {
  angle: number;
  va: number;
  spin: number;
  vs: number;
  dropY: number;
  dropVY: number;
  phase: "wait" | "drop" | "settle" | "idle";
  t: number;
}

function createInitialPhys(): Phys {
  return {
    angle: 0,
    va: 0,
    spin: 0,
    vs: 0,
    dropY: -380,
    dropVY: 0,
    phase: "wait",
    t: 0,
  };
}

/** Rested card: visible, no swing — used off-viewport, reduced-motion, or before interactive drop. */
function applyRestedDom(
  pendulum: HTMLDivElement | null,
  cardInner: HTMLDivElement | null,
  hint: HTMLParagraphElement | null,
  showHint: boolean,
) {
  if (pendulum) {
    pendulum.style.transform = "rotate(0deg) translateY(0px)";
    pendulum.style.opacity = "1";
  }
  if (cardInner) {
    cardInner.style.transform = "perspective(800px) rotateY(0deg)";
  }
  if (hint) {
    hint.style.opacity = showHint ? "1" : "0";
  }
}

export function LanyardBadge() {
  const { ref: inViewRef, visible: sectionInView } = useInView(0.1);
  const reduceMotion = usePrefersReducedMotion();
  const runPhysics = sectionInView && !reduceMotion;

  const raf = useRef(0);
  const p = useRef<Phys>(createInitialPhys());
  const drag = useRef(false);
  const lastX = useRef(0);

  const pendulumRef = useRef<HTMLDivElement>(null);
  const cardInnerRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLParagraphElement>(null);

  /* Off-viewport or reduced-motion: park card at rest, no RAF (ingen dra-hint när statisk). */
  useLayoutEffect(() => {
    if (runPhysics) return;
    applyRestedDom(pendulumRef.current, cardInnerRef.current, hintRef.current, false);
  }, [runPhysics, reduceMotion]);

  /* When interactive region enters view: reset and run drop intro */
  useEffect(() => {
    if (!runPhysics) return;
    p.current = createInitialPhys();
    if (pendulumRef.current) {
      pendulumRef.current.style.opacity = "0";
    }
    if (hintRef.current) {
      hintRef.current.style.opacity = "0";
    }
    const timer = setTimeout(() => {
      p.current.phase = "drop";
    }, 500);
    return () => clearTimeout(timer);
  }, [runPhysics]);

  useEffect(() => {
    if (!runPhysics) {
      cancelAnimationFrame(raf.current);
      return;
    }

    const step = () => {
      const s = p.current;
      s.t += 1 / 60;

      if (s.phase === "drop") {
        s.dropVY += 1800 * (1 / 60);
        s.dropY += s.dropVY * (1 / 60);
        if (s.dropY >= 0) {
          s.dropY = 0;
          s.dropVY *= -0.25;
          s.va += (Math.random() - 0.5) * 1.5;
          if (Math.abs(s.dropVY) < 15) {
            s.dropVY = 0;
            s.phase = "settle";
          }
        }
      }

      if (s.phase === "settle") {
        s.dropVY += -s.dropY * 8 * (1 / 60);
        s.dropVY *= 0.92;
        s.dropY += s.dropVY;
        if (Math.abs(s.dropY) < 0.2 && Math.abs(s.dropVY) < 0.3) {
          s.dropY = 0;
          s.dropVY = 0;
          s.phase = "idle";
        }
      }

      if (!drag.current) {
        s.va += -s.angle * 0.025;
        s.va *= 0.97;
        if (s.phase === "idle") {
          s.va += Math.sin(s.t * 0.8) * 0.015 + Math.cos(s.t * 0.5) * 0.008;
        }
      }
      s.angle += s.va;
      s.angle = Math.max(-35, Math.min(35, s.angle));

      if (!drag.current) {
        s.vs += -s.spin * 0.015;
        s.vs *= 0.985;
      }
      s.spin += s.vs;

      const pendulumShown = s.phase !== "wait";

      if (pendulumRef.current) {
        pendulumRef.current.style.transform = `rotate(${s.angle}deg) translateY(${s.dropY}px)`;
        pendulumRef.current.style.opacity = pendulumShown ? "1" : "0";
      }

      if (cardInnerRef.current) {
        cardInnerRef.current.style.transform = `perspective(800px) rotateY(${s.spin}deg)`;
      }

      if (hintRef.current) {
        hintRef.current.style.opacity = s.phase === "idle" ? "1" : "0";
      }

      raf.current = requestAnimationFrame(step);
    };

    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [runPhysics]);

  const onDown = useCallback((e: React.PointerEvent) => {
    if (!runPhysics) return;
    e.preventDefault();
    drag.current = true;
    lastX.current = e.clientX;
    p.current.va = 0;
    p.current.vs = 0;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  }, [runPhysics]);

  const onMove = useCallback((e: React.PointerEvent) => {
    if (!runPhysics || !drag.current) return;
    const dx = e.clientX - lastX.current;
    lastX.current = e.clientX;

    p.current.angle = Math.max(-35, Math.min(35, p.current.angle + dx * 0.3));
    p.current.va = dx * 0.15;
    p.current.vs += dx * 0.04;
  }, [runPhysics]);

  const onUp = useCallback(() => {
    drag.current = false;
  }, []);

  const cardGrabClass = runPhysics ? "cursor-grab active:cursor-grabbing" : "cursor-default";

  return (
    <div ref={inViewRef} className="relative w-full">
      <div
        className="relative w-full h-[450px] md:h-[530px] overflow-hidden select-none"
        onPointerMove={runPhysics ? onMove : undefined}
        onPointerUp={runPhysics ? onUp : undefined}
        onPointerLeave={runPhysics ? onUp : undefined}
        style={{ touchAction: runPhysics ? "none" : "auto" }}
      >
        <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40">
          <div className="w-5 h-5 rounded-full bg-primary shadow-lg shadow-primary/40 border-2 border-background" />
        </div>

        <div
          ref={pendulumRef}
          className="absolute top-[34px] left-1/2 z-20 opacity-0"
          style={{
            transformOrigin: "top center",
            marginLeft: "-110px",
            width: "220px",
            willChange: "transform, opacity",
            transition: "opacity 0.3s",
          }}
        >
          <div
            className="mx-auto"
            style={{
              width: "2.5px",
              height: "110px",
              background: "linear-gradient(to bottom, oklch(0.72 0.15 192), oklch(0.72 0.15 192 / 0.3))",
              boxShadow: "0 0 8px oklch(0.72 0.15 192 / 0.2)",
              borderRadius: "0 0 1px 1px",
            }}
          />

          <div className="w-4 h-2 rounded-b-sm bg-muted-foreground/30 mx-auto" />

          <div
            ref={cardInnerRef}
            onPointerDown={onDown}
            className={`mt-0.5 ${cardGrabClass}`}
            style={{ willChange: "transform", transformStyle: "preserve-3d" }}
          >
            <div
              className="relative rounded-2xl border border-border/30 bg-card backdrop-blur-xl overflow-hidden shadow-2xl shadow-black/40"
              style={{ backfaceVisibility: "hidden" }}
            >
              <div className="absolute top-2.5 left-1/2 -translate-x-1/2 w-7 h-2.5 rounded-full bg-background/80 border border-border/20 z-10" />
              <div className="h-11 bg-linear-to-br from-primary/10 via-primary/3 to-transparent" />

              <div className="px-4 pb-4 -mt-1">
                <div className="w-9 h-9 rounded-lg bg-primary/8 border border-primary/15 flex items-center justify-center mb-2 shadow-md shadow-primary/5">
                  <Zap className="w-4 h-4 text-primary" />
                </div>

                <h3 className="text-sm text-foreground font-(--font-heading) tracking-tight leading-none">
                  SajtMaskin
                </h3>
                <p className="text-[10px] text-muted-foreground mt-0.5 mb-2.5">AI-driven webbplatsgenerering</p>

                <div className="flex flex-wrap gap-1 mb-3">
                  {[
                    { icon: Code2, label: "React 19" },
                    { icon: Globe, label: "Next.js" },
                    { icon: Sparkles, label: "AI SDK" },
                  ].map((item) => (
                    <span
                      key={item.label}
                      className="inline-flex items-center gap-0.5 text-[8px] font-medium text-primary/70 bg-primary/6 border border-primary/10 rounded px-1.5 py-px"
                    >
                      <item.icon className="w-2 h-2" />
                      {item.label}
                    </span>
                  ))}
                </div>

                <div className="h-px bg-border/15 mb-2.5" />

                <div className="flex items-center justify-between text-[9px]">
                  <div>
                    <p className="text-muted-foreground/40 uppercase tracking-wider leading-none mb-0.5">Grundare</p>
                    <p className="text-foreground/80 font-medium">Erik</p>
                  </div>
                  <div className="text-right">
                    <p className="text-muted-foreground/40 uppercase tracking-wider leading-none mb-0.5">Status</p>
                    <div className="flex items-center gap-1 justify-end">
                      <span className="relative flex h-1.5 w-1.5">
                        {!reduceMotion ? (
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
                        ) : null}
                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary" />
                      </span>
                      <span className="text-primary font-medium">Beta</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div
              className="absolute inset-0 rounded-2xl border border-border/30 bg-card/95 backdrop-blur-xl flex items-center justify-center shadow-2xl shadow-black/40"
              style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
            >
              <div className="text-center px-6">
                <div className="w-14 h-14 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-3">
                  <Zap className="w-7 h-7 text-primary" />
                </div>
                <p className="text-xs text-foreground font-(--font-heading)">SajtMaskin</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">sajtmaskin.se</p>
              </div>
            </div>
          </div>
        </div>

        <p
          ref={hintRef}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[11px] text-muted-foreground/25 opacity-0 transition-opacity duration-1000 z-30"
          style={{ transitionDelay: "1.5s" }}
        >
          &larr; dra kortet &rarr;
        </p>
      </div>
    </div>
  );
}
