import OpenAI from "openai";

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

const DEFAULT_MODEL = process.env.OPENAI_MODEL ?? "gpt-5.4";
const INPUT_USD_PER_1K = Number(process.env.OPENAI_INPUT_USD_PER_1K ?? "0");
const OUTPUT_USD_PER_1K = Number(process.env.OPENAI_OUTPUT_USD_PER_1K ?? "0");

let openaiClient: OpenAI | null = null;

function getClient(): OpenAI {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY saknas. Lägg till den i apps/viewser/.env.local.");
  }
  if (!openaiClient) {
    openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openaiClient;
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
    (inputTokens / 1000) * INPUT_USD_PER_1K + (outputTokens / 1000) * OUTPUT_USD_PER_1K;

  return {
    inputTokens,
    outputTokens,
    totalTokens,
    estimatedCostUsd,
    currency: "USD",
    model,
  };
}

export async function chatWithOpenAi(messages: ChatMessage[]): Promise<{
  message: ChatMessage;
  usage: UsageSummary;
}> {
  const client = getClient();
  const model = DEFAULT_MODEL;

  const completion = await client.chat.completions.create({
    model,
    messages,
    temperature: 0.3,
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
