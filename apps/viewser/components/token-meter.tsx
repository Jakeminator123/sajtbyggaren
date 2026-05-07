"use client";

import { createContext, useContext, useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type UsageDelta = {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  estimatedCostUsd: number;
};

type TokenMeterState = UsageDelta & {
  chatCalls: number;
  builds: number;
};

type TokenMeterContextValue = {
  totals: TokenMeterState;
  recordChatUsage: (usage: UsageDelta) => void;
  recordBuildUsage: (usage?: Partial<UsageDelta>) => void;
};

const TokenMeterContext = createContext<TokenMeterContextValue | null>(null);

const ZERO_STATE: TokenMeterState = {
  inputTokens: 0,
  outputTokens: 0,
  totalTokens: 0,
  estimatedCostUsd: 0,
  chatCalls: 0,
  builds: 0,
};

export function TokenMeterProvider({ children }: { children: React.ReactNode }) {
  const [totals, setTotals] = useState<TokenMeterState>(ZERO_STATE);

  const value = useMemo<TokenMeterContextValue>(
    () => ({
      totals,
      recordChatUsage: (usage) => {
        setTotals((prev) => ({
          inputTokens: prev.inputTokens + usage.inputTokens,
          outputTokens: prev.outputTokens + usage.outputTokens,
          totalTokens: prev.totalTokens + usage.totalTokens,
          estimatedCostUsd: prev.estimatedCostUsd + usage.estimatedCostUsd,
          chatCalls: prev.chatCalls + 1,
          builds: prev.builds,
        }));
      },
      recordBuildUsage: (usage) => {
        setTotals((prev) => ({
          inputTokens: prev.inputTokens + (usage?.inputTokens ?? 0),
          outputTokens: prev.outputTokens + (usage?.outputTokens ?? 0),
          totalTokens: prev.totalTokens + (usage?.totalTokens ?? 0),
          estimatedCostUsd: prev.estimatedCostUsd + (usage?.estimatedCostUsd ?? 0),
          chatCalls: prev.chatCalls,
          builds: prev.builds + 1,
        }));
      },
    }),
    [totals],
  );

  return <TokenMeterContext.Provider value={value}>{children}</TokenMeterContext.Provider>;
}

export function useTokenMeter() {
  const context = useContext(TokenMeterContext);
  if (!context) {
    throw new Error("useTokenMeter måste användas inuti TokenMeterProvider.");
  }
  return context;
}

function formatTokens(value: number): string {
  if (value < 1_000) return `${value}`;
  return `${(value / 1_000).toFixed(1)}k`;
}

export function TokenMeter() {
  const { totals } = useTokenMeter();
  const warning = totals.estimatedCostUsd >= 1;

  return (
    <Card className={warning ? "border-red-500/50" : ""}>
      <CardHeader className="py-3">
        <CardTitle className="text-sm font-medium">Token Meter</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 pb-3 text-xs text-muted-foreground">
        <p className={warning ? "text-red-600 dark:text-red-400" : ""}>
          Sökt: {formatTokens(totals.totalTokens)} tokens / ${totals.estimatedCostUsd.toFixed(4)}
        </p>
        <p>
          Chat calls: {totals.chatCalls} | Builds: {totals.builds}
        </p>
      </CardContent>
    </Card>
  );
}
