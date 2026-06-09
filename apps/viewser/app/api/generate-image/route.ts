import { NextRequest, NextResponse } from "next/server";

import { getAssetStore } from "@/lib/asset-store";
import type {
  AssetMimeType,
  AssetRef,
  AssetRole,
} from "@/lib/asset-store/types";
import { assertLocalhost } from "@/lib/localhost-guard";
import { openaiEnv } from "@/lib/openai";

/**
 * POST /api/generate-image — generera en bild med OpenAI GPT Image 1.5
 * och spara den genom samma AssetStore som operatör-uppladdade filer.
 *
 * Detta är ett komplement till `/api/upload-asset` så användaren kan
 * antingen ladda upp egen bild ELLER generera en med AI. Båda ger
 * tillbaka en identisk `AssetRef` med samma `role`/`mime`/`alt`/
 * `sourceUrl`-shape — wizardens MediaStep konsumerar resultatet utan
 * att veta om bilden kommer från upload eller AI.
 *
 * Modell-val: `gpt-image-1.5` (default) eller `gpt-image-1`. Båda
 * accepterar samma parametrar — endast pris/kvalitet skiljer. 1.5 är
 * ~20% billigare och har bättre instruction-following enligt OpenAI.
 *
 * Cost-control:
 *   - Default quality = "medium" (≈ $0.04/img för 1024×1024)
 *   - Role-specifika storlekar (logo 1024², hero 1536×1024)
 *   - Inga generationer för `backgroundVideo` (image API ≠ video)
 *
 * Säkerhet:
 *   - Localhost-only (samma guard som upload-asset)
 *   - Prompt-längd cappad till 1000 tecken
 *   - Operator-prompt augmenteras med brand-context (companyName, color,
 *     style) på server-side så LLM-prompten är konsekvent + filtrerar
 *     bort uppenbara prompt-injection-mönster
 *
 * Body JSON:
 *   - prompt:        string         (operatörens önskan, krävs)
 *   - role:          AssetRole       (logo|hero|gallery|favicon|ogImage)
 *   - style?:        StylePreset    (photoreal|minimal|illustration|brand)
 *   - companyName?:  string         (för brand-konsekvens i prompten)
 *   - brandColorHex?: string        (för brand-konsekvens i prompten)
 *   - siteId?:       string         (samma som upload — "__draft" default)
 *
 * Returnerar `{ ok: true, ref: AssetRef }` eller `{ ok: false, error }`.
 */

export const runtime = "nodejs";
// gpt-image-1.5 quality=medium tar typiskt 8-15 sek; quality=high upp
// till 30-40 sek. 60s ger comfort-margin innan Vercels/Next dev-server
// default-timeout (10s) skulle döda requesten.
export const maxDuration = 60;

const ALLOWED_ROLES = new Set<AssetRole>([
  "logo",
  "hero",
  "gallery",
  "favicon",
  "ogImage",
  // backgroundVideo medvetet utelämnad — OpenAI har ingen text-to-video API
  // i Images-endpointen. Frontend visar "Generera med AI" knappen disabled
  // för den rollen med tooltip-förklaring.
]);

const ALLOWED_STYLES = new Set([
  "photoreal",
  "minimal",
  "illustration",
  "brand",
] as const);
type StylePreset = "photoreal" | "minimal" | "illustration" | "brand";

const SITE_ID_PATTERN = /^[a-z0-9_-]{1,64}$/i;
const HEX_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;
const MAX_PROMPT_LENGTH = 1000;

interface RoleConfig {
  size: "1024x1024" | "1024x1536" | "1536x1024";
  background: "transparent" | "opaque" | "auto";
  format: "png" | "webp";
  mime: AssetMimeType;
  // Augmentation-prefix som LLM:n får före user-prompten. Hjälper modellen
  // förstå kontexten utan att operatorn behöver beskriva den varje gång.
  contextHint: string;
  // En default-alt-text om operatorn inte ger en egen via prompten.
  fallbackAlt: string;
}

const ROLE_CONFIG: Record<Exclude<AssetRole, "backgroundVideo">, RoleConfig> = {
  logo: {
    size: "1024x1024",
    background: "transparent",
    format: "png",
    mime: "image/png",
    contextHint:
      "Generate a professional company logo, vector-style, transparent background, " +
      "balanced composition, clear silhouette readable at 32×32 px (favicon size).",
    fallbackAlt: "Företagslogotyp",
  },
  hero: {
    size: "1536x1024",
    background: "auto",
    format: "webp",
    mime: "image/webp",
    contextHint:
      "Generate a wide cinematic hero image (16:10 aspect) suitable for a website " +
      "above-the-fold section. Editorial photography quality, natural lighting, " +
      "no overlaid text.",
    fallbackAlt: "Hero-bild",
  },
  gallery: {
    size: "1024x1024",
    background: "auto",
    format: "webp",
    mime: "image/webp",
    contextHint:
      "Generate a square portfolio image (1:1). Editorial photography style, " +
      "single clear subject, no overlaid text or watermarks.",
    fallbackAlt: "Galleribild",
  },
  favicon: {
    size: "1024x1024",
    background: "transparent",
    format: "png",
    mime: "image/png",
    contextHint:
      "Generate a square icon (1:1) suitable for use as a browser favicon. " +
      "Bold simple shape readable at 16×16 px, no fine details, transparent background.",
    fallbackAlt: "Webbikon",
  },
  ogImage: {
    size: "1536x1024",
    background: "auto",
    format: "webp",
    mime: "image/webp",
    contextHint:
      "Generate a 1.91:1 social-sharing image suitable for Facebook/LinkedIn/" +
      "Twitter open graph preview. Editorial style, central composition, leave " +
      "space on the lower third for potential text overlay (do NOT add text yourself).",
    fallbackAlt: "Social preview",
  },
};

const STYLE_HINTS: Record<StylePreset, string> = {
  photoreal:
    "Photorealistic, high-end editorial photography aesthetic, natural lighting, " +
    "shallow depth of field, no AI-looking artifacts.",
  minimal:
    "Minimalist flat design, geometric shapes, single subject, high contrast, " +
    "Swiss design principles, generous negative space.",
  illustration:
    "Hand-illustrated vector art, soft palette, organic line work, modern editorial " +
    "illustration style (similar to The New Yorker or Wired).",
  brand:
    "Brand-aligned premium look that matches the provided brand color exactly. " +
    "Modern, professional, suitable for small-business website.",
};

function badRequest(message: string): NextResponse {
  return NextResponse.json({ ok: false, error: message }, { status: 400 });
}

function serverError(message: string, status = 500): NextResponse {
  return NextResponse.json({ ok: false, error: message }, { status });
}

interface GenerateRequest {
  prompt: string;
  role: Exclude<AssetRole, "backgroundVideo">;
  style?: StylePreset;
  companyName?: string;
  brandColorHex?: string;
  siteId?: string;
}

function parseBody(body: unknown): GenerateRequest | string {
  if (!body || typeof body !== "object") {
    return "Body måste vara ett JSON-objekt.";
  }
  const b = body as Record<string, unknown>;

  const prompt = typeof b.prompt === "string" ? b.prompt.trim() : "";
  if (!prompt) return "Fält 'prompt' krävs och får inte vara tomt.";
  if (prompt.length > MAX_PROMPT_LENGTH) {
    return `Fält 'prompt' får vara max ${MAX_PROMPT_LENGTH} tecken (var ${prompt.length}).`;
  }

  const role = typeof b.role === "string" ? (b.role as AssetRole) : null;
  if (!role || !ALLOWED_ROLES.has(role)) {
    return (
      "Fält 'role' måste vara logo, hero, gallery, favicon eller ogImage. " +
      "(backgroundVideo stöds ej — OpenAI Images API är text-to-image, inte text-to-video.)"
    );
  }

  let style: StylePreset | undefined;
  if (b.style !== undefined && b.style !== null) {
    if (typeof b.style !== "string" || !ALLOWED_STYLES.has(b.style as StylePreset)) {
      return "Fält 'style' måste vara photoreal, minimal, illustration eller brand.";
    }
    style = b.style as StylePreset;
  }

  let companyName: string | undefined;
  if (b.companyName !== undefined && b.companyName !== null) {
    if (typeof b.companyName !== "string") {
      return "Fält 'companyName' måste vara sträng om angivet.";
    }
    companyName = b.companyName.trim().slice(0, 120) || undefined;
  }

  let brandColorHex: string | undefined;
  if (b.brandColorHex !== undefined && b.brandColorHex !== null) {
    if (
      typeof b.brandColorHex !== "string" ||
      !HEX_COLOR_PATTERN.test(b.brandColorHex)
    ) {
      return "Fält 'brandColorHex' måste vara #RRGGBB-format om angivet.";
    }
    brandColorHex = b.brandColorHex.toLowerCase();
  }

  let siteId: string | undefined;
  if (b.siteId !== undefined && b.siteId !== null) {
    if (typeof b.siteId !== "string" || !SITE_ID_PATTERN.test(b.siteId.trim())) {
      return "Fält 'siteId' måste matcha [a-z0-9_-]{1,64} om angivet.";
    }
    siteId = b.siteId.trim();
  }

  return {
    prompt,
    role: role as Exclude<AssetRole, "backgroundVideo">,
    style,
    companyName,
    brandColorHex,
    siteId,
  };
}

/**
 * Bygg den slutgiltiga prompten som skickas till GPT Image. Operator-
 * texten kommer FÖRST så modellen får största vikten på den; våra
 * augmentations (role-context, style, brand) appended efter som
 * "constraints"-sektion.
 *
 * Vi sanerar lättviktigt — ingen aggressiv prompt-injection-filter (det
 * blir false-positives för legitima company-namn) men vi capper längden
 * och tar bort kontroll-chars.
 */
function buildFullPrompt(req: GenerateRequest): string {
  const config = ROLE_CONFIG[req.role];
  const sanitizedUserPrompt = req.prompt
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  const segments: string[] = [sanitizedUserPrompt];

  if (req.companyName) {
    segments.push(
      `This image is for the company "${req.companyName.replace(/"/g, "'")}".`,
    );
  }
  if (req.brandColorHex && (req.role === "logo" || req.style === "brand")) {
    segments.push(
      `Brand primary color: ${req.brandColorHex}. Use this color as the dominant accent.`,
    );
  }
  if (req.style) {
    segments.push(`Style: ${STYLE_HINTS[req.style]}`);
  }
  segments.push(`Constraint: ${config.contextHint}`);
  segments.push(
    "Do NOT include text, watermarks, logos of other brands, or any human faces of recognisable real persons.",
  );

  return segments.join(" ");
}

/**
 * Anropa OpenAI Images API. Returnerar PNG/WebP-bytes som Buffer.
 *
 * Fel-strategi: vi lyfter exceptions med klara svenska meddelanden så
 * frontend kan visa dem direkt utan att läcka API-detaljer.
 */
async function callOpenAIImageAPI(req: GenerateRequest): Promise<Buffer> {
  // B168: gå via openaiEnv (process.env -> repo-rotens .env) precis som
  // chatten i lib/openai.ts. Tidigare lästes bara process.env här, så AI-
  // bilder gav "nyckel saknas" i den dokumenterade single-source-setupen
  // (nyckel i rot-.env, tom rad i apps/viewser/.env.local).
  const apiKey = openaiEnv("OPENAI_API_KEY");
  if (!apiKey) {
    throw new Error(
      "OPENAI_API_KEY saknas i env. Sätt den i repo-rotens .env (single " +
        "source) eller i apps/viewser/.env.local.",
    );
  }

  const model = (openaiEnv("OPENAI_IMAGE_MODEL") ?? "gpt-image-1.5").trim();
  const quality = (openaiEnv("OPENAI_IMAGE_QUALITY") ?? "medium").trim();
  const config = ROLE_CONFIG[req.role];

  const payload: Record<string, unknown> = {
    model,
    prompt: buildFullPrompt(req),
    n: 1,
    size: config.size,
    quality,
    output_format: config.format,
  };
  // ``background`` stöds bara på vissa modeller; vi skickar den endast
  // för gpt-image-1.5/1 som har den (alla nyare image-modeller har den).
  if (config.background !== "auto") {
    payload.background = config.background;
  }

  const response = await fetch("https://api.openai.com/v1/images/generations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    // Spara svaret i server-loggar men returnera generic-meddelande till
    // frontend så vi inte läcker API-error-payload (kan innehålla intern
    // request-id eller policy-detaljer).
    console.error("[/api/generate-image] OpenAI returnerade fel:", {
      status: response.status,
      body: errorBody.slice(0, 500),
    });
    if (response.status === 400) {
      throw new Error(
        "OpenAI avvisade prompten. Försök beskriva bilden i mer neutrala termer " +
          "(undvik specifika personer, varumärken eller känsligt innehåll).",
      );
    }
    if (response.status === 401) {
      throw new Error(
        "OPENAI_API_KEY accepterades inte av OpenAI. Verifiera att nyckeln är " +
          "giltig och att kontot har tillgång till gpt-image-1.5.",
      );
    }
    if (response.status === 429) {
      throw new Error(
        "OpenAI rate-limit nådd. Vänta en minut innan du försöker igen.",
      );
    }
    throw new Error(
      `OpenAI returnerade ${response.status}. Försök igen om en stund.`,
    );
  }

  type ImagesResponse = {
    data?: Array<{ b64_json?: string; url?: string }>;
  };
  const data = (await response.json()) as ImagesResponse;
  const first = data.data?.[0];
  if (!first?.b64_json) {
    throw new Error(
      "OpenAI returnerade ingen b64_json-bild — oväntat svar-format.",
    );
  }
  return Buffer.from(first.b64_json, "base64");
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let json: unknown;
  try {
    json = await request.json();
  } catch (caught) {
    return badRequest(
      `Ogiltig JSON-body: ${caught instanceof Error ? caught.message : "okänt parse-fel"}.`,
    );
  }

  const parsed = parseBody(json);
  if (typeof parsed === "string") return badRequest(parsed);

  const config = ROLE_CONFIG[parsed.role];
  let imageBytes: Buffer;
  try {
    imageBytes = await callOpenAIImageAPI(parsed);
  } catch (caught) {
    const message =
      caught instanceof Error ? caught.message : "Okänt fel vid bild-generering.";
    return serverError(message);
  }

  // Skapa ett "originalName" som hjälper operatören känna igen filen i
  // listor — slug:as senare av AssetStore.
  const slug = parsed.role + "-ai-" + Date.now().toString(36);
  const originalName = `${slug}.${config.format}`;

  const siteId = parsed.siteId ?? "__draft";

  let ref: AssetRef;
  try {
    const store = getAssetStore();
    const result = await store.save({
      siteId,
      buffer: imageBytes,
      originalName,
      mimeType: config.mime,
      role: parsed.role,
    });
    ref = result.ref;
    // Om AssetStore.save() inte gav alt-text (sker när vision-pipelinen
    // är avstängd eller failade) fyller vi med en role-specifik default
    // så img-taggen i genererade sajten aldrig får tom alt.
    if (!ref.alt || !ref.alt.trim()) {
      ref = { ...ref, alt: config.fallbackAlt };
    }
  } catch (caught) {
    const message =
      caught instanceof Error ? caught.message : "Okänt fel vid asset-spar.";
    console.error("[/api/generate-image] AssetStore.save misslyckades:", caught);
    return serverError(`Bilden genererades men kunde inte sparas: ${message}`);
  }

  return NextResponse.json(
    { ok: true, ref, aiGenerated: true, prompt: parsed.prompt },
    { status: 200 },
  );
}
