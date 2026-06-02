/**
 * Server-guard för auth/billing-ytan. När ``NEXT_PUBLIC_AUTH_ENABLED`` inte är
 * "true" är hela auth/checkout-ytan avstängd (dormant groundwork): API-routes
 * svarar 404 så ingen kan logga in/registrera/köpa innan operatören flippar på
 * featuren. UI-sidorna gardas separat med ``notFound()``; kärnloopen rörs inte.
 */

import { NextResponse } from "next/server";

import { AUTH_ENABLED } from "@/lib/auth-config";

/**
 * Returnerar ett 404-svar om auth-ytan är avstängd, annars ``null``. Anropas
 * först i auth/checkout-routes: ``const off = authSurfaceDisabled(); if (off) return off;``
 */
export function authSurfaceDisabled(): NextResponse | null {
  if (AUTH_ENABLED) return null;
  return NextResponse.json({ error: "Inte tillgängligt." }, { status: 404 });
}
