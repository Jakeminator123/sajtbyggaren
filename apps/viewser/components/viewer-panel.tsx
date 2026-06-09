"use client";

import { Check, Loader2 } from "lucide-react";
import {
  type ComponentType,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { resolvePreviewRuntimeDescriptor } from "@preview-runtime";

import { Button } from "@/components/ui/button";

/**
 * Props-shape för den lazy-laddade StackBlitz-preview-komponenten. Inlinad
 * HÄR (i st.f. ``import type`` från modulen) som extra försäkran om att inget
 * — varken runtime- eller typ-led — binder ihop ViewerPanel:s eager-graf med
 * ``stackblitz-preview``-modulen.
 */
type StackblitzPreviewComponentProps = {
  runId: string;
  isBuilding?: boolean;
};

/**
 * StackBlitz-preview (LEGACY/PAUSAD WebContainer-väg, ADR 0033) laddas via en
 * RUNTIME ``import()`` — MEDVETET INTE via top-level ``next/dynamic``.
 *
 * Varför inte ``dynamic()`` på modulnivå? Next/Turbopack STATISKT-analyserar
 * en modulnivå-``dynamic(() => import("x"))`` och pre-scriptar ``x``:s
 * chunk-graf (inkl. den nästlade ``@stackblitz/sdk``-chunken) som
 * ``<script async>`` i den serverade ``studio.html``. Resultatet var att SDK-
 * vendor-chunken eager-laddades vid varje ``vercel-sandbox``/``local-next``-
 * studioladdning trots att SDK:n aldrig kördes (verifierat i serverad HTML).
 *
 * Genom att i stället anropa ``import("@/components/stackblitz-preview")``
 * inuti en effekt som BARA körs när StackBlitz-vägen är aktiv
 * (``CAN_FALL_BACK_TO_STACKBLITZ`` + ``useStackblitz``) ligger referensen inte
 * i den eager-analyserade modulgrafen — chunken hämtas först när en
 * ``stackblitz``/``auto``-preview faktiskt behövs.
 */
const STACKBLITZ_PREVIEW_IMPORT = () =>
  import("@/components/stackblitz-preview");
import type { PromptStage } from "@/components/prompt-builder";
import {
  DEVICE_PRESET_WIDTHS,
  useDevicePreset,
} from "@/components/device-preset-context";
import { cn } from "@/lib/utils";

// Device-preset state + DEVICE_OPTIONS-listan lever numera i
// `components/device-preset-context.tsx` så toggle-UI:t kan flyttas
// från top-right av canvasen till FloatingChat:s footer utan
// prop-drilling. ViewerPanel läser bara aktuell preset via
// `useDevicePreset()`-hooken och stänger inte längre av setter:n.

type ViewerPanelProps = {
  runId: string | null;
  /**
   * Aktivt siteId från page.tsx. Behövs för lokal preview-server-
   * pathen ``POST /api/preview/<siteId>`` — det är siteId (inte
   * runId) som matchar mappen ``.generated/<siteId>/`` där den
   * byggda Next.js-appen ligger redo att ``next start``.
   */
  siteId?: string | null;
  /**
   * Sätts till true av page.tsx under hela request-cykeln mot
   * /api/prompt. Triggar BuildProgressCard i mitten av canvasen i
   * stället för hero-texten så operatören ser en dedikerad bygg-vy.
   */
  isBuilding?: boolean;
  /**
   * Aktuell PromptStage från PromptBuilder. Styr vilken rad som är
   * aktiv i BuildProgressCard-stegmarkören.
   */
  buildStage?: PromptStage;
};

// prefers-reduced-motion-prenumeration för studio-hero-videorna. Speglar
// marketing-sajtens `hero-video.tsx`: via useSyncExternalStore (Reacts
// kanoniska väg att läsa en extern store) i st.f. useEffect+setState — ger
// en deterministisk SSR-snapshot (rörelse OK) som matchar första klient-
// render och undviker react-hooks/set-state-in-effect.
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia(REDUCED_MOTION_QUERY);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getReducedMotionSnapshot() {
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

function getReducedMotionServerSnapshot() {
  return false;
}

/**
 * Strukturerad info-shape som banner-renderaren kan visa istället för
 * den tidigare hårdkodade "Mock-runs skriver inte..."-strängen. Tillåter
 * att olika misslyckanden (sajten inte byggd, port-pool full, mock-run
 * utan files, etc.) får specifik copy med titel, beskrivning och en
 * actionable hint istället för en gemensam grå text.
 */
type UnavailableInfo = {
  title?: string;
  message: string;
  hint?: string;
};

/**
 * Felshape som ``/api/preview/<siteId>`` returnerar (4xx/5xx). Synkad
 * mot ``apps/viewser/app/api/preview/[siteId]/route.ts:PreviewErrorBody``.
 * Vi kopierar typen istället för att importera den eftersom denna
 * komponent kör i klienten och importera från en server-route-fil
 * skulle dra in onödiga server-bara beroenden.
 */
type PreviewApiError = {
  error: string;
  code?:
    | "validation_error"
    | "not_built"
    | "missing_artifacts"
    | "port_pool_full"
    | "spawn_failed"
    | "not_running"
    // Vercel Sandbox-adaptern (ADR 0033) degraderar ärligt:
    | "vercel_auth"
    | "sandbox_failed"
    | "unknown";
  hint?: string;
};

/**
 * Svar-shape från ``POST /api/preview/<siteId>`` vid lyckad start. local-next
 * returnerar full info (port/uptimeMs), vercel-sandbox bara
 * ``{ url, kind, sessionId }``. Båda har ``url`` — det är allt ViewerPanel
 * behöver för att iframe:a previewn.
 */
type PreviewStartResponse = {
  url: string;
  siteId?: string;
  status?: "starting" | "ready";
  port?: number;
  uptimeMs?: number;
  kind?: string;
  sessionId?: string;
};

function unavailableForPreviewError(
  payload: PreviewApiError | null,
): UnavailableInfo {
  const code = payload?.code ?? "unknown";
  const errMsg = payload?.error;
  const errHint = payload?.hint;
  if (code === "not_built" || code === "missing_artifacts") {
    return {
      title: "Sajten är inte byggd än",
      message:
        errMsg ??
        "Lokal preview-server kunde inte starta — den genererade sajten finns inte på disk.",
      hint:
        errHint ??
        "Kör python scripts/build_site.py för att bygga sajten först.",
    };
  }
  if (code === "port_pool_full") {
    return {
      title: "Inga lediga preview-portar",
      message: errMsg ?? "Port-poolen 4100-4199 är full.",
      hint:
        errHint ??
        "Stäng några äldre preview-servrar via DELETE /api/preview/<siteId>.",
    };
  }
  if (code === "spawn_failed") {
    return {
      title: "Lokal preview-server kraschade",
      message: errMsg ?? "next start startade inte korrekt.",
      hint:
        errHint ??
        "Kontrollera viewser-loggen för stderr-tail från next start.",
    };
  }
  // Vercel Sandbox-adaptern (ADR 0033): saknad/utgången OIDC-token. Visa ett
  // pedagogiskt inloggningsfel i stället för en tyst fallback.
  if (code === "vercel_auth") {
    return {
      title: "Vercel-inloggning saknas",
      message:
        errMsg ??
        "Vercel Sandbox kräver en giltig OIDC-token som saknas eller har gått ut.",
      hint:
        errHint ??
        "Kör `vercel env pull apps/viewser/.env.vercel.local` för en färsk token (gäller ~12 h) och starta om npm run dev.",
    };
  }
  // Sandboxen byggde/startade inte (npm install / next build / timeout).
  if (code === "sandbox_failed") {
    return {
      title: "Molnförhandsvisningen kunde inte startas",
      message: errMsg ?? "Vercel Sandbox byggde inte den genererade sajten.",
      hint:
        errHint ??
        "Försök igen, eller kontrollera viewser-loggen för install/build-loggar.",
    };
  }
  return {
    title: "Lokal preview-server kunde inte starta",
    message: errMsg ?? "Okänt fel från /api/preview/<siteId>.",
    hint: errHint,
  };
}

/**
 * Operatörens uttryckta preview-runtime-läge, läst från den
 * ``NEXT_PUBLIC_VIEWSER_PREVIEW_MODE``-spegel som ``next.config.ts``
 * exponerar (raw ``VIEWSER_PREVIEW_MODE``, inte production-gate-utfallet).
 * Värdet bakas in i bundlen vid build-time så det är konstant per session.
 *
 * Bite C (2026-06-08): tidigare lästes env-värdet rått här och IS_*-
 * booleanerna härleddes via ``=== "..."``. Nu drivs allt genom den
 * client-säkra ``resolvePreviewRuntimeDescriptor`` (@preview-runtime,
 * commit ee68add) så klienten och host-transporten (``scripts/dev.mjs``)
 * delar EN mode-normaliserare i stället för två som kan driva isär.
 *
 * VIKTIGT — ``auto`` ≠ ``local-next``: descriptorns lossy ``kind`` kollapsar
 * ``local-next``/``auto``/``local`` till ``"local"``, men COEP/fallback-
 * beslutet skiljer dem åt. Därför läses ``IS_LOCAL_NEXT_MODE`` ur
 * ``rawMode`` (som bevarar distinktionen), aldrig ur ``kind`` — annars
 * skulle ``auto`` felaktigt flippas till local-next och tappa sin
 * StackBlitz-fallback (descriptor.prefersCoep / canFallbackToStackblitz
 * är ``true`` för ``auto``/``stackblitz``, ``false`` för local-next).
 *
 * ``?? "local-next"`` behålls medvetet (descriptorns egna tomma default är
 * ``"local"``) så en osatt env beter sig EXAKT som förr: local-next, dvs
 * COEP av och ingen StackBlitz-fallback.
 *
 * Avgör om StackBlitz-fallback överhuvudtaget är ett giltigt nästa steg när
 * LocalRuntime failar:
 *
 *   - ``local-next``  → COEP är OFF på host, så StackBlitz-embeds skulle
 *                       blockas av Chrome med "Specify a Cross-Origin
 *                       Embedder Policy". Bättre att visa pedagogiskt
 *                       fel direkt än att tyst fall till en path som
 *                       inte kan fungera.
 *   - ``stackblitz``  → COEP är ON, StackBlitz-fallback är legit nästa
 *                       steg om LocalRuntime är ouppnåelig.
 *   - ``auto``        → Som ``stackblitz`` på header-nivå idag.
 */
const PREVIEW_RUNTIME = resolvePreviewRuntimeDescriptor(
  process.env.NEXT_PUBLIC_VIEWSER_PREVIEW_MODE ?? "local-next",
);
// ``rawMode`` (inte ``kind``): ``kind`` kollapsar local-next/auto/local till
// ``"local"`` och skulle därför göra ``auto`` till local-next. ``rawMode``
// bevarar den exakta token som COEP/fallback-beslutet hänger på.
const IS_LOCAL_NEXT_MODE = PREVIEW_RUNTIME.rawMode === "local-next";
// Reviewer-fynd (post-PR #101): tidigare provades alltid
// ``POST /api/preview/<siteId>`` först, även i ``stackblitz``-mode.
// Det betydde att configen namn (``stackblitz``) inte var sann end-to-
// end — om sajten råkade ha en lokal ``.next/`` hamnade operatören på
// lokal preview ändå. ``IS_STACKBLITZ_MODE`` låter Steg 1 (lokal
// preview-server) hoppas helt i strikt stackblitz-läge, så
// VIEWSER_PREVIEW_MODE=stackblitz blir auktoritativ:
//   - ``local-next``  → prova lokal, pedagogiskt fel vid miss
//   - ``stackblitz``  → hoppa Steg 1, gå direkt till StackBlitz Steg 2
//   - ``auto``        → prova lokal, fall till StackBlitz vid miss
//                       (oförändrat — det är vad ``auto`` betyder)
// ``kind === "stackblitz"`` är 1:1 med ``rawMode`` här (descriptorn mappar
// ``stackblitz`` rakt igenom); ``auto`` ger ``kind === "local"`` så grinden
// nedan släpper fortfarande igenom auto till Steg 1.
const IS_STACKBLITZ_MODE = PREVIEW_RUNTIME.kind === "stackblitz";
// ``vercel-sandbox`` (ADR 0033, primärt förstahandsval): preview serveras från
// en isolerad Vercel Sandbox och POST /api/preview/<siteId> returnerar en publik
// ``…vercel.run``-https-URL. ViewerPanel behandlar den EXAKT som local-next-
// vägen — iframe:ar den returnerade URL:en — och visar pedagogiskt fel (t.ex.
// saknad token) i stället för att tyst falla till StackBlitz. Skillnaden mot
// local-next är bara cold-starten (~28 s medan sandboxen kör npm install +
// next build innan URL:en svarar), som loading-UI:t nedan tål.
const IS_VERCEL_SANDBOX_MODE = PREVIEW_RUNTIME.kind === "vercel-sandbox";
// AUKTORITATIV gate för att överhuvudtaget nå den LEGACY/PAUSADE StackBlitz-
// vägen (ADR 0033). Descriptorn sätter ``canFallbackToStackblitz === true``
// ENBART för ``stackblitz`` + ``auto`` (de enda lägena som kör COEP-on, där en
// WebContainer-embed faktiskt kan boota). För alla andra lägen —
// ``local-next``, ``vercel-sandbox`` OCH de COEP-av-aliasen ``local``/``fly``
// plus tomt/okänt env-värde — är en StackBlitz-embed ogiltig (browsern
// blockar den utan COEP), så ``ViewerPanel`` får ALDRIG falla till
// StackBlitz där. De tre per-gren-checkarna nedan
// (``IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE``) returnerar redan med
// pedagogiskt fel för de två primära lägena; denna konstant är den hårda
// backstop som dessutom täcker ``local``/``fly``/tomt/okänt (annars läckte de
// igenom till StackBlitz — den verkliga, om än latenta, gating-buggen).
const CAN_FALL_BACK_TO_STACKBLITZ = PREVIEW_RUNTIME.canFallbackToStackblitz;

// Mode-aware UI-copy för BuildProgressCard-preview-steget. Tidigare
// hårdkodat "Förbereder StackBlitz-iframen." även i local-next-mode
// där flödet faktiskt startar en lokal ``next start``-server. Liten
// drift men ger fel mental modell. Reviewer-fynd post-PR #101.
//
// Texten är kundvänlig — inga tekniska termer (preview-server,
// next start, StackBlitz, iframe) eftersom slutkunden inte ska
// behöva förstå pipelinen för att vänta i lugn och ro.
const PREVIEW_PREP_HINT = IS_LOCAL_NEXT_MODE
  ? "Snart kan du klicka runt på er sajt."
  : IS_VERCEL_SANDBOX_MODE
    ? "Vi startar en säker molnförhandsvisning – det tar en stund första gången."
    : "Laddar förhandsvisningen i webbläsaren.";

export function ViewerPanel({
  runId,
  siteId,
  isBuilding = false,
  buildStage = "idle",
}: ViewerPanelProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  // Tidigare en ren boolean. Utvidgad till strukturerad info-shape så
  // banner-rendraren kan visa specifik copy per failure-läge (sajten
  // inte byggd, port-pool full, mock-run utan files, ...) istället för
  // en gemensam "Mock-runs..."-text. ``null`` = inget fel; ``object`` =
  // visa banner med dessa fält.
  const [unavailable, setUnavailable] = useState<UnavailableInfo | null>(null);
  const [loading, setLoading] = useState(false);
  // Lokal preview-server-URL. När den är satt renderar vi en simpel
  // iframe direkt mot ``http://localhost:<port>`` istället för att gå
  // genom StackBlitz. Snabbare (~1s vs ~60s), funkar i Safari/Firefox,
  // och same-machine-iframen tar emot postMessage från Site Inspector
  // för Sprint 5:s live token-editor.
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  // Iframe-dokumentets laddningsstatus. När ``localPreviewUrl`` precis
  // satts (första preview ELLER byte av vald run) är iframen vit tills
  // Next.js hunnit hydrera. ``iframeLoaded`` flippas av iframens onLoad
  // och styr en subtil skelett-overlay (se render) så operatören ser en
  // laddningsindikator i stället för en blank vit canvas. Återställs till
  // false varje gång URL:en ändras.
  const [iframeLoaded, setIframeLoaded] = useState(false);
  // Sätts true bara när Steg 1 (lokal/sandbox) inte gäller/misslyckas OCH
  // läget tillåter en StackBlitz-fallback (``CAN_FALL_BACK_TO_STACKBLITZ``,
  // dvs ``stackblitz``/``auto``). Styr renderingen av den lazy-laddade
  // ``<StackblitzPreview/>`` — så hela ``@stackblitz/sdk``-modulgrafen
  // laddas FÖRST här (via en runtime ``import()``, se loader-effekten
  // nedan), aldrig vid en vanlig
  // ``vercel-sandbox``/``local-next``-studioladdning.
  const [useStackblitz, setUseStackblitz] = useState(false);
  // Den lazy-laddade StackBlitz-preview-komponenten. Hålls i state och laddas
  // via en RUNTIME ``import()`` (se loader-effekten nedan) först när
  // ``useStackblitz`` blir true — aldrig via top-level ``dynamic()`` (som
  // skulle pre-scripta SDK-chunken i studio.html).
  const [StackblitzPreviewComp, setStackblitzPreviewComp] =
    useState<ComponentType<StackblitzPreviewComponentProps> | null>(null);
  // Bumpas av "Försök igen"-knappen i otillgänglig-bannern. Ingår i preview-
  // effektens deps så ett klick kör om hela hämtningen (samma reset-väg som
  // ett runId-byte) utan att operatören måste välja om runen.
  const [retryNonce, setRetryNonce] = useState(0);

  // Device-preset hämtas från DevicePresetProvider (page.tsx → provider →
  // ViewerPanel + FloatingChat). Tidigare hade ViewerPanel lokal state
  // med sessionStorage-persistens, men efter att toggle-UI:t flyttats
  // till FloatingChat:s footer ligger state lifted i contexten istället.
  // Hydration-mönstret (initial = "full", post-mount-läs från storage)
  // har följt med dit oförändrat så vi slipper SSR-mismatch.
  const { devicePreset } = useDevicePreset();

  // Studio-hero-videorna är dekorativa (aria-hidden). Under reduced-motion
  // pausar vi dem på första framen (ingen autoplay/loop) i st.f. att rulla
  // en oönskad bakgrundsanimation — samma a11y-kontrakt som marketing-hero:n.
  const reducedMotion = useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    getReducedMotionServerSnapshot,
  );

  /**
   * Preview-wrapper-stil. När devicePreset != "full" får wrappern en
   * max-width-constraint som centreras med mx-auto. Preview-innehållet
   * (iframe eller StackblitzPreview) fyller wrappern (h-full w-full) så det
   * krymper när wrappern krymper. useMemo så stilobjektet inte recreate:as
   * per render — undviker onödiga reflows i preview-iframen.
   */
  const previewWrapperStyle = useMemo(() => {
    const width = DEVICE_PRESET_WIDTHS[devicePreset];
    if (width === null) return undefined;
    return { maxWidth: `${width}px` };
  }, [devicePreset]);

  useEffect(() => {
    // Preview-resolvern (Steg 1: lokal/sandbox; sedan ev. handoff till den
    // lazy StackBlitz-vägen). Återställs helt vid varje runId/siteId-byte
    // och vid "Försök igen" (retryNonce).
    let cancelled = false;

    void (async () => {
      // Skjut upp de initiala state-skrivningarna ett microtask så React
      // 19:s ``react-hooks/set-state-in-effect`` inte flaggar synkrona
      // setState i effect-kroppen. Samma mönster som versions-tab /
      // use-run-artefacts använder för sina reset-effekter. ``cancelled``-
      // guarden efteråt skyddar mot ett runId/siteId-byte under microtasken.
      await Promise.resolve();
      if (cancelled) return;

      if (!runId) {
        setUnavailable(null);
        setLoading(false);
        setUseStackblitz(false);
        return;
      }

      setUnavailable(null);
      setUseStackblitz(false);
      setLocalPreviewUrl(null);
      setIframeLoaded(false);
      setLoading(true);

      // Steg 1: försök starta en lokal preview-server. Mycket snabbare
      // än StackBlitz (~1s vs ~60s första gången), funkar i alla
      // browsers, och same-machine-iframen tar emot postMessage från
      // Site Inspector för Sprint 5:s live token-editor.
      //
      // Samma POST-väg används av vercel-sandbox: svaret är då en publik
      // ``…vercel.run``-URL (i stället för ``http://localhost:<port>``) men
      // hanteras identiskt — iframe:a ``info.url``.
      //
      // Vad vi gör vid misslyckande beror på ``VIEWSER_PREVIEW_MODE``:
      //
      //   - ``local-next``    → visa pedagogiskt fel direkt. Försök INTE
      //                         StackBlitz; host saknar COEP-headers och
      //                         Chrome skulle bara svara med "Specify a
      //                         Cross-Origin Embedder Policy", vilket
      //                         maskerar det riktiga problemet (sajten
      //                         inte byggd, port-pool full, etc.). Det
      //                         här är fixet för "CORS-tjafset" som
      //                         drabbar nya prompts där siteId ännu inte
      //                         hunnits byggas.
      //   - ``vercel-sandbox``→ samma ärliga fel-väg som local-next (visa
      //                         pedagogiskt fel, t.ex. ``vercel_auth`` vid
      //                         saknad token). Fall ALDRIG till StackBlitz —
      //                         host saknar COEP och sandboxen är den valda
      //                         primära runtimen (ADR 0033).
      //   - ``stackblitz``    → hoppa Steg 1 HELT (configens namn är
      //                         auktoritativ — vi vill se WebContainer-
      //                         flödet, inte lokal preview). Fall genom
      //                         till Steg 2 nedan med tom files-fetch.
      //   - ``auto``          → prova lokal, fall till StackBlitz vid
      //                         miss (befintlig auto-semantik). COEP är
      //                         då ON och embedded WebContainer kan
      //                         rendera.
      //
      // ``IS_STACKBLITZ_MODE``-grinden ovanför Steg 1 stänger reviewerns
      // ärlighetsglapp där configens namn antydde "use StackBlitz" men
      // flödet i praktiken var "try local first, fall back to
      // StackBlitz" — oavsett mode.
      if (!IS_STACKBLITZ_MODE && siteId) {
        try {
          const previewResponse = await fetch(`/api/preview/${siteId}`, {
            method: "POST",
          });
          if (previewResponse.ok) {
            // local-next → http://localhost:<port>; vercel-sandbox →
            // publik …vercel.run-https-URL. Båda iframe:as identiskt.
            const info = (await previewResponse.json()) as PreviewStartResponse;
            if (cancelled) return;
            setIframeLoaded(false);
            setLocalPreviewUrl(info.url);
            setLoading(false);
            return;
          }
          if (IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE) {
            if (cancelled) return;
            const errPayload = (await previewResponse
              .json()
              .catch(() => null)) as PreviewApiError | null;
            // Re-check cancelled AFTER the JSON-parse await: a runId
            // switch during the parse must not write stale state.
            // Mirror of the success-branch guard above and the 404
            // guard on the StackBlitz fallback below (Codex P2, PR #97).
            if (cancelled) return;
            setUnavailable(unavailableForPreviewError(errPayload));
            setLoading(false);
            return;
          }
          // I stackblitz/auto-mode: fall genom till StackBlitz nedan.
          // 404/500 från preview-routen är då förväntat eftersom
          // build_site.py kan ha skippats medvetet och vi har files
          // tillgängliga via /api/runs/<runId>/files istället.
        } catch {
          if (IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE) {
            if (cancelled) return;
            setUnavailable({
              title: "Preview-servern kunde inte nås",
              message: "Nätverksfel mot /api/preview/<siteId>.",
              hint: "Är viewser-dev-servern igång? Starta om med npm run dev.",
            });
            setLoading(false);
            return;
          }
          // Stackblitz-mode: fortsätt med StackBlitz-fallback.
        }
      } else if (IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE) {
        // siteId saknas men runId finns — t.ex. en mock-run från
        // dev_generate.py. Varken local-next eller vercel-sandbox kan bygga
        // preview utan siteId (sandboxen behöver en byggd .generated/<siteId>/-
        // mapp att kopiera), så visa pedagogiskt fel istället för att tyst
        // försöka StackBlitz (vilket ändå skulle blockas av Chrome).
        if (cancelled) return;
        setUnavailable({
          title: "Saknar siteId för preview",
          message:
            "Den valda runen har inget siteId i build-result.json. Preview kräver en byggd .generated/<siteId>/-mapp.",
          hint: "Kör en ny prompt för att skapa en builder-run, eller byt till VIEWSER_PREVIEW_MODE=stackblitz för fil-baserad preview.",
        });
        setLoading(false);
        return;
      }

      // Hård gate FÖRE den legacy/pausade StackBlitz-vägen (ADR 0033).
      // Detta är ENDA punkten där ViewerPanel kan lämna över till
      // ``<StackblitzPreview/>`` (och därmed ``@stackblitz/sdk``). Den får
      // bara nås när descriptorn säger att en StackBlitz-embed är en giltig
      // fallback — ``CAN_FALL_BACK_TO_STACKBLITZ === true``, vilket ENBART
      // gäller ``stackblitz`` + ``auto`` (COEP on). De två primära lägena
      // (``local-next``/``vercel-sandbox``) har redan returnerat ovan med
      // pedagogiskt fel, så för dem är denna gate defense-in-depth. Dess
      // verkliga uppgift är att göra StackBlitz OMÖJLIG att nå för alla
      // andra lägen (``local``/``fly``/tomt/okänt env-värde) — den latenta
      // gating-bugg där de annars föll igenom till en embed som browsern
      // ändå skulle blocka utan COEP.
      if (!CAN_FALL_BACK_TO_STACKBLITZ) {
        if (cancelled) return;
        setUnavailable({
          title: "Förhandsvisningen kunde inte startas",
          message:
            "Den här förhandsvisningen kunde inte laddas och det aktuella preview-läget tillåter ingen StackBlitz-reserv.",
          hint: "Kör en ny prompt för att bygga sajten, eller kontrollera VIEWSER_PREVIEW_MODE.",
        });
        setLoading(false);
        return;
      }

      // Steg 2: lämna över till den LEGACY/PAUSADE StackBlitz-vägen. Hela
      // ``@stackblitz/sdk``-grafen lever i ``<StackblitzPreview/>`` som
      // laddas via en runtime ``import()`` (loader-effekten nedan) — så
      // filhämtningen (``/api/runs/<runId>/
      // files``), browser-kind-checken och embedden sker FÖRST när den
      // komponenten faktiskt renderas (dvs här, i stackblitz/auto-läge),
      // aldrig vid en normal vercel-sandbox/local-next-studioladdning.
      if (cancelled) return;
      setUseStackblitz(true);
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
    // retryNonce: bumpas av "Försök igen" i otillgänglig-bannern → kör om
    // effekten med full state-reset (samma väg som ett runId-byte).
  }, [runId, siteId, retryNonce]);

  // Lazy-loader för StackBlitz-preview-komponenten. Körs BARA när
  // ``useStackblitz`` blivit true (dvs i ``stackblitz``/``auto`` efter att
  // Steg 1 inte gällt/misslyckats). ``import()`` ligger här — i en effekt som
  // gate:as på runtime — i st.f. i en top-level ``dynamic()``, så Turbopack
  // INTE pre-scriptar ``@stackblitz/sdk``-chunken i studio.html vid en vanlig
  // vercel-sandbox/local-next-load. ``setState`` sker i ``.then``-callbacken
  // (asynkront), inte synkront i effekt-kroppen → inget
  // react-hooks/set-state-in-effect.
  useEffect(() => {
    if (!useStackblitz || StackblitzPreviewComp) return;
    let cancelled = false;
    void STACKBLITZ_PREVIEW_IMPORT()
      .then((mod) => {
        if (!cancelled) {
          setStackblitzPreviewComp(() => mod.StackblitzPreview);
        }
      })
      .catch(() => {
        // Chunk-laddningen kan faila (nät-glapp, utgången deploy, blockad
        // vendor-chunk). Utan denna catch blev ``useStackblitz`` kvar true
        // medan ``StackblitzPreviewComp`` förblev null → tyst blank canvas.
        // Degradera ärligt via samma unavailable-banner som övriga
        // preview-fel (med "Försök igen"-knapp) i stället för tyst blankt.
        if (cancelled) return;
        setUseStackblitz(false);
        setUnavailable({
          title: "Förhandsvisningen kunde inte laddas",
          message:
            "Komponenten för förhandsvisningen kunde inte hämtas (nätverksfel eller utgången version).",
          hint: "Kontrollera nätverket och tryck Försök igen, eller ladda om sidan.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [useStackblitz, StackblitzPreviewComp]);

  const showEmpty = !runId;
  const showUnavailable = unavailable && !!runId;
  // Den legacy/pausade StackBlitz-vägen är aktiv: render:as via den lazy-
  // laddade ``<StackblitzPreview/>``. Bara möjlig i stackblitz/auto
  // (``CAN_FALL_BACK_TO_STACKBLITZ``); effekten sätter ``useStackblitz``
  // först efter att Steg 1 inte gällt/misslyckats.
  const showStackblitz =
    useStackblitz &&
    CAN_FALL_BACK_TO_STACKBLITZ &&
    !!runId &&
    !unavailable &&
    !showEmpty;
  // "Finalize"-fasen efter build_site.py är klart: backend har skrivit
  // build-result.json (status=ok), frontend har satt stage="success" och
  // building=false, men ViewerPanel väntar fortfarande på att Steg 1
  // (lokal/sandbox) ska svara. Utan denna flagga försvann
  // BuildProgressCard direkt vid success — operatören tappade den
  // visuella kontinuiteten från "Bygger sajt" → "Startar preview".
  const isFinalizing =
    buildStage === "success" && loading && !!runId && !unavailable;
  // Visa hero-videon så länge ingen riktig preview har tagit över canvasen.
  // Det täcker: ingen run vald (empty), unavailable-banner, pågående fetch
  // (loading) och pågående bygge. `loading` räcker — `isFinalizing` är en
  // delmängd av `loading`. När StackblitzPreview är aktiv är `loading`
  // false så hero släcks och den lazy-komponenten äger ytan.
  const showHero =
    showEmpty || showUnavailable || loading || isBuilding;
  // BuildProgressCard tar över mittenytan när vi aktivt bygger ELLER
  // när bygget precis blivit klart men preview fortfarande bootas.
  // Hero-texten ska INTE visas i någondera fas — det skulle vara dubbel
  // information med två konkurrerande UI:n.
  const showHeroText =
    (showEmpty || showUnavailable) && !isBuilding && !isFinalizing;
  const showBuildCard = isBuilding || isFinalizing;

  // showDeviceToggle-flaggan tas bort härifrån: toggle-UI:t lever
  // numera i FloatingChat:s footer (DevicePresetToggleBar) och visas
  // när en sajt-preview är aktiv via samma synlighets-villkor där.

  return (
    <div
      className={cn(
        // Mobil: flex-col så SM-mobile.mp4 (top-banner) + hero-text staplas
        //   vertikalt som ett naturligt flöde. Bakgrundsfärgen byts till
        //   videons egen off-white (#f0f2ed) när hero visas så filmens
        //   bakgrund flyter sömlöst in i canvasen utan synlig edge.
        // Desktop (md+): flex-row + bg-background — videon ligger absolute
        //   och hero-texten ovanpå som overlay (oförändrad layout).
        //
        // overflow på mobil: när hero visas behöver vi `overflow-y-auto`
        // så hero-text kan scrolla om viewport-höjden är liten (iPhone SE
        // 667px med video ~300px + text ~200px + composer ~150px lämnar
        // ingen marginal). Desktop håller `overflow-hidden` eftersom
        // hero där är absolute-positioned overlay (ingen scroll-behov).
        "viewer-canvas relative flex h-full w-full flex-col md:flex-row md:overflow-hidden",
        showHero
          ? "md:bg-background overflow-y-auto bg-[#f0f2ed]"
          : "bg-background overflow-hidden",
      )}
    >
      {/* Hero-bakgrundsvideo. Två separata videos: SM_hero.mp4
          (16:9 desktop-version med 3D-objekt skiftat höger via 78%
          object-position) och SM-mobile.mp4 (960x960 fyrkantig
          mobile-version med 3D-objekt centrerat). Båda är autoPlay +
          muted + loop + playsInline för universal browser-support.

          - Mobil (<md): SM-mobile.mp4 som centrerad fyrkantig top-banner.
            Hero-bakgrund får videons egen färg (#f0f2ed) via
            mobile-hero-bg-klassen så filmen flyter sömlöst in i
            bakgrunden — ingen hård edge mellan video och canvas.
          - Desktop (md+): SM_hero.mp4 fullbredd-bakgrund med två
            gradient-overlays (horisontell + vertikal) som ger hero-
            texten kontrast i vänsterspalten. */}
      {showHero ? (
        <>
          {/* Mobile-only fyrkantig top-banner. md:hidden så desktop-
              video aldrig laddas dubbelt. aspect-square + max-w-xs
              centrerar filmen utan att äta mer än ~280px höjd på en
              iPhone 14 Pro (393×852). */}
          <video
            key="sm-hero-mobile"
            className="pointer-events-none relative z-0 mx-auto mt-6 block aspect-square w-[min(280px,70vw)] object-contain md:hidden"
            autoPlay={!reducedMotion}
            muted
            loop={!reducedMotion}
            playsInline
            preload="auto"
            aria-hidden
          >
            <source src="/SM-mobile.mp4" type="video/mp4" />
          </video>
          {/* Desktop-version: 16:9 fullbredd-bakgrund. hidden md:block
              så mobilen aldrig laddar 1.5MB-filen. */}
          <video
            key="sm-hero"
            className="pointer-events-none absolute inset-0 hidden h-full w-full object-cover [object-position:78%_center] md:block"
            autoPlay={!reducedMotion}
            muted
            loop={!reducedMotion}
            playsInline
            preload="auto"
            aria-hidden
          >
            <source src="/SM_hero.mp4" type="video/mp4" />
          </video>
          {/* Två gradienter (desktop only): horisontell som mörknar
              vänsterkanten + vertikal som fadar mot botten där prompt-
              rutan lever. Inte renderade på mobil där videon är en
              fristående top-banner istället för fullbredd-bakgrund. */}
          <div
            aria-hidden
            className="from-background/85 via-background/40 dark:from-background/90 dark:via-background/50 pointer-events-none absolute inset-0 hidden bg-gradient-to-r to-transparent md:block"
          />
          <div
            aria-hidden
            className="to-background/80 dark:to-background/90 pointer-events-none absolute inset-0 hidden bg-gradient-to-b from-transparent via-transparent md:block"
          />
        </>
      ) : null}

      {/* Thin top progress strip while building/loading. */}
      {loading ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-20 h-[2px] overflow-hidden bg-transparent"
        >
          <div className="bg-foreground/70 h-full w-1/3 animate-[viewer-progress_1.6s_ease-in-out_infinite] rounded-full" />
        </div>
      ) : null}

      {/* BuildProgressCard — dominant central laddningsmodul när
          bygget pågår. Absolut positionerad så cardet är garanterat
          centrerat på canvasen oavsett vad andra siblings gör i
          flex-layouten.

          När operatören iterar på en EXISTERANDE preview (followup-
          mode) hålls föregående iframe mountad under bygge (se 1094
          nedan) så hen ser v1 medan v2 byggs istället för en vit ruta.
          Vi lägger då en semi-transparent backdrop på containern så
          BuildProgressCard har klart fokus utan att helt dölja
          föregående preview. För första-bygge (ingen tidigare iframe)
          fungerar samma backdrop ovanpå tom canvas utan visuell
          skillnad. */}
      {showBuildCard ? (
        <div className="bg-background/85 pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-6 backdrop-blur-sm">
          <div className="pointer-events-auto">
            {/* key={buildStage} forces a full remount on every stage
                transition so elapsedSec restarts at 0 via useState(0)
                without needing a setState call inside the effect
                body (react-hooks/set-state-in-effect). */}
            <BuildProgressCard key={buildStage} stage={buildStage} />
          </div>
        </div>
      ) : null}

      {/* Hero-text — visas alltid när StackBlitz inte aktivt visar en
          sajt (empty, unavailable, error).

          Två olika layouter för mobil vs desktop:
            - Mobil (<md): text staplad direkt under SM-mobile.mp4-bannern.
              Center-justerad (items-center) så hela hero ser ut som ett
              vertikalt flöde: video → eyebrow → rubrik → underrubrik →
              composer (composer kommer från PromptBuilder i page.tsx
              och ligger fixed bottom).
            - Desktop (md+): absolute overlay vänsterställd i canvasen
              ovanpå videons 3D-objekt (som sitter höger via 78%
              object-position).

          Rubriken har inte längre hårdkodad br — radbrytningen styrs
          istället av container-width och text-balance, vilket på 393px
          ger naturligt "Beskriv din sajt så / bygger vi den." istället
          för tidigare 4-rads-staplingen. */}
      {showHeroText ? (
        // pb-40 på mobil = ~160px safe zone under hero-text så PromptBuilder
        // (composer ~150px från bottom inkl. safe-area-padding) aldrig täcker
        // underrad. md:pb-0 + md:absolute återställer desktop-overlay-layouten
        // där hero-texten är vertikalt centrerad utan bottom-padding-behov.
        <div className="relative z-10 flex w-full flex-col items-center px-5 pt-4 pb-40 text-center md:absolute md:inset-0 md:h-full md:flex-row md:items-center md:px-12 md:pb-0 md:text-left lg:px-20">
          <div className="flex max-w-lg flex-col items-center gap-4 md:items-start">
            <span className="border-border/40 bg-background/70 text-foreground/70 rounded-full border px-3 py-1 font-mono text-[10px] tracking-[0.22em] uppercase shadow-sm backdrop-blur">
              Sajtbyggaren · localhost
            </span>
            <h1 className="text-foreground text-3xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-4xl md:text-5xl">
              Beskriv din sajt{" "}
              <span className="text-foreground/60">så bygger vi den.</span>
            </h1>
            <p className="text-foreground/75 max-w-md text-[13.5px] leading-relaxed text-balance sm:text-[14px] md:text-[15px]">
              Berätta kort vad sajten ska göra. Vi planerar, bygger och visar en
              förhandsvisning du kan klicka runt i direkt här.
            </p>
          </div>
        </div>
      ) : null}

      {/* Tidigare bodde en status-pill här (top-4 left-4) som visade
          "Förhandsvisning aktiv för {runId}". Den krockade visuellt
          med SiteHeader-logon och läckte rå run-ID-text in i UI:t
          utan att tillföra något: FloatingChat-headern säger redan
          "Sajten {siteId} är aktiv", och loading-pulsen längst upp
          (showLoading-stripen) räcker för att signalera arbete.
          Hela status-state togs bort när pillan gick. */}

      {/* Unavailable banner. Renderar strukturerad info per failure-läge:
          mock-run utan files, sajten inte byggd än, port-pool full, etc.
          ``unavailable`` är ``UnavailableInfo | null`` — när satt visas
          banner med titel/message/hint istället för den tidigare hårdkodade
          mock-run-strängen. */}
      {showUnavailable && unavailable ? (
        // pointer-events-none på overlayn så den inte fångar klick i tomma
        // ytan, men kortet självt är pointer-events-auto så "Försök igen"
        // går att trycka på. Tidigare saknades retry helt — operatören var
        // tvungen att välja om runen för att trigga om hämtningen.
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="pointer-events-auto max-w-md rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-4 text-sm text-amber-800 dark:text-amber-300">
            {unavailable.title ? (
              <div className="mb-1 font-medium">{unavailable.title}</div>
            ) : null}
            <div>{unavailable.message}</div>
            {unavailable.hint ? (
              <div className="mt-2 text-[12px] text-amber-700/80 dark:text-amber-300/80">
                {unavailable.hint}
              </div>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setRetryNonce((n) => n + 1)}
              className="mt-3 border-amber-500/50 bg-transparent text-amber-800 hover:bg-amber-500/15 dark:text-amber-200"
            >
              Försök igen
            </Button>
          </div>
        </div>
      ) : null}

      {/*
        Browser-fallback (Safari/Firefox/iOS) + StackBlitz SDK error-pre
        bor numera INUTI ``<StackblitzPreview/>`` (se render längst ned).
        Hela den vägen flyttades dit så ``@stackblitz/sdk`` aldrig dras in
        i ViewerPanel:s eager-chunk (bundle-bloat-fixen, ADR 0033).
      */}

      {/*
        Preview-iframe. Renderas bara när /api/preview/<siteId>
        returnerat en URL. Den URL:en är antingen en lokal
        ``http://localhost:<port>`` (``local-next``: ``next start`` på den
        genererade sajten) ELLER en publik ``…vercel.run``-https-URL
        (``vercel-sandbox``: en isolerad kopia i en Vercel Sandbox, ADR 0033).
        Båda iframe:as identiskt — ``localPreviewUrl`` håller den returnerade
        URL:en oavsett mode.
        Stora vinster (local-next): ~1s init istället för StackBlitz 60+s,
        funkar i Safari/Firefox utan credentialless-fallback, och
        same-machine-iframe kan ta emot postMessage från Site Inspector för
        Sprint 5:s live token-editor. vercel-sandbox är en publik https-iframe
        som fungerar i alla browsers utan att belasta operatörens maskin.

        Positionering: ``absolute inset-0`` så iframen fyller HELA
        canvasen oavsett vad andra flex-syskon (containerRef-divet,
        hero-text-wrappern) gör i layouten. Utan absolute hamnar
        iframen i flex-flödet och delar bredden med osynliga syskon,
        vilket gör previewen halvbred. z-index ligger under
        BuildProgressCard (z-20), error-pre (z-20), unavailable/
        fallback (z-10) men över hero-bakgrunden.
      */}
      {localPreviewUrl && !unavailable && !showEmpty ? (
        // Wrapper-divet bär device-toggle constraint:en (maxWidth).
        // När devicePreset === "full" har wrappern ingen style så
        // iframen fyller hela canvasen (oförändrat default-beteende).
        // När en preset (375/768/1024) är vald får wrappern
        // max-width + mx-auto så iframen krymper och centreras.
        //
        // Iframen hålls mountad även under `isBuilding`/`isFinalizing`
        // så operatören ser v1 medan v2 byggs (BuildProgressCard har
        // bg-background/85 backdrop-blur-sm för fokus). Slipper vit
        // canvas mellan iterationer. Om backenden stänger v1-server
        // för att starta v2 kan iframen visa ERR_CONNECTION_REFUSED
        // kort — backdrop-blurren slöjar det visuellt och progress-
        // cardet flyttar fokus. Inga visuella regressioner för
        // första-bygget eftersom localPreviewUrl då är null.
        <div
          className="absolute inset-0 z-[5] mx-auto h-full w-full bg-white transition-[max-width] duration-300 ease-out"
          style={previewWrapperStyle}
        >
          <iframe
            ref={iframeRef}
            src={localPreviewUrl}
            title="Sajt-preview"
            className="h-full w-full border-0 bg-white"
            // onLoad flippar iframeLoaded → skelett-overlayn nedan döljs.
            // Fångar både första render och byte av vald run. (Hanterar
            // inte fel inuti iframen — det är ett separat, framtida steg.)
            onLoad={() => setIframeLoaded(true)}
            // Tillåt scripts (Next.js client-side hydration) och
            // same-origin (sajten behåller sin egen origin —
            // localhost:<port> som vi spawnat, eller vercel.run-sandboxen
            // vi startat) men inte top-navigation eller popups. För den
            // cross-origin publika vercel.run-URL:en är allow-same-origin
            // ofarlig (sajten är cross-origin mot oss → ingen sandbox-escape)
            // och behövs så den genererade sajtens egna fetch/hydration fungerar.
            sandbox="allow-scripts allow-same-origin allow-forms"
          />
          {/*
            Skelett-overlay tills iframens dokument laddat. Dödar den vita
            blixten mellan att URL:en sätts och Next.js hydrerat. Gate:ad
            mot isBuilding/isFinalizing så den inte dubblerar
            BuildProgressCard (som redan äger ytan under bygge).
          */}
          {!iframeLoaded && !isBuilding && !isFinalizing ? (
            <div
              className="pointer-events-none absolute inset-0 z-[6] flex items-center justify-center bg-white"
              role="status"
              aria-live="polite"
            >
              <span className="sr-only">Laddar preview…</span>
              <Loader2
                aria-hidden
                className="text-muted-foreground/50 h-6 w-6 motion-safe:animate-spin"
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {/* StackBlitz-preview (LEGACY/PAUSED, ADR 0033) — bär device-preset-
          constraint på samma sätt som lokal preview-iframen ovan. mx-auto
          centrerar wrappern när max-width är satt; transition håller
          resize-rörelsen smooth.

          ``<StackblitzPreview/>`` laddas via en runtime ``import()`` (loader-
          effekten ovan) och RENDERAS
          bara här, när ``showStackblitz`` är true (stackblitz/auto efter att
          Steg 1 inte gällt/misslyckats). Det är så ``@stackblitz/sdk`` hålls
          UTANFÖR ViewerPanel:s eager-chunk — en normal vercel-sandbox/
          local-next-studioladdning monterar aldrig denna komponent och
          hämtar därför aldrig stackblitz-chunken. Komponenten äger sin egen
          containerRef, browser-fallback och error-pre.

          ``StackblitzPreviewComp`` är null tills den lazy runtime-``import()``
          (loader-effekten ovan) resolvat — det sker bara när
          ``showStackblitz`` är true. */}
      {showStackblitz && runId && StackblitzPreviewComp ? (
        <div
          className="mx-auto h-full w-full transition-[max-width] duration-300 ease-out"
          style={previewWrapperStyle}
        >
          <StackblitzPreviewComp runId={runId} isBuilding={isBuilding} />
        </div>
      ) : null}
    </div>
  );
}

/**
 * Central laddningskort som visas i mitten av canvasen under hela
 * /api/prompt-cykeln. Stegmarkören visar var vi är i pipelinen.
 *
 * Texterna är medvetet kundvänliga — slutoperatorn är inte tekniker
 * och behöver inte se "briefModel", "Project Input", "npm install",
 * "Next.js-sandbox" eller liknande. Vi beskriver vad SOM HÄNDER, inte
 * VILKEN modul som kör. Den tekniska pipelinen lever kvar i kod-
 * kommentarer och `current-focus.md` för utvecklare som behöver
 * felsöka.
 *
 * Mappas från PromptStage så vi kan visa rätt aktivt steg medan
 * `executeBuild()` jobbar.
 */
const BUILD_STEPS: ReadonlyArray<{
  id: "prepare" | "generate" | "build" | "preview";
  title: string;
  hint: string;
}> = [
  {
    id: "prepare",
    title: "Läser dina svar",
    hint: "Vi går igenom det du har fyllt i i wizarden.",
  },
  {
    id: "generate",
    title: "Planerar sajten",
    hint: "Vi väljer rätt struktur, ton och funktioner för er verksamhet.",
  },
  {
    id: "build",
    title: "Bygger sajten",
    hint: "Vi monterar alla sidor och bilder. Första bygget tar 1–3 minuter, sedan går det snabbare.",
  },
  {
    id: "preview",
    title: "Öppnar förhandsvisning",
    hint: PREVIEW_PREP_HINT,
  },
];

function stageToStepIndex(stage: PromptStage): number {
  switch (stage) {
    case "idle":
      return 0;
    case "thinking":
      return 1;
    case "building":
      return 2;
    case "success":
    case "degraded":
    case "failed":
      return 3;
    default:
      return 0;
  }
}

function BuildProgressCard({ stage }: { stage: PromptStage }) {
  const activeIdx = stageToStepIndex(stage);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const minutes = Math.floor(elapsedSec / 60);
  const seconds = (elapsedSec % 60).toString().padStart(2, "0");

  return (
    <div className="border-border/60 bg-background/95 w-full max-w-[560px] rounded-3xl border p-9 shadow-[0_32px_80px_-16px_rgba(0,0,0,0.25)] backdrop-blur-xl">
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-foreground text-[17px] font-semibold tracking-tight">
          Bygger din sajt
        </h2>
        <span className="bg-muted/50 text-foreground rounded-full px-2.5 py-1 font-mono text-[11px] tracking-tight tabular-nums">
          {minutes}:{seconds}
        </span>
      </div>

      <ol className="flex flex-col gap-0.5">
        {BUILD_STEPS.map((step, idx) => {
          const isActive = idx === activeIdx;
          const isPast = idx < activeIdx;
          const isFuture = idx > activeIdx;
          return (
            <li
              key={step.id}
              className={[
                "flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors",
                isActive ? "bg-foreground/[0.04]" : "",
              ].join(" ")}
            >
              <span
                className={[
                  "mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] transition-colors",
                  isPast
                    ? "bg-foreground text-background"
                    : isActive
                      ? "bg-foreground text-background"
                      : "border-border/70 bg-background text-muted-foreground/70 border",
                ].join(" ")}
              >
                {isPast ? (
                  <Check className="h-3 w-3" strokeWidth={2.5} />
                ) : isActive ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <span className="font-mono text-[9.5px] tracking-tight">
                    {idx + 1}
                  </span>
                )}
              </span>
              <div className="flex flex-1 flex-col leading-snug">
                <span
                  className={[
                    "text-[13px] font-medium tracking-tight",
                    isFuture ? "text-muted-foreground" : "text-foreground",
                  ].join(" ")}
                >
                  {step.title}
                </span>
                <span
                  className={[
                    "text-[11.5px] leading-relaxed",
                    isActive
                      ? "text-muted-foreground"
                      : "text-muted-foreground/70",
                  ].join(" ")}
                >
                  {step.hint}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="bg-border/50 mt-6 h-[2px] w-full overflow-hidden rounded-full">
        <div
          className="bg-foreground/80 h-full animate-pulse rounded-full transition-[width] duration-500 ease-out"
          style={{
            width: `${((activeIdx + 1) / BUILD_STEPS.length) * 100}%`,
          }}
        />
      </div>
    </div>
  );
}
