import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth/auth-form";
import { isSafeNext } from "@/lib/auth-config";
import { getCurrentUser } from "@/lib/auth/session";
import { FREE_SIGNUP_CREDITS } from "@/lib/billing/plans";

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  // ``//evil.com``/``/\evil`` är öppna redirects — kräv ren intern path.
  if (await getCurrentUser()) {
    redirect(isSafeNext(next) ? next! : "/konto");
  }

  return (
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-foreground text-2xl font-semibold tracking-tight">
          Skapa konto
        </h1>
        <p className="text-muted-foreground text-[15px] leading-relaxed">
          {FREE_SIGNUP_CREDITS > 0
            ? `Skapa ett konto så bjuder vi på ${FREE_SIGNUP_CREDITS} bygg-kredit att prova med.`
            : "Skapa ett konto för att bygga och spara dina sajter."}
        </p>
      </div>
      <AuthForm mode="register" next={next} />
    </div>
  );
}
