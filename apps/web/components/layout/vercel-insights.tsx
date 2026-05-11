"use client";

import { useSyncExternalStore } from "react";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";

interface VercelInsightsProps {
  enabled: boolean;
}

function subscribeToNoopStore() {
  return () => {};
}

export function VercelInsights({ enabled }: VercelInsightsProps) {
  const shouldRender = useSyncExternalStore(
    subscribeToNoopStore,
    () => {
      if (!enabled) return false;
      if (typeof window === "undefined") return false;
      const hostname = window.location.hostname;
      return hostname !== "localhost" && hostname !== "127.0.0.1";
    },
    () => false,
  );

  if (!shouldRender) return null;

  return (
    <>
      <Analytics />
      <SpeedInsights />
    </>
  );
}
