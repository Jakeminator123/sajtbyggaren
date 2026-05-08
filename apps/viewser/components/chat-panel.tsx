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

type ChatPanelProps = {
  siteId: string;
  onBuildDone: (runId: string) => void;
};

export function ChatPanel({ siteId, onBuildDone }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hej! Detta är Viewser-chatten (backed by briefModel). Jag kan diskutera valt Project Input men ändrar inte data i denna runda. Klicka 'Build' när du vill köra Builder MVP.",
    },
  ]);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { recordChatUsage, recordBuildUsage } = useTokenMeter();

  async function sendPrompt() {
    const cleaned = prompt.trim();
    if (!cleaned || busy) return;

    const userMessage: Message = { role: "user", content: cleaned };
    const nextMessages = [...messages, userMessage];

    setPrompt("");
    setError(null);
    setMessages(nextMessages);
    setBusy(true);

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
      setBusy(false);
    }
  }

  async function runBuild() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
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
      onBuildDone(payload.runId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt build-fel.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="h-full">
      <CardHeader className="border-b">
        <CardTitle className="text-base">Chat Panel</CardTitle>
      </CardHeader>
      <CardContent className="flex h-[calc(100%-57px)] flex-col gap-4 p-4">
        <ScrollArea className="h-[52vh] rounded-md border p-3">
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

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        <div className="flex gap-2">
          <Input
            placeholder="Skriv ditt meddelande..."
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void sendPrompt();
              }
            }}
          />
          <Button disabled={busy} onClick={() => void sendPrompt()}>
            Skicka
          </Button>
        </div>

        <Button disabled={busy} onClick={() => void runBuild()} variant="secondary">
          Build {siteId}
        </Button>
      </CardContent>
    </Card>
  );
}
