# When to use

Use this dossier when the brief implies a physical location that visitors need to find: restaurants, salons, clinics, contractors with a showroom, retail shops, gyms, event venues. Triggers include `hitta hit`, `adress`, `karta`, `var ligger`, `find us`, `location`, `directions`, `vägbeskrivning`.

Best fit:

- A `/hitta-hit` or `/kontakt` route that pairs the address block with an embedded map.
- A small map thumbnail in the site footer next to the address line.
- A "Här finns vi" section on the home page for hyperlocal small businesses.

Do not use for:

- Multi-location businesses that need a store locator with search — that requires a custom dossier with a marker layer.
- Showing a delivery zone or service-area polygon — that needs a real maps SDK (planned `mapbox-gl` hard dossier).
- Pure address blocks with no visual map — use the contact-info section, no map embed needed.

# How to integrate

A map-embed output MUST deliver these five contract points:

1. **OpenStreetMap default.** Use an OSM iframe with `https://www.openstreetmap.org/export/embed.html?bbox=...&marker=...` — no API key, no tracker, no cost. Google Maps embeds require billed API keys and ship a 200KB+ tracker that hurts both Lighthouse and GDPR posture.
2. **Address block always rendered.** The map is decorative; the address `<address>` element with street, postal code, city is the source of truth. Visitors with maps blocked, screen-reader users and SEO crawlers all read the `<address>` first.
3. **Native-app deep links.** Every map block includes a "Vägbeskrivning" link that uses `https://www.google.com/maps/dir/?api=1&destination=<address>` on desktop. On mobile the same URL opens the Maps app via OS-level handling. NEVER hardcode `tel:` or platform-specific schemas — let the OS pick.
4. **Lazy iframe.** Use `loading="lazy"` on the iframe so the map is not loaded until visitors scroll near it. Saves 80-200KB of initial-page weight for visitors who never reach the contact section.
5. **Aspect ratio reservation.** The iframe wrapper has an explicit aspect ratio (e.g. `aspect-video` 16:9 or `aspect-[4/3]`) so the page does not jump when the map loads. Avoids CLS-spikes.

# Implementation skeleton

```tsx
// components/map/map-embed.tsx — Server Component

interface MapAddress {
  streetAddress: string;
  postalCode: string;
  addressLocality: string;
  addressCountry?: string;
  latitude?: number;
  longitude?: number;
}

interface MapEmbedProps {
  address: MapAddress;
  bboxPadding?: number;
  aspectRatio?: "video" | "square" | "wide";
}

function buildOsmBbox(lat: number, lng: number, padding: number) {
  return [lng - padding, lat - padding, lng + padding, lat + padding].join(",");
}

export function MapEmbed({
  address,
  bboxPadding = 0.01,
  aspectRatio = "video",
}: MapEmbedProps) {
  const fullAddress = `${address.streetAddress}, ${address.postalCode} ${address.addressLocality}`;
  const directionsHref = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(
    fullAddress,
  )}`;

  const hasCoords =
    typeof address.latitude === "number" && typeof address.longitude === "number";

  const bbox = hasCoords
    ? buildOsmBbox(address.latitude!, address.longitude!, bboxPadding)
    : null;

  const marker = hasCoords ? `${address.latitude},${address.longitude}` : null;

  const osmSrc = bbox
    ? `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${marker}`
    : null;

  const aspectClass =
    aspectRatio === "square"
      ? "aspect-square"
      : aspectRatio === "wide"
        ? "aspect-[2/1]"
        : "aspect-video";

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_2fr]">
      <address className="not-italic text-base leading-relaxed">
        <p className="font-medium">{address.streetAddress}</p>
        <p className="text-muted-foreground">
          {address.postalCode} {address.addressLocality}
        </p>
        {address.addressCountry ? (
          <p className="text-muted-foreground">{address.addressCountry}</p>
        ) : null}
        <a
          href={directionsHref}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-primary underline underline-offset-4"
        >
          Vägbeskrivning →
        </a>
      </address>
      {osmSrc ? (
        <div className={`${aspectClass} overflow-hidden rounded-lg border bg-muted`}>
          <iframe
            src={osmSrc}
            loading="lazy"
            title={`Karta över ${fullAddress}`}
            className="h-full w-full"
          />
        </div>
      ) : (
        <div className={`${aspectClass} grid place-items-center rounded-lg border bg-muted text-sm text-muted-foreground`}>
          Karta laddas när koordinater finns
        </div>
      )}
    </div>
  );
}
```

Adapt the JSX to the variant: `nordic-fine-dining` may strip the rounded corners and use a tight 4:3 frame, `casual-cafe` may use a Polaroid-style border. Keep the five contract points intact.

# Forbidden anti-patterns

- Embedding Google Maps without an API key — produces the "For development purposes only" watermark in production.
- Skipping the `<address>` element when the map is present — defeats SEO + accessibility.
- Loading the iframe eagerly above the fold when no visitor scrolls there in the first paint.
- Hard-coding `geo:` or `maps://` schemes — modern browsers handle the `google.com/maps/dir/?api=1` URL on every platform.
- Rendering a fictional address when coordinates are missing — show the "koordinater saknas" fallback instead.
