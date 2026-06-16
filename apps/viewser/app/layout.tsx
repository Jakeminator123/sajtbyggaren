import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/app/providers";
import { Analytics } from "@vercel/analytics/next";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://sajtbyggaren.se"),
  title: {
    default: "Sajtbyggaren — din hemsida, byggd med AI",
    template: "%s · Sajtbyggaren",
  },
  description:
    "Sajtbyggaren bygger en färdig företagshemsida åt dig med AI. Beskriv din verksamhet — vi sköter resten.",
};

// Tonar mobilwebbläsarens chrome till samma varma off-white som sajtens
// bakgrund (--background) i stället för webbläsarens standard.
export const viewport: Viewport = {
  themeColor: "#f7f6f2",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="sv"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <Providers>{children}</Providers>
        <Analytics />
      </body>
    </html>
  );
}
