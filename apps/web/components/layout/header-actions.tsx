"use client";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-store";
import { LogIn, User, LogOut, FolderOpen, Coins } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { SiteNavMenu } from "./site-nav-menu";

interface HeaderActionsProps {
  onLoginClick?: () => void;
  onRegisterClick?: () => void;
}

export function HeaderActions({ onLoginClick, onRegisterClick }: HeaderActionsProps) {
  const { user, isAuthenticated, isInitialized, diamonds, logout } = useAuth();
  const router = useRouter();
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-user-menu]")) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const handlePrimaryClick = () => {
    if (isInitialized && isAuthenticated) {
      router.push("/builder");
      return;
    }
    onRegisterClick?.();
  };

  const handleLoginClick = () => {
    if (isInitialized && isAuthenticated) {
      router.push("/projects");
      return;
    }
    onLoginClick?.();
  };

  return (
    <div className="flex items-center gap-2">
      {!isInitialized ? (
        <div className="h-8 w-8 animate-pulse rounded-md bg-muted" />
      ) : isAuthenticated ? (
        <>
          {diamonds !== null && (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-brand-amber"
              onClick={() => router.push("/buy-credits")}
            >
              <Coins className="h-3.5 w-3.5" />
              <span className="text-xs font-semibold">{diamonds}</span>
            </Button>
          )}
          <div className="relative" data-user-menu>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowUserMenu(!showUserMenu)}
              aria-label="Konto"
              className="text-foreground/70 hover:text-foreground"
            >
              <User className="h-5 w-5" />
            </Button>
            {showUserMenu && (
              <div className="animate-in fade-in slide-in-from-top-2 absolute right-0 mt-2 w-48 rounded-md border border-border bg-card py-1 shadow-xl duration-150">
                <div className="border-b border-border px-3 py-2">
                  <p className="truncate text-sm font-medium text-foreground">
                    {user?.name || user?.email?.split("@")[0] || "Konto"}
                  </p>
                </div>
                <button
                  onClick={() => { router.push("/projects"); setShowUserMenu(false); }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                >
                  <FolderOpen className="h-4 w-4" />
                  Projekt
                </button>
                <button
                  onClick={() => { logout(); setShowUserMenu(false); }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                >
                  <LogOut className="h-4 w-4" />
                  Logga ut
                </button>
              </div>
            )}
          </div>
        </>
      ) : (
        <>
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrimaryClick}
            className="border-primary/30 text-primary hover:bg-primary/10 hover:text-primary"
          >
            Kom igång gratis
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLoginClick}
            aria-label="Logga in"
            className="text-foreground/70 hover:text-foreground"
          >
            <LogIn className="h-5 w-5" />
          </Button>
        </>
      )}
      <SiteNavMenu />
    </div>
  );
}
