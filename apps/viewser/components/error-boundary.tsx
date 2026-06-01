"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// React 19 har fortfarande inget hook-baserat ErrorBoundary-API. Klass-
// komponent är därför enda vägen att fånga rendering-fel som annars skulle
// ge tom skärm. Boundary placeras runt `BuilderShell`, `DiscoveryWizard`,
// `ViewerPanel` och `PromptBuilder` i `app/page.tsx` så ett crash i någon
// av dessa subtrees avgränsas och resten av appen (header + ConsoleDrawer)
// fortsätter fungera.
//
// Beteendet är medvetet defensivt:
// - Vi loggar inte automatiskt till någon extern tjänst — `console.error`
//   räcker tills vi har en observability-strategi.
// - Reset-knappen ökar `resetKey` så barn-trädet remountas efter klick.
// - `fallback` är optional för callsites som vill rendera egen rad.

type ErrorBoundaryProps = {
  children: ReactNode;
  // Operatör-läsbart label för fallback-cardet (t.ex. "Builder", "Wizard").
  // Används i headlinen men inte i logged event så det är säkert att
  // skriva svenska, känsliga texter får inte hamna här.
  area: string;
  // Optional anpassad fallback. Får (error, reset) och tar då över hela
  // ytan. Default-fallback räcker i 99% av fallen.
  fallback?: (error: Error, reset: () => void) => ReactNode;
  className?: string;
};

type ErrorBoundaryState = {
  error: Error | null;
  // Bumpas varje reset så React tvingar remount av barn-trädet. Utan
  // detta fortsätter samma error-cascade i barnen om de hade en
  // permanent state-bug.
  resetKey: number;
};

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Localhost-konsol — `console.error` läses av operatören i devtools
    // och syns även i ConsoleDrawer om vi senare hookar dit. Vi loggar
    // bara error-meddelandet + componentStack-namn (inte hela stacken)
    // för att hålla payloaden mindre.
    console.error(`[ErrorBoundary:${this.props.area}]`, error, info);
  }

  reset = (): void => {
    this.setState((prev) => ({ error: null, resetKey: prev.resetKey + 1 }));
  };

  render(): ReactNode {
    const { error, resetKey } = this.state;
    const { children, fallback, area, className } = this.props;

    if (error) {
      if (fallback) return fallback(error, this.reset);
      return (
        <DefaultFallback
          area={area}
          message={error.message || "Ett oväntat fel inträffade."}
          onReset={this.reset}
          className={className}
        />
      );
    }

    // resetKey som key tvingar React att skapa ett nytt subtree efter
    // reset — viktigt eftersom samma element-stuktur annars återanvänder
    // den korrupta state:n som kraschade.
    return <div key={resetKey}>{children}</div>;
  }
}

function DefaultFallback({
  area,
  message,
  onReset,
  className,
}: {
  area: string;
  message: string;
  onReset: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "border-destructive/40 bg-destructive/5 mx-auto my-6 flex max-w-xl flex-col gap-3 rounded-2xl border p-5 shadow-sm",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <AlertTriangle
          className="text-destructive h-5 w-5 shrink-0"
          aria-hidden
        />
        <h2 className="text-foreground text-sm font-semibold">
          {area} kunde inte ritas
        </h2>
      </div>
      <p className="text-muted-foreground text-[13px] leading-relaxed">
        Något gick fel när vi renderade {area.toLowerCase()}. Övriga delar
        av Sajtbyggaren fungerar fortfarande. Försök igen — om felet kommer
        tillbaka, ladda om sidan.
      </p>
      <pre className="bg-muted/60 text-muted-foreground max-h-32 overflow-auto rounded-md p-2 font-mono text-[11px] leading-snug">
        {message}
      </pre>
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={onReset}>
          <RefreshCw aria-hidden />
          Försök igen
        </Button>
      </div>
    </div>
  );
}
