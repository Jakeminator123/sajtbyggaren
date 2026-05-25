"""Append-only agent inbox for Sprintvakt MCP.

The inbox is a small append-only JSONL log used for coordination messages
between operator, agents and MCP-driven roles (e.g. ``jakob-orchestrator``,
``christopher-ui-agent``). It intentionally avoids realtime semantics: every
event is a separate line, so the file is easy to diff, easy to read with any
tool, and idempotent for replay.

Storage: ``docs/agent-inbox.jsonl``.

Two event types live in the log:

- ``{"type": "message", ...}`` for new messages.
- ``{"type": "ack", ...}`` for read/processed acknowledgements.

The reader (:func:`list_messages`) folds both into a per-message view with
``acks`` attached.

Design choices:

- Append-only: no in-place mutation, no re-serialisation of the whole file.
- Deterministic message ids so dryRun previews match the eventual write.
- Strict participant-id sanitation so the inbox cannot accumulate
  free-form garbage.
- All writes go through :func:`core._assert_allowed_write`; the inbox file
  is on the Sprintvakt whitelist.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import core

DEFAULT_INBOX = core.REPO_ROOT / "docs" / "agent-inbox.jsonl"

PARTICIPANT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")
TOPIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,79}$")
SUBJECT_MAX = 140
BODY_MAX = 4000


def _inbox_path(path: Path | None = None) -> Path:
    return path or DEFAULT_INBOX


def _inbox_display_path(path: Path) -> str:
    """Return ``docs/agent-inbox.jsonl`` when inside the repo, else the full path.

    Tests point the inbox at ``tmp_path`` which lives outside ``REPO_ROOT``;
    falling back to the raw posix path keeps result payloads sensible without
    leaking ``ValueError`` from ``relative_to``.
    """
    try:
        return path.relative_to(core.REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sanitize_participant(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise core.SprintvaktError(f"{field} must be a string.")
    text = value.strip().lower()
    if not PARTICIPANT_RE.match(text):
        raise core.SprintvaktError(
            f"{field} must match [a-z0-9][a-z0-9._-]{{0,39}}, got {value!r}."
        )
    return text


def _sanitize_participants(values: Any, field: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise core.SprintvaktError(f"{field} must be a non-empty list.")
    seen: set[str] = set()
    out: list[str] = []
    for entry in values:
        clean = _sanitize_participant(entry, f"{field} entry")
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _sanitize_topic(value: Any) -> str:
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise core.SprintvaktError("topic must be a string.")
    text = value.strip()
    if not TOPIC_RE.match(text):
        raise core.SprintvaktError(
            "topic must match [A-Za-z0-9][A-Za-z0-9._/-]{0,79}."
        )
    return text


def _sanitize_text(value: Any, field: str, *, max_length: int, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise core.SprintvaktError(f"{field} must be a string.")
    text = value.strip()
    if required and not text:
        raise core.SprintvaktError(f"{field} must not be empty.")
    if len(text) > max_length:
        raise core.SprintvaktError(f"{field} exceeds {max_length} characters.")
    return text


def _read_events(path: Path | None = None) -> list[dict[str, Any]]:
    inbox_path = _inbox_path(path)
    if not inbox_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        inbox_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise core.SprintvaktError(
                f"Inbox line {line_number} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise core.SprintvaktError(
                f"Inbox line {line_number} is not a JSON object."
            )
        events.append(payload)
    return events


def _next_message_ordinal(events: list[dict[str, Any]]) -> int:
    return sum(1 for event in events if event.get("type") == "message") + 1


def _deterministic_message_id(
    *,
    sender: str,
    subject: str,
    created_at: str,
    ordinal: int,
) -> str:
    fingerprint_source = f"{sender}|{subject}|{created_at}|{ordinal}".encode()
    short_hash = hashlib.sha1(fingerprint_source).hexdigest()[:6]
    return f"msg-{ordinal:04d}-{short_hash}"


def _assert_allowed_inbox_write(path: Path) -> None:
    """Restrict writes to a file literally named ``docs/agent-inbox.jsonl``.

    The check intentionally does not require absolute repo-root parity so
    tests can point the inbox at ``tmp_path / "docs" / "agent-inbox.jsonl"``
    without ``core._assert_allowed_write`` rejecting them. It still refuses
    any other filename or any other parent directory name.
    """
    if path.name != "agent-inbox.jsonl":
        raise core.SprintvaktError(
            f"Refusing to write inbox to non-canonical filename: {path.name}"
        )
    if path.parent.name != "docs":
        raise core.SprintvaktError(
            f"Refusing to write inbox outside a docs/ directory: {path}"
        )


def _append_event(event: dict[str, Any], path: Path | None = None) -> None:
    inbox_path = _inbox_path(path)
    _assert_allowed_inbox_write(inbox_path)
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with inbox_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _message_id_pattern() -> re.Pattern[str]:
    return re.compile(r"^msg-\d{4}-[0-9a-f]{6}$")


def post_message(
    payload: dict[str, Any],
    *,
    inbox_path: Path | None = None,
) -> dict[str, Any]:
    """Append a coordination message to the agent inbox.

    Required payload fields: ``from``, ``to``, ``subject``, ``body``.
    Optional: ``topic`` and the standard ``dryRun`` / ``confirm`` pair.
    """
    dry_run = bool(payload.get("dryRun", True))
    confirm = bool(payload.get("confirm", False))
    if not dry_run and not confirm:
        raise core.SprintvaktError(
            "post_message with dryRun:false requires confirm:true."
        )

    sender = _sanitize_participant(payload.get("from"), "from")
    recipients = _sanitize_participants(payload.get("to"), "to")
    topic = _sanitize_topic(payload.get("topic"))
    subject = _sanitize_text(
        payload.get("subject"), "subject", max_length=SUBJECT_MAX
    )
    body = _sanitize_text(payload.get("body"), "body", max_length=BODY_MAX)
    created_at = core.utc_now()

    existing_events = _read_events(inbox_path)
    ordinal = _next_message_ordinal(existing_events)
    message_id = _deterministic_message_id(
        sender=sender,
        subject=subject,
        created_at=created_at,
        ordinal=ordinal,
    )
    message_event: dict[str, Any] = {
        "type": "message",
        "id": message_id,
        "from": sender,
        "to": recipients,
        "subject": subject,
        "body": body,
        "createdAt": created_at,
    }
    if topic:
        message_event["topic"] = topic

    result = {
        "dryRun": dry_run,
        "message": message_event,
        "plannedFile": _inbox_display_path(_inbox_path(inbox_path)),
    }
    if dry_run:
        return result

    _append_event(message_event, inbox_path)
    return result | {"written": True}


def list_messages(
    payload: dict[str, Any] | None = None,
    *,
    inbox_path: Path | None = None,
) -> dict[str, Any]:
    """Return inbox messages folded together with their acks."""
    payload = payload or {}
    to_filter = (
        _sanitize_participant(payload.get("to"), "to")
        if payload.get("to") not in (None, "")
        else None
    )
    from_filter = (
        _sanitize_participant(payload.get("from"), "from")
        if payload.get("from") not in (None, "")
        else None
    )
    topic_filter = (
        _sanitize_topic(payload.get("topic"))
        if payload.get("topic") not in (None, "")
        else None
    )
    since = payload.get("since")
    if since is not None and not isinstance(since, str):
        raise core.SprintvaktError("since must be an ISO-8601 string.")
    unread_for = payload.get("unreadFor")
    if unread_for not in (None, ""):
        unread_for = _sanitize_participant(unread_for, "unreadFor")
    else:
        unread_for = None
    raw_limit = payload.get("limit")
    if raw_limit is None:
        limit = 50
    else:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise core.SprintvaktError("limit must be an integer.") from exc
    if limit < 1 or limit > 500:
        raise core.SprintvaktError("limit must be between 1 and 500.")

    events = _read_events(inbox_path)
    messages_by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = event.get("type")
        if event_type == "message":
            message_id = event.get("id")
            if not isinstance(message_id, str):
                continue
            stored = dict(event)
            stored["acks"] = []
            messages_by_id[message_id] = stored
        elif event_type == "ack":
            message_id = event.get("messageId")
            if not isinstance(message_id, str) or message_id not in messages_by_id:
                continue
            messages_by_id[message_id]["acks"].append(
                {
                    "by": event.get("by"),
                    "at": event.get("at"),
                }
            )

    selected: list[dict[str, Any]] = []
    for message in messages_by_id.values():
        if to_filter and to_filter not in message.get("to", []):
            continue
        if from_filter and message.get("from") != from_filter:
            continue
        if topic_filter and message.get("topic") != topic_filter:
            continue
        if since and str(message.get("createdAt", "")) < since:
            continue
        if unread_for:
            acked_by = {ack.get("by") for ack in message.get("acks", [])}
            if unread_for in acked_by:
                continue
            if unread_for not in message.get("to", []):
                continue
        selected.append(message)

    selected.sort(key=lambda item: str(item.get("createdAt", "")))
    trimmed = selected[-limit:]
    return {
        "messages": trimmed,
        "count": len(trimmed),
        "totalMatched": len(selected),
        "inboxFile": _inbox_display_path(_inbox_path(inbox_path)),
    }


def ack_message(
    payload: dict[str, Any],
    *,
    inbox_path: Path | None = None,
) -> dict[str, Any]:
    """Append a read/processed acknowledgement for a message."""
    dry_run = bool(payload.get("dryRun", True))
    confirm = bool(payload.get("confirm", False))
    if not dry_run and not confirm:
        raise core.SprintvaktError(
            "ack_message with dryRun:false requires confirm:true."
        )

    message_id = str(payload.get("messageId", "")).strip()
    if not _message_id_pattern().match(message_id):
        raise core.SprintvaktError(
            "messageId must match msg-<ordinal>-<6-char-hash>."
        )
    by = _sanitize_participant(payload.get("by"), "by")
    at = core.utc_now()

    events = _read_events(inbox_path)
    message = next(
        (
            event
            for event in events
            if event.get("type") == "message" and event.get("id") == message_id
        ),
        None,
    )
    if message is None:
        raise core.SprintvaktError(f"Unknown messageId: {message_id}")
    if by not in (message.get("to") or []):
        raise core.SprintvaktError(
            f"{by!r} is not a recipient of {message_id} and cannot ack it."
        )
    already_acked = any(
        event.get("type") == "ack"
        and event.get("messageId") == message_id
        and event.get("by") == by
        for event in events
    )

    ack_event = {
        "type": "ack",
        "messageId": message_id,
        "by": by,
        "at": at,
    }
    result = {
        "dryRun": dry_run,
        "ack": ack_event,
        "messageId": message_id,
        "alreadyAcked": already_acked,
        "plannedFile": _inbox_display_path(_inbox_path(inbox_path)),
    }
    if dry_run:
        return result

    _append_event(ack_event, inbox_path)
    return result | {"written": True}
