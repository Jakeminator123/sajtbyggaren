import assert from "node:assert/strict";

import {
  configurePreviewRuntimeHandlers,
  currentRuntime,
  resolveRuntime,
  type PreviewRuntimeConfig,
} from "@preview-runtime";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;

const baseConfig: PreviewRuntimeConfig = {
  kind: "local",
  projectName: "preview-runtime-test",
  siteId: "preview-runtime-test-site",
  runId: "preview-runtime-test-run",
};

function envWithPreviewMode(mode: string): NodeJS.ProcessEnv {
  return { ...process.env, VIEWSER_PREVIEW_MODE: mode };
}

describe("PreviewRuntime registry and handler injection", () => {
  it("resolves current runtime from VIEWSER_PREVIEW_MODE aliases", () => {
    assert.equal(
      currentRuntime(envWithPreviewMode("local-next")).kind,
      "local",
    );
    assert.equal(
      currentRuntime(envWithPreviewMode("stackblitz")).kind,
      "stackblitz",
    );
  });

  it("delegates local runtime to the injected handler", async () => {
    let delegatedSiteId = "";
    configurePreviewRuntimeHandlers({
      local: {
        start: async (config) => {
          delegatedSiteId = config.siteId ?? "";
          return {
            siteId: delegatedSiteId,
            status: "ready",
            url: "http://localhost:4101",
          };
        },
      },
    });

    const runtime = resolveRuntime("local");
    assert.equal(await runtime.isAvailable(), true);

    const result = await runtime.start(baseConfig);
    assert.equal(delegatedSiteId, baseConfig.siteId);
    assert.equal(result.status, "ready");
    assert.equal(result.previewSession?.kind, "local");
    assert.equal(result.previewUrl, "http://localhost:4101");
  });

  it("returns stackblitz files from the injected payload builder", async () => {
    configurePreviewRuntimeHandlers({
      stackblitz: {
        readFiles: async () => ({
          "app/page.tsx": "export default function Page() { return null; }",
          "package.json": "{\"scripts\":{}}",
        }),
      },
    });

    const result = await resolveRuntime("stackblitz").start(baseConfig);

    assert.equal(result.status, "ready");
    assert.deepEqual(
      result.files?.map((file) => file.path),
      ["app/page.tsx", "package.json"],
    );
  });
});
