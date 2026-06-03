import type { Metadata } from "next";
import Link from "next/link";

import { LegalPageLayout } from "@/components/marketing/legal-page-layout";

export const metadata: Metadata = {
  title: "Cookies",
  description: "Hur Sajtbyggaren använder cookies.",
};

export default function CookiesPage() {
  return (
    <LegalPageLayout title="Cookiepolicy" lastUpdated="1 juni 2026">
      <p>
        Cookies är små textfiler som sparas i din webbläsare. Vi använder dem
        för att sajten ska fungera och, om du samtycker, för att förstå hur den
        används.
      </p>

      <h2>Nödvändiga cookies</h2>
      <p>
        Krävs för grundläggande funktioner som säkerhet och för att komma ihåg
        ditt cookie-val. De kan inte stängas av och kräver inget samtycke.
      </p>

      <h2>Övriga cookies</h2>
      <p>
        Cookies för statistik och förbättring sätts bara om du aktivt
        accepterar dem i cookie-rutan. Tills du gör det använder vi enbart
        nödvändiga cookies.
      </p>

      <h2>Hantera dina val</h2>
      <p>
        Du kan när som helst ändra ditt val via länken{" "}
        <strong>Hantera cookies</strong> längst ner på sidan.
      </p>

      <h2>Frågor</h2>
      <p>
        Hör av dig via vår <Link href="/kontakt">kontaktsida</Link> om du undrar
        något.
      </p>
    </LegalPageLayout>
  );
}
