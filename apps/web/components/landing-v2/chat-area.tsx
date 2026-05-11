"use client"

import { ArrowRight, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { LandingBackground } from "@/components/landing-v2/landing-background"
import { LandingMinimalFooter } from "@/components/landing-v2/landing-minimal-footer"
import { LandingHero } from "@/components/landing-v2/landing-hero"
import {
  features,
  integrations,
  techStack,
  creditPackages,
  studioTeam,
  studioTiers,
} from "@/components/landing-v2/landing-chat-data"
import { FeatureCard, FeatureModal } from "@/components/landing-v2/landing-feature-blocks"
import { IntegrationCard, TechStackCard } from "@/components/landing-v2/landing-tech-integration-cards"
import { useLandingController, type ChatAreaProps } from "@/components/landing-v2/use-landing-controller"

export type { ChatAreaProps }

export function ChatArea(props: ChatAreaProps = {}) {
  const { expandedContent, heroPrefix } = props
  const {
    router,
    showVoiceRecorder,
    setShowVoiceRecorder,
    selectedCategory,
    inputValue,
    setInputValue,
    isSubmitting,
    activeFeature,
    setActiveFeature,
    activeCategory,
    isAuditMode,
    currentAuditUrl,
    handleAuditUrlChange,
    startBuild,
    submitPrimaryInput,
  } = useLandingController(props)

  return (
    <main className="landing-v2-page relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <LandingBackground
        selectedCategory={selectedCategory}
        isAuditMode={isAuditMode}
        activeCategory={activeCategory}
      />

      <div
        className="relative z-10 flex min-h-0 flex-1 touch-pan-y flex-col overflow-y-auto overscroll-y-contain scroll-smooth [-webkit-overflow-scrolling:touch]"
        data-scroll-container
      >
        <LandingHero
          heroPrefix={heroPrefix}
          expandedContent={expandedContent}
          showVoiceRecorder={showVoiceRecorder}
          setShowVoiceRecorder={setShowVoiceRecorder}
          inputValue={inputValue}
          setInputValue={setInputValue}
          isSubmitting={isSubmitting}
          activeCategory={activeCategory}
          isAuditMode={isAuditMode}
          currentAuditUrl={currentAuditUrl}
          handleAuditUrlChange={handleAuditUrlChange}
          submitPrimaryInput={submitPrimaryInput}
          startBuild={startBuild}
        />

        {/* Nedanför fold: mer info */}
        <div className="border-t border-border/40">
          <Tabs defaultValue="funktioner" className="w-full">
            <div className="sticky top-0 z-20 border-b border-border/40 bg-background/60 backdrop-blur-md">
              <div className="mx-auto max-w-5xl px-5 md:px-6">
                <TabsList variant="line" className="min-h-11 h-11 w-full justify-start gap-0 md:h-10 md:min-h-10">
                  <TabsTrigger value="funktioner" className="text-sm">
                    Funktioner
                  </TabsTrigger>
                  <TabsTrigger value="teknik" className="text-sm">
                    Teknik
                  </TabsTrigger>
                  <TabsTrigger value="priser" className="text-sm">
                    Priser
                  </TabsTrigger>
                </TabsList>
              </div>
            </div>

            {/* ── FUNKTIONER ── */}
            <TabsContent value="funktioner" className="mt-0">
              <section id="funktioner" className="px-6 py-14 md:py-20">
                <div className="mx-auto max-w-6xl">
                  <div className="mb-10 text-center">
                    <h2 className="mb-2 font-(--font-heading) text-2xl tracking-tight text-foreground md:text-3xl">
                      Teknik du känner igen
                    </h2>
                    <p className="mx-auto max-w-md text-sm text-muted-foreground">
                      React, Next.js, TypeScript.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {features.map((feature, i) => (
                      <FeatureCard
                        key={feature.title}
                        feature={feature}
                        onClick={() => setActiveFeature(feature)}
                        index={i}
                      />
                    ))}
                  </div>
                </div>
              </section>

              <section className="border-t border-border/40 px-6 py-14">
                <div className="mx-auto max-w-5xl">
                  <div className="mb-8 text-center">
                    <h2 className="mb-2 font-(--font-heading) text-xl tracking-tight text-foreground md:text-2xl">
                      Integrationer
                    </h2>
                    <p className="mx-auto max-w-md text-sm text-muted-foreground">
                      Betalning, e-post, data.
                    </p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    {integrations.map((item, index) => (
                      <IntegrationCard key={item.name} item={item} index={index} />
                    ))}
                  </div>
                </div>
              </section>
            </TabsContent>

            {/* ── TEKNIK ── */}
            <TabsContent value="teknik" className="mt-0">
              <section id="teknik" className="px-6 py-14 md:py-20">
                <div className="mx-auto max-w-5xl">
                  <div className="mb-10 text-center">
                    <h2 className="mb-2 font-(--font-heading) text-2xl tracking-tight text-foreground md:text-3xl">
                      Stack
                    </h2>
                    <p className="mx-auto max-w-md text-sm text-muted-foreground">
                      Verktyg för produktion.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {techStack.map((tech, index) => (
                      <TechStackCard key={tech.name} tech={tech} index={index} />
                    ))}
                  </div>
                </div>
              </section>
            </TabsContent>

            {/* ── PRISER ── */}
            <TabsContent value="priser" className="mt-0">
              <section className="px-6 py-14 md:py-20">
                <div className="mx-auto max-w-5xl">
                  <div className="mb-10 text-center">
                    <h2 className="mb-2 font-(--font-heading) text-2xl tracking-tight text-foreground md:text-3xl">
                      Priser
                    </h2>
                    <p className="mx-auto max-w-md text-sm text-muted-foreground">
                      Credits. Bygg i din takt.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                    {creditPackages.map((pkg) => (
                      <div
                        key={pkg.id}
                        className={`flex flex-col gap-5 rounded-2xl border border-border/50 p-7 transition-[border-color,box-shadow] duration-200 ease-out motion-reduce:transition-none ${
                          pkg.popular
                            ? "relative border-primary/25 bg-primary/5 shadow-lg shadow-[0_12px_40px_-12px_hsl(var(--primary)/0.25)] md:-my-2 md:scale-[1.02]"
                            : "bg-card/40 hover:border-border/70"
                        }`}
                      >
                        {pkg.popular && (
                          <div className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] font-semibold uppercase tracking-wider text-primary-foreground bg-primary px-3 py-1 rounded-full">
                            Populärast
                          </div>
                        )}
                        <div>
                          <h3 className="text-lg text-foreground font-(--font-heading)">{pkg.name}</h3>
                          <p className="text-sm text-muted-foreground mt-0.5">{pkg.description}</p>
                        </div>
                        <div className="flex items-end gap-2">
                          <span className="text-3xl text-foreground font-(--font-heading)">{pkg.price} kr</span>
                          <span className="text-sm text-muted-foreground mb-1">{pkg.credits} credits</span>
                        </div>
                        <div className="h-px bg-border/60" />
                        <ul className="space-y-3 flex-1">
                          {pkg.features.map((feature) => (
                            <li key={feature} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                              <CheckCircle2 className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                              <span>{feature}</span>
                            </li>
                          ))}
                        </ul>
                        <Button
                          className={`mt-2 w-full min-h-11 rounded-xl font-medium transition-colors duration-200 ease-out motion-reduce:transition-none ${
                            pkg.popular
                              ? "landing-cta-primary bg-primary text-primary-foreground hover:bg-primary/90"
                              : "border border-border/50 bg-secondary/80 text-secondary-foreground hover:bg-secondary"
                          }`}
                          onClick={() => router.push("/buy-credits")}
                          disabled={isSubmitting}
                        >
                          {pkg.cta}
                          {pkg.popular && <ArrowRight className="w-4 h-4 ml-2" />}
                        </Button>
                      </div>
                    ))}
                  </div>

                  {/* SajtStudio upsell */}
                  <div className="mt-12 rounded-2xl border border-border/50 bg-card/30 p-6 md:p-8">
                    <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
                      <div>
                        <p className="text-xs font-medium text-primary tracking-widest uppercase mb-2">SajtStudio</p>
                        <h3 className="text-xl md:text-2xl font-(--font-heading) text-foreground tracking-tight mb-3">
                          Behöver du ett team?
                        </h3>
                        <p className="text-sm text-muted-foreground mb-5">
                          Vi hjälper till med strategi, design, integrationer och lansering.
                        </p>
                        <div className="space-y-2 mb-5">
                          {studioTeam.map((member) => (
                            <div key={member.name} className="flex items-center gap-3 rounded-xl border border-border/50 bg-background/50 px-3 py-2">
                              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-xs font-(--font-heading) text-primary">
                                {member.name.slice(0, 1)}
                              </div>
                              <div>
                                <p className="text-sm font-medium text-foreground">{member.name}</p>
                                <p className="text-xs text-muted-foreground">{member.role}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                        <Button
                          className="landing-cta-primary min-h-11 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                          onClick={() => { window.location.href = "mailto:ch.genberg@gmail.com,erik@sajtstudio.se" }}
                        >
                          Prata med teamet
                          <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>
                      </div>
                      <div className="grid gap-3 md:grid-cols-3">
                        {studioTiers.map((tier) => (
                          <div key={tier.name} className="rounded-xl border border-border/50 bg-background/50 p-4">
                            <p className="text-xs uppercase tracking-wider text-primary/70 mb-2">{tier.name}</p>
                            <p className="text-lg font-(--font-heading) text-foreground">{tier.range}</p>
                            <p className="mt-1.5 text-sm text-muted-foreground">{tier.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </TabsContent>
          </Tabs>
        </div>

        <LandingMinimalFooter />
      </div>

      <FeatureModal feature={activeFeature} onClose={() => setActiveFeature(null)} />
    </main>
  )
}
