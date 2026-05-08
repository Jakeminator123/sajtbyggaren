import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SlidersHorizontal } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

const categoryProducts: Record<string, { title: string; description: string; products: Array<{ id: string; name: string; price: string; image: string; badge?: string }> }> = {
  "category-1": {
    title: "[Kategori 1]",
    description: "Utforska våra mest populära produkter i denna kategori.",
    products: [
      { id: "1", name: "[Produktnamn 1]", price: "[Pris]", image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop", badge: "Nyhet" },
      { id: "4", name: "[Produktnamn 4]", price: "[Pris]", image: "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=500&h=500&fit=crop" },
    ],
  },
  "category-2": {
    title: "[Kategori 2]",
    description: "Noggrant utvalda produkter för vardag och premiumbehov.",
    products: [
      { id: "2", name: "[Produktnamn 2]", price: "[Pris]", image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop" },
      { id: "5", name: "[Produktnamn 5]", price: "[Pris]", image: "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop", badge: "Bästsäljare" },
    ],
  },
  "category-3": {
    title: "[Kategori 3]",
    description: "Produkter för dig som vill kombinera funktion och stil.",
    products: [
      { id: "3", name: "[Produktnamn 3]", price: "[Pris]", image: "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500&h=500&fit=crop" },
      { id: "6", name: "[Produktnamn 6]", price: "[Pris]", image: "https://images.unsplash.com/photo-1617038220319-276d3cfab638?w=500&h=500&fit=crop" },
    ],
  },
};

export default async function CategoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const category = categoryProducts[slug] ?? categoryProducts["category-1"];

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-16">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">{category.title}</h1>
          <p className="max-w-2xl text-muted-foreground">{category.description}</p>
        </div>
        <Button variant="outline" className="gap-2">
          <SlidersHorizontal className="h-4 w-4" />
          Filter (kommer snart)
        </Button>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {category.products.map((product) => (
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
              <CardContent className="space-y-2 p-4">
                <p className="font-medium">{product.name}</p>
                <p className="text-sm text-muted-foreground">{product.price}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
