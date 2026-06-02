import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE_NAME, verifySessionToken } from "@/lib/auth/tokens";

// Next 16 proxy-konvention (tidigare middleware.ts). Billig grind framför
// kontosidorna: verifierar BARA cookie-signatur + utgång (Web Crypto, ingen
// DB) — den auktoritativa sessions-/användarslagningen sker i server-
// komponenten (getCurrentUser).
//
// Medvetet smal: bara /konto grindas. /studio (bygg-konsolen) lämnas orört så
// operatörs- och bygg-flöden (och smoke-tester) inte påverkas — bygg-logiken
// ska inte stökas till av auth-arbetet.
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const payload = await verifySessionToken(token);
  if (payload) return NextResponse.next();

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/konto", "/konto/:path*"],
};
