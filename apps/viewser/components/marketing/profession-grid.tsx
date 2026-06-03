"use client";

import { motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { PROFESSIONS, type Profession } from "@/lib/professions";

// Interaktiv "living wall" (P3). Responsiv grid av yrkesrutor som på en lång
// timer byter plats två och två med en mjuk FLIP-animation (Framer Motions
// layout-prop). En swap per tick + lång vila = premium, inte skärmsläckare.
// P4 byter tile-länken från /studio till /for/[slug] när landningssidorna
// finns (P4) — varje ruta länkar nu till sin landningssida /for/[slug].
//
// A11y/perf: prefers-reduced-motion stänger AV auto-swap helt (ingen
// rörelse); animeringen pausas vid hover/fokus (rutan glider aldrig bort
// från en klickare), när fliken är dold och när väggen är utanför viewporten.
// Fast aspect-ratio = noll CLS; bara transform/opacity animeras.
const SWAP_INTERVAL_MS = 4000;

function swapTwo(list: readonly Profession[]): Profession[] {
  const next = [...list];
  if (next.length < 2) return next;
  const i = Math.floor(Math.random() * next.length);
  let j = Math.floor(Math.random() * next.length);
  while (j === i) j = Math.floor(Math.random() * next.length);
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

export function ProfessionGrid() {
  const reduced = useReducedMotion();
  const [order, setOrder] = useState<Profession[]>(() => [...PROFESSIONS]);
  const pausedRef = useRef(false);
  const wallRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (reduced) return;
    const el = wallRef.current;
    let visible = true;
    const io = el
      ? new IntersectionObserver(
          ([entry]) => {
            visible = entry.isIntersecting;
          },
          { threshold: 0.15 },
        )
      : null;
    if (io && el) io.observe(el);

    const id = window.setInterval(() => {
      if (pausedRef.current || document.hidden || !visible) return;
      setOrder((prev) => swapTwo(prev));
    }, SWAP_INTERVAL_MS);

    return () => {
      window.clearInterval(id);
      if (io) io.disconnect();
    };
  }, [reduced]);

  const pause = () => {
    pausedRef.current = true;
  };
  const resume = () => {
    pausedRef.current = false;
  };

  return (
    <ul
      ref={wallRef}
      onMouseEnter={pause}
      onMouseLeave={resume}
      onFocusCapture={pause}
      onBlurCapture={resume}
      className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-5"
    >
      {order.map((p) => (
        <motion.li
          key={p.slug}
          layout
          transition={{ type: "spring", stiffness: 320, damping: 34, mass: 0.9 }}
        >
          <Link
            href={`/for/${p.slug}`}
            aria-label={`${p.displayName} — se hur en hemsida kan se ut`}
            className="group focus-visible:ring-ring/50 border-border/60 relative block aspect-[4/3] overflow-hidden rounded-2xl border focus-visible:ring-2 focus-visible:outline-none"
          >
            <Image
              src={p.image}
              alt={p.displayName}
              fill
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
              className="object-cover transition-transform duration-700 ease-out group-hover:scale-105"
            />
            <span
              aria-hidden
              className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent"
            />
            <span className="absolute bottom-2.5 left-3 text-[13px] font-medium text-white drop-shadow-sm">
              {p.displayName}
            </span>
          </Link>
        </motion.li>
      ))}
    </ul>
  );
}
