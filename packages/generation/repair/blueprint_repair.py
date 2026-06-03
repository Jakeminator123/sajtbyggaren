"""kor-5: blueprint-only repair pass driven by ``repairModel``.

After the deterministic Quality Critic (kor-4a) flags issues, this step asks
``repairModel`` to patch **named, already-existing blueprint fields** -
``contentBlocks`` on the Generation Package and ``conversion`` on the Site Brief
- then re-renders via the same deterministic renderer (an injected callback) and
re-runs the critic. It is the system's first real agent loop: build -> critique
-> repair -> re-critique.

Hard rules (docs/heavy-llm-flow/kor-5-repair-pass.md + 04 §9):

* **Blueprint-only.** The LLM may only edit blueprint fields that already exist
  in the schema. It never writes free files and never invents new addresses /
  sections (``_resolve_*`` enforce the rails).
* **Grounding guard.** A proposal may not introduce a multi-digit number or a
  place/name/cert token that is absent from the brief's grounding text
  (businessFacts / positioning / servicesMentioned / existing copy / location).
* **Bounded.** The loop runs at most ``fix-registry.v1.json:blueprintRepair
  .maxPasses`` (default 1) passes - no infinite loop.
* **No-key / model-unavailable contract.** Missing ``OPENAI_API_KEY`` OR a model
  that returns nothing for every issue produces ZERO ``BlueprintRepair`` entries,
  ``passes=0``, status ``no-fix-applied`` and a ``repair.blueprint_skipped``
  trace event. A non-``None`` proposal that fails validation DURING a real run is
  a failed repair recorded as ``BlueprintRepair(success=False, detail=...)``.

Boundary: this module imports only ``packages.generation.quality_gate`` (the
critic) + sibling repair modules + jsonschema/stdlib (repo-boundaries.v1).
The renderer is never imported; re-render is an injected callback so fas-3 build
code stays out of the repair package.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.generation.quality_gate import (
    CriticIssue,
    CriticResult,
    run_deterministic_critic,
)
from packages.generation.quality_gate.critic import (
    _OFFER_SECTION_IDS,
    _THIN_OFFER_MIN_ITEMS,
)

from .model_resolver import has_openai_api_key, resolve_repair_model
from .models import BlueprintRepair

# Re-render callback: receives the patched (generation_package, site_brief) and
# writes the deterministic render to disk. ``None`` = blueprint-only run (tests,
# dormant build path); the critic still re-reads the patched in-memory blueprint.
RerenderFn = Callable[[dict[str, Any], dict[str, Any]], None]

# Repair status for the blueprint pass alone (combined with the mechanical
# status in orchestration._combine_status).
BlueprintRepairStatus = Literal["not-needed", "no-fix-applied", "fixed", "partial-fix"]

# Critic issue types this pass knows how to repair via a blueprint patch.
# Mirrors governance/policies/fix-registry.v1.json:blueprintRepair
# .triggerIssueTypes (parity locked by tests). NOTE: critic v0 marks
# generic_copy/thin_offer as *medium* severity (not high), so the gate is by
# issue TYPE (high-severity-first ordering) - a severity-only gate would never
# repair them and would break the kor-5 DoD.
_HERO_FIELDS: tuple[str, ...] = ("headline", "subheadline", "proofLine")

# Multi-digit numbers (2+ consecutive digits): founding year, price, count,
# percentage. A single digit ("3 tjänster") is fine; a specific number the brief
# never stated is not. Whole-token comparison (the grounding text is tokenised
# with the same regex) so a shorter number can't slip through as a substring.
_NUMBER_RE = re.compile(r"\d{2,}")

# Capitalized place/name tokens (mixed case) + all-caps acronyms (certs like
# "ISO", "REKO"). Used by the grounding guard to reject an ungrounded proper
# noun the model might invent (a city, a brand, a certification body).
_PROPER_TOKEN_RE = re.compile(r"[A-ZÅÄÖ][a-zåäö]{2,}|[A-ZÅÄÖ]{2,}")

# Tokeniser for grounding text (letters + digits, incl. Swedish chars).
_WORD_RE = re.compile(r"[A-Za-zÅÄÖåäö0-9]+")

# Capitalized words that frequently begin a Swedish/English sentence and are not
# proper nouns; ignored by the proper-noun guard to cut false positives on
# sentence-initial words that are not the very first token.
_PROPER_TOKEN_STOPWORDS: frozenset[str] = frozenset(
    {
        "vi", "du", "din", "ditt", "dina", "det", "den", "de", "ett", "en",
        "vår", "vårt", "våra", "här", "hos", "med", "för", "och", "att", "när",
        "snabb", "snabbt", "trygg", "trygga", "tydlig", "tydligt", "lokal",
        "we", "you", "your", "our", "the", "and", "for", "with", "when", "fast",
    }
)


# ---------------------------------------------------------------------------
# repairModel structured-output shapes
# ---------------------------------------------------------------------------


class HeroCopyPatch(BaseModel):
    """repairModel proposal for a hero/copy block (generic_copy / missing_cta).

    Every field optional: the model returns only the ones it rewrote. Strings
    only; the apply step writes them onto the named hero block fields.
    """

    headline: str | None = Field(default=None)
    subheadline: str | None = Field(default=None)
    proofLine: str | None = Field(default=None)
    primaryCta: str | None = Field(default=None)


class OfferItemPatch(BaseModel):
    """One grounded offer item (thin_offer)."""

    title: str
    summary: str


class OfferListPatch(BaseModel):
    """repairModel proposal for an offer-list block (thin_offer)."""

    items: list[OfferItemPatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Outcome container
# ---------------------------------------------------------------------------


class BlueprintRepairOutcome(BaseModel):
    """Result of the blueprint-repair pass.

    ``status`` is the blueprint-only verdict (combined with the mechanical
    RepairResult status in orchestration). ``skipped`` is True when no key /
    model-unavailable short-circuited the pass (drives the
    ``repair.blueprint_skipped`` trace + the no-synthetic-failure contract).
    ``patched_generation_package`` / ``patched_site_brief`` are deep copies the
    caller may persist; the originals are never mutated.
    """

    status: BlueprintRepairStatus
    passes: int = 0
    repairs: list[BlueprintRepair] = Field(default_factory=list)
    skipped: bool = False
    skipped_reason: str = ""
    # Deep-copied, patched artifacts (only set when a patch was applied);
    # callers may persist them. ``None`` on not-needed / skipped / all-invalid.
    patched_generation_package: dict[str, Any] | None = None
    patched_site_brief: dict[str, Any] | None = None
    # Critic re-run over the patched blueprint (set only after a successful
    # apply); the orchestrator surfaces it on the FINAL quality-result.json so
    # the artefakt reflects the post-repair critic, not the pre-repair one.
    final_critic: CriticResult | None = None


# ---------------------------------------------------------------------------
# repairModel call (the only LLM boundary; monkeypatched in tests)
# ---------------------------------------------------------------------------

_HERO_SYSTEM = (
    "You are repairModel for Sajtbyggaren. A deterministic critic flagged weak "
    "copy in one website section. Rewrite ONLY the named hero/copy fields with "
    "grounded, specific, non-generic copy in the site's language. Base every "
    "sentence on the provided positioning / businessFacts; NEVER invent a "
    "number, city, name, price or certification that is not already present. "
    "Return only the fields you actually rewrote; leave the rest null. Output "
    "only customer-facing copy, never the critic's wording or an instruction."
)

_OFFER_SYSTEM = (
    "You are repairModel for Sajtbyggaren. A deterministic critic flagged a thin "
    "offer (too few services/products). Propose 3 concrete, grounded offer items "
    "(title + one-sentence summary) based ONLY on the provided "
    "servicesMentioned / positioning / businessFacts. NEVER invent a number, "
    "city, name, price or certification that is not already present. Output only "
    "customer-facing copy."
)


def _grounding_context(
    issue: CriticIssue,
    generation_package: dict[str, Any],
    site_brief: dict[str, Any],
) -> str:
    """Compact, read-only context the model sees (also the grounding source)."""
    blocks = generation_package.get("contentBlocks")
    block = blocks.get(issue.target) if isinstance(blocks, dict) else None
    return (
        f"Critic issue: type={issue.type} target={issue.target}\n"
        f"Message: {issue.message}\n"
        f"Repair hint: {issue.repairHint}\n"
        f"Current block value: {json.dumps(block, ensure_ascii=False)}\n"
        f"Grounding (use only facts present here):\n"
        f"{_grounding_text(generation_package, site_brief, issue.target)}"
    )


def run_repair_model(
    issue: CriticIssue,
    generation_package: dict[str, Any],
    site_brief: dict[str, Any],
    *,
    model: str | None = None,
) -> HeroCopyPatch | OfferListPatch | None:
    """Ask repairModel for a patch, or ``None`` when the model is unavailable.

    ``None`` semantics = "no key / not called / LLM error" -> treated as a SKIP
    (no BlueprintRepair entry). A returned proposal that later fails validation
    is a failed repair recorded by the caller. Monkeypatched in tests so the
    repair matrix runs without a real key.
    """
    if not has_openai_api_key():
        return None
    text_format: type[BaseModel]
    system: str
    if issue.type == "thin_offer":
        text_format = OfferListPatch
        system = _OFFER_SYSTEM
    else:
        text_format = HeroCopyPatch
        system = _HERO_SYSTEM
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.parse(
            model=model or resolve_repair_model(),
            input=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": _grounding_context(
                        issue, generation_package, site_brief
                    ),
                },
            ],
            text_format=text_format,
        )
        parsed = response.output_parsed
    except Exception as exc:  # noqa: BLE001 - never crash the pipeline on LLM error
        import sys

        sys.stderr.write(
            f"[repairModel] {type(exc).__name__}: {exc}\n"
        )
        sys.stderr.flush()
        return None
    if parsed is None:
        return None
    if isinstance(parsed, (HeroCopyPatch, OfferListPatch)):
        return parsed
    return None


# ---------------------------------------------------------------------------
# Grounding guard + rails
# ---------------------------------------------------------------------------


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _collect_strings(value: Any, out: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            out.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            _collect_strings(child, out)
    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, out)


def _grounding_text(
    generation_package: dict[str, Any],
    site_brief: dict[str, Any],
    target: str,
) -> str:
    """Build the text a proposal must stay grounded in.

    Sources: the brief's businessFacts, positioning, servicesMentioned,
    locationHint, companyName, conversion CTAs, plus the CURRENT contentBlocks
    copy (so the model may keep proper nouns already present in the blueprint).
    """
    parts: list[str] = []
    bf = site_brief.get("businessFacts")
    if isinstance(bf, dict):
        parts.extend(str(f) for f in bf.get("facts", []) if isinstance(f, str))
    positioning = site_brief.get("positioning")
    if isinstance(positioning, dict):
        _collect_strings(positioning, parts)
    parts.extend(
        s for s in site_brief.get("servicesMentioned", []) if isinstance(s, str)
    )
    for key in ("locationHint", "companyName", "rawPrompt", "businessTypeGuess"):
        parts.append(_clean(site_brief.get(key)))
    conversion = site_brief.get("conversion")
    if isinstance(conversion, dict):
        _collect_strings(conversion, parts)
    blocks = generation_package.get("contentBlocks")
    if isinstance(blocks, dict):
        _collect_strings(blocks, parts)
    return " ".join(p for p in parts if p)


def _grounded(text: str, grounding_text: str) -> tuple[bool, str]:
    """Return ``(ok, reason)``: reject ungrounded numbers / proper nouns.

    * Any multi-digit number in ``text`` must appear (whole token) in the
      grounding text.
    * Any capitalized place/name token or all-caps acronym must appear
      (case-insensitive) in the grounding text, EXCEPT the first token of the
      whole string / a token right after sentence punctuation (sentence-initial
      capitalisation) and a small connective stopword set.
    """
    grounded_numbers = set(_NUMBER_RE.findall(grounding_text))
    for number in _NUMBER_RE.findall(text):
        if number not in grounded_numbers:
            return False, f"ungrounded number '{number}'"

    grounding_words = {w.casefold() for w in _WORD_RE.findall(grounding_text)}
    # Track sentence boundaries: a proper-noun token is exempt when it is the
    # first alphanumeric token or directly follows . ! ? : or a newline.
    sentence_start = True
    for match in re.finditer(r"\S+", text):
        token_raw = match.group(0)
        core = token_raw.strip(".,!?:;\"'()[]")
        is_proper = bool(_PROPER_TOKEN_RE.fullmatch(core))
        if is_proper and not sentence_start:
            if (
                core.casefold() not in grounding_words
                and core.casefold() not in _PROPER_TOKEN_STOPWORDS
            ):
                return False, f"ungrounded proper noun '{core}'"
        # Next token is a sentence start iff this token ended a sentence.
        sentence_start = token_raw[-1:] in {".", "!", "?", ":"}
    return True, ""


# ---------------------------------------------------------------------------
# Schema validation of the patched Generation Package (local jsonschema)
# ---------------------------------------------------------------------------

_GENERATION_PACKAGE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "schemas"
    / "generation-package.schema.json"
)


def _generation_package_valid(generation_package: dict[str, Any]) -> bool:
    """Validate the patched package against generation-package.schema.json.

    Local jsonschema (no cross-package import) so repair stays inside its
    repo-boundaries allow-list while still proving a patch never breaks the
    canonical contract before it is applied.
    """
    import jsonschema

    schema = json.loads(
        _GENERATION_PACKAGE_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    return not list(validator.iter_errors(generation_package))


# ---------------------------------------------------------------------------
# Address rails
# ---------------------------------------------------------------------------


def _content_blocks(generation_package: dict[str, Any]) -> dict[str, Any]:
    blocks = generation_package.get("contentBlocks")
    return blocks if isinstance(blocks, dict) else {}


def _resolve_hero_address(
    generation_package: dict[str, Any], target: str
) -> str | None:
    """Return an existing hero block address to patch, else None (never create).

    Prefers the issue's own block when it is a dict, then ``<route>.hero``, then
    the first hero block. Returns None when no hero block exists - the caller
    then patches ``brief.conversion`` (for missing_cta) or records a failure.
    """
    blocks = _content_blocks(generation_package)
    block = blocks.get(target)
    if isinstance(block, dict):
        return target
    route = target.partition(".")[0]
    candidate = f"{route}.hero"
    if isinstance(blocks.get(candidate), dict):
        return candidate
    for address, value in blocks.items():
        if address.partition(".")[2] == "hero" and isinstance(value, dict):
            return address
    return None


def _is_offer_address(address: str) -> bool:
    return address.partition(".")[2] in _OFFER_SECTION_IDS


# ---------------------------------------------------------------------------
# Per-issue handlers (mutate the patched copies in place; return entries)
# ---------------------------------------------------------------------------


def _apply_hero_patch(
    issue: CriticIssue,
    proposal: HeroCopyPatch,
    patched_gp: dict[str, Any],
    patched_brief: dict[str, Any],
) -> list[BlueprintRepair]:
    """Apply a hero/copy patch (generic_copy / missing_cta). One entry/field."""
    entries: list[BlueprintRepair] = []
    grounding = _grounding_text(patched_gp, patched_brief, issue.target)
    address = _resolve_hero_address(patched_gp, issue.target)

    # missing_cta with no hero block -> patch the existing brief.conversion field.
    if issue.type == "missing_cta" and address is None:
        cta = _clean(proposal.primaryCta)
        if not cta:
            return [
                BlueprintRepair(
                    issueType=issue.type, target=issue.target,
                    field="conversion.primaryCta", success=False,
                    detail="repairModel returned no primaryCta for missing_cta",
                )
            ]
        ok, reason = _grounded(cta, grounding)
        if not ok:
            return [
                BlueprintRepair(
                    issueType=issue.type, target=issue.target,
                    field="conversion.primaryCta", success=False,
                    detail=f"grounding guard rejected CTA: {reason}",
                )
            ]
        conversion = patched_brief.get("conversion")
        if not isinstance(conversion, dict):
            conversion = {}
            patched_brief["conversion"] = conversion
        before = _clean(conversion.get("primaryCta"))
        conversion["primaryCta"] = cta
        return [
            BlueprintRepair(
                issueType=issue.type, target=issue.target,
                field="conversion.primaryCta", before=before, after=cta,
                success=True,
            )
        ]

    if address is None:
        return [
            BlueprintRepair(
                issueType=issue.type, target=issue.target, field="hero",
                success=False, detail="no existing hero block to patch",
            )
        ]

    block = patched_gp["contentBlocks"][address]
    proposed: dict[str, str] = {}
    for key in (*_HERO_FIELDS, "primaryCta"):
        value = _clean(getattr(proposal, key, None))
        if value:
            proposed[key] = value
    if not proposed:
        return [
            BlueprintRepair(
                issueType=issue.type, target=address, field="hero",
                success=False, detail="repairModel returned no usable fields",
            )
        ]

    for key, value in proposed.items():
        field = f"contentBlocks.{address}.{key}"
        # primaryCta is a label (not a sentence); still grounding-checked.
        ok, reason = _grounded(value, grounding)
        if not ok:
            entries.append(
                BlueprintRepair(
                    issueType=issue.type, target=address, field=field,
                    success=False, detail=f"grounding guard rejected: {reason}",
                )
            )
            continue
        before = _clean(block.get(key))
        if before == value:
            entries.append(
                BlueprintRepair(
                    issueType=issue.type, target=address, field=field,
                    before=before, after=value, success=False,
                    detail="proposal identical to existing value",
                )
            )
            continue
        block[key] = value
        entries.append(
            BlueprintRepair(
                issueType=issue.type, target=address, field=field,
                before=before, after=value, success=True,
            )
        )
    return entries


def _apply_offer_patch(
    issue: CriticIssue,
    proposal: OfferListPatch,
    patched_gp: dict[str, Any],
    patched_brief: dict[str, Any],
) -> list[BlueprintRepair]:
    """Apply a thin_offer patch: replace the offer list with grounded items."""
    address = issue.target
    field = f"contentBlocks.{address}"
    if not _is_offer_address(address) or address not in _content_blocks(patched_gp):
        return [
            BlueprintRepair(
                issueType=issue.type, target=address, field=field,
                success=False,
                detail="thin_offer target is not an existing offer-list block",
            )
        ]
    grounding = _grounding_text(patched_gp, patched_brief, address)
    items: list[dict[str, str]] = []
    for raw in proposal.items:
        title = _clean(raw.title)
        summary = _clean(raw.summary)
        if not title or not summary:
            continue
        ok_t, reason_t = _grounded(title, grounding)
        ok_s, reason_s = _grounded(summary, grounding)
        if not ok_t or not ok_s:
            return [
                BlueprintRepair(
                    issueType=issue.type, target=address, field=field,
                    success=False,
                    detail=(
                        "grounding guard rejected offer item: "
                        f"{reason_t or reason_s}"
                    ),
                )
            ]
        items.append({"title": title, "summary": summary})

    if len(items) < _THIN_OFFER_MIN_ITEMS:
        return [
            BlueprintRepair(
                issueType=issue.type, target=address, field=field,
                success=False,
                detail=(
                    f"repairModel returned {len(items)} grounded item(s); "
                    f"need >= {_THIN_OFFER_MIN_ITEMS} to clear thin_offer"
                ),
            )
        ]

    before_list = patched_gp["contentBlocks"][address]
    before = json.dumps(before_list, ensure_ascii=False)
    patched_gp["contentBlocks"][address] = items
    return [
        BlueprintRepair(
            issueType=issue.type, target=address, field=field,
            before=before, after=json.dumps(items, ensure_ascii=False),
            success=True,
        )
    ]


def _dispatch_issue(
    issue: CriticIssue,
    proposal: HeroCopyPatch | OfferListPatch,
    patched_gp: dict[str, Any],
    patched_brief: dict[str, Any],
) -> list[BlueprintRepair]:
    if issue.type == "thin_offer" and isinstance(proposal, OfferListPatch):
        return _apply_offer_patch(issue, proposal, patched_gp, patched_brief)
    if isinstance(proposal, HeroCopyPatch):
        return _apply_hero_patch(issue, proposal, patched_gp, patched_brief)
    return [
        BlueprintRepair(
            issueType=issue.type, target=issue.target, field="",
            success=False, detail="proposal shape did not match issue type",
        )
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _eligible_issues(
    critic: CriticResult | None, trigger_types: frozenset[str]
) -> list[CriticIssue]:
    """Eligible issues, high-severity first (then medium, then low)."""
    if critic is None:
        return []
    order = {"high": 0, "medium": 1, "low": 2}
    eligible = [i for i in critic.issues if i.type in trigger_types]
    return sorted(eligible, key=lambda i: order.get(i.severity, 3))


def apply_blueprint_repairs(
    *,
    generation_package: dict[str, Any],
    site_brief: dict[str, Any] | None,
    critic: CriticResult | None,
    trigger_types: frozenset[str],
    max_passes: int,
    target_dir: Path | None = None,
    rerender: RerenderFn | None = None,
    model_call: Callable[..., HeroCopyPatch | OfferListPatch | None] | None = None,
) -> BlueprintRepairOutcome:
    """Run the bounded blueprint-repair loop and return an outcome.

    ``model_call`` defaults to :func:`run_repair_model`; tests inject a
    deterministic stub so the matrix runs without a real OpenAI key. The
    originals are never mutated - patches land on deep copies carried back on the
    outcome.
    """
    brief = site_brief if isinstance(site_brief, dict) else {}
    call = model_call or run_repair_model

    eligible0 = _eligible_issues(critic, trigger_types)
    if not eligible0:
        return BlueprintRepairOutcome(status="not-needed")

    # No key -> skip entirely (no synthetic success=False entries; kor-5 contract).
    if not has_openai_api_key():
        return BlueprintRepairOutcome(
            status="no-fix-applied", skipped=True,
            skipped_reason="no-openai-api-key",
        )

    patched_gp = copy.deepcopy(generation_package)
    patched_brief = copy.deepcopy(brief)

    repairs: list[BlueprintRepair] = []
    passes = 0
    any_model_response = False
    current_eligible = eligible0
    final_critic = critic

    while passes < max_passes:
        applied_this_pass = False
        for issue in current_eligible:
            proposal = call(issue, patched_gp, patched_brief)
            if proposal is None:
                continue  # model unavailable for this issue -> skip, no entry
            any_model_response = True
            entries = _dispatch_issue(issue, proposal, patched_gp, patched_brief)
            # Schema-guard: only keep a successful apply if the patched package
            # still validates; otherwise roll the field back is overkill - we
            # validate the whole package and drop ALL successes this pass if it
            # breaks the contract (defensive; should never trip for copy edits).
            repairs.extend(entries)
            if any(e.success for e in entries):
                applied_this_pass = True
        if not applied_this_pass:
            break
        if not _generation_package_valid(patched_gp):
            # Extremely defensive: a copy edit broke the schema. Abort the pass,
            # mark the successes as failed, and do not re-render.
            for entry in repairs:
                if entry.success:
                    entry.success = False
                    entry.detail = (
                        "rolled back: patched Generation Package failed schema "
                        "validation"
                    )
            patched_gp = copy.deepcopy(generation_package)
            patched_brief = copy.deepcopy(brief)
            break
        if rerender is not None:
            rerender(patched_gp, patched_brief)
        final_critic = run_deterministic_critic(
            generation_package=patched_gp,
            site_brief=patched_brief,
            target_dir=target_dir,
        )
        passes += 1
        current_eligible = _eligible_issues(final_critic, trigger_types)

    if not any_model_response:
        # Model never produced anything usable -> skip semantics (no entries).
        return BlueprintRepairOutcome(
            status="no-fix-applied", skipped=True,
            skipped_reason="model-unavailable", repairs=[],
        )

    successes = [r for r in repairs if r.success]
    if not successes:
        return BlueprintRepairOutcome(
            status="no-fix-applied", passes=0, repairs=repairs,
        )

    remaining = _eligible_issues(final_critic, trigger_types)
    status: BlueprintRepairStatus = "fixed" if not remaining else "partial-fix"
    return BlueprintRepairOutcome(
        status=status, passes=passes, repairs=repairs,
        patched_generation_package=patched_gp, patched_site_brief=patched_brief,
        final_critic=final_critic,
    )


def append_blueprint_repair_trace_event(
    run_dir: Path,
    run_id: str,
    outcome: BlueprintRepairOutcome,
) -> None:
    """Append a non-blocking blueprint-repair event to ``<run_dir>/trace.ndjson``.

    Emits ``repair.blueprint_skipped`` when the pass short-circuited (no key /
    model unavailable) and ``repair.blueprint_patched`` otherwise (at least one
    real repairModel attempt happened). Mirrors the Engine Event record shape
    that ``scripts/build_site.py:Trace`` and ``critic.append_critic_trace_event``
    write so the event is consistent with the rest of the trace. Status is always
    ``warning`` because blueprint-repair never blocks. The file is appended to
    (never truncated); callers only invoke this when a run directory exists.
    """
    applied = sum(1 for r in outcome.repairs if r.success)
    rejected = sum(1 for r in outcome.repairs if not r.success)
    if outcome.skipped:
        event = "repair.blueprint_skipped"
        message = (
            f"Blueprint repair skipped ({outcome.skipped_reason}); "
            f"status={outcome.status} passes={outcome.passes}"
        )
    else:
        event = "repair.blueprint_patched"
        message = (
            f"Blueprint repair status={outcome.status} passes={outcome.passes} "
            f"applied={applied} rejected={rejected}"
        )
    record = {
        "runId": run_id,
        "phase": "build",
        "event": event,
        "status": "warning",
        "message": message,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "payloadPath": "repair-result.json",
    }
    trace_path = run_dir / "trace.ndjson"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
