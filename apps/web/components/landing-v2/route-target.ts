import {
  isTemplateEntryMode,
  type BuildIntent,
  type BuildMethod,
} from "@/lib/builder/build-intent";

export type LandingRouteTarget = {
  buildMethod: BuildMethod;
  buildIntent: BuildIntent;
  source?: string;
};

export function resolveLandingRouteTarget(categoryId: string | null): LandingRouteTarget {
  if (isTemplateEntryMode(categoryId)) {
    return { buildMethod: "category", buildIntent: "template" };
  }
  switch (categoryId) {
    case "analyserad":
      return { buildMethod: "wizard", buildIntent: "website" };
    case "audit":
      return { buildMethod: "audit", buildIntent: "website", source: "audit" };
    case "fritext":
    default:
      return { buildMethod: "freeform", buildIntent: "website" };
  }
}
