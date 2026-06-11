import { existsSync } from "node:fs";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";

import {
  hostedRuntimeNotice,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import { assertLocalhost } from "@/lib/localhost-guard";

type taxonomyCategory = {
  id: string;
  labelSv: string;
  contentBranch: string;
  supportStatus: "active" | "fallback" | "planned" | "disabled";
  targetScaffoldId: string;
  activeScaffoldId?: string;
  fallbackScaffoldId?: string;
  defaultVariantId: string;
  recommendedPages?: string[];
  operatorNotes?: string;
};

type discoveryTaxonomyPolicy = {
  categories: taxonomyCategory[];
};

type scaffoldRegistryEntry = {
  id: string;
  label: string;
};

type scaffoldContractPolicy = {
  primaryScaffoldRegistry: scaffoldRegistryEntry[];
};

/**
 * Variant summary returned to the Site Inspector so its Variants-tab can
 * render live-switchable preview cards without an extra fetch per variant.
 * We expose only the four canonical colour tokens (matching ``TokenId`` in
 * ``lib/runtime-tokens.ts``) plus tone.vibe; rich token data (typography,
 * radius, spacing, motion) stays on disk and is only read by the codegen
 * pipeline at build time.
 */
type variantSummary = {
  id: string;
  label: string;
  description: string;
  tokens: {
    primary: string;
    accent: string;
    background: string;
    foreground: string;
  };
  tone: {
    vibe: string[];
  };
};

type variantFile = {
  id?: unknown;
  enabled?: unknown;
  label?: unknown;
  description?: unknown;
  tokens?: {
    color?: {
      primary?: unknown;
      accent?: unknown;
      background?: unknown;
      foreground?: unknown;
    };
  };
  tone?: {
    vibe?: unknown;
  };
};

function asString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function asHexColor(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  return /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : fallback;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

/**
 * Reads every enabled variant JSON file under
 * ``packages/generation/orchestration/scaffolds/<scaffoldId>/variants/`` and
 * returns the canonical four-colour summary the Site Inspector needs. We
 * silently skip variants that are disabled or that fail to parse so a
 * single bad file cannot crash the whole discovery-options response.
 */
async function readScaffoldVariants(
  scaffoldId: string,
): Promise<variantSummary[]> {
  const variantsDir = path.join(
    repoRoot(),
    "packages",
    "generation",
    "orchestration",
    "scaffolds",
    scaffoldId,
    "variants",
  );
  if (!existsSync(variantsDir)) return [];
  let entries: string[];
  try {
    entries = await readdir(variantsDir);
  } catch {
    return [];
  }
  const jsonFiles = entries.filter(
    (name) => name.endsWith(".json") && !name.startsWith("_"),
  );
  const summaries: variantSummary[] = [];
  for (const filename of jsonFiles) {
    try {
      const raw = await readFile(path.join(variantsDir, filename), "utf-8");
      const parsed = JSON.parse(raw) as variantFile;
      if (parsed.enabled === false) continue;
      const id = asString(parsed.id, filename.replace(/\.json$/, ""));
      const colour = parsed.tokens?.color ?? {};
      summaries.push({
        id,
        label: asString(parsed.label, id),
        description: asString(parsed.description, ""),
        tokens: {
          primary: asHexColor(colour.primary, "#1a1a1a"),
          accent: asHexColor(colour.accent, "#0066ff"),
          background: asHexColor(colour.background, "#ffffff"),
          foreground: asHexColor(colour.foreground, "#0a0a0a"),
        },
        tone: {
          vibe: asStringArray(parsed.tone?.vibe),
        },
      });
    } catch {
      continue;
    }
  }
  return summaries.sort((a, b) => a.label.localeCompare(b.label, "sv"));
}

function repoRoot(): string {
  const candidates = [
    process.cwd(),
    path.resolve(process.cwd(), ".."),
    path.resolve(process.cwd(), "..", ".."),
  ];
  const match = candidates.find((candidate) =>
    existsSync(
      path.join(
        candidate,
        "governance",
        "policies",
        "discovery-taxonomy.v1.json",
      ),
    ),
  );
  // Only return a match if the expected file actually exists;
  // Else default to the correct repo root relative to the current working dir.
  if (match) return match;

  // Fallback — check if the fallback actually contains the file as a last-gasp
  const fallback = path.resolve(process.cwd(), "..", "..");
  if (
    existsSync(
      path.join(
        fallback,
        "governance",
        "policies",
        "discovery-taxonomy.v1.json",
      ),
    )
  ) {
    return fallback;
  }

  // If nothing works: throw explicit error (prevents unpredictable bundle behavior)
  throw new Error(
    'Could not find repo root containing "governance/policies/discovery-taxonomy.v1.json". Sajtbyggaren discovery-options API will not function.',
  );
}

async function readJson<T>(...segments: string[]): Promise<T> {
  // If repoRoot throws, surface as 500 (not broad dynamic bundle trace)
  const filePath = path.join(repoRoot(), ...segments);
  return JSON.parse(await readFile(filePath, "utf-8")) as T;
}

function categoryRuntimeScaffoldId(category: taxonomyCategory): string {
  if (category.supportStatus === "active") {
    return category.activeScaffoldId ?? category.targetScaffoldId;
  }
  return category.fallbackScaffoldId ?? category.targetScaffoldId;
}

function isOperatorRequest(request: NextRequest): boolean {
  const host = request.headers.get("host")?.toLowerCase() ?? "";
  return (
    host.startsWith("localhost") ||
    host.startsWith("127.0.0.1") ||
    host.startsWith("[::1]") ||
    process.env.VIEWSER_DISCOVERY_OPERATOR_NOTES === "true"
  );
}

export async function GET(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  try {
    const [taxonomy, scaffoldContract] = await Promise.all([
      readJson<discoveryTaxonomyPolicy>(
        "governance",
        "policies",
        "discovery-taxonomy.v1.json",
      ),
      readJson<scaffoldContractPolicy>(
        "governance",
        "policies",
        "scaffold-contract.v1.json",
      ),
    ]);
    const scaffoldLabels = new Map(
      scaffoldContract.primaryScaffoldRegistry.map((entry) => [
        entry.id,
        entry.label,
      ]),
    );
    const includeOperatorNotes = isOperatorRequest(request);
    const options = await Promise.all(
      taxonomy.categories.map(async (category) => {
        const runtimeScaffoldId = categoryRuntimeScaffoldId(category);
        const availableVariants = await readScaffoldVariants(runtimeScaffoldId);
        return {
          id: category.id,
          label: category.labelSv,
          contentBranch: category.contentBranch,
          supportStatus: category.supportStatus,
          defaultVariantId: category.defaultVariantId,
          // msg-0056 punkt 1: taxonomins sidförslag per kategori, så
          // FunctionsStep kan hämta förslagen från API:t med TS-cachen
          // (RELEVANT_PAGES_BY_FAMILY m.fl.) som fallback.
          recommendedPages: asStringArray(category.recommendedPages),
          targetScaffoldLabel:
            scaffoldLabels.get(category.targetScaffoldId) ??
            category.targetScaffoldId,
          fallbackLabel:
            runtimeScaffoldId !== category.targetScaffoldId
              ? (scaffoldLabels.get(runtimeScaffoldId) ?? runtimeScaffoldId)
              : undefined,
          runtimeScaffoldId,
          availableVariants,
          operatorNotes: includeOperatorNotes
            ? category.operatorNotes
            : undefined,
        };
      }),
    );

    return NextResponse.json({ options });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unknown error while reading discovery options.";
    // Hosted Vercel reads the taxonomy/scaffold policy files from disk at
    // runtime. They are bundled via `outputFileTracingIncludes` in
    // `next.config.ts`, but if a hosted deploy ever fails to resolve them we
    // degrade honestly (empty options + Swedish notice) instead of a raw 500
    // that would leave the wizard stuck with no explanation.
    if (isHostedVercelRuntime()) {
      return NextResponse.json({ options: [], hostedNotice: hostedRuntimeNotice() });
    }
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
