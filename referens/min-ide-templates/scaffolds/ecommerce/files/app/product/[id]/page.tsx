import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";

const products: Record<string, { name: string; price: string; description: string; category: string; image: string; bullets: string[] }> = {
  "1": {
    name: "[Produktnamn 1]",
    price: "[Pris]",
    description: "Kort produktbeskrivning som lyfter värde, material och användningsområde.",
    category: "[Kategori 1]",
    image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=1000&h=1000&fit=crop",
    bullets: ["Snabb leverans", "14 dagars returrätt", "Trygg betalning"],
  },
  "2": {
    name: "[Produktnamn 2]",
    price: "[Pris]",
    description: "Kort produktbeskrivning som hjälper kunden att förstå varför produkten passar.",
    category: "[Kategori 2]",
    image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1000&h=1000&fit=crop",
    bullets: ["Populärt val", "Premiumkvalitet", "Fri frakt över [Belopp]"],
  },
  "3": {
    name: "[Produktnamn 3]",
    price: "[Pris]",
    description: "Kort produktbeskrivning med fokus på nytta och kvalitet.",
    category: "[Kategori 3]",
    image: "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=1000&h=1000&fit=crop",
    bullets: ["Kundfavorit", "Snabb support", "Säker checkout"],
  },
};

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = products[id];

  if (!product) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="overflow-hidden">
          <div className="relative aspect-square bg-muted">
            <Image src={product.image} alt={product.name} fill className="object-cover" />
          </div>
        </Card>
        <div className="space-y-6">
          <div className="space-y-3">
            <Badge variant="outline" className="rounded-full">{product.category}</Badge>
            <h1 className="text-3xl font-semibold tracking-tight">{product.name}</h1>
            <p className="text-2xl font-semibold">{product.price}</p>
            <p className="text-muted-foreground">{product.description}</p>
          </div>
          <div className="space-y-2">
            {product.bullets.map((item) => (
              <p key={item} className="text-sm text-muted-foreground">• {item}</p>
            ))}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button size="lg">Lägg i varukorgen</Button>
            <Button size="lg" variant="outline">Köp nu</Button>
          </div>
          <Link
            href="/products"
            className="inline-flex text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Tillbaka till produkter
          </Link>
        </div>
      </div>
      <section className="mt-16 space-y-4">
        <h2 className="text-2xl font-semibold tracking-tight">Relaterade produkter</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(products)
            .filter(([productId]) => productId !== id)
            .map(([productId, item]) => (
              <Link key={productId} href={`/product/${productId}`}>
                <Card className="transition-shadow hover:shadow-md">
                  <CardContent className="space-y-2 p-4">
                    <p className="font-medium">{item.name}</p>
                    <p className="text-sm text-muted-foreground">{item.price}</p>
                  </CardContent>
                </Card>
              </Link>
            ))}
        </div>
      </section>
    </div>
  );
}
