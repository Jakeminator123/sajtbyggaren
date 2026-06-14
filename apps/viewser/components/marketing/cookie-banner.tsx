"use client";

import Link from "next/link";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCookieConsent } from "@/components/marketing/cookie-consent";

// Icke-blockerande cookie-bar (role="region", ingen cookie-wall) + en
// manager-dialog med riktig focus-trap. Bar:en visas bara innan ett val
// gjorts; "Hantera cookies" i footern öppnar managern igen när som helst.
function ActionButtons({
  onAccept,
  onDecline,
}: {
  onAccept: () => void;
  onDecline: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <button
        type="button"
        onClick={onDecline}
        className="border-border text-foreground hover:bg-muted focus-visible:ring-ring/50 inline-flex h-9 items-center rounded-full border px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        Endast nödvändiga
      </button>
      <button
        type="button"
        onClick={onAccept}
        className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-9 items-center rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        Acceptera alla
      </button>
    </div>
  );
}

export function CookieBanner() {
  const { ready, consent, managerOpen, accept, decline, closeManager } =
    useCookieConsent();

  const showBar = ready && consent === null && !managerOpen;

  return (
    <>
      {showBar ? (
        <div
          role="region"
          aria-label="Cookie-samtycke"
          // Mobil: kompakt kort längst ned. Desktop (sm+): litet kort i NEDRE
          // HÖGRA hörnet (smalt, max-w-sm) så det håller sig undan startsidans
          // vänsterställda hero-CTA och bara nuddar hörnet av yrkessidornas
          // kort-rutnät. Baren är transient — den försvinner när ett val gjorts
          // — så ett litet hörnkort ger minimal störning på innehållet.
          className="fixed inset-x-3 bottom-3 z-50 sm:inset-x-auto sm:right-4 sm:bottom-4 sm:max-w-sm"
        >
          <div className="border-border/60 bg-card/95 flex flex-col gap-3 rounded-2xl border p-4 shadow-lg backdrop-blur-xl">
            <p className="text-muted-foreground text-[13px] leading-relaxed">
              Vi använder nödvändiga cookies för att sajten ska fungera. Övriga
              cookies sätts bara om du accepterar. Läs mer i vår{" "}
              <Link
                href="/cookies"
                className="text-foreground underline underline-offset-2"
              >
                cookiepolicy
              </Link>
              .
            </p>
            <ActionButtons onAccept={accept} onDecline={decline} />
          </div>
        </div>
      ) : null}

      <Dialog
        open={managerOpen}
        onOpenChange={(open) => {
          if (!open) closeManager();
        }}
      >
        <DialogContent aria-label="Hantera cookies">
          <DialogHeader>
            <DialogTitle>Hantera cookies</DialogTitle>
            <DialogDescription>
              Nödvändiga cookies krävs för att sajten ska fungera och är alltid
              på. Du kan välja att även tillåta övriga cookies, eller behålla
              endast de nödvändiga.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <ActionButtons onAccept={accept} onDecline={decline} />
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
