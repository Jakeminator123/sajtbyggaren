"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Monitor, Smartphone, Tablet } from "lucide-react";

/**
 * DevicePreset — operatörens valda preview-bredd på desktop. Sätts via
 * device-toggle-baren (numera i FloatingChat:s footer) som constraint:ar
 * iframe-wrappern till en max-width matchande typiska viewports.
 *
 * Värden:
 *   - "mobile"  → 375px (iPhone SE / 12 mini bredd)
 *   - "tablet"  → 768px (iPad mini portrait)
 *   - "laptop"  → 1024px (vanlig laptop-canvas-bredd)
 *   - "full"    → ingen constraint (default; iframe fyller canvasen)
 *
 * State delas mellan ViewerPanel (iframe-constraint) och FloatingChat
 * (toggle-UI) via denna context för att slippa prop-drilling genom
 * BuilderShell och samtidigt hålla state lifted så toggle-UI:t inte är
 * fysiskt bundet till canvas-toppen längre.
 *
 * Valet persisterar i sessionStorage så valet behålls tills tab/flik
 * stängs. Nästa gång samma operatör öppnar viewser i en ny tab börjar
 * det därför alltid på "full" (sessionStorage är per-tab, inte
 * cross-session).
 */
export type DevicePreset = "mobile" | "tablet" | "laptop" | "full";

export const DEVICE_PRESET_WIDTHS: Record<DevicePreset, number | null> = {
  mobile: 375,
  tablet: 768,
  laptop: 1024,
  full: null,
};

const DEVICE_STORAGE_KEY = "viewser:device-preset";

export const DEVICE_PRESET_OPTIONS: ReadonlyArray<{
  id: DevicePreset;
  label: string;
  Icon: typeof Monitor;
  width: number | null;
}> = [
  { id: "mobile", label: "375", Icon: Smartphone, width: 375 },
  { id: "tablet", label: "768", Icon: Tablet, width: 768 },
  { id: "laptop", label: "1024", Icon: Monitor, width: 1024 },
  { id: "full", label: "Full", Icon: Monitor, width: null },
];

type DevicePresetContextValue = {
  devicePreset: DevicePreset;
  setDevicePreset: (next: DevicePreset) => void;
};

const DevicePresetContext = createContext<DevicePresetContextValue | null>(
  null,
);

export function DevicePresetProvider({ children }: { children: ReactNode }) {
  // Initialiseras ALLTID till "full" på SSR + första klient-render så
  // server- och klient-output är identiska och vi slipper hydration-
  // mismatch. Faktiskt valt värde läses från sessionStorage post-mount
  // i useEffect nedan (samma async-IIFE-mönster som ViewerPanel hade
  // tidigare för att passera React 19:s react-hooks/set-state-in-effect-
  // regel).
  const [devicePreset, setDevicePresetInternal] =
    useState<DevicePreset>("full");

  // Gating-flag: persist-effekten skriver INTE till sessionStorage förrän
  // hydration-effekten har kört sin first-mount-läsning. Annars skriver
  // initial "full" över ett sparat värde innan vi hinner läsa det
  // (scout-fynd 2026-05-26: reload nollställde valet till Full).
  const hasHydratedRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      const stored = window.sessionStorage.getItem(DEVICE_STORAGE_KEY);
      if (
        stored === "mobile" ||
        stored === "tablet" ||
        stored === "laptop" ||
        stored === "full"
      ) {
        setDevicePresetInternal(stored);
      }
      hasHydratedRef.current = true;
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!hasHydratedRef.current) return;
    window.sessionStorage.setItem(DEVICE_STORAGE_KEY, devicePreset);
  }, [devicePreset]);

  const setDevicePreset = useCallback((next: DevicePreset) => {
    setDevicePresetInternal(next);
  }, []);

  const value = useMemo(
    () => ({ devicePreset, setDevicePreset }),
    [devicePreset, setDevicePreset],
  );

  return (
    <DevicePresetContext.Provider value={value}>
      {children}
    </DevicePresetContext.Provider>
  );
}

/**
 * Hook för att läsa + sätta device-preset från valfri komponent i
 * trädet under DevicePresetProvider. Faller tillbaka till "full" + no-op
 * setter om provider saknas (defensiv default så vi inte kraschar i
 * tester eller om någon glömmer wrappa). Detta gör hooken trygg att
 * använda även i top-level layouts/storybook.
 */
export function useDevicePreset(): DevicePresetContextValue {
  const ctx = useContext(DevicePresetContext);
  if (ctx) return ctx;
  return {
    devicePreset: "full",
    setDevicePreset: () => {
      // Tyst no-op när provider saknas. Eftersom denna fallback bara
      // träffas i tester / fel-monterade träd, gör vi ingen console-
      // varning för att undvika spam i normal körning.
    },
  };
}
