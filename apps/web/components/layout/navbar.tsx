"use client";

import { useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth/auth-store";
import { HeaderActions } from "./header-actions";

interface NavbarProps {
  onLoginClick?: () => void;
  onRegisterClick?: () => void;
}

export function Navbar({ onLoginClick, onRegisterClick }: NavbarProps) {
  const { fetchUser } = useAuth();

  useEffect(() => {
    fetchUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <nav className="fixed top-0 right-0 left-0 z-50 h-14 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-4">
        <Link href="/" className="flex items-center">
          <Image
            src="/LOGO_SM2.0.png"
            alt="Sajtmaskin"
            width={843}
            height={168}
            className="h-6 w-auto object-contain transition-opacity hover:opacity-80 md:h-7"
            priority
          />
        </Link>

        <HeaderActions onLoginClick={onLoginClick} onRegisterClick={onRegisterClick} />
      </div>
    </nav>
  );
}
