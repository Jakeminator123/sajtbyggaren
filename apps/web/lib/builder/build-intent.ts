export type BuildIntent = "template" | "website" | "app";

export type BuildMethod = "wizard" | "category" | "audit" | "freeform" | "kostnadsfri";

export type LandingEntryMode =
  | "template"
  | "kategori"
  | "mall"
  | "analyserad"
  | "audit"
  | "fritext";

const TEMPLATE_ENTRY_MODES = new Set<LandingEntryMode>(["template", "kategori", "mall"]);

export const DEFAULT_BUILD_INTENT: BuildIntent = "website";

export function normalizeBuildIntent(raw?: string | null): BuildIntent {
  const value = String(raw || "").toLowerCase();
  if (value === "template" || value === "website" || value === "app") {
    return value;
  }
  return DEFAULT_BUILD_INTENT;
}

export function normalizeBuildMethod(raw?: string | null): BuildMethod | null {
  const value = String(raw || "").toLowerCase();
  if (value === "wizard" || value === "category" || value === "audit" || value === "freeform" || value === "kostnadsfri") {
    return value;
  }
  return null;
}

const APP_SCAFFOLD_IDS = new Set(["dashboard", "app-shell"]);

export function isAppScaffold(scaffoldId: string | null | undefined): boolean {
  return Boolean(scaffoldId && APP_SCAFFOLD_IDS.has(scaffoldId));
}

export function resolveBuildIntentForMethod(
  method: BuildMethod | null | undefined,
  selected: BuildIntent,
): BuildIntent {
  if (method === "category") return "template";
  if (method === "audit" || method === "kostnadsfri") return "website";
  return selected;
}

export function resolveBuildIntentWithScaffold(
  method: BuildMethod | null | undefined,
  selected: BuildIntent,
  scaffoldMode: "off" | "auto" | "manual" | null | undefined,
  scaffoldId: string | null | undefined,
): BuildIntent {
  if (method === "category") return "template";
  if (method === "audit" || method === "kostnadsfri") return "website";
  if (selected !== "website") return selected;
  if (scaffoldMode === "manual" && isAppScaffold(scaffoldId)) return "app";
  return selected;
}

export function isTemplateEntryMode(raw?: string | null): boolean {
  const value = String(raw || "").toLowerCase() as LandingEntryMode;
  return TEMPLATE_ENTRY_MODES.has(value);
}

export function buildIntentNoun(intent: BuildIntent): string {
  if (intent === "template") return "template";
  if (intent === "app") return "app";
  return "website";
}
