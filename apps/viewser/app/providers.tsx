"use client";

import { TokenMeterProvider } from "@/components/token-meter";

export function Providers({ children }: { children: React.ReactNode }) {
  return <TokenMeterProvider>{children}</TokenMeterProvider>;
}
