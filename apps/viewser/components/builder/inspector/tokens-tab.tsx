"use client";

import { CircleCheck, Palette, RotateCcw, Sparkles, Wand2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  broadcastTokenChange,
  buildTokenCommitPrompt,
  isTokenAckMessage,
  TOKEN_DEFAULTS,
  TOKEN_META,
  type TokenId,
} from "@/lib/runtime-tokens";
import { PRIMARY_INTERACTIONS, SECONDARY_INTERACTIONS } from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

const HEX_PATTERN = /^#[0-9a-f]{6}$/i;
const STORAGE_KEY = "sajtbyggaren:tokens-tab:overrides";
// Hur länge "Live i preview ✓"-badgen visas efter senaste ack:en. När
// timern går ut faller vi tillbaka till "väntar"-state — en frisk ack
// kommer in vid nästa token-ändring så badgen flyttar fram. Tre sekunder
// är tillräckligt för att operatören ska hinna läsa men kort nog att
// gamla ack:s inte fastnar synliga efter att preview-servern dött.
const LIVE_BADGE_TTL_MS = 3000;

/**
 * TokensTab — Site Inspectors färg-editor (Sprint 5).
 *
 * UX i tre lager (se ``lib/runtime-tokens.ts`` för fullständig
 * arkitektur-doc):
 *
 *   1. Live mini-preview i tabben själv — operatören ser visuell
 *      feedback direkt när hen drar i color-pickern.
 *   2. postMessage-broadcast till alla iframes — best-effort
 *      uppdatering av preview-iframen om dess runtime-script
 *      lyssnar (additivt i scripts/build_site.py).
 *   3. "Använd dessa färger"-knapp committar via en quick-prompt
 *      som skickas genom samma follow-up-pipeline som FloatingChat —
 *      pålitlig och ändrar faktiskt sajten.
 *
 * Persistering: pågående overrides sparas i sessionStorage så
 * operatören inte tappar dem när hen byter tab eller råkar stänga
 * inspectorn. Reset-knappen rensar både state och storage.
 */
export interface TokensTabProps {
  isBuilding: boolean;
  pendingPrompt: string | null;
  onPrompt: (prompt: string) => void | Promise<void>;
}

const TOKEN_ORDER: ReadonlyArray<TokenId> = [
  "primary",
  "accent",
  "background",
  "foreground",
];

function readStoredTokens(): Record<TokenId, string> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Record<TokenId, string>>;
    const result: Record<TokenId, string> = { ...TOKEN_DEFAULTS };
    let touched = false;
    for (const id of TOKEN_ORDER) {
      const value = parsed?.[id];
      if (typeof value === "string" && HEX_PATTERN.test(value)) {
        result[id] = value.toLowerCase();
        touched = true;
      }
    }
    return touched ? result : null;
  } catch {
    return null;
  }
}

function persistTokens(tokens: Record<TokenId, string>): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  } catch {
    // Quota exceeded eller private-mode — tokens lever fortsatt i
    // React-state, bara inte över reloads. Säker degradering.
  }
}

function clearStoredTokens(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Se persistTokens.
  }
}

export function TokensTab({ isBuilding, pendingPrompt, onPrompt }: TokensTabProps) {
  // Lazy state-init så sessionStorage-läsningen sker inom render-
  // closure:n (SSR-safe — readStoredTokens returnerar null på server).
  const [tokens, setTokens] = useState<Record<TokenId, string>>(
    () => readStoredTokens() ?? { ...TOKEN_DEFAULTS },
  );

  // ``isLive`` styr om "Live i preview ✓"-badgen visas. Den sätts till
  // ``true`` så fort en ack kommer in från preview-iframens runtime-
  // listener, och resettas av en setTimeout efter LIVE_BADGE_TTL_MS så
  // gamla ack:s inte fastnar synliga efter att preview-servern dött.
  // Vi använder en separat ``ackVersion``-räknare för att restarta
  // TTL-timern vid varje ny ack — useEffect:en på [ackVersion] startar
  // en frisk timer som rensar isLive när den löper ut.
  const [isLive, setIsLive] = useState(false);
  const [ackVersion, setAckVersion] = useState(0);

  // Persistera + broadcast vid varje ändring. Vi gör detta i en
  // effect istället för i setTokens-callern så vi inte glömmer det
  // vid en framtida code-path som råkar uppdatera state.
  useEffect(() => {
    persistTokens(tokens);
    for (const id of TOKEN_ORDER) {
      const value = tokens[id];
      const baseline = TOKEN_DEFAULTS[id];
      // Skicka bara förändringar (jämfört med canonical) så vi inte
      // spammar iframe:n med no-op:s.
      if (value && value.toLowerCase() !== baseline.toLowerCase()) {
        broadcastTokenChange(id, value);
      }
    }
  }, [tokens]);

  // Lyssna på ack-meddelanden från preview-iframens runtime-listener.
  // Detta är det enda sättet vi kan veta om broadcast-en faktiskt
  // nådde fram — postMessage är fire-and-forget utan returvärde. När
  // vi får en ack tänder vi badgen och bumpar ackVersion så TTL-
  // effekten startar om en ny släck-timer.
  useEffect(() => {
    if (typeof window === "undefined") return;
    function onMessage(event: MessageEvent) {
      if (!isTokenAckMessage(event.data)) return;
      setIsLive(true);
      setAckVersion((value) => value + 1);
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  // Auto-släck Live-badgen efter TTL från senaste ack:en. Triggas
  // varje gång ackVersion bumpas — om en ny ack kommer in innan TTL
  // löper ut clearTimeout:en den gamla timern och en frisk schemaläggs.
  useEffect(() => {
    if (ackVersion === 0) return;
    const handle = window.setTimeout(() => setIsLive(false), LIVE_BADGE_TTL_MS);
    return () => window.clearTimeout(handle);
  }, [ackVersion]);

  const handleTokenChange = useCallback((id: TokenId, raw: string) => {
    const value = raw.trim().toLowerCase();
    if (!HEX_PATTERN.test(value)) return;
    setTokens((prev) => ({ ...prev, [id]: value }));
  }, []);

  const handleReset = useCallback(() => {
    setTokens({ ...TOKEN_DEFAULTS });
    clearStoredTokens();
    // Bredcast "reset" så iframen som ev. lyssnar kan återställa
    // sina egna overrides utan att hela sajten behöver byggas om.
    for (const id of TOKEN_ORDER) {
      broadcastTokenChange(id, "reset");
    }
  }, []);

  const commitPrompt = useMemo(
    () => buildTokenCommitPrompt(tokens),
    [tokens],
  );
  const hasOverrides = commitPrompt.length > 0;

  const handleCommit = useCallback(() => {
    if (!hasOverrides || isBuilding) return;
    void onPrompt(commitPrompt);
  }, [commitPrompt, hasOverrides, isBuilding, onPrompt]);

  const isPending = pendingPrompt === commitPrompt && pendingPrompt !== null;

  return (
    <div className="flex flex-col gap-5">
      <div className="border-border/40 bg-foreground/[0.02] flex items-start gap-2.5 rounded-lg border p-3">
        <Palette className="text-foreground/70 mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="text-foreground/85 flex-1 text-[12px] leading-relaxed">
          Experimentera med färgerna här. Mini-preview:n nedan uppdateras
          direkt. Klicka <strong>Använd dessa färger</strong> för att
          committa till sajten via ett nytt bygge.
        </div>
        {/* Live-badge: tänds när vi får ett ack från preview-iframens
            runtime-listener. Med lokal preview-server (same-machine
            iframe) flippar denna omedelbart vid första token-ändringen.
            För StackBlitz cross-origin förblir den släckt — UX:n
            degraderar tystlåtet: mini-preview:n + commit-knappen
            fungerar fortfarande. */}
        {isLive ? (
          <span className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium dark:text-emerald-400">
            <CircleCheck className="h-2.5 w-2.5" />
            Live i preview
          </span>
        ) : null}
      </div>

      <div className="flex flex-col gap-3">
        {TOKEN_ORDER.map((id) => (
          <TokenRow
            key={id}
            id={id}
            value={tokens[id]}
            onChange={(value) => handleTokenChange(id, value)}
          />
        ))}
      </div>

      <TokenPreview tokens={tokens} />

      <div className="border-border/60 flex flex-col gap-2 border-t pt-4">
        <button
          type="button"
          onClick={handleCommit}
          disabled={!hasOverrides || isBuilding || isPending}
          className={cn(
            "bg-foreground text-background inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-2 text-[12.5px] font-medium",
            "hover:bg-foreground/90 disabled:opacity-40",
            "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
            PRIMARY_INTERACTIONS,
          )}
        >
          {isPending ? (
            <>
              <Sparkles className="h-3.5 w-3.5 animate-pulse" />
              Bygger om sajten…
            </>
          ) : (
            <>
              <Wand2 className="h-3.5 w-3.5" />
              {hasOverrides
                ? "Använd dessa färger"
                : "Inga ändringar att applicera"}
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleReset}
          disabled={!hasOverrides}
          className={cn(
            "text-muted-foreground hover:text-foreground border-border/60 hover:border-foreground/40 hover:bg-muted/40",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            "inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-[11.5px] font-medium transition-colors disabled:opacity-40",
            SECONDARY_INTERACTIONS,
          )}
        >
          <RotateCcw className="h-3 w-3" />
          Återställ till sajtens defaults
        </button>
        {hasOverrides ? (
          <p className="text-muted-foreground mt-1 text-[10.5px] leading-relaxed">
            Prompten som skickas:{" "}
            <code className="bg-muted/40 text-foreground/80 rounded px-1 py-0.5 font-mono text-[10px]">
              {commitPrompt}
            </code>
          </p>
        ) : null}
      </div>
    </div>
  );
}

/* ── Token row ─────────────────────────────────────────────────── */

function TokenRow({
  id,
  value,
  onChange,
}: {
  id: TokenId;
  value: string;
  onChange: (next: string) => void;
}) {
  // Spegla input-state lokalt så operatören kan skriva en hex som
  // tillfälligt är ogiltig (t.ex. "#1" → "#1a" → "#1a2") utan att
  // vi nollställer fältet vid varje keystroke. Vi syncar mot
  // ``value``-prop via render-time-jämförelse (React 19 dokumenterat
  // pattern "Storing information from previous renders") istället
  // för useEffect+setState — det senare träffar
  // ``react-hooks/set-state-in-effect`` lint:en eftersom React 19
  // anser det vara onödig effect-arbete.
  const [draft, setDraft] = useState(value);
  const [seenValue, setSeenValue] = useState(value);
  if (seenValue !== value) {
    setSeenValue(value);
    setDraft(value);
  }

  const meta = TOKEN_META[id];
  const isValid = HEX_PATTERN.test(draft);

  return (
    <div className="border-border/40 bg-card/40 flex items-center gap-3 rounded-lg border p-2.5">
      {/* Native color picker — funkar i alla browsers och ger
          drag-friction-fri färgval. Vi förkomprimerar värdet till
          lower-case så jämförelser i state är konsistenta. */}
      <input
        type="color"
        value={value}
        onChange={(event) => onChange(event.target.value.toLowerCase())}
        aria-label={`Välj ${meta.label.toLowerCase()}`}
        className="h-9 w-9 shrink-0 cursor-pointer rounded-md border-0 bg-transparent p-0 [&::-webkit-color-swatch-wrapper]:p-0 [&::-webkit-color-swatch]:rounded-md [&::-webkit-color-swatch]:border-0"
      />
      <div className="min-w-0 flex-1">
        <div className="text-foreground text-[12.5px] font-medium tracking-tight">
          {meta.label}
        </div>
        <div className="text-muted-foreground text-[10.5px] leading-snug">
          {meta.description}
        </div>
      </div>
      <input
        type="text"
        value={draft}
        onChange={(event) => {
          const next = event.target.value;
          setDraft(next);
          if (HEX_PATTERN.test(next)) onChange(next.toLowerCase());
        }}
        spellCheck={false}
        maxLength={7}
        aria-label={`Hex-värde för ${meta.label.toLowerCase()}`}
        className={cn(
          "border-border/60 bg-background w-[88px] shrink-0 rounded-md border px-2 py-1 text-right font-mono text-[11px] tabular-nums",
          "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
          !isValid && "border-amber-500/50 text-amber-700 dark:text-amber-400",
        )}
      />
    </div>
  );
}

/* ── Mini-preview ──────────────────────────────────────────────── */

/**
 * Visuellt sample-card som rendrar med valda tokens via inline-style.
 * Det är inte en byte-för-byte-kopia av sajten men ger operatören en
 * känsla för hur primärknappar/accent/text/bakgrund samspelar utan
 * att behöva vänta på ett nytt bygge.
 */
function TokenPreview({ tokens }: { tokens: Record<TokenId, string> }) {
  return (
    <div className="border-border/60 overflow-hidden rounded-xl border">
      <div className="border-border/60 bg-card/40 border-b px-3 py-2">
        <span className="text-muted-foreground font-mono text-[9.5px] tracking-[0.22em] uppercase">
          Mini-preview
        </span>
      </div>
      <div
        className="space-y-3 p-4"
        style={{
          background: tokens.background,
          color: tokens.foreground,
        }}
      >
        <div
          className="text-[13px] font-semibold tracking-tight"
          style={{ color: tokens.foreground }}
        >
          Välkommen till vår sajt
        </div>
        <p
          className="text-[11.5px] leading-relaxed"
          style={{ color: tokens.foreground, opacity: 0.78 }}
        >
          Vi hjälper små företag att synas online med moderna, snabba
          hemsidor som ger resultat.
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-md px-3 py-1.5 text-[11.5px] font-medium transition-opacity hover:opacity-90"
            style={{
              background: tokens.primary,
              color: tokens.background,
            }}
            onClick={(event) => event.preventDefault()}
          >
            Boka tid
          </button>
          <span
            className="rounded-full px-2 py-0.5 text-[10.5px] font-medium"
            style={{
              background: `${tokens.accent}22`,
              color: tokens.accent,
            }}
          >
            Nyhet
          </span>
        </div>
      </div>
    </div>
  );
}
