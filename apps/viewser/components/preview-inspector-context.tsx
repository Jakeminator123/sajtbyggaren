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
