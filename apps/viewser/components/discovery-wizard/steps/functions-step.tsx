"use client";

import {
  Briefcase,
  CalendarCheck,
  Check,
  HelpCircle,
  Home,
  Image as ImageIcon,
  Info,
  MapPin,
  Mail,
  Newspaper,
  Send,
  ShoppingBag,
  Square,
  Star,
  Tag,
  UtensilsCrossed,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type BusinessFamilyId,
  findFunctionChoice,
  type FunctionChoice,
  functionGroupsForFamily,
  MUST_HAVE_OPTIONS,
  type MustHaveOption,
  RECOMMENDED_EXTRA_PAGES_BY_FAMILY,
  RECOMMENDED_FUNCTIONS_BY_FAMILY,
  RELEVANT_PAGES_BY_FAMILY,
} from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import { FieldStack } from "./step-primitives";

/**
 * FunctionsStep — wizardens steg 3 efter "sidor först"-revisionen
 * (2026-05-26, operator-feedback: "Detta måste bli lättare. För svårt
 * att förstå hur man ska kryssa i olika sidor som ska skapas").
 *
 * Tidigare visade vi en lång lista av funktioner (FAQ, kontaktformulär,
 * kundvagn osv) bakom två gömda disclosures plus en statisk "VALDA
 * FUNKTIONER"-chip-summary som såg klickbar ut men inte var det. För
 * mycket olika lager för operatören att förstå.
 *
 * Ny modell:
 *   - Tab 3 visar SIDOR som hemsidan ska ha. 15 stora klickbara kort
 *     i ett 2/3-kolumns rutnät. Hela kortet är klickbart, ✓-ikon
 *     markerar valda sidor.
 *   - Funktioner härleds automatiskt: varje sida som har en `pageMustHave`-
 *     länk i FUNCTION_GROUPS togglar motsvarande `selectedFunction`-id
 *     samtidigt. Operatören behöver aldrig se funktions-IDs.
 *   - Primär CTA, specialönskemål, USP:er och egen CTA finns kvar i
 *     "Mer information"-popupen (Avancerat-fliken). Inget av det
 *     visas på tab 3 längre.
 *   - Logo + mediamaterial renderas direkt under av wizard-shellet
 *     (AssetsStep i discovery-wizard.tsx).
 *
 * Backend-kontraktet är oförändrat: vi skriver fortfarande till
 * `answers.mustHave` (sidor) och `answers.selectedFunctions` (funktions-
 * IDs). Backend-mappningen till requestedCapabilities + sitemap fungerar
 * därför som tidigare.
 */

const PAGE_ICONS: Record<MustHaveOption, LucideIcon> = {
  "Startsida / Hero": Home,
  "Om oss / Om mig": Info,
  Kontaktformulär: Mail,
  "Priser och paket": Tag,
  "Bokning online": CalendarCheck,
  Bildgalleri: ImageIcon,
  "Blogg / Nyheter": Newspaper,
  Kundrecensioner: Star,
  FAQ: HelpCircle,
  "Portfolio / Case": Briefcase,
  "Vårt team": Users,
  "Karta / Hitta hit": MapPin,
  Nyhetsbrev: Send,
  "Webshop / Produkter": ShoppingBag,
  "Meny / Matsedel": UtensilsCrossed,
};

export function FunctionsStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const family = answers.businessFamily;

  // Page → function-choice. När operatorn togglar en sida som har en
  // FunctionChoice med matchande pageMustHave så togglar vi den
  // funktionen samtidigt — så backend får både rätt mustHave och
  // rätt selectedFunctions utan att operatorn ser funktions-IDs.
  const pageToChoice = useMemo(() => {
    const map = new Map<MustHaveOption, FunctionChoice>();
    for (const group of functionGroupsForFamily(family || "")) {
      for (const choice of group.choices) {
        if (choice.pageMustHave) {
          map.set(choice.pageMustHave as MustHaveOption, choice);
        }
      }
    }
    return map;
  }, [family]);

  const togglePage = useCallback(
    (page: MustHaveOption) => {
      const pages = new Set(answers.mustHave);
      const fns = new Set(answers.selectedFunctions);
      if (pages.has(page)) {
        pages.delete(page);
        const choice = pageToChoice.get(page);
        if (choice) fns.delete(choice.id);
      } else {
        pages.add(page);
        const choice = pageToChoice.get(page);
        if (choice) fns.add(choice.id);
      }
      onChange({
        mustHave: Array.from(pages),
        selectedFunctions: Array.from(fns),
      });
    },
    [answers.mustHave, answers.selectedFunctions, pageToChoice, onChange],
  );

  // Auto-apply familjens rekommenderade sidor + funktioner.
  //
  // Två fall:
  //   1. Första gången family sätts och inget redan är förvalt
  //      (lastAppliedFamilyRef === null) → applicera defaults.
  //   2. Family BYTS från en tidigare family (lastAppliedFamilyRef
  //      var ≠ null och ≠ ny family) → byt ut föregående familjs
  //      defaults mot nya familjens. Custom-tillägg som operatören
  //      lagt till manuellt (poster som inte fanns i föregående
  //      familjs defaults) behålls. Scout-fynd 2026-05-26:
  //      tidigare logik körde bara case 1 — ett family-byte efter
  //      att functions-tabben besökts behöll restaurang-sidor även
  //      om operatören bytte till e-handel.
  const lastAppliedFamilyRef = useRef<BusinessFamilyId | null>(null);
  useEffect(() => {
    if (!family) return;
    const previousFamily = lastAppliedFamilyRef.current;
    if (previousFamily === family) return;

    const buildDefaults = (
      familyKey: BusinessFamilyId,
    ): { pages: Set<string>; fns: Set<string> } => {
      const ids = RECOMMENDED_FUNCTIONS_BY_FAMILY[familyKey] ?? [];
      const pages = new Set<string>([
        "Startsida / Hero",
        "Om oss / Om mig",
      ]);
      const fns = new Set<string>();
      for (const id of ids) {
        const choice = findFunctionChoice(id);
        if (!choice) continue;
        fns.add(choice.id);
        if (choice.pageMustHave) pages.add(choice.pageMustHave);
      }
      // Sidor utan funktions-koppling (t.ex. Portfolio / Case) som
      // taxonomin ändå rekommenderar för familjen.
      for (const page of RECOMMENDED_EXTRA_PAGES_BY_FAMILY[familyKey] ?? []) {
        pages.add(page);
      }
      return { pages, fns };
    };

    if (previousFamily === null) {
      if (
        answers.selectedFunctions.length === 0 &&
        answers.mustHave.length === 0
      ) {
        const next = buildDefaults(family);
        onChange({
          selectedFunctions: Array.from(next.fns),
          mustHave: Array.from(next.pages),
        });
      }
    } else {
      const prev = buildDefaults(previousFamily);
      const next = buildDefaults(family);
      const nextPages = new Set<string>();
      for (const p of answers.mustHave) {
        if (!prev.pages.has(p) || next.pages.has(p)) nextPages.add(p);
      }
      for (const p of next.pages) nextPages.add(p);
      const nextFns = new Set<string>();
      for (const f of answers.selectedFunctions) {
        if (!prev.fns.has(f) || next.fns.has(f)) nextFns.add(f);
      }
      for (const f of next.fns) nextFns.add(f);
      onChange({
        selectedFunctions: Array.from(nextFns),
        mustHave: Array.from(nextPages),
      });
    }

    lastAppliedFamilyRef.current = family;
    // applyRecommendations är stabil. Trigga bara på family-byten.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [family]);

  const selectedCount = answers.mustHave.length;

  // Branschanpassat rutnät (2026-06-09): visa familjens relevanta sidor
  // direkt; övriga (t.ex. "Meny / Matsedel" för en bilverkstad) bakom en
  // "Visa fler sidor"-toggle så de inte ser ut som rekommendationer.
  // Valda sidor visas alltid, oavsett relevanslista.
  const [showAllPages, setShowAllPages] = useState(false);
  const { visiblePages, hiddenPages } = useMemo(() => {
    const relevant = new Set<MustHaveOption>(
      family ? (RELEVANT_PAGES_BY_FAMILY[family] ?? MUST_HAVE_OPTIONS) : [],
    );
    const selected = new Set(answers.mustHave);
    const visible: MustHaveOption[] = [];
    const hidden: MustHaveOption[] = [];
    for (const page of MUST_HAVE_OPTIONS) {
      if (relevant.has(page) || selected.has(page)) visible.push(page);
      else hidden.push(page);
    }
    return { visiblePages: visible, hiddenPages: hidden };
  }, [family, answers.mustHave]);

  return (
    <FieldStack>
      {!family ? (
        <div className="border-border/70 bg-card/50 rounded-xl border p-4">
          <p className="text-muted-foreground text-[12px]">
            Välj verksamhetsfamilj i steg 1 så förvalt vi sidor som passar
            er verksamhet.
          </p>
        </div>
      ) : (
        <div>
          <div className="mb-3 flex items-baseline justify-between gap-2">
            <span className="text-muted-foreground font-mono text-[10px] tracking-[0.2em] uppercase">
              Sidor på er hemsida · {selectedCount}
            </span>
          </div>
          <p className="text-muted-foreground/85 mb-3 text-[12.5px] leading-snug">
            Klicka för att lägga till eller ta bort. Vi har förvalt det
            som passar er verksamhet.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {visiblePages.map((page) => (
              <PageCard
                key={page}
                page={page}
                selected={answers.mustHave.includes(page)}
                onToggle={() => togglePage(page)}
              />
            ))}
            {showAllPages
              ? hiddenPages.map((page) => (
                  <PageCard
                    key={page}
                    page={page}
                    selected={answers.mustHave.includes(page)}
                    onToggle={() => togglePage(page)}
                  />
                ))
              : null}
          </div>
          {hiddenPages.length > 0 ? (
            <button
              type="button"
              onClick={() => setShowAllPages((prev) => !prev)}
              className="text-muted-foreground hover:text-foreground mt-2.5 inline-flex items-center gap-1 text-[11.5px] font-medium underline-offset-2 transition-colors hover:underline"
            >
              {showAllPages
                ? "Visa färre sidor"
                : `Visa fler sidor (${hiddenPages.length})`}
            </button>
          ) : null}
        </div>
      )}
    </FieldStack>
  );
}

function PageCard({
  page,
  selected,
  onToggle,
}: {
  page: MustHaveOption;
  selected: boolean;
  onToggle: () => void;
}) {
  const Icon = PAGE_ICONS[page] ?? Square;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      className={[
        "group relative inline-flex h-auto items-center gap-2 rounded-xl border px-3 py-2.5 text-left transition-all active:scale-[0.98]",
        selected
          ? "border-foreground bg-foreground text-background shadow-sm"
          : "border-border/70 bg-card text-foreground/80 hover:border-foreground/40 hover:text-foreground",
      ].join(" ")}
    >
      <Icon
        className={[
          "h-3.5 w-3.5 shrink-0 transition-colors",
          selected
            ? "text-background"
            : "text-muted-foreground group-hover:text-foreground",
        ].join(" ")}
        aria-hidden
      />
      <span className="flex-1 truncate text-[12px] font-medium leading-tight">
        {page}
      </span>
      {selected ? (
        <Check className="h-3 w-3 shrink-0" strokeWidth={2.5} aria-hidden />
      ) : null}
    </button>
  );
}
