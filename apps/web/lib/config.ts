/**
 * Minimal apps/web config — bara det som publika UI-sidor behöver.
 *
 * apps/web är en publik UI-import från Sajtmaskin_Genberg. Den anropar inga
 * databaser, Stripe, OAuth-providers eller secret-tunga integrationer
 * direkt. Sajtmaskins fulla `lib/config.ts` med SECRETS/REDIS/FEATURES m.m.
 * är inte med — det skulle krocka med `backend.py` + `packages/generation/`.
 *
 * Om en migrerad sida visar sig behöva en flagga härifrån, lägg till den
 * defensivt och utan secrets.
 */

import { getAppBaseUrl } from "./app-url";

export const URLS = {
  get baseUrl() {
    return getAppBaseUrl();
  },
} as const;
