"use client";

import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Liten "snabbprompt"-knapp som inspector-tabbarna använder för att
 * skicka strukturerade follow-up-prompts. Den är medvetet liten
 * (h-7, text-[11.5px]) så raderna i tabbarna inte tar för mycket
 * vertikalt utrymme. Disablar sig själv när ett bygge pågår och
 * visar spinner när en prompt skickas.
 *
 * Den triggerar inte själv build-pipeline:n — den anropar bara
 * `onSelect` med den färdig-formaterade prompten. Logiken lever
 * uppe i `SiteInspectorSheet` som äger `useFollowupBuild`-instansen.
 */

type QuickPromptButtonProps = {
  label: string;
  prompt: string;
  isBuilding: boolean;
  isPending: boolean;
  onSelect: (prompt: string) => void;
  variant?: "default" | "ghost";
  className?: string;
};

export function QuickPromptButton({
  label,
  prompt,
  isBuilding,
  isPending,
  onSelect,
  variant = "ghost",
  className,
}: QuickPromptButtonProps) {
  return (
    <Button
      type="button"
      size="sm"
      variant={variant}
      disabled={isBuilding}
      onClick={() => onSelect(prompt)}
      className={cn(
        "min-tap sm:min-tap-0 gap-1 px-3 text-[12px] font-medium tracking-tight active:scale-95 sm:h-7 sm:px-2 sm:text-[11.5px]",
        className,
      )}
    >
      {isPending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <Sparkles className="h-3 w-3" />
      )}
      {label}
    </Button>
  );
}
