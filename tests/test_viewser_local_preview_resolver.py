"""Source-lock for `apps/viewser/lib/local-preview-server.ts:resolveGeneratedDir`.

Background: the dev-preview pipeline has two ends. The Python side
(``scripts/build_site.py``) writes generated sites into
``SAJTBYGGAREN_GENERATED_DIR``; the Node viewser reads them back to
spawn ``next start``. When the env value is relative and the two ends
resolved it against different cwds, the viewser silently fell back to
"directory not found" pointing at a wrong path.

This source-lock pins the TS resolver to the new contract:

- Use ``import.meta.url`` (anchor on the module's own location), NOT
  ``process.cwd()``. A worktree-launched viewser must resolve to the
  same directory as a repo-root-launched one.
- Walk up looking for ``pyproject.toml`` so the anchor matches the
  Python helper exactly.
- Treat absolute env values as pass-through; relative ones resolve
  against the discovered repo root.

We use a source-lock instead of a Node-level unit test because
``apps/viewser/`` has no Jest/Vitest setup (the Next.js app relies on
type-checking + lint + the Python test surface). Adding a JS test
runner just for this would be heavier than the regression it would
catch. Substring assertions are cheap and unambiguous: they fail loud
when the bug shape (``path.resolve(envOverride)`` against cwd) creeps
back in.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER = (
    REPO_ROOT / "apps" / "viewser" / "lib" / "local-preview-server.ts"
)


def _load_source() -> str:
    assert RESOLVER.exists(), (
        f"Expected {RESOLVER} to exist; if it moved, update this test in lockstep."
    )
    return RESOLVER.read_text(encoding="utf-8")


def _load_code_only_source() -> str:
    """Return ``local-preview-server.ts`` with block- and line-comments stripped.

    The negative source-locks below assert that certain bug-shape
    expressions (``process.cwd()``, ``path.resolve(envOverride``) do
    NOT appear in the file. Without stripping comments, the test would
    trip on the docstring that explains why we no longer use them. We
    walk the source character by character so the rules are unambiguous
    on TS / JSX-flavoured input: ``/* ... */`` and ``// ... \\n`` are
    elided; nothing else is touched.
    """
    source = _load_source()
    out: list[str] = []
    i = 0
    length = len(source)
    while i < length:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < length else ""
        if ch == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            i = length if end == -1 else end + 2
            continue
        if ch == "/" and nxt == "/":
            end = source.find("\n", i + 2)
            i = length if end == -1 else end
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def test_resolver_anchors_on_module_url_not_cwd() -> None:
    """The resolver must derive its anchor from ``import.meta.url``.

    Anchoring on ``process.cwd()`` is the bug shape this commit fixed:
    a viewser process spawned from a Cursor worktree, an arbitrary
    subdirectory or a parent shell with a stale cwd would silently
    resolve relative env values to the wrong place.
    """
    source = _load_source()
    assert "import.meta.url" in source, (
        "local-preview-server.ts must anchor its repo-root walk on "
        "`import.meta.url`, not `process.cwd()`. Removing this anchor "
        "re-opens the cwd-drift bug where a worktree-launched viewser "
        "reads a different .generated/ than the builder wrote to."
    )
    assert "fileURLToPath" in source, (
        "local-preview-server.ts must call `fileURLToPath(import.meta.url)` "
        "to get the module's directory before walking upward."
    )


def test_resolver_does_not_use_process_cwd_for_anchor() -> None:
    """``process.cwd()`` must not appear in the executable code.

    A direct ``path.resolve(envOverride)`` collapses against cwd, which
    is the exact regression the new walk-up was meant to remove. We
    strip comments first so the test does not trip on the docstring
    that explains why the old call site is gone.
    """
    code = _load_code_only_source()
    assert "process.cwd()" not in code, (
        "local-preview-server.ts must not anchor on `process.cwd()` — that "
        "was the source of the worktree/sub-script drift bug. Use the "
        "`findRepoRoot()` walk based on `import.meta.url` instead."
    )
    assert "path.resolve(envOverride" not in code, (
        "local-preview-server.ts must not collapse the env override via "
        "`path.resolve(envOverride.trim())` directly — that resolves "
        "against cwd. Branch on `path.isAbsolute(...)` and join against "
        "the discovered repo root for relative values."
    )


def test_resolver_walks_up_for_pyproject_marker() -> None:
    """The walk-up must look for ``pyproject.toml`` (canonical repo marker).

    Matching the Python helper (``scripts/_repo_root.py``) ensures both
    ends of the dev-preview pipeline converge on the same root.
    """
    source = _load_source()
    assert "pyproject.toml" in source, (
        "local-preview-server.ts must use `pyproject.toml` as the repo-"
        "root marker so the walk-up converges on the same directory as "
        "scripts/_repo_root.py:find_repo_root()."
    )


def test_resolver_respects_absolute_env_value() -> None:
    """Absolute env values must pass through unchanged.

    Operators may point ``SAJTBYGGAREN_GENERATED_DIR`` at a totally
    different drive (Windows ``D:\\stuff\\.generated`` or a tmpfs path
    on CI). The relative-anchor branch must not capture absolutes.
    """
    source = _load_source()
    assert "path.isAbsolute" in source, (
        "local-preview-server.ts must branch on `path.isAbsolute(...)` "
        "for the env override so an operator's absolute path (e.g. "
        "`D:\\\\stuff\\\\.generated`) is honoured verbatim instead of "
        "being re-rooted under the repo."
    )


def test_resolver_caches_repo_root() -> None:
    """The walk-up runs once per process, not per call.

    Every request to ``startPreviewServer`` calls ``resolveGeneratedDir``;
    repeating the disk walk per request adds latency for no benefit
    (the file layout above the module cannot change at runtime).
    """
    source = _load_source()
    assert "cachedRepoRoot" in source, (
        "local-preview-server.ts must cache the discovered repo root in "
        "a module-level variable so subsequent calls skip the walk."
    )


def test_resolver_has_depth_cap_safeguard() -> None:
    """A hardcoded depth cap protects against unbounded walks.

    If viewser is somehow launched from outside the repo (a packaging
    accident, a misplaced symlink) the resolver must bail with a clear
    error instead of walking to the filesystem root.
    """
    source = _load_source()
    assert "REPO_ROOT_MAX_WALK" in source, (
        "local-preview-server.ts must expose a `REPO_ROOT_MAX_WALK` "
        "constant that bounds the walk-up depth. Without the cap a "
        "module placed outside the repo would walk all the way to `/`."
    )
