/**
 * GPT Vision-klassificering för operatör-uppladdade bilder.
 *
 * Anropas synkront i `/api/upload-asset` direkt efter sharp-pipelinen.
 * Returnerar förslag på:
 *   - `subject`           — vad bilden föreställer
 *   - `recommendedPlacement` — vilken sida/sektion den passar bäst på
 *   - `suggestedAltText`  — alt-text på sajtens språk
 *   - `confidence`        — hur säker modellen är (operatorn ser detta)
 *
 * Mock-fallback: om `OPENAI_API_KEY` saknas returneras deterministiska
 * defaults baserade på `role` så att hela upload-flödet fungerar i
 * test/utan nyckel. Mock-output har confidence: "low" så UI:t kan
 * indikera att operatorn bör verifiera placeringen.
 */
import OpenAI from "openai";

import type {
  AssetPlacement,
  AssetRole,
  VisionConfidence,
} from "./types";

export interface VisionResult {
  subject: string;
  recommendedPlacement: AssetPlacement;
  suggestedAltText: string;
  confidence: VisionConfidence;
  modelUsed: string;
  usedFallback: boolean;
}

const VISION_MODEL = process.env.OPENAI_VISION_MODEL ?? "gpt-4o-mini";

const SYSTEM_INSTRUCTIONS = [
  "You analyse photos uploaded by an operator who is building a small business website.",
  "Return JSON with EXACTLY these keys: subject, recommendedPlacement, suggestedAltText, confidence.",
  "subject must be one short noun phrase describing what is in the image (e.g. 'logo', 'product packshot', 'restaurant interior', 'team portrait', 'coffee beans on tray').",
  "recommendedPlacement must be exactly one of: home, about, services, projects, products, gallery.",
  "  - Use 'home' for hero/banner/cover/landscape images that establish the brand.",
  "  - Use 'about' for team photos, portraits, founder shots, workspace interiors.",
  "  - Use 'services' for action shots that depict a service being performed.",
  "  - Use 'projects' for portfolio/case-study/finished-work imagery.",
  "  - Use 'products' for product packshots, e-commerce items, retail goods.",
  "  - Use 'gallery' as a fallback when no specific page is obvious.",
  "suggestedAltText must be written in Swedish unless the asset text is clearly in another language.",
  "  Keep alt text 4-12 words, no leading article, describe what is visible, no marketing fluff.",
  "confidence must be 'high' (clearly diagnostic image), 'medium' (probable fit), or 'low' (ambiguous).",
  "Output ONLY valid JSON. No markdown fences.",
].join("\n");

function mockVisionFor(role: AssetRole): VisionResult {
  const placement: AssetPlacement =
    role === "logo" ? "home" : role === "hero" ? "home" : "gallery";
  return {
    subject: role === "logo" ? "logo" : role === "hero" ? "hero photo" : "photo",
    recommendedPlacement: placement,
    suggestedAltText:
      role === "logo"
        ? "Företagets logotyp"
        : role === "hero"
          ? "Bild från verksamheten"
          : "Foto från verksamheten",
    confidence: "low",
    modelUsed: "mock",
    usedFallback: true,
  };
}

function clampPlacement(value: string): AssetPlacement {
  const normalized = value.trim().toLowerCase();
  const allowed: AssetPlacement[] = [
    "home",
    "about",
    "services",
    "projects",
    "products",
    "gallery",
  ];
  return (allowed.includes(normalized as AssetPlacement)
    ? normalized
    : "gallery") as AssetPlacement;
}

function clampConfidence(value: string): VisionConfidence {
  const v = value.trim().toLowerCase();
  if (v === "high") return "high";
  if (v === "medium") return "medium";
  return "low";
}

function parseVisionJson(raw: string, role: AssetRole): VisionResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ...mockVisionFor(role), modelUsed: VISION_MODEL, usedFallback: true };
  }
  if (typeof parsed !== "object" || parsed === null) {
    return { ...mockVisionFor(role), modelUsed: VISION_MODEL, usedFallback: true };
  }
  const obj = parsed as Record<string, unknown>;
  return {
    subject: typeof obj.subject === "string" && obj.subject.trim() ? obj.subject.trim() : "photo",
    recommendedPlacement: clampPlacement(
      typeof obj.recommendedPlacement === "string" ? obj.recommendedPlacement : "gallery",
    ),
    suggestedAltText:
      typeof obj.suggestedAltText === "string" && obj.suggestedAltText.trim()
        ? obj.suggestedAltText.trim()
        : "Foto",
    confidence: clampConfidence(
      typeof obj.confidence === "string" ? obj.confidence : "low",
    ),
    modelUsed: VISION_MODEL,
    usedFallback: false,
  };
}

let visionClient: OpenAI | null = null;

function getClient(): OpenAI | null {
  if (!process.env.OPENAI_API_KEY) return null;
  if (!visionClient) {
    visionClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return visionClient;
}

/**
 * Analysera en bild-buffer med GPT Vision. Returnerar alltid en
 * VisionResult — på fel/saknad nyckel/timeout faller vi tillbaka till
 * deterministisk mock istället för att låta upload-flödet krascha.
 */
export async function classifyAsset(args: {
  buffer: Buffer;
  mimeType: string;
  role: AssetRole;
}): Promise<VisionResult> {
  const client = getClient();
  if (!client) return mockVisionFor(args.role);

  // SVG-logos är ofta för enkla för meningsfull klassificering — och
  // skickas inte som inline-image till modellen. Behåll role-baserad
  // default men markera som mock så confidence inte ljuger.
  if (args.mimeType === "image/svg+xml") {
    return mockVisionFor(args.role);
  }

  const dataUrl = `data:${args.mimeType};base64,${args.buffer.toString("base64")}`;

  try {
    const completion = await client.chat.completions.create({
      model: VISION_MODEL,
      temperature: 0.2,
      max_tokens: 200,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: SYSTEM_INSTRUCTIONS },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: `Operatorn laddade upp denna bild med role="${args.role}". Klassificera den enligt instruktionerna.`,
            },
            {
              type: "image_url",
              image_url: { url: dataUrl, detail: "low" },
            },
          ],
        },
      ],
    });
    const content = completion.choices[0]?.message?.content?.trim();
    if (!content) return mockVisionFor(args.role);
    return parseVisionJson(content, args.role);
  } catch (caught) {
    console.warn(
      "[classifyAsset] OpenAI Vision-anrop misslyckades, faller tillbaka till mock:",
      caught instanceof Error ? caught.message : String(caught),
    );
    return mockVisionFor(args.role);
  }
}
