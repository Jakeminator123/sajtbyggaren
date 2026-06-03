import type { ReactNode } from "react";

// Gemensam layout för juridiska sidor (cookies, integritetspolicy,
// användarvillkor). Auto-stylar h2/p/ul/a via descendant-selektorer så
// varje sida bara behöver leverera ren semantisk markup. ``draft`` visar en
// tydlig notis om att texten är en platshållare som måste jurist-granskas
// före publik produktion (inga påhittade bindande påståenden).
export function LegalPageLayout({
  title,
  lastUpdated,
  draft = true,
  children,
}: {
  title: string;
  lastUpdated: string;
  draft?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-[760px] px-5 py-20 sm:px-8 sm:py-28">
      <h1 className="text-foreground text-3xl font-semibold tracking-tight sm:text-4xl">
        {title}
      </h1>
      <p className="text-muted-foreground mt-3 text-[13px]">
        Senast uppdaterad: {lastUpdated}
      </p>

      {draft ? (
        <p className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] px-4 py-3 text-[13px] leading-relaxed text-amber-800 dark:text-amber-300">
          Detta är ett utkast. Den slutliga texten granskas innan publik
          lansering.
        </p>
      ) : null}

      <div className="text-muted-foreground mt-10 space-y-5 text-[15px] leading-relaxed [&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-2 [&_h2]:text-foreground [&_h2]:pt-3 [&_h2]:text-[17px] [&_h2]:font-semibold [&_h2]:tracking-tight [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5">
        {children}
      </div>
    </div>
  );
}
