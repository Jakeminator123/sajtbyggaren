import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Kontakt",
  description: "Hör av dig till oss bakom Sajtbyggaren.",
};

// Ärlig kontaktsida: ingen backend för formulär ännu, så vi länkar rakt till
// e-post (mailto) i stället för att fejka ett "skickat"-flöde. Byts till ett
// riktigt formulär när en inkorg/endpoint finns.
const CONTACT_EMAIL = "hej@sajtbyggaren.se";

export default function ContactPage() {
  return (
    <div className="mx-auto w-full max-w-[760px] px-5 py-20 sm:px-8 sm:py-28">
      <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
        Kontakt
      </p>
      <h1 className="text-foreground mt-5 max-w-[18ch] text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        Hör av dig — vi svarar gärna.
      </h1>
      <p className="text-muted-foreground mt-5 max-w-[52ch] text-[16px] leading-relaxed">
        Frågor, idéer eller bara nyfiken? Skicka ett mejl så återkommer vi så
        snart vi kan.
      </p>
      <a
        href={`mailto:${CONTACT_EMAIL}`}
        className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 mt-8 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
      >
        {CONTACT_EMAIL}
      </a>
    </div>
  );
}
