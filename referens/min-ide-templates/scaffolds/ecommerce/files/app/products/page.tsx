import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import Image from "next/image";
import Link from "next/link";

const products = [
  { id: "1", name: "[Produktnamn 1]", price: "[Pris]", image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop", category: "[Kategori 1]" },
  { id: "2", name: "[Produktnamn 2]", price: "[Pris]", image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop", category: "[Kategori 2]" },
  { id: "3", name: "[Produktnamn 3]", price: "[Pris]", image: "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500&h=500&fit=crop", category: "[Kategori 3]" },
  { id: "4", name: "[Produktnamn 4]", price: "[Pris]", image: "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=500&h=500&fit=crop", category: "[Kategori 1]" },
  { id: "5", name: "[Produktnamn 5]", price: "[Pris]", image: "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop", category: "[Kategori 2]" },
  { id: "6", name: "[Produktnamn 6]", price: "[Pris]", image: "https://images.unsplash.com/photo-1617038220319-276d3cfab638?w=500&h=500&fit=crop", category: "[Kategori 3]" },
];

export default function ProductsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-16">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Alla produkter</h1>
        <p className="text-muted-foreground">Utforska hela sortimentet och filtrera vidare per kategori.</p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((product) => (
          <Link key={product.id} href={`/product/${product.id}`} className="group">
            <Card className="overflow-hidden transition-shadow hover:shadow-md">
              <div className="relative aspect-square overflow-hidden bg-muted">
                <Image
                  src={product.image}
                  alt={product.name}
                  fill
                  className="object-cover transition-transform group-hover:scale-105"
                />
              </div>
              <CardContent className="space-y-2 p-4">
                <Badge variant="outline" className="rounded-full">{product.category}</Badge>
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
