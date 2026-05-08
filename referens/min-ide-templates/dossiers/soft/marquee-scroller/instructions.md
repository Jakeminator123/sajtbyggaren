# When to use

Use this dossier whenever the brief asks for a horizontal scrolling row of items — logo strips, customer quote tickers, "as seen in" press rows, or news headline crawls. Triggers (Swedish + English): `marquee`, `ticker`, `logo strip`, `logo cloud`, `as seen in`, `press strip`, `customer logos`, `kundloggor`, `loggrad`, `nyhetstickér`, `rullande text`, `bandscroll`.

Best fit:

- A "Trusted by 200+ teams" logo strip near the top of a SaaS landing page.
- An infinite quote ticker on a marketing page that auto-scrolls one or two short testimonials.
- A press-mention row ("As seen in TechCrunch, Wired, …") that loops slowly.

Do not use for:

- A full carousel where each slide deserves attention (use `embla-carousel` — marquees are for ambient, peripheral content).
- A list users need to read carefully. Marquees are decorative; anything important must also be available in static form.
- A vertical news feed (those should be a `<ul>` with regular scroll, not a marquee).

# How to integrate

`<Marquee>` clones its children once internally so the animation is a perfectly seamless loop without you having to duplicate items by hand. Pass any number of children — typically a row of `<Image>` or short `<span>` elements wrapped in a flex container.

```tsx
import { Marquee } from "@/components/marquee";
import Image from "next/image";

const logos = [
  { src: "/logos/acme.svg", alt: "Acme" },
  { src: "/logos/globex.svg", alt: "Globex" },
  { src: "/logos/initech.svg", alt: "Initech" },
  { src: "/logos/umbrella.svg", alt: "Umbrella" },
  { src: "/logos/soylent.svg", alt: "Soylent" },
];

export function LogoStrip() {
  return (
    <section
      aria-label="Customer logos"
      className="border-y bg-muted/20 py-8"
    >
      <Marquee speed="slow" pauseOnHover className="opacity-70">
        {logos.map((logo) => (
          <Image
            key={logo.src}
            src={logo.src}
            alt={logo.alt}
            width={120}
            height={32}
            className="mx-8 h-8 w-auto grayscale"
          />
        ))}
      </Marquee>
    </section>
  );
}
```

For a quote ticker, pass `<blockquote>` elements directly:

```tsx
<Marquee speed="medium" gap="3rem">
  <blockquote>"Saved us 12 hours per week." — Eva, COO @ Acme</blockquote>
  <blockquote>"Pays for itself." — Tomas, CFO @ Globex</blockquote>
  <blockquote>"The onboarding alone is worth it." — Malin, PM @ Initech</blockquote>
</Marquee>
```

# UX rules

- Marquees are **decorative**. Pair every marquee with a static fallback that conveys the same information for screen readers and SEO. The wrapper sets `aria-hidden="true"` on the moving track and exposes a non-moving `<ul>` of the children to assistive tech via the visually-hidden mirror.
- **Reduced motion is a hard requirement.** When `prefers-reduced-motion: reduce` is set, the marquee FREEZES — the children stay visible, the animation simply stops. Never apply `motion-reduce:hidden` to the marquee or its children; that hides the content for the very users who most need a static layout.
- Pause on hover by default for any marquee with text. Hover-pause is optional for pure logo strips.
- Keep speed slow (`60s` per loop or longer for logos, `40s` for short quotes). Anything faster is hostile to anyone trying to read it.
- Maintain a generous `gap` between items (`2rem` minimum). A cramped marquee reads as a single garbled blur.
- Do not stack two marquees moving in the same direction at the same speed. If you need two rows, alternate directions (`direction="left"` + `direction="right"`) for visual interest.

# Avoid

- Do not animate `width`, `left`, or `margin` to fake a marquee. The wrapper uses `transform: translateX()` for GPU compositing — paraphrasing the keyframes with layout-affecting properties tanks performance and causes layout-thrashing on every frame.
- Do not put interactive elements (`<button>`, `<a href>`) inside a fast-moving marquee. The user cannot reliably click a moving target. If the brief needs clickable logos, slow the speed to ≥120s per loop AND `pauseOnHover` to true.
- Do not use marquees for legally-required text (terms, allergens, disclaimers). Visitors may never catch the loop.
- Do not nest a marquee inside another marquee. Compositing animations stack per layer and the inner one will jank visibly.
- Do not put a marquee with `direction="right"` next to text the user is reading left-to-right — the conflicting motion is uncomfortable.

# Verification

- View the marquee — children scroll smoothly without jumps at the loop seam.
- Hover the marquee → animation pauses if `pauseOnHover` is true.
- Set `prefers-reduced-motion: reduce` in DevTools → animation freezes, content stays visible. Inspect the DOM: the moving track is `aria-hidden="true"`, the static mirror exposes the same items to a screen reader.
- Tab through the page → focus does NOT enter the marquee track (it is `aria-hidden`). Interactive children, if any, must live in the static mirror or in a separate static row.
- Run Lighthouse Performance audit → no layout-shift caused by the marquee on initial paint.
- Inspect compositing in DevTools (Performance → Rendering → Layer borders) → the marquee track has its own compositor layer (transform animation, not a paint-driven one).
