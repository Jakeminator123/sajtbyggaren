import assert from "node:assert/strict";
import { homedir } from "node:os";
import path from "node:path";

import { repoRoot, resolveGeneratedDir } from "./generated-dir";

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;

const ENV_KEY = "SAJTBYGGAREN_GENERATED_DIR";

// Drive resolveGeneratedDir() through process.env (which always wins over the
// repo-root .env fallback) so each case is deterministic and never touches the
// real filesystem. The previous value is restored so cases stay isolated.
function withGeneratedDirEnv(value: string, fn: () => void): void {
  const previous = process.env[ENV_KEY];
  process.env[ENV_KEY] = value;
  try {
    fn();
  } finally {
    if (previous === undefined) delete process.env[ENV_KEY];
    else process.env[ENV_KEY] = previous;
  }
}

describe("resolveGeneratedDir env handling (Python parity)", () => {
  it("expands a leading ~/ to the home dir (mirrors Path.expanduser)", () => {
    withGeneratedDirEnv("~/sajt-output", () => {
      assert.equal(resolveGeneratedDir(), path.join(homedir(), "sajt-output"));
    });
  });

  it("expands a bare ~ to the home dir", () => {
    withGeneratedDirEnv("~", () => {
      assert.equal(resolveGeneratedDir(), path.resolve(homedir()));
    });
  });

  it("resolves a RELATIVE value against the repo root (not cwd)", () => {
    withGeneratedDirEnv("relative/out", () => {
      assert.equal(
        resolveGeneratedDir(),
        path.resolve(repoRoot(), "relative/out"),
      );
    });
  });

  it("keeps an ABSOLUTE value as-is", () => {
    const abs = path.resolve(homedir(), "abs-generated");
    withGeneratedDirEnv(abs, () => {
      assert.equal(resolveGeneratedDir(), path.resolve(abs));
    });
  });
});
