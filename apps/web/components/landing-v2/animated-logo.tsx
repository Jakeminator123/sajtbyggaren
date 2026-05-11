"use client";

import Image from "next/image";
import Link from "next/link";

export function AnimatedLogo({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-2 select-none transition-opacity duration-200 hover:opacity-80 ${className}`}
      aria-label="Sajtbyggaren – startsida"
    >
      <Image
        src="/icon.svg"
        alt=""
        aria-hidden="true"
        width={28}
        height={28}
        className="h-6 w-6 md:h-7 md:w-7"
        priority
      />
      <span className="font-heading text-base font-semibold tracking-tight text-foreground md:text-lg">
        Sajtbyggaren
      </span>
    </Link>
  );
}
