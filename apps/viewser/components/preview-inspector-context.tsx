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
 */

export type PlacementPick = {
  point: InsertionPoint;
  /** Grovposition som backendens router faktiskt kan styra idag. */
  coarsePosition: "top" | "bottom";
  pickedAt: number;
};

type PreviewInspectorContextValue = {
  /** Aktiv preview-URL (server-nåbar) eller null när preview saknas. */
  previewUrl: string | null;
  setPreviewUrl: (url: string | null) => void;
  /** True medan operatören väljer plats i förhandsvisningen. */
  placementPickActive: boolean;
  requestPlacementPick: () => void;
  cancelPlacementPick: () => void;
  completePlacementPick: (pick: PlacementPick) => void;
  /** Senast valda platsen — konsumeras (nollas) av dialogen som bad om den. */
  lastPlacementPick: PlacementPick | null;
  clearPlacementPick: () => void;
  /** Bumpas vid varje avslutad/avbruten pick så BuilderShell kan re-öppna dialogen. */
  placementPickResolvedSignal: number;
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
  const [lastPlacementPick, setLastPlacementPick] =
    useState<PlacementPick | null>(null);
  const [placementPickResolvedSignal, setPlacementPickResolvedSignal] =
    useState(0);

  const setPreviewUrl = useCallback((url: string | null) => {
    setPreviewUrlInternal(url);
  }, []);

  const requestPlacementPick = useCallback(() => {
    setLastPlacementPick(null);
    setPlacementPickActive(true);
  }, []);

  const cancelPlacementPick = useCallback(() => {
    setPlacementPickActive(false);
    setLastPlacementPick(null);
    setPlacementPickResolvedSignal((n) => n + 1);
  }, []);

  const completePlacementPick = useCallback((pick: PlacementPick) => {
    setPlacementPickActive(false);
    setLastPlacementPick(pick);
    setPlacementPickResolvedSignal((n) => n + 1);
  }, []);

  const clearPlacementPick = useCallback(() => {
    setLastPlacementPick(null);
  }, []);

  const value = useMemo(
    () => ({
      previewUrl,
      setPreviewUrl,
      placementPickActive,
      requestPlacementPick,
      cancelPlacementPick,
      completePlacementPick,
      lastPlacementPick,
      clearPlacementPick,
      placementPickResolvedSignal,
    }),
    [
      previewUrl,
      setPreviewUrl,
      placementPickActive,
      requestPlacementPick,
      cancelPlacementPick,
      completePlacementPick,
      lastPlacementPick,
      clearPlacementPick,
      placementPickResolvedSignal,
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
  lastPlacementPick: null,
  clearPlacementPick: () => {},
  placementPickResolvedSignal: 0,
};

/**
 * Läs preview-inspector-state. Utan provider returneras en inert
 * fallback (previewUrl=null) så peka-funktionen döljs i stället för att
 * krascha — samma degraderingsfilosofi som useDevicePreset.
 */
export function usePreviewInspector(): PreviewInspectorContextValue {
  return useContext(PreviewInspectorContext) ?? FALLBACK_VALUE;
}
