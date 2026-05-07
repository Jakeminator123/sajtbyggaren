import { promises as fs } from "node:fs";
import path from "node:path";

import { siteDossierAbsolutePath } from "@/lib/runs";

export type ProjectInputInfo = {
  siteId: string;
  companyName: string;
  scaffoldId: string;
  variantId: string;
  language: string;
};

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

function examplesDir(): string {
  return path.resolve(process.cwd(), "..", "..", "examples");
}

export function assertSafeSiteId(siteId: string): void {
  if (!SITE_ID_PATTERN.test(siteId)) {
    throw new Error(
      `Ogiltigt siteId: '${siteId}'. Tillåtet: lower-case bokstäver, siffror och bindestreck.`,
    );
  }
}

export async function listProjectInputs(): Promise<ProjectInputInfo[]> {
  const dir = examplesDir();
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const siteFiles = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".site-dossier.json"))
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
      };
    }),
  );

  return inputs.sort((a, b) => a.siteId.localeCompare(b.siteId));
}

export async function assertProjectInputExists(siteId: string): Promise<string> {
  assertSafeSiteId(siteId);
  const target = siteDossierAbsolutePath(siteId);
  const examples = examplesDir();
  const relative = path.relative(examples, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`siteId pekar utanför examples/: ${siteId}`);
  }
  await fs.access(target);
  return target;
}
