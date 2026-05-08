"use client";

import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";

export interface AuthButtonsProps {
  signInLabel?: string;
  signUpLabel?: string;
  afterSignOutUrl?: string;
  className?: string;
}

/**
 * Header auth controls. Shows sign-in / sign-up CTAs when signed out and a
 * user avatar dropdown when signed in. Restyle freely — only the
 * <SignedIn> / <SignedOut> boundaries and the modal `mode="modal"` props
 * are load-bearing.
 */
export function AuthButtons({
  signInLabel = "Logga in",
  signUpLabel = "Skapa konto",
  afterSignOutUrl = "/",
  className,
}: AuthButtonsProps) {
  return (
    <div className={className ?? "flex items-center gap-2"}>
      <SignedOut>
        <SignInButton mode="modal">
          <button
            type="button"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-foreground hover:bg-accent"
          >
            {signInLabel}
          </button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            {signUpLabel}
          </button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <UserButton
          afterSignOutUrl={afterSignOutUrl}
          appearance={{ elements: { avatarBox: "h-8 w-8" } }}
        />
      </SignedIn>
    </div>
  );
}
