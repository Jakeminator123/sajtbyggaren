import assert from "node:assert/strict";

import {
  downloadBlobEntries,
  filterPrebuiltRelPaths,
  hasPrebuiltNextRelPath,
  MANIFEST_RELPATH,
  selectServedRelPaths,
  type BlobDownloadEntry,
} from "./generated-blob-source";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;

/** Kör ``fn`` med en stubbar global fetch och återställ alltid efteråt. */
async function withStubbedFetch(
  stub: (url: string) => Promise<Response>,
  fn: () => Promise<void>,
): Promise<void> {
  const realFetch = globalThis.fetch;
  globalThis.fetch = ((input: unknown) =>
    stub(String(input))) as typeof fetch;
  try {
    await fn();
  } finally {
    globalThis.fetch = realFetch;
  }
}

function entryFor(index: number): BlobDownloadEntry {
  return {
    relPath: `file-${index}.txt`,
    url: `https://blob.test/generated/site/file-${index}.txt`,
    pathname: `generated/site/file-${index}.txt`,
  };
}

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

// Incident 2026-06-12: den seriella en-fetch-per-fil-loopen gjorde hostad
// preview-POST långsam. downloadBlobEntries ersätter den med en worker-pool
// (begränsad samtidighet) men måste bevara den seriella vägens kontrakt:
// ordning, vakter och fel-semantik.
describe("downloadBlobEntries (parallelliserad nedladdning)", () => {
  it("laddar ner alla filer, bevarar entry-ordningen och summerar bytes", async () => {
    const entries = Array.from({ length: 40 }, (_, i) => entryFor(i));
    let expectedBytes = 0;
    await withStubbedFetch(
      async (url) => {
        const index = Number(/file-(\d+)\.txt/.exec(url)?.[1]);
        // Olika svarstider så slutförandeordningen GARANTERAT skiljer sig
        // från entry-ordningen — resultatet ska ändå följa entries.
        await new Promise((r) => setTimeout(r, (40 - index) % 7));
        return new Response(`content-${index}`, { status: 200 });
      },
      async () => {
        const { files, totalBytes } = await downloadBlobEntries(
          "site",
          entries,
          16,
        );
        assert.equal(files.length, 40);
        for (let i = 0; i < 40; i += 1) {
          assert.equal(files[i].relPath, `file-${i}.txt`);
          assert.equal(files[i].content.toString("utf-8"), `content-${i}`);
          expectedBytes += files[i].content.byteLength;
        }
        assert.equal(totalBytes, expectedBytes);
      },
    );
  });

  it("kör parallellt men aldrig med fler än angiven samtidighet", async () => {
    const entries = Array.from({ length: 48 }, (_, i) => entryFor(i));
    let inFlight = 0;
    let maxInFlight = 0;
    await withStubbedFetch(
      async () => {
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await new Promise((r) => setTimeout(r, 5));
        inFlight -= 1;
        return new Response("x", { status: 200 });
      },
      async () => {
        await downloadBlobEntries("site", entries, 16);
        assert.ok(
          maxInFlight <= 16,
          `samtidigheten får aldrig överstiga 16 (såg ${maxInFlight})`,
        );
        assert.ok(
          maxInFlight >= 2,
          `nedladdningen ska faktiskt vara parallell (såg ${maxInFlight})`,
        );
      },
    );
  });

  it("kastar samma fel som den seriella vägen när en fil svarar icke-OK", async () => {
    const entries = Array.from({ length: 8 }, (_, i) => entryFor(i));
    await withStubbedFetch(
      async (url) =>
        url.includes("file-5")
          ? new Response("borta", { status: 404 })
          : new Response("ok", { status: 200 }),
      async () => {
        await assert.rejects(
          downloadBlobEntries("site", entries, 4),
          /Kunde inte hämta blob generated\/site\/file-5\.txt \(HTTP 404\)\./,
        );
      },
    );
  });

  it("vägrar deterministiskt starta fil nummer MAX_FILES + 1", async () => {
    // 4001 entries — fil-taket (4 000) ska trippa OAVSETT samtidighet,
    // eftersom vakten är indexbaserad (inte slutförande-baserad).
    const entries = Array.from({ length: 4_001 }, (_, i) => entryFor(i));
    let fetchCalls = 0;
    await withStubbedFetch(
      async () => {
        fetchCalls += 1;
        return new Response("x", { status: 200 });
      },
      async () => {
        await assert.rejects(
          downloadBlobEntries("site", entries, 16),
          /orimligt stort/,
        );
        assert.ok(
          fetchCalls <= 4_000,
          `fil 4001 får aldrig börja hämtas (såg ${fetchCalls} fetchar)`,
        );
      },
    );
  });

  it("stoppar nya hämtningar när byte-taket passerats (samma fel som förr)", async () => {
    // Tre filer à 33 MB: efter två slutförda (66 MB > 64 MB) ska den tredje
    // aldrig startas. Samtidighet 1 gör förloppet deterministiskt — i drift
    // räknas taket på slutförda hämtningar och in-flight får löpa klart.
    const entries = Array.from({ length: 3 }, (_, i) => entryFor(i));
    let fetchCalls = 0;
    await withStubbedFetch(
      async () => {
        fetchCalls += 1;
        return new Response(Buffer.alloc(33 * 1024 * 1024), {
          status: 200,
        });
      },
      async () => {
        await assert.rejects(
          downloadBlobEntries("site", entries, 1),
          /orimligt stort/,
        );
        assert.equal(fetchCalls, 2);
      },
    );
  });

  it("tom entry-lista ger tomt resultat utan fetch-anrop", async () => {
    let fetchCalls = 0;
    await withStubbedFetch(
      async () => {
        fetchCalls += 1;
        return new Response("x", { status: 200 });
      },
      async () => {
        const { files, totalBytes } = await downloadBlobEntries("site", []);
        assert.deepEqual(files, []);
        assert.equal(totalBytes, 0);
        assert.equal(fetchCalls, 0);
      },
    );
  });
});
