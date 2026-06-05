"use client";

import {
  Globe,
  History,
  ImagePlus,
  MessageCircleQuestion,
  Palette,
  Plus,
  RefreshCw,
  ScanSearch,
  Settings2,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";
import { Fragment } from "react";
import {
  KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Minimal "häftiga-ändringar"-meny. En liten pulserande pill nere
 * till vänster (motpol till FloatingChat som default sitter nere
 * till höger). Click → expanderar till en vertikal lista av icon-
 * actions. Pulserar mjukt när bygget jobbar så operatören vet att
 * något händer även om chatten är minimerad.
 *
 * Alla actions är light-weight wrappers över befintliga funktioner
 * — den här komponenten introducerar inga nya backend-anrop. Den
 * är medvetet liten: bara 4 standard-handlingar idag. Lägg in
 * framtida features genom att skicka in dem som extra `actions`-
 * props senare.
 */

export type BuilderActionIcon =
  | "history"
  | "console"
  | "new-site"
  | "design"
  | "settings"
  | "palette"
  | "image"
  | "globe"
  | "rebuild"
  | "ask"
  | "inspect";

export type BuilderAction = {
  id: string;
  label: string;
  description?: string;
  icon: BuilderActionIcon;
  onSelect: () => void;
  isDestructive?: boolean;
  /**
   * Valfri grupp-etikett. Actions med samma `group` renderas under
   * en gemensam sektion-header i menyn. Actions utan `group` visas
   * först (ogrupperat). Renderordning inom en grupp följer ordningen
   * i actions-arrayen.
   */
  group?: string;
  /** Inaktiverar action-knappen (t.ex. "Bygg om" medan ett bygge pågår). */
  disabled?: boolean;
};

type BuilderActionsProps = {
  /** Actions att visa i menyn. Renderas i den ordning de skickas in. */
  actions: BuilderAction[];
  /** Pulserar pillen mjukt när bygget jobbar. */
  pulsing?: boolean;
  /** Override för pill-position. Default: bottom-left. */
  side?: "left" | "right";
  /**
   * "fixed" (default) — pillen positioneras `fixed bottom-safe-6 left-6`
   *   och menyn popar UPPÅT från knappen.
   * "inline" — pillen rendras utan egen positionering (parent ansvarar)
   *   och menyn popar NEDÅT som dropdown via `absolute top-full`. Används
   *   när BuilderActions sitter i FloatingChat-toolbar-raden under chatten.
   */
  variant?: "fixed" | "inline";
};

const STORAGE_KEY_OPEN = "sajtbyggaren:builder-actions:open";

function readStoredOpen(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY_OPEN) === "true";
  } catch {
    return false;
  }
}

function iconComponent(kind: BuilderActionIcon) {
  switch (kind) {
    case "history":
      return History;
    case "console":
      return Terminal;
    case "new-site":
      return Plus;
    case "design":
      return Sparkles;
    case "settings":
      return Settings2;
    case "palette":
      return Palette;
    case "image":
      return ImagePlus;
    case "globe":
      return Globe;
    case "rebuild":
      return RefreshCw;
    case "ask":
      return MessageCircleQuestion;
    case "inspect":
      return ScanSearch;
    default:
      return Settings2;
  }
}

export function BuilderActions({
  actions,
  pulsing = false,
  side = "left",
  variant = "fixed",
}: BuilderActionsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Hydrera open-state efter mount (SSR-säkert).
  //
  // setState körs efter `await` via async IIFE — samma mönster som
  // viewer-panel.tsx + run-details-panel.tsx + floating-chat.tsx
  // använder för att inte trigga React 19:s
  // `react-hooks/set-state-in-effect`-rule.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setIsOpen(readStoredOpen());
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY_OPEN, String(isOpen));
    } catch {
      // Tyst.
    }
  }, [isOpen]);

  // Stäng på klick utanför (men inte på själva pillen).
  // Hoppas över i "inline"-variant — då renderas menyn som Dialog i
  // portal utanför containerRef, så denna handler skulle felaktigt
  // räkna klick på Dialog-content som "utanför" och stänga direkt.
  // Dialog hanterar sin egen backdrop-click och Escape via Base UI.
  useEffect(() => {
    if (!isOpen) return;
    if (variant === "inline") return;
    function onPointerDown(event: PointerEvent) {
      const node = containerRef.current;
      if (!node) return;
      if (event.target instanceof Node && node.contains(event.target)) return;
      setIsOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [isOpen, variant]);

  // Stäng på Escape — samma kommentar som ovan, hoppas över i inline.
  useEffect(() => {
    if (!isOpen) return;
    if (variant === "inline") return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, variant]);

  const handleSelect = useCallback((action: BuilderAction) => {
    if (action.disabled) return;
    setIsOpen(false);
    // Mikropaus så menyn hinner stängas innan ev. dialog öppnas.
    queueMicrotask(() => action.onSelect());
  }, []);

  // Gruppera actions i samma ordning som de skickas in. Actions utan
  // grupp läggs i en separat "_ungrouped"-bucket som renderas först
  // (utan header). Vi använder en Map så insättningsordningen bevaras.
  const groupedActions = useMemo(() => {
    const groups = new Map<string, BuilderAction[]>();
    for (const action of actions) {
      const key = action.group ?? "_ungrouped";
      const bucket = groups.get(key);
      if (bucket) {
        bucket.push(action);
      } else {
        groups.set(key, [action]);
      }
    }
    return groups;
  }, [actions]);

  const handleMenuKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      // Scope:a sökningen till elementet handlern sitter på
      // (event.currentTarget) i st.f. containerRef: i "inline"-varianten
      // renderas Verktyg-modalen i en Base UI-portal UTANFÖR containerRef,
      // så querySelectorAll(containerRef) hittade inga knappar och
      // piltangenterna var döda i just den modal operatören använder.
      // currentTarget pekar på rätt subträd i båda varianterna (fixed
      // dropdown = container-diven, inline = grid-diven i dialogen).
      const node = event.currentTarget;
      const buttons = Array.from(
        node.querySelectorAll<HTMLButtonElement>("[data-action-button]"),
      );
      if (buttons.length === 0) return;
      event.preventDefault();
      const currentIndex = buttons.findIndex(
        (button) => button === document.activeElement,
      );
      const nextIndex =
        event.key === "ArrowDown"
          ? (currentIndex + 1) % buttons.length
          : (currentIndex - 1 + buttons.length) % buttons.length;
      buttons[nextIndex]?.focus();
    },
    [],
  );

  const isInline = variant === "inline";

  return (
    // Verktygsmenyn döljs under md: (768px) — på mobil ockuperar
    // FloatingChat hela bottom-edgen som bottom-sheet, så
    // BuilderActions-pillen hamnar under chatten och blir oåtkomlig.
    // Operatören når samma actions via ConsoleDrawer (SiteHeader-
    // ikonen) och FloatingChat-interaktioner. Power-user-genvägen
    // lever kvar oförändrad på desktop.
    //
    // I "inline"-varianten ligger pillen inuti FloatingChat-toolbar-
    // raden (efter device-presets). Då har vi ingen egen fixed-position
    // utan ärver parentens centrering + drag-position, och menyn
    // renderas som Dialog-modal (grid med snygga boxar + backdrop-blur)
    // istället för dropdown-lista.
    <div
      ref={containerRef}
      onKeyDown={handleMenuKeyDown}
      className={cn(
        isInline
          ? "pointer-events-auto relative hidden md:inline-flex"
          : cn(
              "pointer-events-none fixed bottom-safe-6 z-40 hidden md:flex flex-col items-start gap-2",
              side === "left" ? "left-6 items-start" : "right-6 items-end",
            ),
      )}
    >
      {/* Dropdown-listan används bara i "fixed"-variant (legacy). I
          inline-fall renderas Dialog-modalen längre ner istället. */}
      {!isInline && isOpen ? (
        <div
          role="menu"
          aria-label="Builder-verktyg"
          className={cn(
            "border-border/60 bg-card/95 pointer-events-auto flex w-[230px] flex-col gap-0.5 rounded-xl border p-1 shadow-2xl backdrop-blur-xl",
            "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95 motion-safe:duration-150 origin-bottom",
          )}
        >
          {Array.from(groupedActions.entries()).map(
            ([groupKey, groupActions], groupIdx) => (
              <Fragment key={groupKey}>
                {groupKey !== "_ungrouped" ? (
                  <div
                    className={cn(
                      "text-muted-foreground/80 px-2.5 pt-2 pb-0.5 font-mono text-[9px] tracking-[0.18em] uppercase",
                      groupIdx > 0 && "border-border/40 mt-1 border-t pt-2",
                    )}
                  >
                    {groupKey}
                  </div>
                ) : null}
                {groupActions.map((action) => {
                  const Icon = iconComponent(action.icon);
                  return (
                    <button
                      type="button"
                      key={action.id}
                      role="menuitem"
                      data-action-button
                      disabled={action.disabled}
                      onClick={() => handleSelect(action)}
                      className={cn(
                        "group flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left",
                        "hover:bg-muted/60 focus-visible:bg-muted focus-visible:outline-none",
                        "disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent",
                        action.isDestructive
                          ? "text-destructive hover:text-destructive"
                          : "text-foreground",
                      )}
                    >
                      <Icon
                        className={cn(
                          "mt-0.5 h-3.5 w-3.5 shrink-0",
                          action.isDestructive
                            ? "text-destructive"
                            : "text-muted-foreground group-hover:text-foreground",
                        )}
                        aria-hidden
                      />
                      <span className="flex flex-1 flex-col leading-tight">
                        <span className="text-[12px] font-medium tracking-tight">
                          {action.label}
                        </span>
                        {action.description ? (
                          <span className="text-muted-foreground text-[10.5px]">
                            {action.description}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  );
                })}
              </Fragment>
            ),
          )}
        </div>
      ) : null}

      {/* Dialog-modal för inline-variant. Base UI Dialog hanterar
          backdrop-klick + Escape + focus-trap automatiskt. Operatören
          (2026-05-26) ville ha konsekvent 3-per-rad i hela modalen,
          så vi ignorerar groupedActions här och rendar ALLA actions
          i EN flat grid: grid-cols-2 på mobil, grid-cols-3 från sm:.
          Grupp-headers används bara i fixed-varianten (legacy
          dropdown) ovan. */}
      {isInline ? (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogContent
            showCloseButton={false}
            className="sm:max-w-2xl"
            aria-label="Builder-verktyg"
          >
            <DialogHeader>
              <DialogTitle>Verktyg</DialogTitle>
              <DialogDescription>
                Välj en åtgärd — ↑/↓ flyttar fokus, Esc stänger.
              </DialogDescription>
            </DialogHeader>
            {/* onKeyDown här (inte bara på container-diven): den inline
                modalen portaleras utanför containerRef, så piltangent-
                handlern måste sitta på ett element som faktiskt innehåller
                grid-knapparna. */}
            <div
              onKeyDown={handleMenuKeyDown}
              className="grid grid-cols-2 gap-3 sm:grid-cols-3"
            >
              {actions.map((action) => {
                const Icon = iconComponent(action.icon);
                return (
                  <button
                    type="button"
                    key={action.id}
                    data-action-button
                    disabled={action.disabled}
                    onClick={() => handleSelect(action)}
                    className={cn(
                      "group border-border/60 bg-card/80 flex flex-col items-center gap-2 rounded-xl border p-3 text-center shadow-sm transition",
                      "hover:bg-card hover:border-border focus-visible:ring-ring/50 focus-visible:ring-offset-background focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
                      "disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-card/80",
                      action.isDestructive && "hover:border-destructive/60",
                    )}
                  >
                    <span
                      className={cn(
                        "bg-muted/70 group-hover:bg-muted flex h-10 w-10 items-center justify-center rounded-full transition",
                        action.isDestructive &&
                          "bg-destructive/10 group-hover:bg-destructive/15",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-5 w-5",
                          action.isDestructive
                            ? "text-destructive"
                            : "text-muted-foreground group-hover:text-foreground",
                        )}
                        aria-hidden
                      />
                    </span>
                    <span className="flex min-h-[2.25rem] flex-col leading-tight">
                      <span
                        className={cn(
                          "text-[12.5px] font-medium tracking-tight",
                          action.isDestructive
                            ? "text-destructive"
                            : "text-foreground",
                        )}
                      >
                        {action.label}
                      </span>
                      {action.description ? (
                        <span className="text-muted-foreground mt-0.5 text-[10.5px]">
                          {action.description}
                        </span>
                      ) : null}
                    </span>
                  </button>
                );
              })}
            </div>
          </DialogContent>
        </Dialog>
      ) : null}

      {/* Verktyg-knappen.
          - I "fixed"-variant: en fristående pill (h-10) med egen border
            + shadow.
          - I "inline"-variant: ren knapp utan border/shadow (h-8) som
            matchar device-preset-knapparna i FloatingChat-toolbar-raden
            så hela raden ser ut som EN sammanhängande pill. */}
      <button
        type="button"
        aria-label={isOpen ? "Stäng verktygsmeny" : "Öppna verktygsmeny"}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "group pointer-events-auto inline-flex items-center font-medium transition active:scale-95",
          "focus-visible:ring-ring/50 focus-visible:ring-offset-background focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
          isInline
            ? cn(
                "h-8 gap-1.5 rounded-full px-2.5 text-[11px]",
                isOpen
                  ? "bg-foreground text-background shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )
            : cn(
                "border-border/60 bg-card/95 text-muted-foreground h-10 gap-2 rounded-full border px-3 text-[11px] shadow-lg backdrop-blur-xl",
                "hover:bg-card hover:text-foreground",
              ),
        )}
      >
        <span className="relative flex h-2 w-2 items-center justify-center">
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full",
              isInline
                ? isOpen
                  ? "bg-background/70"
                  : "bg-muted-foreground/60"
                : isOpen
                  ? "bg-foreground/70"
                  : "bg-muted-foreground/60",
              pulsing && !isOpen && "motion-safe:animate-ping",
            )}
            aria-hidden
          />
          <span
            className={cn(
              "relative inline-flex h-2 w-2 rounded-full",
              isInline
                ? isOpen
                  ? "bg-background"
                  : "bg-muted-foreground"
                : isOpen
                  ? "bg-foreground"
                  : "bg-muted-foreground",
            )}
            aria-hidden
          />
        </span>
        <span>Verktyg</span>
        {!isInline && isOpen ? <X className="h-3.5 w-3.5" aria-hidden /> : null}
      </button>
    </div>
  );
}
