/**
 * Serialiserar `WizardAnswers` till det kontrakt som `/api/prompt`
 * (utökad med `discovery`) skickar vidare till
 * `scripts/prompt_to_project_input.py --discovery <fil>`.
 *
 * Mål:
 *   1. Stabilt JSON-schema som backend kan validera (Pydantic eller
 *      Zod-spegling).
 *   2. Strippa tomma fält så payloaden blir liten och så att Python-
 *      mappern kan skilja "ej ifyllt" från "explicit tomsträng".
 *   3. Generera en kort, rik `prompt`-text som befintlig LLM-extraktion
 *      kan använda som fallback om vissa fält saknas — det följer
 *      mönstret i `prompt-builder.tsx` där originalprompten alltid
 *      bevaras som `rawPrompt`.
 */

import { resolveContentBranch, WIZARD_CATEGORIES } from "./wizard-constants";
import type { WizardAnswers } from "./wizard-types";

export type DiscoveryPayload = {
  /**
   * Schema-version så backend kan utveckla kontraktet utan att bryta
   * klienten. Heter `schemaVersion` (inte `version`) — `test_viewser_files`
   * förbjuder client-payload med `version: z` på prompt-routen eftersom
   * det fältet tillhör Project Input-meta-sidecar (`*.meta.json`).
   */
  schemaVersion: 1;
  /** Free-form pitch som operatorn skrev i prompt-builder-input:en. */
  rawPrompt: string;
  /** Beräknad gren (ecommerce, restaurant, ...) — backend kan double-check. */
  contentBranch: ReturnType<typeof resolveContentBranch>;
  /** Scaffold-hint baserat på första valda kategorin. */
  scaffoldHint: string;
  /** Trimmed copy of all wizard answers — tomma fält strippade. */
  answers: WizardAnswers;
};

/** Tar bort tomma strängar, tomma arrays och tomma objekt rekursivt. */
function stripEmpty<T>(value: T): T {
  if (Array.isArray(value)) {
    const next = value
      .map((item) => stripEmpty(item))
      .filter((item) => {
        if (item === null || item === undefined) return false;
        if (typeof item === "string") return item.trim().length > 0;
        if (typeof item === "object" && Object.keys(item).length === 0) return false;
        return true;
      });
    return next as unknown as T;
  }
  if (value && typeof value === "object") {
    const next: Record<string, unknown> = {};
    for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
      const cleaned = stripEmpty(raw);
      if (cleaned === null || cleaned === undefined) continue;
      if (typeof cleaned === "string" && cleaned.trim().length === 0) continue;
      if (Array.isArray(cleaned) && cleaned.length === 0) continue;
      if (
        typeof cleaned === "object" &&
        !Array.isArray(cleaned) &&
        Object.keys(cleaned).length === 0
      ) {
        continue;
      }
      next[key] = cleaned;
    }
    return next as T;
  }
  return value;
}

export function buildDiscoveryPayload(
  rawPrompt: string,
  answers: WizardAnswers,
): DiscoveryPayload {
  const branch = resolveContentBranch(answers.siteType);
  const firstCategory = answers.siteType[0];
  const scaffoldHint =
    WIZARD_CATEGORIES.find((c) => c.id === firstCategory)?.scaffoldHint ??
    "local-service-business";

  return {
    schemaVersion: 1,
    rawPrompt: rawPrompt.trim(),
    contentBranch: branch,
    scaffoldHint,
    answers: stripEmpty(answers),
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
 * den orörda prompten. Discovery-overrides (`_apply_discovery_overrides`
 * i `prompt_to_project_input.py`) körs efter LLM-extraktionen och
 * patchar in wizardens svar deterministiskt — master-prompten är
 * därför primärt till för att hjälpa LLM att fylla i fält wizarden
 * inte täcker (notesForPlanner, businessTypeGuess, contentDepth).
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
  const cleaned = lines.map((line) => line.trim()).filter((line) => line.length > 0);
  if (cleaned.length === 0) return null;
  const bullets = cleaned.map((line) => `  - ${line}`).join("\n");
  return `${title}:\n${bullets}`;
}

function formatService(item: { name: string; price?: string; description?: string; durationMinutes?: number }): string {
  const parts: string[] = [item.name.trim()];
  if (item.price?.trim()) parts.push(`(${item.price.trim()})`);
  if (typeof item.durationMinutes === "number" && item.durationMinutes > 0) {
    parts.push(`(${item.durationMinutes} min)`);
  }
  const description = item.description?.trim();
  if (description) parts.push(`— ${description}`);
  return parts.join(" ");
}

export function composeMasterPrompt(rawPrompt: string, answers: WizardAnswers): string {
  const sections: string[] = [];
  const branch = resolveContentBranch(answers.siteType);
  const categoryLabels = answers.siteType
    .map((id) => WIZARD_CATEGORIES.find((c) => c.id === id)?.label ?? id)
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
  if (answers.companyName.trim()) companyLines.push(`Namn: ${answers.companyName.trim()}`);
  if (answers.offer.trim()) companyLines.push(`Vad vi gör: ${answers.offer.trim()}`);
  if (answers.existingSite.trim()) companyLines.push(`Befintlig hemsida: ${answers.existingSite.trim()}`);
  if (answers.contact.phone.trim()) companyLines.push(`Telefon: ${answers.contact.phone.trim()}`);
  if (answers.contact.email.trim()) companyLines.push(`E-post: ${answers.contact.email.trim()}`);
  if (answers.contact.address.trim()) companyLines.push(`Adress: ${answers.contact.address.trim()}`);
  if (answers.contact.openingHours.trim()) companyLines.push(`Öppettider: ${answers.contact.openingHours.trim()}`);
  if (companyLines.length > 0) {
    sections.push(`[Företag och kontakt]\n${companyLines.join("\n")}`);
  }

  // 3. Kategori / scaffold-signal — hjälper briefModel pinpoint:a
  // businessTypeGuess utan att gissa fritt från prompten.
  if (categoryLabels.length > 0) {
    sections.push(`[Verksamhetstyp]\nValda kategorier: ${categoryLabels.join(", ")}.\nGren: ${branch}.`);
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
      if (project.description?.trim()) parts.push(`— ${project.description.trim()}`);
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
  if (answers.priceTier.trim()) contentLines.push(`Prisnivå: ${answers.priceTier.trim()}.`);
  if (answers.bookingUrl.trim()) contentLines.push(`Bokningslänk: ${answers.bookingUrl.trim()}.`);
  const usps = listSection("Unika säljpunkter (USP)", answers.uniqueSellingPoints);
  if (usps) contentLines.push(usps);
  if (contentLines.length > 0) {
    sections.push(`[Innehåll]\n${contentLines.join("\n")}`);
  }

  // 5. Story — `company.story` / `/om-oss`-copy hämtas härifrån, men
  // vision och history hjälper LLM att forma notesForPlanner.
  const storyLines: string[] = [];
  if (answers.aboutText.trim()) storyLines.push(`Om oss: ${answers.aboutText.trim()}`);
  if (answers.historyText.trim()) storyLines.push(`Historia: ${answers.historyText.trim()}`);
  if (answers.visionText.trim()) storyLines.push(`Vision och mission: ${answers.visionText.trim()}`);
  if (answers.contactIntroText.trim()) storyLines.push(`Kontaktsidans intro: ${answers.contactIntroText.trim()}`);
  if (storyLines.length > 0) {
    sections.push(`[Story]\n${storyLines.join("\n\n")}`);
  }

  // 6. Sidor + CTA + målgrupp — direkt signal till requested_capabilities
  // (must-have-listan), conversion_goals (CTA) och target_audience.
  const pageLines: string[] = [];
  if (answers.mustHave.length > 0) {
    pageLines.push(`Sidor att bygga: ${answers.mustHave.join(", ")}.`);
  }
  if (answers.primaryCta.trim()) {
    pageLines.push(`Primär call-to-action: "${answers.primaryCta.trim()}".`);
  }
  if (answers.targetAudience.trim()) {
    pageLines.push(`Målgrupp: ${answers.targetAudience.trim()}`);
  }
  if (pageLines.length > 0) {
    sections.push(`[Sidor och konvertering]\n${pageLines.join("\n")}`);
  }

  // 7. Ton / brand / visuell stil — driver tone[] och planner-input.
  const brandLines: string[] = [];
  if (answers.brand.toneTags.length > 0) {
    brandLines.push(`Tonarter: ${answers.brand.toneTags.join(", ")}.`);
  }
  if (answers.brand.designStyle.trim()) {
    brandLines.push(`Visuell stil: ${answers.brand.designStyle.trim()}.`);
  }
  if (answers.brand.primaryColorHex.trim()) {
    brandLines.push(`Primärfärg: ${answers.brand.primaryColorHex.trim()}.`);
  }
  if (answers.brand.accentColorHex.trim()) {
    brandLines.push(`Accentfärg: ${answers.brand.accentColorHex.trim()}.`);
  }
  if (answers.brand.wordsToAvoid.trim()) {
    brandLines.push(`Undvik dessa ord och uttryck: ${answers.brand.wordsToAvoid.trim()}.`);
  }
  if (brandLines.length > 0) {
    sections.push(`[Ton och visuellt språk]\n${brandLines.join("\n")}`);
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
    const subjectNote = hero.visionSubject ? ` — visar ${hero.visionSubject}` : "";
    assetLines.push(`Hero-bild på startsidan: "${altText}"${subjectNote}.`);
  }
  if (answers.assets.gallery.length > 0) {
    assetLines.push("Galleribilder:");
    for (const item of answers.assets.gallery) {
      const altText = item.alt.trim() || "Foto";
      const placement = item.placement ?? "gallery";
      const subjectNote = item.visionSubject ? ` — ${item.visionSubject}` : "";
      assetLines.push(`  - "${altText}" (placering: ${placement})${subjectNote}`);
    }
  }
  if (assetLines.length > 0) {
    sections.push(`[Bilder och visuella tillgångar]\n${assetLines.join("\n")}`);
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
export function composeEnrichedPrompt(rawPrompt: string, answers: WizardAnswers): string {
  return composeMasterPrompt(rawPrompt, answers);
}
