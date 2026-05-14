"""Trace parsing and operator-friendly rendering for Engine Runs."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import streamlit as st

Severity = Literal["error", "warning", "success", "info"]

IMPORTANT_EVENT_TOKENS = ("quality", "repair", "codegen")
ERROR_STATUS_TOKENS = ("error", "failed", "failure")
WARNING_STATUS_TOKENS = ("degraded", "skipped", "timeout")
SUCCESS_STATUS_TOKENS = ("done", "ok", "completed", "success")


def _contains_token(text: str, tokens: tuple[str, ...]) -> bool:
    """Match telemetry tokens without substring false positives."""
    return any(
        re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text)
        for token in tokens
    )


def load_trace_events(trace_path: Path) -> tuple[list[dict[str, Any]], int]:
    """Load newline-delimited Engine Events and tolerate partial writes."""
    events: list[dict[str, Any]] = []
    skipped_lines = 0
    for raw_line in trace_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            skipped_lines += 1
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
        else:
            skipped_lines += 1
    return events, skipped_lines


def _text_value(event: Mapping[str, Any], key: str) -> str:
    value = event.get(key)
    return value if isinstance(value, str) else ""


def event_severity(event: Mapping[str, Any]) -> Severity:
    """Classify a trace event for visual emphasis in the backoffice."""
    status = _text_value(event, "status").strip().lower()
    event_name = _text_value(event, "event").lower()
    message = _text_value(event, "message").lower()

    if status in ERROR_STATUS_TOKENS:
        return "error"
    if status in WARNING_STATUS_TOKENS:
        return "warning"
    if status in SUCCESS_STATUS_TOKENS:
        return "success"
    searchable = f"{event_name} {message}"
    if _contains_token(searchable, ERROR_STATUS_TOKENS):
        return "error"
    if _contains_token(searchable, WARNING_STATUS_TOKENS):
        return "warning"
    return "info"


def event_badges(event: Mapping[str, Any]) -> list[str]:
    """Return compact labels that make important trace event types scannable."""
    event_name = _text_value(event, "event").lower()
    message = _text_value(event, "message").lower()
    return [
        token
        for token in IMPORTANT_EVENT_TOKENS
        if token in event_name or token in message
    ]


def summarize_trace_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize trace events for top-level operator metrics."""
    phases = Counter(_text_value(event, "phase") or "unknown" for event in events)
    statuses = Counter(_text_value(event, "status") or "unknown" for event in events)
    severities = Counter(event_severity(event) for event in events)
    important = Counter(
        badge for event in events for badge in event_badges(event)
    )
    timestamps = [
        timestamp
        for event in events
        if isinstance((timestamp := event.get("timestamp")), str) and timestamp
    ]
    return {
        "total": len(events),
        "phases": dict(phases),
        "statuses": dict(statuses),
        "severities": dict(severities),
        "important": dict(important),
        "latestTimestamp": max(timestamps) if timestamps else None,
    }


def _event_title(event: Mapping[str, Any]) -> str:
    phase = _text_value(event, "phase") or "?"
    event_name = _text_value(event, "event") or "?"
    status = _text_value(event, "status") or "?"
    badges = event_badges(event)
    badge_text = f" · {' · '.join(badges)}" if badges else ""
    return f"`{phase}` · `{event_name}` · **{status}**{badge_text}"


def _event_body(event: Mapping[str, Any]) -> str:
    message = _text_value(event, "message")
    timestamp = _text_value(event, "timestamp")
    payload_path = _text_value(event, "payloadPath")

    details = []
    if timestamp:
        details.append(f"tid: `{timestamp}`")
    if payload_path:
        details.append(f"payload: `{payload_path}`")

    body = message or "_Ingen message-text._"
    if details:
        body = f"{body}\n\n" + " · ".join(details)
    return body


def _render_event(event: Mapping[str, Any]) -> None:
    severity = event_severity(event)
    title = _event_title(event)
    body = _event_body(event)
    if severity == "error":
        st.error(f"{title}\n\n{body}")
    elif severity == "warning":
        st.warning(f"{title}\n\n{body}")
    elif severity == "success":
        st.success(f"{title}\n\n{body}")
    else:
        st.info(f"{title}\n\n{body}")


def _filter_events(
    events: list[dict[str, Any]],
    phases: list[str],
    statuses: list[str],
    query: str,
) -> list[dict[str, Any]]:
    if not phases or not statuses:
        return []

    query_normalized = query.strip().lower()
    filtered: list[dict[str, Any]] = []
    for event in events:
        phase = _text_value(event, "phase") or "unknown"
        status = _text_value(event, "status") or "unknown"
        if phases and phase not in phases:
            continue
        if statuses and status not in statuses:
            continue
        if query_normalized:
            haystack = " ".join(
                _text_value(event, key)
                for key in ("phase", "event", "status", "message", "payloadPath")
            ).lower()
            if query_normalized not in haystack:
                continue
        filtered.append(event)
    return filtered


def render_trace_viewer(
    events: list[dict[str, Any]],
    *,
    key_prefix: str,
    skipped_lines: int = 0,
) -> None:
    """Render trace events as grouped, filterable operator telemetry."""
    if not events:
        st.warning("Trace finns men inga giltiga Engine Events kunde visas.")
        if skipped_lines:
            st.caption(f"{skipped_lines} ogiltiga/halvskrivna rader hoppades över.")
        return

    summary = summarize_trace_events(events)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Events", summary["total"])
    metric_cols[1].metric("Faser", len(summary["phases"]))
    metric_cols[2].metric("Fel", summary["severities"].get("error", 0))
    metric_cols[3].metric("Varningar", summary["severities"].get("warning", 0))
    metric_cols[4].metric("Senaste event", summary["latestTimestamp"] or "-")

    if skipped_lines:
        st.caption(f"{skipped_lines} ogiltiga/halvskrivna trace-rader hoppades över.")

    phases = sorted(summary["phases"])
    statuses = sorted(summary["statuses"])
    filter_cols = st.columns([2, 2, 3])
    selected_phases = filter_cols[0].multiselect(
        "Filtrera fas",
        phases,
        default=phases,
        key=f"{key_prefix}-phase-filter",
    )
    selected_statuses = filter_cols[1].multiselect(
        "Filtrera status",
        statuses,
        default=statuses,
        key=f"{key_prefix}-status-filter",
    )
    query = filter_cols[2].text_input(
        "Sök i event/message",
        key=f"{key_prefix}-search",
        placeholder="t.ex. quality, repair, failed",
    )

    filtered = _filter_events(events, selected_phases, selected_statuses, query)
    st.caption(f"Visar {len(filtered)} av {len(events)} events.")

    by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in filtered:
        by_phase[_text_value(event, "phase") or "unknown"].append(event)

    for phase in phases:
        phase_events = by_phase.get(phase, [])
        if not phase_events:
            continue
        error_count = sum(event_severity(event) == "error" for event in phase_events)
        warning_count = sum(event_severity(event) == "warning" for event in phase_events)
        label = f"{phase} ({len(phase_events)} events"
        if error_count:
            label += f", {error_count} fel"
        if warning_count:
            label += f", {warning_count} varningar"
        label += ")"
        with st.expander(label, expanded=bool(error_count or warning_count)):
            for event in phase_events:
                _render_event(event)

    with st.expander("Rå trace-data"):
        st.dataframe(events, use_container_width=True, hide_index=True)
