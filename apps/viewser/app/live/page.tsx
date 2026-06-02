"use client";

import { ArrowUp, Loader2, RefreshCw, Sparkles, AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * /live — HOSTAD demo-yta för prompt→bygg→preview→följdprompt-loopen.
 *
 * Fristående från operatörskonsolen på ``/`` (som är disk-/Python-bunden och
 * bara kör lokalt). Den här sidan pratar bara med /api/live/* som kör hela
 * pipen i en Vercel Sandbox, så loopen fungerar hostat. Den återskapar v0-/
 * Lovable-känslan: en stor prompt, en byggprogress, och sedan previewen i en
 * iframe med en flytande chatt för att fortsätta prompta fram nya versioner.
 */

type LivePhase =
  | "idle"
  | "pending"
  | "cloning"
  | "installing"
  | "generating"
  | "building"
  | "starting"
  | "ready"
  | "failed"
  | "expired"
  | "unknown";

type StatusResponse = {
  siteId: string;
  phase: LivePhase;
  detail?: string;
  url?: string;
  error?: string;
  log?: string;
};

type ChatMessage = {
  id: number;
  role: "user" | "system";
  text: string;
};

const WORKING_PHASES = new Set<LivePhase>([
  "pending",
  "cloning",
  "installing",
  "generating",
  "building",
  "starting",
]);

const PHASE_LABEL: Record<LivePhase, string> = {
  idle: "Redo",
  pending: "Startar sandbox",
  cloning: "Hämtar byggmotorn",
  installing: "Installerar beroenden",
  generating: "Planerar och skapar sajten",
  building: "Bygger sajten",
  starting: "Startar förhandsvisning",
  ready: "Klar",
  failed: "Något gick fel",
  expired: "Sessionen gick ut",
  unknown: "Arbetar",
};

const BUILD_STEPS: { phases: LivePhase[]; title: string; hint: string }[] = [
  {
    phases: ["pending", "cloning", "installing"],
    title: "Förbereder molnmiljön",
    hint: "Vi startar en säker sandbox och hämtar byggmotorn.",
  },
  {
    phases: ["generating"],
    title: "Planerar sajten",
    hint: "Vi väljer struktur, ton och innehåll för din verksamhet.",
  },
  {
    phases: ["building"],
    title: "Bygger sajten",
    hint: "Vi monterar sidorna. Första bygget tar ett par minuter.",
  },
  {
    phases: ["starting", "ready"],
    title: "Öppnar förhandsvisning",
    hint: "Snart kan du klicka runt på din sajt.",
  },
];

function stepIndexForPhase(phase: LivePhase): number {
  const idx = BUILD_STEPS.findIndex((step) => step.phases.includes(phase));
  return idx === -1 ? 0 : idx;
}

export default function LivePage() {
  const [siteId, setSiteId] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [phase, setPhase] = useState<LivePhase>("idle");
  const [detail, setDetail] = useState("");
  const [logTail, setLogTail] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [everReady, setEverReady] = useState(false);
  const [previewVersion, setPreviewVersion] = useState(0);

  const [prompt, setPrompt] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const pendingReloadRef = useRef(false);
  const messageIdRef = useRef(0);

  const isWorking = siteId !== null && WORKING_PHASES.has(phase);

  const pushMessage = useCallback((role: ChatMessage["role"], text: string) => {
    messageIdRef.current += 1;
    setMessages((prev) => [...prev, { id: messageIdRef.current, role, text }]);
  }, []);

  // Polla status medan ett bygge pågår. Stannar automatiskt när phase
  // lämnar working-mängden (ready/failed/expired) eftersom isWorking då
  // flippar och effektens deps ändras.
  useEffect(() => {
    if (!siteId || !isWorking) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const res = await fetch(
          `/api/live/status?siteId=${encodeURIComponent(siteId)}`,
          { cache: "no-store" },
        );
        const data = (await res.json()) as StatusResponse;
        if (cancelled) return;
        setPhase(data.phase);
        setDetail(data.detail ?? "");
        if (data.log) setLogTail(data.log);

        if (data.phase === "ready") {
          if (data.url) setUrl(data.url);
          setEverReady(true);
          setErrorMsg(null);
          if (pendingReloadRef.current) {
            pendingReloadRef.current = false;
            setPreviewVersion((v) => v + 1);
            pushMessage("system", "Ny version är klar.");
          }
        } else if (data.phase === "failed" || data.phase === "expired") {
          setErrorMsg(data.error ?? data.detail ?? "Något gick fel.");
          pushMessage(
            "system",
            data.error ?? data.detail ?? "Något gick fel under bygget.",
          );
        }
      } catch {
        // tillfälligt nätverksfel — fortsätt polla
      }
    };

    void tick();
    const id = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [siteId, isWorking, pushMessage]);

  const startBuild = useCallback(async () => {
    const text = prompt.trim();
    if (!text || submitting) return;
    setSubmitting(true);
    setErrorMsg(null);
    setEverReady(false);
    setUrl(null);
    setLogTail("");
    setPhase("pending");
    pushMessage("user", text);
    try {
      const res = await fetch("/api/live/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text }),
      });
      const data = (await res.json()) as {
        siteId?: string;
        url?: string;
        error?: string;
      };
      if (!res.ok || !data.siteId) {
        throw new Error(data.error ?? "Kunde inte starta bygget.");
      }
      setSiteId(data.siteId);
      if (data.url) setUrl(data.url);
      pushMessage("system", "Bygget har startat – det tar ett par minuter.");
    } catch (error) {
      setPhase("failed");
      setErrorMsg(error instanceof Error ? error.message : "Okänt fel.");
    } finally {
      setSubmitting(false);
    }
  }, [prompt, submitting, pushMessage]);

  const sendFollowup = useCallback(async () => {
    const text = chatInput.trim();
    if (!text || !siteId || isWorking || submitting) return;
    setSubmitting(true);
    setChatInput("");
    setErrorMsg(null);
    setPhase("generating");
    pushMessage("user", text);
    try {
      const res = await fetch("/api/live/followup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ siteId, prompt: text }),
      });
      const data = (await res.json()) as { error?: string };
      if (!res.ok) {
        throw new Error(data.error ?? "Kunde inte starta följdbygget.");
      }
      pendingReloadRef.current = true;
      pushMessage("system", "Bygger en ny version …");
    } catch (error) {
      setPhase("ready");
      setErrorMsg(error instanceof Error ? error.message : "Okänt fel.");
      pushMessage(
        "system",
        error instanceof Error ? error.message : "Kunde inte uppdatera sajten.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [chatInput, siteId, isWorking, submitting, pushMessage]);

  const iframeSrc =
    url && previewVersion > 0 ? `${url}?v=${previewVersion}` : url;
  const showInitialOverlay = isWorking && !everReady;
  const showPreview = !!url && everReady;
  const showFatalError =
    (phase === "failed" || phase === "expired") && !everReady;

  return (
    <main className="bg-background relative h-[100dvh] w-full overflow-hidden">
      {/* Preview-iframe (full-bleed) när vi har en klar sajt. */}
      {showPreview && iframeSrc ? (
        <iframe
          key={url}
          src={iframeSrc}
          title="Din sajt"
          className="absolute inset-0 z-0 h-full w-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      ) : null}

      {/* Idle-hero: stor prompt-ruta innan första bygget. */}
      {!siteId ? (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center px-5">
          <div className="flex w-full max-w-xl flex-col items-center gap-6">
            <span className="border-border/50 bg-background/70 text-foreground/70 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[10px] tracking-[0.22em] uppercase shadow-sm backdrop-blur">
              <Sparkles className="h-3 w-3" />
              Sajtbyggaren · live
            </span>
            <h1 className="text-foreground text-center text-3xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-4xl">
              Beskriv din sajt{" "}
              <span className="text-foreground/55">så bygger vi den i molnet.</span>
            </h1>
            <p className="text-foreground/70 max-w-md text-center text-[14px] leading-relaxed text-balance">
              Skriv vad företaget gör, så genererar vi en riktig
              företagshemsida och startar en förhandsvisning du kan klicka runt
              i. Sedan kan du fortsätta prompta fram nya versioner.
            </p>
            <div className="border-border/60 bg-card focus-within:border-foreground/30 w-full rounded-2xl border p-3 shadow-lg transition-colors">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    void startBuild();
                  }
                }}
                rows={4}
                placeholder="T.ex. En sajt åt Bryggans Bageri i Lund – surdegsbröd, fikabröd, beställning av tårtor och öppettider."
                className="text-foreground placeholder:text-muted-foreground/60 max-h-60 min-h-24 w-full resize-none bg-transparent px-2 py-1.5 text-[15px] leading-relaxed outline-none"
              />
              <div className="flex items-center justify-between gap-3 px-1 pt-1">
                <span className="text-muted-foreground/70 text-[11px]">
                  Tips: ⌘/Ctrl + Enter för att bygga
                </span>
                <Button
                  onClick={() => void startBuild()}
                  disabled={!prompt.trim() || submitting}
                  className="gap-1.5"
                >
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowUp className="h-4 w-4" />
                  )}
                  Bygg min sajt
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Initial byggprogress (innan första previewen finns). */}
      {showInitialOverlay && !showFatalError ? (
        <div className="bg-background/90 absolute inset-0 z-20 flex items-center justify-center px-6 backdrop-blur-sm">
          <BuildProgress phase={phase} detail={detail} logTail={logTail} />
        </div>
      ) : null}

      {/* Fatalt fel innan någon preview hunnit bli klar. */}
      {showFatalError ? (
        <div className="bg-background/95 absolute inset-0 z-30 flex items-center justify-center px-6">
          <div className="border-destructive/40 bg-card w-full max-w-lg rounded-2xl border p-6 shadow-xl">
            <div className="mb-2 flex items-center gap-2">
              <AlertTriangle className="text-destructive h-5 w-5" />
              <h2 className="text-foreground text-lg font-semibold">
                {PHASE_LABEL[phase]}
              </h2>
            </div>
            <p className="text-muted-foreground mb-4 text-sm leading-relaxed">
              {errorMsg ?? "Bygget kunde inte slutföras."}
            </p>
            {logTail ? (
              <pre className="bg-muted/60 text-muted-foreground mb-4 max-h-48 overflow-auto rounded-lg p-3 font-mono text-[11px] leading-snug whitespace-pre-wrap">
                {logTail}
              </pre>
            ) : null}
            <Button
              variant="outline"
              onClick={() => {
                setSiteId(null);
                setPhase("idle");
                setErrorMsg(null);
                setLogTail("");
              }}
              className="gap-1.5"
            >
              <RefreshCw className="h-4 w-4" />
              Börja om
            </Button>
          </div>
        </div>
      ) : null}

      {/* Flytande chatt-overlay när previewen är aktiv. */}
      {showPreview ? (
        <ChatOverlay
          messages={messages}
          chatInput={chatInput}
          onChangeInput={setChatInput}
          onSend={() => void sendFollowup()}
          isWorking={isWorking}
          phase={phase}
          detail={detail}
          errorMsg={errorMsg}
        />
      ) : null}
    </main>
  );
}

function BuildProgress({
  phase,
  detail,
  logTail,
}: {
  phase: LivePhase;
  detail: string;
  logTail: string;
}) {
  const activeIdx = stepIndexForPhase(phase);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - start) / 1000)),
      1000,
    );
    return () => clearInterval(id);
  }, []);

  const mm = Math.floor(elapsed / 60);
  const ss = (elapsed % 60).toString().padStart(2, "0");

  return (
    <div className="border-border/60 bg-card w-full max-w-[560px] rounded-3xl border p-8 shadow-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-foreground text-[17px] font-semibold tracking-tight">
          Bygger din sajt
        </h2>
        <span className="bg-muted/60 text-foreground rounded-full px-2.5 py-1 font-mono text-[11px] tabular-nums">
          {mm}:{ss}
        </span>
      </div>

      <ol className="flex flex-col gap-1">
        {BUILD_STEPS.map((step, idx) => {
          const isActive = idx === activeIdx;
          const isPast = idx < activeIdx;
          return (
            <li
              key={step.title}
              className={`flex items-start gap-3 rounded-xl px-3 py-2.5 ${
                isActive ? "bg-foreground/[0.04]" : ""
              }`}
            >
              <span
                className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${
                  isPast || isActive
                    ? "bg-foreground text-background"
                    : "border-border/70 text-muted-foreground/70 border"
                }`}
              >
                {isActive ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  idx + 1
                )}
              </span>
              <div className="flex flex-col leading-snug">
                <span className="text-foreground text-[13px] font-medium">
                  {step.title}
                </span>
                <span className="text-muted-foreground text-[11.5px] leading-relaxed">
                  {isActive && detail ? detail : step.hint}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      {logTail ? (
        <pre className="bg-muted/50 text-muted-foreground/80 mt-5 max-h-28 overflow-auto rounded-lg p-3 font-mono text-[10.5px] leading-snug whitespace-pre-wrap">
          {logTail.split("\n").slice(-6).join("\n")}
        </pre>
      ) : null}
    </div>
  );
}

function ChatOverlay({
  messages,
  chatInput,
  onChangeInput,
  onSend,
  isWorking,
  phase,
  detail,
  errorMsg,
}: {
  messages: ChatMessage[];
  chatInput: string;
  onChangeInput: (value: string) => void;
  onSend: () => void;
  isWorking: boolean;
  phase: LivePhase;
  detail: string;
  errorMsg: string | null;
}) {
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, isWorking]);

  return (
    <div className="absolute right-4 bottom-4 z-20 flex w-[min(380px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-border/60 bg-card/95 shadow-2xl backdrop-blur-xl">
      <div className="border-border/50 flex items-center gap-2 border-b px-4 py-2.5">
        <span className="bg-foreground/80 inline-flex h-2 w-2 rounded-full" />
        <span className="text-foreground text-[13px] font-medium">
          Fortsätt prompta
        </span>
        {isWorking ? (
          <span className="text-muted-foreground ml-auto inline-flex items-center gap-1.5 text-[11px]">
            <Loader2 className="h-3 w-3 animate-spin" />
            {PHASE_LABEL[phase]}
            {detail ? ` · ${detail}` : ""}
          </span>
        ) : (
          <span className="text-muted-foreground/70 ml-auto text-[11px]">
            Klar
          </span>
        )}
      </div>

      <div
        ref={listRef}
        className="flex max-h-64 min-h-20 flex-col gap-2 overflow-y-auto px-4 py-3"
      >
        {messages.length === 0 ? (
          <p className="text-muted-foreground/70 text-[12px] leading-relaxed">
            Be om ändringar, t.ex. ”gör hero mörkare”, ”lägg till en
            prislista” eller ”byt rubrik till Välkommen”.
          </p>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`max-w-[85%] rounded-xl px-3 py-1.5 text-[12.5px] leading-relaxed ${
                m.role === "user"
                  ? "bg-foreground text-background self-end"
                  : "bg-muted/70 text-foreground self-start"
              }`}
            >
              {m.text}
            </div>
          ))
        )}
        {errorMsg && !isWorking ? (
          <div className="text-destructive bg-destructive/10 self-start rounded-xl px-3 py-1.5 text-[12px]">
            {errorMsg}
          </div>
        ) : null}
      </div>

      <div className="border-border/50 flex items-end gap-2 border-t p-2.5">
        <textarea
          value={chatInput}
          onChange={(e) => onChangeInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          rows={1}
          disabled={isWorking}
          placeholder={isWorking ? "Bygger …" : "Skriv en ändring …"}
          className="text-foreground placeholder:text-muted-foreground/60 max-h-28 min-h-9 flex-1 resize-none rounded-lg bg-transparent px-2 py-1.5 text-[13px] outline-none disabled:opacity-50"
        />
        <Button
          size="sm"
          onClick={onSend}
          disabled={isWorking || !chatInput.trim()}
          className="h-9 shrink-0 gap-1"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
