"use client";

import { Check, Search } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

import { PROFESSIONS } from "@/lib/professions";

import {
  BUSINESS_FAMILIES,
  familyForCategory,
  WIZARD_CATEGORIES,
  type BusinessFamilyId,
  type WizardCategoryId,
} from "./wizard-constants";

/**
 * IndustrySearch — fritextsök/typeahead för bransch i wizardens steg 1
 * (2026-06-09, operatörsriktning "100 branscher som data").
 *
 * Problemet: 8 familje-kort räcker som yta, men operatören tänker i sin
 * BRANSCH ("bilmekaniker", "rörmokare", "advokat") — inte i familjer.
 * Med fler kategorier i taxonomin kan utbudet aldrig visas som chips.
 *
 * Lösningen: ett sökfält ovanför familje-korten. Indexet byggs av tre
 * lager som alla redan finns i repot:
 *   1. PROFESSIONS (lib/professions.ts) — 20 yrken med family+kategori,
 *      samma data som driver /for/[yrke]-landningssidorna.
 *   2. WIZARD_CATEGORIES — 25 taxonomi-speglade kategorier.
 *   3. CATEGORY_SYNONYMS — vardagliga branschord per kategori.
 *
 * Ett val sätter businessFamily + siteType (payload-kontraktet är
 * oförändrat — exakt samma fält som familje-kort + scrape-inferens
 * redan skriver). UI-cache: när taxonomin växer mot ~100 kategorier
 * ska indexet serveras via /api/discovery-options (inbox-topic
 * wizard-page-suggestions, msg-0056).
 */

export type IndustryMatch = {
  key: string;
  /** Visningsnamn, t.ex. "Bilverkstad" eller "Bygg / Hantverk". */
  label: string;
  /** Familjens label — visas som sekundär rad i träfflistan. */
  familyLabel: string;
  family: BusinessFamilyId;
  category: WizardCategoryId;
  /** Normaliserade söknycklar (lowercase, åäö-vikta). */
  keywords: readonly string[];
  /** Yrkes-träffar rankas före kategori-träffar vid lika poäng. */
  kind: "profession" | "category";
};

/**
 * Vardagliga branschord per kategori. Medvetet bred — det här är vad
 * en småföretagare faktiskt skriver i ett sökfält. Orden mappas till
 * kategori (inte yrke) så de följer med när taxonomin växer.
 */
const CATEGORY_SYNONYMS: Partial<
  Record<WizardCategoryId, readonly string[]>
> = {
  auto: [
    "bilverkstad",
    "bilmekaniker",
    "mekaniker",
    "däckverkstad",
    "däckhotell",
    "bilhandlare",
    "biltvätt",
    "lackering",
    "mc-verkstad",
  ],
  salon: [
    "frisör",
    "barberare",
    "nagelsalong",
    "skönhetssalong",
    "hudvård",
    "fransstylist",
    "massör",
  ],
  healthcare: [
    "tandläkare",
    "läkare",
    "klinik",
    "naprapat",
    "kiropraktor",
    "fysioterapeut",
    "psykolog",
    "veterinär",
  ],
  fitness: ["gym", "personlig tränare", "yoga", "pilates", "crossfit", "dans"],
  restaurant: [
    "restaurang",
    "café",
    "kafé",
    "bistro",
    "pizzeria",
    "sushi",
    "bageri",
    "konditori",
    "food truck",
    "bar",
    "pub",
  ],
  food: ["catering", "delikatess", "matbutik", "gårdsbutik", "chark"],
  ecommerce: ["webshop", "webbutik", "butik", "e-handel", "märkesvaror"],
  construction: [
    "snickare",
    "byggfirma",
    "elektriker",
    "rörmokare",
    "vvs",
    "målare",
    "plattsättare",
    "takläggare",
    "murare",
    "golvläggare",
    "anläggning",
    "trädgårdsanläggare",
    "glasmästare",
  ],
  legal: ["advokat", "jurist", "advokatbyrå", "juridisk rådgivning"],
  accounting: ["revisor", "redovisning", "bokföring", "ekonomibyrå", "lön"],
  consulting: [
    "konsult",
    "byrå",
    "rekrytering",
    "marknadsföring",
    "reklambyrå",
    "kommunikationsbyrå",
  ],
  tech: ["startup", "saas", "app", "it-konsult", "mjukvara", "webbyrå"],
  portfolio: [
    "portfolio",
    "konstnär",
    "designer",
    "illustratör",
    "arkitekt",
    "keramiker",
  ],
  photo: ["fotograf", "videograf", "filmproduktion", "bröllopsfotograf"],
  music: ["musiker", "band", "dj", "musiklärare", "artist", "musikstudio"],
  realestate: ["mäklare", "fastighetsmäklare", "fastighetsförvaltning"],
  education: [
    "skola",
    "utbildning",
    "kurser",
    "förskola",
    "körskola",
    "trafikskola",
    "studieförbund",
  ],
  event: ["event", "bröllop", "festplanering", "konferens", "mässa"],
  hotel: [
    "hotell",
    "vandrarhem",
    "bed and breakfast",
    "camping",
    "stuguthyrning",
  ],
  travel: ["resebyrå", "turism", "guide", "upplevelser"],
  nonprofit: ["förening", "ideell", "klubb", "församling", "stiftelse"],
  blog: ["blogg", "magasin", "tidning", "podcast"],
  landing: ["landningssida", "kampanj", "lansering", "produktsida"],
  business: [
    "städfirma",
    "flyttfirma",
    "låssmed",
    "skomakare",
    "kemtvätt",
    "hunddagis",
    "cykelverkstad",
    "skräddare",
    "sotare",
    "bemanning",
  ],
};

/** Lowercase + vik åäö/é så "frisor" matchar "frisör". */
function normalize(text: string): string {
  return text
    .toLowerCase()
    .replaceAll("å", "a")
    .replaceAll("ä", "a")
    .replaceAll("ö", "o")
    .replaceAll("é", "e");
}

function buildIndex(): IndustryMatch[] {
  const familyLabelById = new Map<BusinessFamilyId, string>(
    BUSINESS_FAMILIES.map((f) => [f.id, f.label]),
  );
  const entries: IndustryMatch[] = [];

  for (const profession of PROFESSIONS) {
    entries.push({
      key: `profession:${profession.slug}`,
      label: profession.displayName,
      familyLabel: familyLabelById.get(profession.family) ?? "",
      family: profession.family,
      category: profession.category,
      keywords: [normalize(profession.displayName), normalize(profession.slug)],
      kind: "profession",
    });
  }

  for (const category of WIZARD_CATEGORIES) {
    const family = familyForCategory(category.id);
    if (!family) continue;
    const synonyms = CATEGORY_SYNONYMS[category.id] ?? [];
    entries.push({
      key: `category:${category.id}`,
      label: category.label,
      familyLabel: family.label,
      family: family.id,
      category: category.id,
      keywords: [
        normalize(category.label),
        ...category.label.split("/").map((part) => normalize(part.trim())),
        ...synonyms.map(normalize),
      ],
      kind: "category",
    });
  }

  return entries;
}

function scoreEntry(entry: IndustryMatch, query: string): number {
  let best = 0;
  for (const keyword of entry.keywords) {
    if (keyword.startsWith(query)) {
      best = Math.max(best, 3);
    } else if (keyword.includes(query)) {
      best = Math.max(best, 1);
    }
  }
  return best;
}

const MAX_RESULTS = 7;

export function IndustrySearch({
  onPick,
}: {
  onPick: (match: IndustryMatch) => void;
}) {
  const index = useMemo(() => buildIndex(), []);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [picked, setPicked] = useState<IndustryMatch | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const results = useMemo(() => {
    const normalized = normalize(query.trim());
    if (normalized.length < 2) return [];
    return index
      .map((entry) => ({ entry, score: scoreEntry(entry, normalized) }))
      .filter((hit) => hit.score > 0)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        if (a.entry.kind !== b.entry.kind) {
          return a.entry.kind === "profession" ? -1 : 1;
        }
        return a.entry.label.localeCompare(b.entry.label, "sv");
      })
      .slice(0, MAX_RESULTS)
      .map((hit) => hit.entry);
  }, [index, query]);

  const pick = useCallback(
    (match: IndustryMatch) => {
      setPicked(match);
      setQuery("");
      setActiveIndex(0);
      onPick(match);
    },
    [onPick],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (results.length === 0) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((prev) => (prev + 1) % results.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((prev) => (prev - 1 + results.length) % results.length);
      } else if (event.key === "Enter") {
        event.preventDefault();
        const match = results[activeIndex] ?? results[0];
        if (match) pick(match);
      } else if (event.key === "Escape") {
        setQuery("");
        setActiveIndex(0);
      }
    },
    [results, activeIndex, pick],
  );

  const listboxId = "industry-search-results";
  const open = results.length > 0;

  return (
    <div className="relative">
      <div className="relative">
        <Search
          className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2"
          aria-hidden
        />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Sök din bransch… t.ex. bilverkstad, frisör, advokat"
          className="border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/30 flex h-9 w-full rounded-md border bg-transparent py-1 pr-3 pl-9 text-base shadow-xs transition-colors outline-none focus-visible:ring-2 md:text-[13px]"
        />
      </div>
      {open ? (
        <ul
          id={listboxId}
          role="listbox"
          className="border-border/70 bg-popover absolute top-full right-0 left-0 z-20 mt-1 overflow-hidden rounded-lg border shadow-md"
        >
          {results.map((match, idx) => (
            <li key={match.key} role="option" aria-selected={idx === activeIndex}>
              <button
                type="button"
                onMouseDown={(event) => {
                  // mousedown i stället för click så valet hinner före
                  // input-blur (annars stängs listan utan att välja).
                  event.preventDefault();
                  pick(match);
                }}
                onMouseEnter={() => setActiveIndex(idx)}
                className={[
                  "flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left transition-colors",
                  idx === activeIndex
                    ? "bg-foreground/[0.05]"
                    : "hover:bg-foreground/[0.03]",
                ].join(" ")}
              >
                <span className="text-foreground truncate text-[12.5px] font-medium">
                  {match.label}
                </span>
                <span className="text-muted-foreground shrink-0 text-[11px]">
                  {match.familyLabel}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {picked ? (
        <p className="text-muted-foreground mt-1.5 flex items-center gap-1 text-[11px]">
          <Check
            className="h-3 w-3 text-emerald-600 dark:text-emerald-400"
            aria-hidden
          />
          <span>
            <span className="text-foreground font-medium">{picked.label}</span>
            {" — vi har valt familjen "}
            {picked.familyLabel} nedan. Byt kort om det inte stämmer.
          </span>
        </p>
      ) : null}
    </div>
  );
}
