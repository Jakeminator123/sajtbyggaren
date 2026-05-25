"use client";

import {
  Brush,
  CircleCheck,
  Loader2,
  RotateCcw,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  broadcastTokenBundle,
  broadcastTokenReset,
  type TokenId,
} from "@/lib/runtime-tokens";
import { PRIMARY_INTERACTIONS, SECONDARY_INTERACTIONS } from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";

/**
 * VariantsTab — Site Inspectors live-switch-presets för scaffold-variants.
 *
 * Två lager:
 *
 *   1. LIVE PREVIEW — varje variant-kort har ett mini-preview-block som
 *      renderar variantens fyra färg-tokens direkt i tabben. Klick på
 *      ett kort triggar ``broadcastTokenBundle`` så preview-iframen
 *      (same-origin lokalt) byter färgschema på en gång utan rebuild.
 *
 *   2. COMMIT — "Använd denna variant"-knappen skickar en deterministisk
 *      follow-up-prompt genom samma pipeline som variant-picker-dialog
 *      använder. briefModel uppdaterar Project Input, planeraren väljer
 *      variantId, nästa build lockar in valet permanent.
 *
 * Variant-data kommer från ``/api/discovery-options``s additiva
 * ``availableVariants``-fält så vi slipper en extra fetch per variant.
 */

type VariantSummary = {
  id: string;
  label: string;
  description: string;
  tokens: Record<TokenId, string>;
  tone: {
    vibe: string[];
  };
};

type DiscoveryOption = {
  id: string;
  label: string;
  supportStatus: "active" | "fallback" | "planned" | "disabled";
  defaultVariantId: string;
  targetScaffoldLabel: string;
  fallbackLabel?: string;
  runtimeScaffoldId?: string;
  availableVariants?: VariantSummary[];
};

type DiscoveryOptionsResponse = {
  options?: DiscoveryOption[];
  error?: string;
};

export interface VariantsTabProps {
  bundle: RunArtefactBundle;
  isBuilding: boolean;
  pendingPrompt: string | null;
  onPrompt: (prompt: string) => void | Promise<void>;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function buildVariantSwitchPrompt(
  variant: VariantSummary,
  scaffoldId: string,
): string {
  const vibe = variant.tone.vibe.slice(0, 4).join(", ");
  const vibeHint = vibe ? ` (känsla: ${vibe})` : "";
  return `Byt designvariant till "${variant.label}"${vibeHint}. Använd variantId: ${variant.id} för scaffolden ${scaffoldId}. Behåll allt innehåll och struktur — anpassa endast färgschema, typografi och visuell ton till den nya varianten.`;
}

export function VariantsTab({
  bundle,
  isBuilding,
  pendingPrompt,
  onPrompt,
}: VariantsTabProps) {
  const [options, setOptions] = useState<DiscoveryOption[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [previewVariantId, setPreviewVariantId] = useState<string | null>(null);

  const plan = bundle.sitePlan ?? {};
  const scaffoldId = asString((plan as Record<string, unknown>).scaffoldId);
  const currentVariantId = asString(
    (plan as Record<string, unknown>).variantId,
  );
  const brief = bundle.siteBrief ?? {};
  const companyName = asString((brief as Record<string, unknown>).companyName);

  // Hämta discovery-options en gång per tab-öppning. Listan är konstant
  // per session (genereras från governance-policies + on-disk variants)
  // så cache-policyn är trivial.
  useEffect(() => {
    if (options !== null) return;
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/discovery-options");
        const payload = (await response.json()) as DiscoveryOptionsResponse;
        if (cancelled) return;
        if (!response.ok || !payload.options) {
          throw new Error(payload.error ?? "Kunde inte ladda variants.");
        }
        setOptions(payload.options);
      } catch (caught) {
        if (cancelled) return;
        setLoadError(
          caught instanceof Error ? caught.message : "Okänt fel.",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [options]);

  // Hitta matchande discovery-option för aktuell scaffold. Flera kategorier
  // kan dela samma runtime-scaffold (fallback-mappning), så vi prioriterar
  // i ordningen: exakt match på runtimeScaffoldId → första aktiva → första
  // fallbackable. Returnerar null om scaffoldId saknas i sitePlan.
  const activeOption = useMemo<DiscoveryOption | null>(() => {
    if (!options || !scaffoldId) return null;
    const matches = options.filter(
      (option) => option.runtimeScaffoldId === scaffoldId,
    );
    if (matches.length === 0) return null;
    const active = matches.find((option) => option.supportStatus === "active");
    return active ?? matches[0];
  }, [options, scaffoldId]);

  // useMemo så ?? []-fallbacken inte allokerar en ny tom array varje
  // render — React-hooks/exhaustive-deps-pluginen skulle annars tro att
  // dependency-arrayen ändrats vid varje render i nedanstående memos.
  const variants = useMemo<VariantSummary[]>(
    () => activeOption?.availableVariants ?? [],
    [activeOption],
  );

  const sortedVariants = useMemo(() => {
    // Visa nuvarande variant först om den finns i listan, annars
    // alfabetiskt på label (API:t sorterar redan så detta är defensivt).
    if (!currentVariantId) return variants;
    const current = variants.find((variant) => variant.id === currentVariantId);
    if (!current) return variants;
    const rest = variants.filter((variant) => variant.id !== currentVariantId);
    return [current, ...rest];
  }, [variants, currentVariantId]);

  // Auto-reset preview när tabben stängs (component unmount) så
  // iframen inte fastnar på en hover-preview användaren har "lämnat".
  useEffect(() => {
    return () => {
      if (previewVariantId && previewVariantId !== currentVariantId) {
        broadcastTokenReset();
      }
    };
  }, [previewVariantId, currentVariantId]);

  const handlePreview = useCallback(
    (variant: VariantSummary) => {
      if (variant.id === currentVariantId) {
        broadcastTokenReset();
        setPreviewVariantId(null);
        return;
      }
      broadcastTokenBundle(variant.tokens);
      setPreviewVariantId(variant.id);
    },
    [currentVariantId],
  );

  const handleReset = useCallback(() => {
    broadcastTokenReset();
    setPreviewVariantId(null);
  }, []);

  const previewedVariant = useMemo<VariantSummary | null>(() => {
    if (!previewVariantId) return null;
    return variants.find((variant) => variant.id === previewVariantId) ?? null;
  }, [previewVariantId, variants]);

  const commitPrompt = useMemo(() => {
    if (!previewedVariant || !scaffoldId) return "";
    return buildVariantSwitchPrompt(previewedVariant, scaffoldId);
  }, [previewedVariant, scaffoldId]);

  const handleCommit = useCallback(() => {
    if (!commitPrompt || isBuilding) return;
    void onPrompt(commitPrompt);
  }, [commitPrompt, isBuilding, onPrompt]);

  const isPending = pendingPrompt === commitPrompt && pendingPrompt !== null;

  /* ── Render states ───────────────────────────────────────────── */

  if (loadError) {
    return (
      <p
        role="alert"
        className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
      >
        {loadError}
      </p>
    );
  }

  if (options === null) {
    return (
      <div className="text-muted-foreground flex h-32 items-center justify-center gap-2 text-[12px]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Laddar variants…
      </div>
    );
  }

  if (!scaffoldId) {
    return (
      <EmptyState
        title="Ingen aktiv scaffold"
        body="Bygg en sajt först — sedan kan du byta variant här."
      />
    );
  }

  if (!activeOption) {
    return (
      <EmptyState
        title="Okänd scaffold"
        body={`Scaffold "${scaffoldId}" matchar ingen aktiv discovery-kategori. Variants kan inte listas tills den registreras i governance-taxonomin.`}
      />
    );
  }

  if (sortedVariants.length === 0) {
    return (
      <EmptyState
        title="Inga variants tillgängliga"
        body={`"${activeOption.targetScaffoldLabel}" har inga registrerade variants ännu. Lägg till JSON-filer under packages/generation/orchestration/scaffolds/${scaffoldId}/variants/ för att de ska dyka upp här.`}
      />
    );
  }

  if (sortedVariants.length === 1) {
    return (
      <EmptyState
        title="Bara en variant ännu"
        body={`"${activeOption.targetScaffoldLabel}" har bara varianten "${sortedVariants[0].label}" registrerad. Snabb-byt blir tillgängligt när det finns minst två varianter.`}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="border-border/40 bg-foreground/[0.02] flex items-start gap-2.5 rounded-lg border p-3">
        <Brush className="text-foreground/70 mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="text-foreground/85 flex-1 text-[12px] leading-relaxed">
          Hover/klick på en variant förhandsvisar färgschemat direkt i
          preview:n{companyName ? ` för ${companyName}` : ""} utan att bygga om.
          Klicka <strong>Använd denna variant</strong> för att committa via
          ett nytt bygge.
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {sortedVariants.map((variant) => (
          <VariantCard
            key={variant.id}
            variant={variant}
            isCurrent={variant.id === currentVariantId}
            isPreviewed={variant.id === previewVariantId}
            disabled={isBuilding || isPending}
            onSelect={() => handlePreview(variant)}
          />
        ))}
      </div>

      <div className="border-border/60 flex flex-col gap-2 border-t pt-4">
        <button
          type="button"
          onClick={handleCommit}
          disabled={!previewedVariant || isBuilding || isPending}
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
          ) : previewedVariant ? (
            <>
              <Wand2 className="h-3.5 w-3.5" />
              Använd &ldquo;{previewedVariant.label}&rdquo;
            </>
          ) : (
            <>
              <Wand2 className="h-3.5 w-3.5" />
              Välj en variant att applicera
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleReset}
          disabled={!previewedVariant}
          className={cn(
            "text-muted-foreground hover:text-foreground border-border/60 hover:border-foreground/40 hover:bg-muted/40",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            "inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-[11.5px] font-medium transition-colors disabled:opacity-40",
            SECONDARY_INTERACTIONS,
          )}
        >
          <RotateCcw className="h-3 w-3" />
          Återställ preview
        </button>
      </div>
    </div>
  );
}

/* ── Variant card ──────────────────────────────────────────────── */

function VariantCard({
  variant,
  isCurrent,
  isPreviewed,
  disabled,
  onSelect,
}: {
  variant: VariantSummary;
  isCurrent: boolean;
  isPreviewed: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  const swatches: Array<{ label: string; value: string }> = [
    { label: "background", value: variant.tokens.background },
    { label: "foreground", value: variant.tokens.foreground },
    { label: "primary", value: variant.tokens.primary },
    { label: "accent", value: variant.tokens.accent },
  ];

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      aria-pressed={isPreviewed}
      className={cn(
        "group flex flex-col gap-2.5 rounded-lg border p-2.5 text-left transition-all",
        "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
        isPreviewed
          ? "border-foreground bg-muted/60 shadow-sm"
          : isCurrent
            ? "border-foreground/40 bg-muted/30"
            : "border-border/60 hover:border-border hover:bg-muted/40",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      {/* Live mini-preview — renderar variantens fyra tokens inline. */}
      <div
        className="overflow-hidden rounded-md border"
        style={{
          background: variant.tokens.background,
          borderColor: variant.tokens.foreground + "22",
        }}
      >
        <div className="space-y-1.5 px-2.5 py-2">
          <div
            className="text-[11px] font-semibold tracking-tight"
            style={{ color: variant.tokens.foreground }}
          >
            Aa Välkommen
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="rounded-md px-1.5 py-0.5 text-[9.5px] font-medium"
              style={{
                background: variant.tokens.primary,
                color: variant.tokens.background,
              }}
            >
              Boka
            </span>
            <span
              className="rounded-full px-1.5 py-0.5 text-[9px] font-medium"
              style={{
                background: variant.tokens.accent + "22",
                color: variant.tokens.accent,
              }}
            >
              Nyhet
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-foreground truncate text-[12px] font-medium tracking-tight">
            {variant.label}
          </div>
          {variant.tone.vibe.length > 0 ? (
            <div className="text-muted-foreground mt-0.5 truncate text-[10px]">
              {variant.tone.vibe.slice(0, 3).join(" · ")}
            </div>
          ) : null}
        </div>
        {isCurrent ? (
          <span className="border-foreground/40 text-foreground/80 inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 font-mono text-[9px] tracking-wider uppercase">
            <CircleCheck className="h-2.5 w-2.5" />
            Aktiv
          </span>
        ) : isPreviewed ? (
          <span className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 font-mono text-[9px] tracking-wider uppercase dark:text-emerald-400">
            Preview
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-1" aria-hidden>
        {swatches.map((swatch) => (
          <span
            key={swatch.label}
            title={`${swatch.label} · ${swatch.value}`}
            className="border-border/40 h-3 w-3 rounded-full border"
            style={{ background: swatch.value }}
          />
        ))}
      </div>
    </button>
  );
}

/* ── Empty state ───────────────────────────────────────────────── */

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-border/40 bg-foreground/[0.02] flex flex-col items-start gap-1.5 rounded-lg border p-4">
      <div className="text-foreground text-[12.5px] font-medium tracking-tight">
        {title}
      </div>
      <p className="text-muted-foreground text-[11.5px] leading-relaxed">
        {body}
      </p>
    </div>
  );
}
