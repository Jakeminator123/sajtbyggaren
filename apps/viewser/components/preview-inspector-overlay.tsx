"use client";

import { Loader2, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

import { usePreviewInspector } from "@/components/preview-inspector-context";
import {
  extractSectionZones,
  nearestInsertionPoint,
  type InsertionPoint,
} from "@/lib/inspector/section-zones";
import type { ElementMapItem, ElementMapResponse } from "@/lib/inspector/types";
import { cn } from "@/lib/utils";

/**
 * PreviewInspectorOverlay — peka-i-förhandsvisningen-lagret ovanpå
 * preview-iframen. Porterat från sajtmaskins inspector-flöde
 * (Jakob-OK 2026-06-10). Två lägen, båda drivna av samma element-karta
 * från POST /api/inspector-element-map (Playwright mot den RENDRADE
 * previewn — previewn är en cross-origin iframe vars DOM vi inte kan nå
 * direkt):
 *
 *   - Placeringsläge (placementPickActive via context): sektionszoner
 *     ritas som kontur + etikett, en insättningslinje följer musen och
 *     klick väljer platsen. Ärlighet: backendens section_add-router kan
 *     idag bara "överst"/"längst ner", så valet visar BÅDE närmaste
 *     insättningspunkt OCH vilken grovposition den faktiskt mappar till.
 *   - Inspektionsläge (inspectModeActive via context, startas från
 *     Verktyg-menyn i FloatingChat): hovring markerar minsta elementet
 *     under musen; klick visar ett info-kort (tag, text, närmaste
 *     rubrik) med kopierbar beskrivning som operatören kan klistra in
 *     i en följdprompt.
 *
 * Ren canvas-princip (operatörskrav 2026-06-10): overlayn renderar
 * INGENTING när inget läge är aktivt — inga permanenta knappar eller
 * chrome ovanpå previewn. Båda lägena startas från FloatingChat
 * (Verktyg-menyn resp. Lägg till modul-dialogen) och stängs med Esc
 * eller X-knappen i statusraden.
 *
 * Kända begränsningar (samma som originalet): kartan tas vid sidtopp
 * (scroll 0) — element under första viewporten kläms mot 100 % och
 * zoner därunder degraderar ärligt till "Längst ner". Overlayn fångar
 * mus-events medan ett läge är aktivt; annars är den pointer-genomskinlig.
 */

type MapFetchState = "idle" | "loading" | "ready" | "failed";

/** Grovposition som backendens router kan styra idag. */
function coarsePositionFor(point: InsertionPoint): "top" | "bottom" {
  return point.lineYPercent <= 50 ? "top" : "bottom";
}

const COARSE_LABELS: Record<"top" | "bottom", string> = {
  top: "hamnar överst (efter hero)",
  bottom: "hamnar längst ner",
};

type InspectedElement = {
  item: ElementMapItem;
  nearestHeading: string | null;
};

export function PreviewInspectorOverlay({
  previewUrl,
  active,
}: {
  /** Server-nåbar preview-URL (samma som iframen visar). */
  previewUrl: string;
  /** False medan preview laddar/bygger — döljer toggle + avbryter lägen. */
  active: boolean;
}) {
  const {
    placementPickActive,
    cancelPlacementPick,
    completePlacementPick,
    inspectModeActive,
    setInspectModeActive,
  } = usePreviewInspector();

  const containerRef = useRef<HTMLDivElement | null>(null);
  // Placeringsläget äger overlayn när båda råkar vara aktiva (platsvalet
  // är en pågående dialog-handling med tydligt avslut).
  const inspectMode = inspectModeActive && !placementPickActive;
  const [mapState, setMapState] = useState<MapFetchState>("idle");
  const [mapError, setMapError] = useState<string | null>(null);
  const [elementMap, setElementMap] = useState<ElementMapItem[]>([]);
  const [hoveredElement, setHoveredElement] = useState<ElementMapItem | null>(
    null,
  );
  const [hoveredInsertion, setHoveredInsertion] =
    useState<InsertionPoint | null>(null);
  const [inspected, setInspected] = useState<InspectedElement | null>(null);
  const [copied, setCopied] = useState(false);
  const fetchTokenRef = useRef(0);

  const overlayActive = active && (placementPickActive || inspectMode);

  const sectionZones = useMemo(
    () => extractSectionZones(elementMap),
    [elementMap],
  );

  const fetchElementMap = useCallback(async () => {
    const token = ++fetchTokenRef.current;
    setMapState("loading");
    setMapError(null);
    setElementMap([]);

    const rect = containerRef.current?.getBoundingClientRect();
    const width = Math.round(rect?.width || 1280);
    const height = Math.round(rect?.height || 800);

    // Upp till tre försök med kort paus — previewn kan hydrera klart
    // strax efter att operatören aktiverar läget (samma kadens-idé som
    // sajtmaskins delayed map-fetch, nedkortad eftersom iframen redan
    // hunnit ladda när togglen är synlig).
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const res = await fetch("/api/inspector-element-map", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            url: previewUrl,
            viewportWidth: width,
            viewportHeight: height,
            maxElements: 300,
          }),
        });
        const data = (await res
          .json()
          .catch(() => null)) as ElementMapResponse | null;
        if (token !== fetchTokenRef.current) return;

        if (
          res.ok &&
          data?.success &&
          Array.isArray(data.elements) &&
          data.elements.length > 0
        ) {
          setElementMap(data.elements);
          setMapState("ready");
          return;
        }
        if (!res.ok) {
          // 503 (Playwright saknas) / 502 — visa routens ärliga feltext
          // direkt, fler försök ändrar inget.
          setMapError(data?.error ?? `Kartläggningen svarade ${res.status}.`);
          setMapState("failed");
          return;
        }
      } catch {
        if (token !== fetchTokenRef.current) return;
        // Nätverksfel — prova igen efter pausen nedan.
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
      if (token !== fetchTokenRef.current) return;
    }

    setMapError(
      "Förhandsvisningen gav ingen elementkarta. Försök igen om en stund.",
    );
    setMapState("failed");
  }, [previewUrl]);

  // Hämta kartan när ett läge aktiveras; släng den när läget stängs så
  // nästa aktivering alltid kartlägger aktuell version av sajten.
  // setTimeout(0) deferar setState:n ur effektkroppen
  // (react-hooks/set-state-in-effect, samma mönster som övriga appen).
  useEffect(() => {
    if (!overlayActive) {
      fetchTokenRef.current += 1;
      return;
    }
    const timerId = window.setTimeout(() => {
      void fetchElementMap();
    }, 0);
    return () => {
      window.clearTimeout(timerId);
      fetchTokenRef.current += 1;
    };
  }, [overlayActive, fetchElementMap]);

  // Nollställ transient state när läget stängs (deferred — inte synkront
  // i effektkroppen, för react-hooks/set-state-in-effect).
  useEffect(() => {
    if (overlayActive) return;
    const timerId = window.setTimeout(() => {
      setHoveredElement(null);
      setHoveredInsertion(null);
      setInspected(null);
      setCopied(false);
      setMapState("idle");
      setMapError(null);
      setElementMap([]);
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [overlayActive]);

  // Esc avbryter placeringsläget (och stänger inspektionsläget).
  useEffect(() => {
    if (!overlayActive) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (placementPickActive) cancelPlacementPick();
      setInspectModeActive(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    overlayActive,
    placementPickActive,
    cancelPlacementPick,
    setInspectModeActive,
  ]);

  // Preview försvann/byggdes om medan ett läge var aktivt → avbryt ärligt.
  useEffect(() => {
    if (active) return;
    if (placementPickActive) cancelPlacementPick();
    if (inspectModeActive) setInspectModeActive(false);
  }, [
    active,
    placementPickActive,
    cancelPlacementPick,
    inspectModeActive,
    setInspectModeActive,
  ]);

  const relativePercent = useCallback(
    (
      event: ReactMouseEvent<HTMLDivElement>,
    ): { x: number; y: number } | null => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || rect.width <= 0 || rect.height <= 0) return null;
      const x = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
      const y = Math.min(Math.max(event.clientY - rect.top, 0), rect.height);
      return {
        x: Number(((x / rect.width) * 100).toFixed(2)),
        y: Number(((y / rect.height) * 100).toFixed(2)),
      };
    },
    [],
  );

  const handleMouseMove = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      const point = relativePercent(event);
      if (!point) return;

      if (placementPickActive) {
        setHoveredInsertion(nearestInsertionPoint(point.y, sectionZones));
        return;
      }

      if (inspectMode && elementMap.length > 0) {
        // Minsta elementet vars box innehåller punkten — samma val som
        // sajtmaskins map-engine (minst area vinner).
        let best: ElementMapItem | null = null;
        let bestArea = Infinity;
        for (const el of elementMap) {
          const vp = el.vpPercent;
          if (
            point.x >= vp.x &&
            point.x <= vp.x + vp.w &&
            point.y >= vp.y &&
            point.y <= vp.y + vp.h
          ) {
            const area = vp.w * vp.h;
            if (area < bestArea && area > 0.01) {
              best = el;
              bestArea = area;
            }
          }
        }
        setHoveredElement(best);
      }
    },
    [
      relativePercent,
      placementPickActive,
      inspectMode,
      elementMap,
      sectionZones,
    ],
  );

  const nearestHeadingFor = useCallback(
    (item: ElementMapItem): string | null => {
      // Närmaste rubrik OVANFÖR elementet i kartan — klient-approximation
      // av capture-endpointens nearestHeading (ingen extra Playwright-
      // körning per klick).
      let best: ElementMapItem | null = null;
      for (const el of elementMap) {
        if (!/^h[1-6]$/.test(el.tag)) continue;
        if (el.vpPercent.y > item.vpPercent.y + 0.5) continue;
        if (!best || el.vpPercent.y > best.vpPercent.y) best = el;
      }
      return best?.text ?? null;
    },
    [elementMap],
  );

  const handleClick = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      const point = relativePercent(event);
      if (!point) return;

      if (placementPickActive) {
        const insertion = nearestInsertionPoint(point.y, sectionZones);
        completePlacementPick({
          point: insertion,
          coarsePosition: coarsePositionFor(insertion),
          pickedAt: Date.now(),
        });
        return;
      }

      if (inspectMode && hoveredElement) {
        setCopied(false);
        setInspected({
          item: hoveredElement,
          nearestHeading: nearestHeadingFor(hoveredElement),
        });
      }
    },
    [
      relativePercent,
      placementPickActive,
      sectionZones,
      completePlacementPick,
      inspectMode,
      hoveredElement,
      nearestHeadingFor,
    ],
  );

  const handleCopyDescription = useCallback(async () => {
    if (!inspected) return;
    const { item, nearestHeading } = inspected;
    const parts: string[] = [];
    if (nearestHeading) parts.push(`I sektionen "${nearestHeading}":`);
    parts.push(`<${item.tag}>-elementet`);
    if (item.text) parts.push(`med texten "${item.text}"`);
    try {
      await navigator.clipboard.writeText(parts.join(" "));
      setCopied(true);
    } catch {
      // Clipboard kan nekas (permissions) — kortet visar texten ändå.
    }
  }, [inspected]);

  if (!active) return null;

  // Ren canvas: ingenting renderas alls när inget läge är aktivt.
  // Båda lägena startas från FloatingChat (Verktyg-menyn resp.
  // Lägg till modul-dialogen) — previewn har noll permanent chrome.
  return (
    <>
      {overlayActive ? (
        <div
          ref={containerRef}
          onMouseMove={handleMouseMove}
          onClick={handleClick}
          onMouseLeave={() => {
            setHoveredElement(null);
            setHoveredInsertion(null);
          }}
          className={cn(
            "absolute inset-0 z-[7]",
            placementPickActive ? "cursor-crosshair" : "cursor-help",
          )}
          role="application"
          aria-label={
            placementPickActive
              ? "Välj plats i förhandsvisningen"
              : "Inspektera förhandsvisningen"
          }
        >
          {/* Statusrad högst upp. */}
          <div className="pointer-events-none absolute inset-x-0 top-3 z-[9] flex justify-center px-12">
            <div className="border-border/60 bg-background/90 text-foreground flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[12px] shadow-sm backdrop-blur">
              {mapState === "loading" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                  Kartlägger förhandsvisningen…
                </>
              ) : mapState === "failed" ? (
                <span className="text-amber-700 dark:text-amber-300">
                  {mapError}
                </span>
              ) : placementPickActive ? (
                <>
                  Klicka där modulen ska placeras
                  <span className="text-muted-foreground">· Esc avbryter</span>
                </>
              ) : (
                <>
                  Hovra och klicka för att identifiera element
                  <span className="text-muted-foreground">
                    · gäller sajtens topp-vy
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Stäng-knapp — avbryter platsvalet resp. stänger inspektionen.
              Syns BARA medan ett läge är aktivt (ren canvas annars). */}
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              if (placementPickActive) {
                cancelPlacementPick();
              } else {
                setInspectModeActive(false);
              }
            }}
            className="border-border/60 bg-background/90 text-muted-foreground hover:text-foreground absolute top-3 right-3 z-[9] inline-flex h-8 w-8 items-center justify-center rounded-full border shadow-sm backdrop-blur transition"
            aria-label={
              placementPickActive ? "Avbryt platsval" : "Stäng inspektionen"
            }
          >
            <X className="h-4 w-4" aria-hidden />
          </button>

          {/* Sektionszoner som visuell kontext i placeringsläget. */}
          {placementPickActive
            ? sectionZones.map((zone) => (
                <div
                  key={zone.id}
                  className="border-foreground/20 pointer-events-none absolute inset-x-2 rounded-md border border-dashed"
                  style={{
                    top: `${zone.top}%`,
                    height: `${Math.max(zone.height, 2)}%`,
                  }}
                >
                  <span className="bg-background/80 text-muted-foreground absolute top-1 left-2 rounded px-1.5 py-0.5 text-[10px] backdrop-blur">
                    {zone.label}
                  </span>
                </div>
              ))
            : null}

          {/* Insättningslinje + ärlig grovpositions-chip. */}
          {placementPickActive && hoveredInsertion ? (
            <div
              className="pointer-events-none absolute inset-x-0 z-[8]"
              style={{
                top: `${Math.min(Math.max(hoveredInsertion.lineYPercent, 0.5), 99.5)}%`,
              }}
            >
              <div className="bg-foreground h-[2px] w-full shadow-[0_0_0_1px_rgba(255,255,255,0.6)]" />
              <div className="absolute top-1.5 left-1/2 -translate-x-1/2">
                <span className="bg-foreground text-background rounded-full px-2.5 py-1 text-[11px] font-medium whitespace-nowrap shadow">
                  {hoveredInsertion.label}
                  <span className="opacity-75">
                    {" "}
                    → {COARSE_LABELS[coarsePositionFor(hoveredInsertion)]}
                  </span>
                </span>
              </div>
            </div>
          ) : null}

          {/* Hover-highlight i inspektionsläget. */}
          {inspectMode && !placementPickActive && hoveredElement ? (
            <div
              className="border-foreground/70 bg-foreground/5 pointer-events-none absolute z-[8] rounded-sm border"
              style={{
                left: `${hoveredElement.vpPercent.x}%`,
                top: `${hoveredElement.vpPercent.y}%`,
                width: `${hoveredElement.vpPercent.w}%`,
                height: `${hoveredElement.vpPercent.h}%`,
              }}
            >
              <span className="bg-foreground text-background absolute -top-6 left-0 max-w-[260px] truncate rounded px-1.5 py-0.5 font-mono text-[10px]">
                {hoveredElement.tag}
                {hoveredElement.text
                  ? ` · ${hoveredElement.text.slice(0, 40)}`
                  : ""}
              </span>
            </div>
          ) : null}

          {/* Info-kort efter klick i inspektionsläget. */}
          {inspectMode && !placementPickActive && inspected ? (
            <div
              className="border-border/70 bg-background/95 absolute bottom-4 left-4 z-[9] w-[min(340px,calc(100%-2rem))] rounded-xl border p-3.5 shadow-lg backdrop-blur"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="mb-1.5 flex items-start justify-between gap-2">
                <span className="text-foreground font-mono text-[11px] font-semibold">
                  &lt;{inspected.item.tag}&gt;
                </span>
                <button
                  type="button"
                  onClick={() => setInspected(null)}
                  aria-label="Stäng elementinfo"
                  className="text-muted-foreground hover:text-foreground rounded p-0.5 transition"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
              {inspected.nearestHeading ? (
                <p className="text-muted-foreground text-[11px]">
                  Närmaste rubrik:{" "}
                  <span className="text-foreground">
                    {inspected.nearestHeading}
                  </span>
                </p>
              ) : null}
              {inspected.item.text ? (
                <p className="text-foreground mt-1 line-clamp-3 text-[12px] leading-snug">
                  ”{inspected.item.text}”
                </p>
              ) : (
                <p className="text-muted-foreground mt-1 text-[11px]">
                  Ingen synlig text.
                </p>
              )}
              <button
                type="button"
                onClick={() => void handleCopyDescription()}
                className="border-border/60 hover:border-border text-foreground mt-2.5 rounded-md border px-2.5 py-1 text-[11px] transition"
              >
                {copied ? "Kopierad!" : "Kopiera beskrivning till prompt"}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
