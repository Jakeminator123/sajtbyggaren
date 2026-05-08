import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "[Butiksnamn] — Handla online",
  description: "Utforska vårt sortiment och hitta det du letar efter.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv" suppressHydrationWarning>
      <body className={`${inter.variable} antialiased`}>
        <SiteHeader />
        <main className="min-h-[80vh]">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
