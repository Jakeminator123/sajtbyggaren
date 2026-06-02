import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth/auth-form";
import { isSafeNext } from "@/lib/auth-config";
import { getCurrentUser } from "@/lib/auth/session";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  // Redan inloggad → hoppa förbi login. ``//evil.com`` och ``/\evil`` är
  // protokoll-relativa öppna redirects — kräv en ren intern path.
  if (await getCurrentUser()) {
    redirect(isSafeNext(next) ? next! : "/konto");
  }

  return (
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-foreground text-2xl font-semibold tracking-tight">
          Logga in
        </h1>
        <p className="text-muted-foreground text-[15px] leading-relaxed">
          Välkommen tillbaka. Logga in för att fortsätta bygga.
        </p>
      </div>
      <AuthForm mode="login" next={next} />
    </div>
  );
}
