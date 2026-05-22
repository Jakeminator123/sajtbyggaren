/**
 * build-changes — paraphrasera operatörens follow-up-prompt till en
 * kort "Vad gjordes typiskt"-summa som kan visas under success-
 * meddelandet i FloatingChat.
 *
 * Detta är en bästa-uppskattning baserat på prompt-textens nyckelord.
 * När backend så småningom exponerar en strukturerad change-set i
 * `PromptApiResponse` (lista över ändrade routes, copy-fält, brand-
 * tokens etc.) kan vi ersätta heuristiken med exakta deltas.
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
