"use client";

import { Children, type CSSProperties, type ReactNode } from "react";

export interface MarqueeProps {
  children: ReactNode;
  /** Animation direction. Defaults to 'left'. */
  direction?: "left" | "right";
  /** Loop duration preset, OR a CSS time string like '90s'. Defaults to 'medium' = 40s. */
  speed?: "slow" | "medium" | "fast" | (string & {});
  /** Pause animation while the pointer is over the marquee. Defaults to true. */
  pauseOnHover?: boolean;
  /** Spacing between items in the track. Defaults to '2rem'. */
  gap?: string;
  /** Outer wrapper className (background, padding, masking). */
  className?: string;
}

const SPEED_PRESETS: Record<"slow" | "medium" | "fast", string> = {
  slow: "60s",
  medium: "40s",
  fast: "25s",
};

function resolveDuration(speed: MarqueeProps["speed"]): string {
  if (!speed || speed === "medium") return SPEED_PRESETS.medium;
  if (speed === "slow" || speed === "fast") return SPEED_PRESETS[speed];
  return speed;
}

/**
 * CSS-driven horizontal marquee. The visible track duplicates the children
 * once so the loop is seamless. A second copy of the children is rendered
 * outside the moving track, marked with `sr-only` styling, so screen
 * readers and search engines see a normal static list — the moving track
 * is `aria-hidden="true"`. When prefers-reduced-motion is set, the
 * animation freezes via CSS `media (prefers-reduced-motion: reduce)`; the
 * children stay fully visible (no `motion-reduce:hidden` trap).
 */
export function Marquee({
  children,
  direction = "left",
  speed = "medium",
  pauseOnHover = true,
  gap = "2rem",
  className,
}: MarqueeProps) {
  const items = Children.toArray(children);
  const duration = resolveDuration(speed);
  const animationName =
    direction === "right" ? "sajtmaskin-marquee-right" : "sajtmaskin-marquee-left";

  const trackStyle: CSSProperties = {
    gap,
    animationName,
    animationDuration: duration,
    animationTimingFunction: "linear",
    animationIterationCount: "infinite",
  };

  return (
    <div className={`sajtmaskin-marquee group relative overflow-hidden ${className ?? ""}`}>
      <ul className="sr-only">
        {items.map((child, i) => (
          <li key={`mirror-${i}`}>{child}</li>
        ))}
      </ul>

      <div
        aria-hidden="true"
        className={`sajtmaskin-marquee-track flex w-max flex-nowrap items-center ${
          pauseOnHover ? "group-hover:[animation-play-state:paused]" : ""
        }`}
        style={trackStyle}
      >
        {items.map((child, i) => (
          <div key={`a-${i}`} className="shrink-0">
            {child}
          </div>
        ))}
        {items.map((child, i) => (
          <div key={`b-${i}`} className="shrink-0">
            {child}
          </div>
        ))}
      </div>

      <style jsx global>{`
        @keyframes sajtmaskin-marquee-left {
          from {
            transform: translateX(0);
          }
          to {
            transform: translateX(-50%);
          }
        }
        @keyframes sajtmaskin-marquee-right {
          from {
            transform: translateX(-50%);
          }
          to {
            transform: translateX(0);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .sajtmaskin-marquee-track {
            animation: none !important;
            transform: none !important;
          }
        }
      `}</style>
    </div>
  );
}
