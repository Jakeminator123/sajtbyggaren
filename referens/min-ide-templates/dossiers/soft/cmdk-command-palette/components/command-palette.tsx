"use client";

import { Command } from "cmdk";
import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";

export interface CommandItem {
  label: string;
  keywords?: string[];
  shortcut?: string[];
  onSelect: () => void;
  trailing?: ReactNode;
}

export interface CommandGroup {
  heading: string;
  items: CommandItem[];
}

export interface CommandPaletteProps {
  groups: CommandGroup[];
  placeholder?: string;
  emptyMessage?: string;
  /** Receives a setter that opens the palette programmatically. */
  openSignalRef?: MutableRefObject<(() => void) | null>;
  /** Disable the global cmd/ctrl+K shortcut. Defaults to false. */
  disableShortcut?: boolean;
}

let globalListenerCount = 0;

export function CommandPalette({
  groups,
  placeholder = "Type a command or search…",
  emptyMessage = "No results found.",
  openSignalRef,
  disableShortcut = false,
}: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const triggerSourceRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const openPalette = useCallback(() => {
    triggerSourceRef.current = (document.activeElement as HTMLElement) ?? null;
    setOpen(true);
  }, []);

  useImperativeHandle(openSignalRef, () => openPalette, [openPalette]);

  useEffect(() => {
    if (disableShortcut) return;
    globalListenerCount += 1;
    if (globalListenerCount > 1 && process.env.NODE_ENV !== "production") {
      console.warn(
        "[command-palette] more than one CommandPalette is mounted — global cmd+K will fire on each instance.",
      );
    }
    const handler = (event: KeyboardEvent) => {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (!isShortcut) return;
      event.preventDefault();
      setOpen((prev) => !prev);
    };
    window.addEventListener("keydown", handler);
    return () => {
      globalListenerCount -= 1;
      window.removeEventListener("keydown", handler);
    };
  }, [disableShortcut]);

  useEffect(() => {
    if (open) return;
    const source = triggerSourceRef.current;
    if (source && typeof source.focus === "function") {
      source.focus();
    }
  }, [open]);

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      ref={dialogRef}
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 motion-safe:animate-in motion-safe:fade-in-0 sm:pt-[15vh]"
    >
      <div
        role="presentation"
        onClick={() => setOpen(false)}
        className="absolute inset-0"
      />
      <div className="relative w-full max-w-xl rounded-xl border bg-popover text-popover-foreground shadow-2xl motion-safe:animate-in motion-safe:zoom-in-95">
        <Command shouldFilter className="flex flex-col overflow-hidden rounded-xl">
          <Command.Input
            placeholder={placeholder}
            className="w-full border-b bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
          <Command.List className="max-h-[60vh] overflow-y-auto p-2">
            <Command.Empty className="px-3 py-8 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </Command.Empty>
            {groups.map((group) => (
              <Command.Group
                key={group.heading}
                heading={group.heading}
                className="mb-2 last:mb-0 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground"
              >
                {group.items.map((item) => (
                  <Command.Item
                    key={`${group.heading}::${item.label}`}
                    value={[item.label, ...(item.keywords ?? [])].join(" ")}
                    onSelect={() => {
                      setOpen(false);
                      item.onSelect();
                    }}
                    className="flex cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2 text-sm aria-selected:bg-accent aria-selected:text-accent-foreground"
                  >
                    <span className="truncate">{item.label}</span>
                    <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
                      {item.trailing}
                      {item.shortcut?.map((key) => (
                        <kbd
                          key={key}
                          className="rounded border bg-muted px-1.5 py-0.5 font-sans text-[10px] uppercase"
                        >
                          {key}
                        </kbd>
                      ))}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </div>
    </Command.Dialog>
  );
}
