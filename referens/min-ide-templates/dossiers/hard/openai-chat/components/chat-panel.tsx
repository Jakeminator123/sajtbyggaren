"use client";

import { useChat } from "@ai-sdk/react";

interface ChatPanelProps {
  title?: string;
  placeholder?: string;
  starterPrompts?: string[];
  className?: string;
}

export function ChatPanel({
  title = "Ask the assistant",
  placeholder = "Type a message…",
  starterPrompts = ["What can you help me with?"],
  className,
}: ChatPanelProps) {
  const { messages, input, handleInputChange, handleSubmit, status, stop, append } = useChat({
    api: "/api/chat",
  });
  const isStreaming = status === "streaming" || status === "submitted";

  return (
    <div className={className ?? "flex h-[600px] flex-col rounded-lg border bg-background"}>
      <header className="border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Try:</p>
            <ul className="space-y-1">
              {starterPrompts.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => append({ role: "user", content: p })}
                    className="text-left text-sm text-primary underline-offset-4 hover:underline"
                  >
                    {p}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === "user"
                ? "ml-8 rounded-md bg-primary/10 px-3 py-2 text-sm"
                : "mr-8 rounded-md bg-muted px-3 py-2 text-sm"
            }
          >
            <span className="block text-xs font-medium opacity-60">
              {m.role === "user" ? "You" : "Assistant"}
            </span>
            <p className="whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t p-3">
        <input
          value={input}
          onChange={handleInputChange}
          placeholder={placeholder}
          className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={() => stop()}
            className="rounded-md border px-3 py-2 text-sm"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            Send
          </button>
        )}
      </form>
    </div>
  );
}
