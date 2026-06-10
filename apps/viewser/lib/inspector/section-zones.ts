import type { ElementMapItem } from "@/lib/inspector/types";

/**
 * Sektionszoner ur en element-karta.
 *
 * Porterad från sajtmaskins sectionAnalyzer (enbart element-map-delen —
 * kodanalys-halvan behövs inte här eftersom våra sektioner alltid kommer
 * från den rendrade previewn). Zonerna driver placeringsläget i
 * förhandsvisningen: hovra → närmaste insättningspunkt (linje) visas,
 * klick → vald placering. Etiketterna är operatörstext på svenska.
 */

type SectionKind =
  | "hero"
  | "features"
  | "pricing"
  | "testimonials"
  | "cta"
  | "footer"
  | "header"
  | "content"
  | "form"
  | "gallery"
  | "faq"
  | "contact"
  | "about"
  | "team"
  | "stats";

const SECTION_LABELS: Record<SectionKind, string> = {
  hero: "Hero",
  header: "Sidhuvud",
  features: "Tjänster",
  pricing: "Priser",
  testimonials: "Omdömen",
  cta: "Call-to-action",
  faq: "FAQ",
  contact: "Kontakt",
  about: "Om oss",
  team: "Team",
  stats: "Statistik",
  gallery: "Galleri",
  form: "Formulär",
  footer: "Sidfot",
  content: "Innehåll",
};

export type SectionZone = {
  id: string;
  label: string;
  type: SectionKind;
  /** Övre kant i procent av viewporten. */
  top: number;
  /** Nedre kant i procent av viewporten. */
  bottom: number;
  height: number;
};

export type InsertionPoint = {
  /** Grovposition: "top" | "bottom" | "after-<sektionstyp>". */
  placement: string;
  /** Operatörsetikett, t.ex. "Efter Omdömen". */
  label: string;
  /** Var insättningslinjen ritas, i procent av viewporten. */
  lineYPercent: number;
  anchorSection?: {
    id: string;
    label: string;
    type: string;
    top: number;
    bottom: number;
  };
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function inferSectionKind(element: ElementMapItem): SectionKind {
  const haystack = [
    element.tag,
    element.id || "",
    element.className || "",
    element.selector || "",
    element.text || "",
  ]
    .join(" ")
    .toLowerCase();

  if (/(^|\s)(header|navbar|navigation|topbar|nav)(\s|$)/.test(haystack))
    return "header";
  if (/(^|\s)(hero|banner|jumbotron|landing)(\s|$)/.test(haystack))
    return "hero";
  if (/(^|\s)(feature|benefit|service|capabilit|tjänst)(\s|$)/.test(haystack))
    return "features";
  if (/(^|\s)(pricing|price|plan|tier|subscription|pris)(\s|$)/.test(haystack))
    return "pricing";
  if (/(^|\s)(testimonial|review|feedback|quote|omdöme)(\s|$)/.test(haystack))
    return "testimonials";
  if (
    /(^|\s)(cta|call.?to.?action|get.?started|ready.?to)(\s|$)/.test(haystack)
  )
    return "cta";
  if (/(^|\s)(faq|accordion|question|fråg)(\s|$)/.test(haystack)) return "faq";
  if (/(^|\s)(contact|get.?in.?touch|reach.?us|kontakt)(\s|$)/.test(haystack))
    return "contact";
  if (/(^|\s)(about|mission|story|company|om.?oss)(\s|$)/.test(haystack))
    return "about";
  if (/(^|\s)(team|member|staff|employee)(\s|$)/.test(haystack)) return "team";
  if (/(^|\s)(stat|metric|number|achievement)(\s|$)/.test(haystack))
    return "stats";
  if (/(^|\s)(gallery|portfolio|showcase|project|galleri)(\s|$)/.test(haystack))
    return "gallery";
  if (/(^|\s)(form|newsletter|subscribe|signup|formulär)(\s|$)/.test(haystack))
    return "form";
  if (
    element.tag.toLowerCase() === "footer" ||
    /(^|\s)(footer|copyright|sidfot)(\s|$)/.test(haystack)
  ) {
    return "footer";
  }
  return "content";
}

/**
 * Plocka ut vertikala sektionszoner ur element-kartan: breda (≥45 % av
 * viewporten), någorlunda höga (≥8 %) section/main/header/footer/article/
 * div-element, sorterade uppifrån och ned och sammanslagna när de
 * överlappar. Max 10 zoner — fler blir bara brus i overlayn.
 */
export function extractSectionZones(
  elementMap: ElementMapItem[],
): SectionZone[] {
  const candidateTags = new Set([
    "section",
    "main",
    "header",
    "footer",
    "article",
    "div",
  ]);
  const candidates = elementMap
    .filter((element) => {
      const tag = element.tag?.toLowerCase?.() || "";
      if (!candidateTags.has(tag)) return false;
      const width = clampPercent(element.vpPercent.w);
      const height = clampPercent(element.vpPercent.h);
      return width >= 45 && height >= 8;
    })
    .map((element, index) => {
      const type = inferSectionKind(element);
      const top = clampPercent(element.vpPercent.y);
      const bottom = clampPercent(element.vpPercent.y + element.vpPercent.h);
      return {
        id: `zone-${index}-${type}`,
        type,
        label: SECTION_LABELS[type],
        top,
        bottom,
        height: Math.max(0, bottom - top),
      } satisfies SectionZone;
    })
    .filter((zone) => zone.height >= 6)
    .sort((a, b) => a.top - b.top || b.height - a.height);

  if (candidates.length === 0) return [];

  const merged: SectionZone[] = [];
  for (const candidate of candidates) {
    const last = merged[merged.length - 1];
    if (!last) {
      merged.push(candidate);
      continue;
    }

    const overlaps = candidate.top <= last.bottom - 3;
    const veryClose = Math.abs(candidate.top - last.top) <= 2;
    if (overlaps || veryClose) {
      const nextTop = Math.min(last.top, candidate.top);
      const nextBottom = Math.max(last.bottom, candidate.bottom);
      const shouldReplaceIdentity =
        candidate.height > last.height ||
        (last.type === "content" && candidate.type !== "content");
      merged[merged.length - 1] = {
        id: shouldReplaceIdentity ? candidate.id : last.id,
        type: shouldReplaceIdentity ? candidate.type : last.type,
        label: shouldReplaceIdentity ? candidate.label : last.label,
        top: nextTop,
        bottom: nextBottom,
        height: Math.max(0, nextBottom - nextTop),
      };
      continue;
    }
    merged.push(candidate);
  }

  return merged.slice(0, 10);
}

/**
 * Närmaste insättningspunkt för en hovrad/klickad y-position. Utan zoner
 * faller vi till topp/botten (samma grovpositioner som backendens
 * section_add-router förstår idag).
 */
export function nearestInsertionPoint(
  yPercent: number,
  zones: SectionZone[],
): InsertionPoint {
  const y = clampPercent(yPercent);

  if (zones.length === 0) {
    if (y <= 50) {
      return { placement: "top", label: "Längst upp", lineYPercent: 0 };
    }
    return { placement: "bottom", label: "Längst ner", lineYPercent: 100 };
  }

  const points: InsertionPoint[] = [
    { placement: "top", label: "Längst upp", lineYPercent: 0 },
    ...zones.map((zone) => {
      return {
        placement: `after-${zone.type}`,
        label: `Efter ${zone.label}`,
        lineYPercent: clampPercent(zone.bottom),
        anchorSection: {
          id: zone.id,
          label: zone.label,
          type: zone.type,
          top: zone.top,
          bottom: zone.bottom,
        },
      } satisfies InsertionPoint;
    }),
    { placement: "bottom", label: "Längst ner", lineYPercent: 100 },
  ];

  let best = points[0];
  let bestDistance = Math.abs(y - best.lineYPercent);
  for (let i = 1; i < points.length; i += 1) {
    const candidate = points[i];
    const distance = Math.abs(y - candidate.lineYPercent);
    if (distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }

  return best;
}
