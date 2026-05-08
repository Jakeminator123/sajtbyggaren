import Link from "next/link";

const footerLinks = {
  Butik: [
    { label: "Alla produkter", href: "/products" },
    { label: "Kategorier", href: "/categories" },
    { label: "Kategori 1", href: "/category/category-1" },
    { label: "Kategori 2", href: "/category/category-2" },
  ],
  Info: [
    { label: "Om oss", href: "/om" },
    { label: "Produkter", href: "/products" },
    { label: "Kategorier", href: "/categories" },
    { label: "Hem", href: "/" },
  ],
};

export function SiteFooter() {
  return (
    <footer className="border-t px-6 py-12">
      <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-3">
        <div className="space-y-4">
          <p className="text-lg font-bold tracking-tight">[Butiksnamn]</p>
          <p className="max-w-sm text-sm leading-7 text-muted-foreground">
            Din destination för [produkttyp]. Snabb leverans, trygga betalningar och personlig service.
          </p>
        </div>
        {Object.entries(footerLinks).map(([title, items]) => (
          <div key={title} className="space-y-3">
            <p className="text-sm font-medium">{title}</p>
            <div className="space-y-2">
              {items.map((link) => (
                <Link key={link.href} href={link.href} className="block text-sm text-muted-foreground transition-colors hover:text-foreground">
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mx-auto mt-10 max-w-6xl border-t pt-6 text-center text-xs text-muted-foreground">
        &copy; {new Date().getFullYear()} [Butiksnamn]. Alla rättigheter förbehållna.
      </div>
    </footer>
  );
}

export default SiteFooter;
