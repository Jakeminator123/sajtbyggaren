import Link from "next/link";

import { LOGIN_HREF } from "@/lib/auth-config";

// Lösenordsåterställning kräver e-postutskick, vilket är medvetet uppskjutet
// (beslut 2026-06-02). Tills mail-transporten är på plats hänvisar vi ärligt
// till support istället för att fejka ett återställningsflöde.
export default function ForgotPasswordPage() {
  return (
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-foreground text-2xl font-semibold tracking-tight">
          Glömt lösenordet?
        </h1>
        <p className="text-muted-foreground text-[15px] leading-relaxed">
          Vi rullar snart ut återställning via e-post. Under tiden — mejla oss
          på{" "}
          <a
            href="mailto:hej@sajtbyggaren.se"
            className="text-foreground font-medium underline-offset-4 hover:underline"
          >
            hej@sajtbyggaren.se
          </a>{" "}
          så hjälper vi dig tillbaka in i ditt konto.
        </p>
      </div>
      <Link
        href={LOGIN_HREF}
        className="border-border text-foreground hover:bg-muted focus-visible:ring-ring/50 inline-flex h-12 items-center justify-center rounded-full border text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        Tillbaka till inloggning
      </Link>
    </div>
  );
}
