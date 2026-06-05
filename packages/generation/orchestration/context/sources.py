"""Read-only source resolution and readers for the Context Assembler (KÖR-7a).

Everything in this module *reads*. There is no function that writes a file,
creates a directory, starts a build or a preview, or creates a run. Missing
inputs return ``None`` / an empty list (never created); malformed canonical
JSON is allowed to raise, because silent corruption of an artefakt is a real
bug, not an empty context.

Path roots are resolved once from the repo root, with the same environment
override the rest of the repo uses for the runs directory
(``VIEWSER_RUNS_DIR``, see docs/heavy-llm-flow/03 §5). A caller (or a test)
may override any root explicitly via :class:`ContextPaths`.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "ContextPaths",
    "generated_files_dir",
    "list_generated_files",
    "read_capability_map",
    "read_dossier_manifests",
    "read_generated_file",
    "read_meta",
    "read_run_artifact",
    "read_sections",
    "run_dir",
    "sha256_bytes",
]

# packages/generation/orchestration/context/sources.py -> repo root is 4 up.
_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class ContextPaths:
    """The read-only roots the assembler reads from.

    Defaults resolve to the repo layout; ``runsDir`` additionally honours the
    ``VIEWSER_RUNS_DIR`` environment override so the assembler reads the same
    runs an operator session would. Construct with explicit paths in tests to
    point at a ``tmp_path`` sandbox.
    """

    repoRoot: Path = _REPO_ROOT
    runsDir: Path | None = None
    promptInputsDir: Path | None = None
    scaffoldsDir: Path | None = None
    dossiersDir: Path | None = None
    capabilityMapPath: Path | None = None

    @property
    def runs(self) -> Path:
        if self.runsDir is not None:
            return self.runsDir
        env = os.environ.get("VIEWSER_RUNS_DIR", "").strip()
        if env:
            env_path = Path(env)
            if env_path.is_absolute():
                return env_path
            # VIEWSER_RUNS_DIR is documented relative to apps/viewser/
            # (apps/viewser/.env.example: ``../../data/runs``). Resolve a
            # relative value against that base, cwd-independently, so the
            # assembler reads the SAME runs dir an operator's Viewser session
            # does regardless of the Python process working directory.
            return (self.repoRoot / "apps" / "viewser" / env_path).resolve()
        return self.repoRoot / "data" / "runs"

    @property
    def prompt_inputs(self) -> Path:
        if self.promptInputsDir is not None:
            return self.promptInputsDir
        return self.repoRoot / "data" / "prompt-inputs"

    @property
    def scaffolds(self) -> Path:
        if self.scaffoldsDir is not None:
            return self.scaffoldsDir
        return self.repoRoot / "packages" / "generation" / "orchestration" / "scaffolds"

    @property
    def dossiers(self) -> Path:
        if self.dossiersDir is not None:
            return self.dossiersDir
        return self.repoRoot / "packages" / "generation" / "orchestration" / "dossiers"

    @property
    def capability_map(self) -> Path:
        if self.capabilityMapPath is not None:
            return self.capabilityMapPath
        return self.repoRoot / "governance" / "policies" / "capability-map.v1.json"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    """Parse a JSON object from ``path``; ``None`` if the file is absent."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_meta(
    paths: ContextPaths,
    site_id: str,
    *,
    version: int | None = None,
) -> dict[str, Any] | None:
    """Read ``<prompt-inputs>/<siteId>.meta.json`` (or the ``.v<N>`` snapshot).

    Returns the parsed sidecar or ``None`` when it does not exist. Never
    creates the prompt-inputs directory or any file.
    """
    name = f"{site_id}.v{version}.meta.json" if version is not None else f"{site_id}.meta.json"
    return _read_json(paths.prompt_inputs / name)


def run_dir(paths: ContextPaths, run_id: str) -> Path:
    return paths.runs / run_id


def read_run_artifact(
    paths: ContextPaths,
    run_id: str,
    filename: str,
) -> dict[str, Any] | None:
    """Read one JSON artefakt under ``data/runs/<runId>/`` (read-only)."""
    return _read_json(run_dir(paths, run_id) / filename)


def generated_files_dir(paths: ContextPaths, run_id: str) -> Path:
    """The ``generated-files/`` directory inside a run (per the Engine Run contract)."""
    return run_dir(paths, run_id) / "generated-files"


def list_generated_files(paths: ContextPaths, run_id: str) -> list[tuple[str, int]]:
    """List ``(relativePath, byteSize)`` for every file under ``generated-files/``.

    Sorted by path for determinism. Returns an empty list when the directory
    does not exist - it is never created. Pure ``stat``/scandir, no content
    is read here.
    """
    base = generated_files_dir(paths, run_id)
    if not base.is_dir():
        return []
    out: list[tuple[str, int]] = []
    for path in base.rglob("*"):
        if path.is_file():
            out.append((path.relative_to(base).as_posix(), path.stat().st_size))
    out.sort(key=lambda entry: entry[0])
    return out


def read_generated_file(
    paths: ContextPaths,
    run_id: str,
    rel_path: str,
) -> tuple[int, str, str] | None:
    """Read one generated file as ``(byteSize, sha256Hex, textContent)``.

    The requested path is resolved and confined to ``generated-files/`` so a
    caller cannot read outside the run sandbox via ``..``. Returns ``None``
    when the file is missing or escapes the sandbox. Content is decoded as
    UTF-8 with replacement so an odd byte never crashes the assembler; the
    digest is taken over the raw bytes for stability.
    """
    base = generated_files_dir(paths, run_id)
    if not base.is_dir():
        return None
    candidate = (base / rel_path).resolve()
    if not candidate.is_relative_to(base.resolve()):
        return None
    if not candidate.is_file():
        return None
    raw = candidate.read_bytes()
    return len(raw), sha256_bytes(raw), raw.decode("utf-8", errors="replace")


def read_capability_map(paths: ContextPaths) -> dict[str, Any] | None:
    return _read_json(paths.capability_map)


def read_dossier_manifests(paths: ContextPaths) -> list[dict[str, Any]]:
    """Read every dossier ``manifest.json`` under ``dossiers/{soft,hard}/``.

    Sorted by dossier id for determinism. Missing class directories are
    skipped; the dossiers root is never created.
    """
    out: list[dict[str, Any]] = []
    base = paths.dossiers
    for klass in ("soft", "hard"):
        klass_dir = base / klass
        if not klass_dir.is_dir():
            continue
        for child in sorted(klass_dir.iterdir(), key=lambda p: p.name):
            manifest = child / "manifest.json"
            data = _read_json(manifest)
            if isinstance(data, dict):
                out.append(data)
    out.sort(key=lambda d: str(d.get("id", "")))
    return out


def read_sections(paths: ContextPaths, scaffold_id: str) -> dict[str, Any] | None:
    """Read ``scaffolds/<scaffoldId>/sections.json`` (route -> sections map)."""
    return _read_json(paths.scaffolds / scaffold_id / "sections.json")
