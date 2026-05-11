/**
 * Stub pricing-konstanter för apps/web.
 *
 * Sajtmaskins fulla pricing.ts har modell-tier-baserad credit-uträkning + import
 * av models-katalog och OpenAI-tokens. apps/web behöver bara konstanten
 * AUDIT_COSTS för UI-rendering. Importera den fulla pricing.ts först när
 * apps/web faktiskt anropar credits-endpointen.
 */

export const AUDIT_COSTS = {
  basic: 5,
  advanced: 25,
} as const;
