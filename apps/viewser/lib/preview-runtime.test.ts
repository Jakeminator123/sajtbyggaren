import assert from "node:assert/strict";

import {
  configurePreviewRuntimeHandlers,
  currentRuntime,
  resolveRuntime,
  type PreviewRuntimeConfig,
} from "@preview-runtime";

import {
  currentViewserRuntime,
  resolveViewserRuntime,
} from "./preview-runtime-server";

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
    assert.equal(
      currentRuntime(envWithPreviewMode("vercel-sandbox")).kind,
      "vercel-sandbox",
    );
  });

  it("delegates vercel-sandbox runtime to the injected handler", async () => {
    configurePreviewRuntimeHandlers({
      vercelSandbox: {
        isAvailable: () => true,
        start: async (config) => ({
          status: "ready",
          url: "https://sb-test.vercel.run",
          sessionId: `sandbox-${config.siteId}`,
        }),
      },
    });

    const runtime = resolveRuntime("vercel-sandbox");
    assert.equal(await runtime.isAvailable(), true);

    const result = await runtime.start(baseConfig);
    assert.equal(result.status, "ready");
    assert.equal(result.previewSession?.kind, "vercel-sandbox");
    assert.equal(result.previewUrl, "https://sb-test.vercel.run");
  });

  it("maps a failed vercel-sandbox delegate to 'failed' (never 'unsupported')", async () => {
    configurePreviewRuntimeHandlers({
      vercelSandbox: {
        isAvailable: () => false,
        start: async () => ({
          status: "failed",
          error: "Vercel-credentials saknas.",
        }),
      },
    });

    const result = await resolveRuntime("vercel-sandbox").start(baseConfig);
    assert.equal(result.status, "failed");
    assert.match(result.error ?? "", /credentials saknas/);
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

  it("maps a thrown delegate error to status 'failed' (never 'unsupported')", async () => {
    configurePreviewRuntimeHandlers({
      local: {
        start: async () => {
          throw new Error("Build-artefakter saknas: .next/ saknas.");
        },
      },
    });

    const result = await resolveRuntime("local").start(baseConfig);

    assert.equal(result.status, "failed");
    assert.match(result.error ?? "", /Build-artefakter saknas/);
  });

  it("keeps fly as the only reserved 'unsupported' adapter", async () => {
    const result = await resolveRuntime("fly").start(baseConfig);
    assert.equal(result.status, "unsupported");
    assert.equal(resolveRuntime("fly").isAvailable(), false);
  });
});

describe("Viewser preview-runtime server wiring", () => {
  it("resolves the env-driven runtime with handlers auto-installed", async () => {
    assert.equal(
      currentViewserRuntime(envWithPreviewMode("local-next")).kind,
      "local",
    );
    assert.equal(
      currentViewserRuntime(envWithPreviewMode("stackblitz")).kind,
      "stackblitz",
    );
    assert.equal(
      currentViewserRuntime(envWithPreviewMode("vercel-sandbox")).kind,
      "vercel-sandbox",
    );
    assert.equal(await resolveViewserRuntime("local").isAvailable(), true);
    assert.equal(await resolveViewserRuntime("stackblitz").isAvailable(), true);
  });
});
