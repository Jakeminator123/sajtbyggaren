import assert from "node:assert/strict";

import {
  filterPrebuiltRelPaths,
  hasPrebuiltNextRelPath,
  MANIFEST_RELPATH,
  selectServedRelPaths,
} from "./generated-blob-source";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;

// B195: ``selectServedRelPaths`` är kärnan i stale-blob-cleanupen. Hostat bygge
// laddar upp filer med overwrite per fil men raderar ALDRIG blobbar som
// försvunnit mellan två byggen mot samma siteId. Manifestet (publicerat sist av
// bygget) listar det aktuella byggets exakta fil-set; serveringen får bara visa
// de filerna så en borttagen route/asset inte ligger kvar stale i previewen.
describe("selectServedRelPaths (B195 stale-blob-cleanup)", () => {
  it("serverar bara manifest-listade filer och ignorerar stale blobbar", () => {
    // ``stale/old-page.html`` finns kvar i blob (overwrite raderar den inte)
    // men saknas i det nya byggets manifest → ska INTE serveras.
    const listed = ["index.html", "about.html", "stale/old-page.html"];
    const manifest = ["index.html", "about.html"];

    const served = selectServedRelPaths(listed, manifest);

    assert.deepEqual(served, ["index.html", "about.html"]);
    assert.equal(served.includes("stale/old-page.html"), false);
  });

  it("faller tillbaka till hela listningen utan manifest (bakåtkompatibelt)", () => {
    const listed = ["index.html", "legacy/asset.png"];

    const served = selectServedRelPaths(listed, null);

    assert.deepEqual(served.sort(), ["index.html", "legacy/asset.png"]);
  });

  it("serverar aldrig själva manifest-filen", () => {
    const listed = [MANIFEST_RELPATH, "index.html"];
    const manifest = [MANIFEST_RELPATH, "index.html"];

    const served = selectServedRelPaths(listed, manifest);

    assert.deepEqual(served, ["index.html"]);
    assert.equal(served.includes(MANIFEST_RELPATH), false);
  });

  it("hoppar defensivt över en manifest-post vars blob saknas", () => {
    // Manifestet refererar ``missing.html`` men ingen sådan blob listades
    // (t.ex. en enstaka PUT som försvann) → uteslut den hellre än att 404:a.
    const listed = ["index.html"];
    const manifest = ["index.html", "missing.html"];

    const served = selectServedRelPaths(listed, manifest);

    assert.deepEqual(served, ["index.html"]);
  });

  it("avduplicerar och bevarar manifestets ordning", () => {
    const listed = ["b.html", "a.html", "c.html"];
    const manifest = ["c.html", "a.html", "c.html", "b.html"];

    const served = selectServedRelPaths(listed, manifest);

    assert.deepEqual(served, ["c.html", "a.html", "b.html"]);
  });

  it("behandlar ett tomt manifest som 'servera ingenting' (inte fallback)", () => {
    const listed = ["index.html", "stale.html"];

    const served = selectServedRelPaths(listed, []);

    assert.deepEqual(served, []);
  });
});

// Hostad pre-built (2026-06-12): hostade byggen laddar upp .next (minus
// cache/trace) så preview-sandboxen kan köra next start utan eget bygge.
// filterPrebuiltRelPaths avgör om .next-filerna ska dras ner ur blob.
describe("filterPrebuiltRelPaths (hostad pre-built)", () => {
  const relPaths = [
    "package.json",
    "app/page.tsx",
    ".next/BUILD_ID",
    ".next/server/app/page.js",
    ".next/cache/webpack/0.pack",
    ".next/trace",
    ".next/trace/events.json",
  ];

  it("utan pre-built: allt under .next/ utelämnas (gamla beteendet)", () => {
    const filtered = filterPrebuiltRelPaths(relPaths, false);

    assert.deepEqual(filtered, ["package.json", "app/page.tsx"]);
  });

  it("med pre-built: .next/** följer med, men aldrig cache/trace", () => {
    const filtered = filterPrebuiltRelPaths(relPaths, true);

    assert.deepEqual(filtered, [
      "package.json",
      "app/page.tsx",
      ".next/BUILD_ID",
      ".next/server/app/page.js",
    ]);
  });

  it("rör aldrig vanliga källfiler vars namn råkar likna .next", () => {
    const filtered = filterPrebuiltRelPaths(
      ["app/.nextish/file.ts", "docs/.next.md"],
      false,
    );

    assert.deepEqual(filtered, ["app/.nextish/file.ts", "docs/.next.md"]);
  });
});

describe("hasPrebuiltNextRelPath (BUILD_ID-readiness)", () => {
  it("kräver exakt .next/BUILD_ID — samma kontrakt som disk-vägen", () => {
    assert.equal(hasPrebuiltNextRelPath([".next/BUILD_ID", "a.js"]), true);
    assert.equal(hasPrebuiltNextRelPath([".next/server/x.js"]), false);
    assert.equal(hasPrebuiltNextRelPath([]), false);
  });
});
