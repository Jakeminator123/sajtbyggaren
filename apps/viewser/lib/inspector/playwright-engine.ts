import type { Browser, Page } from "playwright";

import type { CapturedElement, ElementMapItem } from "@/lib/inspector/types";

/**
 * Playwright-motorn bakom inspector-routes.
 *
 * Porterad från sajtmaskins services/inspector-worker/server.mjs
 * (Jakob-OK 2026-06-10). Två körvägar delar den här koden:
 *
 *   1. Extern inspector-worker (docker, port 3310) — proxas via
 *      `tryInspectorWorker` när INSPECTOR_CAPTURE_WORKER_URL är satt.
 *      Workern kan INTE nå loopback-mål (egen SSRF-guard) så den används
 *      bara för publika preview-URL:er (vercel-sandbox).
 *   2. Lokal Playwright-fallback — `withInspectorPage` + collect/describe
 *      nedan. Kräver `playwright` (devDependency) och en installerad
 *      Chromium (`npx playwright install chromium`). Det är primärvägen
 *      för local-next-previews på operatörens maskin.
 *
 * In-page-utvärderingarna (kartläggning, punktbeskrivning, overlay) är
 * avsiktligt 1:1 med worker-originalet så att båda körvägarna ger samma
 * svar för samma sida.
 */

export const INSPECTOR_NAVIGATION_TIMEOUT_MS = 25_000;
const NETWORK_IDLE_TIMEOUT_MS = 8_000;

const WORKER_URL = process.env.INSPECTOR_CAPTURE_WORKER_URL?.trim() || "";
const WORKER_TOKEN = process.env.INSPECTOR_CAPTURE_WORKER_TOKEN?.trim() || "";
const WORKER_TIMEOUT_MS = (() => {
  const parsed = Number(
    process.env.INSPECTOR_CAPTURE_WORKER_TIMEOUT_MS || "12000",
  );
  if (!Number.isFinite(parsed)) return 12_000;
  return Math.max(1_000, Math.min(30_000, Math.round(parsed)));
})();

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function toNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number(value);
  return Number.NaN;
}

/**
 * Proxar en request till den externa inspector-workern. Returnerar `null`
 * när workern inte är konfigurerad, inte svarar eller svarar fel — då
 * faller anroparen vidare till den lokala Playwright-vägen.
 */
export async function tryInspectorWorker(
  endpointPath: "/capture" | "/element-map",
  payload: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  if (!WORKER_URL) return null;

  let endpoint: URL;
  try {
    endpoint = new URL(endpointPath, WORKER_URL);
  } catch {
    console.warn(
      "[inspector] Ogiltig INSPECTOR_CAPTURE_WORKER_URL — använder lokal fallback.",
    );
    return null;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), WORKER_TIMEOUT_MS);

  try {
    const headers: HeadersInit = { "content-type": "application/json" };
    if (WORKER_TOKEN) headers["x-inspector-token"] = WORKER_TOKEN;

    const response = await fetch(endpoint.toString(), {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const data = (await response.json().catch(() => null)) as Record<
      string,
      unknown
    > | null;
    if (response.ok && data) return data;

    const reason =
      data && typeof data.error === "string"
        ? data.error
        : `HTTP ${response.status}`;
    console.warn(
      `[inspector] Worker otillgänglig (${reason}) — använder lokal fallback.`,
    );
    return null;
  } catch (error) {
    const reason = error instanceof Error ? error.message : "okänt worker-fel";
    console.warn(
      `[inspector] Worker-request misslyckades (${reason}) — använder lokal fallback.`,
    );
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

export type InspectorPageUnavailable = {
  unavailable: true;
  /** Svensk operatörstext om varför lokal Playwright inte kan köras. */
  reason: string;
};

type PlaywrightModule = typeof import("playwright");

async function loadPlaywright(): Promise<
  PlaywrightModule | InspectorPageUnavailable
> {
  if (process.env.VERCEL === "1") {
    return {
      unavailable: true,
      reason:
        "Inspector kräver Playwright och kan inte köras hosted. Kör viewser lokalt, eller peka INSPECTOR_CAPTURE_WORKER_URL på en inspector-worker.",
    };
  }
  try {
    return await import("playwright");
  } catch {
    return {
      unavailable: true,
      reason:
        "Playwright saknas. Installera med `npm install` i apps/viewser och `npx playwright install chromium`, eller sätt INSPECTOR_CAPTURE_WORKER_URL.",
    };
  }
}

/**
 * Öppna mål-URL:en i en headless Chromium, vänta in stabil rendering och
 * kör `fn` mot sidan. Stänger alltid browsern. Returnerar
 * InspectorPageUnavailable när Playwright inte finns i denna miljö.
 */
export async function withInspectorPage<T>(
  targetUrl: string,
  viewport: { width: number; height: number },
  fn: (page: Page) => Promise<T>,
): Promise<T | InspectorPageUnavailable> {
  const playwright = await loadPlaywright();
  if ("unavailable" in playwright) return playwright;

  let browser: Browser | null = null;
  try {
    browser = await playwright.chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport,
      deviceScaleFactor: 2,
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    });
    await page.goto(targetUrl, {
      waitUntil: "domcontentloaded",
      timeout: INSPECTOR_NAVIGATION_TIMEOUT_MS,
    });
    await waitForStabilizedPage(page);
    return await fn(page);
  } finally {
    if (browser) {
      await browser.close().catch(() => undefined);
    }
  }
}

async function waitForStabilizedPage(page: Page): Promise<void> {
  await page
    .waitForLoadState("networkidle", { timeout: NETWORK_IDLE_TIMEOUT_MS })
    .catch(() => undefined);
  await page
    .waitForSelector("body > *:not(script):not(style)", {
      state: "attached",
      timeout: 4_000,
    })
    .catch(() => undefined);
  await page
    .evaluate(async () => {
      const fontsApi = (
        document as Document & { fonts?: { ready?: Promise<unknown> } }
      ).fonts;
      if (!fontsApi?.ready) return;
      try {
        await fontsApi.ready;
      } catch {
        // Font-laddningsfel får inte stoppa inspektionen.
      }
    })
    .catch(() => undefined);
  await page.waitForTimeout(500).catch(() => undefined);
}

/** Kartlägg synliga element på sidan (samma evaluering som worker-originalet). */
export async function collectElementMap(
  page: Page,
  maxElements: number,
): Promise<ElementMapItem[]> {
  // Vänta in att sidan faktiskt har synligt innehåll (SPA-hydrering kan
  // släpa efter networkidle); upp till 4 × 2 s precis som i originalet.
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const hasContent = await page
      .evaluate(() => {
        const els = document.querySelectorAll(
          "body *:not(script):not(style):not(noscript):not(link):not(meta)",
        );
        let visible = 0;
        for (const el of els) {
          try {
            const r = el.getBoundingClientRect();
            if (r.width > 10 && r.height > 10) visible += 1;
          } catch {
            // Element utan layout ignoreras.
          }
        }
        return visible >= 3;
      })
      .catch(() => false);
    if (hasContent) break;
    await page.waitForTimeout(2_000).catch(() => undefined);
  }

  return page.evaluate(
    (params) => {
      const skip = new Set([
        "script",
        "style",
        "noscript",
        "head",
        "meta",
        "link",
        "template",
        "html",
        "body",
      ]);
      const vpW = window.innerWidth || 1;
      const vpH = window.innerHeight || 1;
      const pct = (v: number, base: number) =>
        Math.round(Math.max(0, Math.min(1, v / base)) * 100 * 10) / 10;

      const cssEscape = (val: string) => {
        if (typeof CSS !== "undefined" && typeof CSS.escape === "function")
          return CSS.escape(val);
        return String(val).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
      };
      const buildSelector = (el: Element): string => {
        const parts: string[] = [];
        let cur: Element | null = el;
        while (cur && cur.nodeType === 1) {
          const tag = cur.tagName.toLowerCase();
          if (tag === "html") break;
          const id = cur.getAttribute("id");
          if (id) {
            parts.unshift("#" + cssEscape(id));
            break;
          }
          const cls = (cur.getAttribute("class") || "")
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((c) => "." + cssEscape(c))
            .join("");
          const curTagName: string = cur.tagName;
          const parent: Element | null = cur.parentElement;
          let nth = 1;
          if (parent) {
            const siblings = (Array.from(parent.children) as Element[]).filter(
              (c) => c.tagName === curTagName,
            );
            nth = Math.max(1, siblings.indexOf(cur) + 1);
          }
          parts.unshift(tag + cls + ":nth-of-type(" + nth + ")");
          cur = parent;
        }
        return parts.join(" > ");
      };

      const all = Array.from(document.querySelectorAll("*")).filter((el) => {
        const tag = (el.tagName || "").toLowerCase();
        if (skip.has(tag)) return false;
        let r: DOMRect;
        try {
          r = el.getBoundingClientRect();
        } catch {
          return false;
        }
        return Boolean(r) && r.width > 2 && r.height > 2;
      });

      return all.slice(0, params.max).map((el) => {
        const r = el.getBoundingClientRect();
        const tag = el.tagName.toLowerCase();
        const text =
          ((el as HTMLElement).innerText || el.textContent || "")
            .trim()
            .replace(/\s+/g, " ")
            .slice(0, 120) || null;
        const className =
          (typeof el.className === "string" ? el.className.trim() : "") || null;
        return {
          tag,
          id: el.id || null,
          className,
          text,
          selector: buildSelector(el),
          rect: {
            x: Math.round(r.left),
            y: Math.round(r.top),
            width: Math.round(r.width),
            height: Math.round(r.height),
          },
          vpPercent: {
            x: pct(r.left, vpW),
            y: pct(r.top, vpH),
            w: pct(r.width, vpW),
            h: pct(r.height, vpH),
          },
        };
      });
    },
    { max: maxElements },
  );
}

export type CapturePointDetails = {
  pointSummary: string;
  element?: CapturedElement;
  resolvedX: number;
  resolvedY: number;
};

/**
 * Beskriv elementet närmast en punkt. Söker i en offset-spiral runt
 * klickpunkten och poängsätter kandidater (interaktiva element vinner)
 * — samma heuristik som worker-originalet.
 */
export async function describePoint(
  page: Page,
  x: number,
  y: number,
): Promise<CapturePointDetails> {
  return page.evaluate(
    ({ pointX, pointY }) => {
      const cleanText = (value: string | null | undefined): string | null => {
        if (!value) return null;
        const normalized = String(value).replace(/\s+/g, " ").trim();
        if (!normalized) return null;
        return normalized.slice(0, 160);
      };

      const cssEscape = (value: string) => {
        if (typeof CSS !== "undefined" && typeof CSS.escape === "function")
          return CSS.escape(value);
        return value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
      };

      const buildSelector = (el: Element): string | null => {
        const parts: string[] = [];
        let current: Element | null = el;
        while (current && current.nodeType === Node.ELEMENT_NODE) {
          const tag = current.tagName.toLowerCase();
          if (tag === "html") break;
          const id = current.getAttribute("id");
          if (id) {
            parts.unshift(`#${cssEscape(id)}`);
            break;
          }
          const classNames = (current.getAttribute("class") || "")
            .split(/\s+/)
            .map((item) => item.trim())
            .filter(Boolean)
            .slice(0, 2)
            .map((item) => `.${cssEscape(item)}`)
            .join("");
          const currentTagName: string = current.tagName;
          const parentElement: Element | null = current.parentElement;
          let nth = 1;
          if (parentElement) {
            const siblings = (
              Array.from(parentElement.children) as Element[]
            ).filter((candidate) => candidate.tagName === currentTagName);
            nth = Math.max(1, siblings.indexOf(current) + 1);
          }
          parts.unshift(`${tag}${classNames}:nth-of-type(${nth})`);
          current = parentElement;
        }
        return parts.length > 0 ? parts.join(" > ") : null;
      };

      const maxX = Math.max(0, window.innerWidth - 1);
      const maxY = Math.max(0, window.innerHeight - 1);
      const clampCoord = (value: number, max: number) =>
        Math.max(0, Math.min(max, Math.round(value)));
      const cleanTag = (el: Element | null | undefined) =>
        (el?.tagName || "").toLowerCase();
      const isRootLike = (el: Element | null | undefined) => {
        const tag = cleanTag(el);
        return (
          tag === "html" ||
          tag === "body" ||
          tag === "head" ||
          tag === "style" ||
          tag === "script"
        );
      };

      const pickAtPoint = (
        sampleX: number,
        sampleY: number,
      ): HTMLElement | null => {
        const stack = document.elementsFromPoint(sampleX, sampleY);
        const firstUseful = stack.find((entry) => !isRootLike(entry));
        if (firstUseful instanceof HTMLElement) return firstUseful;
        const fallback = document.elementFromPoint(sampleX, sampleY);
        return fallback instanceof HTMLElement ? fallback : null;
      };

      const offsets: Array<[number, number]> = [
        [0, 0],
        [-12, 0],
        [12, 0],
        [0, -12],
        [0, 12],
        [-24, 0],
        [24, 0],
        [0, -24],
        [0, 24],
        [-36, -12],
        [36, -12],
        [-36, 12],
        [36, 12],
        [-52, 0],
        [52, 0],
        [0, -52],
        [0, 52],
      ];
      const interactiveTags = new Set([
        "button",
        "a",
        "input",
        "select",
        "textarea",
        "summary",
        "label",
      ]);
      const interactiveRoles = new Set([
        "button",
        "link",
        "menuitem",
        "tab",
        "switch",
        "checkbox",
      ]);

      let best: {
        element: HTMLElement;
        x: number;
        y: number;
        score: number;
      } | null = null;

      for (const [dx, dy] of offsets) {
        const sampleX = clampCoord(pointX + dx, maxX);
        const sampleY = clampCoord(pointY + dy, maxY);
        const candidate = pickAtPoint(sampleX, sampleY);
        if (!candidate) continue;

        const tag = candidate.tagName.toLowerCase();
        const role = (candidate.getAttribute("role") || "").toLowerCase();
        const candidateText = cleanText(
          candidate.innerText || candidate.textContent || "",
        );
        const distance = Math.hypot(dx, dy);

        let score = 0;
        if (!isRootLike(candidate)) score += 45;
        if (interactiveTags.has(tag)) score += 85;
        if (interactiveRoles.has(role)) score += 65;
        if (candidate.closest("button,a,[role='button'],[role='link']"))
          score += 42;
        if (candidate.id) score += 20;
        if (String(candidate.className || "").trim()) score += 8;
        if (candidateText) score += Math.min(36, candidateText.length / 4);
        score -= distance * 0.9;

        if (!best || score > best.score) {
          best = { element: candidate, x: sampleX, y: sampleY, score };
        }
      }

      const resolvedX = best?.x ?? clampCoord(pointX, maxX);
      const resolvedY = best?.y ?? clampCoord(pointY, maxY);
      const target = best?.element ?? pickAtPoint(resolvedX, resolvedY);
      if (!target) {
        return {
          pointSummary: `Ingen DOM-träff vid x=${Math.round(pointX)}, y=${Math.round(pointY)}.`,
          resolvedX,
          resolvedY,
        };
      }

      const element = target;
      const id = element.id || null;
      const className = cleanText(element.className || null);
      const text = cleanText(element.innerText || element.textContent || null);
      const ariaLabel = cleanText(element.getAttribute("aria-label"));
      const role = cleanText(element.getAttribute("role"));
      const href =
        element instanceof HTMLAnchorElement
          ? cleanText(element.href)
          : cleanText(element.getAttribute("href"));
      const selector = buildSelector(element);

      let nearestHeading: string | null = null;
      let headingCandidate: Element | null =
        element.closest("h1,h2,h3,h4,h5,h6");
      if (!headingCandidate) {
        const sectionRoot =
          element.closest("section,article,main,aside,nav,header,footer") ||
          element.parentElement;
        headingCandidate =
          sectionRoot?.querySelector?.("h1,h2,h3,h4,h5,h6") || null;
      }
      if (headingCandidate) {
        nearestHeading = cleanText(
          (headingCandidate as HTMLElement).innerText ||
            headingCandidate.textContent ||
            "",
        );
      }

      const shortTag = element.tagName.toLowerCase();
      const adjusted =
        Math.abs(resolvedX - pointX) > 0.5 ||
        Math.abs(resolvedY - pointY) > 0.5;
      const adjustedPart = adjusted
        ? ` (justerad från klick x=${Math.round(pointX)}, y=${Math.round(pointY)})`
        : "";
      const textPart = text ? ` text="${text}"` : "";
      const headingPart = nearestHeading
        ? ` närmast rubrik="${nearestHeading}"`
        : "";
      const summary = `Träffade <${shortTag}> vid x=${Math.round(resolvedX)}, y=${Math.round(resolvedY)}${adjustedPart}.${textPart}${headingPart}`;

      return {
        pointSummary: summary,
        resolvedX,
        resolvedY,
        element: {
          tag: shortTag,
          id,
          className,
          text,
          ariaLabel,
          role,
          href,
          selector,
          nearestHeading,
        },
      };
    },
    { pointX: x, pointY: y },
  ) as Promise<CapturePointDetails>;
}

/** Rita kryssmarkör + pulsande punkt vid capture-punkten innan screenshot. */
export async function drawCaptureOverlay(
  page: Page,
  x: number,
  y: number,
  xPercent: number,
  yPercent: number,
): Promise<void> {
  await page.evaluate(
    ({ pointX, pointY, pointXPercent, pointYPercent }) => {
      const previous = document.getElementById(
        "__sajtbyggaren_capture_overlay__",
      );
      if (previous) previous.remove();

      const overlay = document.createElement("div");
      overlay.id = "__sajtbyggaren_capture_overlay__";
      overlay.style.position = "fixed";
      overlay.style.inset = "0";
      overlay.style.pointerEvents = "none";
      overlay.style.zIndex = "2147483647";

      const style = document.createElement("style");
      style.textContent = `
        @keyframes sajtbyggarenCapturePulse {
          0% { transform: translate(-50%, -50%) scale(0.55); opacity: 0.95; }
          80% { transform: translate(-50%, -50%) scale(1.8); opacity: 0; }
          100% { opacity: 0; }
        }
        @keyframes sajtbyggarenCaptureDot {
          0%, 100% { transform: translate(-50%, -50%) scale(1); }
          50% { transform: translate(-50%, -50%) scale(0.86); }
        }
      `;

      const crossH = document.createElement("div");
      crossH.style.position = "absolute";
      crossH.style.left = "0";
      crossH.style.top = `${pointY}px`;
      crossH.style.width = "100%";
      crossH.style.height = "2px";
      crossH.style.background = "rgba(244, 63, 94, 0.9)";
      crossH.style.boxShadow = "0 0 0 1px rgba(0,0,0,0.35)";

      const crossV = document.createElement("div");
      crossV.style.position = "absolute";
      crossV.style.left = `${pointX}px`;
      crossV.style.top = "0";
      crossV.style.width = "2px";
      crossV.style.height = "100%";
      crossV.style.background = "rgba(244, 63, 94, 0.9)";
      crossV.style.boxShadow = "0 0 0 1px rgba(0,0,0,0.35)";

      const pulse = document.createElement("div");
      pulse.style.position = "absolute";
      pulse.style.left = `${pointX}px`;
      pulse.style.top = `${pointY}px`;
      pulse.style.width = "44px";
      pulse.style.height = "44px";
      pulse.style.border = "3px solid rgba(244, 63, 94, 0.95)";
      pulse.style.borderRadius = "999px";
      pulse.style.animation =
        "sajtbyggarenCapturePulse 900ms ease-out infinite";
      pulse.style.boxShadow = "0 0 0 1px rgba(0,0,0,0.35)";
      pulse.style.transform = "translate(-50%, -50%)";

      const marker = document.createElement("div");
      marker.style.position = "absolute";
      marker.style.left = `${pointX}px`;
      marker.style.top = `${pointY}px`;
      marker.style.width = "14px";
      marker.style.height = "14px";
      marker.style.borderRadius = "999px";
      marker.style.background = "rgba(244, 63, 94, 1)";
      marker.style.border = "2px solid rgba(255,255,255,0.9)";
      marker.style.boxShadow =
        "0 0 0 2px rgba(0,0,0,0.35), 0 0 14px rgba(244, 63, 94, 0.95)";
      marker.style.animation =
        "sajtbyggarenCaptureDot 900ms ease-in-out infinite";
      marker.style.transform = "translate(-50%, -50%)";

      const label = document.createElement("div");
      label.textContent = `Punkt x ${pointXPercent.toFixed(1)}% • y ${pointYPercent.toFixed(1)}%`;
      label.style.position = "absolute";
      label.style.left = `${Math.max(8, Math.min(window.innerWidth - 240, pointX + 18))}px`;
      label.style.top = `${Math.max(8, Math.min(window.innerHeight - 42, pointY - 42))}px`;
      label.style.padding = "6px 9px";
      label.style.borderRadius = "8px";
      label.style.font =
        "600 12px system-ui, -apple-system, Segoe UI, sans-serif";
      label.style.color = "#ecfeff";
      label.style.background = "rgba(3, 7, 18, 0.82)";
      label.style.border = "1px solid rgba(244, 63, 94, 0.65)";
      label.style.boxShadow = "0 4px 14px rgba(0,0,0,0.35)";

      overlay.appendChild(style);
      overlay.appendChild(crossH);
      overlay.appendChild(crossV);
      overlay.appendChild(pulse);
      overlay.appendChild(marker);
      overlay.appendChild(label);
      (document.body || document.documentElement).appendChild(overlay);
    },
    { pointX: x, pointY: y, pointXPercent: xPercent, pointYPercent: yPercent },
  );

  await page.waitForTimeout(260).catch(() => undefined);
}
