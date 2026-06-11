"use client";

import {
  ArrowDownToLine,
  ArrowUpToLine,
  Blocks,
  ImagePlus,
  Loader2,
  MessageSquareText,
  Move,
  Palette,
  Pin,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { ModuleMockup } from "@/components/builder/module-mockups";
import {
  usePreviewInspector,
  type MarkedSectionRef,
} from "@/components/preview-inspector-context";
import {
  extractSectionZones,
  nearestInsertionPoint,
  type InsertionPoint,
  type SectionZone,
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
 *     ritas som kontur + etikett, en insättningslinje följer musen.
 *     Bär picken en drag-payload (modulkort/bild-thumbnail) följer även
 *     en ghost-bricka pekaren. Klick SLÄPPER vid närmaste insättnings-
 *     punkt och operatören bekräftar med "Placera här" (eller flyttar
 *     genom att klicka någon annanstans / Esc för att ångra släppet).
 *     Ärlighet: backendens section_add-router kan idag bara "överst"/
 *     "längst ner", så valet visar BÅDE närmaste insättningspunkt OCH
 *     vilken grovposition den faktiskt mappar till.
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
 * Skroll (operatörsbugg 2026-06-10: "kan inte skrolla i markläge"):
 * overlayn fångar alla mus-events medan ett läge är aktivt, och en
 * cross-origin-iframe kan aldrig skrollas via förälder-events. Lösningen
 * är att den lokala kartläggningen numera räknar y/h mot HELA dokument-
 * höjden och skickar med documentHeightPx — overlayn publicerar höjden
 * via contexten (setPreviewPageHeightPx) och ViewerPanel renderar då
 * iframen i full sidhöjd inuti en skrollbar wrapper, så preview och
 * overlay skrollar ihop med bibehållen kartjustering. Statusrad, X-knapp
 * och info-kort ligger i sticky h-0-wrappers så de följer skrollporten.
 *
 * Kvarvarande begränsning: en extern inspector-worker (vercel-sandbox-
 * previews) svarar utan documentHeightPx och med viewport-relativa
 * procent — då degraderar overlayn ärligt till det gamla topp-vy-
 * beteendet utan skroll. Overlayn fångar mus-events medan ett läge är
 * aktivt; annars är den pointer-genomskinlig.
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

/** Storleksgränser för den dockade mockupen (% av sidbredden). */
const DROP_SIZE_MIN = 20;
const DROP_SIZE_MAX = 96;
/** Startstorlek per payload-typ — moduler är sektioner, bilder mindre. */
const DROP_SIZE_DEFAULTS: Record<"module" | "image", number> = {
  module: 60,
  image: 36,
};

function clampDropSize(percent: number): number {
  return Math.min(DROP_SIZE_MAX, Math.max(DROP_SIZE_MIN, percent));
}

/**
 * Resize-handtag runt den dockade mockupen — samma åtta-punkts-layout
 * som fönster-resizen i FloatingChat (operatörskrav 2026-06-10: "som
 * floating chat-fönstret"). Kanterna är smala band strax utanför boxen,
 * hörnen större träffytor med diagonal-cursor.
 */
type DropResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

const DROP_RESIZE_HANDLES: ReadonlyArray<[DropResizeEdge, string]> = [
  ["n", "-top-1.5 right-4 left-4 h-3 cursor-ns-resize"],
  ["s", "right-4 -bottom-1.5 left-4 h-3 cursor-ns-resize"],
  ["e", "top-4 -right-1.5 bottom-4 w-3 cursor-ew-resize"],
  ["w", "top-4 bottom-4 -left-1.5 w-3 cursor-ew-resize"],
  ["ne", "-top-2 -right-2 h-5 w-5 cursor-nesw-resize"],
  ["nw", "-top-2 -left-2 h-5 w-5 cursor-nwse-resize"],
  ["se", "-right-2 -bottom-2 h-5 w-5 cursor-nwse-resize"],
  ["sw", "-bottom-2 -left-2 h-5 w-5 cursor-nesw-resize"],
];

type InspectedElement = {
  item: ElementMapItem;
  nearestHeading: string | null;
};

/**
 * En markerbar sektion i Markera modul-läget. Kanonisk när den kommer
 * från en data-section-id-markör i den rendrade previewn; heuristisk
 * (canonical=false) på äldre builds utan markörer — då skickas
 * heuristikens sektionstyp som id och backendens valideringsgrind
 * droppar okända id:n med varning i stället för att gissa.
 */
type MarkableSection = {
  sectionId: string;
  top: number;
  bottom: number;
  left: number;
  width: number;
  headingText: string | null;
  canonical: boolean;
};

/**
 * Sektioner backendens section_add-pipeline faktiskt kan FLYTTA (ADR
 * 0042, move-semantik när sektionen redan finns). Speglar
 * ``INLINE_SECTION_PLACEMENTS`` i
 * packages/generation/followup/section_directives.py: nyckeln är
 * sektionens data-section-id i previewn, värdet är det stabila modul-id
 * som AddModuleDialog/toolIntent använder. Flytt gäller bara home-routen
 * (``INLINE_SECTION_ROUTES``). Source-lockad i
 * tests/test_marked_sections_followup.py — ändra ALDRIG den här listan
 * utan att backend-allowlisten ändrats först (ärlighetsprincipen:
 * menyn ljuger aldrig om kapacitet).
 */
const MOVABLE_SECTION_TYPES: Record<string, string> = {
  gallery: "gallery",
  "hours-summary": "opening-hours",
};

/** Routes där flytt-åtgärden stöds — speglar INLINE_SECTION_ROUTES. */
const MOVABLE_SECTION_ROUTE = "home";

/**
 * Sektionsmenyn (klick i markläge): ankare + vilken sektion den gäller.
 * routeId är redan upplöst via routePlan-kartan vid klicket.
 */
type SectionActionMenuState = {
  section: MarkableSection;
  routeId: string;
  /** Klickpunkten i procent av overlay-ytan — menyn ankras här. */
  anchorXPercent: number;
  anchorYPercent: number;
};

/** Mappa previewns pathname till routePlan-route-id ("/" → home). */
function routeIdForPath(
  path: string | null | undefined,
  pathToRouteId: Record<string, string>,
): string {
  const segment = (path || "/").replace(/^\/+|\/+$/g, "");
  const mapped = pathToRouteId[segment];
  if (mapped) return mapped;
  return segment || "home";
}

export function PreviewInspectorOverlay({
  previewUrl,
  active,
  runId,
}: {
  /** Server-nåbar preview-URL (samma som iframen visar). */
  previewUrl: string;
  /** False medan preview laddar/bygger — döljer toggle + avbryter lägen. */
  active: boolean;
  /**
   * Aktiv run — används av Markera modul-läget för att läsa routePlan
   * (path → routeId) ur runens artefakter. null → segment-fallback.
   */
  runId?: string | null;
}) {
  const {
    placementPickActive,
    cancelPlacementPick,
    completePlacementPick,
    placementDragPayload,
    inspectModeActive,
    setInspectModeActive,
    markModeActive,
    setMarkModeActive,
    markedSections,
    addMarkedSection,
    requestSectionAction,
    previewPageHeightPx,
    setPreviewPageHeightPx,
  } = usePreviewInspector();

  const containerRef = useRef<HTMLDivElement | null>(null);
  // Placeringsläget äger overlayn när båda råkar vara aktiva (platsvalet
  // är en pågående dialog-handling med tydligt avslut). Contexten håller
  // granska/markera ömsesidigt uteslutande, så ordningen här är bara
  // ett bälte-och-hängslen-skydd.
  const markMode = markModeActive && !placementPickActive;
  const inspectMode = inspectModeActive && !placementPickActive && !markMode;
  const [mapState, setMapState] = useState<MapFetchState>("idle");
  const [mapError, setMapError] = useState<string | null>(null);
  const [elementMap, setElementMap] = useState<ElementMapItem[]>([]);
  const [hoveredElement, setHoveredElement] = useState<ElementMapItem | null>(
    null,
  );
  const [hoveredInsertion, setHoveredInsertion] =
    useState<InsertionPoint | null>(null);
  // Släppt-men-obekräftad insättningspunkt i drag-läget: klick släpper
  // brickan här, "Placera här" bekräftar, nytt klick flyttar, Esc ångrar.
  const [pendingDrop, setPendingDrop] = useState<InsertionPoint | null>(null);
  // Vald storlek (% av sidbredden) för den dockade mockupen — justeras
  // med resize-handtagen på boxens kanter/hörn och följer med i picken
  // så prompten kan beskriva hur stor sektionen/bilden ska vara.
  const [dropSizePercent, setDropSizePercent] = useState(
    DROP_SIZE_DEFAULTS.module,
  );
  // Pågående kant-/hörn-drag på den dockade boxen: edge + startposition
  // + startbredd.
  const dropResizeRef = useRef<{
    edge: DropResizeEdge;
    pointerX: number;
    pointerY: number;
    originPercent: number;
  } | null>(null);
  const [isDropResizing, setIsDropResizing] = useState(false);
  // Pågående direkt-drag av den dockade boxen (grab-och-flytta).
  const dropDragRef = useRef<{ pointerId: number } | null>(null);
  const [isDropDragging, setIsDropDragging] = useState(false);
  // Ghost-brickan följer pekaren via DIREKTA style-skrivningar på den här
  // ref:en — inte via state. Ett setState per mousemove re-renderade hela
  // overlayn (zoner + mockup-SVG) och kändes laggigt (operatörsfynd
  // 2026-06-10); style.left/top på en befintlig nod är en ren composite.
  const ghostRef = useRef<HTMLDivElement | null>(null);
  // Senast satta insättningspunkt — så hover bara gör setState när
  // NÄRMASTE punkt faktiskt byts (linjen flyttar sig), inte per pixel.
  const lastInsertionRef = useRef<InsertionPoint | null>(null);
  const [inspected, setInspected] = useState<InspectedElement | null>(null);
  const [copied, setCopied] = useState(false);
  // Markera modul-läget: hovrad sektion + path→routeId-karta ur runens
  // site-plan (routePlan). Kartan hämtas lazily när läget aktiveras.
  const [hoveredMarkable, setHoveredMarkable] =
    useState<MarkableSection | null>(null);
  // Sektionsmenyn: öppnas vid klick på en sektion i markläge i stället
  // för att direkt lägga chip. Null = ingen meny öppen.
  const [actionMenu, setActionMenu] = useState<SectionActionMenuState | null>(
    null,
  );
  const [pathToRouteId, setPathToRouteId] = useState<Record<string, string>>(
    {},
  );
  const routeMapTokenRef = useRef(0);
  const fetchTokenRef = useRef(0);

  const overlayActive =
    active && (placementPickActive || inspectMode || markMode);

  const sectionZones = useMemo(
    () => extractSectionZones(elementMap),
    [elementMap],
  );

  // Markerbara sektioner: primärt elementen som BÄR data-section-id-
  // markören (tag=section), sekundärt heuristik-zonerna för äldre builds
  // utan markörer. Kanoniska sektioner deduplas på id (hero emitterar
  // två <section> för samma id — vi slår ihop till en sammanhängande yta).
  const markableSections = useMemo<MarkableSection[]>(() => {
    const canonical = new Map<string, MarkableSection>();
    for (const el of elementMap) {
      if (!el.sectionId) continue;
      if (el.tag !== "section") continue;
      const top = el.vpPercent.y;
      const bottom = el.vpPercent.y + el.vpPercent.h;
      const existing = canonical.get(el.sectionId);
      if (existing) {
        existing.top = Math.min(existing.top, top);
        existing.bottom = Math.max(existing.bottom, bottom);
        continue;
      }
      // Närmaste rubrik inom sektionen (första h1–h6 i kart-ordningen
      // vars y ligger inom sektionens band) som operatörsvänlig kontext.
      let heading: string | null = null;
      for (const candidate of elementMap) {
        if (candidate.sectionId !== el.sectionId) continue;
        if (!/^h[1-6]$/.test(candidate.tag)) continue;
        heading = candidate.text;
        break;
      }
      canonical.set(el.sectionId, {
        sectionId: el.sectionId,
        top,
        bottom,
        left: el.vpPercent.x,
        width: el.vpPercent.w,
        headingText: heading,
        canonical: true,
      });
    }
    if (canonical.size > 0) {
      return Array.from(canonical.values()).sort((a, b) => a.top - b.top);
    }
    // Fallback för builds utan markörer: heuristik-zonerna. Id:t blir
    // heuristikens sektionstyp — backendens grind validerar ärligt.
    return sectionZones.map((zone: SectionZone) => ({
      sectionId: zone.type,
      top: zone.top,
      bottom: zone.bottom,
      left: 0,
      width: 100,
      headingText: zone.label,
      canonical: false,
    }));
  }, [elementMap, sectionZones]);

  // Route-id-kartan (path → routeId) ur runens site-plan. Hämtas när
  // Markera modul-läget aktiveras; utan run/plan faller markeringen
  // tillbaka på path-segmentet (routeIdForPath).
  useEffect(() => {
    if (!markMode || !runId) return;
    const token = ++routeMapTokenRef.current;
    void (async () => {
      try {
        const response = await fetch(`/api/runs/${runId}/artifacts`);
        const bundle = (await response.json().catch(() => null)) as {
          sitePlan?: { routePlan?: unknown } | null;
        } | null;
        if (token !== routeMapTokenRef.current) return;
        const routePlan = bundle?.sitePlan?.routePlan;
        if (!Array.isArray(routePlan)) return;
        const mapping: Record<string, string> = {};
        for (const entry of routePlan) {
          if (!entry || typeof entry !== "object") continue;
          const id = (entry as { id?: unknown }).id;
          const path = (entry as { path?: unknown }).path;
          if (typeof id !== "string" || typeof path !== "string") continue;
          mapping[path.replace(/^\/+|\/+$/g, "")] = id;
        }
        setPathToRouteId(mapping);
      } catch {
        // Plan saknas/oläsbar — segment-fallbacken gäller.
      }
    })();
    return () => {
      routeMapTokenRef.current += 1;
    };
  }, [markMode, runId]);

  const fetchElementMap = useCallback(async () => {
    const token = ++fetchTokenRef.current;
    setMapState("loading");
    setMapError(null);
    setElementMap([]);

    // Bredd från containern (följer device-preset), höjd från operatörens
    // fönster — containern kan redan vara uppdragen till full sidhöjd
    // från en tidigare kartläggning och får inte blåsa upp Playwright-
    // viewporten.
    const rect = containerRef.current?.getBoundingClientRect();
    const width = Math.round(rect?.width || 1280);
    const height = Math.min(Math.round(window.innerHeight || 800), 1600);

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
            // Kartan täcker numera HELA sidan (dokument-relativa
            // koordinater) — 600 är routens tak och behövs för att
            // längre sidor inte ska kapas under folden.
            maxElements: 600,
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
          // Full sidhöjd från den lokala Playwright-vägen → ViewerPanel
          // gör previewn skrollbar i full höjd så overlay + iframe
          // skrollar ihop. Extern worker (utan documentHeightPx) →
          // null → ärlig topp-vy som tidigare.
          setPreviewPageHeightPx(
            typeof data.documentHeightPx === "number" &&
              data.documentHeightPx > 0
              ? Math.round(data.documentHeightPx)
              : null,
          );
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
  }, [previewUrl, setPreviewPageHeightPx]);

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
      setPendingDrop(null);
      setInspected(null);
      setCopied(false);
      setHoveredMarkable(null);
      setActionMenu(null);
      setMapState("idle");
      setMapError(null);
      setElementMap([]);
      // Tillbaka till normal viewport-hög iframe med intern skroll.
      setPreviewPageHeightPx(null);
      dropResizeRef.current = null;
      setIsDropResizing(false);
      dropDragRef.current = null;
      setIsDropDragging(false);
      lastInsertionRef.current = null;
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [overlayActive, setPreviewPageHeightPx]);

  // Startstorlek per payload-typ när ett nytt placeringsläge öppnas
  // (moduler dockas som halvbreda sektioner, bilder mindre).
  useEffect(() => {
    if (!placementPickActive) return;
    const kind = placementDragPayload?.kind ?? "module";
    const timerId = window.setTimeout(() => {
      setDropSizePercent(DROP_SIZE_DEFAULTS[kind]);
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [placementPickActive, placementDragPayload]);

  // Esc: ångra ett obekräftat släpp först; annars avbryt placerings-
  // läget (och stäng inspektions-/markeringsläget).
  useEffect(() => {
    if (!overlayActive) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (placementPickActive) {
        if (pendingDrop) {
          setPendingDrop(null);
          return;
        }
        cancelPlacementPick();
      }
      // I markläge stänger Esc sektionsmenyn först; nästa Esc avslutar läget.
      if (actionMenu) {
        setActionMenu(null);
        return;
      }
      setInspectModeActive(false);
      setMarkModeActive(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    overlayActive,
    placementPickActive,
    pendingDrop,
    actionMenu,
    cancelPlacementPick,
    setInspectModeActive,
    setMarkModeActive,
  ]);

  // Preview försvann/byggdes om medan ett läge var aktivt → avbryt ärligt.
  useEffect(() => {
    if (active) return;
    if (placementPickActive) cancelPlacementPick();
    if (inspectModeActive) setInspectModeActive(false);
    if (markModeActive) setMarkModeActive(false);
  }, [
    active,
    placementPickActive,
    cancelPlacementPick,
    inspectModeActive,
    setInspectModeActive,
    markModeActive,
    setMarkModeActive,
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

  // Sätt insättnings-state BARA när närmaste punkt faktiskt byts —
  // nearestInsertionPoint returnerar nytt objekt per anrop, så en naiv
  // setState per mousemove re-renderade hela overlayn i onödan.
  const applyHoveredInsertion = useCallback((next: InsertionPoint) => {
    const prev = lastInsertionRef.current;
    if (
      prev &&
      prev.placement === next.placement &&
      prev.lineYPercent === next.lineYPercent
    ) {
      return;
    }
    lastInsertionRef.current = next;
    setHoveredInsertion(next);
  }, []);

  const handleMouseMove = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      const point = relativePercent(event);
      if (!point) return;

      if (placementPickActive) {
        // Ghost-brickan flyttas via direkta style-skrivningar (ingen
        // re-render per pixel — det var lagg-källan).
        const ghost = ghostRef.current;
        if (ghost) {
          ghost.style.left = `${point.x}%`;
          ghost.style.top = `${point.y}%`;
          ghost.style.visibility = "visible";
        }
        // Efter ett släpp ligger linjen kvar tills operatören bekräftar
        // eller drar/klickar till en ny plats — hovring flyttar den inte.
        if (!pendingDrop) {
          applyHoveredInsertion(nearestInsertionPoint(point.y, sectionZones));
        }
        return;
      }

      if (markMode && markableSections.length > 0) {
        // Medan sektionsmenyn är öppen fryser vi hover-valet — menyn
        // gäller den klickade sektionen tills den stängs.
        if (actionMenu) return;
        // Sektionen vars vertikala band innehåller punkten — smalast
        // band vinner när kanoniska sektioner överlappar (hero-bannern
        // ligger t.ex. inom hero-totalytan).
        let best: MarkableSection | null = null;
        let bestHeight = Infinity;
        for (const section of markableSections) {
          if (point.y < section.top || point.y > section.bottom) continue;
          const height = section.bottom - section.top;
          if (height < bestHeight) {
            best = section;
            bestHeight = height;
          }
        }
        setHoveredMarkable((prev) =>
          prev?.sectionId === best?.sectionId ? prev : best,
        );
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
      pendingDrop,
      inspectMode,
      markMode,
      actionMenu,
      markableSections,
      elementMap,
      sectionZones,
      applyHoveredInsertion,
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
        // Klick = SLÄPP vid närmaste insättningspunkt. Bekräftelsen sker
        // via "Placera här"-knappen (eller flytt genom nytt klick) så
        // operatören aldrig binder sig vid ett feltryck.
        const insertion = nearestInsertionPoint(point.y, sectionZones);
        setPendingDrop(insertion);
        setHoveredInsertion(insertion);
        return;
      }

      if (markMode) {
        // Klick utanför en öppen sektionsmeny stänger den (menyns egna
        // knappar stopPropagation:ar så de aldrig landar här).
        if (actionMenu) {
          setActionMenu(null);
          return;
        }
        if (!hoveredMarkable) return;
        // Klick öppnar sektionsmenyn förankrad vid klickpunkten.
        // routeId mappas via routePlan-kartan (elementkartan bär
        // previewns pathname); själva markeringen sker först när
        // operatören väljer en åtgärd i menyn.
        const routePath =
          elementMap.find((el) => el.routePath)?.routePath ?? "/";
        setActionMenu({
          section: hoveredMarkable,
          routeId: routeIdForPath(routePath, pathToRouteId),
          anchorXPercent: point.x,
          anchorYPercent: point.y,
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
      inspectMode,
      markMode,
      actionMenu,
      hoveredMarkable,
      elementMap,
      pathToRouteId,
      hoveredElement,
      nearestHeadingFor,
    ],
  );

  // Sektionsmenyns åtgärder. "Markera för prompt" hanteras helt lokalt
  // (chip via addMarkedSection, som tidigare direkt-klicket); övriga
  // signaleras till BuilderShell via contextens sectionActionRequest.
  // Alla åtgärder utom ren markering lämnar markläget — operatören
  // landar i dialogen/composern och previewn blir ren igen.
  const handleMenuAction = useCallback(
    (
      action:
        | "mark"
        | "prefill-copy"
        | "asset"
        | "module"
        | "colorize"
        | "move-top"
        | "move-bottom",
    ) => {
      if (!actionMenu) return;
      const { section, routeId } = actionMenu;
      const ref: MarkedSectionRef = {
        routeId,
        sectionId: section.sectionId,
        headingText: section.headingText,
      };
      // Grov position härledd ur sektionens mittpunkt — samma top/bottom-
      // semantik som placeringslägets coarsePositionFor.
      const coarsePosition: "top" | "bottom" =
        (section.top + section.bottom) / 2 <= 50 ? "top" : "bottom";
      setActionMenu(null);
      if (action === "mark") {
        addMarkedSection(ref);
        return;
      }
      if (action === "prefill-copy") {
        addMarkedSection(ref);
        requestSectionAction({ action: "prefill-copy", ref });
      } else if (action === "asset") {
        requestSectionAction({ action: "asset", ref });
      } else if (action === "colorize") {
        requestSectionAction({ action: "colorize", ref });
      } else if (action === "module") {
        requestSectionAction({
          action: "module",
          ref,
          position: coarsePosition,
        });
      } else {
        requestSectionAction({
          action: "move",
          ref,
          position: action === "move-top" ? "top" : "bottom",
          sectionType: MOVABLE_SECTION_TYPES[section.sectionId],
        });
      }
      setMarkModeActive(false);
    },
    [actionMenu, addMarkedSection, requestSectionAction, setMarkModeActive],
  );

  const handleConfirmDrop = useCallback(() => {
    if (!pendingDrop) return;
    completePlacementPick({
      point: pendingDrop,
      coarsePosition: coarsePositionFor(pendingDrop),
      sizePercent: Math.round(clampDropSize(dropSizePercent)),
      pickedAt: Date.now(),
    });
  }, [pendingDrop, dropSizePercent, completePlacementPick]);

  // Kant-/hörn-drag på den dockade mockupen: boxen är centrerad så
  // draget är symmetriskt (faktor 2 på delta). Pointern fångas på
  // handtaget och stopPropagation hindrar overlayns klick-handler från
  // att tolka släppet som "flytta droppen". Hörnen kombinerar x- och
  // y-deltat (utåt = större åt båda hållen) så det känns som fönster-resizen
  // i FloatingChat oavsett vilket hörn operatören tar tag i.
  const handleDropResizePointerDown = useCallback(
    (edge: DropResizeEdge) => (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      event.stopPropagation();
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      dropResizeRef.current = {
        edge,
        pointerX: event.clientX,
        pointerY: event.clientY,
        originPercent: dropSizePercent,
      };
      setIsDropResizing(true);
    },
    [dropSizePercent],
  );

  const handleDropResizePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const start = dropResizeRef.current;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!start || !rect || rect.width <= 0) return;
      const dx = event.clientX - start.pointerX;
      const dy = event.clientY - start.pointerY;
      // Teckenjustera per sida: drag UTÅT från boxen = växa. Rena
      // vertikalhandtag (n/s) skalar också bredden — boxen har EN
      // storleksdimension (% av sidbredden) så alla handtag styr samma
      // värde, precis som operatören förväntar sig av "höj/sänk i hörnet".
      const horizontal = start.edge.includes("e")
        ? dx
        : start.edge.includes("w")
          ? -dx
          : 0;
      const vertical = start.edge.includes("s")
        ? dy
        : start.edge.includes("n")
          ? -dy
          : 0;
      const deltaPercent = ((horizontal + vertical) / rect.width) * 200;
      setDropSizePercent(clampDropSize(start.originPercent + deltaPercent));
    },
    [],
  );

  const handleDropResizePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dropResizeRef.current) return;
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        // Capture kan redan vara släppt — inget att göra.
      }
      dropResizeRef.current = null;
      setIsDropResizing(false);
    },
    [],
  );

  // Direkt-drag av den dockade boxen: ta tag var som helst i mockupen
  // och dra — boxen snäpper till närmaste insättningspunkt medan du
  // drar och ligger kvar där du släpper. Ersätter inte "Flytta"-knappen
  // (som plockar upp brickan till pekar-ghosten) utan är den snabba
  // vägen (operatörskrav 2026-06-10: "lättare kunna dra runt den").
  const handleDropBoxPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      event.stopPropagation();
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      dropDragRef.current = { pointerId: event.pointerId };
      setIsDropDragging(true);
    },
    [],
  );

  const handleDropBoxPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dropDragRef.current) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || rect.height <= 0) return;
      const y =
        (Math.min(Math.max(event.clientY - rect.top, 0), rect.height) /
          rect.height) *
        100;
      const next = nearestInsertionPoint(y, sectionZones);
      // Behåll referensen när närmaste punkt är oförändrad — annars
      // re-renderas overlayn per pixel (samma lagg-klass som ghosten).
      setPendingDrop((prev) =>
        prev &&
        prev.placement === next.placement &&
        prev.lineYPercent === next.lineYPercent
          ? prev
          : next,
      );
    },
    [sectionZones],
  );

  const handleDropBoxPointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dropDragRef.current) return;
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        // Capture kan redan vara släppt — inget att göra.
      }
      dropDragRef.current = null;
      setIsDropDragging(false);
    },
    [],
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
            setHoveredMarkable(null);
            if (ghostRef.current) {
              ghostRef.current.style.visibility = "hidden";
            }
            // Ett släpp ligger kvar även om pekaren lämnar ytan.
            if (!pendingDrop) {
              lastInsertionRef.current = null;
              setHoveredInsertion(null);
            }
          }}
          className={cn(
            "absolute inset-0 z-[7]",
            placementPickActive || markMode
              ? "cursor-crosshair"
              : "cursor-help",
          )}
          role="application"
          aria-label={
            placementPickActive
              ? "Välj plats i förhandsvisningen"
              : markMode
                ? "Markera modul i förhandsvisningen"
                : "Inspektera förhandsvisningen"
          }
        >
          {/* Statusrad + stäng-knapp i en sticky h-0-wrapper: overlayn
              kan vara hela sidan hög (skrollbar preview) och pillen/X:et
              ska följa med skrollporten i stället för att försvinna upp
              med dokumenttoppen. h-0 håller wrappern utanför layouten
              (alla övriga barn är absolute). Statusraden döljs medan ett
              släpp väntar på bekräftelse — knappraden vid linjen är
              självförklarande och pillen skulle täcka knapparna när
              släppet snäpper högt upp (operatörsfynd 2026-06-10). */}
          <div className="sticky top-0 z-[9] h-0">
            {pendingDrop ? null : (
              <div className="pointer-events-none absolute inset-x-0 top-3 flex justify-center px-12">
                <div className="border-border/60 bg-background/90 text-foreground flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[12px] shadow-sm backdrop-blur">
                  {mapState === "loading" ? (
                    <>
                      <Loader2
                        className="h-3.5 w-3.5 animate-spin"
                        aria-hidden
                      />
                      Kartlägger förhandsvisningen…
                    </>
                  ) : mapState === "failed" ? (
                    <span className="text-amber-700 dark:text-amber-300">
                      {mapError}
                    </span>
                  ) : placementPickActive ? (
                    <>
                      {placementDragPayload
                        ? `Dra ${placementDragPayload.label} till önskad plats och klicka`
                        : "Klicka där modulen ska placeras"}
                      <span className="text-muted-foreground">
                        · Esc avbryter
                      </span>
                    </>
                  ) : markMode ? (
                    <>
                      Klicka på en modul för åtgärder ({markedSections.length}
                      /5 markerade)
                      <span className="text-muted-foreground">
                        · Esc avslutar
                      </span>
                    </>
                  ) : (
                    <>
                      Hovra och klicka för att identifiera element
                      <span className="text-muted-foreground">
                        {previewPageHeightPx
                          ? "· skrolla för hela sidan"
                          : "· gäller sajtens topp-vy"}
                      </span>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Stäng-knapp — avbryter platsvalet resp. stänger inspektionen.
                Syns BARA medan ett läge är aktivt (ren canvas annars). */}
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                if (placementPickActive) {
                  cancelPlacementPick();
                } else if (markMode) {
                  setMarkModeActive(false);
                } else {
                  setInspectModeActive(false);
                }
              }}
              className="border-border/60 bg-background/90 text-muted-foreground hover:text-foreground absolute top-3 right-3 inline-flex h-8 w-8 items-center justify-center rounded-full border shadow-sm backdrop-blur transition"
              aria-label={
                placementPickActive
                  ? "Avbryt platsval"
                  : markMode
                    ? "Avsluta modulmarkeringen"
                    : "Stäng inspektionen"
              }
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>

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

          {/* Insättningslinje + ärlig grovpositions-chip. Efter ett släpp
              låses linjen vid släpp-punkten och bekräftelseknapparna tar
              chipens plats. translate-y lyfter knappraden ovanför linjen
              nära botten så den aldrig klipps. */}
          {placementPickActive && (pendingDrop ?? hoveredInsertion)
            ? (() => {
                const line = pendingDrop ?? hoveredInsertion!;
                const yPercent = Math.min(
                  Math.max(line.lineYPercent, 0.5),
                  99.5,
                );
                const flipChip = yPercent > 88;
                return (
                  <div
                    className="pointer-events-none absolute inset-x-0 z-[8]"
                    style={{ top: `${yPercent}%` }}
                  >
                    <div
                      className={cn(
                        "h-[2px] w-full shadow-[0_0_0_1px_rgba(255,255,255,0.6)]",
                        pendingDrop ? "bg-emerald-500" : "bg-foreground",
                      )}
                    />
                    <div
                      className={cn(
                        "absolute left-1/2 -translate-x-1/2",
                        flipChip ? "bottom-1.5" : "top-1.5",
                      )}
                    >
                      {pendingDrop ? (
                        <div className="pointer-events-auto flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleConfirmDrop();
                            }}
                            className="bg-foreground text-background rounded-full px-3 py-1.5 text-[11.5px] font-medium whitespace-nowrap shadow transition hover:opacity-90 active:scale-95"
                          >
                            Placera här
                            <span className="opacity-75">
                              {" "}
                              · {COARSE_LABELS[coarsePositionFor(pendingDrop)]}
                            </span>
                          </button>
                          {/* Flytta: ta upp modulen igen så den följer
                            pekaren (operatörskrav 2026-06-10) — samma
                            effekt som att klicka en ny plats, men som
                            explicit knapp. */}
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              setPendingDrop(null);
                            }}
                            aria-label="Flytta — ta upp och välj ny plats"
                            title="Flytta — ta upp och välj ny plats"
                            className="border-border/60 bg-background/95 text-muted-foreground hover:text-foreground inline-flex h-7 w-7 items-center justify-center rounded-full border shadow backdrop-blur transition active:scale-95"
                          >
                            <Move className="h-3.5 w-3.5" aria-hidden />
                          </button>
                          {/* X: avbryt HELA placeringen (dialogen öppnas
                            igen utan val) — tidigare ångrade X:et bara
                            släppet, vilket var otydligt när flytta-
                            knappen tillkom. */}
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              cancelPlacementPick();
                            }}
                            aria-label="Avbryt placeringen"
                            title="Avbryt placeringen"
                            className="border-border/60 bg-background/95 text-muted-foreground hover:text-foreground inline-flex h-7 w-7 items-center justify-center rounded-full border shadow backdrop-blur transition active:scale-95"
                          >
                            <X className="h-3.5 w-3.5" aria-hidden />
                          </button>
                        </div>
                      ) : (
                        <span className="bg-foreground text-background rounded-full px-2.5 py-1 text-[11px] font-medium whitespace-nowrap shadow">
                          {line.label}
                          <span className="opacity-75">
                            {" "}
                            → {COARSE_LABELS[coarsePositionFor(line)]}
                          </span>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })()
            : null}

          {/* Ghost som följer pekaren i drag-läget (payload från dialogen):
              moduler visas som wireframe-mockup av sektionen (operatörs-
              krav 2026-06-10 — kunden ska se ungefär hur det kommer se
              ut, inte bara en etikett), bilder som thumbnail. Efter
              släpp dockar mockupen i full bredd vid linjen nedan.

              Positionen styrs via DIREKTA style-skrivningar i
              handleMouseMove (ghostRef) — inte state — så brickan följer
              pekaren utan en re-render per pixel. Osynlig tills första
              mousemove ger en position. */}
          {placementPickActive && placementDragPayload && !pendingDrop ? (
            <div
              ref={ghostRef}
              className="pointer-events-none absolute z-[9] -translate-x-1/2 -translate-y-[110%] will-change-[left,top]"
              style={{ visibility: "hidden" }}
            >
              {placementDragPayload.kind === "image" &&
              placementDragPayload.thumbnailUrl ? (
                // Ren förhandsvisnings-ghost — inte sajtinnehåll, så
                // next/image:s optimering är inte relevant här.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={placementDragPayload.thumbnailUrl}
                  alt={placementDragPayload.label}
                  className="border-border/60 max-h-24 w-28 rounded-lg border object-cover opacity-90 shadow-lg"
                />
              ) : (
                <div className="w-56 opacity-95">
                  <ModuleMockup
                    moduleId={placementDragPayload.moduleId ?? ""}
                  />
                  <div className="mt-1 flex justify-center">
                    <span className="bg-foreground text-background rounded-full px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shadow">
                      {placementDragPayload.label}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {/* Dockad mockup vid släpp-punkten: visar hur sektionen/bilden
              ungefär kommer ligga på platsen medan operatören tar
              ställning till "Placera här". Boxen är storleksjusterbar
              via åtta handtag (kanter + hörn, samma layout som
              fönster-resizen i FloatingChat) och kan dras direkt med
              pekaren till en ny insättningspunkt (operatörskrav
              2026-06-10). Vald bredd i % följer med picken så prompten
              kan beskriva storleken. flip:en speglar chip-raden så
              mockupen aldrig klipps vid sidans botten. */}
          {placementPickActive && pendingDrop && placementDragPayload
            ? (() => {
                const yPercent = Math.min(
                  Math.max(pendingDrop.lineYPercent, 0.5),
                  99.5,
                );
                const flip = yPercent > 70;
                return (
                  <div
                    className={cn(
                      "pointer-events-none absolute left-1/2 z-[8] -translate-x-1/2",
                      flip ? "-translate-y-full pb-8" : "pt-8",
                    )}
                    style={{
                      top: `${yPercent}%`,
                      width: `${clampDropSize(dropSizePercent)}%`,
                    }}
                  >
                    <div className="relative">
                      {/* Grab-yta: hela mockupen är dragbar. pointerdown
                        fångar pekaren och boxen snäpper till närmaste
                        insättningspunkt medan den dras; handtagen nedan
                        stopPropagation:ar så resize aldrig startar ett
                        boxdrag. */}
                      <div
                        onPointerDown={handleDropBoxPointerDown}
                        onPointerMove={handleDropBoxPointerMove}
                        onPointerUp={handleDropBoxPointerUp}
                        onPointerCancel={handleDropBoxPointerUp}
                        onClick={(event) => event.stopPropagation()}
                        role="presentation"
                        className={cn(
                          "pointer-events-auto touch-none select-none",
                          isDropDragging ? "cursor-grabbing" : "cursor-grab",
                        )}
                      >
                        {placementDragPayload.kind === "image" &&
                        placementDragPayload.thumbnailUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={placementDragPayload.thumbnailUrl}
                            alt={placementDragPayload.label}
                            className="border-border/60 pointer-events-none w-full rounded-lg border object-cover opacity-95 shadow-xl"
                            draggable={false}
                          />
                        ) : (
                          <ModuleMockup
                            moduleId={placementDragPayload.moduleId ?? ""}
                            className="pointer-events-none w-full opacity-95"
                          />
                        )}
                      </div>

                      {/* Storleks-badge — uppdateras live under resize-draget. */}
                      <span
                        className={cn(
                          "bg-foreground text-background absolute -top-2 right-2 -translate-y-full rounded-full px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shadow transition-opacity",
                          isDropResizing ? "opacity-100" : "opacity-80",
                        )}
                      >
                        ≈ {Math.round(clampDropSize(dropSizePercent))} % av
                        sidbredden
                      </span>

                      {/* Åtta resize-handtag (kanter + hörn) — samma mönster
                        som fönster-resizen i FloatingChat. stopPropagation i
                        alla handlers så draget aldrig tolkas som "flytta
                        droppen" av overlayns klick. */}
                      {DROP_RESIZE_HANDLES.map(([edge, cls]) => (
                        <div
                          key={edge}
                          onPointerDown={handleDropResizePointerDown(edge)}
                          onPointerMove={handleDropResizePointerMove}
                          onPointerUp={handleDropResizePointerUp}
                          onPointerCancel={handleDropResizePointerUp}
                          onClick={(event) => event.stopPropagation()}
                          role="presentation"
                          className={cn(
                            "pointer-events-auto absolute touch-none",
                            cls,
                          )}
                        />
                      ))}

                      {/* Synliga grepp-markörer: streck mitt på kanterna +
                        punkter i hörnen så det syns var boxen kan dras
                        ut. pointer-events-none — träffytorna ovanför äger
                        interaktionen. */}
                      <span className="bg-foreground/70 pointer-events-none absolute top-1/2 -left-1 h-9 w-1 -translate-y-1/2 rounded-full shadow" />
                      <span className="bg-foreground/70 pointer-events-none absolute top-1/2 -right-1 h-9 w-1 -translate-y-1/2 rounded-full shadow" />
                      <span className="bg-foreground/70 pointer-events-none absolute -top-1 left-1/2 h-1 w-9 -translate-x-1/2 rounded-full shadow" />
                      <span className="bg-foreground/70 pointer-events-none absolute -bottom-1 left-1/2 h-1 w-9 -translate-x-1/2 rounded-full shadow" />
                      {(
                        [
                          "-top-1 -left-1",
                          "-top-1 -right-1",
                          "-bottom-1 -left-1",
                          "-bottom-1 -right-1",
                        ] as const
                      ).map((pos) => (
                        <span
                          key={pos}
                          className={cn(
                            "bg-background border-foreground/80 pointer-events-none absolute h-2.5 w-2.5 rounded-full border-2 shadow",
                            pos,
                          )}
                        />
                      ))}
                    </div>
                  </div>
                );
              })()
            : null}

          {/* Markera modul-läget: hover-ram med sektions-id-etikett +
              ihållande emerald-kontur på redan markerade sektioner.
              Kanoniska markeringar visar id:t från data-section-id;
              heuristik-fallbacken (äldre builds) flaggas med "≈" så
              operatören ser att id:t är en gissning. Medan sektions-
              menyn är öppen pinnas ramen vid menyns sektion (hovring
              är frusen) så det alltid syns vilken sektion menyn gäller. */}
          {(() => {
            const framed = markMode
              ? (actionMenu?.section ?? hoveredMarkable)
              : null;
            if (!framed) return null;
            return (
              <div
                className="border-foreground/80 bg-foreground/5 pointer-events-none absolute inset-x-1 z-[8] rounded-md border-2"
                style={{
                  top: `${Math.max(framed.top, 0)}%`,
                  height: `${Math.max(framed.bottom - framed.top, 2)}%`,
                }}
              >
                <span className="bg-foreground text-background absolute top-1.5 left-2 max-w-[280px] truncate rounded px-1.5 py-0.5 font-mono text-[10px]">
                  {framed.canonical ? "" : "≈ "}
                  {framed.sectionId}
                  {framed.headingText
                    ? ` · ${framed.headingText.slice(0, 40)}`
                    : ""}
                </span>
              </div>
            );
          })()}
          {/* Sektionsmenyn: popover förankrad vid klickpunkten. Varje
              åtgärd återanvänder en befintlig pipeline (chip, composer-
              prefill, asset-/modul-dialog, section_add-move) — ingen ny
              backend-kapacitet utlovas. Flytt-alternativen visas BARA
              för sektioner backendens inline-allowlist kan flytta
              (MOVABLE_SECTION_TYPES + home-routen, ADR 0042). */}
          {markMode && actionMenu
            ? (() => {
                const { section, routeId, anchorXPercent, anchorYPercent } =
                  actionMenu;
                const movable =
                  section.canonical &&
                  routeId === MOVABLE_SECTION_ROUTE &&
                  Boolean(MOVABLE_SECTION_TYPES[section.sectionId]);
                const flip = anchorYPercent > 62;
                const left = Math.min(Math.max(anchorXPercent, 6), 70);
                const items: Array<{
                  key:
                    | "mark"
                    | "prefill-copy"
                    | "asset"
                    | "module"
                    | "colorize"
                    | "move-top"
                    | "move-bottom";
                  label: string;
                  Icon: typeof Pin;
                }> = [
                  { key: "mark", label: "Markera för prompt", Icon: Pin },
                  {
                    key: "prefill-copy",
                    label: "Ändra text i sektionen",
                    Icon: MessageSquareText,
                  },
                  { key: "asset", label: "Byt bild här", Icon: ImagePlus },
                  {
                    key: "colorize",
                    label: "Färglägg sektionen",
                    Icon: Palette,
                  },
                  {
                    key: "module",
                    label: "Lägg till modul här",
                    Icon: Blocks,
                  },
                  ...(movable
                    ? ([
                        {
                          key: "move-top",
                          label: "Flytta överst",
                          Icon: ArrowUpToLine,
                        },
                        {
                          key: "move-bottom",
                          label: "Flytta nederst",
                          Icon: ArrowDownToLine,
                        },
                      ] as const)
                    : []),
                ];
                return (
                  <div
                    className={cn(
                      "border-border/70 bg-background/95 absolute z-[10] w-[240px] rounded-xl border p-1.5 shadow-lg backdrop-blur",
                      flip ? "-translate-y-full" : "",
                    )}
                    style={{
                      left: `${left}%`,
                      top: `${Math.min(Math.max(anchorYPercent, 2), 96)}%`,
                    }}
                    onClick={(event) => event.stopPropagation()}
                    role="menu"
                    aria-label={`Åtgärder för sektionen ${section.sectionId}`}
                  >
                    <div className="text-muted-foreground flex items-center justify-between gap-2 px-2 py-1">
                      <span className="truncate font-mono text-[10px]">
                        {section.canonical ? "" : "≈ "}
                        {section.sectionId}
                        {section.headingText
                          ? ` · ${section.headingText.slice(0, 28)}`
                          : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => setActionMenu(null)}
                        aria-label="Stäng sektionsmenyn"
                        className="hover:text-foreground rounded p-0.5 transition"
                      >
                        <X className="h-3 w-3" aria-hidden />
                      </button>
                    </div>
                    {items.map(({ key, label, Icon }) => (
                      <button
                        key={key}
                        type="button"
                        role="menuitem"
                        onClick={() => handleMenuAction(key)}
                        className="text-foreground hover:bg-muted/70 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] transition"
                      >
                        <Icon
                          className="text-muted-foreground h-3.5 w-3.5 shrink-0"
                          aria-hidden
                        />
                        {label}
                      </button>
                    ))}
                  </div>
                );
              })()
            : null}
          {markMode
            ? markableSections
                .filter((section) =>
                  markedSections.some(
                    (marked) => marked.sectionId === section.sectionId,
                  ),
                )
                .map((section) => (
                  <div
                    key={`marked-${section.sectionId}`}
                    className="pointer-events-none absolute inset-x-1 z-[7] rounded-md border-2 border-emerald-500/80 bg-emerald-500/5"
                    style={{
                      top: `${Math.max(section.top, 0)}%`,
                      height: `${Math.max(section.bottom - section.top, 2)}%`,
                    }}
                  >
                    <span className="absolute top-1.5 right-2 rounded bg-emerald-600 px-1.5 py-0.5 font-mono text-[10px] text-white">
                      Markerad
                    </span>
                  </div>
                ))
            : null}

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

          {/* Info-kort efter klick i inspektionsläget. Sticky h-0-wrapper
              (samma trick som statusraden) så kortet följer skrollporten
              i den fullhöga overlayn — absolute bottom-4 hade hamnat vid
              dokumentets botten, utanför synfältet. */}
          {inspectMode && !placementPickActive && inspected ? (
            <div className="sticky top-0 z-[9] h-0">
              <div
                className="border-border/70 bg-background/95 absolute top-14 left-4 w-[min(340px,calc(100%-2rem))] rounded-xl border p-3.5 shadow-lg backdrop-blur"
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
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
