"use client";

import useEmblaCarousel from "embla-carousel-react";
import Autoplay from "embla-carousel-autoplay";
import {
  Children,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface CarouselProps {
  children: ReactNode;
  ariaLabel: string;
  className?: string;
  /** Autoplay delay in ms, or `false` / 0 to disable. Pauses on hover, focus, and when the tab is hidden. */
  autoplay?: number | false;
  /** Visible slides per viewport (1, 2, or 3). Defaults to 1. */
  slidesPerView?: 1 | 2 | 3;
  /** When true, the last slide loops back to the first. Defaults to true. */
  loop?: boolean;
  hideArrows?: boolean;
  hideDots?: boolean;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = () => setReduced(mq.matches);
    handler();
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

const SLIDE_BASIS: Record<1 | 2 | 3, string> = {
  1: "flex-[0_0_100%]",
  2: "flex-[0_0_50%]",
  3: "flex-[0_0_33.3333%]",
};

export function Carousel({
  children,
  ariaLabel,
  className,
  autoplay = false,
  slidesPerView = 1,
  loop = true,
  hideArrows = false,
  hideDots = false,
}: CarouselProps) {
  const reducedMotion = usePrefersReducedMotion();
  const slides = Children.toArray(children);
  const slideCount = slides.length;

  const autoplayDelay = !autoplay || reducedMotion ? null : autoplay;
  const autoplayPlugin = useRef(
    autoplayDelay !== null
      ? Autoplay({ delay: autoplayDelay, stopOnInteraction: false, stopOnMouseEnter: true })
      : null,
  );

  const [emblaRef, emblaApi] = useEmblaCarousel(
    {
      loop,
      align: "start",
      duration: reducedMotion ? 0 : 25,
    },
    autoplayPlugin.current ? [autoplayPlugin.current] : [],
  );

  const [selectedIndex, setSelectedIndex] = useState(0);
  const [scrollSnaps, setScrollSnaps] = useState<number[]>([]);

  const scrollTo = useCallback(
    (index: number) => emblaApi?.scrollTo(index),
    [emblaApi],
  );
  const scrollPrev = useCallback(() => emblaApi?.scrollPrev(), [emblaApi]);
  const scrollNext = useCallback(() => emblaApi?.scrollNext(), [emblaApi]);

  useEffect(() => {
    if (!emblaApi) return;
    const onSelect = () => setSelectedIndex(emblaApi.selectedScrollSnap());
    onSelect();
    setScrollSnaps(emblaApi.scrollSnapList());
    emblaApi.on("select", onSelect);
    emblaApi.on("reInit", onSelect);
    return () => {
      emblaApi.off("select", onSelect);
      emblaApi.off("reInit", onSelect);
    };
  }, [emblaApi]);

  return (
    <section
      role="region"
      aria-roledescription="carousel"
      aria-label={ariaLabel}
      className={className ?? "relative"}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          scrollPrev();
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          scrollNext();
        }
      }}
      tabIndex={0}
    >
      <div ref={emblaRef} className="overflow-hidden">
        <div className="flex">
          {slides.map((slide, i) => (
            <div
              key={i}
              role="group"
              aria-roledescription="slide"
              aria-label={`${i + 1} of ${slideCount}`}
              className={`min-w-0 ${SLIDE_BASIS[slidesPerView]}`}
            >
              {slide}
            </div>
          ))}
        </div>
      </div>

      {!hideArrows && slideCount > 1 && (
        <>
          <button
            type="button"
            onClick={scrollPrev}
            aria-label={`Previous slide in ${ariaLabel}`}
            className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 p-2 shadow ring-1 ring-border backdrop-blur hover:bg-background"
          >
            <span aria-hidden="true">‹</span>
          </button>
          <button
            type="button"
            onClick={scrollNext}
            aria-label={`Next slide in ${ariaLabel}`}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 p-2 shadow ring-1 ring-border backdrop-blur hover:bg-background"
          >
            <span aria-hidden="true">›</span>
          </button>
        </>
      )}

      {!hideDots && scrollSnaps.length > 1 && (
        <div className="mt-3 flex items-center justify-center gap-1.5">
          {scrollSnaps.map((_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => scrollTo(i)}
              aria-label={`Go to slide ${i + 1}`}
              aria-current={i === selectedIndex ? "true" : undefined}
              className={`h-2 rounded-full transition-all ${
                i === selectedIndex ? "w-6 bg-primary" : "w-2 bg-muted-foreground/40"
              }`}
            />
          ))}
        </div>
      )}
    </section>
  );
}
