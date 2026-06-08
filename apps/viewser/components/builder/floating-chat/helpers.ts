import {
  PANEL_MAX_HEIGHT,
  PANEL_MAX_WIDTH,
  PANEL_MIN_HEIGHT,
  PANEL_MIN_WIDTH,
  TOOLBAR_ROW_HEIGHT,
  VIEWPORT_PADDING,
} from "./constants";
import type { ErrorKind, Position, Size } from "./types";

/**
 * Tolka ett backend-felmeddelande och returnera en kort, åtgärdsbar
 * text + ett "tips" för operatören. Vi ser specifika fel oftast
 * (OpenAI/Anthropic rate-limits, schema-valideringar, timeout) och
 * vill ge användaren något konkret att göra istället för bara
 * generic "Bygget misslyckades".
 *
 * Mappningen bygger på faktiska error-strängar från
 * `apps/viewser/lib/build-runner.ts` och `scripts/build_site.py`.
 * När en sträng inte matchar någon känd kategori returneras en
 * generic-tip som ändå är bättre än "okänt fel".
 */
export function classifyFollowupError(rawError: string): {
  kind: ErrorKind;
  message: string;
  tip: string;
} {
  const text = rawError.toLowerCase();
  if (text.includes("rate limit") || text.includes("429")) {
    return {
      kind: "rate-limit",
      message: "AI-tjänsten är överbelastad just nu.",
      tip: "Vänta 10–20 sekunder och försök igen.",
    };
  }
  if (text.includes("timeout") || text.includes("timed out")) {
    return {
      kind: "timeout",
      message: "Bygget tog för lång tid.",
      tip: "Prova en mindre, mer specifik ändring.",
    };
  }
  if (
    text.includes("schema") ||
    text.includes("validation") ||
    text.includes("invalid")
  ) {
    return {
      kind: "schema",
      message: "Sajtens struktur kunde inte uppdateras automatiskt.",
      tip: "Beskriv ändringen mer konkret (vilken sektion, vad ska ändras).",
    };
  }
  if (
    text.includes("openai") ||
    text.includes("anthropic") ||
    text.includes("api key")
  ) {
    return {
      kind: "auth",
      message: "AI-tjänsten är otillgänglig.",
      tip: "Kontrollera att .env.local har giltig OPENAI_API_KEY.",
    };
  }
  if (
    text.includes("quality") ||
    text.includes("typecheck") ||
    text.includes("build failed")
  ) {
    return {
      kind: "quality",
      message: "Den nya versionen klarade inte Quality Gate.",
      tip: "Pipelinen avbröt automatiskt — sajten är oförändrad. Prova en mer specifik instruktion.",
    };
  }
  if (
    text.includes("network") ||
    text.includes("fetch") ||
    text.includes("econnreset")
  ) {
    return {
      kind: "network",
      message: "Nätverket avbröts.",
      tip: "Kontrollera anslutningen och försök igen.",
    };
  }
  return {
    kind: "generic",
    message: rawError.length > 200 ? rawError.slice(0, 200) + "…" : rawError,
    tip: "Prova en mer specifik instruktion eller dela upp ändringen i flera steg.",
  };
}

export function clampToViewport(
  pos: Position,
  width: number,
  height: number,
): Position {
  if (typeof window === "undefined") return pos;
  const maxX = Math.max(
    VIEWPORT_PADDING,
    window.innerWidth - width - VIEWPORT_PADDING,
  );
  const maxY = Math.max(
    VIEWPORT_PADDING,
    window.innerHeight - height - VIEWPORT_PADDING,
  );
  return {
    x: Math.min(Math.max(VIEWPORT_PADDING, pos.x), maxX),
    y: Math.min(Math.max(VIEWPORT_PADDING, pos.y), maxY),
  };
}

// Clamp:ar panel-storleken mot min/max-konstanterna OCH viewporten så att
// panelen + toolbar-raden (TOOLBAR_ROW_HEIGHT) alltid får plats med
// VIEWPORT_PADDING på båda kanter. Anropas vid hydrering, under resize-drag
// och vid window-resize.
export function clampSize(size: Size): Size {
  const maxWidth =
    typeof window !== "undefined"
      ? Math.min(PANEL_MAX_WIDTH, window.innerWidth - 2 * VIEWPORT_PADDING)
      : PANEL_MAX_WIDTH;
  const maxHeight =
    typeof window !== "undefined"
      ? Math.min(
          PANEL_MAX_HEIGHT,
          window.innerHeight - TOOLBAR_ROW_HEIGHT - 2 * VIEWPORT_PADDING,
        )
      : PANEL_MAX_HEIGHT;
  return {
    width: Math.min(
      Math.max(PANEL_MIN_WIDTH, size.width),
      Math.max(PANEL_MIN_WIDTH, maxWidth),
    ),
    height: Math.min(
      Math.max(PANEL_MIN_HEIGHT, size.height),
      Math.max(PANEL_MIN_HEIGHT, maxHeight),
    ),
  };
}

export function defaultPosition(width: number, height: number): Position {
  if (typeof window === "undefined") return { x: 0, y: 0 };
  return clampToViewport(
    {
      x: window.innerWidth - width - VIEWPORT_PADDING,
      y: window.innerHeight - height - VIEWPORT_PADDING,
    },
    width,
    height,
  );
}
