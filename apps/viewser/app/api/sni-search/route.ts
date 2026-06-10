import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";

/**
 * /api/sni-search — branschsök över hela SNI 2025-spegeln (ADR 0045).
 *
 * Wizardens branschsök matchade tidigare bara de 25 kategorierna + en
 * handfull synonymer. Den här routen läser SNI-spegeln server-side
 * (1 882 etiketter; för stor för att skeppas till klienten) och svarar
 * med träffar berikade med:
 *
 * - `wizardCategoryId` — kategorin via sni-discovery-map (grupp-override
 *   slår huvudgrupps-default, samma prefix-logik som
 *   `packages/generation/discovery/sni_map.py`).
 * - `profile` — huvudgruppens branschprofil (industry-profiles.v1.json)
 *   för prefill av funktions-/CTA-val. Skickas bara när profilens
 *   kategori matchar den resolvade kategorin (samma ärlighetsgrind som
 *   backend-resolvern).
 *
 * Policyfilerna cacheas i modul-scope; de ändras bara vid deploy.
 */

type sniItem = {
  code: string;
  labelSv: string;
  level: "section" | "division" | "group" | "class" | "subclass";
};

type sniMapRow = {
  sniCode: string;
  wizardCategoryId: string;
};

type industryProfileRow = {
  profileId: string;
  sniCode: string;
  wizardCategoryId: string;
  curated: boolean;
  primaryCta: string;
  extraCapabilities: string[];
  recommendedPages: string[];
};

export type SniSearchMatch = {
  code: string;
  labelSv: string;
  level: string;
  wizardCategoryId: string;
  profile: {
    profileId: string;
    curated: boolean;
    primaryCta: string;
    extraCapabilities: string[];
    recommendedPages: string[];
  } | null;
};

type sniIndex = {
  items: sniItem[];
  divisions: Map<string, string>;
  groups: Map<string, string>;
  profiles: Map<string, industryProfileRow>;
};

let indexPromise: Promise<sniIndex> | null = null;

function repoRoot(): string {
  const candidates = [
    process.cwd(),
    path.resolve(process.cwd(), ".."),
    path.resolve(process.cwd(), "..", ".."),
  ];
  const match = candidates.find((candidate) =>
    existsSync(
      path.join(candidate, "data", "taxonomies", "sni", "sni-2025.v1.json"),
    ),
  );
  if (match) return match;
  throw new Error(
    'Could not find repo root containing "data/taxonomies/sni/sni-2025.v1.json".',
  );
}

async function readRepoJson<T>(...segments: string[]): Promise<T> {
  const filePath = path.join(repoRoot(), ...segments);
  return JSON.parse(await readFile(filePath, "utf-8")) as T;
}

async function loadIndex(): Promise<sniIndex> {
  const [taxonomy, sniMap, profilesPolicy] = await Promise.all([
    readRepoJson<{ items: sniItem[] }>(
      "data",
      "taxonomies",
      "sni",
      "sni-2025.v1.json",
    ),
    readRepoJson<{ divisionMappings: sniMapRow[]; groupOverrides?: sniMapRow[] }>(
      "governance",
      "policies",
      "sni-discovery-map.v1.json",
    ),
    readRepoJson<{ divisionProfiles: industryProfileRow[] }>(
      "governance",
      "policies",
      "industry-profiles.v1.json",
    ),
  ]);
  return {
    items: taxonomy.items.filter((item) => item.level !== "section"),
    divisions: new Map(
      sniMap.divisionMappings.map((row) => [row.sniCode, row.wizardCategoryId]),
    ),
    groups: new Map(
      (sniMap.groupOverrides ?? []).map((row) => [
        row.sniCode,
        row.wizardCategoryId,
      ]),
    ),
    profiles: new Map(
      profilesPolicy.divisionProfiles.map((row) => [row.sniCode, row]),
    ),
  };
}

function getIndex(): Promise<sniIndex> {
  if (indexPromise === null) {
    indexPromise = loadIndex().catch((error) => {
      // Nollställ cachen vid fel så nästa request försöker igen i stället
      // för att fastna på ett rejectat promise för processens livstid.
      indexPromise = null;
      throw error;
    });
  }
  return indexPromise;
}

/** Lowercase + vik åäö/é — samma vikning som wizardens lokala index. */
function normalize(text: string): string {
  return text
    .toLowerCase()
    .replaceAll("å", "a")
    .replaceAll("ä", "a")
    .replaceAll("ö", "o")
    .replaceAll("é", "e");
}

/**
 * Kategori för en SNI-kod — TS-spegling av prefix-logiken i
 * `resolve_sni_discovery_category` (mest specifik först: 3-siffrig
 * grupp-override, sedan 2-siffrig huvudgrupp).
 */
function categoryForCode(index: sniIndex, code: string): string | null {
  const digits = code.replace(/[^0-9]/g, "");
  if (digits.length >= 3) {
    const group = index.groups.get(digits.slice(0, 3));
    if (group) return group;
  }
  if (digits.length >= 2) {
    const division = index.divisions.get(digits.slice(0, 2));
    if (division) return division;
  }
  return null;
}

function profileForCode(
  index: sniIndex,
  code: string,
  categoryId: string,
): SniSearchMatch["profile"] {
  const digits = code.replace(/[^0-9]/g, "");
  if (digits.length < 2) return null;
  const profile = index.profiles.get(digits.slice(0, 2));
  if (!profile) return null;
  // Ärlighetsgrind (ADR 0045): profilen gäller bara när dess kategori
  // matchar den resolvade — annars skulle t.ex. 96.03 (begravning →
  // business via grupp-override) prefyllas med salongs-innehåll.
  if (profile.wizardCategoryId !== categoryId) return null;
  return {
    profileId: profile.profileId,
    curated: profile.curated,
    primaryCta: profile.primaryCta,
    extraCapabilities: profile.extraCapabilities ?? [],
    recommendedPages: profile.recommendedPages ?? [],
  };
}

const MAX_MATCHES = 8;

export async function GET(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  const query = normalize(
    (request.nextUrl.searchParams.get("q") ?? "").trim(),
  );
  if (query.length < 2) {
    return NextResponse.json({ matches: [] });
  }

  let index: sniIndex;
  try {
    index = await getIndex();
  } catch {
    // Ärlig degradering — wizardens lokala synonym-index fungerar ändå.
    return NextResponse.json({ matches: [] });
  }

  const scored: { item: sniItem; score: number }[] = [];
  for (const item of index.items) {
    const label = normalize(item.labelSv);
    let score = 0;
    if (label.startsWith(query)) {
      score = 3;
    } else if (label.includes(` ${query}`)) {
      score = 2;
    } else if (label.includes(query)) {
      score = 1;
    }
    if (score > 0) scored.push({ item, score });
  }

  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    // Kortare label = mer specifik träff för operatörens sökord.
    if (a.item.labelSv.length !== b.item.labelSv.length) {
      return a.item.labelSv.length - b.item.labelSv.length;
    }
    return a.item.code.localeCompare(b.item.code, "sv");
  });

  const matches: SniSearchMatch[] = [];
  const seenLabels = new Set<string>();
  for (const { item } of scored) {
    if (matches.length >= MAX_MATCHES) break;
    const categoryId = categoryForCode(index, item.code);
    if (!categoryId) continue;
    // Dedupe på label — SNI upprepar ofta samma etikett på class- och
    // subclass-nivå ("56.10" och "56.100"); en rad räcker i UI:t.
    const labelKey = normalize(item.labelSv);
    if (seenLabels.has(labelKey)) continue;
    seenLabels.add(labelKey);
    matches.push({
      code: item.code,
      labelSv: item.labelSv,
      level: item.level,
      wizardCategoryId: categoryId,
      profile: profileForCode(index, item.code, categoryId),
    });
  }

  return NextResponse.json({ matches });
}
