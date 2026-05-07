import { promises as fs } from "node:fs";
import path from "node:path";

import { dossierAbsolutePath } from "@/lib/runs";

export type DossierInfo = {
  siteId: string;
  companyName: string;
  scaffoldId: string;
  variantId: string;
  language: string;
};

function examplesDir(): string {
  return path.resolve(process.cwd(), "..", "..", "examples");
}

export async function listSiteDossiers(): Promise<DossierInfo[]> {
  const dir = examplesDir();
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const siteFiles = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".site-dossier.json"))
    .map((entry) => entry.name);

  const dossiers = await Promise.all(
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

  return dossiers.sort((a, b) => a.siteId.localeCompare(b.siteId));
}

export async function assertDossierExists(siteId: string): Promise<string> {
  const target = dossierAbsolutePath(siteId);
  await fs.access(target);
  return target;
}
