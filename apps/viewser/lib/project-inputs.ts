import { promises as fs } from "node:fs";
import type { Dirent } from "node:fs";
import path from "node:path";

import { projectInputAbsolutePath } from "@/lib/runs";

export type ProjectInputInfo = {
  siteId: string;
  companyName: string;
  scaffoldId: string;
  variantId: string;
  language: string;
  source: "examples" | "prompt-inputs";
};

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;
const VERSIONED_PROJECT_INPUT_PATTERN =
  /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.v[1-9][0-9]*\.project-input\.json$/;

function examplesDir(): string {
  return path.resolve(process.cwd(), "..", "..", "examples");
}

function promptInputsDir(): string {
  return path.resolve(process.cwd(), "..", "..", "data", "prompt-inputs");
}

export function assertSafeSiteId(siteId: string): void {
  if (!SITE_ID_PATTERN.test(siteId)) {
    throw new Error(
      `Ogiltigt siteId: '${siteId}'. Tillåtet: lower-case bokstäver, siffror och bindestreck.`,
    );
  }
}

async function listProjectInputsFromDir(
  dir: string,
  source: ProjectInputInfo["source"],
): Promise<ProjectInputInfo[]> {
  let entries: Dirent[];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return [];
    }
    throw error;
  }

  const siteFiles = entries
    .filter(
      (entry) =>
        entry.isFile() &&
        entry.name.endsWith(".project-input.json") &&
        !VERSIONED_PROJECT_INPUT_PATTERN.test(entry.name),
    )
    .map((entry) => entry.name);

  const inputs = await Promise.all(
    siteFiles.map(async (filename): Promise<ProjectInputInfo | null> => {
      const filePath = path.join(dir, filename);
      let parsed: {
        siteId: string;
        scaffoldId: string;
        variantId: string;
        language: string;
        company?: { name?: string };
      };
      try {
        const raw = await fs.readFile(filePath, "utf-8");
        parsed = JSON.parse(raw) as typeof parsed;
      } catch {
        return null;
      }

      return {
        siteId: parsed.siteId,
        companyName: parsed.company?.name ?? parsed.siteId,
        scaffoldId: parsed.scaffoldId,
        variantId: parsed.variantId,
        language: parsed.language,
        source,
      };
    }),
  );

  return inputs.filter((item): item is ProjectInputInfo => item !== null);
}

export async function listProjectInputs(): Promise<ProjectInputInfo[]> {
  const [examples, promptInputs] = await Promise.all([
    listProjectInputsFromDir(examplesDir(), "examples"),
    listProjectInputsFromDir(promptInputsDir(), "prompt-inputs"),
  ]);

  const bySiteId = new Map<string, ProjectInputInfo>();
  for (const item of examples) {
    bySiteId.set(item.siteId, item);
  }
  for (const item of promptInputs) {
    bySiteId.set(item.siteId, item);
  }

  return Array.from(bySiteId.values()).sort((a, b) => a.siteId.localeCompare(b.siteId));
}

export async function assertProjectInputExists(siteId: string): Promise<string> {
  assertSafeSiteId(siteId);
  const target = projectInputAbsolutePath(siteId);
  const examples = examplesDir();
  const relative = path.relative(examples, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`siteId pekar utanför examples/: ${siteId}`);
  }
  await fs.access(target);
  return target;
}
