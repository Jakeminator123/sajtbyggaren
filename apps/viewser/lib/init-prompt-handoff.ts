/**
 * Handoff-seam mellan marknadssajtens hero och studions PromptBuilder.
 *
 * Operatörsmålet (juni 2026): besökaren ska kunna börja BESKRIVA sin sajt
 * direkt på den nya heron och landa rakt i bygg-flödet — utan att passera
 * studions tomma prompt-landning. Heron skriver prompten hit och navigerar
 * till ``/studio``; PromptBuildern läser (och nollar) den vid mount och
 * öppnar DiscoveryWizarden förifylld, precis som om operatören skrivit i
 * studion.
 *
 * sessionStorage (inte query-param) eftersom prompten kan vara lång (upp till
 * 4000 tecken) och inte hör hemma i URL/historik. Nyckeln rensas direkt vid
 * konsumtion så en reload av studion inte återöppnar wizarden av misstag.
 *
 * Identifierare på engelska, användarvänd text på svenska (AGENTS.md).
 */

import type { discoveryOption } from "@/components/discovery-wizard/discovery-options";
import type {
  BusinessFamilyId,
  WizardCategoryId,
} from "@/components/discovery-wizard/wizard-constants";
import type { WizardAnswers } from "@/components/discovery-wizard/wizard-types";

const INIT_PROMPT_KEY = "sajtbyggaren:init-prompt";
const WIZARD_HANDOFF_KEY = "sajtbyggaren:wizard-handoff";
const WIZARD_SEED_KEY = "sajtbyggaren:wizard-seed";

/** Heron lägger besökarens prompt här innan navigation till studion. */
export function setInitPrompt(text: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(INIT_PROMPT_KEY, text);
  } catch {
    // sessionStorage kan vara blockerat (privat läge, härdade policies).
    // Då degraderar vi tyst till "ingen handoff" — studion visar sin egen
    // prompt-ruta och besökaren skriver där istället. Ingen krasch.
  }
}

/**
 * Studion läser besökarens prompt EN gång vid mount och nollar nyckeln.
 * Returnerar null när ingen handoff finns (direktbesök på /studio, reload
 * efter konsumtion, eller blockerad storage).
 */
export function consumeInitPrompt(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.sessionStorage.getItem(INIT_PROMPT_KEY);
    if (value) window.sessionStorage.removeItem(INIT_PROMPT_KEY);
    return value;
  } catch {
    return null;
  }
}

/**
 * Rik handoff: hela wizard-resultatet (juni 2026). Operatören kör numera
 * DiscoveryWizarden DIREKT på marknads-heron — så besökaren stannar kvar på
 * den nya startsidan (hero + logotyp) medan popupen är öppen. När wizarden
 * är klar lämnas svaren hit och studion bygger direkt, utan att öppna en
 * andra wizard eller visa någon gammal start-/tom-sida.
 */
export type WizardHandoff = {
  prompt: string;
  answers: WizardAnswers;
  discoveryOptions: readonly discoveryOption[];
};

/** Heron lägger hela wizard-resultatet här innan navigation till studion. */
export function setWizardHandoff(handoff: WizardHandoff): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(WIZARD_HANDOFF_KEY, JSON.stringify(handoff));
  } catch {
    // Samma tysta degradering som setInitPrompt — utan storage faller vi
    // tillbaka på att studion öppnar wizarden själv via text-handoffen.
  }
}

/**
 * Studion läser wizard-resultatet EN gång vid mount och nollar nyckeln.
 * Returnerar null när ingen rik handoff finns (då används ev. text-handoff
 * eller, vid direktbesök, studions egen wizard).
 */
export function consumeWizardHandoff(): WizardHandoff | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(WIZARD_HANDOFF_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(WIZARD_HANDOFF_KEY);
    const parsed = JSON.parse(raw) as WizardHandoff;
    if (!parsed || typeof parsed.prompt !== "string" || !parsed.answers) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Lätt "starter"-handoff (juni 2026): en yrkessida (/for/[yrke]) eller en
 * starter-chip på heron pekar besökaren mot en bransch. I stället för att
 * landa på en tom studio lämnas en lätt seed hit — bara prompttext +
 * vald verksamhetsfamilj/kategori. Studion öppnar då DiscoveryWizarden
 * FÖRIFYLLD (men bygger INTE direkt — till skillnad från den rika
 * ``WizardHandoff``), så besökaren kan bekräfta/komplettera innan bygget.
 *
 * Skiljt från ``WizardHandoff`` med flit: seed:en bär inga fullständiga
 * wizard-svar, så vi vill alltid visa wizarden för att samla resten.
 */
export type WizardSeed = {
  prompt: string;
  businessFamily: BusinessFamilyId;
  siteType: WizardCategoryId[];
};

/** Yrkessida/starter-chip lägger en lätt seed här innan navigation till studion. */
export function setWizardSeed(seed: WizardSeed): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(WIZARD_SEED_KEY, JSON.stringify(seed));
  } catch {
    // Samma tysta degradering som övriga handoffs — utan storage öppnar
    // studion sin egen tomma wizard och besökaren väljer bransch där.
  }
}

/**
 * Studion läser seed:en EN gång vid mount och nollar nyckeln. Returnerar
 * null när ingen seed finns (direktbesök, reload efter konsumtion eller
 * blockerad storage).
 */
export function consumeWizardSeed(): WizardSeed | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(WIZARD_SEED_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(WIZARD_SEED_KEY);
    const parsed = JSON.parse(raw) as WizardSeed;
    if (
      !parsed ||
      typeof parsed.prompt !== "string" ||
      typeof parsed.businessFamily !== "string" ||
      !Array.isArray(parsed.siteType)
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}
