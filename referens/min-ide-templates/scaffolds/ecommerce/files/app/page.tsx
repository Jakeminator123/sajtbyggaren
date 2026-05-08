import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

const categories = [
  { name: "[Kategori 1]", slug: "category-1", image: "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600&h=400&fit=crop" },
  { name: "[Kategori 2]", slug: "category-2", image: "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=600&h=400&fit=crop" },
  { name: "[Kategori 3]", slug: "category-3", image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=600&h=400&fit=crop" },
];

const featuredProducts = [
  { id: "1", name: "[Produktnamn 1]", price: "[Pris]", image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop", badge: "Nyhet" },
  { id: "2", name: "[Produktnamn 2]", price: "[Pris]", image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop" },
  { id: "3", name: "[Produktnamn 3]", price: "[Pris]", image: "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500&h=500&fit=crop" },
  { id: "4", name: "[Produktnamn 4]", price: "[Pris]", image: "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=500&h=500&fit=crop", badge: "Populär" },
];

export default function Home() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center gap-6 bg-muted/40 px-6 py-24 text-center sm:py-32">
        <Badge variant="outline" className="rounded-full px-4 py-1 text-sm">Välkommen till [Butiksnamn]</Badge>
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
          Upptäck vårt sortiment
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          Handla enkelt online. Snabb leverans och trygga betalningar.
        </p>
        <div className="flex gap-3">
          <Button asChild size="lg" className="rounded-full">
            <Link href="/products">
              Handla nu <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="rounded-full">
            <Link href="/categories">Kategorier</Link>
          </Button>
        </div>
      </section>

      {/* Categories */}
      <section id="kategorier" className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="mb-8 text-2xl font-semibold tracking-tight">Kategorier</h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((cat) => (
            <Link key={cat.slug} href={`/category/${cat.slug}`} className="group">
              <Card className="overflow-hidden transition-shadow hover:shadow-lg">
                <div className="relative aspect-3/2 overflow-hidden">
                  <Image
                    src={cat.image}
                    alt={cat.name}
                    fill
                    className="object-cover transition-transform group-hover:scale-105"
                  />
                </div>
                <CardContent className="p-4">
                  <p className="font-medium">{cat.name}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured Products */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="mb-8 flex items-center justify-between">
          <h2 className="text-2xl font-semibold tracking-tight">Utvalda produkter</h2>
          <Button variant="ghost" className="text-sm">
            Visa alla <ArrowRight className="ml-1 h-3 w-3" />
          </Button>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {featuredProducts.map((product) => (
            <Link key={product.id} href={`/product/${product.id}`} className="group">
              <Card className="overflow-hidden transition-shadow hover:shadow-md">
                <div className="relative aspect-square overflow-hidden bg-muted">
                  <Image
                    src={product.image}
                    alt={product.name}
                    fill
                    className="object-cover transition-transform group-hover:scale-105"
                  />
                  {product.badge && (
                    <Badge className="absolute left-3 top-3 rounded-full">{product.badge}</Badge>
                  )}
                </div>
                <CardContent className="p-4">
                  <p className="font-medium">{product.name}</p>
                  <p className="text-sm text-muted-foreground">{product.price}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
