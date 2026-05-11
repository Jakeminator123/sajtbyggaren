import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Användarvillkor",
  description:
    "Användarvillkor för Sajtbyggaren — vad du får och inte får göra med tjänsten.",
};

export default function TermsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
