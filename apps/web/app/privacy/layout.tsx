import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Integritetspolicy",
  description:
    "Integritetspolicy för Sajtbyggaren — vilka uppgifter vi behandlar, varför, och dina rättigheter under GDPR.",
};

export default function PrivacyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
