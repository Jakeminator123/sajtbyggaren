import { Card, CardContent } from "@/components/ui/card";
import Image from "next/image";
import Link from "next/link";

const categories = [
  { name: "[Kategori 1]", slug: "category-1", image: "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=800&h=500&fit=crop" },
  { name: "[Kategori 2]", slug: "category-2", image: "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=800&h=500&fit=crop" },
  { name: "[Kategori 3]", slug: "category-3", image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=800&h=500&fit=crop" },
];

export default function CategoriesPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-16">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Kategorier</h1>
        <p className="text-muted-foreground">Välj en kategori för att se relevanta produkter.</p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((category) => (
          <Link key={category.slug} href={`/category/${category.slug}`} className="group">
            <Card className="overflow-hidden transition-shadow hover:shadow-md">
              <div className="relative aspect-4/3 overflow-hidden">
                <Image
                  src={category.image}
                  alt={category.name}
                  fill
                  className="object-cover transition-transform group-hover:scale-105"
                />
              </div>
              <CardContent className="p-4">
                <p className="font-medium">{category.name}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
