"use client";

import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";

export function AnalyticsProviders() {
  return (
    <>
      <Analytics />
      <SpeedInsights />
    </>
  );
}
