"use client";

import {
  Blocks,
  ChevronDown,
  Crosshair,
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
} from "lucide-react";
import {
  KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { cn } from "@/lib/utils";

/**
 * Topp-centrerad verktygsyta över preview-canvasen (operatörsbeslut
 * 2026-06-11): en minimal "Verktyg ˅"-pill mitt på överkanten som
 * expanderar nedåt till en flik-panel. Ersätter den tidigare
 * Verktyg-pillen som bodde i FloatingChat-toolbaren.
 *
 * Flikarna härleds ur `action.group` i insättningsordning — en flik
 * per grupp, gridden visar bara aktiv fliks actions. Tanken är att
 * varje flik mappar mot en specialist-domän (KÖR-6) och kan växa med
 * fler verktyg utan att panelen blir en oöverskådlig platt grid.
 *
 * Alla actions är fortsatt light-weight wrappers över befintliga
 * funktioner — komponenten introducerar inga nya backend-anrop.
 *
 * Desktop-only (hidden under md:) av samma skäl som tidigare pill:
 * på mobil ockuperar FloatingChat bottom-edgen och operatören når
 * motsvarande funktioner via ConsoleDrawer.
 */

export type BuilderActionIcon =
  | "history"
  | "console"
  | "new-site"
  | "design"
  | "settings"
  | "palette"
  | "image"
  | "module"
  | "globe"
  | "rebuild"
  | "ask"
  | "inspect"
  | "preview-inspect";

export type BuilderAction = {
  id: string;
  label: string;
  description?: string;
  icon: BuilderActionIcon;
  onSelect: () => void;
  isDestructive?: boolean;
  /**
   * Flik-etikett. Actions med samma `group` hamnar under samma flik
   * i panelen. Flik-ordningen följer första förekomsten i
   * actions-arrayen; actions utan grupp hamnar under "Övrigt".
   */
  group?: string;
  /** Inaktiverar action-knappen (t.ex. "Bygg om" medan ett bygge pågår). */
  disabled?: boolean;
};

type ToolsPopoverProps = {
  /** Actions att visa. Flikar härleds ur `group` i insättningsordning. */
  actions: BuilderAction[];
  /** Pulserar pillens statusprick mjukt när bygget jobbar. */
  pulsing?: boolean;
};

const STORAGE_KEY_OPEN = "sajtbyggaren:tools-popover:open";
const STORAGE_KEY_TAB = "sajtbyggaren:tools-popover:tab";
const UNGROUPED_TAB = "Övrigt";

function readStoredOpen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY_OPEN) === "true";
  } catch {
    return false;
  }
}

function readStoredTab(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY_TAB);
  } catch {
    return null;
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
    case "module":
      return Blocks;
    case "globe":
      return Globe;
    case "rebuild":
      return RefreshCw;
    case "ask":
      return MessageCircleQuestion;
    case "inspect":
      return ScanSearch;
    case "preview-inspect":
      return Crosshair;
    default:
      return Settings2;
  }
}

export function ToolsPopover({ actions, pulsing = false }: ToolsPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Flikar i insättningsordning: en per group, ogrupperade sist.
  const tabs = useMemo(() => {
    const map = new Map<string, BuilderAction[]>();
    for (const action of actions) {
      const key = action.group ?? UNGROUPED_TAB;
      const bucket = map.get(key);
      if (bucket) {
        bucket.push(action);
      } else {
        map.set(key, [action]);
      }
    }
    return Array.from(map.entries()).map(([label, items]) => ({
      label,
      items,
    }));
  }, [actions]);

  // Hydrera open-state + senast valda flik efter mount (SSR-säkert).
  // setState körs efter `await` via async IIFE — samma mönster som
  // viewer-panel.tsx + floating-chat.tsx använder för att inte trigga
  // React 19:s `react-hooks/set-state-in-effect`-rule.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setIsOpen(readStoredOpen());
      setActiveTab(readStoredTab());
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

  useEffect(() => {
    if (!activeTab) return;
    try {
      window.localStorage.setItem(STORAGE_KEY_TAB, activeTab);
    } catch {
      // Tyst.
    }
  }, [activeTab]);

  // Lagrad/initial flik valideras mot faktiska flikar — faller
  // tillbaka på första fliken om den lagrade inte längre finns.
  const resolvedTab = useMemo(() => {
    if (activeTab && tabs.some((tab) => tab.label === activeTab)) {
      return activeTab;
    }
    return tabs[0]?.label ?? null;
  }, [activeTab, tabs]);

  const activeItems = useMemo(
    () => tabs.find((tab) => tab.label === resolvedTab)?.items ?? [],
    [tabs, resolvedTab],
  );

  // Stäng på klick utanför (men inte på själva pillen/panelen).
  useEffect(() => {
    if (!isOpen) return;
    function onPointerDown(event: PointerEvent) {
      const node = containerRef.current;
      if (!node) return;
      if (event.target instanceof Node && node.contains(event.target)) return;
      setIsOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [isOpen]);

  // Stäng på Escape.
  useEffect(() => {
    if (!isOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen]);

  const handleSelect = useCallback((action: BuilderAction) => {
    if (action.disabled) return;
    setIsOpen(false);
    // Mikropaus så panelen hinner stängas innan ev. dialog öppnas.
    queueMicrotask(() => action.onSelect());
  }, []);

  // ↑/↓ flyttar fokus mellan action-korten i aktiv fliks grid.
  const handleGridKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
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

  // ←/→ byter flik när fokus står i flikraden.
  const handleTabsKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (tabs.length === 0 || !resolvedTab) return;
      event.preventDefault();
      const currentIndex = tabs.findIndex((tab) => tab.label === resolvedTab);
      const nextIndex =
        event.key === "ArrowRight"
          ? (currentIndex + 1) % tabs.length
          : (currentIndex - 1 + tabs.length) % tabs.length;
      const next = tabs[nextIndex];
      if (next) {
        setActiveTab(next.label);
        // Flytta fokus till den nya flik-knappen så ←/→ kan kedjas.
        const node = event.currentTarget;
        const buttons = node.querySelectorAll<HTMLButtonElement>(
          "[data-tab-button]",
        );
        buttons[nextIndex]?.focus();
      }
    },
    [tabs, resolvedTab],
  );

  return (
    // Topp-centrerad, desktop-only. z-40 ligger över SiteHeader (z-30)
    // och preview-overlays men under ev. modaler (z-50). pt-safe-fri:
    // studio-canvasen är h-[100dvh] utan notch-problematik på desktop.
    <div
      ref={containerRef}
      className="fixed top-3 left-1/2 z-40 hidden -translate-x-1/2 flex-col items-center md:flex"
    >
      {/* Pillen: "Verktyg" + chevron som roterar när panelen är öppen. */}
      <button
        type="button"
        aria-label={isOpen ? "Stäng verktygspanelen" : "Öppna verktygspanelen"}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "group pointer-events-auto inline-flex h-9 items-center gap-2 rounded-full border px-3.5 text-[11px] font-medium transition active:scale-95",
          "border-border/60 bg-card/95 shadow-lg backdrop-blur-xl",
          "focus-visible:ring-ring/50 focus-visible:ring-offset-background focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
          isOpen
            ? "text-foreground"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <span className="relative flex h-2 w-2 items-center justify-center">
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full",
              isOpen ? "bg-foreground/70" : "bg-muted-foreground/60",
              pulsing && !isOpen && "motion-safe:animate-ping",
            )}
            aria-hidden
          />
          <span
            className={cn(
              "relative inline-flex h-2 w-2 rounded-full",
              isOpen ? "bg-foreground" : "bg-muted-foreground",
            )}
            aria-hidden
          />
        </span>
        <span>Verktyg</span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-200",
            isOpen && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      {/* Panelen: flikrad + aktiv fliks action-grid. Expanderar nedåt
          från pillen. */}
      {isOpen ? (
        <div
          className={cn(
            "border-border/60 bg-card/95 pointer-events-auto mt-2 w-[620px] max-w-[calc(100vw-2rem)] rounded-2xl border p-3 shadow-2xl backdrop-blur-xl",
            "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-2 motion-safe:duration-150",
          )}
        >
          {/* Flikrad. role=tablist + ←/→-navigering. */}
          <div
            role="tablist"
            aria-label="Verktygsflikar"
            onKeyDown={handleTabsKeyDown}
            className="mb-3 flex items-center gap-1"
          >
            {tabs.map((tab) => {
              const isActive = tab.label === resolvedTab;
              return (
                <button
                  key={tab.label}
                  type="button"
                  role="tab"
                  data-tab-button
                  aria-selected={isActive}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => setActiveTab(tab.label)}
                  className={cn(
                    "inline-flex h-8 items-center rounded-full px-3 text-[11.5px] font-medium transition active:scale-95",
                    "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                    isActive
                      ? "bg-foreground text-background shadow-sm"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                  )}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Aktiv fliks actions — samma kortstil (3 per rad) som den
              tidigare Verktyg-modalen, operatörsönskan 2026-05-26. */}
          <div
            role="tabpanel"
            aria-label={resolvedTab ?? undefined}
            onKeyDown={handleGridKeyDown}
            className="grid grid-cols-3 gap-3"
          >
            {activeItems.map((action) => {
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
                    "disabled:hover:bg-card/80 disabled:cursor-not-allowed disabled:opacity-45",
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
        </div>
      ) : null}
    </div>
  );
}
