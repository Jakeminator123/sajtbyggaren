"use client"

import Link from "next/link"
import { Zap } from "lucide-react"

export function LandingFooter() {
  return (
    <footer className="px-6 py-10 border-t border-border/15">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-10">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
                <Zap className="w-3.5 h-3.5 text-primary-foreground" />
              </div>
              <span className="text-sm text-foreground font-(--font-heading)">SajtMaskin</span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed max-w-[200px]">
              Professionella hemsidor f&ouml;r svenska f&ouml;retag &mdash; snabbt, enkelt och med riktig teknik bakom.
            </p>
            <p className="mt-3 max-w-[200px] text-[10px] leading-relaxed text-muted-foreground/70">
              En tj&auml;nst fr&aring;n{" "}
              <a
                href="https://sajtstudio.se"
                target="_blank"
                rel="noopener noreferrer"
                className="underline-offset-2 hover:text-foreground hover:underline"
              >
                Pretty Good AB
              </a>
              .
            </p>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider mb-3">Produkt</h4>
            <ul className="space-y-2">
              <li>
                <Link href="/#funktioner" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Funktioner
                </Link>
              </li>
              <li>
                <Link href="/#teknik" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Teknik
                </Link>
              </li>
              <li>
                <a href="#priser" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Priser
                </a>
              </li>
              <li>
                <Link href="/templates" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Mallar
                </Link>
              </li>
              <li>
                <Link
                  href="/landningssidor"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Sajtkarta
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider mb-3">F&ouml;retag</h4>
            <ul className="space-y-2">
              <li>
                <Link href="/om" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Om oss
                </Link>
              </li>
              <li>
                <Link href="/blogg" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Blogg
                </Link>
              </li>
              <li>
                <a
                  href="mailto:support@sajtmaskin.se?subject=Karri%C3%A4r"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Karri&auml;r
                </a>
              </li>
              <li>
                <a
                  href="mailto:support@sajtmaskin.se"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Kontakt
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider mb-3">Juridiskt</h4>
            <ul className="space-y-2">
              <li>
                <Link href="/privacy" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Integritetspolicy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Anv&auml;ndarvillkor
                </Link>
              </li>
              <li>
                <Link
                  href="/privacy#gdpr"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  GDPR
                </Link>
              </li>
              <li>
                <Link
                  href="/privacy#cookies"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cookies
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6 border-t border-border/15">
          <p className="text-xs text-muted-foreground/60">
            &copy; {new Date().getFullYear()} Pretty Good AB. Alla r&auml;ttigheter f&ouml;rbeh&aring;llna.
          </p>
          <p className="text-xs text-muted-foreground/60">Sociala länkar publiceras här när de finns.</p>
        </div>
      </div>
    </footer>
  )
}
