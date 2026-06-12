"use client";

import { Cloud, RefreshCw, WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BuilderShell } from "@/components/builder/builder-shell";
import type { FollowupVisibleEffect } from "@/components/builder/use-followup-build";
import { usePendingBuild } from "@/components/builder/use-pending-build";
import { ConsoleDrawer } from "@/components/console-drawer";
import { DevicePresetProvider } from "@/components/device-preset-context";
import { PreviewInspectorProvider } from "@/components/preview-inspector-context";
import { ErrorBoundary } from "@/components/error-boundary";
import { SiteHeader } from "@/components/layout/site-header";
import type { ProjectInputOption } from "@/components/project-input-picker";
import {
  PromptBuilder,
  type PromptBuildOutcome,
  type PromptStage,
} from "@/components/prompt-builder";
import type { RunHistoryItem } from "@/components/run-history";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { ViewerPanel } from "@/components/viewer-panel";

type RunsApiPayload = {
  runs?: RunHistoryItem[];
  projectInputs?: ProjectInputOption[];
  error?: string;
  // Hostad Vercel-vy: ren info-banner från /api/runs (VERCEL=1). Sedan
  // B199 v2 är detta ENBART en banner — den armar INTE 404-latchen i
  // lib/hosted-run-artefacts.ts, eftersom artefakt-/trace-ytorna numera
  // serveras hostat (KV/blob) och ska få fetcha som lokalt.
  hostedBanner?: string;
};

type FetchedRunsPayload = {
  nextRuns: RunHistoryItem[];
  nextInputs: ProjectInputOption[];
  hostedBanner: string | null;
};

// B197-omladdning: builder-valet (runId + siteId) persisteras per flik i
// sessionStorage så en hård reload kan återställa builder-läget — hostat
// är det dessutom nyckeln till per-sajt-historiken (/api/runs?siteId=).
const STUDIO_SELECTION_STORAGE_KEY = "viewser-studio-selection";
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

type SavedStudioSelection = { runId: string; siteId: string };

function readSavedStudioSelection(): SavedStudioSelection | null {
  try {
    const raw = sessionStorage.getItem(STUDIO_SELECTION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<SavedStudioSelection>;
    if (typeof parsed.runId !== "string" || parsed.runId.length === 0) {
      return null;
    }
    if (
      typeof parsed.siteId !== "string" ||
      !SITE_ID_PATTERN.test(parsed.siteId)
    ) {
      return null;
    }
    return { runId: parsed.runId, siteId: parsed.siteId };
  } catch {
    return null;
  }
}

function headerStatusForOutcome(
  runId: string,
  outcome: PromptBuildOutcome,
): string {
  if (outcome === "ok") return `Build klar via prompt: ${runId}`;
  if (outcome === "degraded") return `Build klar med varning: ${runId}`;
  if (outcome === "failed") return `Build misslyckades: ${runId}`;
  return `Build klar med okänd status: ${runId}`;
}

// Pure data fetcher. Separated from setState so callers can place a
// cancellation guard between the await and the state mutation. Without
// this split the success path runs setState unconditionally even when
// the effect has been cancelled (component unmount), which races with
// a fresh effect that has already populated state.
//
// ``siteIdHint`` (B199 v2): hostat listar /api/runs bara per sajt (siteId
// är capability-nyckeln), så hostade anrop skickar den aktiva sajten.
// Lokalt skickas aldrig en hint — listan förblir ofiltrerad som förut.
async function fetchRuns(
  siteIdHint?: string | null,
): Promise<FetchedRunsPayload> {
  const url =
    siteIdHint && SITE_ID_PATTERN.test(siteIdHint)
      ? `/api/runs?siteId=${encodeURIComponent(siteIdHint)}`
      : "/api/runs";
  const response = await fetch(url, { cache: "no-store" });
  const payload = (await response.json()) as RunsApiPayload;
  if (!response.ok || payload.error) {
    throw new Error(payload.error ?? "Kunde inte läsa /api/runs.");
  }
  return {
    nextRuns: payload.runs ?? [],
    nextInputs: payload.projectInputs ?? [],
    hostedBanner: payload.hostedBanner ?? null,
  };
}

export default function Home() {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [projectInputs, setProjectInputs] = useState<ProjectInputOption[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("painter-palma");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState(
    "Laddar runs och project inputs…",
  );
  const [building, setBuilding] = useState(false);
  const [buildStage, setBuildStage] = useState<PromptStage>("idle");
  const [consoleOpen, setConsoleOpen] = useState(false);
  // Network-failure UX: när initial /api/runs failar visar vi en
  // dedikerad retry-rad i hero-ytan istället för bara en stuck status-
  // text. `runsLoadError` är operatör-läsbart fel-meddelande, eller null
  // när allt är OK eller ännu inte laddat. Sätts av `loadRuns()` nedan.
  const [runsLoadError, setRunsLoadError] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);
  // Hostad Vercel-vy: när /api/runs svarar med en hostedBanner (VERCEL=1)
  // visar vi en ärlig info-banner. Null lokalt (oförändrad upplevelse).
  const [hostedBanner, setHostedBanner] = useState<string | null>(null);
  const toast = useToast();
  // Live Build Sync: pending-build-state delas mellan BuilderShell
  // (som äger FloatingChat + dialogerna) och Versions-tab. Sätts
  // av onBuildStart-callbacks, rensas av onBuildEnd.
  //
  // pendingBaseRunId: när operatören klickar "Iterera från denna" i
  // Versions-tab plockas runId upp här så FloatingChat kan skicka
  // ``baseRunId`` i nästa /api/prompt-fetch. Rensas på onBuildEnd
  // (eller TTL i hooken om operatören aldrig submittade).
  const {
    pendingBuild,
    beginPending,
    clearPending,
    pendingBaseRunId,
    setPendingBaseRunId,
  } = usePendingBuild();

  // Sätts till true om operatören aktivt lämnar den pågående buildens
  // mål-vy (klick på "Ny sajt", val av annan run i ConsoleDrawer). När
  // handleBuildDone landar efteråt får den inte rycka tillbaka
  // selectedRunId/selectedSiteId — den ska bara uppdatera history-
  // listan så den färdiga runen finns där om operatören vill gå
  // tillbaka. B6 i scout-review 2026-05-24.
  const userNavigatedAwayRef = useRef(false);
  // B197-omladdning: återställningen från sessionStorage får bara ske en
  // gång per sidvisning (första lyckade /api/runs-laddningen) — annars
  // skulle en senare refetch kunna rycka tillbaka ett aktivt operatörsval.
  const restoredSelectionRef = useRef(false);
  // Hostad builder-paritet (B194-uppföljning): hostat returnerar /api/runs
  // alltid tomma runs/projectInputs, så builderTarget kan aldrig aktiveras
  // via listorna. Men byggen som klienten SJÄLV slutfört i denna session
  // är betrodda — backend har redan persisterat run-state (B194) och tar
  // emot följdprompter när VIEWSER_ENABLE_HOSTED_BUILD=1. Vi minns
  // runId → siteId för lyckade byggen så builder-läget (FloatingChat) kan
  // tändas hostat. Nollställs vid omladdning (känd B197-paritetslucka).
  // State (inte ref) — läses i builderTarget-memon under render. Muteras
  // aldrig på plats; varje uppdatering skapar en ny Map (se handleBuildDone).
  const [sessionBuiltRuns, setSessionBuiltRuns] = useState<Map<string, string>>(
    new Map(),
  );
  // Speglar consoleOpen för ⌘K-handlern (som lever i en []-effekt och
  // annars stänger över initialt värde). Synkas i effekt — ref-mutation i
  // render flaggas av react-hooks/refs.
  const consoleOpenRef = useRef(consoleOpen);
  useEffect(() => {
    consoleOpenRef.current = consoleOpen;
  }, [consoleOpen]);

  // B197-omladdning: persistera builder-valet per flik. Rensas när
  // operatören går till "Ny sajt" (selectedRunId null). Best-effort —
  // privat läge utan sessionStorage degraderar tyst till dagens beteende.
  useEffect(() => {
    try {
      if (selectedRunId) {
        sessionStorage.setItem(
          STUDIO_SELECTION_STORAGE_KEY,
          JSON.stringify({ runId: selectedRunId, siteId: selectedSiteId }),
        );
      } else {
        sessionStorage.removeItem(STUDIO_SELECTION_STORAGE_KEY);
      }
    } catch {
      // Storage otillgänglig (privat läge/kvot) — återställning är opt-in.
    }
  }, [selectedRunId, selectedSiteId]);

  // siteId som är "aktivt" via vald run (om någon). Används för att
  // visa "Följer vald run"-hint i ProjectInputPicker så operatören ser
  // att panelen automatiskt följer runens DNA istället för det
  // manuellt valda Project Input:et.
  const activeRun = runs.find((run) => run.runId === selectedRunId);
  const runSiteId =
    activeRun?.siteId && activeRun.siteId !== "unknown"
      ? activeRun.siteId
      : null;
  const runSiteIdUnknown =
    !!selectedRunId &&
    !!activeRun &&
    (!activeRun.siteId || activeRun.siteId === "unknown");

  function applyRunsData(
    {
      nextRuns,
      nextInputs,
      hostedBanner: nextHostedBanner,
    }: FetchedRunsPayload,
    ctx?: {
      selectedRunId: string | null;
      selectedSiteId: string;
    },
  ) {
    const effectiveRunId = ctx?.selectedRunId ?? selectedRunId;
    const effectiveSiteId = ctx?.selectedSiteId ?? selectedSiteId;

    setRuns(nextRuns);
    setProjectInputs(nextInputs);
    setHostedBanner(nextHostedBanner);
    // Auto-väljer INTE senaste run vid mount. Det orsakade att
    // ViewerPanel direkt triggade en /api/runs/:runId/files-fetch
    // mot en gammal run innan operatören överhuvudtaget bett om något,
    // vilket gömde hero-vyn och visade en orelevant status-pill. Nu
    // visas hero tills operatören skickar en ny prompt eller väljer
    // en run explicit i ConsoleDrawer.
    //
    // Reset-fallbacken körs bara när ingen run är vald — annars äger
    // run-following (handler-sync i onBuildDone/onSelectRunIdAndSync)
    // selectedSiteId och vi får inte skriva över den med "första
    // inputen i listan". ctx skickas från onBuildDone så vi inte läser
    // ett gammalt selectedRunId ur closure efter fetchRuns().then().
    if (
      !effectiveRunId &&
      !nextInputs.find((item) => item.siteId === effectiveSiteId) &&
      nextInputs.length
    ) {
      setSelectedSiteId(nextInputs[0].siteId);
    }
    setStatusText("Sajtbyggaren — localhost-only operator-konsol.");
  }

  // Run-following sync via handlers (inte useEffect) för att inte bryta
  // React 19:s `react-hooks/set-state-in-effect`. När operatören väljer
  // en run i RunHistory / ConsoleDrawer eller en build precis blivit
  // klar uppdaterar vi selectedRunId OCH selectedSiteId atomiskt så
  // ProjectInputPicker aldrig visar fel run:s DNA.
  function selectRunAndSyncSiteId(runId: string) {
    // Markera att operatören aktivt navigerar bort om ett bygge pågår —
    // den färdig-payloaden får inte rycka tillbaka selectedRunId.
    if (building) userNavigatedAwayRef.current = true;
    setSelectedRunId(runId);
    const run = runs.find((item) => item.runId === runId);
    if (run && run.siteId && run.siteId !== "unknown") {
      setSelectedSiteId(run.siteId);
    }
  }

  // Stable ref för retry-callback i toast-action. Utan ref:en skulle vi
  // stänga över sig själv (`loadRuns` används innan den deklareras), vilket
  // bryter React 19:s `react-hooks/immutability`-regel. Ref:en pekar alltid
  // på senaste `loadRuns` och kallas bara på user-klick, så det är en
  // safe escape hatch.
  const loadRunsRef = useRef<(() => Promise<void>) | null>(null);

  // Återanvändbar loader för initial fetch + retry-knapp. Sätter både
  // `runsLoadError` (för retry-cardet) och `statusText` (för headern).
  // Använder `cancelled` så avmonterad component inte skriver state efter
  // unmount. Returneras som callback så retry-knappen kan trigga om.
  //
  // OBS: vi sätter INTE `setRunsLoading(true)` här. React 19:s
  // `react-hooks/set-state-in-effect` flaggar sync setState innan första
  // `await` i en effect-trigad async-funktion. `runsLoading` initieras
  // istället till `true` i useState ovan, och retry-callsite (user event)
  // sätter den till true igen — vilket är OK eftersom det inte är en
  // effect.
  const loadRuns = useCallback(
    async (cancelledRef?: { current: boolean }): Promise<void> => {
      try {
        let data = await fetchRuns();
        // B197-omladdning, hostade halvan: /api/runs utan siteId är tom
        // hostat (capability-modellen), så finns ett sparat val hämtar vi
        // den sajtens historik innan återställningen nedan. Best-effort —
        // ett fel behåller bas-payloaden (banner + tomma listor).
        if (data.hostedBanner && !restoredSelectionRef.current) {
          const saved = readSavedStudioSelection();
          if (saved) {
            try {
              data = await fetchRuns(saved.siteId);
            } catch {
              // Behåll bas-payloaden — återställningen är best-effort.
            }
          }
        }
        if (cancelledRef?.current) return;
        applyRunsData(data);
        // B197-omladdning: återställ builder-valet EN gång per sidvisning,
        // och bara om den sparade runen faktiskt finns i den hämtade listan
        // (annars vore builder-läget en lögn mot en raderad/okänd run).
        if (!restoredSelectionRef.current) {
          restoredSelectionRef.current = true;
          const saved = readSavedStudioSelection();
          if (
            saved &&
            data.nextRuns.some((run) => run.runId === saved.runId)
          ) {
            setSelectedRunId(saved.runId);
            setSelectedSiteId(saved.siteId);
          }
        }
        setRunsLoadError(null);
      } catch (error) {
        if (cancelledRef?.current) return;
        const message =
          error instanceof Error
            ? error.message
            : "Kunde inte läsa initial data.";
        setRunsLoadError(message);
        setStatusText(message);
        // Toast så operatören ser felet även om hen inte tittar på hero
        // -ytan. Action ger snabb retry utan att leta upp kortet — vi
        // läser via ref:en så vi inte stänger över oss själva.
        toast.show({
          variant: "error",
          title: "Kunde inte ladda runs",
          description: message,
          action: {
            label: "Försök igen",
            onClick: () => {
              setRunsLoading(true);
              void loadRunsRef.current?.();
            },
          },
        });
      } finally {
        if (!cancelledRef?.current) {
          setRunsLoading(false);
        }
      }
    },
    // applyRunsData är en stabil closure (samma identitet hela komponentens
    // livstid) och ändras aldrig — låter eslint-disable peka ut det
    // explicit istället för att lyfta den ut till useCallback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [toast],
  );

  // Håll ref:en synkad med senaste closure varje render.
  useEffect(() => {
    loadRunsRef.current = () => loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    const cancelledRef = { current: false };
    // Wrap i async IIFE så React 19:s `react-hooks/set-state-in-effect`
    // ser att setState landar EFTER en await-gräns. Att kalla `loadRuns`
    // direkt fångar inte regelmotorn — den kan inte följa setState förbi
    // callback-gränsen och flaggar som om vi satte state synkront.
    void (async () => {
      await loadRuns(cancelledRef);
    })();
    return () => {
      cancelledRef.current = true;
    };
  }, [loadRuns]);

  // Global Cmd/Ctrl+K toggle:ar ConsoleDrawer. Standardgenvägen i moderna
  // dev-tools (Linear, Vercel, Stripe Dashboard) — operatören förväntar
  // sig den. Vi lyssnar på document-nivå men hoppar över när fokus är i
  // ett editable-element (textarea, contenteditable, input) så vi inte
  // stjäl tangenten från composern. Browsern reserverar inte Cmd+K på
  // localhost (bara Cmd+L för adressfältet) så ``preventDefault`` är
  // säker.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "k" && event.key !== "K") return;
      if (!event.metaKey && !event.ctrlKey) return;
      const target = event.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName;
        if (
          tagName === "INPUT" ||
          tagName === "TEXTAREA" ||
          // ``SELECT`` skyddar ConsoleDrawer's projekt-väljare (samt
          // andra select:s i appen) — DiscoveryWizard hoppar redan
          // över SELECT i sin egen ⌘K-skip, så vi följer samma
          // mönster här för att inte stänga drawern mitt i ett val.
          tagName === "SELECT" ||
          target.isContentEditable
        ) {
          // Composern (FloatingChat / PromptBuilder) — låt tangenten gå
          // som vanlig text-edit istället för att toggla drawern.
          return;
        }
      }
      // Modal-guard: är konsolen STÄNGD och en annan modal öppen
      // (DiscoveryWizard, MoreInfoDialog, Verktyg, bygg-dialoger) ska ⌘K
      // inte öppna konsolen BAKOM den — det rycker upp en bakgrundspanel
      // mitt i kärnflödet. Stängda dialoger avmonteras, så närvaron av ett
      // [role="dialog"]/[aria-modal]-element = en öppen modal. När konsolen
      // själv är öppen hoppar vi över kontrollen så ⌘K alltid kan stänga den.
      if (!consoleOpenRef.current) {
        if (
          document.querySelector(
            '[role="dialog"], [role="alertdialog"], [aria-modal="true"]',
          )
        ) {
          return;
        }
      }
      event.preventDefault();
      setConsoleOpen((prev) => !prev);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // Aktuell runs- + project-input-state avgör om vi är i "builder-mode"
  // (= en prompt-genererad sajt är vald, follow-ups via FloatingChat är
  // möjliga) eller i pre-build-läget med hero + DiscoveryWizard.
  //
  // Vi följer EXAKT samma logik som PromptBuilder använder internt för
  // sin `followupReady`-flagga — annars riskerar vi att visa BuilderShell
  // för en sajt som backend faktiskt vägrar göra followup på.
  const builderTarget = useMemo(() => {
    if (!selectedRunId) return null;
    const selectedRun = runs.find((run) => run.runId === selectedRunId);
    if (
      selectedRun &&
      (!selectedRun.siteId || selectedRun.siteId === "unknown")
    ) {
      return null;
    }
    const targetSiteId =
      selectedRun?.siteId && selectedRun.siteId !== "unknown"
        ? selectedRun.siteId
        : selectedSiteId;
    if (!targetSiteId || targetSiteId === "unknown") return null;
    // Hostad vy: ett bygge som den här sessionen själv slutförde är ett
    // betrott followup-mål (B194) även innan per-sajt-historiken hunnit
    // refetchas — KV-indexet (B199 v2) fyller listorna strax efter.
    if (hostedBanner && sessionBuiltRuns.get(selectedRunId) === targetSiteId) {
      return { siteId: targetSiteId };
    }
    const targetInput = projectInputs.find(
      (input) => input.siteId === targetSiteId,
    );
    if (targetInput?.source !== "prompt-inputs") return null;
    return { siteId: targetSiteId };
  }, [
    selectedRunId,
    runs,
    selectedSiteId,
    projectInputs,
    hostedBanner,
    sessionBuiltRuns,
  ]);

  const builderActive = builderTarget !== null;

  function handleBuildDone(
    runId: string,
    outcome: PromptBuildOutcome,
    siteId?: string,
    visibleEffect?: FollowupVisibleEffect,
  ) {
    // Kom ihåg lyckade byggen i sessionen så hostad vy kan aktivera
    // builder-läget trots tomma runs/projectInputs (se sessionBuiltRuns).
    // OBS: follow-ups via BuilderShell skickar siteId=undefined (löses lokalt
    // via runs-listan, som hostat alltid är tom) — fall tillbaka på
    // selectedSiteId, som i builder-läget är den aktiva sajten. Utan
    // fallbacken tappade hostade följdprompter builder-läget efter rebuild.
    const sessionSiteId =
      siteId && siteId !== "unknown" ? siteId : selectedSiteId;
    if (outcome !== "failed" && sessionSiteId && sessionSiteId !== "unknown") {
      setSessionBuiltRuns((prev) => {
        const next = new Map(prev);
        next.set(runId, sessionSiteId);
        return next;
      });
    }
    // Bygget landade — visa toast så operatören ser status även om
    // FloatingChat eller PromptBuilder inte är synlig (t.ex. på liten
    // skärm där hero scrollats ur sikte). FloatingChat visar fortfarande
    // sin egen rad med detaljer; toasten är en kort sammanfattning.
    //
    // Ärlighet (dialog-vägen, 2026-06-09): ``visibleEffect`` bär den
    // granulära signal som FloatingChat redan har. En follow-up som byggde
    // en ny version UTAN synlig effekt (mount-only section_add) eller en
    // ren no-op får INTE samma gröna "klart" som en verklig ändring —
    // annars upprepar dialog-toasten exakt den falska success vi tog bort i
    // FloatingChat. ``visible``/``unknown`` (init + äldre payloads) behåller
    // det neutrala success-beteendet.
    if (outcome === "ok") {
      if (visibleEffect === "registered") {
        toast.show({
          variant: "info",
          title: "Ändringen registrerades",
          description:
            "Den nya versionen byggdes, men ändringen syns inte i previewen ännu — sektionen monteras men renderas inte automatiskt på sidan.",
        });
      } else if (visibleEffect === "none") {
        toast.show({
          variant: "info",
          title: "Ingen synlig ändring",
          description: `Bygget gick igenom (${runId}) men ingen synlig ändring landade i previewen.`,
        });
      } else {
        toast.show({
          variant: "success",
          description: `Bygget klart för ${runId}.`,
        });
      }
    } else if (outcome === "degraded") {
      toast.show({
        variant: "warning",
        title: "Bygget klart med varning",
        description: `Run ${runId} levererade mock- eller degraded-resultat. Se Quality Gate i Inspector.`,
      });
    } else if (outcome === "failed") {
      toast.show({
        variant: "error",
        title: "Bygget misslyckades",
        description: `Run ${runId} kunde inte slutföras. Försök igen eller iterera från en tidigare version.`,
      });
    }

    // B6: om operatören aktivt lämnat den här buildens mål-vy mellan
    // start och completion (Ny sajt eller annan run vald) får vi inte
    // rycka tillbaka selectedRunId/selectedSiteId. Vi uppdaterar bara
    // history-listan så den färdiga runen finns i ConsoleDrawer.
    if (userNavigatedAwayRef.current) {
      userNavigatedAwayRef.current = false;
      setStatusText(headerStatusForOutcome(runId, outcome));
      void fetchRuns(hostedBanner ? selectedSiteId : null)
        .then((data) =>
          applyRunsData(data, {
            selectedRunId,
            selectedSiteId,
          }),
        )
        .catch((error) => {
          const message =
            error instanceof Error
              ? error.message
              : "Kunde inte uppdatera runs.";
          setStatusText(message);
          toast.show({
            variant: "warning",
            title: "Kunde inte uppdatera historiken",
            description: message,
          });
        });
      return;
    }

    setSelectedRunId(runId);
    const effectiveSiteId =
      siteId && siteId !== "unknown" ? siteId : selectedSiteId;
    if (siteId && siteId !== "unknown") {
      setSelectedSiteId(siteId);
    }
    setStatusText(headerStatusForOutcome(runId, outcome));
    void fetchRuns(hostedBanner ? effectiveSiteId : null)
      .then((data) =>
        applyRunsData(data, {
          selectedRunId: runId,
          selectedSiteId: effectiveSiteId,
        }),
      )
      .catch((error) => {
        const message =
          error instanceof Error ? error.message : "Kunde inte uppdatera runs.";
        setStatusText(message);
        toast.show({
          variant: "warning",
          title: "Kunde inte uppdatera historiken",
          description: message,
        });
      });
  }

  return (
    <DevicePresetProvider>
      {/* Preview-inspector: delar peka-i-previewn-state mellan ViewerPanel
        (overlay + element-karta) och builder-dialogerna (platsval). */}
      <PreviewInspectorProvider>
        <main className="bg-background relative h-[100dvh] w-full overflow-hidden">
          <SiteHeader
            onOpenConsole={() => setConsoleOpen(true)}
            // Dölj brand-bubblan i builder-läget — den ligger ovanpå
            // preview-iframens vänsterkant och stör operatörens
            // granskning av designen. Konsol-knappen i höger hörn
            // behålls så snabb-access till run-historik fortfarande
            // är ett enkelt klick.
            hideBrand={builderActive}
          />

          {hostedBanner ? <HostedNoticeBanner message={hostedBanner} /> : null}

          <ErrorBoundary area="Förhandsvisningen" className="h-full w-full">
            {/* C4: preview-POST:en går mot /api/preview/<siteId> medan runId
            driver fil-/StackBlitz-fallbacken. Project Input-väljaren i
            ConsoleDrawer kan sätta selectedSiteId UTAN att rensa
            selectedRunId → siteId och runId pekade då på olika sajter och
            previewen startade fel .generated/<siteId>/. runSiteId är den
            valda runens faktiska siteId (eller null när ingen run är vald),
            så vi låter den vinna när en run är aktiv och faller tillbaka på
            picker-sajten i hero/pre-build-läget. I normalfallet (run vald via
            selectRunAndSyncSiteId/handleBuildDone) är de redan identiska. */}
            <ViewerPanel
              runId={selectedRunId}
              siteId={runSiteId ?? selectedSiteId}
              isBuilding={building}
              buildStage={buildStage}
            />
          </ErrorBoundary>

          {/* Network-failure UX: visas bara om initial /api/runs failade
          OCH operatören ännu inte kommit in i builder-läget (då har vi
          redan en run och kan jobba mot den lokalt). Cardet ligger
          centrerat över hero-ytan så det syns även när PromptBuilder är
          dold. Retry-knappen anropar samma loader som useEffect:en. */}
          {runsLoadError && !runsLoading && !builderActive ? (
            <RunsLoadErrorCard
              message={runsLoadError}
              onRetry={() => {
                setRunsLoading(true);
                void loadRuns();
              }}
            />
          ) : null}

          {/* Prompt-rutan döljs visuellt medan bygget pågår (BuildProgressCard
          tar över hero-ytan) OCH när builder-mode är aktivt (då tar
          FloatingChat över follow-up-flödet). Vi får ABSOLUT inte
          unmounta komponenten under bygget — den äger fetch-promise:n
          mot /api/prompt och setTimeout som flyttar stage `thinking`→
          `building`. B7 i scout-review 2026-05-24: komponenten hålls
          nu alltid mountad även när builder-mode är aktivt. Tidigare
          conditional unmount → remount under follow-up återställde
          stage till "idle" och kraschade build-progress-cardet. */}
          <ErrorBoundary area="Prompt-rutan">
            <PromptBuilder
              isBusy={building}
              runs={runs}
              projectInputs={projectInputs}
              selectedRunId={selectedRunId}
              selectedSiteId={selectedSiteId}
              onBuildStart={() => setBuilding(true)}
              onBuildEnd={() => setBuilding(false)}
              // Rapportera stage endast när PromptBuilder är "owner" av
              // bygget. I builder-mode driver FloatingChat follow-ups så
              // PromptBuilder:s interna stage-effekt får inte skriva över
              // buildStage med "idle" eller en stale tidigare success.
              onStageChange={builderActive ? undefined : setBuildStage}
              hidden={building || builderActive}
              onBuildDone={handleBuildDone}
            />
          </ErrorBoundary>

          {/* Builder-shell: floating draggable chat + dolt verktygsmeny.
          Visas så snart vi har en prompt-genererad run vald. Pre-build
          eller exempel-only-runs faller tillbaka till PromptBuilder
          ovan. FloatingChat skickar follow-up-prompts till /api/prompt
          med mode:"followup" och delar build-state med page.tsx så
          ViewerPanel:s BuildProgressCard fortsätter fungera under
          rebuild-cykeln. */}
          {builderActive && builderTarget ? (
            <ErrorBoundary area="Builder">
              <BuilderShell
                siteId={builderTarget.siteId}
                runId={selectedRunId}
                isBuilding={building}
                pendingBuild={pendingBuild}
                onPendingBuildBegin={beginPending}
                onPendingBuildClear={clearPending}
                pendingBaseRunId={pendingBaseRunId}
                onSetPendingBaseRunId={setPendingBaseRunId}
                // Driv buildStage under follow-ups så ViewerPanel:s
                // BuildProgressCard visar rätt steg. I builder-läge är
                // PromptBuilder:s egen onStageChange avstängd, så detta är
                // enda källan till buildStage tills bygget landar.
                onStageChange={setBuildStage}
                onBuildStart={() => setBuilding(true)}
                onBuildEnd={() => {
                  setBuilding(false);
                  // Säkerhetsnet: om onPendingBuildClear inte hann kallas
                  // (t.ex. dialog som glömde rensa pending) tar vi bort den
                  // här så vi aldrig får orphan-pending-rader.
                  clearPending();
                  // OBS: pendingBaseRunId rensas INTE här. onBuildEnd kallas
                  // även när bygget misslyckas, och en operatör som klickar
                  // "Försök igen" på error-bubblan vill iterera från samma
                  // base-version — inte fall tillbaka till latest. Vi rensar
                  // istället i handleBuildDone (success-path), via TTL-guarden
                  // i usePendingBuild (5 min) och via "Iterera"-toggle.
                }}
                onBuildDone={(runId, outcome, visibleEffect) => {
                  // Bygget producerade en riktig version (ok/degraded) → iterationen
                  // konsumerades och ska inte oavsiktligt återanvändas av nästa
                  // fri-text-prompt. Vid ``failed`` BEHÅLLER vi base-run:en: error-
                  // bubblans "Försök igen" ska iterera från samma bas, inte falla
                  // tillbaka till latest (matchar onBuildEnd-kommentaren ovan).
                  // Signaturen i BuilderShell skickar inte siteId vidare; det löser
                  // handleBuildDone själv via runs-listan när den re-fetchar
                  // (hostat via selectedSiteId-fallbacken i sessionBuiltRuns).
                  // ``visibleEffect`` (dialog-vägen) trådas vidare så studio-toasten
                  // blir ärlig om mount-only/no-op-byggen.
                  if (outcome !== "failed") setPendingBaseRunId(null);
                  handleBuildDone(runId, outcome, undefined, visibleEffect);
                }}
                onNewSite={() => {
                  // Återgår till pre-build-läget: rensar både selectedRunId
                  // och buildStage så hero + DiscoveryWizard tar över igen.
                  // Markera att operatören navigerat bort om ett bygge pågår
                  // så handleBuildDone inte rycker tillbaka selectedRunId.
                  if (building) userNavigatedAwayRef.current = true;
                  setSelectedRunId(null);
                  setBuildStage("idle");
                  setStatusText(
                    "Beskriv en ny sajt nedan så bygger vi den åt dig.",
                  );
                }}
                onOpenConsole={() => setConsoleOpen(true)}
                onOpenHistory={() => setConsoleOpen(true)}
              />
            </ErrorBoundary>
          ) : null}

          <ConsoleDrawer
            open={consoleOpen}
            onOpenChange={setConsoleOpen}
            runs={runs}
            projectInputs={projectInputs}
            selectedSiteId={selectedSiteId}
            onSelectSiteId={setSelectedSiteId}
            selectedRunId={selectedRunId}
            onSelectRunId={selectRunAndSyncSiteId}
            runSiteId={runSiteId}
            runSiteIdUnknown={runSiteIdUnknown}
            isBuilding={building}
            runsLoading={runsLoading}
            statusText={statusText}
          />
        </main>
      </PreviewInspectorProvider>
    </DevicePresetProvider>
  );
}

// Hostad Vercel-vy: en lugn, icke-blockerande info-banner högst upp som ärligt
// beskriver det hostade driftläget. Visas bara när /api/runs svarat med en
// hostedBanner (VERCEL=1) — aldrig lokalt.
function HostedNoticeBanner({ message }: { message: string }) {
  return (
    <div
      role="status"
      className="pointer-events-none fixed inset-x-0 top-16 z-30 mx-auto flex w-full max-w-2xl justify-center px-4"
    >
      <div className="border-border bg-card/95 text-muted-foreground pointer-events-auto flex items-start gap-2 rounded-xl border px-3 py-2 text-[12px] leading-relaxed shadow-sm backdrop-blur">
        <Cloud
          className="text-muted-foreground mt-0.5 h-4 w-4 shrink-0"
          aria-hidden
        />
        <p>{message}</p>
      </div>
    </div>
  );
}

// Visas i hero-ytan när initial /api/runs failade. Använder `role="alert"`
// så skärmläsare läser upp den direkt vid mount. Retry-knappen anropar
// `loadRuns()` igen och rensar felet om det lyckas.
function RunsLoadErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="pointer-events-none fixed inset-x-0 top-24 z-30 mx-auto flex w-full max-w-md justify-center px-4"
    >
      <div className="border-destructive/40 bg-card pointer-events-auto flex flex-col gap-3 rounded-2xl border p-4 shadow-md">
        <div className="flex items-center gap-2">
          <WifiOff className="text-destructive h-4 w-4 shrink-0" aria-hidden />
          <h2 className="text-foreground text-sm font-semibold">
            Kunde inte ladda runs
          </h2>
        </div>
        <p className="text-muted-foreground text-[13px] leading-relaxed">
          Servern svarade inte. Kontrollera att backend kör (
          <code className="bg-muted/60 rounded px-1 py-0.5 font-mono text-[11px]">
            npm run dev
          </code>
          ) och försök igen.
        </p>
        <pre className="bg-muted/60 text-muted-foreground max-h-20 overflow-auto rounded-md p-2 font-mono text-[11px] leading-snug">
          {message}
        </pre>
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw aria-hidden />
            Försök igen
          </Button>
        </div>
      </div>
    </div>
  );
}
