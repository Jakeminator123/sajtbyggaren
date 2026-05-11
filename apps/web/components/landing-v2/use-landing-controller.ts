"use client"

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { createProject } from "@/lib/project-client"
import { resolveLandingRouteTarget } from "@/components/landing-v2/route-target"
import {
  categories,
  comparisonMethods,
  comparisonScenarios,
  features,
  getComparisonScore,
  siteTypes,
  type ComparisonScenarioId,
} from "@/components/landing-v2/landing-chat-data"
import { use3DTilt, useHonestCounter, useRotatingText, useTerminalTypewriter } from "@/components/landing-v2/landing-hooks"

export interface ChatAreaProps {
  selectedCategory?: string | null
  onSelectedCategoryChange?: (id: string | null) => void
  expandedContent?: ReactNode
  heroPrefix?: ReactNode
  auditUrl?: string
  onAuditUrlChange?: (url: string) => void
  onAuditSubmit?: () => void
}

/** Return shape of `useLandingController` — for prop typing in split components (type-only imports). */
export type LandingController = ReturnType<typeof useLandingController>

export function useLandingController({
  selectedCategory: controlledCategory,
  onSelectedCategoryChange,
  auditUrl,
  onAuditUrlChange,
  onAuditSubmit,
}: ChatAreaProps = {}) {
  const router = useRouter()
  const [showVoiceRecorder, setShowVoiceRecorder] = useState(false)
  const [internalCategory, setInternalCategory] = useState<string | null>("fritext")
  const selectedCategory = controlledCategory !== undefined ? controlledCategory : internalCategory
  const [inputValue, setInputValue] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeFeature, setActiveFeature] = useState<(typeof features)[number] | null>(null)
  const [activeComparisonScenarioId, setActiveComparisonScenarioId] = useState<ComparisonScenarioId>("growth")
  const [selectedComparisonMethodKey, setSelectedComparisonMethodKey] = useState("next")

  const activeComparisonScenario =
    comparisonScenarios.find((scenario) => scenario.id === activeComparisonScenarioId) ?? comparisonScenarios[0]!

  const rankedComparisonMethods = useMemo(
    () =>
      comparisonMethods
        .map((method) => ({
          method,
          total: getComparisonScore(method, activeComparisonScenario),
        }))
        .sort((a, b) => b.total - a.total),
    [activeComparisonScenario],
  )

  const fallbackComparisonMethod = comparisonMethods[0]!
  const selectedComparisonMethod = useMemo(
    () =>
      rankedComparisonMethods.find((entry) => entry.method.key === selectedComparisonMethodKey) ?? {
        method: fallbackComparisonMethod,
        total: getComparisonScore(fallbackComparisonMethod, activeComparisonScenario),
      },
    [activeComparisonScenario, fallbackComparisonMethod, rankedComparisonMethods, selectedComparisonMethodKey],
  )

  const wordpressComparisonMethod = comparisonMethods.find((method) => method.key === "wordpress") ?? fallbackComparisonMethod
  const wordpressScenarioScore = getComparisonScore(wordpressComparisonMethod, activeComparisonScenario)
  const selectedVsWordpressDelta = selectedComparisonMethod.total - wordpressScenarioScore

  const websitesCounter = useHonestCounter(
    2480,
    41,
    "41 sajter live just nu. Varje ny version ger oss bättre signaler om vad som faktiskt konverterar.",
  )
  const usersCounter = useHonestCounter(
    850,
    28,
    "28 företagare kör redan skarpt. Nästa våg handlar om fler bokningar, fler leads och bättre uppföljning.",
  )
  const rotatingType = useRotatingText(siteTypes)
  const headlineTilt = use3DTilt(10)
  const terminal = useTerminalTypewriter()
  const terminalBoxRef = useRef<HTMLDivElement>(null)

  const preloadHowItWorksScene = useCallback(() => {
    // 3D-scene är inte med i apps/web (kräver Three.js). Lazy-laddningen
    // ersätts av no-op tills vi tar in @react-three/fiber.
  }, [])

  const handleTerminalMouse = useCallback((e: ReactMouseEvent) => {
    const el = terminalBoxRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    el.style.setProperty("--term-glow-x", `${e.clientX - rect.left}px`)
    el.style.setProperty("--term-glow-y", `${e.clientY - rect.top}px`)
  }, [])

  const activeCategory = categories.find((c) => c.id === selectedCategory)
  const isAuditMode = selectedCategory === "audit"
  const currentAuditUrl = auditUrl ?? inputValue

  const handleAuditUrlChange = useCallback(
    (value: string) => {
      if (onAuditUrlChange) {
        onAuditUrlChange(value)
        return
      }
      setInputValue(value)
    },
    [onAuditUrlChange],
  )

  useEffect(() => {
    if (!activeFeature) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActiveFeature(null)
    }
    document.addEventListener("keydown", onKey)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = ""
    }
  }, [activeFeature])

  useEffect(() => {
    if (isAuditMode && showVoiceRecorder) {
      setShowVoiceRecorder(false)
    }
  }, [isAuditMode, showVoiceRecorder])

  const startBuild = useCallback(
    async (categoryOverride?: string | null, promptOverride?: string) => {
      if (isSubmitting) return

      const targetCategory = categoryOverride ?? selectedCategory
      const prompt = (promptOverride ?? inputValue).trim()
      const routeTarget = resolveLandingRouteTarget(targetCategory)

      setIsSubmitting(true)

      try {
        const categoryLabel = categories.find((category) => category.id === targetCategory)?.label ?? "Sajt"
        const project = await createProject(
          `${categoryLabel} - ${new Date().toLocaleDateString("sv-SE")}`,
          routeTarget.buildMethod,
          prompt ? prompt.slice(0, 100) : undefined,
        )

        const params = new URLSearchParams()
        params.set("project", project.id)
        params.set("buildMethod", routeTarget.buildMethod)
        params.set("buildIntent", routeTarget.buildIntent)
        if (routeTarget.source) {
          params.set("source", routeTarget.source)
        }

        if (prompt.length > 0) {
          const response = await fetch("/api/prompts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              prompt,
              source: routeTarget.source ?? routeTarget.buildMethod,
              projectId: project.id,
            }),
          })

          const data = (await response.json().catch(() => null)) as
            | {
                success?: boolean
                promptId?: string
                error?: string
              }
            | null

          if (!response.ok || !data?.promptId) {
            throw new Error(data?.error || "Kunde inte spara prompten")
          }

          params.set("promptId", data.promptId)
        }

        router.push(`/builder?${params.toString()}`)
      } catch (error) {
        console.error("[LandingV2] Failed to start builder flow:", error)
        toast.error(error instanceof Error ? error.message : "Kunde inte starta buildern")
      } finally {
        setIsSubmitting(false)
      }
    },
    [inputValue, isSubmitting, router, selectedCategory],
  )

  const submitPrimaryInput = useCallback(() => {
    if (isAuditMode && onAuditSubmit) {
      onAuditSubmit()
      return
    }
    void startBuild()
  }, [isAuditMode, onAuditSubmit, startBuild])

  return {
    router,
    showVoiceRecorder,
    setShowVoiceRecorder,
    selectedCategory,
    inputValue,
    setInputValue,
    isSubmitting,
    activeFeature,
    setActiveFeature,
    activeComparisonScenarioId,
    setActiveComparisonScenarioId,
    selectedComparisonMethodKey,
    setSelectedComparisonMethodKey,
    activeComparisonScenario,
    rankedComparisonMethods,
    selectedComparisonMethod,
    wordpressComparisonMethod,
    wordpressScenarioScore,
    selectedVsWordpressDelta,
    websitesCounter,
    usersCounter,
    rotatingType,
    headlineTilt,
    terminal,
    terminalBoxRef,
    handleTerminalMouse,
    preloadHowItWorksScene,
    activeCategory,
    isAuditMode,
    currentAuditUrl,
    handleAuditUrlChange,
    startBuild,
    submitPrimaryInput,
  }
}
