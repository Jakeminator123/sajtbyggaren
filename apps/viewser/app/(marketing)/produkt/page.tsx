import type { Metadata } from "next";

import { PlaceholderPage } from "@/components/marketing/placeholder-page";

export const metadata: Metadata = {
  title: "Produkt",
  description:
    "Så fungerar Sajtbyggaren: beskriv din verksamhet, få en färdig hemsida, förhandsgranska och förfina med ord.",
};

export default function ProductPage() {
  return (
    <PlaceholderPage
      title="Produkt"
      note="Här beskriver vi snart hur Sajtbyggaren bygger din hemsida steg för steg — prompt, förhandsvisning och förfining. Under tiden kan du börja bygga direkt."
    />
  );
}
