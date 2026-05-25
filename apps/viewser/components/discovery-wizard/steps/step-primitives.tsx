"use client";

import { ChevronDown, Info } from "lucide-react";
import { useCallback, useId, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/**
 * Återanvändbara UI-primitiver för wizard-stegen. Hålls i en egen fil
 * så att varje step-komponent (`company-step.tsx`, `content-step.tsx`,
 * ...) inte behöver duplicera tailwind-klasser för chip / fält-label /
 * litet rad-redigerare.
 */

export function FieldLabel({
  children,
  optional,
  help,
  htmlFor,
}: {
  children: React.ReactNode;
  optional?: boolean;
  /** Optional secondary text. Renders as a click-to-expand
   *  CollapsibleHelp next to the label so the field UI stays
   *  minimal by default. */
  help?: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <Label
      htmlFor={htmlFor}
      className="mb-1.5 flex items-center gap-1.5 text-[12px] font-medium text-foreground/85"
    >
      <span className="inline-flex items-center gap-1.5">
        {children}
        {optional ? (
          <span className="text-[10px] font-normal text-muted-foreground/70">valfritt</span>
        ) : null}
      </span>
      {help ? <InlineHelpButton>{help}</InlineHelpButton> : null}
    </Label>
  );
}

export function HelperText({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-[11px] text-muted-foreground/70">{children}</p>;
}

/**
 * CollapsibleHelp — used by `FieldLabel`'s `help` prop and by
 * sections that want a discrete "i"-icon to reveal optional
 * explanatory text without consuming layout space by default.
 *
 * The toggle is rendered inside a `<button>` (not nested inside the
 * `<label>` itself, which would forward clicks to the field).
 * Pattern: `aria-expanded` on the trigger + `aria-controls` to the
 * panel. The panel uses `role="note"` so screen readers anmäler den
 * som tilläggsinformation, inte ett nytt formulärfält.
 */
function InlineHelpButton({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <span className="contents">
      <button
        type="button"
        onClick={(event) => {
          // Den här knappen lever inuti `<label>` så ett klick
          // skulle annars vandra upp till labeln och flytta fokus
          // till associerade fältet — vi vill bara toggla helpern.
          event.preventDefault();
          event.stopPropagation();
          setOpen((prev) => !prev);
        }}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Dölj hjälp" : "Visa hjälp"}
        className="text-muted-foreground/60 hover:text-foreground/80 focus-visible:ring-ring/40 inline-flex h-4 w-4 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <Info className="h-3 w-3" aria-hidden />
      </button>
      {/* Panelen renderas alltid (hidden när stängd) så `aria-controls`
          alltid pekar på ett element som finns i DOM — bättre AT-stöd
          än conditional rendering. */}
      <span
        id={panelId}
        role="note"
        hidden={!open}
        className="text-muted-foreground/80 block w-full pt-1 pl-0 text-[11px] leading-snug font-normal sm:basis-full"
      >
        {children}
      </span>
    </span>
  );
}

/**
 * CollapsibleHelp — fristående variant av samma mönster, för sektioner
 * och rubriker som vill expose en hjälptext utan att vara inuti ett
 * `<label>`. Visar info-ikonen + en kort visuell label, och expanderar
 * texten under raden vid klick.
 */
export function CollapsibleHelp({
  children,
  triggerLabel,
}: {
  children: React.ReactNode;
  triggerLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="mt-1 inline-flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls={panelId}
        className="text-muted-foreground/70 hover:text-foreground/85 focus-visible:ring-ring/40 inline-flex items-center gap-1 rounded-full text-[10.5px] focus-visible:ring-2 focus-visible:outline-none"
      >
        <Info className="h-3 w-3" aria-hidden />
        <span>{triggerLabel ?? (open ? "Dölj förklaring" : "Visa förklaring")}</span>
      </button>
      <p
        id={panelId}
        role="note"
        hidden={!open}
        className="text-muted-foreground/80 mt-1 w-full text-[11px] leading-snug"
      >
        {children}
      </p>
    </div>
  );
}

/**
 * MetadataPanel — collapsible wrapper for "transparency" blocks
 * (FoundationSummary, ContextChips, DirectivesPreview etc.) that
 * default to hidden so the wizard chrome stays clean.
 *
 * Skiljer sig från `AdvancedDisclosure` på två sätt:
 *   1. Tänkt för dekorativa/transparens-block, inte fält som
 *      operatören ska fylla i.
 *   2. Saknar fält-räknare (count/activeCount) — barnen är
 *      en visualisering, inte en lista av fält att aktivera.
 */
export function MetadataPanel({
  title,
  subtitle,
  children,
  defaultOpen = false,
  id,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  id?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = id ?? "metadata-panel";
  return (
    <div className="border-border/40 bg-muted/10 rounded-2xl border">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="hover:bg-muted/30 flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-2.5 text-left transition-colors"
        aria-expanded={open}
        aria-controls={panelId}
      >
        <div className="flex min-w-0 flex-col">
          <span className="text-[12px] font-medium text-foreground/85">{title}</span>
          {subtitle ? (
            <span className="text-muted-foreground/70 mt-0.5 text-[10.5px] leading-snug">
              {subtitle}
            </span>
          ) : null}
        </div>
        <ChevronDown
          className={cn(
            "text-muted-foreground h-4 w-4 transition-transform",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {/* Panelen är alltid mountad (hidden när stängd) så aria-controls
          alltid pekar på ett element i DOM. För dyra transparency-block
          (t.ex. FoundationSummary) är detta acceptabelt eftersom de är
          rena beräknade vyer av befintlig state. */}
      <div
        id={panelId}
        role="region"
        aria-label={title}
        hidden={!open}
        className="border-border/40 border-t px-4 pt-3 pb-4"
      >
        {children}
      </div>
    </div>
  );
}

export type ChipProps = {
  label: string;
  selected: boolean;
  onToggle: () => void;
  size?: "sm" | "md";
  title?: string;
};

export function Chip({
  label,
  selected,
  onToggle,
  size = "md",
  title,
}: ChipProps) {
  const padding = size === "sm" ? "px-2.5 py-1" : "px-3 py-1.5";
  const text = size === "sm" ? "text-[11px]" : "text-[12px]";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      title={title}
      className={`${padding} ${text} rounded-full border transition-colors ${
        selected
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-card text-foreground/80 hover:border-foreground/40 hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}

export function ChipRow({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap gap-1.5">{children}</div>;
}

/**
 * Inline tag input — användaren skriver fritext + Enter, taggen läggs
 * till listan. Klick på taggen tar bort den. Används av USP-fält,
 * målgrupp-tags, etc.
 */
export type TagListInputProps = {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  maxItems?: number;
};

export function TagListInput({
  values,
  onChange,
  placeholder,
  maxItems,
}: TagListInputProps) {
  const handleKey = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key !== "Enter" && event.key !== ",") return;
      event.preventDefault();
      const raw = event.currentTarget.value.trim();
      if (!raw) return;
      if (maxItems && values.length >= maxItems) return;
      if (values.includes(raw)) {
        event.currentTarget.value = "";
        return;
      }
      onChange([...values, raw]);
      event.currentTarget.value = "";
    },
    [maxItems, onChange, values],
  );
  return (
    <div className="flex flex-col gap-2">
      {values.length > 0 ? (
        <ChipRow>
          {values.map((value) => (
            <Chip
              key={value}
              label={`${value} ×`}
              selected
              size="sm"
              onToggle={() => onChange(values.filter((v) => v !== value))}
            />
          ))}
        </ChipRow>
      ) : null}
      <Input
        type="text"
        placeholder={placeholder ?? "Skriv och tryck Enter…"}
        onKeyDown={handleKey}
        className="h-9 text-[13px]"
      />
    </div>
  );
}

export function SectionHeader({
  children,
  help,
}: {
  children: React.ReactNode;
  /** Optional secondary text. Renders next to the section header as
   *  a click-to-expand info-icon so the default rendering stays
   *  minimal. */
  help?: React.ReactNode;
}) {
  return (
    <div className="mb-3 mt-4 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground/70 first:mt-0">
      <span>{children}</span>
      {help ? <InlineHelpButton>{help}</InlineHelpButton> : null}
    </div>
  );
}

export function FieldStack({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-4">{children}</div>;
}

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  optional,
  helper,
  helperInline,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  optional?: boolean;
  helper?: string;
  /** When true, render `helper` as visible HelperText under the field
   *  instead of behind a CollapsibleHelp info-icon. Use sparingly — only
   *  for instructions critical enough to halt the user (e.g. URL-scrape
   *  status text). */
  helperInline?: boolean;
  type?: "text" | "url" | "tel" | "email";
}) {
  return (
    <div>
      <FieldLabel optional={optional} help={helper && !helperInline ? helper : undefined}>
        {label}
      </FieldLabel>
      <Input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-9 text-[13px]"
      />
      {helper && helperInline ? <HelperText>{helper}</HelperText> : null}
    </div>
  );
}

export function TextareaField({
  label,
  value,
  onChange,
  placeholder,
  optional,
  helper,
  helperInline,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  optional?: boolean;
  helper?: string;
  /** Se TextField.helperInline — default false så hjälpen läggs bakom
   *  info-ikonen för minimalistisk default-vy. */
  helperInline?: boolean;
  rows?: number;
}) {
  return (
    <div>
      <FieldLabel optional={optional} help={helper && !helperInline ? helper : undefined}>
        {label}
      </FieldLabel>
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="text-[13px]"
      />
      {helper && helperInline ? <HelperText>{helper}</HelperText> : null}
    </div>
  );
}

/**
 * Progressive-disclosure-block för "advanced" wizard-val.
 *
 * Mönster (efter `DirectivesPreview`): kollapsbar knapp med chevron +
 * räknare-badge så operatören ser HUR MÅNGA dolda val som finns
 * innan hen klickar. Default kollapsad så essentials-flödet är
 * minimalt; power-users öppnar för fine-tuning.
 *
 * UX-regler:
 *   - Knappen ska beskriva vad som finns DÄRINNE ("Fler designval",
 *     inte bara "Visa fler"). Default-label är "Visa fler val".
 *   - ``count`` används som badge så operatören ser om något är dolt
 *     överhuvudtaget (count=0 → ingen badge). När count > 0 visas
 *     "(N val)" diskret bredvid labeln.
 *   - ``activeCount`` är antal val DÄRINNE som faktiskt är ifyllda
 *     — t.ex. när operatören har satt en hex-färg eller laddat upp
 *     en favicon. Då visar vi "(N val · M ifyllda)" så hen vet att
 *     gå tillbaka och granska.
 *   - Hela blocket har samma rundade kort-look som
 *     ``DirectivesPreview`` så det inte sticker ut i stegen.
 *
 * Tillgänglighet: ``aria-expanded`` + ``aria-controls`` pekar mot
 * panelen. Panelen får ``role="region"`` så skärmläsare anmäler
 * den när den öppnas.
 */
export function AdvancedDisclosure({
  label = "Visa fler val",
  hint,
  count,
  activeCount,
  defaultOpen = false,
  children,
  id,
}: {
  label?: string;
  hint?: string;
  count?: number;
  activeCount?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
  id?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = id ?? "advanced-disclosure-panel";
  const showActiveBadge =
    typeof activeCount === "number" && activeCount > 0;
  return (
    <div className="border-border/40 bg-muted/10 rounded-2xl border">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="hover:bg-muted/30 flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-2.5 text-left transition-colors"
        aria-expanded={open}
        aria-controls={panelId}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-[12px] font-medium text-foreground/85">{label}</span>
          {typeof count === "number" && count > 0 ? (
            <span className="text-muted-foreground text-[11px]">
              {showActiveBadge
                ? `(${count} val · ${activeCount} ifyllda)`
                : `(${count} val)`}
            </span>
          ) : null}
          {showActiveBadge && (typeof count !== "number" || count === 0) ? (
            <span className="rounded-full bg-foreground/10 px-1.5 py-0.5 text-[10px] font-medium text-foreground">
              {activeCount} ifyllda
            </span>
          ) : null}
        </div>
        <ChevronDown
          className={cn(
            "text-muted-foreground h-4 w-4 transition-transform",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <div
          id={panelId}
          role="region"
          className="border-border/40 space-y-4 border-t px-4 pt-4 pb-4"
        >
          {hint ? (
            <p className="text-muted-foreground text-[11px]">{hint}</p>
          ) : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}
