"use client";

import { useCallback } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

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
