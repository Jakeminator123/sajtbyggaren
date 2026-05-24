# When to use

Use this dossier when the brief explicitly supplies a hero background video asset (an `.mp4`/`.webm` URL or path) AND the operator's domain benefits from motion proof: gyms, dance studios, ski resorts, restaurants showing food preparation, photographers, video producers, event venues. Triggers include `bakgrundsvideo`, `hero-video`, `video i topp`, `motion in hero`, `cinemagraph`, `loop`.

Best fit:

- A home-page hero with a 6-12 second muted loop of authentic action (cooking, training, dancing, the venue full of people).
- A landing-page above-the-fold video for a campaign launch.
- A product-page hero on `ecommerce-lite` when the product is showcased in motion (apparel, kitchenware in use, sports gear).

Do not use for:

- Sites where the brief did NOT supply a real video asset. NEVER generate a stock-footage URL or embed a YouTube placeholder — both produce off-brand content.
- Above-the-fold video on slow-connection target audiences (rural Sweden, Brazil, India). Use a static hero with a play-button-revealing-modal pattern instead.
- Sound-required video (testimonials, narrated walk-throughs). Autoplay-with-sound is blocked by every major browser; those need a click-to-play interactive `video` element.
- Multi-clip hero carousels (rotating videos). That's a separate `hero-video-carousel` capability, not yet implemented.

# How to integrate

A video-hero output MUST deliver these five contract points:

1. **Native `<video>`, no third-party SDK.** Use a single `<video>` element with `autoPlay`, `muted`, `loop`, `playsInline`. NEVER YouTube/Vimeo embeds — they ship 600KB+ trackers, add CSP-violations, and the YouTube logo undermines brand. NEVER mux/cloudflare-stream players unless the brief explicitly opted in.
2. **Poster image MUST be present.** The `poster` attribute renders instantly while the video loads (LCP element). Use a high-quality still extracted from the video itself — same crop, same brightness. Without a poster, the hero is a black rectangle for 1-3 seconds.
3. **`preload="metadata"`, not `"auto"`.** `auto` aggressively pre-downloads the whole video on every page load, including for visitors who scroll past. `metadata` loads only the first ~200KB which is enough to render the poster and start playback when scrolled-into-view.
4. **Reduced-motion fallback.** Wrap the `<video>` in a `<picture>` or check `prefers-reduced-motion` via CSS `@media (prefers-reduced-motion: reduce) { video { display: none; } picture.hero-fallback { display: block; } }`. Visitors with vestibular disorders see the still poster — accessibility AA requirement.
5. **Foreground overlay with text contrast.** The headline + CTA overlay must remain readable when the video reaches its brightest frame. Use a darkening gradient overlay (`linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.6))`) sized to behind-the-text area, NOT a full-image scrim that ruins the visual.

# Implementation skeleton

```tsx
// components/hero/video-hero.tsx — Server Component

interface VideoHeroSource {
  src: string;
  type: "video/mp4" | "video/webm";
}

interface VideoHeroOverlay {
  eyebrow?: string;
  headline: string;
  subhead?: string;
  cta?: {
    label: string;
    href: string;
  };
}

interface VideoHeroProps {
  sources: ReadonlyArray<VideoHeroSource>;
  posterSrc: string;
  posterAlt: string;
  overlay: VideoHeroOverlay;
  reducedMotionPosterOnly?: boolean;
}

export function VideoHero({
  sources,
  posterSrc,
  posterAlt,
  overlay,
}: VideoHeroProps) {
  return (
    <section className="relative isolate aspect-[16/9] w-full overflow-hidden md:aspect-[21/9]">
      <video
        className="absolute inset-0 h-full w-full object-cover motion-reduce:hidden"
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
        poster={posterSrc}
        aria-hidden="true"
      >
        {sources.map((s) => (
          <source key={s.src} src={s.src} type={s.type} />
        ))}
      </video>
      <img
        src={posterSrc}
        alt={posterAlt}
        className="absolute inset-0 hidden h-full w-full object-cover motion-reduce:block"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/0 to-black/55"
      />
      <div className="relative z-10 flex h-full flex-col justify-end p-8 text-white md:p-16">
        {overlay.eyebrow ? (
          <p className="mb-2 text-sm uppercase tracking-wide opacity-80">
            {overlay.eyebrow}
          </p>
        ) : null}
        <h1 className="max-w-3xl text-balance text-4xl font-semibold md:text-6xl">
          {overlay.headline}
        </h1>
        {overlay.subhead ? (
          <p className="mt-4 max-w-2xl text-pretty text-lg opacity-90">
            {overlay.subhead}
          </p>
        ) : null}
        {overlay.cta ? (
          <a
            href={overlay.cta.href}
            className="mt-8 inline-block w-fit rounded-md bg-white px-6 py-3 font-medium text-black"
          >
            {overlay.cta.label}
          </a>
        ) : null}
      </div>
    </section>
  );
}
```

Adapt the JSX to the variant: `midnight-counsel` may strip the bottom gradient for pure top-overlay text, `pulse-fit` may use the energetic-red CTA, `nordic-fine-dining` may use serif headline and a smaller aspect ratio. Keep the five contract points intact.

# Forbidden anti-patterns

- Embedding YouTube/Vimeo iframe as the "hero video" — ships off-brand UI, trackers and a click-to-play overlay on mobile.
- Autoplay with sound (`muted` removed) — blocked by every browser, often silently. The hero appears not to autoplay at all on visitors' first visit.
- 20+ second video loop — visitors notice the loop and the brand feels low-budget. Keep loops 6-12 seconds with a natural-looking cut.
- Skipping the poster — produces a black rectangle as the LCP element, tanks Lighthouse perf.
- Foreground text dropped directly on the brightest video frame without a gradient — the headline becomes invisible on the highest-contrast frame of the loop, the worst possible UX.
- Generating a placeholder `https://example.com/hero.mp4` URL when the brief did not supply a real asset — produces a broken `<video>` element on first load.
