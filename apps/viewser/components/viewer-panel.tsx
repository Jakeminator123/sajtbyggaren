"use client";

import { ExternalLink, Check, Loader2 } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { resolvePreviewRuntimeDescriptor } from "@preview-runtime";

import { Button } from "@/components/ui/button";
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

type FilesPayload = {
  runId: string;
  files: Record<string, string>;
  error?: string;
};

type BrowserKind = "chromium" | "safari" | "firefox" | "unknown";

/**
 * Heuristik för "kan denna webbläsare köra en embeddad WebContainer-
 * iframe?". StackBlitz embed kräver `COEP: credentialless` på host-
 * dokumentet plus stöd för credentialless-iframes i browsern. Per
 * StackBlitz egen browser-support-tabell:
 *   - Chromium-baserade (Chrome, Edge, Brave, Opera, Vivaldi): JA
 *   - Safari (desktop + iOS, inkl. CriOS/FxiOS som är WebKit under huven):
 *     NEJ — Safari saknar credentialless och kan därför inte ladda embeds
 *   - Firefox: NEJ — beta-stöd för WebContainers men inte för embeds
 *
 * Detta dokumenteras i `docs/integrations/webcontainers-notes.md` och
 * `docs/integrations/stackblitz-research.md`. När browsern inte stödjer
 * embed visar ViewerPanel ett fallback-kort med en "Öppna i nytt fönster"-
 * knapp som anropar `sdk.openProject()` (top-level navigation till
 * stackblitz.com, fungerar i alla browsers eftersom det inte är embeddat).
 */
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

function getBrowserKind(): BrowserKind {
  if (typeof navigator === "undefined") return "chromium";
  const ua = navigator.userAgent;
  if (/Firefox\/\d+/.test(ua)) return "firefox";
  // iOS-browsers är alla WebKit oavsett etikett (CriOS = Chrome iOS,
  // FxiOS = Firefox iOS, EdgiOS = Edge iOS) — räkna som Safari.
  if (/iPhone|iPad|iPod|CriOS|FxiOS|EdgiOS/.test(ua)) return "safari";
  // Desktop Safari: "Safari/" finns men "Chrome/"/"Chromium/" saknas.
  if (/Safari\/\d+/.test(ua) && !/Chrom(e|ium)\/\d+/.test(ua)) return "safari";
  if (/Chrom(e|ium)\/\d+/.test(ua)) return "chromium";
  return "unknown";
}

function supportsStackBlitzEmbed(kind: BrowserKind): boolean {
  // SSR och okänd browser: vi optimistiskt försöker embeda. Worst case
  // får operatören error-pre + kan klicka "Öppna i nytt fönster".
  if (kind === "unknown") return true;
  return kind === "chromium";
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

function formatViewerError(caught: unknown): string {
  if (caught instanceof Error) {
    const details = [
      `name: ${caught.name || "Error"}`,
      `message: ${caught.message || "(empty message)"}`,
    ];
    if (caught.stack) {
      details.push(
        `stack:\n${caught.stack.split("\n").slice(0, 20).join("\n")}`,
      );
    }
    return details.join("\n");
  }

  try {
    return `non-Error rejection:\n${JSON.stringify(caught, null, 2)}`;
  } catch {
    return `non-Error rejection:\n${String(caught)}`;
  }
}

export function ViewerPanel({
  runId,
  siteId,
  isBuilding = false,
  buildStage = "idle",
}: ViewerPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [error, setError] = useState<string | null>(null);
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
  // När browsern inte stödjer embed sparar vi hämtade filer + den
  // detekterade browser-kinden i ett gemensamt state-objekt.
  // Knappen anropar `sdk.openProject()` med samma payload (utan att
  // fetcha igen) och fallback-kortets text personifieras via
  // `fallback.kind`. Browser-detekteringen sker synkront inuti
  // run-id-effekten (navigator är tillgänglig där eftersom effekten
  // kör efter mount) — ingen separat detect-effect behövs, och
  // useEffect-deps-arrayen förblir konstant så HMR inte klagar.
  const [fallback, setFallback] = useState<{
    files: Record<string, string>;
    kind: BrowserKind;
  } | null>(null);
  const [openingExternal, setOpeningExternal] = useState(false);
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
   * Iframe-wrapper-stil. När devicePreset != "full" får wrappern en
   * max-width-constraint som centreras med mx-auto. iframen själv
   * fyller wrappern (h-full w-full) så den krympker när wrappern krymper.
   * useMemo så stilobjektet inte recreate:as per render — undviker
   * onödiga reflows i StackBlitz-iframen.
   */
  const previewWrapperStyle = useMemo(() => {
    const width = DEVICE_PRESET_WIDTHS[devicePreset];
    if (width === null) return undefined;
    return { maxWidth: `${width}px` };
  }, [devicePreset]);

  // Öppna sajten i en ny flik på stackblitz.com (top-level navigation,
  // ingen embed = ingen credentialless-iframe = funkar i Safari/Firefox).
  // Använder samma SDK + samma files-payload som embed-vägen.
  const handleOpenExternal = useCallback(async () => {
    if (!fallback || !runId || openingExternal) return;
    setOpeningExternal(true);
    setError(null);
    try {
      const sdk = (await import("@stackblitz/sdk")).default;
      sdk.openProject(
        {
          title: `Sajtbyggaren preview ${runId}`,
          description: "Generated site snapshot",
          template: "node",
          files: fallback.files,
        },
        {
          openFile: "app/page.tsx",
          newWindow: true,
        },
      );
    } catch (caught) {
      setError(formatViewerError(caught));
    } finally {
      setOpeningExternal(false);
    }
  }, [fallback, openingExternal, runId]);

  useEffect(() => {
    // containerRef-div is now mounted unconditionally (see render
    // below) so containerRef.current is bound on every runId change,
    // including transitions out of unavailable=true. The remaining
    // null-check covers the very first render before React has
    // attached the ref (effect runs after commit, but we still keep
    // the guard for defense in depth).
    if (!runId || !containerRef.current) {
      setUnavailable(null);
      setLoading(false);
      setFallback(null);
      return;
    }

    const node = containerRef.current;
    let cancelled = false;
    setError(null);
    setUnavailable(null);
    setFallback(null);
    setLocalPreviewUrl(null);
    setIframeLoaded(false);
    setLoading(true);
    node.replaceChildren();

    void (async () => {
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

      // Steg 2: gammal StackBlitz-väg som fallback (endast i
      // stackblitz/auto-mode — local-next-grenen ovan returnerar
      // tidigare med strukturerat fel).
      try {
        const response = await fetch(`/api/runs/${runId}/files`);
        const payload = (await response.json()) as FilesPayload;
        if (!response.ok || payload.error) {
          // 404 = run-dir saknar generated-files / .generated/<siteId>/.
          // Det är förväntat för dev_generate-mock-runs (placeholder-pipeline).
          // Visa pedagogisk fallback istället för stack trace.
          if (response.status === 404) {
            // Cancelled-guard: a stale 404 from a previous runId must
            // not overwrite UI state for the run that is currently
            // selected (race condition when runId changes faster than
            // the in-flight fetch resolves). Mirrors the guard on the
            // success / catch paths below.
            if (cancelled) return;
            setUnavailable({
              title: "Mock-run utan generated-files",
              message:
                "Förhandsvisning saknas för denna run. Mock-runs skriver inte en faktisk Next.js-app.",
              hint: "Skicka en prompt i chat-rutan för att köra en riktig builder-run.",
            });
            setLoading(false);
            return;
          }
          throw new Error(payload.error ?? "Kunde inte hämta filer för run.");
        }

        if (cancelled || !containerRef.current) return;

        // Browser-kind-check: Safari, Firefox och iOS-browsers kan
        // inte rendera embeddade WebContainer-iframes (saknar stöd
        // för credentialless cross-origin isolation). Visa
        // fallback-kort med "Öppna i nytt fönster" istället för
        // StackBlitz' kryptiska "Unable to run Embedded Project"-
        // fel som annars dyker upp inuti iframen. Vi detekterar
        // synkront här eftersom navigator är tillgänglig efter mount
        // — separat detect-effect behövs inte.
        const kind = getBrowserKind();
        if (!supportsStackBlitzEmbed(kind)) {
          setFallback({ files: payload.files, kind });
          setLoading(false);
          return;
        }

        // B43 (post-review-2): the dynamic import + embedProject have
        // their own awaits. If the operator switches runId between
        // them, cleanup sets cancelled=true but the in-flight
        // embedProject still mounts the stale preview into the
        // always-mounted ref-div. Re-check cancelled after BOTH
        // awaits and explicitly clear the node if we mounted into
        // a stale tree.
        const sdk = (await import("@stackblitz/sdk")).default;
        if (cancelled || !containerRef.current) return;

        // StackBlitz SDK replaces the target element with an iframe
        // (`target.replaceWith(frame)`). Never pass it the React-owned
        // shell div itself; create an unmanaged child and let the SDK
        // replace that child. React then keeps owning a stable shell,
        // avoiding DOM placement crashes when sibling status/error UI
        // re-renders while StackBlitz mutates the preview DOM.
        const mountTarget = document.createElement("div");
        mountTarget.className = "h-full w-full";
        containerRef.current.replaceChildren(mountTarget);

        // Patch document.createElement so the <iframe> StackBlitz SDK
        // creates inside embedProject is tagged with the
        // `credentialless` HTML attribute BEFORE the browser starts
        // loading its src. Our host page sends
        // `Cross-Origin-Embedder-Policy: credentialless` (see
        // apps/viewser/next.config.ts), which is required for the
        // WebContainer inside the iframe to access SharedArrayBuffer.
        // But Chrome additionally requires that EACH embedded iframe
        // either responds with its own COEP header or carries the
        // credentialless attribute on the <iframe> element — and
        // StackBlitz's embed response does not send a COEP header.
        // Without the attribute Chrome shows "Specify a Cross-Origin
        // Embedder Policy to prevent this frame from being blocked"
        // in DevTools and refuses to load the embed. The attribute
        // must be set before insertion because the browser begins
        // fetching the iframe's document as soon as it enters the DOM
        // with src already populated. See
        // https://developer.chrome.com/blog/iframe-credentialless for
        // the credentialless-iframe model and why parent COEP alone
        // is insufficient.
        //
        // CRITICAL — credentialless ALONE is INTE tillräckligt. För
        // att `window.crossOriginIsolated` ska bli `true` inuti
        // iframen (och därmed `SharedArrayBuffer` exponeras till
        // WebContainern) krävs OCKSÅ att iframen taggas med
        // `allow="cross-origin-isolated"` (Permissions Policy-
        // delegering från parent). Annars visar StackBlitz "Unable
        // to run Embedded Project — Looks like this project is being
        // embedded without proper isolation headers" trots att vår
        // COEP/COOP-headers är korrekt levererade.
        //
        // Den delen sköts via SDK:ns `crossOriginIsolated: true`-flagga
        // i embedProject-options nedan — den lägger till
        // `cross-origin-isolated` i iframens `allow`-lista via
        // `setFrameAllowList` (se sdk.m.js:132-140). Dokumenterad i
        // EmbedOptions-typen och refererad i
        // https://blog.stackblitz.com/posts/cross-browser-with-coop-coep/
        // som den officiella vägen för cross-origin-isolated embed.
        //
        // Båda behövs: `credentialless`-attributet löser COEP-kravet,
        // `allow="cross-origin-isolated"` löser Permissions Policy-
        // delegeringen. Saknar man någondera fallerar embedden.
        //
        // The patch is scoped via try/finally so we never leave the
        // global API mutated past the SDK's internal iframe creation.
        const originalCreateElement = document.createElement.bind(document);
        const patchedCreateElement = ((
          tagName: string,
          options?: ElementCreationOptions,
        ) => {
          const elem = originalCreateElement(tagName, options);
          if (
            typeof tagName === "string" &&
            tagName.toLowerCase() === "iframe"
          ) {
            elem.setAttribute("credentialless", "");
          }
          return elem;
        }) as typeof document.createElement;
        document.createElement = patchedCreateElement;

        try {
          await sdk.embedProject(
            mountTarget,
            {
              title: `Sajtbyggaren preview ${runId}`,
              description: "Generated site snapshot",
              template: "node",
              files: payload.files,
              settings: {
                compile: {
                  // Auto-rebuild when files ändras (StackBlitz default = on,
                  // men vi sätter explicit så det aldrig avbryts av framtida
                  // SDK-versionsändringar).
                  trigger: "auto",
                },
              },
            },
            {
              openFile: "app/page.tsx",
              view: "preview",
              // Ljust tema för att matcha Sajtbyggarens egen UI istället för
              // StackBlitz default-mörkblå. Möjliga värden: "default" (mörk),
              // "light", "dark". `terminalHeight: 0` döljer den lilla
              // terminal-panelen som annars syns nere i preview-läget och
              // gör helhetsintrycket mörkare.
              theme: "light",
              terminalHeight: 0,
              // Göm sidebar med fil-listan eftersom vi visar bara preview
              // (operatören inspekterar koden via Run History-drawern i
              // Sajtbyggaren-UI:t, inte via StackBlitz-sidebaren).
              hideExplorer: true,
              hideNavigation: true,
              hideDevTools: true,
              clickToLoad: false,
              height: 1200,
              // Säg åt SDK:n att lägga till `cross-origin-isolated` i
              // iframens `allow`-lista. Krävs för att Permissions Policy
              // ska delegera cross-origin-isolation till stackblitz.com-
              // origin:en — utan det blir `window.crossOriginIsolated`
              // alltid `false` inuti iframen oavsett vad host:en
              // skickar för COEP/COOP-headers, och WebContainern
              // bootar inte (visar "Unable to run Embedded Project").
              // Tillsammans med `credentialless`-attributet ovan
              // (createElement-patchen) ger detta full cross-origin
              // isolation åt embedden. Se EmbedOptions i
              // @stackblitz/sdk/types/interfaces.d.ts och
              // https://blog.stackblitz.com/posts/cross-browser-with-coop-coep/.
              crossOriginIsolated: true,
            },
          );
        } finally {
          document.createElement = originalCreateElement;
        }

        if (cancelled) {
          // Stale embed mounted while we were unmounting. Tear it
          // down so the next runId starts from an empty node.
          if (containerRef.current) {
            containerRef.current.replaceChildren();
          }
          return;
        }

        // Fullscreen preview canvas: StackBlitz SDK sets a fixed
        // height attribute on the iframe (from the `height` option
        // above). Override it via inline style so the iframe expands
        // to fill the canvas container. The container itself owns
        // sizing via flex/CSS — the iframe should always be 100%
        // height/width inside it.
        const iframe = containerRef.current?.querySelector("iframe");
        if (iframe) {
          iframe.style.height = "100%";
          iframe.style.width = "100%";
          iframe.style.border = "0";
        }

        setLoading(false);
      } catch (caught) {
        if (!cancelled) {
          setError(formatViewerError(caught));
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (node) node.replaceChildren();
    };
    // retryNonce: bumpas av "Försök igen" i otillgänglig-bannern → kör om
    // effekten med full state-reset (samma väg som ett runId-byte).
  }, [runId, siteId, retryNonce]);

  const showEmpty = !runId;
  const showUnavailable = unavailable && !!runId;
  const showFallback = !!fallback && !!runId && !isBuilding;
  // "Finalize"-fasen efter build_site.py är klart: backend har skrivit
  // build-result.json (status=ok), frontend har satt stage="success" och
  // building=false, men ViewerPanel hämtar nu manifest från
  // /api/runs/X/files och bootar StackBlitz-SDK:n. Utan denna flagga
  // försvann BuildProgressCard direkt vid success — operatören tappade
  // den visuella kontinuiteten från "Bygger sajt" → "Startar preview".
  const isFinalizing =
    buildStage === "success" && loading && !!runId && !unavailable;
  // Visa hero-videon så länge ingen riktig iframe har mountats. Det
  // täcker: ingen run vald (empty), 404 på files (unavailable),
  // pågående fetch (loading), SDK-error, pågående bygge OCH
  // browser-fallback (Safari/Firefox). `loading` räcker —
  // `isFinalizing` är en delmängd av `loading`.
  const showHero =
    showEmpty ||
    showUnavailable ||
    showFallback ||
    loading ||
    !!error ||
    isBuilding;
  // BuildProgressCard tar över mittenytan när vi aktivt bygger ELLER
  // när bygget precis blivit klart men preview-iframen fortfarande
  // bootas. Hero-texten ska INTE visas i någondera fas — det skulle
  // vara dubbel information med två konkurrerande UI:n. Inte heller
  // när vi visar browser-fallback-kortet (det äger mittenytan).
  const showHeroText =
    (showEmpty || showUnavailable || !!error) &&
    !isBuilding &&
    !isFinalizing &&
    !showFallback;
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

      {/* Browser-fallback för Safari/Firefox/iOS. Sajten är byggd men
          inbäddad preview funkar inte (browsern stödjer inte
          credentialless cross-origin isolation). Knappen öppnar samma
          projekt i nytt fönster på stackblitz.com via sdk.openProject
          — top-level navigation som funkar i alla browsers. */}
      {showFallback ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center px-6">
          <div className="border-border/60 bg-background/95 pointer-events-auto w-full max-w-[460px] rounded-3xl border p-7 shadow-[0_32px_80px_-16px_rgba(0,0,0,0.25)] backdrop-blur-xl">
            <h2 className="text-foreground mb-4 text-[17px] font-semibold tracking-tight">
              Sajten är klar
            </h2>

            <p className="text-foreground/85 mb-3 text-[13px] leading-relaxed">
              {fallback?.kind === "firefox"
                ? "Firefox stödjer inte ännu inbäddad preview från WebContainers."
                : "Safari stödjer inte inbäddad preview från WebContainers."}{" "}
              Sajten är byggd och redo — öppna den i ett nytt fönster på
              stackblitz.com där den fungerar direkt.
            </p>

            <Button
              type="button"
              onClick={handleOpenExternal}
              disabled={openingExternal}
              className="w-full justify-center gap-2"
            >
              {openingExternal ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Öppnar…
                </>
              ) : (
                <>
                  <ExternalLink className="h-4 w-4" />
                  Öppna preview i nytt fönster
                </>
              )}
            </Button>

            {/* Två tips, prioriterade efter ROI för operatören:
                1. Bygg lokalt → LocalRuntime-iframen (port 4100-4199) är
                   en plain http-iframe utan credentialless-krav och funkar
                   i alla browsers inklusive Safari/Firefox/iOS. Det är
                   den DEFAULT-rekommenderade vägen för operator-bygda
                   sajter (se VIEWSER_PREVIEW_MODE=local-next i .env.example).
                2. Byt browser → endast om operatören är fast i StackBlitz-
                   mode och inte kan bygga lokalt. Mindre prioriterat. */}
            <p className="text-muted-foreground mt-3 text-[11.5px] leading-relaxed">
              Tips: kör{" "}
              <code className="font-mono">python scripts/build_site.py</code>{" "}
              och sätt{" "}
              <code className="font-mono">VIEWSER_PREVIEW_MODE=local-next</code>{" "}
              för en inbäddad preview som fungerar i alla browsers — eller öppna
              Sajtbyggaren i Chrome/Edge/Brave om du vill stanna i
              StackBlitz-läget.
            </p>
          </div>
        </div>
      ) : null}

      {/* StackBlitz SDK error pre — kept as readable diagnostic. */}
      {error ? (
        <pre className="border-destructive/40 bg-destructive/10 text-destructive absolute bottom-24 left-1/2 z-20 max-h-48 w-[min(90vw,640px)] -translate-x-1/2 overflow-auto rounded-lg border px-3 py-2 text-[11px] whitespace-pre-wrap shadow-lg">
          {error}
        </pre>
      ) : null}

      {/*
        containerRef-div hålls mounted oavsett `unavailable` så
        containerRef.current är bunden över transitions. Tidigare
        satt den i else-grenen av en `unavailable ? tips : <div ref>`
        ternary, vilket avmonterade ref när 404 satte
        unavailable=true - det låste UI:t i stuck state när nästa
        runId valdes (effekten har bara `[runId]` som dep och kör
        inte om vid unavailable-flip). Hidden via Tailwind när
        empty/unavailable äger ytan.
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

      {/*
        containerRef-div hålls mounted oavsett `unavailable` så
        containerRef.current är bunden över transitions. Tidigare
        satt den i else-grenen av en `unavailable ? tips : <div ref>`
        ternary, vilket avmonterade ref när 404 satte
        unavailable=true - det låste UI:t i stuck state när nästa
        runId valdes (effekten har bara `[runId]` som dep och kör
        inte om vid unavailable-flip). Hidden via Tailwind när
        empty/unavailable äger ytan ELLER när lokal preview tagit
        över canvasen.
      */}
      {/* StackBlitz-container — bär device-preset-constraint på samma
          sätt som lokal preview-iframen ovan. mx-auto centrerar wrappern
          när max-width är satt; transition håller resize-rörelsen smooth
          så iframen inte hoppar abrupt mellan storlekar. */}
      <div
        className="mx-auto h-full w-full transition-[max-width] duration-300 ease-out"
        style={previewWrapperStyle}
      >
        <div
          ref={containerRef}
          className={`h-full w-full ${unavailable || showEmpty || isBuilding || isFinalizing || showFallback || localPreviewUrl ? "invisible" : ""}`}
        />
      </div>
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
