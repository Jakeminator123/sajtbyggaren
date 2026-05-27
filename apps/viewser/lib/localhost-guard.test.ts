import assert from "node:assert/strict";

import { assertLocalhost } from "./localhost-guard";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;

function withEnv(
  overrides: { allowNonLocalhost?: string; allowedHosts?: string },
  fn: () => void | Promise<void>,
) {
  return async () => {
    const previousAllowNonLocalhost = process.env.VIEWSER_ALLOW_NON_LOCALHOST;
    const previousAllowedHosts = process.env.VIEWSER_ALLOWED_HOSTS;

    if (overrides.allowNonLocalhost === undefined) {
      delete process.env.VIEWSER_ALLOW_NON_LOCALHOST;
    } else {
      process.env.VIEWSER_ALLOW_NON_LOCALHOST = overrides.allowNonLocalhost;
    }

    if (overrides.allowedHosts === undefined) {
      delete process.env.VIEWSER_ALLOWED_HOSTS;
    } else {
      process.env.VIEWSER_ALLOWED_HOSTS = overrides.allowedHosts;
    }

    try {
      await fn();
    } finally {
      if (previousAllowNonLocalhost === undefined) {
        delete process.env.VIEWSER_ALLOW_NON_LOCALHOST;
      } else {
        process.env.VIEWSER_ALLOW_NON_LOCALHOST = previousAllowNonLocalhost;
      }

      if (previousAllowedHosts === undefined) {
        delete process.env.VIEWSER_ALLOWED_HOSTS;
      } else {
        process.env.VIEWSER_ALLOWED_HOSTS = previousAllowedHosts;
      }
    }
  };
}

function requestWithHost(host: string): Request {
  return new Request("https://viewser.test/api/discovery-options", {
    headers: { host },
  });
}

describe("assertLocalhost", () => {
  it(
    "allows localhost callers",
    withEnv({}, () => {
      const response = assertLocalhost(requestWithHost("localhost:3000"));

      assert.equal(response, null);
    }),
  );

  it(
    "returns 403 for a non-whitelisted public host",
    withEnv({}, () => {
      const response = assertLocalhost(requestWithHost("preview.example.com"));

      assert.equal(response?.status, 403);
    }),
  );

  it(
    "allows a host listed in VIEWSER_ALLOWED_HOSTS",
    withEnv(
      { allowedHosts: "sajtbyggaren-viewser.vercel.app,sajtbyggaren-viewser-jakob-be.vercel.app" },
      () => {
        const response = assertLocalhost(
          requestWithHost("sajtbyggaren-viewser-jakob-be.vercel.app"),
        );

        assert.equal(response, null);
      },
    ),
  );

  it(
    "allows any host when VIEWSER_ALLOW_NON_LOCALHOST is true",
    withEnv({ allowNonLocalhost: "true" }, () => {
      const response = assertLocalhost(requestWithHost("unlisted.example.com"));

      assert.equal(response, null);
    }),
  );

  it(
    "treats an empty VIEWSER_ALLOWED_HOSTS value as localhost-only",
    withEnv({ allowedHosts: " ,   , " }, () => {
      const response = assertLocalhost(requestWithHost("preview.example.com"));

      assert.equal(response?.status, 403);
    }),
  );

  it(
    "matches VIEWSER_ALLOWED_HOSTS case-insensitively after trimming whitespace",
    withEnv({ allowedHosts: " Sajtbyggaren-Viewser.Vercel.App , other.vercel.app " }, () => {
      const response = assertLocalhost(requestWithHost("sajtbyggaren-viewser.vercel.app:443"));

      assert.equal(response, null);
    }),
  );
});
