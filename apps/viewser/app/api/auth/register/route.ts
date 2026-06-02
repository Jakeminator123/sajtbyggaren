/**
 * POST /api/auth/register — skapar ett konto, loggar in och ger gratis
 * start-krediter. Rör INTE bygg-pipelinen; egen auth-store (lib/auth/*).
 */

import { NextResponse } from "next/server";

import { addCredits } from "@/lib/auth/credits";
import { clientIp, rateLimit } from "@/lib/auth/rate-limit";
import { createSession } from "@/lib/auth/session";
import { createUser, emailExists } from "@/lib/auth/users";
import { registerSchema } from "@/lib/auth/validation";
import { FREE_SIGNUP_CREDITS } from "@/lib/billing/plans";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const limit = rateLimit(`register:${clientIp(request)}`, 10, 60 * 60 * 1000);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: "För många försök. Försök igen senare." },
      { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Ogiltig förfrågan." }, { status: 400 });
  }

  const parsed = registerSchema.safeParse(body);
  if (!parsed.success) {
    const message = parsed.error.issues[0]?.message ?? "Ogiltiga uppgifter.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const { email, password, name } = parsed.data;
  if (emailExists(email)) {
    return NextResponse.json(
      { error: "Det finns redan ett konto med den e-postadressen." },
      { status: 409 },
    );
  }

  const user = createUser(email, password, name ?? null);
  if (FREE_SIGNUP_CREDITS > 0) {
    addCredits(user.id, FREE_SIGNUP_CREDITS, "signup-bonus");
  }
  await createSession(user.id);

  return NextResponse.json(
    { user: { id: user.id, email: user.email, name: user.name } },
    { status: 201 },
  );
}
