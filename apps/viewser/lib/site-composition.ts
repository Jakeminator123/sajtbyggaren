/**
 * site-composition — härleder en "Projektinnehåll"-bild för en sajt ur
 * BEFINTLIGA källor (ingen ny lagring, inga nya artefakter):
 *
 *   - senaste runens artefakter (build-result.json + site-plan.json) ger
 *     version, scaffold/variant, routes och dossier-urvalet,
 *   - den genererade sajtens ``generated-files/package.json`` +
 *     ``generated-files/component-manifest.json`` ger dependencies och
 *     monterade UI-komponenter,
 *   - trace-eventet ``npm.install.dependency_drift`` (ADR 0056) är den
 *     auktoritativa källan för VILKA paket dossiers faktiskt lade till
 *     utöver starterns lockfile ("Tillagda paket"),
 *   - project-input ger företagsnamn/språk (lokalt från disk, hostat via
 *     run-state-pekarens blob-URL genom ``hostedProjectInputForSite``).
 *
 * Lokalt läses allt från ``data/runs/<runId>/`` + ``data/prompt-inputs/``;
 * hostat (VERCEL=1) återanvänds B199-kedjan: KV-indexet → versionens
 * run-artifacts.tar.gz → samma filer ur tarballen. Allt är ärligt
 * degraderande: en källa som saknas blir ``null`` ("okänt"), aldrig en
 * gissning. Dossier-attributionen för tillagda paket läser de
 * operatörskuraterade manifesten under ``packages/generation/orchestration/
 * dossiers/`` — finns de inte på disken (hostat) blir ``source`` null.
 */

import { promises as fs } from "node:fs";
import path from "node:path";

import {
  fetchHostedRunArtefactsTar,
  hostedProjectInputForSite,
  hostedRunArtefactBundle,
  listHostedRunsForSite,
} from "./hosted-run-history";
import { hostedRuntimeNotice } from "./hosted-python-runtime";
import {
  listRuns,
  readArtefactOrNull,
  readRunArtefacts,
  runDirFromId,
  type RunMeta,
} from "./runs";

export const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/** Dossier-id:n är operatörskuraterade slugs — samma form som siteId. */
const DOSSIER_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

export type SiteComposition = {
  siteId: string;
  /** Sajtens version (followup-räknaren) — null när okänd. */
  version: number | null;
  scaffoldId: string | null;
  variantId: string | null;
  starterId: string | null;
  language: string | null;
  companyName: string | null;
  /** Sidor ur site-plan (id + path); null = okänt (artefakt saknas). */
  routes: Array<{ id: string | null; path: string }> | null;
  /** Dossier-urvalet ur site-plan; null = okänt (artefakt saknas). */
  dossiers: Array<{
    id: string;
    status: "required" | "recommended" | "conditional" | "rejected";
    reason: string | null;
  }> | null;
  /** Monterade UI-komponenter (component-manifest); null = okänt. */
  components: string[] | null;
  /**
   * Dependencies ur den genererade package.json. ``base`` är starterns
   * paket; ``added`` är dossier-tillagda paket (ADR 0056) med ärlig
   * dossier-attribution (``source`` null när manifesten inte är läsbara,
   * t.ex. hostat). null = package.json kunde inte läsas.
   */
  dependencies: {
    base: Record<string, string>;
    added: Array<{ name: string; version: string; source: string | null }>;
  } | null;
  lastBuild: {
    runId: string;
    status: string;
    createdAt: string | null;
  } | null;
  /** Sätts hostat när en källa medvetet saknas (B199-degradering). */
  hostedNotice?: string;
};

function repoRoot(): string {
  // Spread gör sökvägen opak för Turbopacks statiska analys (samma trick
  // som lib/runs.ts) så repo-rot-läsningar inte viks till asset-referenser.
  const up = ["..", ".."];
  return path.resolve(process.cwd(), ...up);
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function intOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** routePlan ur site-plan.json → [{id, path}]; null när formen saknas. */
export function routesFromArtefacts(
  sitePlan: Record<string, unknown> | null,
  buildResult: Record<string, unknown> | null,
): SiteComposition["routes"] {
  const plan = sitePlan?.routePlan;
  if (Array.isArray(plan)) {
    const routes: Array<{ id: string | null; path: string }> = [];
    for (const item of plan) {
      const entry = recordOrNull(item);
      const routePath = stringOrNull(entry?.path);
      if (!routePath) continue;
      routes.push({ id: stringOrNull(entry?.id), path: routePath });
    }
    if (routes.length > 0) return routes;
  }
  // Äldre runs utan routePlan: build-result.routes är en ren path-lista.
  const built = buildResult?.routes;
  if (Array.isArray(built)) {
    const routes = built
      .filter((item): item is string => typeof item === "string" && item.length > 0)
      .map((routePath) => ({ id: null, path: routePath }));
    if (routes.length > 0) return routes;
  }
  return null;
}

/**
 * selectedDossiers ur site-plan.json → platt lista med status. Poster kan
 * vara strängar (required/recommended/conditional) eller objekt med
 * id+reason (rejected) — båda hanteras defensivt.
 */
export function dossiersFromSitePlan(
  sitePlan: Record<string, unknown> | null,
): SiteComposition["dossiers"] {
  const selected = recordOrNull(sitePlan?.selectedDossiers);
  if (!selected) return null;
  const statuses = ["required", "recommended", "conditional", "rejected"] as const;
  const out: NonNullable<SiteComposition["dossiers"]> = [];
  for (const status of statuses) {
    const bucket = selected[status];
    if (!Array.isArray(bucket)) continue;
    for (const item of bucket) {
      if (typeof item === "string" && item.trim()) {
        out.push({ id: item, status, reason: null });
        continue;
      }
      const entry = recordOrNull(item);
      const id = stringOrNull(entry?.id);
      if (!id) continue;
      out.push({ id, status, reason: stringOrNull(entry?.reason) });
    }
  }
  return out;
}

/** component-manifest.json → komponentnamn; null när manifestet saknas. */
export function componentsFromManifest(
  manifest: Record<string, unknown> | null,
): string[] | null {
  const list = manifest?.components;
  if (!Array.isArray(list)) return null;
  const names = list
    .map((item) => stringOrNull(recordOrNull(item)?.name))
    .filter((name): name is string => name !== null);
  return names;
}

/**
 * Parsar trace-eventet ``npm.install.dependency_drift`` (ADR 0056) ur
 * trace.ndjson-text. Eventets ``reason`` är "added: name@1.2.3, name@~4.5.6".
 * Returnerar en name→version-map; tom map = ingen drift (inga tillagda
 * paket), null = trace-texten saknas/oläsbar (ärligt okänt).
 */
export function addedDependenciesFromTrace(
  traceText: string | null,
): Map<string, string> | null {
  if (traceText === null) return null;
  const added = new Map<string, string>();
  for (const line of traceText.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.includes("dependency_drift")) continue;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(trimmed) as Record<string, unknown>;
    } catch {
      continue;
    }
    if (parsed.event !== "npm.install.dependency_drift") continue;
    const reason = stringOrNull(parsed.reason);
    if (!reason || !reason.startsWith("added: ")) continue;
    for (const spec of reason.slice("added: ".length).split(",")) {
      const text = spec.trim();
      // rpartition på "@" — klarar scoped paket ("@scope/name@1.2.3").
      const at = text.lastIndexOf("@");
      if (at <= 0) continue;
      const name = text.slice(0, at);
      const version = text.slice(at + 1);
      if (name && version) added.set(name, version);
    }
  }
  return added;
}

/**
 * Dossier-attribution för tillagda paket: läs de monterade dossiers
 * manifest från repo-disken och bygg paketnamn→dossier-id. Best-effort —
 * hostat (ingen repo-disk) eller vid läsfel returneras en tom map och
 * ``source`` blir ärligt null i svaret.
 */
async function dependencySourcesFromManifests(
  dossierIds: string[],
): Promise<Map<string, string>> {
  const sources = new Map<string, string>();
  const dossiersRoot = path.join(
    ...[repoRoot(), "packages", "generation", "orchestration", "dossiers"],
  );
  for (const dossierId of dossierIds) {
    if (!DOSSIER_ID_PATTERN.test(dossierId)) continue;
    for (const dossierClass of ["soft", "hard"]) {
      const manifestPath = path.join(
        dossiersRoot,
        dossierClass,
        dossierId,
        "manifest.json",
      );
      let manifest: Record<string, unknown>;
      try {
        manifest = JSON.parse(
          await fs.readFile(manifestPath, "utf-8"),
        ) as Record<string, unknown>;
      } catch {
        continue;
      }
      const deps = manifest.dependencies;
      if (!Array.isArray(deps)) break;
      for (const spec of deps) {
        if (typeof spec !== "string") continue;
        const at = spec.lastIndexOf("@");
        if (at <= 0) continue;
        sources.set(spec.slice(0, at), dossierId);
      }
      break;
    }
  }
  return sources;
}

/**
 * Sätter ihop dependencies-blocket ur genererad package.json + trace-drift
 * + manifest-attribution. ``added``-setet kommer från trace-eventet (det
 * enda som vet vad som faktiskt lades till relativt starterns lockfile);
 * utan trace antas inga tillägg (ärligt: mekanismen fanns inte före #310).
 */
function buildDependencies(
  pkg: Record<string, unknown> | null,
  addedFromTrace: Map<string, string> | null,
  sources: Map<string, string>,
): SiteComposition["dependencies"] {
  const deps = recordOrNull(pkg?.dependencies);
  if (!deps) return null;
  const added: NonNullable<SiteComposition["dependencies"]>["added"] = [];
  const base: Record<string, string> = {};
  for (const [name, version] of Object.entries(deps)) {
    if (typeof version !== "string") continue;
    if (addedFromTrace?.has(name)) {
      added.push({ name, version, source: sources.get(name) ?? null });
    } else {
      base[name] = version;
    }
  }
  return { base, added };
}

function compositionSkeleton(siteId: string): SiteComposition {
  return {
    siteId,
    version: null,
    scaffoldId: null,
    variantId: null,
    starterId: null,
    language: null,
    companyName: null,
    routes: null,
    dossiers: null,
    components: null,
    dependencies: null,
    lastBuild: null,
  };
}

function applyArtefacts(
  composition: SiteComposition,
  buildResult: Record<string, unknown> | null,
  sitePlan: Record<string, unknown> | null,
): void {
  composition.version =
    intOrNull(buildResult?.version) ?? composition.version;
  composition.scaffoldId =
    stringOrNull(buildResult?.scaffoldId) ??
    stringOrNull(sitePlan?.scaffoldId) ??
    composition.scaffoldId;
  composition.variantId =
    stringOrNull(buildResult?.variantId) ??
    stringOrNull(sitePlan?.variantId) ??
    composition.variantId;
  composition.starterId =
    stringOrNull(buildResult?.starterId) ??
    stringOrNull(sitePlan?.starterId) ??
    composition.starterId;
  composition.language =
    stringOrNull(buildResult?.language) ?? composition.language;
  composition.routes = routesFromArtefacts(sitePlan, buildResult);
  composition.dossiers = dossiersFromSitePlan(sitePlan);
}

/** Välj nyaste run som inte är ett dött/pågående bygge utan artefakter. */
function pickLatestUsableRun(runs: RunMeta[]): RunMeta | null {
  const usable = runs.find(
    (run) => run.status !== "pending" && run.status !== "aborted",
  );
  return usable ?? runs[0] ?? null;
}

async function readLocalProjectInput(
  siteId: string,
): Promise<Record<string, unknown> | null> {
  const root = repoRoot();
  const candidates = [
    path.join(...[root, "data", "prompt-inputs", `${siteId}.project-input.json`]),
    path.join(...[root, "examples", `${siteId}.project-input.json`]),
  ];
  for (const candidate of candidates) {
    try {
      return JSON.parse(
        await fs.readFile(candidate, "utf-8"),
      ) as Record<string, unknown>;
    } catch {
      continue;
    }
  }
  return null;
}

async function readLocalTraceText(runId: string): Promise<string | null> {
  try {
    const runDir = await runDirFromId(runId);
    return await fs.readFile(path.join(...[runDir, "trace.ndjson"]), "utf-8");
  } catch {
    return null;
  }
}

/**
 * Lokal härledning: senaste runens artefakter + generated-files på disk +
 * project-input. Returnerar null när sajten inte har någon run alls
 * (callern svarar 404).
 */
export async function readLocalSiteComposition(
  siteId: string,
): Promise<SiteComposition | null> {
  const runs = await listRuns(10, { siteId });
  const latest = pickLatestUsableRun(runs);
  const composition = compositionSkeleton(siteId);

  const projectInput = await readLocalProjectInput(siteId);
  if (projectInput) {
    const company = recordOrNull(projectInput.company);
    composition.companyName = stringOrNull(company?.name);
    composition.scaffoldId = stringOrNull(projectInput.scaffoldId);
    composition.variantId = stringOrNull(projectInput.variantId);
    composition.language = stringOrNull(projectInput.language);
  }

  if (!latest && !projectInput) return null;

  if (latest) {
    composition.lastBuild = {
      runId: latest.runId,
      status: latest.status,
      createdAt: stringOrNull(latest.createdAt),
    };
    composition.version = latest.version ?? null;

    let bundle: Awaited<ReturnType<typeof readRunArtefacts>> | null = null;
    try {
      bundle = await readRunArtefacts(latest.runId);
    } catch {
      bundle = null;
    }
    if (bundle) {
      applyArtefacts(composition, bundle.buildResult, bundle.sitePlan);
    }

    const [pkg, manifest, traceText] = await Promise.all([
      readArtefactOrNull(latest.runId, "generated-files/package.json").catch(
        () => null,
      ),
      readArtefactOrNull(
        latest.runId,
        "generated-files/component-manifest.json",
      ).catch(() => null),
      readLocalTraceText(latest.runId),
    ]);
    composition.components = componentsFromManifest(manifest);
    const addedFromTrace = addedDependenciesFromTrace(traceText);
    const mountedIds = (composition.dossiers ?? [])
      .filter((entry) => entry.status === "required")
      .map((entry) => entry.id);
    const sources =
      addedFromTrace && addedFromTrace.size > 0
        ? await dependencySourcesFromManifests(mountedIds)
        : new Map<string, string>();
    composition.dependencies = buildDependencies(pkg, addedFromTrace, sources);
  }

  return composition;
}

function readTarText(
  files: Map<string, Buffer>,
  runId: string,
  relPath: string,
): string | null {
  const raw = files.get(`${runId}/${relPath}`);
  return raw ? raw.toString("utf-8") : null;
}

function readTarJson(
  files: Map<string, Buffer>,
  runId: string,
  relPath: string,
): Record<string, unknown> | null {
  const text = readTarText(files, runId, relPath);
  if (text === null) return null;
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Hostad härledning (B199-kedjan): KV-indexets senaste versionspost →
 * run-artifacts.tar.gz → samma artefakter + generated-files ur tarballen,
 * plus project-input via run-state-pekarens blob-URL. Saknade källor ger
 * en partiell bild med ``hostedNotice`` — aldrig påhittade data.
 * Returnerar null när sajten saknar både indexposter och run-state-pekare.
 */
export async function readHostedSiteComposition(
  siteId: string,
): Promise<SiteComposition | null> {
  const { runs, entries } = await listHostedRunsForSite(siteId, 5);
  const projectInput = await hostedProjectInputForSite(siteId);
  if (entries.length === 0 && !projectInput) return null;

  const composition = compositionSkeleton(siteId);
  if (projectInput) {
    composition.companyName = stringOrNull(projectInput.companyName);
    composition.scaffoldId = stringOrNull(projectInput.scaffoldId);
    composition.variantId = stringOrNull(projectInput.variantId);
    composition.language = stringOrNull(projectInput.language);
  }

  const entry = entries[0] ?? null;
  const latest = runs[0] ?? null;
  if (latest) {
    composition.lastBuild = {
      runId: latest.runId,
      status: latest.status,
      createdAt: stringOrNull(latest.createdAt),
    };
    composition.version = latest.version ?? null;
  }

  const files = entry ? await fetchHostedRunArtefactsTar(entry) : null;
  if (!entry || !files) {
    // Äldre hostade byggen (före B199) saknar artefakt-tarball — säg det.
    composition.hostedNotice = hostedRuntimeNotice();
    return composition;
  }

  const bundle = hostedRunArtefactBundle(entry, files);
  applyArtefacts(composition, bundle.buildResult, bundle.sitePlan);

  const pkg = readTarJson(files, entry.runId, "generated-files/package.json");
  const manifest = readTarJson(
    files,
    entry.runId,
    "generated-files/component-manifest.json",
  );
  composition.components = componentsFromManifest(manifest);
  const addedFromTrace = addedDependenciesFromTrace(
    readTarText(files, entry.runId, "trace.ndjson"),
  );
  // Hostat finns ingen repo-disk med dossier-manifest — attribution blir
  // ärligt null (UI visar paketet utan käll-dossier).
  composition.dependencies = buildDependencies(
    pkg,
    addedFromTrace,
    new Map<string, string>(),
  );

  if (!pkg && !manifest) {
    composition.hostedNotice = hostedRuntimeNotice();
  }

  return composition;
}
