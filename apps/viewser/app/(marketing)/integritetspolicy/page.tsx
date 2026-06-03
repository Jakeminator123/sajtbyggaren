import type { Metadata } from "next";
import Link from "next/link";

import { LegalPageLayout } from "@/components/marketing/legal-page-layout";

export const metadata: Metadata = {
  title: "Integritetspolicy",
  description: "Hur Sajtbyggaren behandlar dina personuppgifter.",
};

export default function PrivacyPage() {
  return (
    <LegalPageLayout title="Integritetspolicy" lastUpdated="1 juni 2026">
      <p>
        Vi värnar om din integritet. Här beskriver vi vilka personuppgifter vi
        behandlar, varför, och vilka rättigheter du har enligt GDPR.
      </p>

      <h2>Uppgifter vi behandlar</h2>
      <ul>
        <li>Kontaktuppgifter du själv lämnar, t.ex. när du hör av dig.</li>
        <li>Innehåll du beskriver för att bygga din hemsida.</li>
        <li>Teknisk information som krävs för att leverera tjänsten.</li>
      </ul>

      <h2>Varför vi behandlar dem</h2>
      <p>
        För att leverera och förbättra tjänsten, svara på frågor och uppfylla
        rättsliga skyldigheter.
      </p>

      <h2>Lagring</h2>
      <p>
        Vi sparar uppgifter så länge det behövs för ändamålet eller så länge
        lagen kräver, därefter raderas de.
      </p>

      <h2>Dina rättigheter</h2>
      <p>
        Du har rätt att begära tillgång till, rättelse av eller radering av
        dina uppgifter. Kontakta oss via vår{" "}
        <Link href="/kontakt">kontaktsida</Link> för att utöva dem.
      </p>
    </LegalPageLayout>
  );
}
