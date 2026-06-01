import { NextResponse } from "next/server";

const LOCAL_HOST_NAMES = new Set(["localhost", "127.0.0.1", "::1"]);

function allowedHostsFromEnv(): Set<string> {
  return new Set(
    (process.env.VIEWSER_ALLOWED_HOSTS ?? "")
      .split(",")
      .map((host) => host.trim().toLowerCase())
      .filter(Boolean),
  );
}

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
  if (LOCAL_HOST_NAMES.has(host)) return true;
  return allowedHostsFromEnv().has(host);
}

/**
 * Refuse non-localhost callers in MVP. Viewser is an operator-prototype: no
 * auth and no rate limit. Use VIEWSER_ALLOWED_HOSTS for specific public hosts
 * such as Vercel preview/production domains. Set
 * VIEWSER_ALLOW_NON_LOCALHOST=true only as a full bypass on a trusted private
 * network (still no auth - use SSH tunnel etc).
 */
export function assertLocalhost(request: Request): NextResponse | null {
  if (process.env.VIEWSER_ALLOW_NON_LOCALHOST === "true") return null;

  const host = request.headers.get("host");
  if (isAllowedHost(host)) return null;

  return NextResponse.json(
    {
      error:
        "Viewser är localhost-only. Sätt VIEWSER_ALLOWED_HOSTS=<host> för specifika domäner eller VIEWSER_ALLOW_NON_LOCALHOST=true för full bypass.",
    },
    { status: 403 },
  );
}
