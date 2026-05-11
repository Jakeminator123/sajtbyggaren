"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Search, Coins, Loader2, AlertCircle, BarChart2, Lock, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth/auth-store";
import { AUDIT_COSTS } from "@/lib/credits/pricing";
import type { AuditMode, AuditResult } from "@/types/audit";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface SiteAuditSectionProps {
  onAuditComplete: (result: AuditResult, auditedUrl: string) => void;
  onRequireAuth: () => void;
  url?: string;
  onUrlChange?: (url: string) => void;
  hideUrlInput?: boolean;
  externalSubmitSignal?: number;
}

export function SiteAuditSection({
  onAuditComplete,
  onRequireAuth,
  url,
  onUrlChange,
  hideUrlInput = false,
  externalSubmitSignal,
}: SiteAuditSectionProps) {
  const { user, isAuthenticated, updateDiamonds } = useAuth();
  const [internalUrl, setInternalUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [showModeDialog, setShowModeDialog] = useState(false);
  // Initialize with current signal so mount does not auto-submit.
  const lastHandledSubmitSignalRef = useRef<number | undefined>(externalSubmitSignal);

  const isUrlControlled = typeof url === "string";
  const currentUrl = isUrlControlled ? url : internalUrl;

  const setUrlValue = useCallback(
    (value: string) => {
      if (isUrlControlled) {
        onUrlChange?.(value);
        return;
      }
      setInternalUrl(value);
    },
    [isUrlControlled, onUrlChange],
  );

  const canAffordBasic = user && user.diamonds >= AUDIT_COSTS.basic;
  const canAffordAdvanced = user && user.diamonds >= AUDIT_COSTS.advanced;

  const requestModeSelection = useCallback(() => {
    if (isLoading) return;
    setError(null);
    if (!currentUrl.trim()) {
      setError("Ange en URL för att analysera.");
      return;
    }
    setShowModeDialog(true);
  }, [currentUrl, isLoading]);

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      requestModeSelection();
    },
    [requestModeSelection],
  );

  useEffect(() => {
    if (externalSubmitSignal === undefined) return;
    if (lastHandledSubmitSignalRef.current === externalSubmitSignal) return;
    lastHandledSubmitSignalRef.current = externalSubmitSignal;
    requestModeSelection();
  }, [externalSubmitSignal, requestModeSelection]);

  const startAudit = useCallback(async (mode: AuditMode) => {
    setShowModeDialog(false);
    setError(null);

    // Check authentication
    if (!isAuthenticated || !user) {
      onRequireAuth();
      return;
    }

    const auditCost = AUDIT_COSTS[mode];
    if (user.diamonds < auditCost) {
      setError(`Du behöver minst ${auditCost} credits. Du har ${user.diamonds}.`);
      return;
    }

    // Validate URL
    let normalizedUrl = currentUrl.trim();
    if (!normalizedUrl) {
      setError("Ange en URL för att analysera.");
      return;
    }

    // Auto-add https if missing
    if (!normalizedUrl.match(/^https?:\/\//i)) {
      normalizedUrl = `https://${normalizedUrl}`;
    }

    setIsLoading(true);
    setProgress(10);

    // Progress simulation
    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 5, 90));
    }, 1000);

    try {
      setProgress(20);

      const response = await fetch("/api/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: normalizedUrl, auditMode: mode }),
      });

      setProgress(80);

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 401) {
          onRequireAuth();
          clearInterval(progressInterval);
          setIsLoading(false);
          setProgress(0);
          return;
        }
        if (response.status === 402) {
          setError(data.error || `Du behöver minst ${auditCost} credits.`);
          clearInterval(progressInterval);
          setIsLoading(false);
          setProgress(0);
          return;
        }
        throw new Error(data.error || "Något gick fel vid analysen.");
      }

      if (!data.success || !data.result) {
        throw new Error(data.error || "Kunde inte få resultat från analysen.");
      }

      setProgress(100);

      // Update local diamonds (server already deducted)
      if (user) {
        updateDiamonds(user.diamonds - auditCost);
      }

      // Pass result and URL to parent
      onAuditComplete(data.result, normalizedUrl);
      setUrlValue("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ett oväntat fel uppstod.");
    } finally {
      clearInterval(progressInterval);
      setIsLoading(false);
      setProgress(0);
    }
  }, [currentUrl, isAuthenticated, onAuditComplete, onRequireAuth, setUrlValue, updateDiamonds, user]);

  return (
    <div className="w-full max-w-2xl">
      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {!hideUrlInput && (
          <div className="input-3d rounded-2xl border border-border/30 bg-secondary/50 backdrop-blur-xl shadow-2xl overflow-hidden">
            <label htmlFor="audit-url" className="sr-only">
              URL att analysera
            </label>
            <div className="relative flex items-center">
              <Search className="absolute left-4 h-5 w-5 text-muted-foreground pointer-events-none" />
              <input
                id="audit-url"
                name="auditUrl"
                type="text"
                value={currentUrl}
                onChange={(e) => setUrlValue(e.target.value)}
                placeholder="exempel.se eller https://exempel.se"
                autoComplete="url"
                disabled={isLoading}
                className="w-full bg-transparent border-none py-4 pl-12 pr-4 text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors disabled:opacity-50"
              />
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {isLoading && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        <Button
          type="submit"
          disabled={isLoading || !currentUrl.trim()}
          className="btn-3d btn-glow w-full gap-3 rounded-xl bg-primary px-6 py-4 font-medium text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Analyserar...</span>
            </>
          ) : (
            <>
              <Search className="h-5 w-5 transition-transform group-hover:scale-110" />
              <span>Välj analysnivå</span>
              <span className="flex items-center gap-1 rounded-md bg-primary-foreground/20 px-2 py-0.5 text-sm">
                <Coins className="h-3.5 w-3.5" />
                <span>
                  {AUDIT_COSTS.basic}/{AUDIT_COSTS.advanced}
                </span>
              </span>
            </>
          )}
        </Button>

        {isAuthenticated && user && (
          <div className="space-y-1 text-center text-xs text-muted-foreground">
            <p>
              Du har{" "}
              <span
                className={user.diamonds >= AUDIT_COSTS.basic ? "text-primary font-medium" : "text-destructive"}
              >
                {user.diamonds} credits
              </span>
            </p>
            <p>
              Vanlig:{" "}
              <span className={canAffordBasic ? "text-primary" : "text-destructive"}>
                {AUDIT_COSTS.basic}
              </span>{" "}
              | Avancerad:{" "}
              <span className={canAffordAdvanced ? "text-primary" : "text-destructive"}>
                {AUDIT_COSTS.advanced}
              </span>
            </p>
          </div>
        )}

        {!isAuthenticated && (
          <p className="text-center text-xs text-muted-foreground">
            <button
              type="button"
              onClick={onRequireAuth}
              className="text-primary hover:text-primary/80 underline font-medium"
            >
              Logga in
            </button>{" "}
            för att använda audit-funktionen.
          </p>
        )}
      </form>

      {/* Feature cards - same style as landing */}
      <div className="mt-8 grid grid-cols-2 gap-3">
        {[
          { icon: BarChart2, text: "SEO & Prestanda" },
          { icon: Coins, text: "Budgetuppskattning" },
          { icon: Lock, text: "Säkerhetsanalys" },
          { icon: Sparkles, text: "Affärs- & marknadsinsikter" },
        ].map(({ icon: Icon, text }) => (
          <div
            key={text}
            className="flex items-center gap-2.5 rounded-xl border border-border/20 bg-card/50 px-3 py-2.5 text-muted-foreground transition-colors hover:border-primary/20 hover:bg-card/80"
          >
            <Icon className="h-4 w-4 shrink-0 text-primary/80" />
            <span className="text-xs font-medium text-foreground">{text}</span>
          </div>
        ))}
      </div>

      <Dialog open={showModeDialog} onOpenChange={setShowModeDialog}>
        <DialogContent
          className="max-w-2xl border-border/40 bg-background/95 backdrop-blur-xl rounded-2xl shadow-2xl"
        >
          <DialogHeader>
            <DialogTitle className="text-foreground font-(--font-heading)">Välj analysnivå</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Vanlig ger en snabb kvalitetskontroll. Avancerad gör djupare marknads- och
              affärsanalys med fler dimensioner.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 px-6 pb-6 md:grid-cols-2">
            <button
              type="button"
              onClick={() => startAudit("basic")}
              className="rounded-xl border border-border/30 bg-card/50 p-4 text-left transition-all hover:border-primary/30 hover:bg-card/80 hover:shadow-lg"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">Vanlig analys</span>
                <span className="flex items-center gap-1 text-xs text-primary">
                  <Coins className="h-3.5 w-3.5" />
                  {AUDIT_COSTS.basic}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Fokuserar på SEO, UX, prestanda och tydliga förbättringsförslag.
              </p>
            </button>
            <button
              type="button"
              onClick={() => startAudit("advanced")}
              className="rounded-xl border border-border/30 bg-card/50 p-4 text-left transition-all hover:border-primary/30 hover:bg-card/80 hover:shadow-lg"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">Avancerad analys</span>
                <span className="flex items-center gap-1 text-xs text-primary">
                  <Coins className="h-3.5 w-3.5" />
                  {AUDIT_COSTS.advanced}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Inkluderar bransch, företagsstorlek, kundsegment, geo, konkurrens och affärslogik.
              </p>
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
