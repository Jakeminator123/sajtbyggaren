// ADR 0044: load the conductor's constitution (the persona base) from
// docs/openclaw-workspace/SOUL.md so the chat persona has ONE source of truth,
// mirroring a real OpenClaw workspace SOUL file. generateConversationAnswer in
// app/api/prompt/route.ts reads this server-side for the chat persona only — it
// never controls build behaviour (the apply-chain rules live in code/governance,
// not in prose).
//
// Contract (kept deliberately small + defensive):
//   - read once, cache per process (success OR failure are both cached so a
//     missing/unreadable file degrades cheaply, not on every chat turn),
//   - truncate to a safe length so the assembled system message can never
//     approach lib/openai.ts's MAX_INPUT_CHARS_PER_MESSAGE (8000) cap,
//   - return null on any failure so the caller falls back to its hardcoded
//     persona lines. The honest DYNAMIC lines are appended AFTER this base by
//     the caller and therefore always win.

import { readFileSync } from "node:fs";
import path from "node:path";

import { repoRoot } from "./generated-dir";

const SOUL_RELATIVE_PATH = "docs/openclaw-workspace/SOUL.md";

// Truncation budget for the SOUL base text. The whole system message (SOUL base
// + dynamic honesty lines, including a site_opinion context snippet that can be
// several thousand chars) must stay under lib/openai.ts's 8000-char/message cap.
// This cap bounds the base; the caller additionally drops the base entirely if
// the combined message would still be too long (dynamic lines always survive).
const SOUL_MAX_CHARS = 3500;

let soulLoadAttempted = false;
let soulBaseCache: string[] | null = null;

// Turn the SOUL markdown into clean persona lines: drop blank lines, strip
// leading heading (`#`) and bullet (`-`/`*`) markers, keep the prose. The text
// is capped FIRST so a runaway file can never blow the budget.
function soulMarkdownToBaseLines(raw: string): string[] {
  const capped = raw.length > SOUL_MAX_CHARS ? raw.slice(0, SOUL_MAX_CHARS) : raw;
  const lines: string[] = [];
  for (const rawLine of capped.split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (!trimmed) continue;
    const cleaned = trimmed.replace(/^#{1,6}\s+/, "").replace(/^[-*]\s+/, "").trim();
    if (cleaned) lines.push(cleaned);
  }
  return lines;
}

/**
 * The SOUL persona base as system-prompt lines, or null when SOUL.md is
 * missing/unreadable/empty. Cached per process (the read happens at most once).
 */
export function loadSoulBaseLines(): string[] | null {
  if (soulLoadAttempted) return soulBaseCache;
  soulLoadAttempted = true;
  try {
    const soulPath = path.join(repoRoot(), SOUL_RELATIVE_PATH);
    const raw = readFileSync(soulPath, "utf8");
    const lines = soulMarkdownToBaseLines(raw);
    soulBaseCache = lines.length > 0 ? lines : null;
  } catch {
    soulBaseCache = null;
  }
  return soulBaseCache;
}
