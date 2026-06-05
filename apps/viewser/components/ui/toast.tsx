"use client";

import { CheckCircle2, Info, TriangleAlert, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Lättviktigt internt toast-system. Eget istället för Sonner/react-hot-
// toast eftersom vi vill hålla bundle-size och dep-graph minimala — vi har
// redan @base-ui/react för andra primitiver, ingen anledning att dra in
// en till.
//
// Tre publika API:er:
//   - <ToastProvider>: wrappa app:en (i Providers).
//   - <Toaster>: rendera regionen (mountas EN gång nära root).
//   - useToast(): { show, dismiss } i komponenter.
//
// Alla toaster har `aria-live` så skärmläsare läser upp dem. Default
// auto-dismiss är 4500 ms. `variant: "error"` ligger längre (8000) eftersom
// fel ofta innehåller actionable information operatören vill hinna läsa.

export type ToastVariant = "info" | "success" | "warning" | "error";

export type ToastInput = {
  title?: string;
  description: string;
  variant?: ToastVariant;
  // 0 = persistent (dismiss kräver klick).
  durationMs?: number;
  // Optional knapp: "Försök igen", "Ångra" osv.
  action?: {
    label: string;
    onClick: () => void;
  };
};

type ToastEntry = ToastInput & {
  id: string;
  // För animationen — markeras true när vi börjar fade-out, body avmonteras
  // efter en kort delay så transitionen hinner spelas.
  closing: boolean;
};

type ToastContextValue = {
  show: (toast: ToastInput) => string;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATIONS: Record<ToastVariant, number> = {
  info: 4500,
  success: 4500,
  warning: 6000,
  error: 8000,
};

// Lite längre än CSS-transitionen (250 ms) så DOM-noden är borta när
// nästa toast slidar in.
const CLOSE_ANIMATION_MS = 280;

// Tak för hur många toaster som visas samtidigt. När en ny pushas över
// taket stängs den äldsta aktiva (med close-animation) så stacken inte
// växer obegränsat vid t.ex. upprepade retry-fel.
const MAX_VISIBLE_TOASTS = 4;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  // Vi håller alla aktiva timeouts i en ref så de kan rensas vid manuell
  // dismiss eller unmount. Använder en plain Map istället för state — vi
  // vill inte trigga rerender när timern startar.
  const timeoutsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map(),
  );
  // Synk-spegel av `toasts` så `show` kan läsa aktuell stack synkront
  // (dedupe + max-stack) utan att stänga över stale state.
  const toastsRef = useRef<ToastEntry[]>([]);
  useEffect(() => {
    toastsRef.current = toasts;
  }, [toasts]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
    // Rensa BÅDA tänkbara timer-nycklar — auto-dismiss (``id``) och
    // cleanup-timer (``${id}:cleanup``) — så att vi inte läcker
    // entries i Map:en om en toast både auto-dismissade och blev
    // manuellt stängd innan close-animationen hann landa.
    const autoTimeout = timeoutsRef.current.get(id);
    if (autoTimeout) {
      clearTimeout(autoTimeout);
      timeoutsRef.current.delete(id);
    }
    const cleanupTimeout = timeoutsRef.current.get(`${id}:cleanup`);
    if (cleanupTimeout) {
      clearTimeout(cleanupTimeout);
      timeoutsRef.current.delete(`${id}:cleanup`);
    }
  }, []);

  const dismiss = useCallback(
    (id: string) => {
      // Idempotent: om denna toast redan håller på att stängas (vi har
      // en cleanup-timer för den) hoppar vi över. Annars schedulerar
      // vi en ny close-animation + cleanup, vilket leder till dubbel
      // ``removeToast``-anrop när auto-dismiss och manuell dismiss
      // träffar samtidigt — ofarligt logiskt men tidigare läckte vi
      // Map-entries för cleanup-nyckeln.
      if (timeoutsRef.current.has(`${id}:cleanup`)) return;

      // Stäng pågående auto-dismiss-timer så den inte triggar dismiss
      // igen mitt under close-animationen och försöker köra
      // ``removeToast`` parallellt med cleanup-timern.
      const autoTimeout = timeoutsRef.current.get(id);
      if (autoTimeout) {
        clearTimeout(autoTimeout);
        timeoutsRef.current.delete(id);
      }

      setToasts((prev) =>
        prev.map((toast) =>
          toast.id === id ? { ...toast, closing: true } : toast,
        ),
      );
      // Avmontera först efter close-animation så transitionen syns.
      const cleanupTimeout = setTimeout(() => {
        removeToast(id);
      }, CLOSE_ANIMATION_MS);
      timeoutsRef.current.set(`${id}:cleanup`, cleanupTimeout);
    },
    [removeToast],
  );

  const show = useCallback(
    (input: ToastInput): string => {
      const variant = input.variant ?? "info";

      // Dedupe: en identisk (variant + titel + beskrivning), ännu icke-
      // stängande toast finns redan → returnera dess id i st.f. att stapla
      // en dubblett. Fångar t.ex. upprepade "Kunde inte ladda runs"-retrys.
      const duplicate = toastsRef.current.find(
        (toast) =>
          !toast.closing &&
          (toast.variant ?? "info") === variant &&
          toast.title === input.title &&
          toast.description === input.description,
      );
      if (duplicate) return duplicate.id;

      // Max-stack: stäng äldsta aktiva toasten innan vi lägger till en ny
      // över taket (med close-animation via dismiss, inte hård slice — så
      // timers städas och transitionen syns).
      const active = toastsRef.current.filter((toast) => !toast.closing);
      if (active.length >= MAX_VISIBLE_TOASTS) {
        dismiss(active[0].id);
      }

      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

      setToasts((prev) => [
        ...prev,
        {
          ...input,
          id,
          variant,
          closing: false,
        },
      ]);

      const duration = input.durationMs ?? DEFAULT_DURATIONS[variant];
      if (duration > 0) {
        const timeout = setTimeout(() => {
          dismiss(id);
        }, duration);
        timeoutsRef.current.set(id, timeout);
      }

      return id;
    },
    [dismiss],
  );

  // Cleanup vid unmount så pågående timers inte uppdaterar avmonterad state.
  useEffect(() => {
    const timeouts = timeoutsRef.current;
    return () => {
      timeouts.forEach((timeout) => clearTimeout(timeout));
      timeouts.clear();
    };
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({ show, dismiss }),
    [show, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext);
  if (!value) {
    throw new Error("useToast måste användas inuti <ToastProvider>");
  }
  return value;
}

const VARIANT_ICONS: Record<ToastVariant, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  error: XCircle,
};

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  info: "border-border bg-card text-foreground [&_[data-variant-icon]]:text-foreground/70",
  success:
    "border-emerald-500/40 bg-emerald-500/10 text-foreground [&_[data-variant-icon]]:text-emerald-600 dark:[&_[data-variant-icon]]:text-emerald-400",
  warning:
    "border-amber-500/40 bg-amber-500/10 text-foreground [&_[data-variant-icon]]:text-amber-600 dark:[&_[data-variant-icon]]:text-amber-400",
  error:
    "border-destructive/40 bg-destructive/10 text-foreground [&_[data-variant-icon]]:text-destructive",
};

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastEntry[];
  onDismiss: (id: string) => void;
}) {
  // role="region" + aria-live ligger på själva listan — varje toast får
  // role="status" eller "alert" beroende på variant.
  //
  // Position: top-center på mobil (< sm), top-right på desktop. Vi
  // bodde tidigare i bottom-region men där krockar vi med
  // FloatingChat-composern (desktop bottom-6) och bottom-sheet-modes på
  // mobil. Top är säkrare yta — site-header är vår enda fixed-top och
  // den ligger på z-20 medan vi använder z-[80].
  return (
    <ol
      role="region"
      aria-label="Aviseringar"
      className={cn(
        "pointer-events-none fixed inset-x-0 top-20 z-[80] mx-auto flex w-full max-w-md flex-col gap-2 px-4",
        "sm:top-20 sm:right-4 sm:left-auto sm:mx-0 sm:max-w-sm sm:px-0",
      )}
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </ol>
  );
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastEntry;
  onDismiss: (id: string) => void;
}) {
  const variant = toast.variant ?? "info";
  const Icon = VARIANT_ICONS[variant];
  const liveRole = variant === "error" ? "alert" : "status";

  return (
    <li
      role={liveRole}
      aria-live={variant === "error" ? "assertive" : "polite"}
      className={cn(
        "pointer-events-auto flex items-start gap-3 rounded-xl border px-3.5 py-3 shadow-sm backdrop-blur-sm",
        "transition-all duration-200 ease-out motion-reduce:transition-none",
        VARIANT_CLASSES[variant],
        toast.closing
          ? "-translate-y-1 opacity-0"
          : "animate-in slide-in-from-top-2 fade-in",
      )}
    >
      <Icon data-variant-icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1 text-[13px] leading-snug">
        {toast.title ? (
          <p className="text-foreground font-medium">{toast.title}</p>
        ) : null}
        <p
          className={cn(
            "text-muted-foreground",
            !toast.title && "text-foreground",
          )}
        >
          {toast.description}
        </p>
        {toast.action ? (
          <div className="mt-2">
            <Button
              size="xs"
              variant="outline"
              onClick={() => {
                toast.action?.onClick();
                onDismiss(toast.id);
              }}
            >
              {toast.action.label}
            </Button>
          </div>
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Stäng avisering"
        className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 min-tap sm:min-tap-0 -mt-1 -mr-1 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <X className="h-3.5 w-3.5" aria-hidden />
      </button>
    </li>
  );
}
