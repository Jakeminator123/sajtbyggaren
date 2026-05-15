import { NextResponse } from "next/server";

const LOCAL_HOST_NAMES = new Set(["localhost", "127.0.0.1", "::1"]);

function hostFromHeader(hostHeader: string | null): string | null {
  if (!hostHeader) return null;

  const bracketedIpv6 = hostHeader.match(/^\[(.+)\](?::\d+)?$/);
  if (bracketedIpv6?.[1]) {
    return bracketedIpv6[1].toLowerCase();
  }

  const hostname = hostHeader.match(/^([^:]+)(?::\d+)?$/);
  if (hostname?.[1]) {
    return hostname[1].toLowerCase();
  }

  return null;
}

function isAllowedHost(hostHeader: string | null): boolean {
  const host = hostFromHeader(hostHeader);
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
