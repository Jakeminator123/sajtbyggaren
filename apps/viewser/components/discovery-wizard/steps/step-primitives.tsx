"use client";

import { ChevronDown } from "lucide-react";
import { useCallback, useState } from "react";

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
}: {
  children: React.ReactNode;
  optional?: boolean;
}) {
  return (
    <Label className="mb-1.5 flex items-center gap-1.5 text-[12px] font-medium text-foreground/85">
      {children}
      {optional ? (
        <span className="text-[10px] font-normal text-muted-foreground/70">valfritt</span>
      ) : null}
    </Label>
  );
}

export function HelperText({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-[11px] text-muted-foreground/70">{children}</p>;
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

export function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 mt-4 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground/70 first:mt-0">
      {children}
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
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  optional?: boolean;
  helper?: string;
  type?: "text" | "url" | "tel" | "email";
}) {
  return (
    <div>
      <FieldLabel optional={optional}>{label}</FieldLabel>
      <Input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-9 text-[13px]"
      />
      {helper ? <HelperText>{helper}</HelperText> : null}
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
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  optional?: boolean;
  helper?: string;
  rows?: number;
}) {
  return (
    <div>
      <FieldLabel optional={optional}>{label}</FieldLabel>
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="text-[13px]"
      />
      {helper ? <HelperText>{helper}</HelperText> : null}
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
