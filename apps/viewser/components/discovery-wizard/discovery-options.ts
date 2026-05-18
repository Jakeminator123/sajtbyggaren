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
