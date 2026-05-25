/**
 * Section design-treatments catalogue (UI-mirror).
 *
 * Speglar exakt enum-tabellen i
 * `governance/schemas/project-input.schema.json` directives.sectionTreatments
 * och Python-runtime-tabellen `_SECTION_TREATMENTS_BY_VARIANT` i
 * `scripts/build_site.py`. Wizardens visual-step läser denna fil för
 * att veta vilka treatments som finns per section, vilka som faktiskt
 * är relevanta för den valda scaffold/variant, och vilken som är
 * default.
 *
 * Mirror-strategin är medveten:
 * - Behovet att läsa katalogen i klienten utan ett extra API-anrop till
 *   `governance/schemas/...` motiverar en konstant.
 * - Schema ↔ Python-drift fångas av två tester:
 *     * `tests/test_project_input_schema.py` — schema-enum vs
 *       runtime-tabellen.
 *     * `tests/test_section_treatments_prompts.py` — planning-prompt
 *       vs runtime-tabellen.
 *   En framtida commit som lägger till en ny treatment i Python utan
 *   att uppdatera schemat fångas där.
 * - Schema ↔ TS-drift (denna fil) fångas av
 *     * `tests/test_treatment_options_ts_mirror.py` — parsar
 *       `SECTION_TREATMENT_SPECS` och jämför med schemat och
 *       `_SECTION_TREATMENTS_BY_VARIANT`.
 *   UI:t kommer fortsätta vara en strikt subset av schemat även om
 *   TS-mirror skulle släpa, vilket gör operator-pinningen säker
 *   (operatören kan inte välja en treatment som schemat avvisar).
 *
 * ADR 0032 förklarar resolve-ordningen: operator-pin (denna fil) >
 * variant-default (Python-runtime) > section-default. Visual-step
 * renderar disclosure:n så fort scaffolden har minst en section som
 * är registrerad här — operatören kan då alltid välja "Auto" för att
 * köra variant- eller section-default deterministiskt utan pin.
 */

/**
 * Snäv union över de section-id:n som har en treatment-katalog. Speglar
 * Python `_SECTION_RENDERERS`-nycklarna som har en treatment-dispatch
 * och schema-enums i `directives.sectionTreatments`. Om en ny section
 * läggs till på Python-sidan måste även denna typ utökas — TypeScript
 * fångar då alla call-sites som behöver uppdateras.
 */
export type WizardSectionId =
  | "selected-work-preview"
  | "treatment-list"
  | "practice-grid"
  | "expertise-areas"
  | "service-list";

/**
 * Snäv union över alla treatment-id:n som finns i schema-enum för
 * Phase 1+2. Drift mot schema/Python fångas av
 * `tests/test_project_input_schema.py` och `tests/test_section_-
 * treatments_prompts.py`; typen här ger dessutom compile-time-skydd
 * för UI-koden så en typo som ``"editor-stack"`` inte lyckas
 * passera till backend.
 */
export type SectionTreatmentId =
  | "editorial-stack"
  | "asymmetric-grid"
  | "marquee-row"
  | "minimal-rows"
  | "split-cards"
  | "numbered-stack"
  | "dense-grid"
  | "tabular"
  | "grouped"
  | "numbered-2col"
  | "tag-cluster"
  | "card-grid"
  | "alternating-rows"
  | "icon-strip";

export type SectionTreatmentOption = {
  /** Treatment-id som matchar Python `_SECTION_TREATMENTS_BY_VARIANT`. */
  id: SectionTreatmentId;
  /** Operator-vänlig svensk etikett. */
  label: string;
  /** Kort beskrivning som visas under etiketten. */
  description: string;
};

export type SectionTreatmentSpec = {
  /** Section-id som matchar Python `_SECTION_RENDERERS`. */
  id: WizardSectionId;
  /** Operator-vänlig svensk etikett. */
  label: string;
  /** Kort beskrivning av sektionen i förhållande till sajten. */
  description: string;
  /**
   * Vilka scaffolds som har den här sektionen aktiverad. Visual-step
   * filtrerar SECTION_TREATMENT_SPECS mot vald scaffold-hint för att
   * inte visa irrelevanta sektioner (t.ex. `selected-work-preview`
   * för en restaurant-bygge).
   */
  scaffolds: readonly string[];
  /** Section-default-treatment om varianten inte har en pin. */
  defaultTreatment: SectionTreatmentId;
  /** Tillgängliga treatments — speglar schema-enum exakt. */
  treatments: readonly SectionTreatmentOption[];
  /**
   * Variant → treatment-mapping speglar Python
   * `_SECTION_TREATMENTS_BY_VARIANT`. Används för att visa "auto"-
   * label:n som "Auto (variantens default: <treatment>)" så
   * operatören förstår vilken treatment som körs när inget pinnas.
   */
  variantDefaults: Readonly<Record<string, SectionTreatmentId>>;
};

export const SECTION_TREATMENT_SPECS: readonly SectionTreatmentSpec[] = [
  {
    id: "selected-work-preview",
    label: "Utvalda projekt (start)",
    description:
      "Förhandsvisning av portfolio på startsidan för agency-studio-scaffolds.",
    scaffolds: ["agency-studio"],
    defaultTreatment: "editorial-stack",
    treatments: [
      {
        id: "editorial-stack",
        label: "Editorial-stack",
        description:
          "Rolig magasin-känsla — fyra stora kort i rytmiskt staplad layout.",
      },
      {
        id: "asymmetric-grid",
        label: "Asymmetrisk grid",
        description:
          "Varannan ruta förskjuten vertikalt — bryter taktart, monochrome-look.",
      },
      {
        id: "marquee-row",
        label: "Marquee-row",
        description:
          "Horisontell scroll-snap-rail med sex kompakta kort — motion-led studioreel.",
      },
    ],
    variantDefaults: {
      "studio-monochrome": "asymmetric-grid",
      "bold-electric": "marquee-row",
    },
  },
  {
    id: "treatment-list",
    label: "Behandlingar (klinik)",
    description:
      "Behandlingsmeny på clinic-healthcare-startsidor och kliniksidor.",
    scaffolds: ["clinic-healthcare"],
    defaultTreatment: "minimal-rows",
    treatments: [
      {
        id: "minimal-rows",
        label: "Minimal-rows",
        description: "Lugna rundade kort i vertikal lista — pre-Phase-2-känsla.",
      },
      {
        id: "split-cards",
        label: "Split-cards",
        description:
          "Två-kolumns kort med varm accent-rail — broschyrkänsla, varm-care-vibe.",
      },
      {
        id: "numbered-stack",
        label: "Numbered-stack",
        description:
          "Stora monospace-numerals med tunna separatorer — klinisk sekvens.",
      },
    ],
    variantDefaults: {
      "warm-care": "split-cards",
      "modern-precision": "numbered-stack",
    },
  },
  {
    id: "practice-grid",
    label: "Verksamhetsområden (advokat/konsult)",
    description:
      "Kompetensblock på professional-services-startsidor (legal/consulting/accounting).",
    scaffolds: ["professional-services"],
    defaultTreatment: "dense-grid",
    treatments: [
      {
        id: "dense-grid",
        label: "Dense-grid",
        description:
          "Tät 3-kolumns grid med kompakta kort — klassisk byrå-portfolio.",
      },
      {
        id: "tabular",
        label: "Tabular",
        description:
          "Tabular katalog utan card-chrome — domstols-protokoll-känsla.",
      },
      {
        id: "grouped",
        label: "Grouped",
        description:
          "Grupperad lista med kategori-headers — accounting-trust-känsla.",
      },
    ],
    variantDefaults: {
      "legal-classic": "tabular",
      "accounting-trust": "grouped",
    },
  },
  {
    id: "expertise-areas",
    label: "Expertis (start, advokat/konsult)",
    description:
      "Praktikområden på professional-services-startsidan.",
    scaffolds: ["professional-services"],
    defaultTreatment: "numbered-2col",
    treatments: [
      {
        id: "numbered-2col",
        label: "Numbered 2-col",
        description:
          "Två-kolumns grid med 01-06 numerics — court-filing-restraint.",
      },
      {
        id: "tag-cluster",
        label: "Tag-cluster",
        description:
          "Pill-moln där varje praktikområde är en kompakt rounded pill — associativ vy.",
      },
    ],
    variantDefaults: {
      "consulting-modern": "tag-cluster",
    },
  },
  {
    id: "service-list",
    label: "Tjänster (LSB)",
    description:
      "Tjänstelistan på local-service-business-tjänstesidor.",
    scaffolds: ["local-service-business"],
    defaultTreatment: "card-grid",
    treatments: [
      {
        id: "card-grid",
        label: "Card-grid",
        description:
          "3-kolumns gradient-headered grid med ikon + label — byte-identisk default.",
      },
      {
        id: "alternating-rows",
        label: "Alternating-rows",
        description:
          "Varannan rad ikon vänster, varannan ikon höger — vi-och-du-rytm.",
      },
      {
        id: "icon-strip",
        label: "Icon-strip",
        description:
          "Kompakt horisontell strip med små ikon-pills — minimalist contents-bar.",
      },
      {
        id: "tabular",
        label: "Tabular",
        description:
          "Formell rad-lista utan card-chrome — service-katalog-känsla.",
      },
    ],
    variantDefaults: {
      "warm-craft": "alternating-rows",
      "clinical-calm": "icon-strip",
      "nordic-trust": "tabular",
    },
  },
] as const;

/**
 * Hitta de section-specs som är relevanta för den valda scaffold-
 * hint:en. Returnerar tom lista om scaffolden inte har några
 * registrerade treatments — i så fall renderar visual-step ingen
 * disclosure alls.
 */
export function sectionTreatmentSpecsForScaffold(
  scaffoldHint: string,
): readonly SectionTreatmentSpec[] {
  return SECTION_TREATMENT_SPECS.filter((spec) =>
    spec.scaffolds.includes(scaffoldHint),
  );
}

/**
 * Resolve den treatment som faktiskt körs när inget operator-pin är
 * satt. Speglar Python `_treatment_for_section`:s nuvarande resolve-
 * ordning (variant-default > section-default). Används för att visa
 * "Auto" -alternativet med korrekt undertext.
 */
export function resolveAutoTreatment(
  spec: SectionTreatmentSpec,
  variantId: string | undefined,
): SectionTreatmentId {
  if (variantId && spec.variantDefaults[variantId]) {
    return spec.variantDefaults[variantId];
  }
  return spec.defaultTreatment;
}
