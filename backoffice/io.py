"""Shared file IO helpers for Backoffice writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(target: Path, contents: str) -> None:
    """Write text atomically: temp file, fsync, then replace."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object atomically with stable formatting."""
    atomic_write_text(
        target,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
