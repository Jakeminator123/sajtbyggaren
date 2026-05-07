import { NextResponse } from "next/server";

const LOCAL_HOST_NAMES = new Set(["localhost", "127.0.0.1", "::1"]);

function isAllowedHost(hostHeader: string | null): boolean {
  if (!hostHeader) return false;
  const host = hostHeader.split(":")[0]?.toLowerCase().replace(/^\[|\]$/g, "");
  if (!host) return false;
  return LOCAL_HOST_NAMES.has(host);
}

/**
 * Refuse non-localhost callers in MVP. Viewser is an operator-prototype: no
 * auth, no rate limit, no public deploy. Set VIEWSER_ALLOW_NON_LOCALHOST=true
 * only on a trusted private network (still no auth - use SSH tunnel etc).
 */
export function assertLocalhost(request: Request): NextResponse | null {
  if (process.env.VIEWSER_ALLOW_NON_LOCALHOST === "true") return null;

  const host = request.headers.get("host");
  if (isAllowedHost(host)) return null;

  return NextResponse.json(
    {
      error:
        "Viewser är localhost-only. Sätt VIEWSER_ALLOW_NON_LOCALHOST=true endast om du vet vad du gör.",
    },
    { status: 403 },
  );
}
