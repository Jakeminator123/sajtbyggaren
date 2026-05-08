"use client";

import Script from "next/script";

const DEFAULT_API_HOST = "https://plausible.io";

/**
 * Plausible Analytics tracking script.
 *
 * Renders a single deferred <script> when NEXT_PUBLIC_PLAUSIBLE_DOMAIN is
 * configured, otherwise renders null so missing config never breaks the
 * build. Mount once in the root layout — Plausible auto-tracks SPA-style
 * navigation when present at the root.
 */
export function PlausibleAnalytics() {
  const domain = (process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN ?? "").trim();
  if (!domain) return null;

  const apiHost = (process.env.NEXT_PUBLIC_PLAUSIBLE_API_HOST ?? DEFAULT_API_HOST).trim() || DEFAULT_API_HOST;
  const scriptSrc = `${apiHost.replace(/\/$/, "")}/js/script.js`;

  return (
    <Script
      id="plausible-analytics"
      src={scriptSrc}
      data-domain={domain}
      strategy="afterInteractive"
      defer
    />
  );
}
