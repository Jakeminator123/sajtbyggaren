import Link from "next/link";

import { STUDIO_HREF } from "@/lib/auth-config";

// Minimal, on-brand platshållare för marknadssidor som byggs ut i senare
// faser (Produkt/Om oss/Kontakt + legal). Finns i P0 enbart så header- och
// footer-länkar aldrig 404:ar innan riktigt innehåll landar. Avsiktligt
// återhållsam: rubrik + en mening + en väg vidare.
export function PlaceholderPage({
  title,
  note,
}: {
  title: string;
  note: string;
}) {
  return (
    <section className="mx-auto flex w-full max-w-[760px] flex-col items-start gap-5 px-5 py-24 sm:px-8 sm:py-32">
      <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
        Sajtbyggaren
      </p>
      <h1 className="text-foreground text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h1>
      <p className="text-muted-foreground max-w-[60ch] text-[15px] leading-relaxed">
        {note}
      </p>
      <Link
        href={STUDIO_HREF}
        className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 mt-2 inline-flex h-11 items-center rounded-full px-6 text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        Bygg din hemsida
      </Link>
    </section>
  );
}
