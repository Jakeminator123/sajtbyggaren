/**
 * Discovery wizard UI constants. Discovery Taxonomy is the canonical
 * category -> branch/scaffold/variant source; these TS values are a local UI
 * cache for labels, fallback rendering and non-governance chip lists.
 *
 * Datamodellen är organiserad i fyra nivåer som speglar pipelinens
 * fyra valpunkter (`Scaffold` / `Variant` / `Dossier` / `Starter`):
 *
 *   - `BUSINESS_FAMILIES` (8 st) → driver Scaffold + Starter via
 *     `WIZARD_CATEGORIES`. Operatören väljer ETT primärt val i steg 1.
 *   - `WIZARD_CATEGORIES` (25 st) → behålls för sub-specialisering
 *     (chip-rad under familje-valet) + governance-fallback i
 *     `discovery-options.ts`.
 *   - `VIBE_OPTIONS` (14 st) → driver Variant. Steg 2 visar bara de
 *     5 vibes som är kompatibla med vald scaffold.
 *   - `FUNCTION_GROUPS` (5 grupper × N chips) → driver Dossier-
 *     kapabiliteter + sid-routes. Ersätter den platta `MUST_HAVE_OPTIONS`-
 *     listan i steg 3.
 */

export type WizardCategoryId =
  | "business"
  | "ecommerce"
  | "restaurant"
  | "portfolio"
  | "landing"
  | "blog"
  | "consulting"
  | "tech"
  | "healthcare"
  | "realestate"
  | "salon"
  | "fitness"
  | "construction"
  | "education"
  | "event"
  | "nonprofit"
  | "music"
  | "hotel"
  | "legal"
  | "accounting"
  | "auto"
  | "travel"
  | "food"
  | "photo"
  | "other";

/**
 * Runtime-safe scaffold hints. Frontend may send these as hints only; the
 * backend Discovery Resolver decides selected scaffold/fallback from taxonomy.
 *
 * Speglar `_RUNTIME_SCAFFOLD_HINTS` i
 * `packages/generation/discovery/resolve.py`. När en ny scaffold flyttas
 * från planned till runtime (Path A eller Path B) måste denna typ
 * uppdateras tillsammans med resolve.py:s whitelist.
 */
export type ScaffoldHint =
  | "local-service-business"
  | "ecommerce-lite"
  | "restaurant-hospitality"
  | "clinic-healthcare"
  | "professional-services"
  | "agency-studio";

export type WizardCategory = {
  id: WizardCategoryId;
  label: string;
  scaffoldHint: ScaffoldHint;
  defaultVariantId: string;
};

/**
 * 25 chip categories mirrored from Discovery Taxonomy for first render only.
 * /api/discovery-options replaces these with governance-backed options when
 * the overlay opens.
 */
export const WIZARD_CATEGORIES: WizardCategory[] = [
  { id: "business", label: "Företag / Tjänster", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "ecommerce", label: "Webshop / E-handel", scaffoldHint: "ecommerce-lite", defaultVariantId: "clean-store" },
  // Restaurang/Café pekar mot restaurant-hospitality (Path A active
  // sedan 2026-05-25 — discovery-taxonomy.v1.json id="restaurant"
  // har activeScaffoldId: restaurant-hospitality). Måste matcha
  // BUSINESS_FAMILIES[restaurant] så att fallback-discovery-options
  // (FALLBACK_DISCOVERY_OPTIONS i discovery-options.ts) producerar
  // samma scaffold + variant som familje-grenen. Tidigare stod här
  // local-service-business / nordic-trust, vilket missades i den
  // ursprungliga GAP-viewser-restaurant-wizard-hint-PR:en — fixen
  // landar nu under samma GAP.
  { id: "restaurant", label: "Restaurang / Café", scaffoldHint: "restaurant-hospitality", defaultVariantId: "warm-bistro" },
  { id: "portfolio", label: "Portfolio / CV", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "landing", label: "Landningssida", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "blog", label: "Blogg / Magasin", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "consulting", label: "Konsult / Byrå", scaffoldHint: "agency-studio", defaultVariantId: "studio-monochrome" },
  { id: "tech", label: "Tech / Startup", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "healthcare", label: "Vård / Klinik", scaffoldHint: "clinic-healthcare", defaultVariantId: "clinic-calm" },
  { id: "realestate", label: "Fastighet / Mäklare", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "salon", label: "Salong / Skönhet", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "fitness", label: "Gym / Tränare", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "construction", label: "Bygg / Hantverk", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "education", label: "Utbildning / Skola", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "event", label: "Event / Bröllop", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "nonprofit", label: "Förening / Ideell", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "music", label: "Musik / Artist", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "hotel", label: "Hotell / Boende", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "legal", label: "Juridik / Advokat", scaffoldHint: "professional-services", defaultVariantId: "legal-classic" },
  { id: "accounting", label: "Ekonomi / Redovisning", scaffoldHint: "professional-services", defaultVariantId: "accounting-trust" },
  { id: "auto", label: "Bil / Motor", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "travel", label: "Resa / Turism", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "food", label: "Mat / Catering", scaffoldHint: "ecommerce-lite", defaultVariantId: "clean-store" },
  { id: "photo", label: "Foto / Video", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "other", label: "Annat", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
];

/**
 * 8 verksamhetsfamiljer som operatören väljer i steg 1. Varje familj
 * mappar till ett primärt scaffold/branch och ett antal sub-kategorier
 * (chips visas under familjevalet). Familjen driver scaffold-valet
 * deterministiskt; sub-kategorin är finlir för copy/SEO.
 */
export type BusinessFamilyId =
  | "service"
  | "ecommerce"
  | "restaurant"
  | "health"
  | "creative"
  | "construction"
  | "consulting"
  | "landing";

export type BusinessFamily = {
  id: BusinessFamilyId;
  label: string;
  description: string;
  scaffoldHint: ScaffoldHint;
  defaultVariantId: string;
  subCategories: WizardCategoryId[];
};

export const BUSINESS_FAMILIES: BusinessFamily[] = [
  {
    id: "service",
    label: "Lokalt företag / Tjänster",
    description: "Hantverkare, butiker, lokalt verksamma företag med kunder i området.",
    scaffoldHint: "local-service-business",
    defaultVariantId: "nordic-trust",
    subCategories: ["business", "realestate", "auto", "education", "legal", "accounting", "travel", "nonprofit", "music", "hotel"],
  },
  {
    id: "ecommerce",
    label: "E-handel / Webshop",
    description: "Sajt med produkter, kundvagn och checkout — fysiska eller digitala varor.",
    scaffoldHint: "ecommerce-lite",
    defaultVariantId: "clean-store",
    subCategories: ["ecommerce", "food"],
  },
  {
    id: "restaurant",
    label: "Restaurang / Café",
    description: "Meny, bordsbokning, öppettider och plats — visuellt aptitligt.",
    scaffoldHint: "restaurant-hospitality",
    defaultVariantId: "warm-bistro",
    subCategories: ["restaurant"],
  },
  {
    id: "health",
    label: "Salong / Klinik / Hälsa",
    description: "Tjänster, bokning, team och pris — fokus på förtroende och välmående.",
    scaffoldHint: "local-service-business",
    defaultVariantId: "clinical-calm",
    subCategories: ["healthcare", "salon", "fitness"],
  },
  {
    id: "creative",
    label: "Portfolio / Kreativ",
    description: "Visa projekt, case, fotografi eller eget skapande.",
    scaffoldHint: "local-service-business",
    // W3 i scout-review 2026-05-24: ``noir-editorial`` ligger under
    // ecommerce-lite-scaffolden. Creative family använder local-service-
    // business, så vi måste välja en variant som faktiskt finns där.
    // ``midnight-counsel`` ger samma premium-dark-känsla.
    defaultVariantId: "midnight-counsel",
    subCategories: ["portfolio", "photo"],
  },
  {
    id: "construction",
    label: "Bygg / Hantverk",
    description: "Referensprojekt, specialiteter och offertförfrågan.",
    scaffoldHint: "local-service-business",
    defaultVariantId: "warm-craft",
    subCategories: ["construction"],
  },
  {
    id: "consulting",
    label: "Konsult / Byrå / Tech",
    description: "Tjänsteområden, team och case — kunskap som säljs som tid.",
    scaffoldHint: "local-service-business",
    defaultVariantId: "midnight-counsel",
    subCategories: ["consulting", "tech"],
  },
  {
    id: "landing",
    label: "Landningssida / Event / Blogg",
    description: "Smal sajt för en lansering, kampanj, event eller publicering.",
    scaffoldHint: "local-service-business",
    defaultVariantId: "nordic-trust",
    subCategories: ["landing", "event", "blog", "other"],
  },
];

/** Returnerar verksamhetsfamiljen som äger en given sub-kategori. */
export function familyForCategory(
  categoryId: WizardCategoryId,
): BusinessFamily | undefined {
  return BUSINESS_FAMILIES.find((family) =>
    family.subCategories.includes(categoryId),
  );
}

/**
 * Härleder den faktiska scaffold-hint som UI:t och payloaden ska
 * använda. Steg-1-familyen är den primära signalen, men när operatören
 * också valt en sub-kategori vars `scaffoldHint` skiljer sig från
 * familyens (t.ex. "service"-family + "legal"-sub-cat → professional-
 * services i stället för LSB) vinner sub-kategorin. Detta är ren
 * UI-mapping; backend kör fortfarande sin egen Discovery Resolver mot
 * `discoveryTaxonomyId` och behandlar scaffoldHint bara som ett hint.
 *
 * Returnerar en deterministisk default när varken family eller sub-cat
 * är vald (LSB) så vibe-griden alltid har något att visa.
 *
 * Konsekvens av denna helper: Phase 3 section-treatments-disclosure
 * når också `agency-studio`/`clinic-healthcare`/`professional-services`
 * när operatören använder en sub-cat som mappar dit, även om
 * BUSINESS_FAMILIES-listan ännu inte har en egen entry för scaffolden.
 */
export function deriveEffectiveScaffoldHint(
  family: BusinessFamily | undefined,
  siteType: readonly WizardCategoryId[],
): ScaffoldHint {
  if (!family) {
    for (const categoryId of siteType) {
      const wizardCategory = WIZARD_CATEGORIES.find(
        (entry) => entry.id === categoryId,
      );
      if (wizardCategory) return wizardCategory.scaffoldHint;
    }
    return "local-service-business";
  }

  for (const categoryId of siteType) {
    if (!family.subCategories.includes(categoryId)) continue;
    const wizardCategory = WIZARD_CATEGORIES.find(
      (entry) => entry.id === categoryId,
    );
    if (wizardCategory && wizardCategory.scaffoldHint !== family.scaffoldHint) {
      return wizardCategory.scaffoldHint;
    }
  }

  return family.scaffoldHint;
}

/** Content branches control which content fields are shown in step 3. */
export type ContentBranch =
  | "ecommerce"
  | "restaurant"
  | "salon"
  | "portfolio"
  | "hotel"
  | "construction"
  | "education"
  | "event"
  | "legal"
  | "realestate"
  | "nonprofit"
  | "consulting"
  | "business"
  | "minimal";

/** UI-cache branch resolver used only before governance options load. */
export function resolveContentBranch(siteType: WizardCategoryId[]): ContentBranch {
  const set = new Set(siteType);
  if (set.has("ecommerce") || set.has("food")) return "ecommerce";
  if (set.has("restaurant")) return "restaurant";
  if (set.has("salon") || set.has("fitness") || set.has("healthcare")) return "salon";
  if (set.has("portfolio") || set.has("photo") || set.has("music")) return "portfolio";
  if (set.has("hotel") || set.has("travel")) return "hotel";
  if (set.has("construction") || set.has("auto")) return "construction";
  if (set.has("education")) return "education";
  if (set.has("event")) return "event";
  if (set.has("legal") || set.has("accounting")) return "legal";
  if (set.has("realestate")) return "realestate";
  if (set.has("nonprofit")) return "nonprofit";
  if (set.has("consulting") || set.has("tech")) return "consulting";
  if (set.has("business")) return "business";
  if (set.has("landing") || set.has("blog") || set.has("other")) return "minimal";
  return "business";
}

/** Härled content-branch från en BusinessFamilyId — används i steg 1 när
 * operatören valt familj men ännu inte sub-kategori. Detta är primärt
 * en UI-hint som visar vilket content-block som kommer i steg 4. */
export function branchForFamily(family: BusinessFamilyId): ContentBranch {
  switch (family) {
    case "ecommerce": return "ecommerce";
    case "restaurant": return "restaurant";
    case "health": return "salon";
    case "creative": return "portfolio";
    case "construction": return "construction";
    case "consulting": return "consulting";
    case "landing": return "minimal";
    case "service":
    default:
      return "business";
  }
}

/**
 * Vibes — de faktiska Variants som finns på disk i
 * `packages/generation/orchestration/scaffolds/<id>/variants/`. Varje vibe
 * tillhör ett scaffold och har en preview-färg + ord som beskriver känslan.
 * Wizardens steg 2 visar bara de som tillhör det valda scaffoldet.
 *
 * Aktuell fördelning (post-Path-B + Phase 3 polish 2026-05-25):
 *   - local-service-business: 7 (nordic-trust, warm-craft, clinical-calm,
 *     midnight-counsel, pulse-fit, sunrise-startup, family-warmth)
 *   - ecommerce-lite: 7 (clean-store, earth-wellness, mono-tech,
 *     noir-editorial, street-vivid, artisan-market, vintage-curio)
 *   - restaurant-hospitality: 4 (warm-bistro, casual-cafe, midnight-bar,
 *     nordic-fine-dining) — exponerade efter Path A runtime-aktivering
 *   - clinic-healthcare: 3 (clinic-calm, warm-care, modern-precision)
 *   - professional-services: 3 (legal-classic, consulting-modern,
 *     accounting-trust)
 *   - agency-studio: 3 (studio-monochrome, editorial-warm, bold-electric)
 *
 * Totalsumman måste matcha antalet `enabled: true`-variants på disk.
 * `tests/test_starter_scaffold_mapping.py` och liknande backend-tester
 * fångar drift mellan disk och dessa labels indirekt; UI:t kraschar inte
 * om en label saknas men operatören får inte se en vy för varianten.
 */
export type Vibe = {
  id: string;
  scaffoldHint: ScaffoldHint;
  label: string;
  description: string;
  primarySwatch: string;
  accentSwatch: string;
  background: string;
  defaultTypographyFeel: TypographyFeelId;
};

export const VIBE_OPTIONS: Vibe[] = [
  {
    id: "nordic-trust",
    scaffoldHint: "local-service-business",
    label: "Nordic Trust",
    description: "Rent, lugnt och professionellt — som en nordisk advokatbyrå.",
    primarySwatch: "#1f2937",
    accentSwatch: "#4f46e5",
    background: "#f8fafc",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "warm-craft",
    scaffoldHint: "local-service-business",
    label: "Warm Craft",
    description: "Varma jordtoner, hantverk och äkthet — som ett bageri.",
    primarySwatch: "#7c2d12",
    accentSwatch: "#d97706",
    background: "#fef3c7",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "clinical-calm",
    scaffoldHint: "local-service-business",
    label: "Clinical Calm",
    description: "Lugn, ljus och vårdande — som en privatklinik.",
    primarySwatch: "#0e7490",
    accentSwatch: "#22d3ee",
    background: "#ecfeff",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "midnight-counsel",
    scaffoldHint: "local-service-business",
    label: "Midnight Counsel",
    description: "Mörk elegans och exklusivitet — som en konsultbyrå.",
    primarySwatch: "#0f172a",
    accentSwatch: "#c0a062",
    background: "#020617",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "pulse-fit",
    scaffoldHint: "local-service-business",
    label: "Pulse Fit",
    description: "Energi, rörelse och kraft — som ett gym eller en träningsapp.",
    primarySwatch: "#dc2626",
    accentSwatch: "#facc15",
    background: "#fff7ed",
    defaultTypographyFeel: "geometric",
  },
  {
    id: "clean-store",
    scaffoldHint: "ecommerce-lite",
    label: "Clean Store",
    description: "Vit och saklig — produkterna i fokus, lågt visuellt brus.",
    primarySwatch: "#111827",
    accentSwatch: "#2563eb",
    background: "#ffffff",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "earth-wellness",
    scaffoldHint: "ecommerce-lite",
    label: "Earth Wellness",
    description: "Natur, jordnära och eko — som en hälsobutik.",
    primarySwatch: "#365314",
    accentSwatch: "#a3a060",
    background: "#f7fee7",
    defaultTypographyFeel: "organic",
  },
  {
    id: "mono-tech",
    scaffoldHint: "ecommerce-lite",
    label: "Mono Tech",
    description: "Minimalistisk svart-vit tech-känsla — som Apple eller Linear.",
    primarySwatch: "#000000",
    accentSwatch: "#525252",
    background: "#fafafa",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "noir-editorial",
    scaffoldHint: "ecommerce-lite",
    label: "Noir Editorial",
    description: "Magasin-aktig, mörk och utstuderad — som en modetidning.",
    primarySwatch: "#171717",
    accentSwatch: "#e11d48",
    background: "#0a0a0a",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "street-vivid",
    scaffoldHint: "ecommerce-lite",
    label: "Street Vivid",
    description: "Urbant, färgstarkt och uttrycksfullt — som streetwear.",
    primarySwatch: "#9333ea",
    accentSwatch: "#facc15",
    background: "#fff7ed",
    defaultTypographyFeel: "geometric",
  },
  {
    id: "sunrise-startup",
    scaffoldHint: "local-service-business",
    label: "Sunrise Startup",
    description: "Ljust, optimistiskt och modernt — som en ny byrå med stora planer.",
    primarySwatch: "#f06b48",
    accentSwatch: "#16a89a",
    background: "#fefaf2",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "family-warmth",
    scaffoldHint: "local-service-business",
    label: "Family Warmth",
    description: "Mjukt, varmt och familjevänligt — som en förskola eller barnaktivitet.",
    primarySwatch: "#e3899c",
    accentSwatch: "#9bb59a",
    background: "#fdf4ee",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "artisan-market",
    scaffoldHint: "ecommerce-lite",
    label: "Artisan Market",
    description: "Hantverk, småskaligt och äkta — som en marknad i ett gammalt lagerhus.",
    primarySwatch: "#4f5926",
    accentSwatch: "#b04428",
    background: "#f7f1e3",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "clinic-calm",
    scaffoldHint: "clinic-healthcare",
    label: "Clinic Calm",
    description: "Ljust, lugnt och vårdande — som en privatklinik.",
    primarySwatch: "#1f6f8b",
    accentSwatch: "#a8d8c5",
    background: "#fbfdfe",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "warm-care",
    scaffoldHint: "clinic-healthcare",
    label: "Warm Care",
    description: "Varmt, mänskligt och hands-on — som en naprapat eller barnmorska.",
    primarySwatch: "#6f7a4a",
    accentSwatch: "#cf997b",
    background: "#faf6f0",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "modern-precision",
    scaffoldHint: "clinic-healthcare",
    label: "Modern Precision",
    description: "Skarpt, tekniskt och precist — som en specialistklinik.",
    primarySwatch: "#1c2e4a",
    accentSwatch: "#c7cfdb",
    background: "#ffffff",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "vintage-curio",
    scaffoldHint: "ecommerce-lite",
    label: "Vintage Curio",
    description: "Patina, läderbunden och samlat — som en antikbutik med karaktär.",
    primarySwatch: "#6a1a20",
    accentSwatch: "#a87f3e",
    background: "#f4ecd8",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "warm-bistro",
    scaffoldHint: "restaurant-hospitality",
    label: "Warm Bistro",
    description:
      "Terrakotta och rostat bärnstensljus — som en kvartersbistro med pressad linne och kopparkastruller.",
    primarySwatch: "#8a3a20",
    accentSwatch: "#c98c4a",
    background: "#fbf6ee",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "casual-cafe",
    scaffoldHint: "restaurant-hospitality",
    label: "Casual Café",
    description:
      "Soligt persika och gräddvit — som ett dagligt café med nybryggt espresso och rundade former.",
    primarySwatch: "#d97842",
    accentSwatch: "#f4c773",
    background: "#fff8ef",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "midnight-bar",
    scaffoldHint: "restaurant-hospitality",
    label: "Midnight Bar",
    description:
      "Nattmörkt med borstad mässing och vinrött — som en cocktailbar där dimheten är medveten elegans.",
    primarySwatch: "#c39247",
    accentSwatch: "#7a1f24",
    background: "#0e0b0a",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "nordic-fine-dining",
    scaffoldHint: "restaurant-hospitality",
    label: "Nordic Fine Dining",
    description:
      "Galleritystnad i off-white och mossgrönt — för smakmenyer där maten själv är dramaturgin.",
    primarySwatch: "#2a3a2c",
    accentSwatch: "#a39167",
    background: "#f9f8f4",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "legal-classic",
    scaffoldHint: "professional-services",
    label: "Legal Classic",
    description: "Mörk navy och elfenben — som en traditionsrik advokatbyrå.",
    primarySwatch: "#0d1c2c",
    accentSwatch: "#9b7a3b",
    background: "#fbf8f1",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "consulting-modern",
    scaffoldHint: "professional-services",
    label: "Consulting Modern",
    description: "Vitt, grafit och kyligt — som en strategikonsult med skarpt språk.",
    primarySwatch: "#101418",
    accentSwatch: "#0e7c86",
    background: "#ffffff",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "accounting-trust",
    scaffoldHint: "professional-services",
    label: "Accounting Trust",
    description: "Varmt grönt och pergament — som en revisionsbyrå med hand om småföretag.",
    primarySwatch: "#1f4d3a",
    accentSwatch: "#c9a55a",
    background: "#f7f4ec",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "studio-monochrome",
    scaffoldHint: "agency-studio",
    label: "Studio Monochrome",
    description: "Strikt svart och vit — som en designstudio som låter arbetet tala.",
    primarySwatch: "#0a0a0a",
    accentSwatch: "#caa14a",
    background: "#ffffff",
    defaultTypographyFeel: "modern-sans",
  },
  {
    id: "editorial-warm",
    scaffoldHint: "agency-studio",
    label: "Editorial Warm",
    description: "Krämvit och bläck — som ett magasin som råkar vara en byrå.",
    primarySwatch: "#1a1612",
    accentSwatch: "#a64f30",
    background: "#f5f0e6",
    defaultTypographyFeel: "classic-serif",
  },
  {
    id: "bold-electric",
    scaffoldHint: "agency-studio",
    label: "Bold Electric",
    description: "Mörkt och elektriskt — som en motion-studio med energi.",
    primarySwatch: "#3d5cff",
    accentSwatch: "#3d5cff",
    background: "#0a0a0a",
    defaultTypographyFeel: "modern-sans",
  },
];

export function vibesForScaffold(scaffoldHint: ScaffoldHint): Vibe[] {
  return VIBE_OPTIONS.filter((vibe) => vibe.scaffoldHint === scaffoldHint);
}

export function findVibe(vibeId: string): Vibe | undefined {
  return VIBE_OPTIONS.find((vibe) => vibe.id === vibeId);
}

/** 4 typografi-känslor — chip-val i steg 2. */
export type TypographyFeelId =
  | "modern-sans"
  | "classic-serif"
  | "geometric"
  | "organic";

export const TYPOGRAPHY_FEEL_OPTIONS: {
  id: TypographyFeelId;
  label: string;
  description: string;
}[] = [
  {
    id: "modern-sans",
    label: "Modern sans",
    description: "Rent, tydligt och tidlöst — som Inter eller Helvetica.",
  },
  {
    id: "classic-serif",
    label: "Klassisk serif",
    description: "Förtroende och tradition — som The New York Times.",
  },
  {
    id: "geometric",
    label: "Geometrisk",
    description: "Skarpt och digitalt — som Futura eller Eurostile.",
  },
  {
    id: "organic",
    label: "Organisk / handskriven",
    description: "Mjukt, personligt och hantverksmässigt — som ett kort.",
  },
];

/** Ton-alternativ — chip-val i steg 4. */
export const TONE_OPTIONS = [
  "Professionell",
  "Varm och personlig",
  "Lekfull",
  "Exklusiv / lyxig",
  "Rak och enkel",
  "Modern och teknisk",
  "Lugn och förtroendeingivande",
] as const;

/** Design-stilar — chip-val i steg 2 (fallback om vibe väljs "låt AI:n välja"). */
export const DESIGN_STYLE_OPTIONS = [
  "Minimalistisk",
  "Kraftfull och bold",
  "Elegant och klassisk",
  "Lekfull och färgglad",
  "Naturlig och varm",
  "Låt AI:n välja",
] as const;

/** Primär call-to-action förslag — chip i steg 3. */
export const CTA_OPTIONS = [
  "Boka tid",
  "Kontakta oss",
  "Köp nu",
  "Begär offert",
  "Registrera dig",
  "Läs mer",
  "Ring oss",
  "Ladda ner",
] as const;

/**
 * 5 funktionsgrupper som ersätter den platta `MUST_HAVE_OPTIONS`-listan.
 * Varje grupp har chips med både ett label (det operatören ser) och en
 * `capability`-slug + `pageMustHave`-länk så vi kan översätta valet
 * till `requestedCapabilities[]` (Dossier) OCH `mustHave[]` (sidor).
 *
 * Detta är hjärtat i nya steg 3 — den nya "Funktioner"-vyn.
 */
export type FunctionGroupId =
  | "info"
  | "conversion"
  | "ecommerce"
  | "food"
  | "interaction";

export type FunctionChoice = {
  id: string;
  label: string;
  description?: string;
  /** Vilken backend-capability den triggar (Dossier-kandidat). */
  capability?: string;
  /** Vilken sid-route den lägger till i `mustHave[]`. */
  pageMustHave?: MustHaveOption;
};

/** Lucide-ikon-namn som UI:t mappar till en konkret komponent. Vi
 * håller mappingen i FunctionsStep så vi inte drar in icons-paketet
 * i konstant-filen. */
export type FunctionGroupIconKey =
  | "info"
  | "conversion"
  | "ecommerce"
  | "food"
  | "interaction";

export type FunctionGroup = {
  id: FunctionGroupId;
  label: string;
  description: string;
  iconKey: FunctionGroupIconKey;
  /** Filterfält per family — om null visas gruppen för alla. */
  visibleForFamilies?: BusinessFamilyId[];
  choices: FunctionChoice[];
};

/**
 * Per-family rekommendation av funktioner som auto-väljs första gången
 * operatören öppnar steget. Listan plockas från `FUNCTION_GROUPS` så
 * den alltid är synkroniserad — om ett ID inte finns ignoreras det.
 */
export const RECOMMENDED_FUNCTIONS_BY_FAMILY: Record<
  BusinessFamilyId,
  readonly string[]
> = {
  // Utökade förval (2026-06-09, operatörsfynd "bilsajt fick för få/fel
  // sidförslag"): listorna breddades mot taxonomins recommendedPages per
  // kategori (governance/policies/discovery-taxonomy.v1.json) som facit —
  // t.ex. auto→Karta, healthcare→FAQ, salon→Bildgalleri. Fortfarande en
  // UI-cache; det API-drivna kontraktet är reläat till backend (inbox
  // topic wizard-page-suggestions).
  service: [
    "fn-team",
    "fn-contact",
    "fn-quote",
    "fn-reviews",
    "fn-about",
    "fn-map",
    "fn-faq",
    "fn-pricing",
  ],
  ecommerce: [
    "fn-catalog",
    "fn-cart",
    "fn-checkout",
    "fn-faq",
    "fn-contact",
    "fn-reviews",
    "fn-newsletter",
  ],
  restaurant: [
    "fn-menu",
    "fn-tableresv",
    "fn-map",
    "fn-hours",
    "fn-gallery",
    "fn-reviews",
  ],
  health: [
    "fn-team",
    "fn-booking",
    "fn-pricing",
    "fn-map",
    "fn-contact",
    "fn-faq",
    "fn-reviews",
  ],
  creative: ["fn-gallery", "fn-about", "fn-contact", "fn-pricing", "fn-booking"],
  construction: [
    "fn-gallery",
    "fn-team",
    "fn-pricing",
    "fn-quote",
    "fn-reviews",
    "fn-map",
    "fn-faq",
  ],
  consulting: [
    "fn-team",
    "fn-pricing",
    "fn-contact",
    "fn-blog",
    "fn-reviews",
    "fn-faq",
  ],
  landing: ["fn-contact", "fn-newsletter"],
};

/**
 * Sidor som auto-förväljs per familj UTÖVER de som härleds via
 * funktions-valens `pageMustHave`. Behövs för sidor som inte har någon
 * funktions-koppling alls — t.ex. "Portfolio / Case" (referensjobb) som
 * taxonomin rekommenderar för portfolio/construction-kategorierna men
 * som ingen FunctionChoice pekar på.
 */
export const RECOMMENDED_EXTRA_PAGES_BY_FAMILY: Partial<
  Record<BusinessFamilyId, readonly MustHaveOption[]>
> = {
  creative: ["Portfolio / Case"],
  construction: ["Portfolio / Case"],
};

/**
 * Vilka av de 15 sidorna i `MUST_HAVE_OPTIONS` som är RELEVANTA att visa
 * direkt i sidrutnätet för en given familj. Övriga sidor döljs bakom en
 * "Visa fler sidor"-toggle (operatörsfynd 2026-06-09: en bilverkstad såg
 * "Meny / Matsedel" som förslag — irrelevanta sidor ska inte se ut som
 * rekommendationer). Valda sidor visas ALLTID, även utanför listan, så
 * inget val kan gömmas. Grundad i taxonomins recommendedPages per
 * kategori; UI-cache tills backend serverar detta via discovery-options.
 */
export const RELEVANT_PAGES_BY_FAMILY: Record<
  BusinessFamilyId,
  readonly MustHaveOption[]
> = {
  service: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Priser och paket",
    "Bokning online",
    "Bildgalleri",
    "Kundrecensioner",
    "FAQ",
    "Vårt team",
    "Karta / Hitta hit",
    "Blogg / Nyheter",
  ],
  ecommerce: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Webshop / Produkter",
    "FAQ",
    "Kundrecensioner",
    "Bildgalleri",
    "Blogg / Nyheter",
    "Nyhetsbrev",
  ],
  restaurant: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Meny / Matsedel",
    "Bokning online",
    "Bildgalleri",
    "Karta / Hitta hit",
    "Kundrecensioner",
    "FAQ",
    "Nyhetsbrev",
  ],
  health: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Bokning online",
    "Priser och paket",
    "Vårt team",
    "Karta / Hitta hit",
    "FAQ",
    "Bildgalleri",
    "Kundrecensioner",
  ],
  creative: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Portfolio / Case",
    "Bildgalleri",
    "Bokning online",
    "Priser och paket",
    "Blogg / Nyheter",
  ],
  construction: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Portfolio / Case",
    "Bildgalleri",
    "Kundrecensioner",
    "Priser och paket",
    "Vårt team",
    "FAQ",
    "Karta / Hitta hit",
  ],
  consulting: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Vårt team",
    "Priser och paket",
    "Blogg / Nyheter",
    "FAQ",
    "Kundrecensioner",
    "Portfolio / Case",
    "Nyhetsbrev",
  ],
  landing: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Kontaktformulär",
    "Nyhetsbrev",
    "Blogg / Nyheter",
    "FAQ",
  ],
};

export const FUNCTION_GROUPS: FunctionGroup[] = [
  {
    id: "info",
    label: "Information",
    description: "Vad besökaren ska kunna läsa om er.",
    iconKey: "info",
    choices: [
      // Canonical capability-sluggar per msg-0057 (capability-map.v1.json):
      // menu/team-section/reviews/gallery. De gamla UI-aliasen
      // (menu-display/team-display/reviews-display/image-gallery) läggs som
      // skyddsnät i resolverns alias-tabell i Jakobs punkt 1-slice.
      { id: "fn-team", label: "Visa team", capability: "team-section", pageMustHave: "Vårt team" },
      { id: "fn-pricing", label: "Pris-lista", capability: "pricing-display", pageMustHave: "Priser och paket" },
      { id: "fn-gallery", label: "Bildgalleri", capability: "gallery", pageMustHave: "Bildgalleri" },
      { id: "fn-map", label: "Karta & vägbeskrivning", capability: "map-embed", pageMustHave: "Karta / Hitta hit" },
      { id: "fn-hours", label: "Öppettider", capability: "opening-hours" },
      { id: "fn-faq", label: "FAQ", capability: "faq-section", pageMustHave: "FAQ" },
      { id: "fn-blog", label: "Blogg / nyheter", capability: "blog", pageMustHave: "Blogg / Nyheter" },
      { id: "fn-reviews", label: "Kundrecensioner", capability: "reviews", pageMustHave: "Kundrecensioner" },
      { id: "fn-about", label: "Om oss / Om mig", capability: "about-page", pageMustHave: "Om oss / Om mig" },
    ],
  },
  {
    id: "conversion",
    label: "Konvertering",
    description: "Hur besökaren tar nästa steg och blir kund.",
    iconKey: "conversion",
    choices: [
      { id: "fn-contact", label: "Kontaktformulär", capability: "contact-form", pageMustHave: "Kontaktformulär" },
      { id: "fn-booking", label: "Boka tid online", capability: "online-booking", pageMustHave: "Bokning online" },
      { id: "fn-quote", label: "Begär offert", capability: "quote-request" },
      { id: "fn-newsletter", label: "Nyhetsbrevs-prenumeration", capability: "newsletter-signup", pageMustHave: "Nyhetsbrev" },
      { id: "fn-callto", label: "Ring-knapp (mobile)", capability: "click-to-call" },
    ],
  },
  {
    id: "ecommerce",
    label: "E-handel",
    description: "Visas när du valt E-handel som familj.",
    iconKey: "ecommerce",
    visibleForFamilies: ["ecommerce"],
    choices: [
      { id: "fn-catalog", label: "Produktkatalog", capability: "product-catalog", pageMustHave: "Webshop / Produkter" },
      { id: "fn-cart", label: "Kundvagn", capability: "shopping-cart" },
      { id: "fn-checkout", label: "Checkout", capability: "checkout-flow" },
      { id: "fn-inventory", label: "Lager-status", capability: "inventory-display" },
      { id: "fn-prodreview", label: "Recensioner per produkt", capability: "product-reviews" },
    ],
  },
  {
    id: "food",
    label: "Mat & dryck",
    description: "Visas när du valt Restaurang / Café som familj.",
    iconKey: "food",
    visibleForFamilies: ["restaurant"],
    choices: [
      { id: "fn-menu", label: "Meny / matsedel", capability: "menu", pageMustHave: "Meny / Matsedel" },
      { id: "fn-orderonline", label: "Online-beställning", capability: "online-ordering" },
      { id: "fn-tableresv", label: "Bordsbokning", capability: "table-reservation", pageMustHave: "Bokning online" },
    ],
  },
  {
    id: "interaction",
    label: "Interaktion / avancerat",
    description: "Funktioner som ger sajten extra liv eller specialfunktion.",
    iconKey: "interaction",
    choices: [
      { id: "fn-chat", label: "Live-chat", capability: "live-chat" },
      { id: "fn-multilang", label: "Multispråk", capability: "multi-language" },
      { id: "fn-login", label: "Kundinloggning", capability: "user-auth" },
      { id: "fn-portal", label: "Kundportal", capability: "customer-portal" },
      { id: "fn-game", label: "Spel / quiz", capability: "interactive-game" },
      { id: "fn-video", label: "Video-bakgrund", capability: "video-hero" },
      { id: "fn-animation", label: "Animationer", capability: "scroll-animations" },
    ],
  },
];

/** Returnerar alla funktionsgrupper som är synliga för en given family. */
export function functionGroupsForFamily(
  family: BusinessFamilyId | "",
): FunctionGroup[] {
  return FUNCTION_GROUPS.filter((group) => {
    if (!group.visibleForFamilies) return true;
    if (!family) return false;
    return group.visibleForFamilies.includes(family);
  });
}

/** Slå upp en funktion via id — används av demo-data och payload. */
export function findFunctionChoice(id: string): FunctionChoice | undefined {
  for (const group of FUNCTION_GROUPS) {
    const found = group.choices.find((choice) => choice.id === id);
    if (found) return found;
  }
  return undefined;
}

/** Must-have-sidor — chip-listor i steg 5 (legacy + interna sid-namn). */
export const MUST_HAVE_OPTIONS = [
  "Startsida / Hero",
  "Om oss / Om mig",
  "Kontaktformulär",
  "Priser och paket",
  "Bokning online",
  "Bildgalleri",
  "Blogg / Nyheter",
  "Kundrecensioner",
  "FAQ",
  "Portfolio / Case",
  "Vårt team",
  "Karta / Hitta hit",
  "Nyhetsbrev",
  "Webshop / Produkter",
  "Meny / Matsedel",
] as const;

export type MustHaveOption = (typeof MUST_HAVE_OPTIONS)[number];

/**
 * Per-kategori rekommendation av sidor. Används av `PagesStep` för att
 * auto-välja vettiga defaults baserat på vilka kategori-chips operatören
 * markerat i steg 2 (SiteType). Listan är medvetet kort — fler sidor
 * kan alltid läggas till manuellt från "Övriga sidor"-listan.
 *
 * Ordningen i varje array styr vilken ordning sidorna föreslås i UI:t
 * (Startsida / Hero kommer alltid först eftersom den ÄR sajten).
 */
export const RECOMMENDED_PAGES_BY_CATEGORY: Record<
  WizardCategoryId,
  readonly MustHaveOption[]
> = {
  business: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Vårt team",
    "Kundrecensioner",
    "Kontaktformulär",
  ],
  ecommerce: [
    "Startsida / Hero",
    "Webshop / Produkter",
    "Om oss / Om mig",
    "FAQ",
    "Kontaktformulär",
  ],
  restaurant: [
    "Startsida / Hero",
    "Meny / Matsedel",
    "Bokning online",
    "Bildgalleri",
    "Karta / Hitta hit",
    "Om oss / Om mig",
  ],
  portfolio: [
    "Startsida / Hero",
    "Portfolio / Case",
    "Om oss / Om mig",
    "Kontaktformulär",
  ],
  landing: ["Startsida / Hero", "Kontaktformulär"],
  blog: [
    "Startsida / Hero",
    "Blogg / Nyheter",
    "Om oss / Om mig",
    "Nyhetsbrev",
    "Kontaktformulär",
  ],
  consulting: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Vårt team",
    "Priser och paket",
    "Kundrecensioner",
    "Kontaktformulär",
  ],
  tech: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Priser och paket",
    "Blogg / Nyheter",
    "Kontaktformulär",
  ],
  healthcare: [
    "Startsida / Hero",
    "Vårt team",
    "Bokning online",
    "Karta / Hitta hit",
    "FAQ",
    "Kontaktformulär",
  ],
  realestate: [
    "Startsida / Hero",
    "Webshop / Produkter",
    "Om oss / Om mig",
    "Karta / Hitta hit",
    "Kontaktformulär",
  ],
  salon: [
    "Startsida / Hero",
    "Bokning online",
    "Priser och paket",
    "Bildgalleri",
    "Karta / Hitta hit",
    "Om oss / Om mig",
  ],
  fitness: [
    "Startsida / Hero",
    "Priser och paket",
    "Bokning online",
    "Vårt team",
    "Karta / Hitta hit",
    "Om oss / Om mig",
  ],
  construction: [
    "Startsida / Hero",
    "Portfolio / Case",
    "Om oss / Om mig",
    "Kundrecensioner",
    "Kontaktformulär",
  ],
  education: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Priser och paket",
    "Vårt team",
    "FAQ",
    "Kontaktformulär",
  ],
  event: [
    "Startsida / Hero",
    "Bokning online",
    "Bildgalleri",
    "Om oss / Om mig",
    "Kontaktformulär",
  ],
  nonprofit: [
    "Startsida / Hero",
    "Om oss / Om mig",
    "Vårt team",
    "Blogg / Nyheter",
    "Nyhetsbrev",
    "Kontaktformulär",
  ],
  music: [
    "Startsida / Hero",
    "Bildgalleri",
    "Bokning online",
    "Om oss / Om mig",
    "Kontaktformulär",
  ],
  hotel: [
    "Startsida / Hero",
    "Bokning online",
    "Bildgalleri",
    "Priser och paket",
    "Karta / Hitta hit",
    "Om oss / Om mig",
  ],
  legal: [
    "Startsida / Hero",
    "Vårt team",
    "Priser och paket",
    "FAQ",
    "Kontaktformulär",
  ],
  accounting: [
    "Startsida / Hero",
    "Vårt team",
    "Priser och paket",
    "FAQ",
    "Kontaktformulär",
  ],
  auto: [
    "Startsida / Hero",
    "Webshop / Produkter",
    "Om oss / Om mig",
    "Karta / Hitta hit",
    "Kontaktformulär",
  ],
  travel: [
    "Startsida / Hero",
    "Bildgalleri",
    "Priser och paket",
    "Bokning online",
    "Kontaktformulär",
  ],
  food: [
    "Startsida / Hero",
    "Meny / Matsedel",
    "Webshop / Produkter",
    "Karta / Hitta hit",
    "Kontaktformulär",
  ],
  photo: [
    "Startsida / Hero",
    "Portfolio / Case",
    "Bildgalleri",
    "Om oss / Om mig",
    "Kontaktformulär",
  ],
  other: ["Startsida / Hero", "Om oss / Om mig", "Kontaktformulär"],
};

/**
 * Keyword → must-have-page-mapping. Används för att gissa extra
 * sidor som behövs baserat på skrapad text (offer, story, products,
 * menu, etc.). Mönstren är ordlistor — om något av orden hittas
 * (case-insensitive substring) tipsar vi om motsvarande sida.
 *
 * Mönstren är avsiktligt breda och tål både svenska och engelska
 * eftersom skrape-output kan komma från valfri språkblandning.
 */
const PAGE_KEYWORDS: ReadonlyArray<{
  page: MustHaveOption;
  keywords: readonly string[];
}> = [
  {
    page: "Bokning online",
    keywords: ["boka", "bokning", "bokningar", "boktid", "tidsbokning", "appointment", "schedule"],
  },
  {
    page: "Meny / Matsedel",
    keywords: ["meny", "matsedel", "rätt", "huvudrätt", "förrätt", "menu", "dish"],
  },
  {
    page: "Webshop / Produkter",
    keywords: ["produkt", "produkter", "shop", "köp", "varor", "sortiment", "product", "store"],
  },
  {
    page: "Portfolio / Case",
    keywords: ["portfolio", "case", "projekt", "uppdrag", "referensprojekt", "projects"],
  },
  {
    page: "Vårt team",
    keywords: ["team", "medarbetare", "personal", "kollegor", "grundare", "founders", "staff"],
  },
  {
    page: "Blogg / Nyheter",
    keywords: ["blogg", "artikel", "artiklar", "nyheter", "inlägg", "blog", "post", "news"],
  },
  {
    page: "Kundrecensioner",
    keywords: ["recension", "omdöme", "kundröster", "testimonial", "review"],
  },
  {
    page: "FAQ",
    keywords: ["faq", "frågor", "vanliga frågor", "questions"],
  },
  {
    page: "Nyhetsbrev",
    keywords: ["nyhetsbrev", "prenumerera", "newsletter", "subscribe"],
  },
  {
    page: "Bildgalleri",
    keywords: ["galleri", "bilder", "fotografier", "gallery", "photos"],
  },
  {
    page: "Priser och paket",
    keywords: ["pris", "priser", "paket", "kampanj", "pricing", "tier"],
  },
  {
    page: "Karta / Hitta hit",
    keywords: ["hitta hit", "vägbeskrivning", "adress", "karta", "directions", "location"],
  },
];

/**
 * Returnerar en uppsättning rekommenderade sidor baserat på (a) de
 * kategorier som valts i steg 2 och (b) keyword-träffar i fri-text
 * från skrape/wizard-svar. Resultatet är ordnat enligt
 * `MUST_HAVE_OPTIONS` så UI:t alltid visar sidorna i samma ordning.
 */
export function suggestPagesFromAnswers(
  siteType: readonly WizardCategoryId[],
  textInputs: readonly (string | undefined)[] = [],
): MustHaveOption[] {
  const set = new Set<MustHaveOption>();

  for (const id of siteType) {
    const pages = RECOMMENDED_PAGES_BY_CATEGORY[id];
    if (!pages) continue;
    for (const page of pages) set.add(page);
  }

  const haystack = textInputs
    .filter((s): s is string => typeof s === "string" && s.trim().length > 0)
    .join(" ")
    .toLowerCase();

  if (haystack.length > 0) {
    for (const { page, keywords } of PAGE_KEYWORDS) {
      if (keywords.some((kw) => haystack.includes(kw))) {
        set.add(page);
      }
    }
  }

  // Startsidan ÄR sajten — föreslå alltid den även om kategori/keywords
  // inte explicit nämner den.
  set.add("Startsida / Hero");

  // Sortera enligt MUST_HAVE_OPTIONS-ordningen för stabil rendering.
  return MUST_HAVE_OPTIONS.filter((opt) => set.has(opt));
}

/** Restaurang-specifika kök-chip i steg 4. */
export const CUISINE_OPTIONS = [
  "Svenskt",
  "Italienskt",
  "Asiatiskt",
  "Indiskt",
  "Mexikanskt",
  "Sushi",
  "Pizza",
  "Burgare",
  "Café / Fika",
  "Fine dining",
  "Street food",
  "Vegetariskt",
  "Veganskt",
] as const;

/** Restaurang-specifika kostalternativ. */
export const DIETARY_OPTIONS = [
  "Vegetariskt",
  "Veganskt",
  "Glutenfritt",
  "Laktosfritt",
  "Nötfritt",
  "Halal",
  "Kosher",
] as const;

/** Prisnivå-chip för restaurang/ecommerce. */
export const PRICE_TIER_OPTIONS = ["Budget", "Mellan", "Premium"] as const;
