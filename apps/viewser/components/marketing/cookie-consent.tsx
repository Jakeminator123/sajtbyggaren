"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// CMP-lite för marknadssajten. Lagrar operatörens cookie-val i localStorage
// (versionerad nyckel) utan tung tredjepart. Analytics är AV som default —
// vi sätter inga icke-nödvändiga cookies förrän användaren aktivt accepterat.
//
// Storage-läsningen post-mount följer samma async-IIFE-mönster som
// DevicePresetContext (await Promise.resolve() före setState) för att passera
// React 19:s react-hooks/set-state-in-effect. SSR + första klient-render har
// ready=false → varken banner eller manager renderas → ingen hydration-
// mismatch.
export type CookieConsent = "granted" | "denied";

const STORAGE_KEY = "sajtbyggaren.cookie-consent.v1";

type CookieConsentValue = {
  /** True först när storage-läsningen post-mount är klar. */
  ready: boolean;
  /** null = inget val gjort ännu (banner ska visas). */
  consent: CookieConsent | null;
  managerOpen: boolean;
  accept: () => void;
  decline: () => void;
  openManager: () => void;
  closeManager: () => void;
};

const Ctx = createContext<CookieConsentValue | null>(null);

export function CookieConsentProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [consent, setConsent] = useState<CookieConsent | null>(null);
  const [managerOpen, setManagerOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "granted" || stored === "denied") setConsent(stored);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback((value: CookieConsent) => {
    setConsent(value);
    setManagerOpen(false);
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Privat läge / blockerad storage: behåll valet i minnet för sessionen.
    }
  }, []);

  const value = useMemo<CookieConsentValue>(
    () => ({
      ready,
      consent,
      managerOpen,
      accept: () => persist("granted"),
      decline: () => persist("denied"),
      openManager: () => setManagerOpen(true),
      closeManager: () => setManagerOpen(false),
    }),
    [ready, consent, managerOpen, persist],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Hook. Defensiv no-op-fallback om provider saknas (tester/fel-monterat träd). */
export function useCookieConsent(): CookieConsentValue {
  const ctx = useContext(Ctx);
  if (ctx) return ctx;
  return {
    ready: false,
    consent: null,
    managerOpen: false,
    accept: () => {},
    decline: () => {},
    openManager: () => {},
    closeManager: () => {},
  };
}
