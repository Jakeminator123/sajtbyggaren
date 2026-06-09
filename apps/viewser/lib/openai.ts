import OpenAI from "openai";

import { readRepoEnvVar } from "./generated-dir";

// Single source of truth: fall back to the repo-root `.env` for shared OpenAI
// settings, so the API key only has to live in ONE file. process.env still
// wins (shell / Cloud / dev.mjs pass-through / apps/viewser/.env.local), so
// this only kicks in when the key/model is absent from the Viewser env.
// Exported (B168) so other API routes (generate-image) share the exact same
// resolution order instead of reading bare process.env and missing the root.
export function openaiEnv(name: string): string | undefined {
  const fromProcess = process.env[name]?.trim();
  if (fromProcess) return fromProcess;
  return readRepoEnvVar(name)?.trim() || undefined;
}

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type UsageSummary = {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  estimatedCostUsd: number;
  currency: "USD";
  model: string;
};

const DEFAULT_MODEL = openaiEnv("OPENAI_MODEL") ?? "gpt-4o";
// B170: USD-priserna gick tidigare bara via process.env, till skillnad från
// nyckel/modell ovan — Token Meter visade $0 när priserna bara stod i rotens
// .env. Samma openaiEnv-fallback som övriga OpenAI-inställningar.
const INPUT_USD_PER_1K = Number(openaiEnv("OPENAI_INPUT_USD_PER_1K") ?? "0");
const OUTPUT_USD_PER_1K = Number(openaiEnv("OPENAI_OUTPUT_USD_PER_1K") ?? "0");
const DEFAULT_MAX_OUTPUT_TOKENS = 1500;
const MAX_INPUT_CHARS_PER_MESSAGE = 8000;
const MAX_MESSAGES_PER_REQUEST = 40;

let openaiClient: OpenAI | null = null;
let openaiClientKey: string | null = null;

function getClient(): OpenAI {
  const apiKey = openaiEnv("OPENAI_API_KEY");
  if (!apiKey) {
    throw new Error(
      "OPENAI_API_KEY saknas. Lägg till den i repo-rotens .env (single " +
        "source) eller i apps/viewser/.env.local.",
    );
  }
  // B171: återskapa klienten om nyckeln bytts under en långkörande dev-
  // session — den gamla cachen gav 401 tills next dev startades om.
  if (!openaiClient || openaiClientKey !== apiKey) {
    openaiClient = new OpenAI({ apiKey });
    openaiClientKey = apiKey;
  }
  return openaiClient;
}

function maxOutputTokens(): number {
  const raw = process.env.VIEWSER_MAX_CHAT_TOKENS;
  if (!raw) return DEFAULT_MAX_OUTPUT_TOKENS;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_MAX_OUTPUT_TOKENS;
  return Math.floor(parsed);
}

function toUsageSummary(
  model: string,
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  },
): UsageSummary {
  const inputTokens = usage?.prompt_tokens ?? 0;
  const outputTokens = usage?.completion_tokens ?? 0;
  const totalTokens = usage?.total_tokens ?? inputTokens + outputTokens;
  const estimatedCostUsd =
    (inputTokens / 1000) * INPUT_USD_PER_1K +
    (outputTokens / 1000) * OUTPUT_USD_PER_1K;

  return {
    inputTokens,
    outputTokens,
    totalTokens,
    estimatedCostUsd,
    currency: "USD",
    model,
  };
}

function assertWithinChatLimits(messages: ChatMessage[]): void {
  if (messages.length > MAX_MESSAGES_PER_REQUEST) {
    throw new Error(
      `För många chat-meddelanden (${messages.length} > ${MAX_MESSAGES_PER_REQUEST}).`,
    );
  }
  for (const message of messages) {
    if (message.content.length > MAX_INPUT_CHARS_PER_MESSAGE) {
      throw new Error(
        `Chat-meddelande över gränsen ${MAX_INPUT_CHARS_PER_MESSAGE} tecken.`,
      );
    }
  }
}

export async function chatWithOpenAi(messages: ChatMessage[]): Promise<{
  message: ChatMessage;
  usage: UsageSummary;
}> {
  assertWithinChatLimits(messages);
  const client = getClient();
  const model = DEFAULT_MODEL;

  const completion = await client.chat.completions.create({
    model,
    messages,
    temperature: 0.3,
    max_tokens: maxOutputTokens(),
  });

  const answer = completion.choices[0]?.message?.content?.trim();
  if (!answer) {
    throw new Error("OpenAI returnerade inget innehåll i svaret.");
  }

  return {
    message: {
      role: "assistant",
      content: answer,
    },
    usage: toUsageSummary(model, completion.usage),
  };
}
