import fs from "fs";
import path from "path";

export type CaseStudyMetadata = {
  title: string;
  publishedAt: string;
  summary: string;
  image?: string;
};

export type CaseStudyEntry = {
  metadata: CaseStudyMetadata;
  slug: string;
  content: string;
};

const CASE_STUDIES_DIR = path.join(process.cwd(), "content", "case-studies");

function isMetadataKey(key: string): key is keyof CaseStudyMetadata {
  return ["title", "publishedAt", "summary", "image"].includes(key);
}

function parseFrontmatter(fileContent: string): {
  metadata: CaseStudyMetadata;
  content: string;
} {
  const frontmatterRegex = /^---\s*([\s\S]*?)\s*---/;
  const match = frontmatterRegex.exec(fileContent);

  if (!match?.[1]) {
    throw new Error("Case study MDX file is missing frontmatter.");
  }

  const metadata: Partial<CaseStudyMetadata> = {};
  for (const line of match[1].trim().split("\n")) {
    const [rawKey, ...valueParts] = line.split(": ");
    if (!rawKey || valueParts.length === 0) {
      continue;
    }

    const key = rawKey.trim();
    if (!isMetadataKey(key)) {
      continue;
    }

    metadata[key] = valueParts
      .join(": ")
      .trim()
      .replace(/^['"](.*)['"]$/, "$1");
  }

  if (!metadata.title || !metadata.publishedAt || !metadata.summary) {
    throw new Error(
      "Case study MDX frontmatter must include title, publishedAt, and summary.",
    );
  }

  return {
    metadata: {
      title: metadata.title,
      publishedAt: metadata.publishedAt,
      summary: metadata.summary,
      image: metadata.image,
    },
    content: fileContent.replace(frontmatterRegex, "").trim(),
  };
}

function getMDXFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    return [];
  }

  return fs
    .readdirSync(dir)
    .filter((file) => path.extname(file).toLowerCase() === ".mdx");
}

function readMDXFile(filePath: string): {
  metadata: CaseStudyMetadata;
  content: string;
} {
  return parseFrontmatter(fs.readFileSync(filePath, "utf-8"));
}

export function getCaseStudies(): CaseStudyEntry[] {
  return getMDXFiles(CASE_STUDIES_DIR).map((file) => {
    const { metadata, content } = readMDXFile(
      path.join(CASE_STUDIES_DIR, file),
    );

    return {
      metadata,
      slug: path.basename(file, path.extname(file)),
      content,
    };
  });
}

export function formatDate(date: string): string {
  const timestamp = date.includes("T") ? date : `${date}T00:00:00`;

  return new Date(timestamp).toLocaleString("en-US", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function sortByPublishedAt(entries: CaseStudyEntry[]): CaseStudyEntry[] {
  return [...entries].sort(
    (a, b) =>
      new Date(b.metadata.publishedAt).getTime() -
      new Date(a.metadata.publishedAt).getTime(),
  );
}

export function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}
