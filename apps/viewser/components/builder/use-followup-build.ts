"use client";

import { useCallback, useState } from "react";

import {
  classifyBuildStatus,
  type PromptBuildOutcome,
} from "@/components/prompt-builder";

/**
 * Delad hook som alla builder-dialoger använder för att skicka en
 * follow-up-prompt till `/api/prompt` (mode: "followup"). Den
 * kapslar in fetch, error-handling och outcome-mapping så varje
 * dialog kan fokusera på sin egen UI istället för att duplicera
 * build-orchestration.
 *
 * FloatingChat har sin egen variant av samma flöde (med message-
 * tråd-state). Den lever kvar separat eftersom FloatingChat behöver
 * pending-meddelanden i en synlig logg, medan dialogerna stänger
 * sig själva när bygget startar och rapporterar via toast/inline-
 * error vid fel.
 *
 * Returnerar `{ runFollowup, isBusy, error, clearError }`.
 *
 * `runFollowup(prompt)` triggar onBuildStart innan fetchen, anropar
 * onBuildDone(runId, outcome) när bygget är klart, och garanterar
 * onBuildEnd i finally så page.tsx alltid får ren state oavsett
 * lyckat eller misslyckat bygge.
 */

/**
 * Ärlighets-signal för ett dialog-bygge — speglar den granulära
 * visible-effect-info som FloatingChat redan konsumerar
 * (``build-result.json:appliedVisibleEffect`` + apply-bryggans
 * ``previewShouldRefresh``). Trådas via ``onBuildDone`` upp till
 * studio-toasten så dialogerna aldrig säger "klart" när ingen synlig
 * ändring landade.
 *
 *   - ``visible``    — en synlig ändring landade (preview ska laddas om).
 *   - ``registered`` — en version skrevs/monterades men syns inte än
 *     (mount-only section_add, t.ex. galleri/priser).
 *   - ``none``       — bygget gick igenom men motorn rapporterade no-op.
 *   - ``unknown``    — inga signaler i svaret (äldre payload/init) →
 *     toasten faller tillbaka på det neutrala "klart"-beteendet.
 */
export type FollowupVisibleEffect = "visible" | "registered" | "none" | "unknown";

/**
 * Delad callback-typ för alla bygg-utlösande ytor (dialoger + BuilderShell).
 * ``visibleEffect`` är optionellt så befintliga 2-arg-anropare (FloatingChat,
 * init-vägen) fortsätter typchecka oförändrat.
 */
export type OnFollowupBuildDone = (
  runId: string,
  outcome: PromptBuildOutcome,
  visibleEffect?: FollowupVisibleEffect,
) => void;

type FollowupBuildOptions = {
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: OnFollowupBuildDone;
  /**
   * C2 — globalt bygg-lås. Page.tsx äger ett `building`-flagga som är
   * sant så länge NÅGOT bygge pågår (FloatingChat eller en annan dialog).
   * Varje dialog har bara sin egen lokala `isBusy` och vet inget om
   * syskon-byggen — utan denna kan två öppna dialoger (eller en dialog
   * + FloatingChat) starta parallella byggen mot samma siteId och racea
   * om versionsräkningen/preview. Vi avvisar `runFollowup` om ett globalt
   * bygge redan kör. Valfri för bakåtkompatibilitet (default: ingen extra
   * spärr utöver lokal `isBusy`).
   */
  isBuilding?: boolean;
  /**
   * C1 — "Iterera från denna". När operatören pinnat en historisk version
   * i Versions-tab vill nästa bygge — oavsett om det triggas från
   * FloatingChat ELLER en dialog (design/färg/bild/scrape) — grenas från
   * det versionssnapshotet, inte från senaste. FloatingChat skickar redan
   * `baseRunId` i sin egen fetch; dialogerna gjorde det inte, så en
   * pinnad iteration tappades tyst när operatören bytte t.ex. färg.
   * `null`/utelämnad = bygg från senaste (oförändrat beteende).
   */
  baseRunId?: string | null;
};

type PromptApiResponse = {
  runId?: string;
  siteId?: string;
  version?: number | null;
  buildStatus?: string | null;
  briefSource?: string | null;
  // Samma granulära ärlighets-signaler som FloatingChat läser (defensivt,
  // typas som Record så fält-drift aldrig kraschar dialog-vägen):
  //   - buildResult.appliedVisibleEffect (B155, auktoritativ no-op-flagga)
  //   - bridge.{applied, previewShouldRefresh} (OpenClaw apply-utfallet)
  // Saknas båda (äldre payload/init) → readFollowupVisibleEffect → "unknown".
  buildResult?: Record<string, unknown>;
  bridge?: Record<string, unknown>;
  error?: string;
};

export type RunFollowupResult =
  | {
      ok: true;
      runId: string;
      version: number | null;
      outcome: PromptBuildOutcome;
      visibleEffect: FollowupVisibleEffect;
    }
  | { ok: false; error: string };

/**
 * Härleder ``FollowupVisibleEffect`` ur /api/prompt-svaret med samma
 * defensiva läsning som ``extractAppliedVisibleEffect`` +
 * ``extractOpenClawBridge`` i ``floating-chat.tsx``. En positiv synlig
 * signal (``appliedVisibleEffect===true`` ELLER ``previewShouldRefresh===true``)
 * vinner; därefter "monterad men ej synlig" (bryggan applied men ingen
 * refresh); därefter ärlig no-op; annars "unknown".
 */
function readFollowupVisibleEffect(
  payload: PromptApiResponse,
): FollowupVisibleEffect {
  let bridgeApplied: boolean | null = null;
  let bridgeRefresh: boolean | null = null;
  const bridge = payload.bridge;
  if (bridge && typeof bridge === "object") {
    const obj = bridge as Record<string, unknown>;
    if (typeof obj.applied === "boolean") bridgeApplied = obj.applied;
    if (typeof obj.previewShouldRefresh === "boolean") {
      bridgeRefresh = obj.previewShouldRefresh;
    }
  }

  let appliedVisibleEffect: boolean | null = null;
  const buildResult = payload.buildResult;
  if (buildResult && typeof buildResult === "object") {
    const value = (buildResult as Record<string, unknown>).appliedVisibleEffect;
    if (typeof value === "boolean") appliedVisibleEffect = value;
  }

  if (appliedVisibleEffect === true || bridgeRefresh === true) return "visible";
  if (bridgeApplied === true) return "registered";
  if (appliedVisibleEffect === false) return "none";
  return "unknown";
}

export function useFollowupBuild({
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
}: FollowupBuildOptions) {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const runFollowup = useCallback(
    async (prompt: string): Promise<RunFollowupResult> => {
      const trimmed = prompt.trim();
      if (!trimmed) {
        const msg = "Prompten är tom.";
        setError(msg);
        return { ok: false, error: msg };
      }
      if (isBusy || isBuilding) {
        // isBusy = denna dialogs eget bygge; isBuilding = ett globalt
        // bygge (annan dialog/FloatingChat). Båda ska blockera.
        const msg = "Ett bygge pågår redan.";
        setError(msg);
        return { ok: false, error: msg };
      }
      if (!siteId) {
        const msg = "Ingen aktiv sajt.";
        setError(msg);
        return { ok: false, error: msg };
      }

      setIsBusy(true);
      setError(null);
      onBuildStart();
      try {
        const response = await fetch("/api/prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: trimmed,
            mode: "followup",
            siteId,
            // C1: opt-in baseRunId — samma kontrakt som FloatingChat. Backend
            // (scripts/prompt_to_project_input.py --base-run-id) laddar
            // PI-snapshotet från den pinnade runen och versionsräkningen blir
            // max(latest, base) + 1. Utelämnas helt när ingen pin är aktiv.
            ...(baseRunId ? { baseRunId } : {}),
          }),
        });
        const payload = (await response.json()) as PromptApiResponse;
        if (!response.ok || !payload.runId) {
          const msg =
            payload.error ??
            `Prompt-anropet misslyckades (HTTP ${response.status})`;
          setError(msg);
          return { ok: false, error: msg };
        }
        const outcome = classifyBuildStatus(payload.buildStatus);
        const visibleEffect = readFollowupVisibleEffect(payload);
        onBuildDone(payload.runId, outcome, visibleEffect);
        return {
          ok: true,
          runId: payload.runId,
          version: payload.version ?? null,
          outcome,
          visibleEffect,
        };
      } catch (caught) {
        const msg = caught instanceof Error ? caught.message : "Okänt fel.";
        setError(msg);
        return { ok: false, error: msg };
      } finally {
        setIsBusy(false);
        onBuildEnd();
      }
    },
    [isBusy, isBuilding, baseRunId, siteId, onBuildStart, onBuildEnd, onBuildDone],
  );

  return { runFollowup, isBusy, error, clearError };
}
