import type { ContentBranch, WizardCategoryId } from "./wizard-constants";
import { resolveContentBranch, WIZARD_CATEGORIES } from "./wizard-constants";

export type discoveryOption = {
  id: WizardCategoryId;
  label: string;
  contentBranch: ContentBranch;
  supportStatus: "active" | "fallback" | "planned" | "disabled";
  defaultVariantId: string;
  targetScaffoldLabel: string;
  fallbackLabel?: string;
  /**
   * Taxonomins sidförslag per kategori (svenska sidetiketter, t.ex.
   * "Startsida / Hero") från /api/discovery-options. Saknas i TS-cache-
   * fallbacken; konsumenter behåller wizard-constants-listorna som fallback.
   */
  recommendedPages?: readonly string[];
  operatorNotes?: string;
};

const FALLBACK_DISCOVERY_OPTIONS: discoveryOption[] = WIZARD_CATEGORIES.map(
  (category) => ({
    id: category.id,
    label: category.label,
    contentBranch: resolveContentBranch([category.id]),
    supportStatus: "fallback",
    defaultVariantId: category.defaultVariantId,
    targetScaffoldLabel: category.scaffoldHint,
  }),
);

export function fallbackDiscoveryOptions(): discoveryOption[] {
  return [...FALLBACK_DISCOVERY_OPTIONS];
}

export function discoveryOptionsMap(
  options: readonly discoveryOption[],
): Map<WizardCategoryId, discoveryOption> {
  return new Map(options.map((option) => [option.id, option]));
}

export function resolveContentBranchFromOptions(
  siteType: readonly WizardCategoryId[],
  options: readonly discoveryOption[],
  businessFamilyBranch?: ContentBranch,
): ContentBranch {
  const byId = discoveryOptionsMap(options);
  const orderedBranches = siteType
    .map((id) => byId.get(id)?.contentBranch)
    .filter((branch): branch is ContentBranch => Boolean(branch));

  if (orderedBranches.includes("ecommerce")) return "ecommerce";
  if (orderedBranches.includes("restaurant")) return "restaurant";
  if (orderedBranches.includes("salon")) return "salon";
  if (orderedBranches.includes("portfolio")) return "portfolio";
  if (orderedBranches.includes("hotel")) return "hotel";
  if (orderedBranches.includes("construction")) return "construction";
  if (orderedBranches.includes("education")) return "education";
  if (orderedBranches.includes("event")) return "event";
  if (orderedBranches.includes("legal")) return "legal";
  if (orderedBranches.includes("realestate")) return "realestate";
  if (orderedBranches.includes("nonprofit")) return "nonprofit";
  if (orderedBranches.includes("consulting")) return "consulting";
  if (orderedBranches.includes("business")) return "business";
  if (orderedBranches.includes("minimal")) return "minimal";
  // W2 i scout-review 2026-05-24: när siteType är tom (operatören
  // har valt familj men ännu inte sub-kategori), respektera familj-
  // valets branch så content-stegets UI matchar familj-scaffolden
  // (t.ex. ecommerce visar produktfält, inte general business).
  if (businessFamilyBranch) return businessFamilyBranch;
  return "business";
}

export function validateDiscoveryCategoryIds(
  siteType: readonly WizardCategoryId[],
  options: readonly discoveryOption[],
): boolean {
  const known = new Set(options.map((option) => option.id));
  return siteType.every((id) => known.has(id));
}

export function resolveScaffoldHintFromOptions(
  siteType: readonly WizardCategoryId[],
  options: readonly discoveryOption[],
): string {
  const branch = resolveContentBranchFromOptions(siteType, options);
  const ecommerceSelected = branch === "ecommerce";
  return ecommerceSelected ? "ecommerce-lite" : "local-service-business";
}
