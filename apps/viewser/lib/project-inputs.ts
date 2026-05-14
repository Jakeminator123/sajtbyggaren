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
    .filter((entry) => entry.isFile() && entry.name.endsWith(".project-input.json"))
    .map((entry) => entry.name);

  const inputs = await Promise.all(
    siteFiles.map(async (filename) => {
      const filePath = path.join(dir, filename);
      const raw = await fs.readFile(filePath, "utf-8");
      const parsed = JSON.parse(raw) as {
        siteId: string;
        scaffoldId: string;
        variantId: string;
        language: string;
        company?: { name?: string };
      };

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

  return inputs;
}

export async function listProjectInputs(): Promise<ProjectInputInfo[]> {
  const [examples, promptInputs] = await Promise.all([
    listProjectInputsFromDir(examplesDir(), "examples"),
    listProjectInputsFromDir(promptInputsDir(), "prompt-inputs"),
  ]);

  return [...examples, ...promptInputs].sort((a, b) =>
    a.siteId.localeCompare(b.siteId),
  );
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
