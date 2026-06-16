// UI/UX designer-canary mot produktion. Navigerar de centrala ytorna i
// desktop + mobil, öppnar discovery-wizarden, och loggar console-varningar.
// Read-only mot prod: triggar ALDRIG ett riktigt bygge (klickar aldrig den
// slutgiltiga "Skapa sajt"/"Bygg"-knappen). Skärmdumpar -> OUT_DIR.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.CANARY_BASE || "https://sajtbyggaren-viewser.vercel.app";
const OUT_DIR =
  process.env.CANARY_OUT ||
  join(process.cwd(), "..", "..", "audits", "uiux-canary-2026-06-14");
mkdirSync(OUT_DIR, { recursive: true });

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

const consoleLog = [];
const results = [];

function attachConsole(page, label) {
  page.on("console", (msg) => {
    const type = msg.type();
    if (type === "warning" || type === "error") {
      consoleLog.push({ label, type, text: msg.text().slice(0, 300) });
    }
  });
  page.on("pageerror", (err) => {
    consoleLog.push({ label, type: "pageerror", text: String(err).slice(0, 300) });
  });
}

async function shot(page, name, { fullPage = true } = {}) {
  const file = join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage });
  results.push(name);
  console.log("  shot:", name);
}

async function settle(page, ms = 1200) {
  try {
    await page.waitForLoadState("networkidle", { timeout: 8000 });
  } catch {}
  await page.waitForTimeout(ms);
}

async function captureRoute(browser, route, slug, viewport, tag) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  attachConsole(page, `${slug}-${tag}`);
  try {
    console.log(`Route ${route} [${tag}]`);
    await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await settle(page);
    await shot(page, `${slug}-${tag}`);
  } catch (e) {
    console.log(`  FEL ${route} [${tag}]:`, String(e).slice(0, 160));
  } finally {
    await ctx.close();
  }
}

async function captureWizard(browser) {
  // Öppna discovery-wizarden från startsidan/studio utan att bygga.
  const ctx = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  attachConsole(page, "wizard");
  try {
    console.log("Wizard-flöde [desktop]");
    await page.goto(`${BASE}/studio`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await settle(page);
    await shot(page, "studio-empty-desktop");

    // Försök hitta en starter-chip / "Skapa sajt"-ingång som öppnar wizarden.
    const openers = [
      'button:has-text("Skapa sajt")',
      'button:has-text("Kom igång")',
      'button:has-text("Beskriv")',
      'text=/frisör|bageri|snickare|café|restaurang/i',
    ];
    let opened = false;
    for (const sel of openers) {
      const el = page.locator(sel).first();
      if ((await el.count()) > 0) {
        try {
          await el.click({ timeout: 3000 });
          await settle(page, 1500);
          opened = true;
          break;
        } catch {}
      }
    }
    if (opened) {
      await shot(page, "wizard-step1-desktop");
      // Klicka vidare genom stegen (utan slutbygge) och skärmdumpa varje steg.
      for (let i = 2; i <= 6; i++) {
        const next = page
          .locator('button:has-text("Nästa"), button:has-text("Fortsätt")')
          .first();
        if ((await next.count()) === 0 || !(await next.isEnabled().catch(() => false))) break;
        try {
          await next.click({ timeout: 3000 });
          await settle(page, 1200);
          await shot(page, `wizard-step${i}-desktop`);
        } catch {
          break;
        }
      }
    } else {
      console.log("  (kunde inte öppna wizarden via kända selektorer)");
    }
  } catch (e) {
    console.log("  FEL wizard:", String(e).slice(0, 160));
  } finally {
    await ctx.close();
  }
}

async function discoverProfession(browser) {
  const ctx = await browser.newContext({ viewport: DESKTOP });
  const page = await ctx.newPage();
  try {
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await settle(page);
    const href = await page
      .locator('a[href*="/for/"]')
      .first()
      .getAttribute("href")
      .catch(() => null);
    return href;
  } finally {
    await ctx.close();
  }
}

async function main() {
  const browser = await chromium.launch();
  try {
    // 1. Startsida
    await captureRoute(browser, "/", "home", DESKTOP, "desktop");
    await captureRoute(browser, "/", "home", MOBILE, "mobile");

    // 2. Yrkessida (om en länk hittas)
    const prof = await discoverProfession(browser);
    if (prof) {
      await captureRoute(browser, prof, "profession", DESKTOP, "desktop");
      await captureRoute(browser, prof, "profession", MOBILE, "mobile");
    } else {
      console.log("Ingen /for/-länk hittad på startsidan");
    }

    // 3. Studio/konsol
    await captureRoute(browser, "/studio", "studio", MOBILE, "mobile");

    // 4. Wizard-flöde
    await captureWizard(browser);
  } finally {
    await browser.close();
  }

  console.log("\n=== KLART ===");
  console.log("Skärmdumpar:", results.length, "->", OUT_DIR);
  console.log("\n=== CONSOLE-VARNINGAR/FEL ===");
  if (consoleLog.length === 0) console.log("  (inga)");
  for (const c of consoleLog) console.log(`  [${c.label}] ${c.type}: ${c.text}`);
}

main().catch((e) => {
  console.error("CANARY-FEL:", e);
  process.exit(1);
});
