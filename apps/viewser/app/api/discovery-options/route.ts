import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";

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
  return match ?? path.resolve(process.cwd(), "..", "..");
}

async function readJson<T>(...segments: string[]): Promise<T> {
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
    const options = taxonomy.categories.map((category) => {
      const runtimeScaffoldId = categoryRuntimeScaffoldId(category);
      return {
        id: category.id,
        label: category.labelSv,
        contentBranch: category.contentBranch,
        supportStatus: category.supportStatus,
        defaultVariantId: category.defaultVariantId,
        targetScaffoldLabel:
          scaffoldLabels.get(category.targetScaffoldId) ??
          category.targetScaffoldId,
        fallbackLabel:
          runtimeScaffoldId !== category.targetScaffoldId
            ? (scaffoldLabels.get(runtimeScaffoldId) ?? runtimeScaffoldId)
            : undefined,
        operatorNotes: includeOperatorNotes ? category.operatorNotes : undefined,
      };
    });

    return NextResponse.json({ options });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unknown error while reading discovery options.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
