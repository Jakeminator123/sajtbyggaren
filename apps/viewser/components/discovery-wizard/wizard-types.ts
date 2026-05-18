/**
 * Discovery wizard datamodell — `WizardAnswers` är den shape som varje
 * steg-komponent skriver mot. När wizarden är klar serialiseras den
 * via `buildDiscoveryPayload()` (se `wizard-payload.ts`) till en
 * struktur som `/api/prompt` skickar vidare till
 * `scripts/prompt_to_project_input.py --discovery <fil>`.
 *
 * Modellen är medvetet platt (inga nestade arrays av objekt på top-
 * level) så att React-state kan uppdateras med en enkel
 * `setAnswers(prev => ({ ...prev, field: value }))`-callback. Komplexa
 * grenar (produkter, meny, team, projekt) finns som arrays av
 * delobjekt — varje delobjekt har egen `id` så att vi kan rendera
 * stabila keys utan att slumpa generera.
 *
 * Ported från `Sajtmaskin_Genberg/src/components/builder/IntakeWizard.tsx`
 * `WizardAnswers`-typen, men trimmad så bara fält som faktiskt syns
 * i UI:t finns kvar. Saknade fält (avoid, imagery, goal) tas in från
 * scrape/LLM endast.
 */

import type { ContentBranch, WizardCategoryId } from "./wizard-constants";
import type { AssetRef } from "@/lib/asset-store/types";

export type WizardStepId =
  | "company"
  | "siteType"
  | "content"
  | "story"
  | "pages"
  | "assets"
  | "brand";

export const WIZARD_STEP_ORDER: WizardStepId[] = [
  "company",
  "siteType",
  "content",
  "story",
  "pages",
  "assets",
  "brand",
];

export const WIZARD_STEP_TITLES: Record<WizardStepId, string> = {
  company: "Ditt företag",
  siteType: "Kategori",
  content: "Innehåll",
  story: "Om företaget",
  pages: "Sidor och CTA",
  assets: "Bilder och logotyp",
  brand: "Ton och stil",
};

export type ProductItem = {
  id: string;
  name: string;
  price?: string;
  description?: string;
  category?: string;
  imageUrl?: string;
};

export type MenuItem = {
  id: string;
  name: string;
  price?: string;
  description?: string;
  category?: string;
};

export type ServiceItem = {
  id: string;
  name: string;
  price?: string;
  durationMinutes?: number;
  description?: string;
};

export type TeamMember = {
  id: string;
  name: string;
  role?: string;
  bio?: string;
};

export type ProjectItem = {
  id: string;
  name: string;
  client?: string;
  description?: string;
  imageUrl?: string;
};

export type WizardContact = {
  phone: string;
  email: string;
  address: string;
  openingHours: string;
};

export type WizardBrand = {
  toneTags: string[];
  designStyle: string;
  primaryColorHex: string;
  accentColorHex: string;
  wordsToAvoid: string;
};

/**
 * Operatör-uppladdade bilder. Logo + hero är skalärer (max 1 stycken
 * vardera); gallery är en lista. Varje AssetRef har redan gått genom
 * sharp-pipelinen och GPT Vision-klassificeringen i `/api/upload-asset`,
 * så `placement`, `alt` och `visionConfidence` är pre-populerade när
 * AssetsStep tar emot dem.
 */
export type WizardAssets = {
  logo: AssetRef | null;
  heroImage: AssetRef | null;
  gallery: AssetRef[];
};

/**
 * Confidence-nivå per fält när det fylldes från scrape/LLM. UI:t
 * använder den för att visa en diskret "auto-ifylld"-badge så
 * operatorn vet vilka svar som behöver granskas extra noga.
 */
export type FieldConfidence = "high" | "medium" | "low";

export type WizardAnswers = {
  /** Steg 1 — Företag */
  companyName: string;
  offer: string;
  existingSite: string;
  contact: WizardContact;

  /** Steg 2 — Kategori (multi-select chip) */
  siteType: WizardCategoryId[];

  /** Steg 3 — Innehåll (gren-beroende fält) */
  products: ProductItem[];
  menuItems: MenuItem[];
  services: ServiceItem[];
  team: TeamMember[];
  projects: ProjectItem[];
  cuisineTags: string[];
  dietaryTags: string[];
  priceTier: string;
  bookingUrl: string;
  uniqueSellingPoints: string[];

  /** Steg 4 — Story */
  aboutText: string;
  historyText: string;
  visionText: string;
  contactIntroText: string;

  /** Steg 5 — Sidor + CTA + målgrupp */
  mustHave: string[];
  primaryCta: string;
  targetAudience: string;

  /** Steg 6 — Bilder och logotyp */
  assets: WizardAssets;

  /** Steg 7 — Ton och stil */
  brand: WizardBrand;

  /** Meta — vilka fält som autifylldes (för UI-feedback) */
  scrapedFields: Partial<Record<keyof Omit<WizardAnswers, "scrapedFields">, FieldConfidence>>;
};

export function emptyWizardAnswers(): WizardAnswers {
  return {
    companyName: "",
    offer: "",
    existingSite: "",
    contact: { phone: "", email: "", address: "", openingHours: "" },
    siteType: [],
    products: [],
    menuItems: [],
    services: [],
    team: [],
    projects: [],
    cuisineTags: [],
    dietaryTags: [],
    priceTier: "",
    bookingUrl: "",
    uniqueSellingPoints: [],
    aboutText: "",
    historyText: "",
    visionText: "",
    contactIntroText: "",
    mustHave: [],
    primaryCta: "",
    targetAudience: "",
    assets: {
      logo: null,
      heroImage: null,
      gallery: [],
    },
    brand: {
      toneTags: [],
      designStyle: "",
      primaryColorHex: "",
      accentColorHex: "",
      wordsToAvoid: "",
    },
    scrapedFields: {},
  };
}

/**
 * Validering per steg. Returnerar `null` om steget får fortsätta,
 * annars ett kort meddelande som visas under "Fortsätt"-knappen.
 */
export function validateWizardStep(
  step: WizardStepId,
  answers: WizardAnswers,
  branch: ContentBranch,
): string | null {
  switch (step) {
    case "company":
      if (answers.companyName.trim().length < 2) return "Ange minst 2 tecken för företagsnamn.";
      if (answers.offer.trim().length < 3) return "Beskriv kort vad ni gör.";
      return null;
    case "siteType":
      if (answers.siteType.length === 0) return "Välj minst en kategori.";
      return null;
    case "content":
      // Innehållssteget är alltid valfritt — utan tjänster/produkter
      // kan generator-modellen ändå mocka eller fråga senare.
      void branch;
      return null;
    case "story":
      return null;
    case "pages":
      if (answers.mustHave.length === 0) return "Välj minst en sida att bygga.";
      return null;
    case "assets":
      // Bilder är alltid valfria — operatorn kan hoppa över för att
      // få en text-only sajt med monogram-logo.
      return null;
    case "brand":
      return null;
    default:
      return null;
  }
}

/**
 * Returnerar hur många % av wizarden som är klar baserat på vilka steg
 * som har uppfyllt sin minsta-krav-validering. Används som progress-
 * indikator i headern.
 */
export function wizardCompletionPercent(
  answers: WizardAnswers,
  branch: ContentBranch,
): number {
  const completed = WIZARD_STEP_ORDER.filter(
    (step) => validateWizardStep(step, answers, branch) === null,
  ).length;
  return Math.round((completed / WIZARD_STEP_ORDER.length) * 100);
}
