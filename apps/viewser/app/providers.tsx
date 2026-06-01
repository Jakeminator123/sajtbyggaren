"use client";

import { TokenMeterProvider } from "@/components/token-meter";
import { ToastProvider } from "@/components/ui/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <TokenMeterProvider>{children}</TokenMeterProvider>
    </ToastProvider>
  );
}
