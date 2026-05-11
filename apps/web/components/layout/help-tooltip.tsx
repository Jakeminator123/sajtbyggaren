"use client";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { HelpCircle } from "lucide-react";

interface HelpTooltipProps {
  text: string;
  value?: number; // Rating 1-10
  tips?: string;
  className?: string;
}

export function HelpTooltip({ text, value, tips, className }: HelpTooltipProps) {
  // Generate stars based on value (1-10 becomes 1-5 stars)
  const renderStars = (rating: number) => {
    const starCount = Math.ceil(rating / 2);
    return "⭐".repeat(starCount);
  };

  return (
    <TooltipProvider>
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>
          <HelpCircle
            className={`text-muted-foreground hover:text-foreground ml-1 inline-block h-4 w-4 cursor-help transition-colors ${
              className || ""
            }`}
          />
        </TooltipTrigger>
        <TooltipContent className="max-w-xs border-border bg-card p-3" sideOffset={5}>
          <p className="text-sm text-foreground">{text}</p>
          {value && (
            <p className="mt-2 text-xs text-muted-foreground">
              Värde: {value}/10 {renderStars(value)}
            </p>
          )}
          {tips && <p className="text-primary mt-1 text-xs italic">{tips}</p>}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
