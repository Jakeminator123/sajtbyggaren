/**
 * run-change-set — härled en EXAKT change-set för en follow-up-build
 * genom att diffa den nya runens artefakter mot föregående run.
 *
 * Detta stänger UI-gapet som Jakob flaggade (2026-06-02): listan
 * "Troligen ändrat" i FloatingChat var en prompt-heuristik. Här
 * producerar vi i stället bekräftade deltas (routes som lades till/togs
 * bort, variant-byten) ur artefakter som redan ligger under `data/runs/`.
 *
 * Hårda begränsningar (Christopher-lane efter PR):
 *   - Ingen `build_site.py`-ändring. Vi läser bara befintliga artefakter.
 *   - Ingen ny adapter. Vi återanvänder `readRunArtefacts` + den redan
 *     pure & beroende-fria `computeRunDiff` (run-diff.ts).
 *   - Aldrig en throw mot kallaren — fel landar som `null` så
 *     `/api/prompt` faller tillbaka på prompt-heuristiken.
 *   - Copy-direktiv (företagsnamn/tagline) lever kvar i sin egen
 *     `appliedCopyDirectives`-väg och dupliceras inte hit.
 */

import { computeRunDiff } from "@/components/builder/inspector/run-diff";
import type { RunChangeSet } from "@/lib/build-changes";
import { listRuns, readRunArtefacts, type RunArtefactBundle } from "@/lib/runs";

const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;

function readSiteId(bundle: RunArtefactBundle): string | undefined {
  const value = bundle.buildResult?.siteId;
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function readVersion(bundle: RunArtefactBundle): number | null {
  const value = bundle.buildResult?.version;
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

/**
 * Hitta runen som follow-upen itererade från. Prioritetsordning:
 *   1. Explicit `baseRunId` (operatören klickade "Iterera från denna").
 *   2. Runen för samma siteId med version === currentVersion - 1.
 *   3. Senaste övriga run för samma siteId (fallback när versionsfältet
 *      saknas på äldre runs).
 */
async function resolvePreviousRunId(
  runId: string,
  current: RunArtefactBundle,
  baseRunId: string | undefined,
): Promise<string | null> {
  if (baseRunId && baseRunId !== runId && RUN_ID_PATTERN.test(baseRunId)) {
    return baseRunId;
  }
  const siteId = readSiteId(current);
  if (!siteId) return null;

  // Bounded fönster — listRuns slice:ar före JSON-läsning (B72-lock), så
  // detta förblir O(limit) oavsett hur många runs som ligger på disk.
  const runs = await listRuns(25, { siteId });
  const candidates = runs.filter((meta) => meta.runId !== runId);
  if (candidates.length === 0) return null;

  const currentVersion = readVersion(current);
  if (currentVersion !== null) {
    const byVersion = candidates.find(
      (meta) => meta.version === currentVersion - 1,
    );
    if (byVersion) return byVersion.runId;
  }
  // listRuns returnerar nyast först → första kandidaten är senaste övriga.
  return candidates[0]?.runId ?? null;
}

/**
 * Beräkna en exakt change-set för `runId` mot föregående run.
 * Returnerar `null` när:
 *   - ingen föregående run hittas (typiskt v1 / init-build), eller
 *   - diffen inte innehåller någon route-/variant-delta (då räcker
 *     prompt-heuristiken — copy-byten täcks av appliedCopyDirectives).
 */
export async function readRunChangeSet(
  runId: string,
  options: { baseRunId?: string } = {},
): Promise<RunChangeSet | null> {
  let current: RunArtefactBundle;
  try {
    current = await readRunArtefacts(runId);
  } catch {
    return null;
  }

  const previousRunId = await resolvePreviousRunId(
    runId,
    current,
    options.baseRunId,
  );
  if (!previousRunId) return null;

  let previous: RunArtefactBundle;
  try {
    previous = await readRunArtefacts(previousRunId);
  } catch {
    return null;
  }

  // computeRunDiff(a, b): a = före, b = efter. RunArtefactBundle är
  // strukturellt kompatibel med RunArtefactBundleLike.
  const diff = computeRunDiff(previous, current);
  const variantChanged =
    !diff.variant.equal && Boolean(diff.variant.before || diff.variant.after);
  const hasExactDelta =
    diff.routesAdded.length > 0 ||
    diff.routesRemoved.length > 0 ||
    variantChanged;
  if (!hasExactDelta) return null;

  return {
    previousRunId,
    routesAdded: diff.routesAdded,
    routesRemoved: diff.routesRemoved,
    variantBefore: variantChanged ? diff.variant.before : null,
    variantAfter: variantChanged ? diff.variant.after : null,
  };
}
