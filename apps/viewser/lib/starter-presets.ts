/**
 * Starter-presets — delade "kom igång snabbt"-utgångspunkter.
 *
 * Används av två ytor:
 *   - Hero-chips på marknads-startsidan (hero-prompt-form.tsx): klick
 *     förifyller textrutan och öppnar DiscoveryWizarden med rätt
 *     verksamhetsfamilj/kategori redan vald.
 *   - Studions tom-läge (prompt-builder.tsx): samma chips visas när en
 *     besökare landar på en tom /studio utan handoff, så hen aldrig möter
 *     en blank canvas.
 *
 * Detta är INTE ett mall-galleri — produkten väljer fortfarande
 * scaffold/variant deterministiskt i backend via Discovery Resolver.
 * Presetsen sätter bara samma hints som wizardens steg 1 (familj +
 * sub-kategori) plus en naturlig svensk start-mening. ``family`` och
 * ``category`` speglar BUSINESS_FAMILIES / WIZARD_CATEGORIES i
 * discovery-wizard/wizard-constants.ts.
 */

import type {
  BusinessFamilyId,
  WizardCategoryId,
} from "@/components/discovery-wizard/wizard-constants";

export type StarterPreset = {
  id: string;
  label: string;
  family: BusinessFamilyId;
  category: WizardCategoryId;
  promptSeed: string;
};

export const STARTER_PRESETS: readonly StarterPreset[] = [
  {
    id: "frisor",
    label: "Frisörsalong",
    family: "health",
    category: "salon",
    promptSeed:
      "Jag driver en frisörsalong och vill ha en hemsida som visar stil, team och hur man bokar tid.",
  },
  {
    id: "restaurang",
    label: "Restaurang",
    family: "restaurant",
    category: "restaurant",
    promptSeed:
      "Vi är en restaurang och vill ha en hemsida med meny, bordsbokning, öppettider och vägbeskrivning.",
  },
  {
    id: "snickare",
    label: "Snickare",
    family: "construction",
    category: "construction",
    promptSeed:
      "Jag är snickare och vill ha en hemsida med referensprojekt, tjänster och offertförfrågan.",
  },
  {
    id: "webshop",
    label: "Webshop",
    family: "ecommerce",
    category: "ecommerce",
    promptSeed:
      "Vi säljer produkter online och vill ha en webshop med produktkatalog, kundvagn och kassa.",
  },
  {
    id: "klinik",
    label: "Klinik",
    family: "health",
    category: "healthcare",
    promptSeed:
      "Vi är en klinik och vill ha en trygg, professionell hemsida med tjänster, team och tidsbokning.",
  },
  {
    id: "konsult",
    label: "Konsult",
    family: "consulting",
    category: "consulting",
    promptSeed:
      "Vi är en konsultbyrå och vill ha en hemsida med tjänsteområden, case och team.",
  },
];
