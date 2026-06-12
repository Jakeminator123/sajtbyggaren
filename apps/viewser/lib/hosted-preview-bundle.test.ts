import assert from "node:assert/strict";

import { parseHostedSiteCurrentPointer } from "./hosted-preview-bundle";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;

// G2 (ADR 0058): parseHostedSiteCurrentPointer är den rena valideringskärnan
// för preview-bundle-snabbvägen. En trasig/främmande pekare får ALDRIG ge en
// användbar bundle-källa — då tar preview-starten ärligt fil-för-fil-vägen.
describe("parseHostedSiteCurrentPointer (G2 preview-bundle)", () => {
  it("läser en komplett pekare med bundle-fält", () => {
    const pointer = parseHostedSiteCurrentPointer({
      buildId: "20260612T120000Z",
      blobPrefix: "generated/site-x/",
      updatedAt: "2026-06-12T12:00:00Z",
      previewBundleUrl: "https://blob.test/preview-bundles/site-x/b/preview-bundle.tar.gz",
      previewBundleBytes: 12_345_678,
      previewBundleFileCount: 321,
    });

    assert.ok(pointer);
    assert.equal(pointer.buildId, "20260612T120000Z");
    assert.equal(
      pointer.previewBundleUrl,
      "https://blob.test/preview-bundles/site-x/b/preview-bundle.tar.gz",
    );
    assert.equal(pointer.previewBundleBytes, 12_345_678);
    assert.equal(pointer.previewBundleFileCount, 321);
  });

  it("accepterar pekare utan bundle-fält (sajt byggd före G2)", () => {
    const pointer = parseHostedSiteCurrentPointer({
      buildId: "20260611T080000Z",
      blobPrefix: "generated/site-y/",
      updatedAt: "2026-06-11T08:00:00Z",
    });

    assert.ok(pointer);
    assert.equal(pointer.buildId, "20260611T080000Z");
    assert.equal(pointer.previewBundleUrl, undefined);
  });

  it("avvisar icke-https bundle-URL (aldrig en användbar källa)", () => {
    const pointer = parseHostedSiteCurrentPointer({
      buildId: "20260612T120000Z",
      previewBundleUrl: "http://osäkert.example/bundle.tar.gz",
      previewBundleBytes: 100,
    });

    assert.ok(pointer);
    assert.equal(pointer.previewBundleUrl, undefined);
    // Storleksfälten följer bara med en giltig URL.
    assert.equal(pointer.previewBundleBytes, undefined);
  });

  it("utelämnar ogiltiga storleks-/antalsfält i stället för att kasta", () => {
    const pointer = parseHostedSiteCurrentPointer({
      previewBundleUrl: "https://blob.test/bundle.tar.gz",
      previewBundleBytes: "stor",
      previewBundleFileCount: -3,
    });

    assert.ok(pointer);
    assert.equal(pointer.previewBundleUrl, "https://blob.test/bundle.tar.gz");
    assert.equal(pointer.previewBundleBytes, undefined);
    assert.equal(pointer.previewBundleFileCount, undefined);
  });

  it("returnerar null för icke-objekt", () => {
    assert.equal(parseHostedSiteCurrentPointer(null), null);
    assert.equal(parseHostedSiteCurrentPointer("pekare"), null);
    assert.equal(parseHostedSiteCurrentPointer([1, 2, 3]), null);
  });
});
