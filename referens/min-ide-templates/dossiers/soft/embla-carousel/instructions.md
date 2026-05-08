# When to use

Use this dossier whenever the brief mentions a carousel, slider, slideshow, image gallery, or a swipeable row of cards. Triggers (Swedish + English): `carousel`, `slider`, `slideshow`, `gallery`, `swipe`, `karusell`, `bildspel`, `image gallery`, `hero slider`, `produktkarusell`, `kundcase-slider`.

Best fit:

- A hero image slider on a marketing page (3-6 slides, autoplay every 5-7 seconds).
- A product gallery on an e-commerce detail page (single visible slide, prev/next + dots).
- A testimonial / customer-logo row that gently auto-advances on a long landing page.

Do not use for:

- A full-bleed lightbox / modal viewer (use a dedicated lightbox dossier — Embla is for inline-flow slides).
- Vertically stacked content that "scrolls down" (carousels are horizontal by convention; vertical Embla is supported but rarely the right UX).
- A static row of 3 cards that fits on desktop. If everything is visible without sliding, drop the carousel and use a flex/grid row.

# How to integrate

Mount `<Carousel>` with any number of children. Each child is one slide; the wrapper handles the viewport, container, snap, and a11y. Pass `autoplay` (boolean or millisecond delay) for auto-advance and `slidesPerView` to show 1, 2, or 3 slides at once.

```tsx
import { Carousel } from "@/components/carousel";
import Image from "next/image";

const slides = [
  { src: "/hero-1.webp", alt: "Frukost på terrassen" },
  { src: "/hero-2.webp", alt: "Sjöutsikt vid solnedgång" },
  { src: "/hero-3.webp", alt: "Bastu med vedeldning" },
];

export function HeroSlider() {
  return (
    <Carousel
      ariaLabel="Bildgalleri"
      autoplay={5000}
      className="overflow-hidden rounded-2xl"
    >
      {slides.map((slide) => (
        <div
          key={slide.src}
          className="relative aspect-[16/9] flex-[0_0_100%]"
        >
          <Image
            src={slide.src}
            alt={slide.alt}
            fill
            sizes="(min-width: 1024px) 1024px, 100vw"
            priority={slide === slides[0]}
            className="object-cover"
          />
        </div>
      ))}
    </Carousel>
  );
}
```

The wrapper sets `flex-[0_0_<basis>]` automatically based on `slidesPerView`, but you can override per-slide for asymmetric layouts (e.g. a wide hero followed by smaller follow-ups).

# UX rules

- Autoplay is **opt-in** and pauses on hover, on focus, and when the page is hidden (Intersection / Page Visibility API). When `prefers-reduced-motion: reduce` is set, autoplay is disabled and slide transitions snap instantly.
- Always pass `ariaLabel` — screen readers announce "carousel, label" and the prev/next buttons get descriptive labels derived from it.
- Provide a meaningful `alt` on every image. A carousel of `alt=""` images is invisible to screen readers and Google.
- Prev/next buttons are visible by default. Hide them only on touch-first layouts (`hideArrows` prop) — never hide them on desktop.
- Dots indicate position and let users jump. For ≥10 slides the dot strip becomes noisy; use `hideDots` and rely on arrows + swipe instead.
- Keyboard: ArrowLeft / ArrowRight navigate when the carousel viewport has focus.

# Avoid

- Do not nest a carousel inside another carousel. Touch / pointer events fight each other and the parent absorbs swipes meant for the child.
- Do not animate slide content with `motion-reduce:hidden` — that hides the whole slide for users with reduced-motion preference. Animate inside the slide with `motion-safe:`-prefixed classes only.
- Do not put a carousel above the fold without a fixed `aspect-ratio` on the slide container. A late-loading image will reflow the page (CLS hit).
- Do not autoplay faster than every 4 seconds — users cannot read a slide that fast and the WCAG 2.2.2 timing guideline frowns on it.
- Do not use the carousel for legally-required content (terms, refund policy, allergens). Visitors will only see slide 1.
- Do not import `embla-carousel-react/css` — this dossier ships the small amount of CSS it needs inline via Tailwind classes, intentionally avoiding the package's stylesheet.

# Verification

- Tab into the carousel, press ArrowRight → next slide animates in. ArrowLeft → previous.
- Resize to mobile (320px wide) → swipe with touch / drag with mouse → slides snap correctly.
- Set `prefers-reduced-motion: reduce` in DevTools → autoplay stops, transitions become instant snaps.
- Hover over the carousel mid-autoplay → autoplay pauses. Move pointer away → resumes after the configured delay.
- Disable JavaScript → the first slide is visible (graceful degradation), prev/next are inert. This is acceptable for image galleries; for critical content put it outside the carousel entirely.
- Lighthouse accessibility audit reports no `aria-*` violations on the carousel container or buttons.
