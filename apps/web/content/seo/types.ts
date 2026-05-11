/**
 * Typer för den programmatiska SEO-landningssidan.
 *
 * Varje sida lever som en JSON i `src/content/seo-landings/{family}/{slug}.json`
 * och följer `SeoLandingContent`. Innehållet produceras av
 * `scripts/seo/generate-landings.ts` (LLM vid build-time) eller kan skrivas
 * för hand för demo-sidor.
 */

export type SeoLandingFamily =
  | "city"
  | "usecase"
  | "industry"
  | "ai"
  | "compare"
  | "city-usecase";

export interface SeoLandingFaqEntry {
  q: string;
  a: string;
}

export interface SeoLandingContentBlock {
  heading: string;
  body: string;
}

export interface SeoLandingInternalLink {
  href: string;
  label: string;
}

export interface SeoLandingCta {
  /** Text som förifylls i builder-promten vid klick. */
  prompt: string;
  /** Knapptext (CTA). */
  buttonLabel: string;
}

export interface SeoLandingContent {
  family: SeoLandingFamily;
  /** URL-slug. För `city-usecase` är det `"stockholm/webshop"` (path-segment). */
  slug: string;
  /** <title>-innehåll, ska innehålla primär keyword. */
  title: string;
  /** Meta-description, 150–160 tecken. */
  metaDescription: string;
  /** H1, ska matcha sökintent men får skilja sig lätt från title. */
  h1: string;
  /** Kort en-meningslös under-rubrik till hero. */
  heroSub: string;
  /** 2–3 korta stycken, svar-först, unika per sida. */
  introParagraphs: string[];
  /** 3–5 innehållsblock med unik rubrik och kropp. */
  contentBlocks: SeoLandingContentBlock[];
  /** 5–7 vanliga frågor + svar. Renderas som accordion + FAQPage JSON-LD. */
  faq: SeoLandingFaqEntry[];
  /** Lokal/bransch-specifik kontext (exempel, siffror, referenser). */
  localOrIndustryContext?: string;
  /** 3–8 interna länkar till relaterade SEO-landningar. */
  internalLinks: SeoLandingInternalLink[];
  /** Primär CTA: text + prompt till builder. */
  cta: SeoLandingCta;
  /** ISO-datum när content genererades. */
  generatedAt: string;
  /** Modell som producerade texten (eller "manual" för hand-skriven). */
  model: string;
}

/** Data för att bygga en sida i city-familjen (före LLM-generering). */
export interface SeoCityConfig {
  slug: string;
  label: string;
  /** Län, för kontext i promten. */
  region: string;
  /** Invånarantal (SCB 2024 ungefärligt). */
  population: number;
}

export interface SeoUsecaseConfig {
  slug: string;
  /** Kort label ("Webshop"). */
  label: string;
  /** Sökordet vi optimerar för ("skapa hemsida webshop"). */
  targetKeyword: string;
  /** Vilka företag/aktörer använder detta ("en handlare som säljer kläder online"). */
  audience: string;
}

export interface SeoIndustryConfig {
  slug: string;
  label: string;
  /** Sökordet vi optimerar för ("hemsida för frisör"). */
  targetKeyword: string;
  /** Typiska tjänster/kunder för branschen. */
  typicalServices: string;
}

export interface SeoAiConfig {
  slug: string;
  label: string;
  /** Sökordet vi optimerar för ("bygga hemsida med ai"). */
  targetKeyword: string;
  /** Vad användaren egentligen frågar ("kan AI bygga min hemsida åt mig?"). */
  searchIntent: string;
}

export interface SeoCompareConfig {
  slug: string;
  label: string;
  /** Sökordet vi optimerar för ("alternativ till wix"). */
  targetKeyword: string;
  /** Kort beskrivning av konkurrenten. */
  competitorSummary: string;
}

export interface SeoCityUsecaseConfig {
  slug: string; // "stockholm/webshop"
  citySlug: string;
  usecaseSlug: string;
  cityLabel: string;
  usecaseLabel: string;
  targetKeyword: string; // "hemsida webshop stockholm"
}
