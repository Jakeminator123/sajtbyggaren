/**
 * build-changes — sammanfatta vad en follow-up-build ändrade till en
 * kort lista som kan visas under success-meddelandet i FloatingChat.
 *
 * Det finns TVÅ källor, i fallande trovärdighetsordning:
 *
 *   1. `summarizeChangeSet(changeSet)` — EXAKT. Bygger på en strukturerad
 *      change-set som `/api/prompt` härleder serverside genom att diffa
 *      den nya runens artefakter mot föregående run (se
 *      `lib/run-change-set.ts` + `computeRunDiff`). Routes som lades
 *      till/togs bort och variant-byten är faktiska deltas, inte
 *      gissningar. Renderas under rubriken "Ändrat".
 *
 *   2. `summarizeChangesFromPrompt(prompt)` — HEURISTIK. Paraphraserar
 *      operatörens prompt via nyckelord när ingen exakt change-set finns
 *      (t.ex. ren copy-/design-justering som inte ändrar route-uppsättning
 *      eller variant). Renderas under rubriken "Troligen ändrat" så
 *      operatören vet att det är en uppskattning.
 *
 * Designprinciper:
 *   - Aldrig hitta på något som inte rimligt kan ha hänt.
 *   - Mappa till samma vokabulär som `QUICK_PROMPT_CATEGORIES` i
 *     FloatingChat så operatören känner igen begreppen.
 *   - Max 3 bullets — annars blir success-bubblan ett vägg av text.
 *   - Returnera tom array om vi inte kan säga något specifikt så
 *     UI-kallaren kan välja att inte rendera listan alls.
 */

export type BuildChange = {
  category: "design" | "content" | "layout" | "structure" | "media";
  label: string;
};

/**
 * Strukturerad, EXAKT change-set som `/api/prompt` skickar på wiren för
 * follow-up-builds. Härledd serverside i `lib/run-change-set.ts` genom
 * att diffa den nya runens artefakter mot föregående run via
 * `computeRunDiff`. `null`/utelämnad = init-build eller en follow-up
 * där vi inte kunde härleda någon exakt route-/variant-delta (då faller
 * UI:t tillbaka på prompt-heuristiken).
 *
 * Måste hållas medvetet smal: bara deltas vi kan bekräfta från
 * artefakter på disk. Copy-direktiv (företagsnamn, tagline) lever kvar
 * i sin egen `appliedCopyDirectives`-väg och dupliceras inte här.
 */
export type RunChangeSet = {
  /** Run vi diffade emot. `null` när ingen föregående run hittades. */
  previousRunId: string | null;
  /** Route-paths som finns i nya runen men inte den föregående. */
  routesAdded: string[];
  /** Route-paths som fanns i föregående run men inte den nya. */
  routesRemoved: string[];
  /** Designvariant före bytet — `null` om variant var oförändrad. */
  variantBefore: string | null;
  /** Designvariant efter bytet — `null` om variant var oförändrad. */
  variantAfter: string | null;
  /**
   * ADR 0046: de validerade preview-markeringar operatören pekade på när
   * versionen byggdes (`{routeId, sectionId, note?}`). Läses ur
   * build-result.json:s `appliedFocusSections`. Tom lista när inga
   * markeringar fanns.
   */
  appliedFocusSections: { routeId: string; sectionId: string; note?: string }[];
};

interface KeywordRule {
  /** Regex som måste matcha prompten (case-insensitive). */
  match: RegExp;
  category: BuildChange["category"];
  /** Statisk label eller funktion som producerar label från regex-match. */
  label: string | ((match: RegExpMatchArray) => string);
}

/**
 * Reglerna är ordnade efter specificitet. När fler regler matchar
 * samma kategori tar vi bara den första — det undviker att operatören
 * ser "Färgändring · Ny färgpalett · Färgschema uppdaterat" som tre
 * separata bullets.
 *
 * Svenska + engelska keyword:s eftersom operatörer ofta blandar.
 */
const RULES: ReadonlyArray<KeywordRule> = [
  // ── Design / visual ─────────────────────────────────────────────
  {
    match: /(färg|color|palette|palett)/i,
    category: "design",
    label: "Färgschema justerat",
  },
  {
    match: /(typografi|typsnitt|font|typography)/i,
    category: "design",
    label: "Typografi uppdaterad",
  },
  {
    match: /(mörk|dark mode|ljus|light mode|tema|theme)/i,
    category: "design",
    label: "Visuellt tema bytt",
  },
  {
    match: /(luftig|spacing|margin|padding|tighter|tätare)/i,
    category: "design",
    label: "Spacing och rytm justerad",
  },

  // ── Layout ──────────────────────────────────────────────────────
  {
    match: /\bhero\b.*\b(layout|split|gradient|centered|centrera)\b/i,
    category: "layout",
    label: "Hero-layout bytt",
  },
  {
    match: /\b(grid|kolumn|column|row|rad)\b/i,
    category: "layout",
    label: "Sektions-layout justerad",
  },

  // ── Innehåll (sektioner) ────────────────────────────────────────
  {
    match: /\b(lägg till|add|skapa)\b.*\b(sektion|section|sida|page|avsnitt)\b/i,
    category: "structure",
    label: "Ny sektion eller sida tillagd",
  },
  {
    match: /\b(ta bort|remove|delete|radera)\b.*\b(sektion|section|sida|page)\b/i,
    category: "structure",
    label: "Sektion eller sida borttagen",
  },
  {
    match: /\b(faq|frågor och svar|vanliga frågor)\b/i,
    category: "content",
    label: "FAQ-sektion uppdaterad",
  },
  {
    match: /\b(testimonial|recension|kundomdöme|kund-omdöme)\b/i,
    category: "content",
    label: "Kundomdömen uppdaterade",
  },
  {
    match: /\b(team|medarbetare|personal|våra människor)\b/i,
    category: "content",
    label: "Team-sektion uppdaterad",
  },
  {
    match: /\b(galleri|gallery|bilder|images)\b/i,
    category: "media",
    label: "Galleri eller bildsektion uppdaterad",
  },

  // ── Copy ────────────────────────────────────────────────────────
  {
    match: /\b(rubrik|headline|titel|tagline)\b/i,
    category: "content",
    label: "Rubriker och tagline uppdaterade",
  },
  {
    match: /\b(cta|call.?to.?action|knapptext|button)\b/i,
    category: "content",
    label: "CTA-knappar justerade",
  },
  {
    match: /\b(skriv om|rewrite|skriva om|formulera)\b/i,
    category: "content",
    label: "Copy omformulerad",
  },

  // ── Media ───────────────────────────────────────────────────────
  {
    match: /\b(bild|image|photo|foto|hero-?bild)\b/i,
    category: "media",
    label: "Bilder uppdaterade",
  },
  {
    match: /\b(logo|logotyp|brand-?ikon)\b/i,
    category: "media",
    label: "Logotyp uppdaterad",
  },
  {
    match: /\b(video|bakgrundsvideo|hero-?video)\b/i,
    category: "media",
    label: "Video-element uppdaterat",
  },
];

/**
 * Returnera 0-3 ändringar baserat på operatörens prompt. Tom array =
 * "inget specifikt vi kan säga" → kallaren ska inte visa listan.
 */
export function summarizeChangesFromPrompt(prompt: string): BuildChange[] {
  const text = prompt.trim();
  if (!text) return [];
  const seenCategories = new Set<BuildChange["category"]>();
  const changes: BuildChange[] = [];
  for (const rule of RULES) {
    if (changes.length >= 3) break;
    const match = text.match(rule.match);
    if (!match) continue;
    // En kategori, en bullet — undviker dubbel-rendering av samma
    // tema (t.ex. flera färg-relaterade regler i samma prompt).
    if (seenCategories.has(rule.category)) continue;
    seenCategories.add(rule.category);
    const label =
      typeof rule.label === "function" ? rule.label(match) : rule.label;
    changes.push({ category: rule.category, label });
  }
  return changes;
}

/**
 * Mappa en EXAKT change-set till 0-3 BuildChange-bullets. Till skillnad
 * från `summarizeChangesFromPrompt` är varje rad här en bekräftad delta
 * (routes/variant härledda ur run-artefakter), så UI:t kan rendera dem
 * under en "Ändrat"-rubrik istället för "Troligen ändrat".
 *
 * Returnerar tom array när change-set:en saknas eller inte innehåller
 * någon exakt delta — då faller kallaren tillbaka på prompt-heuristiken.
 */
export function summarizeChangeSet(
  changeSet: RunChangeSet | null | undefined,
): BuildChange[] {
  if (!changeSet) return [];
  const changes: BuildChange[] = [];
  for (const route of changeSet.routesAdded) {
    if (changes.length >= 3) return changes;
    changes.push({ category: "structure", label: `Sidan ${route} tillagd` });
  }
  for (const route of changeSet.routesRemoved) {
    if (changes.length >= 3) return changes;
    changes.push({ category: "structure", label: `Sidan ${route} borttagen` });
  }
  if (
    changes.length < 3 &&
    changeSet.variantBefore &&
    changeSet.variantAfter &&
    changeSet.variantBefore !== changeSet.variantAfter
  ) {
    changes.push({
      category: "design",
      label: `Designvariant: ${changeSet.variantBefore} → ${changeSet.variantAfter}`,
    });
  }
  // ADR 0046: visa vad operatören pekade på i preview ("Markera modul")
  // när versionen byggdes. `note` är sektionens rubriktext från overlayn.
  for (const focus of changeSet.appliedFocusSections ?? []) {
    if (changes.length >= 3) return changes;
    const label = focus.note
      ? `Markerad modul: ${focus.note} (${focus.routeId}/${focus.sectionId})`
      : `Markerad modul: ${focus.routeId}/${focus.sectionId}`;
    changes.push({ category: "content", label });
  }
  return changes;
}

/**
 * Människovänlig etikett per kategori. Används för att gruppera
 * BuildChange[]-output i UI:t med en liten ikon.
 */
export const CATEGORY_LABEL: Record<BuildChange["category"], string> = {
  design: "Design",
  content: "Innehåll",
  layout: "Layout",
  structure: "Struktur",
  media: "Media",
};
