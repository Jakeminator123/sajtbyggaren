/**
 * Serialiserar `WizardAnswers` till det kontrakt som `/api/prompt`
 * (utökad med `discovery`) skickar vidare till
 * `scripts/prompt_to_project_input.py --discovery <fil>`.
 *
 * Mål:
 *   1. Stabilt JSON-schema som backend kan validera (Pydantic eller
 *      Zod-spegling).
 *   2. Strippa tomma fält så payloaden blir liten och så att Python-
 *      resolvern kan skilja "ej ifyllt" från "explicit tomsträng".
 *   3. Generera en kort, rik `prompt`-text som befintlig LLM-extraktion
 *      kan använda som fallback om vissa fält saknas — det följer
 *      mönstret i `prompt-builder.tsx` där originalprompten alltid
 *      bevaras som `rawPrompt`.
 *
 * **schemaVersion 2 (2026-05-22):** Lägger till ett `directives`-block med
 * direkt strukturerad data (scaffoldHint, variantHint, pageCount,
 * requestedCapabilities, conversionGoals, tone, brand, notesForPlanner)
 * så backend kan hoppa över `briefModel`-extraktion när data redan finns.
 * Specificerat i `docs/contracts/wizard-discovery.v2.md`. Bakåtkompatibelt:
 * `directives` är optionellt, backend faller tillbaka till v1-flödet
 * (LLM-extraktion på `rawPrompt` + `composeMasterPrompt`-text) när det saknas.
 */

import type { AssetRef } from "@/lib/asset-store/types";

import {
  fallbackDiscoveryOptions,
  resolveContentBranchFromOptions,
  resolveScaffoldHintFromOptions,
  validateDiscoveryCategoryIds,
} from "./discovery-options";
import type { discoveryOption } from "./discovery-options";
import { sectionTreatmentSpecsForScaffold } from "./treatment-options";
import {
  branchForFamily,
  BUSINESS_FAMILIES,
  deriveEffectiveScaffoldHint,
  findFunctionChoice,
  findVibe,
} from "./wizard-constants";
import type { WizardAnswers } from "./wizard-types";

/**
 * Direkt strukturerad data som backend kan använda utan LLM-extraktion.
 * Speglar `WizardDirectives` i `docs/contracts/wizard-discovery.v2.md`.
 *
 * Alla fält utöver `language` är optional eftersom strippEmpty rensar
 * tomma listor och strängar — backend behandlar `undefined` som "fanns inte
 * i wizardin, gör som du gjorde i v1".
 */
export type WizardDirectives = {
  language: "sv" | "en";
  scaffoldHint: string;
  variantHint?: string;
  /**
   * Hero-layout-override för startsidan. När satt skickas det till
   * `build_site.py:_hero_style_for` (via dossier.directives) och vinner
   * över både vibe-default och variant.id-mapping. Tre tillåtna värden:
   *
   * - `gradient`: full-width gradient-panel med vänsterstaplade
   *   element (klassisk minimal-look)
   * - `centered`: text-centrerat med generös vertikal rytm (lugnt och
   *   editorialt)
   * - `split`: två-kolumns layout med hero-bild eller färgblock
   *   (editorialt, produktfokus)
   */
  layoutHint?: "gradient" | "centered" | "split";
  pageCount?: number;
  businessType?: string;
  requestedCapabilities?: string[];
  conversionGoals?: string[];
  tone?: {
    primary?: string;
    secondary?: string[];
    avoid?: string[];
  };
  brand?: {
    primaryColorHex?: string;
    accentColorHex?: string;
    designStyle?: string;
  };
  /**
   * Strukturerad lista över unika säljpunkter. Speglar fri-text-versionen
   * som finns i `notesForPlanner` men ger backend en deterministisk källa
   * för att rendera USP-chips i hero (`build_site.py:_render_hero_block`
   * i en kommande pass) utan att parsea text. Max 4 punkter — fler
   * skulle göra hero-blocket otydligt visuellt.
   */
  uniqueSellingPoints?: string[];
  /**
   * Extra media-assets utöver logo/hero/gallery (de tre primära går
   * fortfarande via `answers.assets`). Backend renderar varje fält i en
   * specifik HTML-position — se `docs/contracts/wizard-discovery.v2.md`
   * sektionen "Media-fält → render-target" för exakt mapping:
   *
   *   - `favicon`         → `<link rel="icon">` + `<link rel="apple-touch-icon">`
   *   - `ogImage`         → `<meta property="og:image">` + Twitter Card
   *   - `backgroundVideo` → `<video autoPlay loop muted playsInline>`
   *                         i hero-sektionen (poster=hero-bild som fallback)
   *
   * Värdet är en `AssetRef` (samma form som `answers.assets.logo` osv.).
   * Asset-bytes ligger redan i AssetStore (lokal disk eller Vercel Blob);
   * `sourceUrl`-fältet pekar mot publik URL när VercelBlobAssetStore
   * är aktiv. Backend ska föredra `sourceUrl` framför disk-lookup.
   *
   * Backend (Jakob M2): persistera till `dossier.media.<role>` så
   * build_site.py kan läsa det vid render. Schema-tillägg krävs i
   * `governance/schemas/project-input.schema.json`.
   */
  /**
   * ``null`` är en **tombstone** som signalerar att operatören har
   * tagit bort en tidigare uppladdad asset i rollen. Backend måste
   * rensa motsvarande fält i ``project_input.media`` när tombstone
   * skickas (annars dyker borttagna bilder upp igen vid rebuild).
   */
  media?: {
    favicon?: AssetRef | null;
    ogImage?: AssetRef | null;
    backgroundVideo?: AssetRef | null;
  };
  /**
   * Operator-pin per section för design-treatments (Phase 3, ADR
   * 0031). Speglar `directives.sectionTreatments` i Project
   * Input.schema.json. Tom = inga overrides; varje section kör sin
   * variant- eller section-default.
   *
   * Resolve-ordning (backend): operator-pin (denna map) >
   * variant-default (`_SECTION_TREATMENTS_BY_VARIANT`) >
   * section-default. Wizardens `treatment-options.ts` exponerar
   * exakt samma katalog som schemats enum.
   */
  sectionTreatments?: Record<string, string>;
  notesForPlanner?: string;
};

export type DiscoveryPayload = {
  /**
   * Schema-version så backend kan utveckla kontraktet utan att bryta
   * klienten. Heter `schemaVersion` (inte `version`) — `test_viewser_files`
   * förbjuder client-payload med `version: z` på prompt-routen eftersom
   * det fältet tillhör Project Input-meta-sidecar (`*.meta.json`).
   *
   * `1` = legacy (ingen `directives`). `2` = inkluderar `directives`-block.
   * Frontend bumpar alltid till `2` när `buildDiscoveryPayload` används
   * eftersom helpern alltid härleder directives — men backend måste
   * tolerera att `directives` är `undefined` om någon framtida caller
   * skulle skicka bara `rawPrompt + answers` direkt.
   */
  schemaVersion: 1 | 2;
  /** Free-form pitch som operatorn skrev i prompt-builder-input:en. */
  rawPrompt: string;
  /** Computed branch from governance options; backend double-checks it. */
  contentBranch: ReturnType<typeof resolveContentBranchFromOptions>;
  /** Generic runtime-safe hint. Backend resolver decides final scaffold. */
  scaffoldHint: string;
  /** Trimmed copy of all wizard answers — tomma fält strippade. */
  answers: WizardAnswers;
  /**
   * v2-direktivblock. Optional för bakåtkompatibilitet — om det saknas
   * faller backend tillbaka till LLM-extraktion via `briefModel`.
   */
  directives?: WizardDirectives;
};

/**
 * Tar bort tomma strängar, tomma arrays och tomma objekt rekursivt.
 *
 * UNDANTAG: ``preserveEmpty``-listan med nyckelnamn behåller sina
 * tomma värden. Detta används för borttagnings-tombstones i
 * ``assets.*`` och ``media.*`` — när operatören tar bort en uppladdad
 * bild (logo, hero, favicon, OG, video) blir state ``null``, och vi
 * MÅSTE skicka ``null`` till backend så den vet att rensa
 * ``project_input.brand.logo`` osv. Strippas ``null`` bort tror
 * backend att operatören "inte angav något" och behåller en eventuell
 * tidigare logo — vilket är den klassiska "borttagen bild dyker upp
 * igen"-buggen.
 *
 * Gallery (lista) behandlas likadant: tom array ``[]`` ska skickas
 * som ``[]`` så backend rensar ``project_input.gallery``.
 */
const PRESERVE_EMPTY_KEYS: ReadonlySet<string> = new Set([
  "logo",
  "heroImage",
  "gallery",
  "favicon",
  "ogImage",
  "backgroundVideo",
]);

function stripEmpty<T>(value: T): T {
  if (Array.isArray(value)) {
    const next = value
      .map((item) => stripEmpty(item))
      .filter((item) => {
        if (item === null || item === undefined) return false;
        if (typeof item === "string") return item.trim().length > 0;
        if (typeof item === "object" && Object.keys(item).length === 0)
          return false;
        return true;
      });
    return next as unknown as T;
  }
  if (value && typeof value === "object") {
    const next: Record<string, unknown> = {};
    for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
      const cleaned = stripEmpty(raw);
      const preserve = PRESERVE_EMPTY_KEYS.has(key);
      if (cleaned === null || cleaned === undefined) {
        if (preserve) {
          next[key] = null;
        }
        continue;
      }
      if (typeof cleaned === "string" && cleaned.trim().length === 0) {
        if (preserve) {
          next[key] = cleaned;
        }
        continue;
      }
      if (Array.isArray(cleaned) && cleaned.length === 0) {
        if (preserve) {
          next[key] = cleaned;
        }
        continue;
      }
      if (
        typeof cleaned === "object" &&
        !Array.isArray(cleaned) &&
        Object.keys(cleaned).length === 0
      ) {
        if (preserve) {
          next[key] = cleaned;
        }
        continue;
      }
      next[key] = cleaned;
    }
    return next as T;
  }
  return value;
}

/**
 * Speglar `detect_language` från `packages/generation/brief/extract.py` —
 * cascade: svenska stop-ord → engelska stop-ord → å/ä/ö-detektion → "sv".
 * Algoritmen matchar inte byte-för-byte (Python äger source of truth),
 * men ger backend ett deterministiskt språkförslag som den kan validera
 * eller skriva över utan att behöva köra LLM-extraktion bara för språk.
 */
const SWEDISH_HINTS = new Set([
  "skapa",
  "för",
  "hemsida",
  "sajt",
  "och",
  "att",
  "med",
  "på",
  "elektriker",
  "rörmokare",
  "tandläkare",
  "restaurang",
  "i",
  "av",
  "ett",
  "en",
  "kontakt",
  "tjänster",
  "om",
  "oss",
]);
const ENGLISH_HINTS = new Set([
  "the",
  "a",
  "an",
  "and",
  "or",
  "but",
  "in",
  "on",
  "at",
  "for",
  "of",
  "with",
  "to",
  "from",
  "is",
  "are",
  "was",
  "were",
  "be",
  "been",
  "create",
  "build",
  "make",
  "need",
  "want",
  "website",
  "site",
  "page",
  "store",
  "shop",
  "my",
  "our",
  "your",
]);
const SWEDISH_CHARS = /[åäöÅÄÖ]/;

function detectLanguage(prompt: string): "sv" | "en" {
  const tokens = new Set(
    prompt
      .split(/\s+/)
      .map((t) => t.toLowerCase().replace(/[,.!?:;]/g, ""))
      .filter(Boolean),
  );
  for (const t of tokens) {
    if (SWEDISH_HINTS.has(t)) return "sv";
  }
  for (const t of tokens) {
    if (ENGLISH_HINTS.has(t)) return "en";
  }
  if (SWEDISH_CHARS.test(prompt)) return "sv";
  return "sv";
}

/**
 * Mappar fri CTA-text till backend-slugs (`conversion_goals`-enum i `SiteBrief`).
 * Multipla CTA:s i samma sträng (t.ex. "Boka eller ring oss") ger flera slugs.
 * Returnerar en deduplicerad lista. Tom array om inget matchar — backend
 * faller tillbaka till sin egen extraktion.
 */
const CTA_KEYWORD_MAP: ReadonlyArray<{
  slug: string;
  keywords: readonly string[];
}> = [
  { slug: "booking", keywords: ["bok", "book", "reserv"] },
  { slug: "call", keywords: ["ring", "call", "tel ", "telefon"] },
  {
    slug: "quote-request",
    keywords: ["offert", "quote", "rfp", "prisförfrågan", "begär"],
  },
  {
    slug: "newsletter-signup",
    keywords: ["nyhetsbrev", "newsletter", "prenumer", "subscribe"],
  },
  { slug: "purchase", keywords: ["köp", "buy", "shop", "beställ", "order"] },
  {
    slug: "contact",
    keywords: ["kontakt", "contact", "hör av", "skriv", "mejla", "email"],
  },
];

function mapCtaToConversionGoals(cta: string): string[] {
  const lower = cta.toLowerCase();
  const found: string[] = [];
  for (const { slug, keywords } of CTA_KEYWORD_MAP) {
    if (keywords.some((kw) => lower.includes(kw))) {
      if (!found.includes(slug)) found.push(slug);
    }
  }
  return found;
}

/**
 * Härleder ett `WizardDirectives`-block från färdig-ifylld `WizardAnswers`.
 *
 * Returnerar alltid ett objekt med minst `language` och `scaffoldHint`.
 * Övriga fält inkluderas bara när wizardin har ett tydligt värde — det är
 * skillnaden mot att skicka "tomsträng" som skulle få backend att tro
 * att operatören explicit valde tomt. `stripEmpty`-pipeline:n rensar bort
 * resultat:et till slut så vi inte skickar tomma listor/objekt.
 */
export function deriveWizardDirectives(
  rawPrompt: string,
  answers: WizardAnswers,
  scaffoldHint: string,
): WizardDirectives {
  const directives: WizardDirectives = {
    language: detectLanguage(rawPrompt),
    scaffoldHint,
  };

  // variantHint — när operatorn valt en vibe. Tomsträng = "default per
  // family", och backend ska INTE få den som directive (annars kan den
  // misslyckas att hitta variant-mapping).
  if (answers.vibe.vibeId.trim()) {
    directives.variantHint = answers.vibe.vibeId.trim();
  }

  // pageCount — `mustHave[]` listar sidor UTÖVER startsidan (Start är
  // alltid med). En naiv ansats: pageCount = mustHave.length + 1.
  // Backend respekterar redan brief.pageCount (B138-fixen) så det här
  // sätter en explicit övre gräns på route-emission.
  if (answers.mustHave.length > 0) {
    directives.pageCount = answers.mustHave.length + 1;
  }

  // businessType — använd familje-id som slug. Backend kan vidareöversätta
  // till en mer specifik slug ("painter", "dental-clinic") via heuristik
  // på `rawPrompt` om de vill, men familje-id räcker för scaffold-val.
  if (answers.businessFamily) {
    directives.businessType = answers.businessFamily;
  }

  // requestedCapabilities — slå upp capability per selectedFunction.
  // Tomma och okända IDs hoppas över; dedupe sker via accumulator.
  if (answers.selectedFunctions.length > 0) {
    const capabilities: string[] = [];
    for (const fnId of answers.selectedFunctions) {
      const choice = findFunctionChoice(fnId);
      if (choice?.capability && !capabilities.includes(choice.capability)) {
        capabilities.push(choice.capability);
      }
    }
    if (capabilities.length > 0) {
      directives.requestedCapabilities = capabilities;
    }
  }

  // conversionGoals — keyword-mappa primaryCta. Tom om inget matchar.
  if (answers.primaryCta.trim()) {
    const goals = mapCtaToConversionGoals(answers.primaryCta);
    if (goals.length > 0) {
      directives.conversionGoals = goals;
    }
  }

  // tone — första toneTag som primary, resten som secondary, wordsToAvoid
  // split:as på komma till tone.avoid[]. Backend kan vidare merge:a med
  // briefModel-output om de har en extra tone-keyword som inte fanns i wizardin.
  const tone: NonNullable<WizardDirectives["tone"]> = {};
  if (answers.brand.toneTags.length > 0) {
    tone.primary = answers.brand.toneTags[0];
    if (answers.brand.toneTags.length > 1) {
      tone.secondary = answers.brand.toneTags.slice(1);
    }
  }
  if (answers.brand.wordsToAvoid.trim()) {
    const avoid = answers.brand.wordsToAvoid
      .split(/[,;]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (avoid.length > 0) {
      tone.avoid = avoid;
    }
  }
  if (Object.keys(tone).length > 0) {
    directives.tone = tone;
  }

  // brand — färgerna skickas alltid när de är non-empty. `useCustomColors`
  // är ett UI-flagg som styr om operatorn AVSIKTLIGT valde att skriva över
  // variantens default; här inkluderar vi färgerna i directives utan att
  // bry oss om flaggan (backend ser dem och kan välja policy själv).
  const brand: NonNullable<WizardDirectives["brand"]> = {};
  if (answers.brand.primaryColorHex.trim()) {
    brand.primaryColorHex = answers.brand.primaryColorHex.trim();
  }
  if (answers.brand.accentColorHex.trim()) {
    brand.accentColorHex = answers.brand.accentColorHex.trim();
  }
  if (answers.brand.designStyle.trim()) {
    brand.designStyle = answers.brand.designStyle.trim();
  }
  if (Object.keys(brand).length > 0) {
    directives.brand = brand;
  }

  // layoutHint — operator-override av hero-layout. Värdet kommer från
  // visual-step (WizardVibe.layoutHint). Tom sträng = "automatic" och
  // skickas inte vidare; backend härleder då layout från vibe + variant.
  if (
    answers.vibe.layoutHint === "gradient" ||
    answers.vibe.layoutHint === "centered" ||
    answers.vibe.layoutHint === "split"
  ) {
    directives.layoutHint = answers.vibe.layoutHint;
  }

  // uniqueSellingPoints — strukturerad lista. Speglar samma data som
  // går in i notesForPlanner-texten nedan, men i strukturerad form så
  // backend kan rendera dem som hero-chips utan att parsea text.
  // Trimmar och tar bort tomma; kapar vid 4 så hero-layouten inte
  // svämmar över.
  if (answers.uniqueSellingPoints.length > 0) {
    const structuredUsps = answers.uniqueSellingPoints
      .map((u) => u.trim())
      .filter(Boolean)
      .slice(0, 4);
    if (structuredUsps.length > 0) {
      directives.uniqueSellingPoints = structuredUsps;
    }
  }

  // notesForPlanner — concat:ar specialRequests + uniqueSellingPoints
  // som fritext. Behålls även när directives.uniqueSellingPoints satt
  // ovan så v1-konsumenter (backend som ännu inte läser den strukturerade
  // listan) fortfarande får informationen.
  const notesParts: string[] = [];
  if (answers.specialRequests.trim()) {
    notesParts.push(answers.specialRequests.trim());
  }
  if (answers.uniqueSellingPoints.length > 0) {
    const usps = answers.uniqueSellingPoints
      .map((u) => u.trim())
      .filter(Boolean);
    if (usps.length > 0) {
      notesParts.push(`USP: ${usps.join(", ")}`);
    }
  }
  if (notesParts.length > 0) {
    directives.notesForPlanner = notesParts.join(" — ");
  }

  // Extra media — favicon / ogImage / backgroundVideo. Vi exponerar dem
  // även i `directives.media` (utöver `answers.media`) så Jakob bara
  // behöver titta i `directives` för all strukturerad render-data.
  //
  // VIKTIGT: vi skickar alltid alla tre fälten — med ``null`` som
  // explicit tombstone när operatören har tagit bort en bild.
  // ``stripEmpty`` är konfigurerad att bevara ``null`` för dessa
  // roller (se ``PRESERVE_EMPTY_KEYS``), så backend kan särskilja
  // "inte angiven" (fältet saknas helt) från "explicit borttagen"
  // (fältet är ``null``). Utan detta dyker en borttagen favicon upp
  // igen vid nästa rebuild eftersom backend behåller en eventuell
  // tidigare lagrad ref.
  const media: NonNullable<WizardDirectives["media"]> = {
    favicon: answers.media.favicon ?? null,
    ogImage: answers.media.ogImage ?? null,
    backgroundVideo: answers.media.backgroundVideo ?? null,
  };
  directives.media = media;

  // sectionTreatments — operator-pin per section. Tomt = ingen
  // override; backend resolve-ordning faller då tillbaka på
  // variant-default och section-default. Vi normaliserar (trim) OCH
  // filtrerar bort pins för sections som inte hör till aktiv scaffold
  // — annars kan ett scaffold-byte i wizardin lämna kvar "ghost-pins"
  // som schemat avvisar (per-section enum) eller som backend skickar
  // vidare till en renderer som aldrig mountas.
  const allowedSectionIds = new Set<string>(
    sectionTreatmentSpecsForScaffold(scaffoldHint).map((spec) => spec.id),
  );
  const sectionPins: Record<string, string> = {};
  for (const [sectionId, treatmentId] of Object.entries(
    answers.vibe.sectionTreatments ?? {},
  )) {
    const trimmedSection = sectionId.trim();
    const trimmedTreatment = treatmentId.trim();
    if (
      trimmedSection &&
      trimmedTreatment &&
      allowedSectionIds.has(trimmedSection)
    ) {
      sectionPins[trimmedSection] = trimmedTreatment;
    }
  }
  if (Object.keys(sectionPins).length > 0) {
    directives.sectionTreatments = sectionPins;
  }

  return directives;
}

export function buildDiscoveryPayload(
  rawPrompt: string,
  answers: WizardAnswers,
  discoveryOptions: readonly discoveryOption[] = fallbackDiscoveryOptions(),
): DiscoveryPayload {
  if (!validateDiscoveryCategoryIds(answers.siteType, discoveryOptions)) {
    throw new Error("Okänd kategori i discovery-svaren.");
  }
  // W2: fall tillbaka till businessFamily-branch om operatören valt
  // familj men inte sub-kategori, så backend ser samma branch som UI:t.
  const branch = resolveContentBranchFromOptions(
    answers.siteType,
    discoveryOptions,
    answers.businessFamily ? branchForFamily(answers.businessFamily) : undefined,
  );

  // Scaffold hint — `deriveEffectiveScaffoldHint` använder family som
  // primär signal men låter sub-kategorin uppgradera scaffolden när den
  // pekar mot en mer specifik runtime-scaffold (t.ex. "service"-family
  // + "legal"-sub-cat → professional-services). När varken family eller
  // sub-cat är vald faller vi tillbaka till governance-resolvern så
  // backend kan se vad UI:t faktiskt visar för varje sub-cat-list.
  const family = BUSINESS_FAMILIES.find((f) => f.id === answers.businessFamily);
  const scaffoldHint =
    family || answers.siteType.length > 0
      ? deriveEffectiveScaffoldHint(family, answers.siteType)
      : resolveScaffoldHintFromOptions(answers.siteType, discoveryOptions);

  const directives = deriveWizardDirectives(rawPrompt, answers, scaffoldHint);

  // Strippa tomma fält i directives så payloaden förblir liten. `stripEmpty`
  // tar bort tomma arrays/objekt rekursivt; det matchar v1-strategin för
  // `answers`-blocket. Resultatet kan vara ett directives-objekt med bara
  // `language` + `scaffoldHint` om operatorn knappt fyllde i något.
  const cleanedDirectives = stripEmpty(directives);

  // schemaVersion = 2. Backend persisterar deterministiskt
  // `directives.layoutHint`, `uniqueSellingPoints`, `media` och
  // (Phase 3, ADR 0031) `sectionTreatments` till Project Input enligt
  // kontraktet i `docs/contracts/wizard-discovery.v2.md`. Återstående
  // directive-fält (tone, variantHint, brand, requestedCapabilities)
  // är fortfarande primärt LLM-kompletterat via briefModel; backend
  // tolererar dem i payloaden men använder dem ännu inte
  // deterministiskt.
  return {
    schemaVersion: 2,
    rawPrompt: rawPrompt.trim(),
    contentBranch: branch,
    scaffoldHint,
    answers: stripEmpty(answers),
    directives: cleanedDirectives,
  };
}

/**
 * Komponerar en rik, sektion-baserad master-prompt som skickas som
 * `prompt`-fältet till `/api/prompt`. Backend kör briefModel med den
 * här texten som user-message — den behöver innehålla maximal kontext
 * för att Site Brief-extraktionen ska få rätt på `tone`, `target_audience`,
 * `requested_capabilities`, `conversion_goals`, `services_mentioned`,
 * `notes_for_planner` osv. (`packages/generation/brief/extract.py`
 * `SiteBrief`).
 *
 * Operatörens originaltext bevaras i toppen ("Operatörens beskrivning")
 * och även i `discovery.rawPrompt` så att vi alltid kan referera till
 * den orörda prompten. Discovery Resolver körs efter LLM-extraktionen
 * och väger in wizardens svar deterministiskt — master-prompten är
 * därför primärt till för att hjälpa LLM att fylla i fält som wizarden
 * inte täcker.
 */
function joinNonEmpty(items: string[], separator = ", "): string {
  return items
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .join(separator);
}

function listSection(title: string, items: string[]): string | null {
  const joined = joinNonEmpty(items);
  if (!joined) return null;
  return `${title}: ${joined}.`;
}

function bulletSection(title: string, lines: string[]): string | null {
  const cleaned = lines
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  if (cleaned.length === 0) return null;
  const bullets = cleaned.map((line) => `  - ${line}`).join("\n");
  return `${title}:\n${bullets}`;
}

function formatService(item: {
  name: string;
  price?: string;
  description?: string;
  durationMinutes?: number;
}): string {
  const parts: string[] = [item.name.trim()];
  if (item.price?.trim()) parts.push(`(${item.price.trim()})`);
  if (typeof item.durationMinutes === "number" && item.durationMinutes > 0) {
    parts.push(`(${item.durationMinutes} min)`);
  }
  const description = item.description?.trim();
  if (description) parts.push(`— ${description}`);
  return parts.join(" ");
}

export function composeMasterPrompt(
  rawPrompt: string,
  answers: WizardAnswers,
  discoveryOptions: readonly discoveryOption[] = fallbackDiscoveryOptions(),
): string {
  const sections: string[] = [];
  const branch = resolveContentBranchFromOptions(
    answers.siteType,
    discoveryOptions,
    answers.businessFamily ? branchForFamily(answers.businessFamily) : undefined,
  );
  const categoryLabels = answers.siteType
    .map((id) => discoveryOptions.find((c) => c.id === id)?.label ?? id)
    .filter(Boolean);

  // 1. Operatörens ursprungliga pitch — bevarad ordagrant så briefModel
  // alltid har originalspråk/tonläge att luta sig mot. Står först så
  // LLM:n läser den som primär källtext.
  const cleanedRaw = rawPrompt.trim();
  if (cleanedRaw) {
    sections.push(`[Operatörens beskrivning]\n${cleanedRaw}`);
  }

  // 2. Företag / kontakt — formateras så LLM kan extrahera
  // companyName, contactPhone, contactEmail, contactAddress, locationHint.
  const companyLines: string[] = [];
  if (answers.companyName.trim())
    companyLines.push(`Namn: ${answers.companyName.trim()}`);
  if (answers.offer.trim())
    companyLines.push(`Vad vi gör: ${answers.offer.trim()}`);
  if (answers.existingSite.trim())
    companyLines.push(`Befintlig hemsida: ${answers.existingSite.trim()}`);
  if (answers.contact.phone.trim())
    companyLines.push(`Telefon: ${answers.contact.phone.trim()}`);
  if (answers.contact.email.trim())
    companyLines.push(`E-post: ${answers.contact.email.trim()}`);
  if (answers.contact.address.trim())
    companyLines.push(`Adress: ${answers.contact.address.trim()}`);
  if (answers.contact.openingHours.trim())
    companyLines.push(`Öppettider: ${answers.contact.openingHours.trim()}`);
  if (companyLines.length > 0) {
    sections.push(`[Företag och kontakt]\n${companyLines.join("\n")}`);
  }

  // 3. Kategori / scaffold-signal — hjälper briefModel pinpoint:a
  // businessTypeGuess utan att gissa fritt från prompten.
  const familyMeta = BUSINESS_FAMILIES.find(
    (f) => f.id === answers.businessFamily,
  );
  if (familyMeta || categoryLabels.length > 0) {
    const verksamhetLines: string[] = [];
    if (familyMeta) {
      verksamhetLines.push(`Verksamhetsfamilj: ${familyMeta.label}.`);
      verksamhetLines.push(`Scaffold-hint: ${familyMeta.scaffoldHint}.`);
    }
    if (categoryLabels.length > 0) {
      verksamhetLines.push(`Sub-kategorier: ${categoryLabels.join(", ")}.`);
    }
    verksamhetLines.push(`Content-branch: ${branch}.`);
    sections.push(`[Verksamhetstyp]\n${verksamhetLines.join("\n")}`);
  }

  // 4. Innehållsblock — varje wizard-gren bidrar med sina egna
  // datapunkter (tjänster/produkter/meny/projekt). Allt formateras
  // som tydliga listor så `services_mentioned` extraheras ordagrant.
  const contentLines: string[] = [];
  if (answers.services.length > 0) {
    const services = answers.services.map(formatService);
    const bullet = bulletSection("Tjänster", services);
    if (bullet) contentLines.push(bullet);
  }
  if (answers.products.length > 0) {
    const products = answers.products.map(formatService);
    const bullet = bulletSection("Produkter", products);
    if (bullet) contentLines.push(bullet);
  }
  if (answers.menuItems.length > 0) {
    const menu = answers.menuItems.map(formatService);
    const bullet = bulletSection("Meny", menu);
    if (bullet) contentLines.push(bullet);
  }
  if (answers.projects.length > 0) {
    const projects = answers.projects.map((project) => {
      const parts: string[] = [project.name.trim()];
      if (project.client?.trim()) parts.push(`(${project.client.trim()})`);
      if (project.description?.trim())
        parts.push(`— ${project.description.trim()}`);
      return parts.join(" ");
    });
    const bullet = bulletSection("Projekt och case", projects);
    if (bullet) contentLines.push(bullet);
  }
  if (answers.team.length > 0) {
    const team = answers.team.map((member) => {
      const parts: string[] = [member.name.trim()];
      if (member.role?.trim()) parts.push(`(${member.role.trim()})`);
      if (member.bio?.trim()) parts.push(`— ${member.bio.trim()}`);
      return parts.join(" ");
    });
    const bullet = bulletSection("Team", team);
    if (bullet) contentLines.push(bullet);
  }
  const cuisine = listSection("Kök/stil", [...answers.cuisineTags]);
  if (cuisine) contentLines.push(cuisine);
  const dietary = listSection("Kostalternativ", [...answers.dietaryTags]);
  if (dietary) contentLines.push(dietary);
  if (answers.priceTier.trim())
    contentLines.push(`Prisnivå: ${answers.priceTier.trim()}.`);
  if (answers.bookingUrl.trim())
    contentLines.push(`Bokningslänk: ${answers.bookingUrl.trim()}.`);
  const usps = listSection(
    "Unika säljpunkter (USP)",
    answers.uniqueSellingPoints,
  );
  if (usps) contentLines.push(usps);
  if (contentLines.length > 0) {
    sections.push(`[Innehåll]\n${contentLines.join("\n")}`);
  }

  // 5. Story — `company.story` / `/om-oss`-copy hämtas härifrån, men
  // vision och history hjälper LLM att forma notesForPlanner.
  const storyLines: string[] = [];
  if (answers.aboutText.trim())
    storyLines.push(`Om oss: ${answers.aboutText.trim()}`);
  if (answers.historyText.trim())
    storyLines.push(`Historia: ${answers.historyText.trim()}`);
  if (answers.visionText.trim())
    storyLines.push(`Vision och mission: ${answers.visionText.trim()}`);
  if (answers.contactIntroText.trim())
    storyLines.push(`Kontaktsidans intro: ${answers.contactIntroText.trim()}`);
  if (storyLines.length > 0) {
    sections.push(`[Story]\n${storyLines.join("\n\n")}`);
  }

  // 6. Sidor + CTA + målgrupp — direkt signal till requested_capabilities
  // (must-have-listan), conversion_goals (CTA) och target_audience.
  const pageLines: string[] = [];
  if (answers.mustHave.length > 0) {
    pageLines.push(`Sidor att bygga: ${answers.mustHave.join(", ")}.`);
  }
  if (answers.selectedFunctions.length > 0) {
    const functionLabels = answers.selectedFunctions
      .map((id) => {
        const choice = findFunctionChoice(id);
        if (!choice) return null;
        const cap = choice.capability ? ` (${choice.capability})` : "";
        return `${choice.label}${cap}`;
      })
      .filter((s): s is string => Boolean(s));
    if (functionLabels.length > 0) {
      pageLines.push(`Önskade funktioner: ${functionLabels.join(", ")}.`);
    }
  }
  if (answers.primaryCta.trim()) {
    pageLines.push(`Primär call-to-action: "${answers.primaryCta.trim()}".`);
  }
  if (answers.targetAudience.trim()) {
    pageLines.push(`Målgrupp: ${answers.targetAudience.trim()}`);
  }
  if (answers.specialRequests.trim()) {
    pageLines.push(`Specialönskemål: ${answers.specialRequests.trim()}`);
  }
  if (pageLines.length > 0) {
    sections.push(`[Sidor och konvertering]\n${pageLines.join("\n")}`);
  }

  // 7. Ton / brand / visuell stil — driver tone[] och planner-input.
  const brandLines: string[] = [];
  const vibeMeta = answers.vibe.vibeId
    ? findVibe(answers.vibe.vibeId)
    : undefined;
  if (vibeMeta) {
    brandLines.push(`Vald vibe: ${vibeMeta.label} — ${vibeMeta.description}`);
  }
  if (answers.vibe.typographyFeel) {
    brandLines.push(`Typografi-känsla: ${answers.vibe.typographyFeel}.`);
  }
  if (answers.vibe.references.trim()) {
    brandLines.push(`Visuella referenser: ${answers.vibe.references.trim()}.`);
  }
  if (answers.brand.toneTags.length > 0) {
    brandLines.push(`Tonarter: ${answers.brand.toneTags.join(", ")}.`);
  }
  if (answers.brand.designStyle.trim()) {
    brandLines.push(`Visuell stil: ${answers.brand.designStyle.trim()}.`);
  }
  if (answers.brand.primaryColorHex.trim()) {
    const note = answers.vibe.useCustomColors ? " (operator-override)" : "";
    brandLines.push(
      `Primärfärg: ${answers.brand.primaryColorHex.trim()}${note}.`,
    );
  }
  if (answers.brand.accentColorHex.trim()) {
    const note = answers.vibe.useCustomColors ? " (operator-override)" : "";
    brandLines.push(
      `Accentfärg: ${answers.brand.accentColorHex.trim()}${note}.`,
    );
  }
  if (answers.brand.wordsToAvoid.trim()) {
    brandLines.push(
      `Undvik dessa ord och uttryck: ${answers.brand.wordsToAvoid.trim()}.`,
    );
  }
  if (brandLines.length > 0) {
    sections.push(`[Ton och visuellt språk]\n${brandLines.join("\n")}`);
  }
  if (answers.moodImages.length > 0) {
    const moodLines = answers.moodImages.map((m) => {
      const alt = m.alt.trim() || "Mood-referens";
      const subject = m.visionSubject ? ` — ${m.visionSubject}` : "";
      return `  - "${alt}"${subject}`;
    });
    sections.push(`[Mood-referenser]\n${moodLines.join("\n")}`);
  }

  // 8. Bilder och logotyp — operatorn har laddat upp bilder genom
  // AssetsStep. Bilderna finns inte i prompten som binärer (LLM kan
  // inte se dem här), men deras alt-text + placement + visionSubject
  // ger briefModel/planner värdefull kontext för copywriting:
  //   - "vi har en hero-bild av X" → hero-copy kan referera till den
  //   - "galleri visar interiör" → about-text kan haka i den
  // copy_operator_uploads i build_site.py kopierar de faktiska
  // binärerna till genererad sajts public/uploads/.
  const assetLines: string[] = [];
  if (answers.assets.logo) {
    const logo = answers.assets.logo;
    const altText = logo.alt.trim() || "Företagets logotyp";
    assetLines.push(
      `Logotyp uppladdad: "${altText}" (filtyp: ${logo.mimeType}).`,
    );
  }
  if (answers.assets.heroImage) {
    const hero = answers.assets.heroImage;
    const altText = hero.alt.trim() || "Hero-bild";
    const subjectNote = hero.visionSubject
      ? ` — visar ${hero.visionSubject}`
      : "";
    assetLines.push(`Hero-bild på startsidan: "${altText}"${subjectNote}.`);
  }
  if (answers.assets.gallery.length > 0) {
    assetLines.push("Galleribilder:");
    for (const item of answers.assets.gallery) {
      const altText = item.alt.trim() || "Foto";
      const placement = item.placement ?? "gallery";
      const subjectNote = item.visionSubject ? ` — ${item.visionSubject}` : "";
      assetLines.push(
        `  - "${altText}" (placering: ${placement})${subjectNote}`,
      );
    }
  }
  if (assetLines.length > 0) {
    sections.push(`[Bilder och visuella tillgångar]\n${assetLines.join("\n")}`);
  }

  // 8b. Extra media-assets (favicon/OG/video) — kräver backend-stöd för
  // full funktionalitet (se docs/backend-handoff.md). Vi skickar ändå
  // info till briefModel så den vet att operatören tänkt på dem.
  const mediaLines: string[] = [];
  if (answers.media.favicon) {
    mediaLines.push(
      `Favicon: "${answers.media.favicon.filename}" (kräver .ico-konvertering).`,
    );
  }
  if (answers.media.ogImage) {
    mediaLines.push(
      `OG-image: "${answers.media.ogImage.filename}" (kräver 1200×630 crop).`,
    );
  }
  if (answers.media.backgroundVideo) {
    mediaLines.push(
      `Bakgrundsvideo: "${answers.media.backgroundVideo.filename}" (${answers.media.backgroundVideo.mimeType}).`,
    );
  }
  if (mediaLines.length > 0) {
    sections.push(`[Extra media]\n${mediaLines.join("\n")}`);
  }

  // 9. Instruktioner till backend — kort sektion som hjälper planner-
  // modellen att förstå att operatorn redan kompletterat input via
  // wizarden, så LLM:n ska respektera given fakta och bara fylla hål.
  sections.push(
    [
      "[Instruktioner till AI]",
      "Operatorn har redan svarat på en discovery-wizard ovan — använd den givna fakta som sanning och hitta inte på företagsnamn, kontaktuppgifter eller tjänster som inte nämns.",
      "Skriv allt kund-vänt innehåll på samma språk som [Operatörens beskrivning].",
      "Generera unika, sajtspecifika texter — inga generiska platshållare ('Vår mission är att…').",
      "Lyft fram primär CTA och målgrupp på startsidan.",
      "Respektera tonarter och färger; undvik ord under 'Undvik'.",
      "Om [Bilder och visuella tillgångar] finns: referera dem i copy (t.ex. 'Som du ser i vår interiörbild...') och låt dem styra var hero/about/galleri-sektioner placeras.",
    ].join("\n"),
  );

  return sections.join("\n\n");
}

/**
 * Bevarad bakåtkompatibel alias — koden använder `composeMasterPrompt`
 * från och med denna ändring, men gamla tester och plan-skisser kan
 * fortfarande importera den enklare varianten. Returnerar samma text.
 */
export function composeEnrichedPrompt(
  rawPrompt: string,
  answers: WizardAnswers,
): string {
  return composeMasterPrompt(rawPrompt, answers);
}
