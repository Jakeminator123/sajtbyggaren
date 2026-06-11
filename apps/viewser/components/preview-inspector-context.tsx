"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { InsertionPoint } from "@/lib/inspector/section-zones";

/**
 * Preview-inspector-context — delat state mellan ViewerPanel (som äger
 * preview-iframen och ritar overlayn) och builder-dialogerna (som vill
 * låta operatören PEKA i förhandsvisningen i stället för att beskriva
 * platsen i text). Samma lift-mönster som DevicePresetProvider: ingen
 * prop-drilling genom BuilderShell, graceful fallback utan provider.
 *
 * Flödet (porterat från sajtmaskins placement-läge, Jakob-OK 2026-06-10):
 *
 *   1. ViewerPanel registrerar aktiv preview-URL via setPreviewUrl när
 *      iframen har en URL (local-next/vercel-sandbox; StackBlitz har
 *      ingen server-nåbar URL → null → peka-knappen döljs ärligt).
 *   2. AddModuleDialog anropar requestPlacementPick() och stänger sig.
 *   3. ViewerPanel ser placementPickActive, hämtar element-kartan via
 *      /api/inspector-element-map och visar sektionszoner + en
 *      insättningslinje som följer musen. Klick → completePlacementPick.
 *   4. BuilderShell ser att lastPlacementPick satts, öppnar dialogen
 *      igen, och dialogen läser ut vald position. Esc/avbryt går via
 *      cancelPlacementPick → dialogen öppnas igen utan val.
 *
 * Ärlighet: backendens section_add-router styr idag bara "överst"/
 * "längst ner". Insättningspunkten snäpper därför till topp/botten —
 * zonerna visas som visuell kontext, och anchorSection följer med i
 * picken så finare placering kan aktiveras när backend stöder det.
 *
 * Drag-läget (operatörskrav 2026-06-10): platsvalet kan bära en
 * payload (modulkort eller bild-thumbnail) som overlayn ritar som en
 * ghost-bricka som följer pekaren. Operatören släpper med klick och
 * bekräftar med "Placera här" — först då fullbordas picken. Vilken
 * dialog som bad om picken (requester) följer med så BuilderShell kan
 * öppna rätt dialog igen efteråt.
 */

export type PlacementPick = {
  point: InsertionPoint;
  /** Grovposition som backendens router faktiskt kan styra idag. */
  coarsePosition: "top" | "bottom";
  /**
   * Vald storlek i procent av sidbredden (20–96, avrundad) — sätts av
   * resize-handtagen på den dockade mockupen (operatörskrav
   * 2026-06-10). Dialogen översätter till en storleksfras i prompten
   * (+ sizePercent i toolIntent) så LLM/bygget vet hur stor
   * sektionen/bilden ska vara.
   */
  sizePercent: number;
  pickedAt: number;
};

/** Ghost-brickan som följer pekaren i drag-läget. */
export type PlacementDragPayload = {
  kind: "module" | "image";
  /** Operatörsvänlig etikett ("Galleri", filnamn). */
  label: string;
  /** Förhandsbild för kind="image" (object-URL eller publik URL). */
  thumbnailUrl?: string;
  /**
   * Modul-id (MODULE_CATALOG-nyckel) för kind="module" — låter overlayn
   * rendera en wireframe-mockup av sektionen i stället för en etikett-
   * bricka, så operatören ser ungefär hur modulen kommer se ut
   * (operatörskrav 2026-06-10).
   */
  moduleId?: string;
};

/** Vilken dialog som bad om platsvalet — styr återöppningen. */
export type PlacementRequester = "module" | "asset";

/**
 * En markerad modul i previewn (sektionsmarkering i preview): klick i
 * Markera modul-läget skapar en strukturerad referens till en kanonisk
 * sektion — routeId ur routePlan + sectionId ur scaffoldens
 * sections.json (via data-section-id-markörerna). headingText är
 * operatörsvänlig kontext (närmaste rubrik) som följer med som note i
 * /api/prompt-payloaden. Markeringen är en MJUK signal: backend
 * validerar mot base-runens emittedSections och droppar okända id:n
 * med varning i stället för att gissa.
 */
export type MarkedSectionRef = {
  routeId: string;
  sectionId: string;
  headingText?: string | null;
};

/** Max antal samtidiga modulmarkeringar — speglar /api/prompt-kontraktet. */
export const MAX_MARKED_SECTIONS = 5;

/**
 * Åtgärd vald i sektionsmenyn (klick på sektion i Markera modul-läget).
 * "Markera för prompt" hanteras direkt i overlayn (addMarkedSection) och
 * passerar aldrig hit — bara åtgärder som BuilderShell/FloatingChat ska
 * utföra signaleras:
 *
 *   - "prefill-copy" — chip + förifylld composer ("Ändra texten i …").
 *   - "asset"        — öppna AssetUploaderDialog med sektions-hint.
 *   - "module"       — öppna AddModuleDialog med förvald grovposition.
 *   - "move"         — kör section_add-followup direkt (move-semantik,
 *     ADR 0042). Visas bara för sektioner backendens inline-allowlist
 *     faktiskt kan flytta (gallery/hours-summary på home).
 */
export type SectionAction =
  | "prefill-copy"
  | "asset"
  | "module"
  | "move"
  | "colorize";

export type SectionActionRequest = {
  action: SectionAction;
  ref: MarkedSectionRef;
  /** Grov position (top/bottom) för modul-/flytt-åtgärden. */
  position?: "top" | "bottom";
  /**
   * Sektionstyp för flytt-åtgärden — samma stabila modul-id som
   * AddModuleDialog:s katalog/toolIntent ("gallery", "opening-hours").
   */
  sectionType?: string;
  /** Monoton nonce så BuilderShell kan skilja två likadana requests åt. */
  requestedAt: number;
};

type RequestPlacementPickOptions = {
  payload?: PlacementDragPayload;
  requester?: PlacementRequester;
};

type PreviewInspectorContextValue = {
  /** Aktiv preview-URL (server-nåbar) eller null när preview saknas. */
  previewUrl: string | null;
  setPreviewUrl: (url: string | null) => void;
  /** True medan operatören väljer plats i förhandsvisningen. */
  placementPickActive: boolean;
  requestPlacementPick: (options?: RequestPlacementPickOptions) => void;
  cancelPlacementPick: () => void;
  completePlacementPick: (pick: PlacementPick) => void;
  /** Ghost-payload för pågående drag-pick (null = klassisk linjepick). */
  placementDragPayload: PlacementDragPayload | null;
  /** Dialogen som bad om aktuell/senaste pick (default "module"). */
  placementRequester: PlacementRequester;
  /** Senast valda platsen — konsumeras (nollas) av dialogen som bad om den. */
  lastPlacementPick: PlacementPick | null;
  clearPlacementPick: () => void;
  /** Bumpas vid varje avslutad/avbruten pick så BuilderShell kan re-öppna dialogen. */
  placementPickResolvedSignal: number;
  /**
   * Inspektera-läget (hover-highlight + element-info). Startas från
   * Verktyg-menyn i FloatingChat — INGEN permanent knapp på canvasen,
   * previewn är helt ren tills operatören aktivt slår på ett läge.
   */
  inspectModeActive: boolean;
  setInspectModeActive: (active: boolean) => void;
  /**
   * Markera modul-läget (sektionsmarkering i preview): klick på en
   * sektion skapar en strukturerad markering som visas som chip i
   * FloatingChat-composern och skickas som markedSections[] i nästa
   * följdprompt. Startas från Verktyg-menyn, precis som inspektionen.
   */
  markModeActive: boolean;
  setMarkModeActive: (active: boolean) => void;
  /** Aktiva modulmarkeringar (max MAX_MARKED_SECTIONS, dedupe på route+sektion). */
  markedSections: MarkedSectionRef[];
  addMarkedSection: (ref: MarkedSectionRef) => void;
  removeMarkedSection: (routeId: string, sectionId: string) => void;
  clearMarkedSections: () => void;
  /**
   * Senaste åtgärds-request från sektionsmenyn (overlayn) — konsumeras
   * (nollas) av BuilderShell. Null när ingen åtgärd väntar.
   */
  sectionActionRequest: SectionActionRequest | null;
  requestSectionAction: (
    request: Omit<SectionActionRequest, "requestedAt">,
  ) => void;
  clearSectionAction: () => void;
  /**
   * Hela preview-sidans höjd i CSS-pixlar — sätts av overlayn när
   * elementkartan (med documentHeightPx) hämtats och nollas när läget
   * stängs. ViewerPanel renderar då iframen i full sidhöjd inuti en
   * skrollbar wrapper så operatören kan skrolla previewn MED overlayn
   * (overlayn ovanpå iframen fångar annars alla wheel-events och
   * cross-origin-iframen kan aldrig skrollas — operatörsbugg
   * 2026-06-10). null = normal viewport-hög iframe med intern skroll.
   */
  previewPageHeightPx: number | null;
  setPreviewPageHeightPx: (height: number | null) => void;
  /**
   * True medan ett bygge som startades av "Placera här" pågår.
   * BuilderShell sätter true vid bekräftat släpp; ViewerPanel renderar
   * då den nordiska 0–100-bannern I STÄLLET för BuildProgressCard och
   * nollar flaggan när previewn tagit över igen (operatörskrav
   * 2026-06-10: ingen dialog-studs efter placering).
   */
  placementBuildActive: boolean;
  setPlacementBuildActive: (active: boolean) => void;
};

const PreviewInspectorContext =
  createContext<PreviewInspectorContextValue | null>(null);

export function PreviewInspectorProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [previewUrl, setPreviewUrlInternal] = useState<string | null>(null);
  const [placementPickActive, setPlacementPickActive] = useState(false);
  const [placementDragPayload, setPlacementDragPayload] =
    useState<PlacementDragPayload | null>(null);
  const [placementRequester, setPlacementRequester] =
    useState<PlacementRequester>("module");
  const [lastPlacementPick, setLastPlacementPick] =
    useState<PlacementPick | null>(null);
  const [placementPickResolvedSignal, setPlacementPickResolvedSignal] =
    useState(0);
  const [inspectModeActive, setInspectModeActiveInternal] = useState(false);
  const [markModeActive, setMarkModeActiveInternal] = useState(false);
  const [markedSections, setMarkedSections] = useState<MarkedSectionRef[]>([]);
  const [sectionActionRequest, setSectionActionRequest] =
    useState<SectionActionRequest | null>(null);
  const [previewPageHeightPx, setPreviewPageHeightPx] = useState<number | null>(
    null,
  );
  const [placementBuildActive, setPlacementBuildActive] = useState(false);

  const setPreviewUrl = useCallback((url: string | null) => {
    setPreviewUrlInternal(url);
  }, []);

  const requestPlacementPick = useCallback(
    (options?: RequestPlacementPickOptions) => {
      setLastPlacementPick(null);
      setPlacementDragPayload(options?.payload ?? null);
      setPlacementRequester(options?.requester ?? "module");
      setPlacementPickActive(true);
    },
    [],
  );

  const cancelPlacementPick = useCallback(() => {
    setPlacementPickActive(false);
    setPlacementDragPayload(null);
    setLastPlacementPick(null);
    setPlacementPickResolvedSignal((n) => n + 1);
  }, []);

  const completePlacementPick = useCallback((pick: PlacementPick) => {
    setPlacementPickActive(false);
    setPlacementDragPayload(null);
    setLastPlacementPick(pick);
    setPlacementPickResolvedSignal((n) => n + 1);
  }, []);

  const clearPlacementPick = useCallback(() => {
    setLastPlacementPick(null);
  }, []);

  const setInspectModeActive = useCallback((active: boolean) => {
    setInspectModeActiveInternal(active);
    // Granska och Markera modul delar overlay-ytan — bara ett läge i taget.
    if (active) setMarkModeActiveInternal(false);
  }, []);

  const setMarkModeActive = useCallback((active: boolean) => {
    setMarkModeActiveInternal(active);
    if (active) setInspectModeActiveInternal(false);
  }, []);

  const addMarkedSection = useCallback((ref: MarkedSectionRef) => {
    setMarkedSections((prev) => {
      const exists = prev.some(
        (item) =>
          item.routeId === ref.routeId && item.sectionId === ref.sectionId,
      );
      if (exists || prev.length >= MAX_MARKED_SECTIONS) return prev;
      return [...prev, ref];
    });
  }, []);

  const removeMarkedSection = useCallback(
    (routeId: string, sectionId: string) => {
      setMarkedSections((prev) =>
        prev.filter(
          (item) => !(item.routeId === routeId && item.sectionId === sectionId),
        ),
      );
    },
    [],
  );

  const clearMarkedSections = useCallback(() => {
    setMarkedSections([]);
  }, []);

  const requestSectionAction = useCallback(
    (request: Omit<SectionActionRequest, "requestedAt">) => {
      setSectionActionRequest({ ...request, requestedAt: Date.now() });
    },
    [],
  );

  const clearSectionAction = useCallback(() => {
    setSectionActionRequest(null);
  }, []);

  const value = useMemo(
    () => ({
      previewUrl,
      setPreviewUrl,
      placementPickActive,
      requestPlacementPick,
      cancelPlacementPick,
      completePlacementPick,
      placementDragPayload,
      placementRequester,
      lastPlacementPick,
      clearPlacementPick,
      placementPickResolvedSignal,
      inspectModeActive,
      setInspectModeActive,
      markModeActive,
      setMarkModeActive,
      markedSections,
      addMarkedSection,
      removeMarkedSection,
      clearMarkedSections,
      sectionActionRequest,
      requestSectionAction,
      clearSectionAction,
      previewPageHeightPx,
      setPreviewPageHeightPx,
      placementBuildActive,
      setPlacementBuildActive,
    }),
    [
      previewUrl,
      setPreviewUrl,
      placementPickActive,
      requestPlacementPick,
      cancelPlacementPick,
      completePlacementPick,
      placementDragPayload,
      placementRequester,
      lastPlacementPick,
      clearPlacementPick,
      placementPickResolvedSignal,
      inspectModeActive,
      setInspectModeActive,
      markModeActive,
      setMarkModeActive,
      markedSections,
      addMarkedSection,
      removeMarkedSection,
      clearMarkedSections,
      sectionActionRequest,
      requestSectionAction,
      clearSectionAction,
      previewPageHeightPx,
      setPreviewPageHeightPx,
      placementBuildActive,
      setPlacementBuildActive,
    ],
  );

  return (
    <PreviewInspectorContext.Provider value={value}>
      {children}
    </PreviewInspectorContext.Provider>
  );
}

const FALLBACK_VALUE: PreviewInspectorContextValue = {
  previewUrl: null,
  setPreviewUrl: () => {},
  placementPickActive: false,
  requestPlacementPick: () => {},
  cancelPlacementPick: () => {},
  completePlacementPick: () => {},
  placementDragPayload: null,
  placementRequester: "module",
  lastPlacementPick: null,
  clearPlacementPick: () => {},
  placementPickResolvedSignal: 0,
  inspectModeActive: false,
  setInspectModeActive: () => {},
  markModeActive: false,
  setMarkModeActive: () => {},
  markedSections: [],
  addMarkedSection: () => {},
  removeMarkedSection: () => {},
  clearMarkedSections: () => {},
  sectionActionRequest: null,
  requestSectionAction: () => {},
  clearSectionAction: () => {},
  previewPageHeightPx: null,
  setPreviewPageHeightPx: () => {},
  placementBuildActive: false,
  setPlacementBuildActive: () => {},
};

/**
 * Läs preview-inspector-state. Utan provider returneras en inert
 * fallback (previewUrl=null) så peka-funktionen döljs i stället för att
 * krascha — samma degraderingsfilosofi som useDevicePreset.
 */
export function usePreviewInspector(): PreviewInspectorContextValue {
  return useContext(PreviewInspectorContext) ?? FALLBACK_VALUE;
}
