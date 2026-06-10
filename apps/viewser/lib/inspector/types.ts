/**
 * Preview-inspector — delade typer.
 *
 * Porterade från sajtmaskins inspector-worker-kontrakt (Jakob-OK 2026-06-10).
 * Två server-ytor delar dessa typer:
 *
 *   - POST /api/inspector-element-map  → ElementMapItem[] (DOM-karta över
 *     previewn: selector + bounding box i viewport-procent per element).
 *   - POST /api/inspector-capture      → punktbild (PNG-crop) + beskrivning
 *     av elementet närmast en klickpunkt (CapturedElement).
 *
 * Båda kör mot den RENDRADE previewn via Playwright (lokalt eller via en
 * extern inspector-worker), aldrig mot källkoden. UI:t använder kartan för
 * hover-inspektion och sektionszoner (se section-zones.ts) så operatören
 * kan peka i förhandsvisningen i stället för att beskriva läget i text.
 */

/** Ett element i DOM-kartan från /api/inspector-element-map. */
export type ElementMapItem = {
  tag: string;
  id: string | null;
  className: string | null;
  /** Normaliserad innertext, max 120 tecken. */
  text: string | null;
  /** CSS-selector (id-förankrad när möjligt, annars nth-of-type-kedja). */
  selector: string;
  /** Bounding box i CSS-pixlar relativt viewporten vid kartläggningen. */
  rect: { x: number; y: number; width: number; height: number };
  /** Bounding box i procent av viewporten — skalfri, används av overlayn. */
  vpPercent: { x: number; y: number; w: number; h: number };
  /**
   * Kanoniskt sektions-id från närmaste `[data-section-id]`-förälder
   * (sektionsmarkering i preview: codegen stämplar varje emitterad
   * sektion). null för element utanför en markerad sektion och för
   * äldre builds utan markörer — overlayn faller då tillbaka på
   * heuristiken i section-zones.ts. Valfri eftersom en extern
   * inspector-worker av äldre version inte rapporterar fältet.
   */
  sectionId?: string | null;
  /**
   * Sidans pathname vid kartläggningen ("/", "/kontakt", …) — används
   * för att mappa markeringen till routePlan-route-id:t. Valfri av
   * samma worker-kompatibilitetsskäl som sectionId.
   */
  routePath?: string | null;
};

export type ElementMapResponse = {
  success: boolean;
  elements?: ElementMapItem[];
  viewport?: { width: number; height: number };
  elementCount?: number;
  collectedAt?: string;
  error?: string;
  details?: string;
};

/** Elementbeskrivningen från /api/inspector-capture (punkt-inspektion). */
export type CapturedElement = {
  tag: string;
  id: string | null;
  className: string | null;
  text: string | null;
  ariaLabel: string | null;
  role: string | null;
  href: string | null;
  selector: string | null;
  /** Närmaste rubrik (eget closest-heading eller sektionens första heading). */
  nearestHeading: string | null;
};

export type CaptureResponse = {
  success: boolean;
  /** "worker" när extern inspector-worker svarade, "local" vid lokal Playwright. */
  source?: "worker" | "local";
  capturedUrl?: string;
  previewDataUrl?: string;
  previewMimeType?: string;
  xPercent?: number;
  yPercent?: number;
  viewportWidth?: number;
  viewportHeight?: number;
  pointSummary?: string;
  element?: CapturedElement;
  clip?: { x: number; y: number; width: number; height: number };
  error?: string;
  details?: string;
};
