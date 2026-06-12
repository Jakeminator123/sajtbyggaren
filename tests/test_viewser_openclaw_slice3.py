"""Viewser source-locks for OpenClaw F1 slice 3 (roll-dispatch, frontend half).

Topic-focused split out of ``test_viewser_floating_chat.py`` (test-hygiene cap):
these lock the slice-3 conductor wiring on the TS side -

  1. ``/api/prompt`` threads the conversation metadata (role + conversationKind
     + expectsAnswer) into ALL follow-up return paths, and reads expectsAnswer
     defensively.
  2. FloatingChat short-circuits answer-only on the explicit ``expectsAnswer``
     signal (additive on top of the existing ``answerText`` path).
  3. FloatingChat renders an HONEST role-row (which conductor role acted +
     conversationKind) from ``payload.conversation``.

The dialog path (use-followup-build) only gets the short-circuit and is locked
in ``test_viewser_runs_versions.py`` (no message thread -> no role-row).
"""

from __future__ import annotations

import pytest

from tests.support.viewser import VIEWSER_DIR


@pytest.mark.tooling
def test_prompt_route_threads_conversation_and_expects_answer() -> None:
    """F1 slice 3 (Scout #262): ``/api/prompt`` måste (a) läsa ``expectsAnswer``
    ur conversation-metadatan och (b) tråda hela conversation-blocket
    (role + conversationKind) till ALLA follow-up-return-vägar (inte bara
    answer-only), så FloatingChat kan visa en ärlig roll-rad även för en
    applicerad ändring (t.ex. section_builder).

    Locks:
      1. ``ConversationMetadata`` bär ``expectsAnswer`` och ``extractConversation``
         läser ``obj.expectsAnswer === true`` defensivt.
      2. ``conversationMeta`` härleds en gång ur bryggans decision.
      3. ``conversation: conversationMeta`` ligger i bridge-applied-, recovery-
         och fallback-return-objekten (NDJSON sprider ``...result``).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "expectsAnswer: boolean;" in text, (
        "ConversationMetadata måste bära expectsAnswer (conductorns Scout-#262-signal)."
    )
    assert "obj.expectsAnswer === true" in text, (
        "extractConversation måste läsa expectsAnswer defensivt (boolean)."
    )
    assert "const conversationMeta = extractConversation(applyResult?.decision);" in text, (
        "Routen måste härleda conversationMeta en gång ur bryggans decision."
    )
    # The metadata must be threaded into the build-path returns so the role-row
    # is honest for edits, not just for answer-only conversations.
    assert text.count("conversation: conversationMeta,") >= 3, (
        "conversation: conversationMeta måste ligga i bridge-applied-, recovery- "
        "och fallback-return-objekten (>=3) så roll-raden trådas på bygg-vägarna."
    )


@pytest.mark.tooling
def test_floating_chat_short_circuits_on_expects_answer() -> None:
    """F1 slice 3 (Scout #262): FloatingChat ska kortsluta answer-only på den
    EXPLICITA ``expectsAnswer``-signalen (additivt — ``extractConversationAnswer``
    förblir primärkällan för svarstexten). Konversations-grenen får aldrig
    anropa ``onBuildDone``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "function extractExpectsAnswer(" in text, (
        "FloatingChat måste läsa expectsAnswer defensivt (extractExpectsAnswer)."
    )
    # extractExpectsAnswer only counts when no real build ran (no runId), same
    # invariant as extractConversationAnswer.
    extract_start = text.index("function extractExpectsAnswer(")
    extract_body = text[extract_start : extract_start + 400]
    assert "if (payload.runId) return false;" in extract_body, (
        "extractExpectsAnswer: ett payload med runId är ett bygge, aldrig answer-only."
    )
    assert ".expectsAnswer === true" in text, (
        "extractExpectsAnswer måste läsa conversation.expectsAnswer (boolean)."
    )
    # The expectsAnswer signal participates in the conversation short-circuit
    # while keeping the locked `if (conversationAnswer !== null) {` branch.
    assert "const expectsAnswer = response.ok && extractExpectsAnswer(payload);" in text, (
        "sendFollowupPrompt måste beräkna expectsAnswer och låta den driva "
        "answer-only-grenen (men behålla extractConversationAnswer som primärkälla)."
    )
    assert "if (conversationAnswer !== null) {" in text, (
        "Den låsta answer-only-grenen (if conversationAnswer !== null) måste finnas kvar."
    )
    branch_start = text.index("if (conversationAnswer !== null) {")
    branch_end = text.index("return;", branch_start)
    branch_body = text[branch_start:branch_end]
    assert "onBuildDone" not in branch_body, (
        "Konversations-grenen får ALDRIG anropa onBuildDone (ingen version)."
    )


@pytest.mark.tooling
def test_floating_chat_renders_honest_role_row() -> None:
    """F1 slice 3: FloatingChat ska rendera en ÄRLIG roll-rad (vilken
    conductor-roll som agerade + conversationKind) ur ``payload.conversation``,
    som idag trådas men inte renderas. Roll-raden visas ENDAST i FloatingChat
    (dialog-vägen har ingen meddelandetråd, per scope).

    Locks:
      1. ``ChatMessage`` bär conversationRole/conversationKind.
      2. ``extractConversationMeta`` läser payload.conversation defensivt.
      3. Svenska etikett-mappningar + ``formatRoleRow`` (UPPER_CASE-konstanter).
      4. Både answer-grenen och done-grenen sätter roll-fälten; MessageBubble
         renderar raden ("Roll: ...") för assistent-bubblor.
    """
    types_text = (
        VIEWSER_DIR / "components" / "builder" / "floating-chat" / "types.ts"
    ).read_text(encoding="utf-8")
    assert "conversationRole?: string | null;" in types_text, (
        "ChatMessage måste bära conversationRole för roll-raden."
    )
    assert "conversationKind?: string | null;" in types_text, (
        "ChatMessage måste bära conversationKind för roll-raden."
    )

    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "function extractConversationMeta(" in text, (
        "FloatingChat måste läsa payload.conversation defensivt (extractConversationMeta)."
    )
    assert "const CONVERSATION_ROLE_LABELS" in text and (
        "const CONVERSATION_KIND_LABELS" in text
    ), (
        "Svenska etikett-mappningar för roll + kind måste finnas (UPPER_CASE-konstanter)."
    )
    assert "section_builder" in text and "sektionsbyggare" in text, (
        "Roll-etiketterna måste mappa section_builder (slice 3:s dispatch-roll)."
    )
    # Uppgift H (deferred från #312): femte rollen component_builder (ADR 0057)
    # måste ha en svensk operatörsetikett — annars ekar roll-raden det råa
    # rollnamnet. Stavningen speglar roles.py/action-registry.json exakt.
    assert 'component_builder: "komponenter"' in text, (
        "Roll-etiketterna måste mappa component_builder till 'komponenter' "
        "(ADR 0057; rollnamnet stavas exakt som i roles.py/action-registry.json)."
    )
    assert "function formatRoleRow(" in text, (
        "FloatingChat måste bygga roll-raden via formatRoleRow."
    )
    # Both the answer branch and the build (done) branch must set the role fields.
    assert text.count("conversationRole: conversationMeta?.role ?? null,") >= 2, (
        "Både answer-grenen och done-grenen måste sätta conversationRole/kind."
    )
    # MessageBubble must render the row from formatRoleRow for assistant bubbles.
    bubble_start = text.index("function MessageBubble(")
    bubble_body = text[bubble_start:]
    assert "formatRoleRow(message.conversationRole, message.conversationKind)" in bubble_body, (
        "MessageBubble måste rendera roll-raden ur message-fälten via formatRoleRow."
    )
    assert "Roll:" in text, (
        "Roll-raden måste ha en igenkännbar 'Roll:'-text-anchor."
    )
