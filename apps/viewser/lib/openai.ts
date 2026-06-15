import { readFileSync } from "node:fs";
import path from "node:path";

import OpenAI from "openai";

import { readRepoEnvVar, repoRoot } from "./generated-dir";

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

// Fallback gpt-5.5 -> gpt-5.4 (prod-fix 2026-06-15): gpt-5.5 avvisar ett eget
// `temperature`-värde (se supportsCustomTemperature nedan), och när
// OPENAI_MODEL inte är satt för Viewser-processen föll vi tillbaka på just
// gpt-5.5 — vilket fick VARJE TS-chat-anrop att kasta på prod. gpt-5.4 är den
// modell governance-Python-lagret redan kör (llm-models.v1.json) och som
// validerat godtar våra parametrar.
const DEFAULT_MODEL = openaiEnv("OPENAI_MODEL") ?? "gpt-5.4";
// B170: USD-priserna gick tidigare bara via process.env, till skillnad från
// nyckel/modell ovan — Token Meter visade $0 när priserna bara stod i rotens
// .env. Samma openaiEnv-fallback som övriga OpenAI-inställningar.
const INPUT_USD_PER_1K = Number(openaiEnv("OPENAI_INPUT_USD_PER_1K") ?? "0");
const OUTPUT_USD_PER_1K = Number(openaiEnv("OPENAI_OUTPUT_USD_PER_1K") ?? "0");
const DEFAULT_MAX_OUTPUT_TOKENS = 1500;
const MAX_INPUT_CHARS_PER_MESSAGE = 8000;
const MAX_MESSAGES_PER_REQUEST = 40;

// Fråga.. vad är max-tokengränsen här då?
// Svar: max-tokengränsen (per svar, dvs max antalet tokens som modellen får generera) sätts av DEFAULT_MAX_OUTPUT_TOKENS,
// dvs 1500 tokens som default, men kan överskrivas via env-variabeln VIEWSER_MAX_CHAT_TOKENS. Modeller har olika absoluta gränser
// för prompt+output, men denna kod begränsar *svarstokens* till maxOutputTokens().

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

// Prod-fix 2026-06-15: gpt-5.x och o-seriens reasoning-modeller stödjer bara
// default-temperaturen (1) och avvisar ett eget värde med
// 400 "Unsupported value: 'temperature' does not support 0.3 ... Only the
// default (1) value is supported". Lokalt kör chatten gpt-4o-mini (godtar 0.3)
// men prod kör en gpt-5.x via OPENAI_MODEL/fallback — så den hårdkodade 0.3:an
// fick VARJE TS-chat-anrop (conversation-svar, G1-preclassify,
// applied-confirmation) att kasta och kunden fick bara den ärliga felraden.
// Samma defensiva, modell-medvetna mönster som B176 (max_tokens ->
// max_completion_tokens): skicka temperature ENBART till modeller som stödjer
// ett eget värde.
function supportsCustomTemperature(model: string): boolean {
  return !/^(gpt-5|o\d)/i.test(model);
}

function maxOutputTokens(): number {
  const raw = process.env.VIEWSER_MAX_CHAT_TOKENS;
  if (!raw) return DEFAULT_MAX_OUTPUT_TOKENS;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_MAX_OUTPUT_TOKENS;
  return Math.floor(parsed);
}

// ADR 0052: per-roll modellparametrar ur llm-models.v1.json. TS-sidan är
// enbart plumbing - chatten är medvetet INGEN registrerad Model Role, så
// utan roleId är beteendet exakt som tidigare. Spegelbild av den delade
// Python-läsaren packages/policies/llm_model_params.py (defensiv: misslyckad
// läsning => inga params, aldrig ett kastat fel).
const VALID_REASONING_EFFORTS = new Set([
  "none",
  "low",
  "medium",
  "high",
  "xhigh",
]);

export type RoleModelParams = {
  reasoningEffort?: "none" | "low" | "medium" | "high" | "xhigh";
  maxOutputTokens?: number;
};

export function readRoleModelParams(roleId: string): RoleModelParams {
  try {
    const policyPath = path.join(
      repoRoot(),
      "governance",
      "policies",
      "llm-models.v1.json",
    );
    const data = JSON.parse(readFileSync(policyPath, "utf8")) as {
      roles?: Array<Record<string, unknown>>;
    };
    const role = data.roles?.find(
      (entry) => entry && entry.id === roleId,
    );
    if (!role) return {};
    const params: RoleModelParams = {};
    const rawEffort = role.reasoningEffort;
    if (typeof rawEffort === "string") {
      // Legacy-skalan: 'minimal' accepteras och mappas till 'low' (ADR 0052).
      const effort = rawEffort === "minimal" ? "low" : rawEffort;
      if (VALID_REASONING_EFFORTS.has(effort)) {
        params.reasoningEffort = effort as RoleModelParams["reasoningEffort"];
      }
    }
    const rawTokens = role.maxOutputTokens;
    if (
      typeof rawTokens === "number" &&
      Number.isInteger(rawTokens) &&
      rawTokens >= 1
    ) {
      params.maxOutputTokens = rawTokens;
    }
    return params;
  } catch {
    return {};
  }
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

export async function chatWithOpenAi(
  messages: ChatMessage[],
  options?: { roleId?: string },
): Promise<{
  message: ChatMessage;
  usage: UsageSummary;
}> {
  assertWithinChatLimits(messages);
  const client = getClient();
  const model = DEFAULT_MODEL;

  // ADR 0052: ett valfritt roleId hämtar per-roll-params ur policyn; utan
  // roleId (dagens chatt) är anropet EXAKT som tidigare.
  const roleParams = options?.roleId ? readRoleModelParams(options.roleId) : {};

  // B176: nyare modeller (gpt-5.x) avvisar `max_tokens` med 400
  // "Unsupported parameter" — `max_completion_tokens` är ersättaren och
  // accepteras även av äldre chat-modeller.
  // max_completion_tokens = max-tokengränsen här, d.v.s. (oftast) 1500 tokens per svar se ovan.
  const completion = await client.chat.completions.create({
    model,
    messages,
    // Se supportsCustomTemperature: gpt-5.x/o-serien får INTE ett eget
    // temperature-värde (de avvisar allt utom default 1 med 400).
    ...(supportsCustomTemperature(model) ? { temperature: 0.3 } : {}),
    max_completion_tokens: roleParams.maxOutputTokens ?? maxOutputTokens(),
    ...(roleParams.reasoningEffort
      ? { reasoning_effort: roleParams.reasoningEffort }
      : {}),
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
