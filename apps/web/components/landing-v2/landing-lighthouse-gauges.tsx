"use client"

import { useInView } from "@/components/landing-v2/landing-hooks"

const lighthouseScores = [
  { label: "Performance", score: 96 },
  { label: "Tillg\u00e4nglighet", score: 98 },
  { label: "Best Practices", score: 100 },
  { label: "SEO", score: 98 },
]

export function LighthouseGauges() {
  const { ref, visible } = useInView(0.25)
  return (
    <div ref={ref} className="mt-14 flex flex-col items-center gap-6">
      <div className="flex flex-wrap justify-center gap-8 md:gap-14">
      {lighthouseScores.map((item, i) => {
        const r = 40
        const c = 2 * Math.PI * r
        const offset = c - (item.score / 100) * c
        return (
          <div key={item.label} className="flex flex-col items-center gap-3">
            <div className="relative w-24 h-24">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50" cy="50" r={r}
                  fill="none" stroke="oklch(0.15 0 0)" strokeWidth="3.5"
                />
                <circle
                  cx="50" cy="50" r={r}
                  fill="none"
                  stroke="oklch(0.72 0.15 192)"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  strokeDasharray={c}
                  strokeDashoffset={visible ? offset : c}
                  style={{
                    transition: `stroke-dashoffset 1.5s cubic-bezier(0.4, 0, 0.2, 1) ${i * 0.2}s`,
                  }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span
                  className={`text-xl font-(--font-heading) transition-all duration-700 ${visible ? "text-foreground opacity-100" : "text-muted-foreground opacity-0"}`}
                  style={{ transitionDelay: `${i * 0.2 + 0.6}s` }}
                >
                  {item.score}
                </span>
              </div>
            </div>
            <span className="text-xs text-muted-foreground">{item.label}</span>
          </div>
        )
      })}
      </div>
      <p className="max-w-md px-4 text-center text-[10px] leading-snug text-muted-foreground/85">
        Siffrorna &auml;r illustrativa exempel f&ouml;r j&auml;mf&ouml;relsen &mdash; inte resultat fr&aring;n en faktisk Lighthouse-k&ouml;rning av denna sida.
      </p>
    </div>
  )
}
