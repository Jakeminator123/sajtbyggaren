"use client";

import { useEffect, useState } from "react";
import { AnimatedLogo } from "./animated-logo";
import { HeaderActions } from "@/components/layout/header-actions";

interface NavbarProps {
  onLoginClick?: () => void;
  onRegisterClick?: () => void;
}

export function Navbar({ onLoginClick, onRegisterClick }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      const el = document.querySelector("[data-scroll-container]");
      if (el) setScrolled(el.scrollTop > 20);
    };
    const el = document.querySelector("[data-scroll-container]");
    el?.addEventListener("scroll", handleScroll, { passive: true });
    return () => el?.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={`absolute left-0 right-0 top-0 z-30 flex min-h-12 items-center justify-between px-4 py-2 transition-[background-color,border-color,backdrop-filter] duration-200 ease-out motion-reduce:transition-none md:min-h-14 md:px-6 md:py-2.5 ${
        scrolled
          ? "border-b border-border/50 bg-background/70 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <AnimatedLogo />

      <HeaderActions onLoginClick={onLoginClick} onRegisterClick={onRegisterClick} />
    </nav>
  );
}
