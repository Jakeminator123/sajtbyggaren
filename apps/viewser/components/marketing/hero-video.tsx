"use client";

import Image from "next/image";
import { useSyncExternalStore } from "react";

// Full-bleed bakgrundsvideo för hero:n. Respekterar prefers-reduced-motion:
// då renderas posterbilden still i stället för en autoplayande video.
// Posterbilden (hero-poster.webp, en frame ur SB-film.mp4) är samtidigt
// LCP-elementet och syns innan videon hunnit buffra.
//
// prefers-reduced-motion läses via useSyncExternalStore (Reacts kanoniska
// väg att prenumerera på en extern store som matchMedia) i st.f.
// useEffect+setState — undviker react-hooks/set-state-in-effect och ger en
// deterministisk SSR-snapshot (rörelse OK) som matchar första klient-render.
const POSTER = "/hero-poster.webp";
const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(callback: () => void) {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getSnapshot() {
  return window.matchMedia(QUERY).matches;
}

function getServerSnapshot() {
  return false;
}

export function HeroVideo() {
  const reducedMotion = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  if (reducedMotion) {
    return (
      <Image
        src={POSTER}
        alt=""
        aria-hidden
        fill
        priority
        sizes="100vw"
        className="object-cover"
      />
    );
  }

  return (
    <video
      poster={POSTER}
      autoPlay
      muted
      loop
      playsInline
      preload="metadata"
      aria-hidden
      className="absolute inset-0 h-full w-full object-cover"
    >
      <source
        src="/film-sm-mobile.mp4"
        media="(max-width: 640px)"
        type="video/mp4"
      />
      <source src="/SB-film.mp4" type="video/mp4" />
    </video>
  );
}
