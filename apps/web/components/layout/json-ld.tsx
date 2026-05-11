interface JsonLdProps {
  nonce?: string;
}

export function OrganizationJsonLd({ nonce }: JsonLdProps) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Pretty Good AB",
    alternateName: "Sajtstudio",
    url: "https://sajtstudio.se",
    sameAs: ["https://sajtmaskin.se"],
  };

  return (
    <script
      nonce={nonce}
      suppressHydrationWarning
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export function SoftwareApplicationJsonLd({ nonce }: JsonLdProps) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Sajtmaskin",
    applicationCategory: "WebApplication",
    operatingSystem: "Web",
    description: "AI-driven webbplatsgenerering. Skapa professionella webbplatser på minuter.",
    url: "https://sajtmaskin.se",
    offers: {
      "@type": "Offer",
      price: "49",
      priceCurrency: "SEK",
      description: "Startpaket med 10 credits",
    },
    creator: {
      "@type": "Organization",
      name: "Pretty Good AB",
      url: "https://sajtstudio.se",
    },
  };

  return (
    <script
      nonce={nonce}
      suppressHydrationWarning
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
