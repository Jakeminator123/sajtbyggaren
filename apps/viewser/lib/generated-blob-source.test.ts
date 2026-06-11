import assert from "node:assert/strict";

import { MANIFEST_RELPATH, selectServedRelPaths } from "./generated-blob-source";

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
