"""Tests for Sprintvakt MCP agent inbox (post/list/ack)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tooling.sprintvakt_mcp import inbox
from tooling.sprintvakt_mcp.core import SprintvaktError


def _inbox_path(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    return docs / "agent-inbox.jsonl"


def _post(
    inbox_path: Path,
    *,
    sender: str = "jakob",
    recipients: list[str] | None = None,
    subject: str = "Hello",
    body: str = "Body text.",
    topic: str | None = None,
    dry_run: bool = False,
    confirm: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "from": sender,
        "to": recipients or ["christopher"],
        "subject": subject,
        "body": body,
        "dryRun": dry_run,
        "confirm": confirm,
    }
    if topic is not None:
        payload["topic"] = topic
    return inbox.post_message(payload, inbox_path=inbox_path)


@pytest.mark.tooling
def test_post_message_dry_run_writes_nothing(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)

    result = _post(inbox_path, dry_run=True, confirm=False)

    assert result["dryRun"] is True
    assert "written" not in result
    assert not inbox_path.exists()
    assert result["message"]["id"].startswith("msg-0001-")
    assert result["message"]["from"] == "jakob"
    assert result["message"]["to"] == ["christopher"]


@pytest.mark.tooling
def test_post_message_confirm_appends_to_file(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)

    result = _post(inbox_path)

    assert result.get("written") is True
    assert inbox_path.is_file()
    lines = inbox_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["type"] == "message"
    assert payload["id"] == result["message"]["id"]
    assert payload["from"] == "jakob"
    assert payload["to"] == ["christopher"]
    assert payload["subject"] == "Hello"
    assert payload["body"] == "Body text."
    assert payload["createdAt"] == result["message"]["createdAt"]


@pytest.mark.tooling
def test_post_message_requires_confirm_for_writes(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)

    with pytest.raises(SprintvaktError, match="requires confirm:true"):
        _post(inbox_path, dry_run=False, confirm=False)


@pytest.mark.tooling
@pytest.mark.parametrize(
    "field,value",
    [
        ("from", ""),
        ("from", "Jakob With Spaces"),
        ("from", "jakob!"),
        ("to", []),
        ("to", ["jakob", "INVALID UPPER"]),
        ("subject", ""),
        ("body", ""),
    ],
)
def test_post_message_rejects_invalid_inputs(
    tmp_path: Path, field: str, value: object
) -> None:
    inbox_path = _inbox_path(tmp_path)
    payload = {
        "from": "jakob",
        "to": ["christopher"],
        "subject": "Hello",
        "body": "Body",
        "dryRun": True,
    }
    payload[field] = value

    with pytest.raises(SprintvaktError):
        inbox.post_message(payload, inbox_path=inbox_path)


@pytest.mark.tooling
def test_post_message_deduplicates_recipients(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)

    result = _post(
        inbox_path,
        recipients=["jakob", "christopher", "jakob"],
        dry_run=True,
        confirm=False,
    )

    assert result["message"]["to"] == ["jakob", "christopher"]


@pytest.mark.tooling
def test_post_message_topic_is_optional_but_validated(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)

    no_topic = _post(inbox_path)
    assert "topic" not in no_topic["message"]

    with_topic = _post(
        inbox_path,
        topic="GAP-backend-build-trace-endpoint",
        subject="Topic message",
    )
    assert with_topic["message"]["topic"] == "GAP-backend-build-trace-endpoint"

    with pytest.raises(SprintvaktError, match="topic must match"):
        _post(inbox_path, topic="bad topic with spaces", subject="bad")


@pytest.mark.tooling
def test_list_messages_filters_by_recipient(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    _post(inbox_path, sender="jakob", recipients=["christopher"], subject="A")
    _post(inbox_path, sender="christopher", recipients=["operator"], subject="B")
    _post(inbox_path, sender="jakob", recipients=["operator", "christopher"], subject="C")

    operator_view = inbox.list_messages({"to": "operator"}, inbox_path=inbox_path)
    subjects = [message["subject"] for message in operator_view["messages"]]

    assert subjects == ["B", "C"]
    assert operator_view["totalMatched"] == 2


@pytest.mark.tooling
def test_list_messages_attaches_acks(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    posted = _post(inbox_path, recipients=["christopher", "operator"])
    message_id = posted["message"]["id"]

    inbox.ack_message(
        {"messageId": message_id, "by": "christopher", "dryRun": False, "confirm": True},
        inbox_path=inbox_path,
    )

    listed = inbox.list_messages({}, inbox_path=inbox_path)

    assert len(listed["messages"]) == 1
    acks = listed["messages"][0]["acks"]
    assert len(acks) == 1
    assert acks[0]["by"] == "christopher"


@pytest.mark.tooling
def test_list_messages_unread_for_excludes_acked(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    posted_a = _post(inbox_path, recipients=["christopher"], subject="A")
    posted_b = _post(inbox_path, recipients=["christopher"], subject="B")

    inbox.ack_message(
        {
            "messageId": posted_a["message"]["id"],
            "by": "christopher",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )

    unread = inbox.list_messages(
        {"unreadFor": "christopher"}, inbox_path=inbox_path
    )

    subjects = [message["subject"] for message in unread["messages"]]
    assert subjects == ["B"]
    assert posted_b["message"]["id"] in {
        message["id"] for message in unread["messages"]
    }


@pytest.mark.tooling
def test_list_messages_since_filter(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    inbox_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "id": "msg-0001-aaaaaa",
                        "from": "jakob",
                        "to": ["christopher"],
                        "subject": "Old",
                        "body": "Old body",
                        "createdAt": "2026-05-25T01:00:00Z",
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "type": "message",
                        "id": "msg-0002-bbbbbb",
                        "from": "jakob",
                        "to": ["christopher"],
                        "subject": "New",
                        "body": "New body",
                        "createdAt": "2026-05-25T04:00:00Z",
                    },
                    sort_keys=True,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    listed = inbox.list_messages(
        {"since": "2026-05-25T03:00:00Z"}, inbox_path=inbox_path
    )

    subjects = [message["subject"] for message in listed["messages"]]
    assert subjects == ["New"]


@pytest.mark.tooling
def test_list_messages_limit_caps_results(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    for index in range(5):
        _post(inbox_path, subject=f"S{index}")

    listed = inbox.list_messages({"limit": 2}, inbox_path=inbox_path)

    assert len(listed["messages"]) == 2
    assert listed["totalMatched"] == 5
    assert [message["subject"] for message in listed["messages"]] == ["S3", "S4"]


@pytest.mark.tooling
def test_ack_message_requires_confirm_for_writes(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    posted = _post(inbox_path)

    with pytest.raises(SprintvaktError, match="requires confirm:true"):
        inbox.ack_message(
            {
                "messageId": posted["message"]["id"],
                "by": "christopher",
                "dryRun": False,
                "confirm": False,
            },
            inbox_path=inbox_path,
        )


@pytest.mark.tooling
def test_ack_message_rejects_unknown_message_id(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    _post(inbox_path)

    with pytest.raises(SprintvaktError, match="Unknown messageId"):
        inbox.ack_message(
            {
                "messageId": "msg-9999-ffffff",
                "by": "christopher",
                "dryRun": False,
                "confirm": True,
            },
            inbox_path=inbox_path,
        )


@pytest.mark.tooling
def test_ack_message_rejects_non_recipient(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    posted = _post(inbox_path, recipients=["christopher"])

    with pytest.raises(SprintvaktError, match="not a recipient"):
        inbox.ack_message(
            {
                "messageId": posted["message"]["id"],
                "by": "operator",
                "dryRun": False,
                "confirm": True,
            },
            inbox_path=inbox_path,
        )


@pytest.mark.tooling
def test_ack_message_already_acked_flag(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    posted = _post(inbox_path, recipients=["christopher"])

    first = inbox.ack_message(
        {
            "messageId": posted["message"]["id"],
            "by": "christopher",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )
    second = inbox.ack_message(
        {
            "messageId": posted["message"]["id"],
            "by": "christopher",
            "dryRun": True,
            "confirm": False,
        },
        inbox_path=inbox_path,
    )

    assert first["alreadyAcked"] is False
    assert second["alreadyAcked"] is True
    assert second["dryRun"] is True


@pytest.mark.tooling
def test_ack_message_rejects_invalid_message_id_shape(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    _post(inbox_path)

    with pytest.raises(SprintvaktError, match="messageId must match"):
        inbox.ack_message(
            {
                "messageId": "not-a-message-id",
                "by": "christopher",
                "dryRun": True,
            },
            inbox_path=inbox_path,
        )


@pytest.mark.tooling
def test_inbox_file_refuses_non_canonical_filename(tmp_path: Path) -> None:
    wrong_name = tmp_path / "docs" / "agent-inbox.txt"
    wrong_name.parent.mkdir(parents=True, exist_ok=True)

    with pytest.raises(SprintvaktError, match="non-canonical filename"):
        inbox.post_message(
            {
                "from": "jakob",
                "to": ["christopher"],
                "subject": "x",
                "body": "y",
                "dryRun": False,
                "confirm": True,
            },
            inbox_path=wrong_name,
        )


@pytest.mark.tooling
def test_inbox_file_refuses_non_docs_parent(tmp_path: Path) -> None:
    wrong_parent = tmp_path / "logs" / "agent-inbox.jsonl"
    wrong_parent.parent.mkdir(parents=True, exist_ok=True)

    with pytest.raises(SprintvaktError, match="outside a docs/"):
        inbox.post_message(
            {
                "from": "jakob",
                "to": ["christopher"],
                "subject": "x",
                "body": "y",
                "dryRun": False,
                "confirm": True,
            },
            inbox_path=wrong_parent,
        )


@pytest.mark.tooling
def test_corrupt_jsonl_line_raises_clear_error(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    inbox_path.write_text("{not json\n", encoding="utf-8")

    with pytest.raises(SprintvaktError, match="line 1 is not valid JSON"):
        inbox.list_messages({}, inbox_path=inbox_path)


# ---------------------------------------------------------------------------
# Regression tests for PR #77 review findings
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_dry_run_message_id_matches_eventual_confirm_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: dryRun preview and confirm-write must produce the same id.

    The previous implementation hashed ``core.utc_now()`` into the id, so a
    dryRun preview at T0 and a confirm-write at T1 returned different ids
    despite the documented "deterministic id" contract.
    """
    inbox_path = _inbox_path(tmp_path)

    timestamps = iter(
        ["2026-05-25T03:00:00Z", "2026-05-25T03:00:05Z"]
    )
    monkeypatch.setattr(inbox.core, "utc_now", lambda: next(timestamps))

    preview = inbox.post_message(
        {
            "from": "jakob",
            "to": ["christopher"],
            "subject": "Same content",
            "body": "Same body",
            "dryRun": True,
        },
        inbox_path=inbox_path,
    )
    written = inbox.post_message(
        {
            "from": "jakob",
            "to": ["christopher"],
            "subject": "Same content",
            "body": "Same body",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )

    assert preview["message"]["id"] == written["message"]["id"]
    assert preview["message"]["createdAt"] != written["message"]["createdAt"]
    assert written.get("written") is True


@pytest.mark.tooling
def test_duplicate_ack_does_not_append_when_already_acked(tmp_path: Path) -> None:
    """Regression: ack_message must be idempotent for the same (id, by) pair.

    Previously a second confirm-call still appended a duplicate ack event
    even though ``alreadyAcked`` was reported as ``true``, contradicting the
    documented idempotent contract and inflating the append-only log.
    """
    inbox_path = _inbox_path(tmp_path)
    posted = _post(inbox_path, recipients=["christopher"])
    message_id = posted["message"]["id"]

    first = inbox.ack_message(
        {
            "messageId": message_id,
            "by": "christopher",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )
    second = inbox.ack_message(
        {
            "messageId": message_id,
            "by": "christopher",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )

    assert first["alreadyAcked"] is False
    assert first["written"] is True
    assert second["alreadyAcked"] is True
    assert second["written"] is False

    ack_lines = [
        json.loads(line)
        for line in inbox_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("type") == "ack"
    ]
    assert len(ack_lines) == 1

    listed = inbox.list_messages({}, inbox_path=inbox_path)
    assert len(listed["messages"]) == 1
    assert len(listed["messages"][0]["acks"]) == 1


@pytest.mark.tooling
def test_message_id_pattern_accepts_ordinals_above_9999(tmp_path: Path) -> None:
    """Regression: ack_message must accept ids with 5+ digit ordinals.

    The ordinal grows organically (``msg-0001-...``, ``msg-9999-...``,
    ``msg-10000-...``); previously the regex hard-coded ``\\d{4}`` so any
    message past 9,999 became permanently unackable.
    """
    inbox_path = _inbox_path(tmp_path)

    seed_events = []
    for ordinal in range(1, 10000):
        seed_events.append(
            json.dumps(
                {
                    "type": "message",
                    "id": f"msg-{ordinal:04d}-aaaaaa",
                    "from": "jakob",
                    "to": ["christopher"],
                    "subject": f"S{ordinal}",
                    "body": "x",
                    "createdAt": "2026-05-25T00:00:00Z",
                },
                sort_keys=True,
            )
        )
    inbox_path.write_text("\n".join(seed_events) + "\n", encoding="utf-8")

    posted = inbox.post_message(
        {
            "from": "jakob",
            "to": ["christopher"],
            "subject": "Tenth-thousand",
            "body": "After the boundary",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )
    message_id = posted["message"]["id"]

    assert message_id.startswith("msg-10000-")
    assert inbox._message_id_pattern().match(message_id)

    acked = inbox.ack_message(
        {
            "messageId": message_id,
            "by": "christopher",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )
    assert acked["alreadyAcked"] is False
    assert acked["written"] is True


@pytest.mark.tooling
def test_since_filter_compares_timestamps_as_datetimes(tmp_path: Path) -> None:
    """Regression: ``since`` must compare ISO-8601 instants, not raw strings.

    Lexicographic comparison breaks for equivalent encodings like ``Z`` vs
    ``+00:00``; the filter must treat them as the same instant and order
    timezone-shifted timestamps numerically.
    """
    inbox_path = _inbox_path(tmp_path)
    inbox_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "id": "msg-0001-aaaaaa",
                        "from": "jakob",
                        "to": ["christopher"],
                        "subject": "z-boundary",
                        "body": "Same instant as since, using Z.",
                        "createdAt": "2026-05-25T03:00:00Z",
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "type": "message",
                        "id": "msg-0002-bbbbbb",
                        "from": "jakob",
                        "to": ["christopher"],
                        "subject": "offset-boundary",
                        "body": "Same instant as since, using +00:00.",
                        "createdAt": "2026-05-25T03:00:00+00:00",
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "type": "message",
                        "id": "msg-0003-cccccc",
                        "from": "jakob",
                        "to": ["christopher"],
                        "subject": "earlier-utc",
                        "body": "02:30Z is BEFORE 03:00Z but lexically AFTER '03:00:00+00:00'.",
                        "createdAt": "2026-05-25T02:30:00Z",
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "type": "message",
                        "id": "msg-0004-dddddd",
                        "from": "jakob",
                        "to": ["christopher"],
                        "subject": "shifted-offset",
                        "body": "04:00+01:00 is the same instant as 03:00Z.",
                        "createdAt": "2026-05-25T04:00:00+01:00",
                    },
                    sort_keys=True,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    listed = inbox.list_messages(
        {"since": "2026-05-25T03:00:00+00:00"}, inbox_path=inbox_path
    )
    subjects = {message["subject"] for message in listed["messages"]}

    assert "earlier-utc" not in subjects
    assert {"z-boundary", "offset-boundary", "shifted-offset"} <= subjects


@pytest.mark.tooling
def test_since_filter_rejects_invalid_iso8601(tmp_path: Path) -> None:
    inbox_path = _inbox_path(tmp_path)
    _post(inbox_path)

    with pytest.raises(SprintvaktError, match="since must be an ISO-8601 timestamp"):
        inbox.list_messages({"since": "yesterday"}, inbox_path=inbox_path)


@pytest.mark.tooling
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows symlink creation often requires elevated privileges",
)
def test_inbox_refuses_symlinked_file_redirecting_outside(tmp_path: Path) -> None:
    """Regression: a symlinked inbox file must not redirect writes elsewhere.

    Without this guard a malicious or accidental symlink at
    ``docs/agent-inbox.jsonl`` could let ``post_message``/``ack_message``
    append to arbitrary files outside the Sprintvakt write whitelist.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    target = tmp_path / "escape.txt"
    target.write_text("", encoding="utf-8")
    inbox_path = docs_dir / "agent-inbox.jsonl"
    os.symlink(target, inbox_path)

    with pytest.raises(SprintvaktError, match="symlinked file"):
        inbox.post_message(
            {
                "from": "jakob",
                "to": ["christopher"],
                "subject": "Should not write",
                "body": "Should not write",
                "dryRun": False,
                "confirm": True,
            },
            inbox_path=inbox_path,
        )

    assert target.read_text(encoding="utf-8") == ""


@pytest.mark.tooling
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows symlink creation often requires elevated privileges",
)
def test_inbox_refuses_symlinked_docs_parent(tmp_path: Path) -> None:
    """Regression: a symlinked ``docs/`` parent dir must not redirect writes."""
    real_docs = tmp_path / "real_docs"
    real_docs.mkdir(parents=True)
    docs_link = tmp_path / "docs"
    os.symlink(real_docs, docs_link, target_is_directory=True)
    inbox_path = docs_link / "agent-inbox.jsonl"

    with pytest.raises(SprintvaktError, match="symlinked docs/"):
        inbox.post_message(
            {
                "from": "jakob",
                "to": ["christopher"],
                "subject": "Should not write",
                "body": "Should not write",
                "dryRun": False,
                "confirm": True,
            },
            inbox_path=inbox_path,
        )

    assert not (real_docs / "agent-inbox.jsonl").exists()


@pytest.mark.tooling
def test_inbox_in_repo_routes_through_core_write_whitelist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: in-repo inbox writes must defer to core._assert_allowed_write.

    Pinning ``core.REPO_ROOT`` and ``DEFAULT_INBOX`` at ``tmp_path`` lets us
    verify that the production path (``path.resolve()`` inside REPO_ROOT)
    calls the shared write whitelist instead of silently falling back to the
    test-friendly literal check.
    """
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    docs_dir = fake_repo / "docs"
    docs_dir.mkdir()
    inbox_path = docs_dir / "agent-inbox.jsonl"

    monkeypatch.setattr(inbox.core, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(inbox, "DEFAULT_INBOX", inbox_path)

    calls: list[Path] = []

    def fake_assert_allowed_write(path: Path, workboard_path: Path | None) -> None:
        calls.append(path)

    monkeypatch.setattr(inbox.core, "_assert_allowed_write", fake_assert_allowed_write)

    inbox.post_message(
        {
            "from": "jakob",
            "to": ["christopher"],
            "subject": "In repo",
            "body": "In repo body",
            "dryRun": False,
            "confirm": True,
        },
        inbox_path=inbox_path,
    )

    assert calls, "Expected core._assert_allowed_write to be invoked for in-repo writes"
    assert calls[-1] == inbox_path
