"use client"

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react"

/* 3D tilt — DOM transform only, prefers-reduced-motion aware */
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"

/** SSR-safe; false until mounted, then syncs with system preference. */
export function usePrefersReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia(REDUCED_MOTION_QUERY)
    const sync = () => setReduce(mq.matches)
    sync()
    mq.addEventListener("change", sync)
    return () => mq.removeEventListener("change", sync)
  }, [])

  return reduce
}
const TILT_NEUTRAL = "perspective(800px) rotateX(0deg) rotateY(0deg) scale(1)"

export function use3DTilt(intensity = 12) {
  const ref = useRef<HTMLDivElement>(null)
  const reduceMotionRef = useRef(false)

  useEffect(() => {
    const mq = window.matchMedia(REDUCED_MOTION_QUERY)
    const sync = () => {
      reduceMotionRef.current = mq.matches
    }
    sync()
    mq.addEventListener("change", sync)
    return () => mq.removeEventListener("change", sync)
  }, [])

  useLayoutEffect(() => {
    const el = ref.current
    if (el) el.style.transform = TILT_NEUTRAL
  }, [])

  const handleMove = useCallback(
    (e: ReactMouseEvent) => {
      const el = ref.current
      if (!el || reduceMotionRef.current) return
      const rect = el.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width - 0.5
      const y = (e.clientY - rect.top) / rect.height - 0.5
      el.style.transform = `perspective(800px) rotateX(${-y * intensity}deg) rotateY(${x * intensity}deg) scale(1.02)`
    },
    [intensity],
  )

  const handleLeave = useCallback(() => {
    const el = ref.current
    if (!el) return
    el.style.transform = TILT_NEUTRAL
  }, [])

  return { ref, handleMove, handleLeave }
}

export function useTerminalTypewriter() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [visibleLines, setVisibleLines] = useState(0)
  const [cursorLine, setCursorLine] = useState(0)
  const started = useRef(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true
          const totalLines = 6
          let line = 0
          const interval = setInterval(() => {
            line++
            setVisibleLines(line)
            setCursorLine(line)
            if (line >= totalLines) clearInterval(interval)
          }, 420)
        }
      },
      { threshold: 0.4 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return { containerRef, visibleLines, cursorLine }
}

export function useHonestCounter(fakeTarget: number, realValue: number, message: string) {
  const [count, setCount] = useState(0)
  const [phase, setPhase] = useState<"idle" | "inflating" | "glitch" | "honest">("idle")
  const ref = useRef<HTMLDivElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true
          setPhase("inflating")

          const duration = 1600
          const start = performance.now()
          const step = (now: number) => {
            const progress = Math.min((now - start) / duration, 1)
            const eased = 1 - Math.pow(1 - progress, 3)
            setCount(Math.floor(eased * fakeTarget))
            if (progress < 1) {
              requestAnimationFrame(step)
            } else {
              setTimeout(() => {
                setPhase("glitch")
                let glitchCount = 0
                const glitchInterval = setInterval(() => {
                  setCount(Math.floor(Math.random() * fakeTarget))
                  glitchCount++
                  if (glitchCount > 8) {
                    clearInterval(glitchInterval)
                    setCount(realValue)
                    setPhase("honest")
                  }
                }, 60)
              }, 800)
            }
          }
          requestAnimationFrame(step)
        }
      },
      { threshold: 0.5 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [fakeTarget, realValue])

  return { count, phase, ref, message }
}

export function useRotatingText(items: string[], interval = 2400) {
  const [index, setIndex] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const timer = setInterval(() => {
      setVisible(false)
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % items.length)
        setVisible(true)
      }, 300)
    }, interval)
    return () => clearInterval(timer)
  }, [items.length, interval])

  return { text: items[index] ?? "", visible }
}

export function useInView(threshold = 0.3) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [threshold])

  return { ref, visible }
}
