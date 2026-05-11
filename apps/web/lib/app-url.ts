const DEFAULT_APP_BASE_URL = "http://localhost:3000";

function stripWrappingQuotes(value: string): string {
  const trimmed = value.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

function normalizeAppBaseUrl(value?: string | null): string {
  const candidate = value ? stripWrappingQuotes(value).replace(/\/+$/, "") : "";
  if (!candidate) return DEFAULT_APP_BASE_URL;

  try {
    return new URL(candidate).origin;
  } catch {
    return DEFAULT_APP_BASE_URL;
  }
}

export function getAppBaseUrl(): string {
  return normalizeAppBaseUrl(
    process.env.NEXT_PUBLIC_APP_URL || process.env.NEXT_PUBLIC_BASE_URL,
  );
}

