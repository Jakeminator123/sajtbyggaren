/**
 * Discovery wizard constants — kategorier, chip-listor och statiska
 * mappnings som styr stegens UI. Ported från
 * `Sajtmaskin_Genberg/src/components/builder/IntakeWizard.tsx`
 * (CATEGORIES / TONE / CTA / MUST_HAVE) men anpassade mot
 * Sajtbyggaren 2.0:s scaffold/variant-namn (se
 * `governance/policies/scaffold-contract.v1.json`).
 *
 * Hålls i en ren TS-fil — inga React-importer — så att backend-
 * mappern (`packages/generation/discovery/`) kan parsa samma
 * enum-listor via genererade JSON-sidor om vi senare väljer att
 * code-genera dem.
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
 * Scaffold-IDs som Sajtbyggaren 2.0 idag erkänner. Speglar
 * `packages/generation/orchestration/scaffolds/<id>/` på disk.
 * Wizarden använder dessa som `scaffoldHint` i Site Brief; planner-
 * modellen har sista ordet om vilken scaffold som faktiskt väljs.
 */
export type ScaffoldHint = "local-service-business" | "ecommerce-lite";

export type WizardCategory = {
  id: WizardCategoryId;
  label: string;
  scaffoldHint: ScaffoldHint;
  defaultVariantId: string;
};

/**
 * 25 chip-kategorier. Varje kategori mappas till en av de scaffolds
 * som Sajtbyggaren idag stödjer. Saknade vertikaler (portfolio etc.)
 * faller tillbaka till `local-service-business` tills nästa scaffold
 * är klar.
 */
export const WIZARD_CATEGORIES: WizardCategory[] = [
  { id: "business", label: "Företag / Tjänster", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "ecommerce", label: "Webshop / E-handel", scaffoldHint: "ecommerce-lite", defaultVariantId: "clean-store" },
  { id: "restaurant", label: "Restaurang / Café", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "portfolio", label: "Portfolio / CV", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "landing", label: "Landningssida", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "blog", label: "Blogg / Magasin", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "consulting", label: "Konsult / Byrå", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "tech", label: "Tech / Startup", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "healthcare", label: "Vård / Klinik", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "realestate", label: "Fastighet / Mäklare", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "salon", label: "Salong / Skönhet", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "fitness", label: "Gym / Tränare", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "construction", label: "Bygg / Hantverk", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "education", label: "Utbildning / Skola", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "event", label: "Event / Bröllop", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "nonprofit", label: "Förening / Ideell", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "music", label: "Musik / Artist", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "hotel", label: "Hotell / Boende", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "legal", label: "Juridik / Advokat", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "accounting", label: "Ekonomi / Redovisning", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "auto", label: "Bil / Motor", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "travel", label: "Resa / Turism", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "food", label: "Mat / Catering", scaffoldHint: "ecommerce-lite", defaultVariantId: "clean-store" },
  { id: "photo", label: "Foto / Video", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
  { id: "other", label: "Annat", scaffoldHint: "local-service-business", defaultVariantId: "nordic-trust" },
];

/**
 * Content-grenar styr vilka inneråslfält som visas i steg 3. Mappas
 * från valda kategorier via `resolveContentBranch()`.
 */
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

/**
 * Returnerar den mest specifika gren som matchar valda kategorier.
 * Mer specifika grenar (ecommerce, restaurant, etc.) vinner över
 * generiska (business, minimal). Tom siteType faller tillbaka till
 * `business`.
 */
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

/** Ton-alternativ — chip-val i steg 6. */
export const TONE_OPTIONS = [
  "Professionell",
  "Varm och personlig",
  "Lekfull",
  "Exklusiv / lyxig",
  "Rak och enkel",
  "Modern och teknisk",
  "Lugn och förtroendeingivande",
] as const;

/** Design-stilar — chip-val i steg 6. */
export const DESIGN_STYLE_OPTIONS = [
  "Minimalistisk",
  "Kraftfull och bold",
  "Elegant och klassisk",
  "Lekfull och färgglad",
  "Naturlig och varm",
  "Låt AI:n välja",
] as const;

/** Primär call-to-action förslag — chip i steg 5. */
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

/** Must-have-sidor — chip-listor i steg 5. */
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

/** Restaurang-specifika kök-chip i steg 3. */
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
