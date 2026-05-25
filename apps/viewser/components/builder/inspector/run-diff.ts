/**
 * run-diff.ts — pure diff-logik för att jämföra två run-artefakter.
 *
 * Används av Versions-tab:en i Site Inspector för att svara på
 * operatörens fråga "vad ändrades mellan v3 och v4?". Bygger på
 * artefakt-bundlen som `/api/runs/[runId]/artifacts` returnerar
 * (RunArtefactBundle i lib/runs.ts).
 *
 * Filen är medvetet React-fri och beroende-fri — det gör den enkel
 * att testa med fixture-data och återanvända i andra ytor (t.ex.
 * en framtida "pre-publish diff"-vy eller en agent-tool).
 *
 * ALIGNMENT: alla läsningar är defensiva mot saknade fält (äldre runs
 * har inte alla artefakter; se readArtefactOrNull i lib/runs.ts).
 * Vi gissar aldrig fram data — saknat fält blir `null` i diff-output
 * så UI:t kan visa "saknas i äldre run" istället för att hitta på.
 */

export type RunArtefactBundleLike = {
  runId: string;
  buildResult: Record<string, unknown> | null;
  qualityResult: Record<string, unknown> | null;
  repairResult: Record<string, unknown> | null;
  siteBrief: Record<string, unknown> | null;
  sitePlan: Record<string, unknown> | null;
  missingArtefacts: string[];
};

/**
 * En enskild scalar-ändring mellan A och B. `null` på endera sidan
 * = fältet saknas i den runen. `equal` = båda har samma värde
 * (renderas inte i UI:t som "ändring", men exponeras så caller kan
 * t.ex. lista "lika"-fält i en debug-vy om de vill).
 */
export type ScalarChange = {
  before: string | null;
  after: string | null;
  equal: boolean;
};

export type RunDiff = {
  runIdA: string;
  runIdB: string;
  /** Site plan-fält som styr Variant + Starter pipeline-valen. */
  scaffold: ScalarChange;
  variant: ScalarChange;
  starter: ScalarChange;
  /** Route-paths som finns i A vs B. */
  routesAdded: string[];
  routesRemoved: string[];
  routesEqual: boolean;
  /** Site brief tone-tags. */
  toneAdded: string[];
  toneRemoved: string[];
  /** Site brief requested capabilities. */
  capabilitiesAdded: string[];
  capabilitiesRemoved: string[];
  /** Quality Gate-status före → efter. */
  qualityStatus: ScalarChange;
  /** Build-status (övergripande pipeline-status). */
  buildStatus: ScalarChange;
};

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string" && item.length > 0)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

/**
 * Diff två strängar; markerar `equal: true` när båda har samma
 * non-empty värde. Saknad data blir `null` så caller kan visa
 * "saknas i äldre run".
 */
function diffScalar(before: unknown, after: unknown): ScalarChange {
  const a = readString(before);
  const b = readString(after);
  return {
    before: a,
    after: b,
    equal: a !== null && b !== null && a === b,
  };
}

/**
 * Plocka route-paths från site-plan.json (routePlan[].path). Faller
 * tillbaka till build-result.json (routes[]) för pre-Sprint-3A runs
 * som inte hade site-plan. Dedupar — ChipDiffRow använder path som
 * React-key, så dubletter (illa-formade site-plans) skulle annars
 * trigga key-collision-warnings.
 */
function readRoutes(bundle: RunArtefactBundleLike): string[] {
  const plan = bundle.sitePlan;
  if (plan && Array.isArray(plan.routePlan)) {
    const fromPlan = (plan.routePlan as unknown[])
      .map((entry) => {
        if (!entry || typeof entry !== "object") return null;
        const path = (entry as Record<string, unknown>).path;
        return typeof path === "string" && path.length > 0 ? path : null;
      })
      .filter((path): path is string => path !== null);
    if (fromPlan.length > 0) return Array.from(new Set(fromPlan));
  }
  const build = bundle.buildResult;
  if (build && Array.isArray(build.routes)) {
    return Array.from(new Set(readStringArray(build.routes)));
  }
  return [];
}

function readToneTags(bundle: RunArtefactBundleLike): string[] {
  const brief = bundle.siteBrief;
  if (!brief) return [];
  if (Array.isArray(brief.tone)) return readStringArray(brief.tone);
  if (Array.isArray(brief.toneTags)) return readStringArray(brief.toneTags);
  return [];
}

function readCapabilities(bundle: RunArtefactBundleLike): string[] {
  const brief = bundle.siteBrief;
  if (!brief) return [];
  if (Array.isArray(brief.requestedCapabilities)) {
    return readStringArray(brief.requestedCapabilities);
  }
  if (Array.isArray(brief.requested_capabilities)) {
    return readStringArray(brief.requested_capabilities);
  }
  return [];
}

function readScaffold(bundle: RunArtefactBundleLike): string | null {
  const plan = bundle.sitePlan;
  if (plan && typeof plan.scaffoldId === "string") return plan.scaffoldId;
  return null;
}

function readVariant(bundle: RunArtefactBundleLike): string | null {
  const plan = bundle.sitePlan;
  if (plan && typeof plan.variantId === "string") return plan.variantId;
  return null;
}

function readStarter(bundle: RunArtefactBundleLike): string | null {
  const plan = bundle.sitePlan;
  if (plan && typeof plan.starterId === "string") return plan.starterId;
  return null;
}

function readQualityStatus(bundle: RunArtefactBundleLike): string | null {
  const quality = bundle.qualityResult;
  if (quality && typeof quality.status === "string") return quality.status;
  return null;
}

function readBuildStatus(bundle: RunArtefactBundleLike): string | null {
  const build = bundle.buildResult;
  if (build && typeof build.status === "string") return build.status;
  return null;
}

/**
 * Beräkna set-diff. Returnerar (added = i B men inte A, removed =
 * i A men inte B). Bevarar källordning från B respektive A så
 * UI-listan är förutsägbar.
 */
function setDiff(
  before: readonly string[],
  after: readonly string[],
): { added: string[]; removed: string[] } {
  const beforeSet = new Set(before);
  const afterSet = new Set(after);
  return {
    added: after.filter((item) => !beforeSet.has(item)),
    removed: before.filter((item) => !afterSet.has(item)),
  };
}

/**
 * Beräkna full diff mellan två run-bundlar. Pure & deterministisk —
 * samma input ⇒ samma output. Hanterar saknade artefakter defensivt
 * (returnerar tomma listor / null-scalar-changes så UI:t inte kraschar
 * på äldre run-shapes).
 */
export function computeRunDiff(
  a: RunArtefactBundleLike,
  b: RunArtefactBundleLike,
): RunDiff {
  const routesA = readRoutes(a);
  const routesB = readRoutes(b);
  const routesDiff = setDiff(routesA, routesB);
  const toneA = readToneTags(a);
  const toneB = readToneTags(b);
  const toneDiff = setDiff(toneA, toneB);
  const capabilitiesA = readCapabilities(a);
  const capabilitiesB = readCapabilities(b);
  const capabilitiesDiff = setDiff(capabilitiesA, capabilitiesB);

  return {
    runIdA: a.runId,
    runIdB: b.runId,
    scaffold: diffScalar(readScaffold(a), readScaffold(b)),
    variant: diffScalar(readVariant(a), readVariant(b)),
    starter: diffScalar(readStarter(a), readStarter(b)),
    routesAdded: routesDiff.added,
    routesRemoved: routesDiff.removed,
    routesEqual:
      routesDiff.added.length === 0 && routesDiff.removed.length === 0,
    toneAdded: toneDiff.added,
    toneRemoved: toneDiff.removed,
    capabilitiesAdded: capabilitiesDiff.added,
    capabilitiesRemoved: capabilitiesDiff.removed,
    qualityStatus: diffScalar(readQualityStatus(a), readQualityStatus(b)),
    buildStatus: diffScalar(readBuildStatus(a), readBuildStatus(b)),
  };
}

/**
 * Bygger en kort prosa-sammanfattning av en diff för rad-listor
 * och summering. Returnerar `"Inga ändringar"` när allt är lika.
 *
 * Exempel-output:
 *   "Variant: warm-craft → nordic-trust · Routes: +1 −0"
 *   "Routes: +2 −1 · Capabilities: +1"
 */
export function formatDiffSummary(diff: RunDiff): string {
  const parts: string[] = [];
  if (!diff.variant.equal && (diff.variant.before || diff.variant.after)) {
    parts.push(
      `Variant: ${diff.variant.before ?? "?"} → ${diff.variant.after ?? "?"}`,
    );
  }
  if (!diff.scaffold.equal && (diff.scaffold.before || diff.scaffold.after)) {
    parts.push(
      `Scaffold: ${diff.scaffold.before ?? "?"} → ${diff.scaffold.after ?? "?"}`,
    );
  }
  if (!diff.starter.equal && (diff.starter.before || diff.starter.after)) {
    parts.push(
      `Starter: ${diff.starter.before ?? "?"} → ${diff.starter.after ?? "?"}`,
    );
  }
  if (!diff.routesEqual) {
    parts.push(
      `Routes: +${diff.routesAdded.length} −${diff.routesRemoved.length}`,
    );
  }
  if (diff.toneAdded.length > 0 || diff.toneRemoved.length > 0) {
    parts.push(`Tone: +${diff.toneAdded.length} −${diff.toneRemoved.length}`);
  }
  if (
    diff.capabilitiesAdded.length > 0 ||
    diff.capabilitiesRemoved.length > 0
  ) {
    parts.push(
      `Capabilities: +${diff.capabilitiesAdded.length} −${diff.capabilitiesRemoved.length}`,
    );
  }
  if (
    !diff.qualityStatus.equal &&
    (diff.qualityStatus.before || diff.qualityStatus.after)
  ) {
    parts.push(
      `Quality: ${diff.qualityStatus.before ?? "?"} → ${diff.qualityStatus.after ?? "?"}`,
    );
  }
  if (
    !diff.buildStatus.equal &&
    (diff.buildStatus.before || diff.buildStatus.after)
  ) {
    parts.push(
      `Build: ${diff.buildStatus.before ?? "?"} → ${diff.buildStatus.after ?? "?"}`,
    );
  }
  return parts.length === 0 ? "Inga ändringar" : parts.join(" · ");
}
