import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  assertSafeSiteId,
  BUILD_CONTEXT_PREFIX,
  classify,
  groupSites,
  isAuthorizedBearer,
  planPrune,
  pruneEnabled,
  resolveRetentionDays,
} from "./blob-prune.mjs";

const DAY = 24 * 60 * 60 * 1000;
const NOW = Date.UTC(2026, 5, 16); // fast referenstid

function blob(pathname, { size = 10, daysAgo = 0 } = {}) {
  return {
    pathname,
    url: `https://blob.test/${pathname}`,
    size,
    uploadedAt: new Date(NOW - daysAgo * DAY).toISOString(),
  };
}

// Retention/staleness är kärnan i auto-prunen (ADR 0063): en gammal sajt
// prunas, den senaste versionen behålls, och build-context/ rörs aldrig.
describe("planPrune (ADR 0063 retention/staleness)", () => {
  it("prunar en sajt vars senaste aktivitet är äldre än retention", () => {
    const sites = groupSites([
      blob("generated/old-site/index.html", { daysAgo: 40, size: 100 }),
      blob("run-state/old-site/v1", { daysAgo: 35, size: 5 }),
    ]);

    const plan = planPrune(sites, { now: NOW, retentionDays: 14 });

    assert.deepEqual(
      plan.prunedSites.map((e) => e.siteId),
      ["old-site"],
    );
    assert.equal(plan.keptSites.length, 0);
    assert.equal(plan.freedBytes, 105);
  });

  it("behåller en sajt vars SENASTE version är nyare än retention", () => {
    // Sajten har både ett gammalt objekt OCH en färsk version. Färskheten är
    // MAX(uploadedAt), så den senaste versionen håller hela sajten kvar.
    const sites = groupSites([
      blob("generated/active-site/old.html", { daysAgo: 90 }),
      blob("generated/active-site/index.html", { daysAgo: 2 }),
    ]);

    const plan = planPrune(sites, { now: NOW, retentionDays: 14 });

    assert.equal(plan.prunedSites.length, 0);
    assert.deepEqual(
      plan.keptSites.map((e) => e.siteId),
      ["active-site"],
    );
  });

  it("behåller sajter med okänd ålder (freshness 0)", () => {
    const sites = groupSites([
      { pathname: "generated/no-date/index.html", url: "u", size: 1 },
    ]);

    const plan = planPrune(sites, { now: NOW, retentionDays: 14 });

    assert.equal(plan.prunedSites.length, 0);
    assert.equal(plan.keptSites.length, 1);
  });

  it("låter run-state-pekarens updatedAt hålla en sajt kvar", () => {
    const sites = groupSites([
      blob("generated/pointer-fresh/index.html", { daysAgo: 30 }),
    ]);

    const plan = planPrune(sites, {
      now: NOW,
      retentionDays: 14,
      runStateUpdatedAt: { "pointer-fresh": NOW - 1 * DAY },
    });

    assert.equal(plan.prunedSites.length, 0);
    assert.equal(plan.keptSites.length, 1);
  });
});

// build-context/ (Python-motorn) är inte en sajt och får ALDRIG raderas.
describe("build-context-skydd", () => {
  it("klassificerar build-context/ som icke-sajt (siteId null)", () => {
    assert.equal(classify("build-context/current.tar.gz").siteId, null);
  });

  it("groupSites/planPrune tar aldrig med build-context", () => {
    const sites = groupSites([
      blob("build-context/current.tar.gz", { daysAgo: 999, size: 9999 }),
      blob("generated/old-site/index.html", { daysAgo: 40 }),
    ]);

    assert.deepEqual(
      sites.map((s) => s.siteId),
      ["old-site"],
    );
    const plan = planPrune(sites, { now: NOW, retentionDays: 14 });
    assert.equal(plan.prunedSites.some((e) => e.siteId === "build-context"), false);
  });

  it("assertSafeSiteId vägrar build-context och ogiltiga id", () => {
    assert.throws(() => assertSafeSiteId("build-context"), /build-context/);
    assert.throws(() => assertSafeSiteId(""), /Ogiltigt/);
    assert.throws(() => assertSafeSiteId("../x"), /Ogiltigt/);
    // ett vanligt siteId passerar
    assert.doesNotThrow(() => assertSafeSiteId("site-abc123"));
  });

  it("exponerar build-context-prefixet för routens/CLI:ts guard", () => {
    assert.equal(BUILD_CONTEXT_PREFIX, "build-context/");
  });
});

// Auth-grinden: utan giltig CRON_SECRET måste anropet avvisas (401-väg).
describe("isAuthorizedBearer (cron-auth)", () => {
  const req = (auth) => ({ headers: { get: () => auth } });

  it("nekar när secret saknas (deny-by-default)", () => {
    assert.equal(isAuthorizedBearer(req("Bearer x"), undefined), false);
    assert.equal(isAuthorizedBearer(req("Bearer x"), ""), false);
    assert.equal(isAuthorizedBearer(req("Bearer x"), "   "), false);
  });

  it("nekar saknad eller felaktig header", () => {
    assert.equal(isAuthorizedBearer(req(null), "s3cr3t"), false);
    assert.equal(isAuthorizedBearer(req("Bearer fel"), "s3cr3t"), false);
    assert.equal(isAuthorizedBearer(req("s3cr3t"), "s3cr3t"), false);
  });

  it("släpper igenom exakt 'Bearer <secret>'", () => {
    assert.equal(isAuthorizedBearer(req("Bearer s3cr3t"), "s3cr3t"), true);
    // trimmar secret men kräver exakt header-match
    assert.equal(isAuthorizedBearer(req("Bearer s3cr3t"), "  s3cr3t  "), true);
  });
});

describe("env-parsing", () => {
  it("resolveRetentionDays faller tillbaka på default vid ogiltigt", () => {
    assert.equal(resolveRetentionDays(undefined), 14);
    assert.equal(resolveRetentionDays(""), 14);
    assert.equal(resolveRetentionDays("abc"), 14);
    assert.equal(resolveRetentionDays("-3"), 14);
    assert.equal(resolveRetentionDays("30"), 30);
    assert.equal(resolveRetentionDays("0"), 0);
  });

  it("pruneEnabled är på som default och stängs av med 0/false/off/no", () => {
    assert.equal(pruneEnabled(undefined), true);
    assert.equal(pruneEnabled(""), true);
    assert.equal(pruneEnabled("true"), true);
    assert.equal(pruneEnabled("0"), false);
    assert.equal(pruneEnabled("false"), false);
    assert.equal(pruneEnabled("OFF"), false);
    assert.equal(pruneEnabled("no"), false);
  });
});
