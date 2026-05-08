"use client";

import { ClerkProvider } from "@clerk/nextjs";
import type { ComponentProps, ReactNode } from "react";

type ClerkProviderProps = ComponentProps<typeof ClerkProvider>;

export interface ClerkProviderShellProps {
  children: ReactNode;
  localization?: ClerkProviderProps["localization"];
  appearance?: ClerkProviderProps["appearance"];
}

/**
 * Wrapper around Clerk's provider that degrades gracefully when keys are
 * missing. When NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is unset, we render the
 * children without the provider plus a small banner — this prevents
 * `<ClerkProvider>` from throwing synchronously on mount, which would
 * black-screen the entire app in dev/preview environments where the
 * operator hasn't pasted the keys yet.
 */
export function ClerkProviderShell({
  children,
  localization,
  appearance,
}: ClerkProviderShellProps) {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (!publishableKey) {
    return (
      <>
        <div
          role="status"
          className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900"
        >
          Auth not configured: set <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and{" "}
          <code>CLERK_SECRET_KEY</code> in <code>.env.local</code> to enable login.
        </div>
        {children}
      </>
    );
  }

  return (
    <ClerkProvider
      publishableKey={publishableKey}
      localization={localization}
      appearance={appearance}
    >
      {children}
    </ClerkProvider>
  );
}
