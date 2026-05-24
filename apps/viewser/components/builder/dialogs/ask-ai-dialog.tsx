"use client";

import { Loader2, Send } from "lucide-react";
import {
  KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/**
 * "Fråga utan att bygga" — kort multi-turn chat mot `/api/chat`.
 * Inga sajt-ändringar, inga builds, ingen Project Input touch.
 * Användbart när operatören vill bolla idéer ("vilka sidor borde
 * en restaurangsajt ha?") innan hen formulerar en följdprompt
 * till FloatingChat.
 *
 * UX: konversationen lever bara i dialogens livstid — ny session
 * varje gång dialogen öppnas. Vi ger en system-prompt med kort
 * sajt-context (siteId) så assistenten vet vilken sajt vi pratar
 * om, men vi skickar inte hela Project Input för att hålla token-
 * kostnaden låg.
 */

type ChatRole = "system" | "user" | "assistant";

type ChatTurn = {
  id: string;
  role: ChatRole;
  content: string;
};

type ChatApiResponse = {
  message?: { role: ChatRole; content: string };
  error?: string;
};

type AskAiDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
};

const systemPrompt = (siteId: string) =>
  `Du är en hjälpsam UI/UX-rådgivare för en operatör som bygger en webbsida (siteId: ${siteId}) via Sajtbyggaren. Svara kort, konkret och på svenska. Föreslå gärna konkreta följdprompts som operatören kan klistra in i builderns chat-ruta för att faktiskt ändra sajten.`;

export function AskAiDialog({ open, onOpenChange, siteId }: AskAiDialogProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  // Nollställ konversationen när dialogen stängs så nästa öppning
  // börjar med ett tomt blad.
  const handleClose = useCallback(
    (next: boolean) => {
      if (!next) {
        setTurns([]);
        setInput("");
        setError(null);
      }
      onOpenChange(next);
    },
    [onOpenChange],
  );

  // Auto-scrolla transcriptet när nya turer kommer.
  useEffect(() => {
    const node = transcriptRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [turns]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    const nextUserTurn: ChatTurn = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const nextTurns = [...turns, nextUserTurn];
    setTurns(nextTurns);
    setInput("");
    setIsSending(true);
    setError(null);

    try {
      // Bygg payload: system + alla turer från dialogen.
      const payload = {
        messages: [
          { role: "system" as ChatRole, content: systemPrompt(siteId) },
          ...nextTurns.map((turn) => ({
            role: turn.role,
            content: turn.content,
          })),
        ],
      };
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await response.json()) as ChatApiResponse;
      if (!response.ok || !data.message) {
        throw new Error(
          data.error ?? `Chat-anropet misslyckades (HTTP ${response.status})`,
        );
      }
      setTurns((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.message?.content ?? "",
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt fel.");
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, turns, siteId]);

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        void handleSend();
      }
    },
    [handleSend],
  );

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="flex h-[min(80dvh,640px)] flex-col sm:max-w-[560px]">
        <DialogHeader className="shrink-0">
          <DialogTitle>Fråga utan att bygga</DialogTitle>
          <DialogDescription>
            Bolla idéer med assistenten utan att triggers ett bygge. Bra för att
            hitta nästa följdprompt.
          </DialogDescription>
        </DialogHeader>

        <div
          ref={transcriptRef}
          className="border-border/60 bg-muted/20 flex-1 overflow-y-auto rounded-md border p-3"
          role="log"
          aria-live="polite"
        >
          {turns.length === 0 ? (
            <div className="text-muted-foreground flex h-full items-center justify-center text-center text-[12px]">
              <span>
                Skriv en fråga — t.ex. <em>&quot;vilka sidor saknas?&quot;</em>{" "}
                eller{" "}
                <em>&quot;hur kan jag göra hero-bilden mer levande?&quot;</em>
              </span>
            </div>
          ) : (
            <ol className="flex flex-col gap-2.5">
              {turns.map((turn) => {
                const isUser = turn.role === "user";
                return (
                  <li
                    key={turn.id}
                    className={cn(
                      "flex max-w-full",
                      isUser ? "justify-end" : "justify-start",
                    )}
                  >
                    <span
                      className={cn(
                        "max-w-[85%] rounded-xl border px-3 py-2 text-[12.5px] leading-relaxed whitespace-pre-wrap",
                        isUser
                          ? "bg-foreground text-background border-transparent"
                          : "bg-card border-border/60 text-foreground",
                      )}
                    >
                      {turn.content}
                    </span>
                  </li>
                );
              })}
              {isSending ? (
                <li className="flex justify-start">
                  <span className="bg-card border-border/60 text-muted-foreground inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[12.5px] italic">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Tänker…
                  </span>
                </li>
              ) : null}
            </ol>
          )}
        </div>

        {error ? (
          <p
            role="alert"
            className="text-destructive bg-destructive/10 border-destructive/40 shrink-0 rounded-md border px-3 py-2 text-[12px]"
          >
            {error}
          </p>
        ) : null}

        <div className="border-border/60 bg-background focus-within:border-ring/50 focus-within:ring-ring/30 shrink-0 overflow-hidden rounded-xl border focus-within:ring-2">
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Skriv en fråga…"
            rows={2}
            maxLength={4000}
            disabled={isSending}
            className="min-h-[60px] resize-none border-0 bg-transparent px-3 py-2 text-[13px] shadow-none focus-visible:ring-0"
          />
          <div className="border-border/60 flex items-center justify-between gap-2 border-t px-2 py-1.5">
            <span className="text-muted-foreground text-[10px]">
              ⌘/Ctrl + Enter
            </span>
            <Button
              type="button"
              size="sm"
              onClick={() => void handleSend()}
              disabled={isSending || input.trim().length === 0}
            >
              {isSending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" />
              )}
              {isSending ? "Skickar" : "Skicka"}
            </Button>
          </div>
        </div>

        <DialogFooter className="shrink-0">
          <Button
            type="button"
            variant="ghost"
            onClick={() => handleClose(false)}
          >
            Stäng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
