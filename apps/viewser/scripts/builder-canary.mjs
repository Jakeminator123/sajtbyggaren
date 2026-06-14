// Builder-flödes-canary mot produktion.
//
// Till skillnad från uiux-canary.mjs (read-only, bygger ALDRIG) kör den här
// HELA kundresan: startsida → beskriv → wizard → "Skapa sajt" → buildern, och
// fångar exakt VAR det fallerar:
//   - console-varningar/fel + pageerror per fas
//   - varje /api/*-svar (status + metod), med body för de kritiska anropen
//     (/api/prompt, /api/preview, /api/runs)
//   - requestfailed (nätverk som dör)
//   - skärmdumpar vid varje milstolpe OCH vid fel
//
// OBS: detta TRIGGAR ett riktigt bygge på prod (ett /api/prompt-anrop).
// Avsiktligt — vi vill se var buildern brister. Rate limit: 3 req / 300 s.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.CANARY_BASE || "https://sajtbyggaren-viewser.vercel.app";
const OUT_DIR =
  process.env.CANARY_OUT ||
  join(process.cwd(), "..", "..", "audits", "builder-canary-2026-06-14");
mkdirSync(OUT_DIR, { recursive: true });

const DESKTOP = { width: 1440, height: 900 };

const consoleLog = [];
const apiLog = [];
const netFail = [];
const shots = [];
let report_outcome = null;

function logPhase(msg) {
  console.log(msg);
}

function attachInstrumentation(page) {
  page.on("console", (msg) => {
    const type = msg.type();
    if (type === "warning" || type === "error") {
      consoleLog.push({ type, text: msg.text().slice(0, 400) });
    }
  });
  page.on("pageerror", (err) => {
    consoleLog.push({ type: "pageerror", text: String(err).slice(0, 400) });
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (url.includes("/api/") || url.startsWith(BASE)) {
      netFail.push({ url: url.slice(0, 200), reason: req.failure()?.errorText ?? "?" });
    }
  });
  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    const entry = {
      method: res.request().method(),
      status: res.status(),
      url: url.replace(BASE, "").slice(0, 160),
    };
    // Body för de kritiska JSON-anropen. /api/prompt UTESLUTS — det är en
    // NDJSON-stream och res.text() skulle hänga upp till maxDuration (300 s).
    if (/\/api\/(preview|runs)/.test(url)) {
      try {
        const text = await res.text();
        entry.body = text.slice(0, 1200);
      } catch {
        entry.body = "(kunde inte läsa body)";
      }
    }
    apiLog.push(entry);
  });
}

async function shot(page, name) {
  const file = join(OUT_DIR, `${name}.png`);
  try {
    await page.screenshot({ path: file, fullPage: false });
    shots.push(name);
    console.log("  shot:", name);
  } catch (e) {
    console.log("  shot-FEL", name, String(e).slice(0, 120));
  }
}

async function settle(page, ms = 1200) {
  try {
    await page.waitForLoadState("networkidle", { timeout: 8000 });
  } catch {}
  await page.waitForTimeout(ms);
}

async function clickIfPresent(page, selector, { timeout = 4000 } = {}) {
  const el = page.locator(selector).first();
  if ((await el.count()) === 0) return false;
  try {
    await el.click({ timeout });
    return true;
  } catch {
    return false;
  }
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  attachInstrumentation(page);

  try {
    // 1. Startsida
    logPhase("1. Startsida");
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await settle(page);
    await shot(page, "01-home");

    // 2. Beskriv + öppna wizarden via hero-prompten
    logPhase("2. Fyll hero-prompt + öppna wizard");
    const ta = page.locator("#hero-prompt");
    if ((await ta.count()) > 0) {
      await ta.fill(
        "Vi är en liten frisörsalong i Visby som vill ha en enkel hemsida med priser, öppettider och bokning.",
      );
    }
    // Submit-pilen (aria-label="Bygg din hemsida") öppnar wizarden på heron.
    let opened = await clickIfPresent(page, 'button[aria-label="Bygg din hemsida"]');
    if (!opened) {
      // Fallback: klicka en starter-chip.
      opened = await clickIfPresent(page, 'button:has-text("Frisörsalong")');
    }
    await settle(page, 1800);
    const wizardVisible =
      (await page.locator('[role="dialog"]').count()) > 0 ||
      (await page.locator('button:has-text("Skapa sajt")').count()) > 0 ||
      (await page.locator('button:has-text("Fortsätt")').count()) > 0;
    logPhase(`   wizard öppen: ${wizardVisible}`);
    await shot(page, "02-wizard-open");

    if (!wizardVisible) {
      logPhase("   KUNDE INTE öppna wizarden — avbryter byggförsök.");
    } else {
      // 3. Fyll demo-profil (klarar alla obligatoriska fält)
      logPhase("3. Fyll demo-profil");
      const demo = await clickIfPresent(
        page,
        'button[aria-label="Fyll wizarden med en demo-profil"]',
      );
      logPhase(`   demo-fyllning klickad: ${demo}`);
      await settle(page, 800);

      // 4. Stega till sista steget och tryck "Skapa sajt →"
      logPhase("4. Stega till sista steget");
      for (let i = 0; i < 6; i++) {
        const create = page.locator('button:has-text("Skapa sajt")').first();
        if ((await create.count()) > 0 && (await create.isVisible().catch(() => false))) {
          break;
        }
        const next = page.locator('button:has-text("Fortsätt")').first();
        if ((await next.count()) === 0) break;
        const enabled = await next.isEnabled().catch(() => false);
        if (!enabled) {
          logPhase(`   "Fortsätt" disabled på steg ${i} (validationError?)`);
          break;
        }
        await next.click({ timeout: 4000 }).catch(() => {});
        await settle(page, 700);
      }
      await shot(page, "03-wizard-last-step");

      // 5. Klicka "Skapa sajt →". Hostat /api/prompt är en NDJSON-STREAM:
      //    200-headern kommer direkt men bygget kör detached i en sandbox och
      //    tar 1-3 min (maxDuration 300 s). waitForResponse löser därför direkt
      //    — vi får INTE lita på det som "klart". I stället pollar vi UI:t.
      logPhase("5. Klicka 'Skapa sajt'");
      page
        .waitForResponse((r) => /\/api\/prompt/.test(r.url()), { timeout: 60000 })
        .then((r) => logPhase(`   /api/prompt headers -> HTTP ${r.status()} (stream öppnad)`))
        .catch(() => logPhase("   /api/prompt-anrop sågs inte inom 60 s"));
      const created = await clickIfPresent(page, 'button:has-text("Skapa sajt")', {
        timeout: 6000,
      });
      logPhase(`   "Skapa sajt" klickad: ${created}`);
      await page.waitForTimeout(2500);
      await shot(page, "04-build-start");

      // 6. Poll:a tills buildern når ett terminalt tillstånd (preview-iframe,
      //    felbubbla eller "är aktiv"-builder), eller tills taket nås.
      logPhase("6. Pollar build-tillstånd (upp till ~6 min)");
      const POLL_MS = 20000;
      const MAX_POLLS = 18; // ~360 s
      let outcome = "okänt (tidsgräns)";
      for (let p = 1; p <= MAX_POLLS; p++) {
        await page.waitForTimeout(POLL_MS);
        const iframeCount = await page.locator("iframe").count().catch(() => 0);
        const buildingCard = await page
          .locator('text="Bygger din sajt"')
          .count()
          .catch(() => 0);
        const errorish = await page
          .locator('text=/misslyckades|kunde inte slutföras|något gick fel|tyvärr/i')
          .count()
          .catch(() => 0);
        const activeHeader = await page
          .locator('text=/är aktiv|förhandsvisning aktiv/i')
          .count()
          .catch(() => 0);
        logPhase(
          `   poll ${p}/${MAX_POLLS} (${p * (POLL_MS / 1000)}s): iframe=${iframeCount} byggkort=${buildingCard} fel=${errorish} aktiv=${activeHeader}`,
        );
        // Skärmdump var ~minut + alltid de första två pollarna.
        if (p <= 2 || p % 3 === 0) await shot(page, `05-poll-${String(p).padStart(2, "0")}`);
        if (iframeCount > 0) {
          outcome = "preview-iframe synlig (bygget landade)";
          break;
        }
        if (errorish > 0) {
          outcome = "felbubbla/fel-text synlig";
          break;
        }
        if (buildingCard === 0 && activeHeader > 0) {
          outcome = "builder aktiv utan iframe (preview ej startad?)";
          break;
        }
        if (buildingCard === 0 && p > 2) {
          outcome = "byggkort borta men ingen preview/fel — oklart sluttillstånd";
          break;
        }
      }
      logPhase(`   UTFALL: ${outcome}`);
      await settle(page, 2000);
      await shot(page, "06-builder-final");
      report_outcome = outcome;
    }
  } catch (e) {
    console.log("FLÖDES-FEL:", String(e).slice(0, 300));
    await shot(page, "99-exception");
  } finally {
    await ctx.close();
    await browser.close();
  }

  // Skriv rapport
  const report = {
    base: BASE,
    when: new Date().toISOString(),
    outcome: report_outcome,
    shots,
    consoleLog,
    apiLog,
    netFail,
  };
  writeFileSync(join(OUT_DIR, "report.json"), JSON.stringify(report, null, 2));

  console.log("\n=== KLART ===");
  console.log("Skärmdumpar:", shots.length, "->", OUT_DIR);

  console.log("\n=== API-ANROP ===");
  if (apiLog.length === 0) console.log("  (inga /api/-anrop sågs)");
  for (const a of apiLog) {
    console.log(`  ${a.method} ${a.status} ${a.url}`);
    if (a.body) console.log(`     body: ${a.body.replace(/\s+/g, " ").slice(0, 600)}`);
  }

  console.log("\n=== NÄTVERKSFEL ===");
  if (netFail.length === 0) console.log("  (inga)");
  for (const n of netFail) console.log(`  ${n.reason} ${n.url}`);

  console.log("\n=== CONSOLE-VARNINGAR/FEL ===");
  if (consoleLog.length === 0) console.log("  (inga)");
  for (const c of consoleLog) console.log(`  ${c.type}: ${c.text}`);
}

main().catch((e) => {
  console.error("CANARY-FEL:", e);
  process.exit(1);
});
