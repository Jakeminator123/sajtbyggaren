import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import "@/styles/landing-v2.css";
import { AnalyticsTracker } from "@/components/layout/analytics-tracker";
import { CookieBanner } from "@/components/layout/cookie-banner";
import { OrganizationJsonLd, SoftwareApplicationJsonLd } from "@/components/layout/json-ld";
import { VercelInsights } from "@/components/layout/vercel-insights";
import { ThemeProvider } from "next-themes";
import { Toaster } from "@/components/ui/sonner";
import { URLS } from "@/lib/config";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Sajtbyggaren – AI-driven webbplatsgenerering",
    template: "%s | Sajtbyggaren",
  },
  description:
    "Skapa professionella webbplatser på minuter med AI. En tjänst från Pretty Good AB.",
  metadataBase: new URL(URLS.baseUrl),
  icons: {
    icon: "/icon.svg",
  },
  openGraph: {
    type: "website",
    locale: "sv_SE",
    siteName: "Sajtbyggaren",
  },
  twitter: {
    card: "summary_large_image",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const requestHeaders = await headers();
  const nonce = requestHeaders.get("x-csp-nonce") ?? undefined;
  const enableVercelInsights = Boolean(process.env.VERCEL_ENV);

  return (
    <html
      lang="sv"
      className={`${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{
            __html: `(function(){try{document.documentElement.classList.remove('dark');document.documentElement.style.colorScheme='light';localStorage.setItem('theme','light')}catch(e){}})()`,
          }}
        />
      </head>
      <body className="font-sans antialiased">
        <noscript>
          <div className="noscript-fallback">
            <h1>Sajtbyggaren</h1>
            <p>AI-driven webbplatsgenerering. Skapa professionella webbplatser på minuter med AI.</p>
            <p>JavaScript krävs för att använda Sajtbyggaren.</p>
          </div>
        </noscript>
        <ThemeProvider attribute="class" defaultTheme="light" forcedTheme="light" enableSystem={false} nonce={nonce}>
          <OrganizationJsonLd nonce={nonce} />
          <SoftwareApplicationJsonLd nonce={nonce} />
          <AnalyticsTracker />
          <VercelInsights enabled={enableVercelInsights} />
          {children}
          <Toaster position="top-right" />
          <CookieBanner />
        </ThemeProvider>
      </body>
    </html>
  );
}
