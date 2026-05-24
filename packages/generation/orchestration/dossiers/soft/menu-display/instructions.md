# When to use

Use this dossier when the brief asks for a restaurant, café, bistro, bar, brunch place, fine-dining venue or any food service that has a menu visitors want to read before deciding to book or walk in. Triggers include `meny`, `menu`, `lunch`, `brunch`, `cuisine`, `restaurang`, `café`, `bistro`, `kök`, `signaturrätt`, `vinlista`, `dryckesmeny`, `dagens`, `à la carte`, `prix fixe`, `tasting menu`.

Best fit:

- A multi-course menu page (`/meny`) with starters, mains, desserts (or equivalent grouping per cuisine).
- A condensed home-page menu preview (3-6 signature dishes) that links to the full menu.
- A rotating lunch menu sub-page where weekday-of-the-week is the primary grouping.
- A drinks or wine list rendered on the same contract.

Do not use for:

- Catering price lists that ship to customer (use a product grid in `ecommerce-lite` instead).
- Single-dish landing pages — those are marketing pages, not menus.

# How to integrate

A menu output MUST deliver these five contract points — anything less ships as a price-list, not a menu:

1. **Course grouping.** The menu is rendered as one or more `<section>` blocks, one per course/category (e.g. *Förrätt*, *Huvudrätt*, *Efterrätt*, *Dryck*). Each section has a clearly-labelled heading. Items inside a section are NOT inter-mixed with items from another category.
2. **Per-item structure.** Every menu item declares: `name` (string), `description` (short string, allergen-aware), `price` (string with currency symbol; `?` is forbidden, missing price is acceptable only when the section is "Pris enligt dagens råvaror"). Optional: `dietaryMarkers` (array: `vegan`, `vegetarian`, `gluten-free`, `lactose-free`, `nuts`, `spicy`).
3. **Dietary key.** If ANY item references a dietary marker, the page must render a small key section explaining each marker once at the top of the menu or in a sticky legend. The key MUST NOT repeat per section.
4. **Price legibility.** Prices use a monospace or tabular-numeric font so they align vertically on desktop. On mobile, item name and price share a row using `flex justify-between`, never separate paragraphs.
5. **Server-rendered.** This dossier is purely presentational. NO `"use client"`, NO state, NO fetch. Menu data is passed in as props from a server component reading `project-input.json` content or scaffold-supplied content. Keep the rendering SSG-friendly so it ships in the initial HTML for SEO.

# Implementation skeleton

```tsx
// components/menu/menu-display.tsx — Server Component, no "use client"

interface MenuItem {
  name: string;
  description?: string;
  price?: string;
  dietaryMarkers?: ReadonlyArray<"vegan" | "vegetarian" | "gluten-free" | "lactose-free" | "nuts" | "spicy">;
}

interface MenuSection {
  id: string;
  title: string;
  items: ReadonlyArray<MenuItem>;
}

interface MenuDisplayProps {
  sections: ReadonlyArray<MenuSection>;
  dietaryKey?: ReadonlyArray<{ marker: string; label: string }>;
}

export function MenuDisplay({ sections, dietaryKey }: MenuDisplayProps) {
  const hasMarkers = sections.some((s) => s.items.some((i) => i.dietaryMarkers?.length));
  return (
    <article aria-label="Meny">
      {hasMarkers && dietaryKey && (
        <aside aria-label="Allergi- och kostnyckel" className="mb-12 text-sm text-muted-foreground">
          {dietaryKey.map(({ marker, label }) => (
            <span key={marker} className="mr-4">
              <strong>{marker}</strong> = {label}
            </span>
          ))}
        </aside>
      )}
      {sections.map((section) => (
        <section key={section.id} aria-labelledby={`menu-${section.id}`} className="mb-16">
          <h2 id={`menu-${section.id}`} className="mb-6 text-2xl font-semibold tracking-tight">
            {section.title}
          </h2>
          <ul className="space-y-6">
            {section.items.map((item) => (
              <li key={item.name} className="flex justify-between gap-8">
                <div>
                  <p className="font-medium">
                    {item.name}
                    {item.dietaryMarkers?.length ? (
                      <span className="ml-2 text-xs uppercase text-muted-foreground">
                        {item.dietaryMarkers.join(" · ")}
                      </span>
                    ) : null}
                  </p>
                  {item.description ? (
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  ) : null}
                </div>
                {item.price ? (
                  <p className="shrink-0 tabular-nums font-medium">{item.price}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
```

The skeleton is a pattern, not a template. Adapt the JSX shape to the variant tokens (e.g. `nordic-fine-dining` may use thinner dividers, `casual-cafe` may use rounded item cards). Keep the five contract points intact.

# Forbidden anti-patterns

- Rendering the menu as a single flat `<table>` with no course grouping.
- Hiding the menu behind a PDF or external link when the brief gave inline dish data.
- Generic placeholder copy like "Maträtt 1 — fantastisk smak" — every item must be a real dish from the brief.
- Adding `useState` or `"use client"` — the menu has no interactive state.
- Adding a "add to cart" button — that is `cart` capability, not `menu`.
