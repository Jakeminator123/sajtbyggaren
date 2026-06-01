import type { Metadata } from "next";
import Link from "next/link";

import { LegalPageLayout } from "@/components/marketing/legal-page-layout";

export const metadata: Metadata = {
  title: "Användarvillkor",
  description: "Villkoren för att använda Sajtbyggaren.",
};

export default function TermsPage() {
  return (
    <LegalPageLayout title="Användarvillkor" lastUpdated="1 juni 2026">
      <p>
        Genom att använda Sajtbyggaren godkänner du dessa villkor. Läs dem
        gärna innan du börjar.
      </p>

      <h2>Tjänsten</h2>
      <p>
        Sajtbyggaren hjälper dig att skapa och förfina en företagshemsida med
        hjälp av AI. Vi utvecklar tjänsten löpande och funktioner kan ändras.
      </p>

      <h2>Ditt ansvar</h2>
      <ul>
        <li>Att innehållet du lägger in inte kränker andras rättigheter.</li>
        <li>Att du följer gällande lag när du använder tjänsten.</li>
      </ul>

      <h2>Vårt ansvar</h2>
      <p>
        Vi strävar efter en stabil tjänst men kan inte garantera att den alltid
        är fri från avbrott eller fel.
      </p>

      <h2>Ändringar</h2>
      <p>
        Vi kan uppdatera villkoren. Väsentliga ändringar informerar vi om innan
        de börjar gälla.
      </p>

      <h2>Kontakt</h2>
      <p>
        Frågor om villkoren? Hör av dig via vår{" "}
        <Link href="/kontakt">kontaktsida</Link>.
      </p>
    </LegalPageLayout>
  );
}
