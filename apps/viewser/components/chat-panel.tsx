"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTokenMeter } from "@/components/token-meter";

type Message = {
  role: "system" | "user" | "assistant";
  content: string;
};

type BuildModelUsage = {
  totalInputTokens?: number;
  totalOutputTokens?: number;
  totalCostUsd?: number;
};

type BuildStage = "idle" | "starting" | "running" | "success" | "failed";

type ChatPanelProps = {
  siteId: string;
  onBuildStart?: () => void;
  onBuildDone: (runId: string) => void;
  onBuildEnd?: () => void;
};

export function ChatPanel({
  siteId,
  onBuildStart,
  onBuildDone,
  onBuildEnd,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hej. Detta är operator-prototypens chatfält. Det är experimentellt: meddelanden ändrar inte Project Input eller run-flödet i denna runda. För att skapa en sajt — välj Project Input ovan och klicka Build.",
    },
  ]);
  const [prompt, setPrompt] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [buildStage, setBuildStage] = useState<BuildStage>("idle");
  const [error, setError] = useState<string | null>(null);
  const { recordChatUsage, recordBuildUsage } = useTokenMeter();

  const isBusy = chatBusy || buildStage === "starting" || buildStage === "running";

  async function sendPrompt() {
    const cleaned = prompt.trim();
    if (!cleaned || isBusy) return;

    const userMessage: Message = { role: "user", content: cleaned };
    const nextMessages = [...messages, userMessage];

    setPrompt("");
    setError(null);
    setMessages(nextMessages);
    setChatBusy(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: nextMessages }),
      });
      const payload = (await response.json()) as {
        error?: string;
        message?: Message;
        usage?: {
          inputTokens: number;
          outputTokens: number;
          totalTokens: number;
          estimatedCostUsd: number;
        };
      };
      if (!response.ok || !payload.message) {
        throw new Error(payload.error ?? "Chat-anropet misslyckades.");
      }

      setMessages((prev) => [...prev, payload.message!]);
      if (payload.usage) {
        recordChatUsage(payload.usage);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt fel.");
    } finally {
      setChatBusy(false);
    }
  }

  async function runBuild() {
    if (isBusy) return;
    setBuildStage("starting");
    setError(null);
    onBuildStart?.();
    try {
      setBuildStage("running");
      const response = await fetch("/api/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ siteId }),
      });
      const payload = (await response.json()) as {
        error?: string;
        runId?: string;
        buildResult?: { modelUsage?: BuildModelUsage };
      };
      if (!response.ok || !payload.runId) {
        throw new Error(payload.error ?? "Build misslyckades.");
      }

      const modelUsage = payload.buildResult?.modelUsage;
      recordBuildUsage({
        inputTokens: modelUsage?.totalInputTokens ?? 0,
        outputTokens: modelUsage?.totalOutputTokens ?? 0,
        totalTokens:
          (modelUsage?.totalInputTokens ?? 0) + (modelUsage?.totalOutputTokens ?? 0),
        estimatedCostUsd: modelUsage?.totalCostUsd ?? 0,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Build klar: ${payload.runId}`,
        },
      ]);
      setBuildStage("success");
      onBuildDone(payload.runId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt build-fel.");
      setBuildStage("failed");
    } finally {
      onBuildEnd?.();
    }
  }

  return (
    <Card className="h-full">
      <CardHeader className="border-b">
        <CardTitle className="text-base">Chat & Build</CardTitle>
      </CardHeader>
      <CardContent className="flex h-[calc(100%-57px)] flex-col gap-4 p-4">
        <ScrollArea className="h-[40vh] rounded-md border p-3">
          <div className="space-y-3">
            {messages.map((message, index) => (
              <article
                key={`${message.role}-${index}`}
                className={
                  message.role === "user"
                    ? "ml-6 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
                    : "mr-6 rounded-md bg-muted px-3 py-2 text-sm"
                }
              >
                {message.content}
              </article>
            ))}
          </div>
        </ScrollArea>

        {error ? (
          <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        ) : null}

        <BuildStatusIndicator stage={buildStage} siteId={siteId} />

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Promptfält (experimentellt): chatten kan diskutera valt Project Input
            men ändrar ingenting i denna runda. För att skapa en sajt — använd
            Build-knappen.
          </p>
          <div className="flex gap-2">
            <Input
              placeholder="Skriv ett experimentellt meddelande..."
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void sendPrompt();
                }
              }}
              disabled={isBusy}
            />
            <Button disabled={isBusy} onClick={() => void sendPrompt()} variant="outline">
              Skicka
            </Button>
          </div>
        </div>

        <Button
          disabled={isBusy}
          onClick={() => void runBuild()}
          variant="default"
          size="lg"
        >
          {buildStage === "running" || buildStage === "starting"
            ? `Bygger ${siteId}...`
            : `Build ${siteId}`}
        </Button>
      </CardContent>
    </Card>
  );
}

function BuildStatusIndicator({
  stage,
  siteId,
}: {
  stage: BuildStage;
  siteId: string;
}) {
  if (stage === "idle") return null;
  if (stage === "starting" || stage === "running") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm text-sky-700 dark:text-sky-300">
        <span className="inline-block size-2 animate-pulse rounded-full bg-sky-500" />
        {stage === "starting"
          ? `Startar build för ${siteId}...`
          : `Kör scripts/build_site.py mot ${siteId}. Detta tar ofta 5–60 sek (npm install + npm run build).`}
      </div>
    );
  }
  if (stage === "success") {
    return (
      <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
        Build klar — se Run Details + Preview nedan.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
      Build misslyckades. Se felmeddelandet ovan.
    </div>
  );
}
