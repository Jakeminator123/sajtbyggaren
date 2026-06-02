/**
 * POST /api/auth/login — verifierar e-post + lösenord och skapar en session.
 * Generiskt felmeddelande (läcker inte om e-posten finns). Egen auth-store.
 */

import { NextResponse } from "next/server";

import { authSurfaceDisabled } from "@/lib/auth/guard";
import { clientIp, rateLimit } from "@/lib/auth/rate-limit";
import { createSession } from "@/lib/auth/session";
import { verifyCredentials } from "@/lib/auth/users";
import { loginSchema } from "@/lib/auth/validation";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const off = authSurfaceDisabled();
  if (off) return off;
  const limit = rateLimit(`login:${clientIp(request)}`, 20, 15 * 60 * 1000);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: "För många inloggningsförsök. Försök igen senare." },
      { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Ogiltig förfrågan." }, { status: 400 });
  }

  const parsed = loginSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Fel e-post eller lösenord." },
      { status: 400 },
    );
  }

  const user = verifyCredentials(parsed.data.email, parsed.data.password);
  if (!user) {
    return NextResponse.json(
      { error: "Fel e-post eller lösenord." },
      { status: 401 },
    );
  }

  await createSession(user.id);
  return NextResponse.json({
    user: { id: user.id, email: user.email, name: user.name },
  });
}
