# When to use

Use this dossier when the brief asks for visual atmosphere proof — restaurant interiors, salon work, portfolio shots, completed renovation projects, event photos, product lifestyle shots. Triggers include `bildgalleri`, `galleri`, `portfolio`, `referensbilder`, `kundprojekt`, `inspiration`, `atmosphere`, `before-and-after`.

Best fit:

- A dedicated `/galleri` route showing 12-24 atmosphere/portfolio images.
- A home-page strip of 4-8 featured images that links to the full gallery.
- An "Tidigare projekt" or "Vårt arbete" page on a craftsman/clinic site.
- Press-photo grids on event/conference pages.

Do not use for:

- Product cards with price + add-to-cart (use `ecommerce-lite` product grid instead).
- A single hero image (use the hero section, not a gallery).
- Image carousels where one image is shown at a time (use `carousel` capability instead — gallery is a static grid).

# How to integrate

An image gallery output MUST deliver these five contract points:

1. **Responsive grid.** Default: 1 column < 640px, 2 columns 640-1024px, 3 columns 1024-1440px, 4 columns > 1440px. Use CSS `grid-template-columns: repeat(auto-fit, minmax(<min>, 1fr))` so the layout never breaks on odd image counts.
2. **Semantic alt text.** Every image has a meaningful `alt` from the brief (e.g. "Eldat surdegsbröd ur stenugn") — NEVER `alt="image"`, `alt="bild"` or empty. If no alt is supplied, fall back to a numbered placeholder like `Galleribild ${index + 1} av ${total}` but log a planner warning so the operator notices.
3. **Native lazy loading.** Every `<img>` after the first 4 visible ones uses `loading="lazy"` and `decoding="async"`. The first 4 (above-the-fold on desktop) use `loading="eager"` and `fetchpriority="high"` to keep LCP within budget.
4. **Aspect ratio reservation.** Every image declares explicit `width` and `height` (or `aspectRatio` CSS) so the grid does not re-flow when images load. Prevents CLS spikes that tank Lighthouse perf scores.
5. **No JS lightbox by default.** The grid is plain HTML — no `"use client"`, no state, no overlay. If the operator wants a fullscreen viewer, they can add the planned `yet-another-react-lightbox` hard dossier on top.

# Implementation skeleton

```tsx
// components/gallery/image-gallery.tsx — Server Component

interface GalleryImage {
  src: string;
  alt: string;
  width: number;
  height: number;
  caption?: string;
}

interface ImageGalleryProps {
  images: ReadonlyArray<GalleryImage>;
  columns?: { sm: 1 | 2; md: 2 | 3; lg: 3 | 4 };
  eagerLoadCount?: number;
}

export function ImageGallery({
  images,
  columns = { sm: 1, md: 2, lg: 3 },
  eagerLoadCount = 4,
}: ImageGalleryProps) {
  return (
    <ul
      role="list"
      className={`grid gap-4 grid-cols-${columns.sm} md:grid-cols-${columns.md} lg:grid-cols-${columns.lg}`}
    >
      {images.map((img, i) => (
        <li key={img.src} className="overflow-hidden rounded-lg bg-muted">
          <figure>
            <img
              src={img.src}
              alt={img.alt}
              width={img.width}
              height={img.height}
              loading={i < eagerLoadCount ? "eager" : "lazy"}
              decoding="async"
              fetchPriority={i < eagerLoadCount ? "high" : "auto"}
              className="h-full w-full object-cover transition hover:scale-[1.02]"
            />
            {img.caption ? (
              <figcaption className="px-3 py-2 text-sm text-muted-foreground">
                {img.caption}
              </figcaption>
            ) : null}
          </figure>
        </li>
      ))}
    </ul>
  );
}
```

Adapt the JSX shape to the variant tokens: `nordic-fine-dining` may use square 1:1 crops with no captions, `casual-cafe` may use varied aspect ratios with Polaroid-style borders, `warm-bistro` may use rounded-lg images on a cream background. Keep the five contract points intact.

# Forbidden anti-patterns

- Rendering placeholder `https://placehold.co/600x400` URLs in production output.
- Empty `alt=""` on every image (acceptable only for purely decorative chrome, never for content photos).
- Loading all 24 images eagerly — kills LCP and mobile bandwidth.
- Embedding a 200KB JS lightbox library when the brief did not request fullscreen viewing.
- Generating images via inline `style={{ backgroundImage: ... }}` — search engines and screen readers ignore CSS backgrounds.
