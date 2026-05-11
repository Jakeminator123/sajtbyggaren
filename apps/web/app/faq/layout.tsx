import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FAQ",
  description:
    "Vanliga frågor om Sajtbyggaren — teknik, priser, GDPR och hur snabbt du kan publicera.",
};

export default function FaqLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
