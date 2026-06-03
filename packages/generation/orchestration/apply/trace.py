"""Trace logging for the patch apply step (KÖR-7c).

Mirrors ``packages/generation/orchestration/router/trace.py`` exactly: when an
apply belongs to an **existing** run, this appends one append-only Engine Event
to that run's ``trace.ndjson``; when there is no run it does **nothing** and
returns ``False`` - it never creates a run directory just to log an apply.

Critical immutability detail (kor-7c DoD): apply must leave every *previous*
``data/runs/<älder runId>/`` artefakt byte-stable. So the caller must only pass
the run directory of the **new** version's run (when one exists), never a prior
run's directory. ``apply_patch_plan`` honours this by defaulting the trace run
dir to ``None`` - the version snapshot is written without touching any run at
all, and a run-trace event is only emitted when kor-7d (or a caller that already
owns a fresh run) hands in that run's directory.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import ApplyResult

# Engine Event fields mirror scripts/build_site.py:Trace, dev_generate.py:emit
# and router/trace.py so the apply event is indistinguishable in shape from the
# rest of a run's trace.
_PHASE = "apply"
_EVENT = "patch-apply"


def log_patch_apply_to_existing_run(
    run_dir: Path | str,
    result: ApplyResult,
    *,
    run_id: str | None = None,
) -> bool:
    """Append the apply outcome to an existing run's ``trace.ndjson``.

    Returns ``True`` when the event was appended, ``False`` when the run
    directory does not exist (in which case nothing is written and no run is
    created). Append-only: it never rewrites or truncates the trace.
    """
    run_path = Path(run_dir)
    if not run_path.is_dir():
        # No existing run -> never create one just to log an apply.
        return False

    resolved_run_id = run_id or run_path.name
    status = "done" if result.applied else "skipped"
    if result.applied:
        message = (
            f"applied patch plan -> {result.siteId} "
            f"v{result.previousVersion}->v{result.version}"
        )
    else:
        message = (
            f"patch plan not applied for {result.siteId} "
            f"({len(result.unmapped)} unmapped patch(es))"
        )
    record = {
        "runId": resolved_run_id,
        "phase": _PHASE,
        "event": _EVENT,
        "status": status,
        "message": message,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "payloadPath": None,
        "apply": result.model_dump(),
    }
    trace_path = run_path / "trace.ndjson"
    with trace_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True
