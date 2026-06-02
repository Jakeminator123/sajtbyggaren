"""Trace logging for router decisions (KÖR-6a).

The router never owns infrastructure. When a decision belongs to an
*existing* Engine Run / follow-up, this module appends one Engine Event to
that run's ``trace.ndjson``. When there is no run (the typical
``answer_only`` case), it does **nothing** and returns ``False`` - it must
never create a run directory just to log a pure answer (kor-6a trace rule).

A standalone router log is a later decision, not this slice.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import RouterDecision

# Engine Event fields mirror scripts/build_site.py:Trace and
# scripts/dev_generate.py:emit so the router's events are indistinguishable
# in shape from the rest of the run's trace.
_PHASE = "route"
_EVENT = "router-decision"


def log_router_decision_to_existing_run(
    run_dir: Path | str,
    decision: RouterDecision,
    *,
    run_id: str | None = None,
) -> bool:
    """Append the router decision to an existing run's ``trace.ndjson``.

    Returns ``True`` when the event was appended, ``False`` when the run
    directory does not exist (in which case nothing is written and no run
    is created). This is the kor-6a guarantee: a pure question without a
    run produces no run on disk.
    """
    run_path = Path(run_dir)
    if not run_path.is_dir():
        # No existing run -> never create one just to log a decision.
        return False

    resolved_run_id = run_id or run_path.name
    record = {
        "runId": resolved_run_id,
        "phase": _PHASE,
        "event": _EVENT,
        "status": "done",
        "message": f"{decision.messageKind}/{decision.buildRequirement}: {decision.rationale}",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "payloadPath": None,
        "decision": decision.model_dump(),
    }
    trace_path = run_path / "trace.ndjson"
    with trace_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True
