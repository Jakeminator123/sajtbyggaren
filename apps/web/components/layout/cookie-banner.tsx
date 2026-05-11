"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function CookieBanner() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const consent = localStorage.getItem("cookie-consent");
    if (!consent) {
      const timer = setTimeout(() => setIsVisible(true), 800);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!isVisible) return null;

  const handleAccept = () => {
    localStorage.setItem("cookie-consent", "accepted");
    localStorage.setItem("cookie-consent-date", new Date().toISOString());
    setIsVisible(false);
  };

  const handleDecline = () => {
    localStorage.setItem("cookie-consent", "declined");
    setIsVisible(false);
  };

  return (
    <div className="animate-in slide-in-from-bottom-4 fixed inset-x-0 bottom-0 z-50 p-3 duration-300 sm:p-4">
      <div className="mx-auto flex max-w-md flex-col gap-3 rounded-2xl border border-border bg-card/95 p-3 shadow-sm backdrop-blur-sm sm:flex-row sm:items-center sm:gap-3 sm:p-3.5">
        <p className="flex-1 text-[11px] leading-snug text-muted-foreground sm:text-xs">
          Cookies för statistik.{" "}
          <Link href="/privacy" className="text-foreground/80 underline underline-offset-2 transition-colors hover:text-foreground">
            Integritet
          </Link>
        </p>
        <div className="flex shrink-0 justify-end gap-1.5 sm:justify-start">
          <Button variant="ghost" size="sm" onClick={handleDecline} className="h-7 px-2 text-[11px]">
            Neka
          </Button>
          <Button size="sm" onClick={handleAccept} className="h-7 px-3 text-[11px]">
            OK
          </Button>
        </div>
      </div>
    </div>
  );
}
