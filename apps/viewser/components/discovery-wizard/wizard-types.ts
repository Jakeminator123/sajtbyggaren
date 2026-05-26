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
 * 2026-05-19 — 5-stegs-omstrukturering: stegen heter nu `foundation`,
 * `visual`, `functions`, `content`, `media` och mappar 1:1 mot de fyra
 * pipeline-delarna (Scaffold/Starter, Variant, Dossier, Copy + Assets).
 * Nya fält tillagda: `businessFamily`, `vibe`, `moodImages`,
 * `selectedFunctions`, `specialRequests`, `productImages` per produkt,
 * `media.{favicon,ogImage,backgroundVideo}`. Gamla fält behålls för att
 * `wizard-payload.ts` / `composeMasterPrompt` ska fungera utan stora
 * backend-ändringar.
 */

import type {
  BusinessFamilyId,
  ContentBranch,
  TypographyFeelId,
  WizardCategoryId,
} from "./wizard-constants";
import type { AssetRef } from "@/lib/asset-store/types";

/**
 * 2026-05-26 — Total-minimalism-omgång (GAP-viewser-wizard-minimal-tabs).
 *
 * Wizarden reducerades från 5 till 3 huvudsteg som visas som tabs överst.
 * `content` och `media` finns kvar som typer (popupen "Mer information"
 * återanvänder samma fält) men ingår INTE längre i `WIZARD_STEP_ORDER`
 * och har följaktligen ingen sidebar/tab-knapp. Backend-payload ändras
 * INTE — alla fält skickas fortfarande via `buildDiscoveryPayload`.
 *
 * 2026-05-26 (v2) — Bilder-flik tillagd (GAP-viewser-wizard-assets-tab).
 * Logo + mediamaterial (AssetsStep) flyttades ut ur "functions"-tabben
 * och fick en egen fjärde tab "Bilder" så operatorn ser tydligt att
 * uppladdning är ett separat steg, inte en kropp under sidor. "Ange
 * information"-popup-knappen flyttades samtidigt till "Bilder"-tabben
 * så den ligger precis innan "Skapa sajt".
 */
export type WizardStepId =
  | "foundation"
  | "visual"
  | "functions"
  | "assets"
  | "content"
  | "media";

export const WIZARD_STEP_ORDER: WizardStepId[] = [
  "foundation",
  "visual",
  "functions",
  "assets",
];

/**
 * Lista över alla steg som någonsin har funnits — används av
 * payload-byggaren och eventuella legacy-validators. ContentBranch +
 * Media-fält nås nu via popupen istället.
 */
export const WIZARD_STEP_ORDER_LEGACY_ALL: WizardStepId[] = [
  "foundation",
  "visual",
  "functions",
  "assets",
  "content",
  "media",
];

export const WIZARD_STEP_TITLES: Record<WizardStepId, string> = {
  foundation: "Företaget",
  visual: "Stil",
  functions: "Funktioner",
  assets: "Bilder",
  // Visas inte som tab, men behålls för legacy-läsare som mappar
  // alla WizardStepId till en titel (t.ex. payload-debug).
  content: "Innehåll",
  media: "Bilder & media",
};

/**
 * Pipeline-del som steget primärt styr. Visas inte längre i UI:t
 * (total-minimalism-pass) men behålls för ev. debug-vy och sänd
 * den till payload-byggaren.
 */
export type PipelinePart = "Sidor" | "Visuellt" | "Funktioner" | "Innehåll" | "Media";

export const WIZARD_STEP_PIPELINE_BADGE: Record<WizardStepId, PipelinePart> = {
  foundation: "Sidor",
  visual: "Visuellt",
  functions: "Funktioner",
  assets: "Media",
  content: "Innehåll",
  media: "Media",
};

export type ProductItem = {
  id: string;
  name: string;
  price?: string;
  description?: string;
  category?: string;
  imageUrl?: string;
  /** Per-produkt-bild (nytt i Pass 1 — uppladdad via dropzone i steg 4). */
  productImage?: AssetRef;
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
 * Steg 2 — Visuell identitet. Drivs av vald `vibeId` (en av 10
 * varianter i `VIBE_OPTIONS`), plus typography-feel och valfri
 * kombination av egna färger + referenser + mood-bilder.
 *
 * `useCustomColors=true` betyder att backend ska skriva över variantens
 * default `--primary` och `--accent` med `brand.primaryColorHex` /
 * `brand.accentColorHex` (kräver att Gap 1 stängs av backend; se
 * `docs/backend-handoff.md`).
 */
/**
 * Hero-layout-preferens för startsidan. Tom sträng betyder "automatisk"
 * — då härleder backend layout från vald `vibeId` (warm-craft → centered,
 * midnight-counsel → split, nordic-trust → gradient, etc.). När operator
 * vill överstyra valet skickas värdet vidare via
 * `directives.layoutHint` och konsumeras av build_site.py:_hero_style_for.
 */
export type HeroLayoutHint = "" | "gradient" | "centered" | "split";

/**
 * Operator-pin för section design treatments (Phase 3, ADR 0032).
 *
 * Nyckeln är section-id (matchar Python `_SECTION_RENDERERS` och
 * schemats `directives.sectionTreatments.properties`-keys), värdet
 * är treatment-id (matchar enum-listan per section). Tom map (eller
 * saknad nyckel) = "auto" — varianten/sectionens default kör.
 *
 * Schemat validerar både keys och values så en typo fångas innan
 * bygget startar; UI:t exponerar bara registrerade ids via
 * `treatment-options.ts`.
 */
export type WizardSectionTreatments = Record<string, string>;

export type WizardVibe = {
  vibeId: string;
  useCustomColors: boolean;
  typographyFeel: TypographyFeelId | "";
  references: string;
  /** Operator-override av hero-layout. Tom = automatic från vibe. */
  layoutHint: HeroLayoutHint;
  /**
   * Operator-pin per section. Speglar
   * `directives.sectionTreatments` i Project Input.schema.json. Tom
   * map = inga overrides; varje section kör sin variant- eller
   * section-default. ADR 0032.
   */
  sectionTreatments: WizardSectionTreatments;
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
 * Steg 5 — extra media-assets utöver logo/hero/gallery. Behöver
 * backend-stöd för att fullt utnyttjas (favicon → .ico-konvertering,
 * OG-image → 1200×630 crop, video → mime-validering). Se
 * `docs/backend-handoff.md` för exakt vad som behövs.
 */
export type WizardMedia = {
  favicon: AssetRef | null;
  ogImage: AssetRef | null;
  backgroundVideo: AssetRef | null;
};

/**
 * Confidence-nivå per fält när det fylldes från scrape/LLM. UI:t
 * använder den för att visa en diskret "auto-ifylld"-badge så
 * operatorn vet vilka svar som behöver granskas extra noga.
 */
export type FieldConfidence = "high" | "medium" | "low";

export type WizardAnswers = {
  /** Steg 1 — Företaget & sajttypen */
  companyName: string;
  offer: string;
  existingSite: string;
  contact: WizardContact;
  /** Ny i Pass 1 — primär verksamhetsfamilj som driver scaffold/starter. */
  businessFamily: BusinessFamilyId | "";
  /** Sub-kategori (sub-specialisering). Multi-select bibehållen för bakåtkompat. */
  siteType: WizardCategoryId[];

  /** Steg 2 — Visuell identitet */
  vibe: WizardVibe;
  /** Ton + designStyle + färger + ord-att-undvika. Levde tidigare i sista steget. */
  brand: WizardBrand;
  /** Nya mood-bilder — referenser, ej sajt-assets. */
  moodImages: AssetRef[];

  /** Steg 3 — Funktioner & sidor */
  /** Funktionsval från `FUNCTION_GROUPS` (chip-IDs som "fn-team"). */
  selectedFunctions: string[];
  /** Konkret sidlista — kan utökas auto från `selectedFunctions`. */
  mustHave: string[];
  primaryCta: string;
  specialRequests: string;

  /** Steg 4 — Innehåll & ton */
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
  aboutText: string;
  historyText: string;
  visionText: string;
  contactIntroText: string;
  targetAudience: string;

  /** Steg 5 — Bilder & media */
  assets: WizardAssets;
  media: WizardMedia;

  /** Meta — vilka fält som autifylldes (för UI-feedback) */
  scrapedFields: Partial<Record<keyof Omit<WizardAnswers, "scrapedFields">, FieldConfidence>>;
};

export function emptyWizardAnswers(): WizardAnswers {
  return {
    companyName: "",
    offer: "",
    existingSite: "",
    contact: { phone: "", email: "", address: "", openingHours: "" },
    businessFamily: "",
    siteType: [],
    vibe: {
      vibeId: "",
      useCustomColors: false,
      typographyFeel: "",
      references: "",
      layoutHint: "",
      sectionTreatments: {},
    },
    brand: {
      toneTags: [],
      designStyle: "",
      primaryColorHex: "",
      accentColorHex: "",
      wordsToAvoid: "",
    },
    moodImages: [],
    selectedFunctions: [],
    mustHave: [],
    primaryCta: "",
    specialRequests: "",
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
    targetAudience: "",
    assets: {
      logo: null,
      heroImage: null,
      gallery: [],
    },
    media: {
      favicon: null,
      ogImage: null,
      backgroundVideo: null,
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
    case "foundation":
      // Total-minimalism-pass (2026-05-26): bara offer + businessFamily är
      // hard-required. Operatorn kan skippa företagsnamn, kontakt och sub-
      // kategori — dessa fält skrapas eller förefyllas av Vision/defaults.
      if (answers.offer.trim().length < 3) return "Beskriv kort vad ni gör.";
      if (!answers.businessFamily) return "Välj vilken typ av verksamhet det är.";
      return null;
    case "visual":
      // Stil-tabben är alltid skip-bar — scaffold har goda defaults.
      return null;
    case "functions":
      // Total-minimalism: ingen hard-validation längre. Recommended-funktioner
      // förefylls auto från businessFamily i `functions-step.tsx`. Operatorn
      // kan alltid gå direkt till "Skapa sajt".
      return null;
    case "assets":
      // Bilder-tabben är alltid skip-bar — operatorn kan generera sajten
      // utan uppladdat material (monogram-logo + AI-genererad hero används).
      return null;
    case "content":
      // Innehållssteget är alltid valfritt — utan tjänster/produkter
      // kan generator-modellen ändå mocka eller fråga senare.
      void branch;
      return null;
    case "media":
      // Bilder är alltid valfria — operatorn kan hoppa över för att
      // få en text-only sajt med monogram-logo.
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
