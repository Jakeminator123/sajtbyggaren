"""kor-4a: deterministic Quality Critic (critic v0).

A **deterministic** self-critique lane that reads the blueprint (Generation
Package ``contentBlocks`` + Site Brief honesty/contact fields) plus the
generated output and produces repairable issues + a simple score. There is
**no LLM, no model role and no OpenAI call** here - that is ``kor-4b``
(``verifierModel``). This module is the cheap, stable regression guard the
LLM critic later builds on (``docs/heavy-llm-flow/kor-4a-deterministic-critic.md``).

Contract (re-used verbatim by ``kor-4b``)::

    critic = {
        "score": <int 0-100>,
        "issues": [
            {"severity", "type", "target", "message", "repairHint"}
        ],
        "source": "deterministic-v0",
    }

``target`` is always the address contract ``<route>.<section>`` (the same
addressing as ``contentBlocks`` / ``sectionPlan``), or the site-wide pseudo
route ``global.<section>`` for brief-level fields that are not bound to a
single section (e.g. brief-level contact placeholders).

**Warning-lane only.** The critic NEVER changes ``QualityResult.status``
(``ok``/``degraded``/``failed``); it is reported alongside the blocking and
warning checks. Repair application is ``kor-5``, not here.

Score formula (documented + locked by tests)::

    score = max(0, 100 - sum(_SEVERITY_WEIGHT[issue.severity] for issue in issues))

with ``_SEVERITY_WEIGHT = {"high": 20, "medium": 10, "low": 5}``. A clean
blueprint scores 100; each finding subtracts a weight proportional to its
severity, floored at 0. The formula is intentionally simple and monotonic so
it works as a regression signal and ``kor-4b`` can refine it without breaking
the contract.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

CriticSeverity = Literal["high", "medium", "low"]
CriticIssueType = Literal[
    "generic_copy",
    "thin_offer",
    "placeholder_leakage",
    "missing_local_context",
    "missing_cta",
]
CriticSource = Literal["deterministic-v0"]

# Weighted-by-severity score penalties. Documented in the module docstring and
# locked by tests/test_quality_gate_critic.py::test_score_formula_is_weighted_by_severity.
_SEVERITY_WEIGHT: dict[str, int] = {"high": 20, "medium": 10, "low": 5}

# A blueprint offer (services/products) thinner than this many items reads as a
# thin offer. Lovable-gap audit (docs/current-focus.md) lists "tunt erbjudande
# (1 tjänst/produkt)" as a concrete finish gap.
_THIN_OFFER_MIN_ITEMS = 3

# Section ids that carry the primary offer list. Mirrors
# packages/generation/build/blueprint_render.py:_OFFER_SECTION_IDS so the critic
# inspects the same block the renderer treats as the offer.
_OFFER_SECTION_IDS: frozenset[str] = frozenset(
    {
        "service-list",
        "product-grid",
        "treatment-list",
        "practice-grid",
        "selected-work-grid",
        "menu-list",
    }
)

# Keys on a hero content block that count as a present call-to-action.
_HERO_CTA_KEYS: tuple[str, ...] = (
    "primaryCta",
    "secondaryCta",
    "cta",
    "ctaLabel",
    "ctaText",
)

# Generic template phrases (Swedish + English). A blueprint string that contains
# one of these (casefolded, whitespace-normalised) reads as ungrounded mall-copy
# rather than business-specific copy. Kept as fragments so a longer real sentence
# that merely embeds the cliché still trips. Extend deliberately; every entry is
# a phrase a human would recognise as filler.
_GENERIC_PHRASES: tuple[str, ...] = (
    "välkommen till vår hemsida",
    "välkommen till vår webbplats",
    "vi erbjuder tjänster av högsta kvalitet",
    "tjänster av högsta kvalitet",
    "kvalitet och service i fokus",
    "vi sätter kunden i fokus",
    "vi hjälper dig med allt inom",
    "marknadens bästa",
    "ledande leverantör",
    "vi är ett ledande företag",
    "professionell och pålitlig",
    "din partner för framgång",
    "lorem ipsum",
    "welcome to our website",
    "we offer high quality services",
    "high quality services",
    "your trusted partner",
    "best in the business",
    "we are committed to excellence",
    "your one-stop shop",
)

# Placeholder-contact regexes (honesty engine, docs/heavy-llm-flow/04 §9). The
# kör-4a card names 08-000…, example.se and "lämnas på förfrågan" explicitly;
# we also catch the .com sibling and the e-mail form of the example domain.
_PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("08-000-placeholder-phone", re.compile(r"\b08[-\s]?0{3}\b")),
    ("example-domain", re.compile(r"@?\bexample\.(?:se|com)\b", re.IGNORECASE)),
    (
        "address-on-request",
        re.compile(r"l[äa]mnas\s+p[åa]\s+f[öo]rfr[åa]gan", re.IGNORECASE),
    ),
)

# File suffixes the optional generated-files scan reads as customer-facing copy.
_TEXT_EXTENSIONS: frozenset[str] = frozenset({".tsx", ".jsx"})
_SCAN_SKIP_DIRS: frozenset[str] = frozenset(
    {"node_modules", ".next", ".git", "out", ".turbo"}
)

# Site-wide pseudo route for brief-level fields not bound to a single section
# (keeps every ``target`` on the ``<route>.<section>`` contract).
_GLOBAL_ROUTE = "global"


class CriticIssue(BaseModel):
    """One deterministic critic finding.

    ``target`` is on the ``<route>.<section>`` address contract. ``repairHint``
    is a short, deterministic suggestion ``kor-5`` (and a human operator) can
    act on - it is advice, never an applied change.
    """

    severity: CriticSeverity
    type: CriticIssueType
    target: str
    message: str
    repairHint: str


class CriticResult(BaseModel):
    """Deterministic critic output embedded in ``quality-result.json:critic``.

    Same shape ``kor-4b``'s ``verifierModel`` critic re-uses. ``source`` is
    locked to ``deterministic-v0`` so a consumer can tell a heuristic finding
    from a future model finding.
    """

    score: int = Field(ge=0, le=100)
    issues: list[CriticIssue] = Field(default_factory=list)
    source: CriticSource = "deterministic-v0"


# ---------------------------------------------------------------------------
# Blueprint text extraction
# ---------------------------------------------------------------------------


def _clean_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _iter_block_texts(content_blocks: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield ``(address, text)`` for every customer-copy string in the blueprint.

    Walks the per-section content blocks keyed by ``<routeId>.<sectionId>`` and
    descends into dicts and lists, always reporting the originating address so a
    finding can point back to the exact section.
    """

    def _walk(address: str, value: Any) -> Iterator[tuple[str, str]]:
        if isinstance(value, str):
            text = _clean_str(value)
            if text:
                yield address, text
        elif isinstance(value, dict):
            for child in value.values():
                yield from _walk(address, child)
        elif isinstance(value, list):
            for item in value:
                yield from _walk(address, item)

    for address, value in content_blocks.items():
        if not isinstance(address, str):
            continue
        yield from _walk(address, value)


def _offer_blocks(content_blocks: dict[str, Any]) -> list[tuple[str, list[Any]]]:
    """Return ``(address, items)`` for every recognised offer-list block."""
    blocks: list[tuple[str, list[Any]]] = []
    for address, value in content_blocks.items():
        if not isinstance(address, str) or not isinstance(value, list):
            continue
        section_id = address.partition(".")[2]
        if section_id in _OFFER_SECTION_IDS:
            blocks.append((address, value))
    return blocks


def _hero_addresses(content_blocks: dict[str, Any]) -> list[str]:
    return [
        address
        for address in content_blocks
        if isinstance(address, str) and address.partition(".")[2] == "hero"
    ]


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def _check_generic_copy(content_blocks: dict[str, Any]) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    seen: set[str] = set()
    for address, text in _iter_block_texts(content_blocks):
        normalised = _normalise(text)
        for phrase in _GENERIC_PHRASES:
            if phrase in normalised and address not in seen:
                seen.add(address)
                issues.append(
                    CriticIssue(
                        severity="medium",
                        type="generic_copy",
                        target=address,
                        message=(
                            f"Generisk mallcopy upptäckt i {address}: "
                            f'"{text[:80]}".'
                        ),
                        repairHint=(
                            "Ersätt mallfrasen med branschspecifik, grundad copy "
                            "(briefModel/copywriter), inte en generisk superlativ."
                        ),
                    )
                )
                break
    return issues


def _check_thin_offer(content_blocks: dict[str, Any]) -> list[CriticIssue]:
    offer_blocks = _offer_blocks(content_blocks)
    if not offer_blocks:
        return []
    issues: list[CriticIssue] = []
    for address, items in offer_blocks:
        count = sum(1 for item in items if isinstance(item, (dict, str)) and item)
        if count < _THIN_OFFER_MIN_ITEMS:
            issues.append(
                CriticIssue(
                    severity="medium",
                    type="thin_offer",
                    target=address,
                    message=(
                        f"Tunt erbjudande i {address}: {count} post(er) "
                        f"(tröskel {_THIN_OFFER_MIN_ITEMS})."
                    ),
                    repairHint=(
                        f"Lyft fram minst {_THIN_OFFER_MIN_ITEMS} konkreta "
                        "tjänster/erbjudanden med egna sammanfattningar."
                    ),
                )
            )
    return issues


def _scan_placeholder(text: str) -> str | None:
    for label, pattern in _PLACEHOLDER_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _check_placeholder_leakage(
    content_blocks: dict[str, Any],
    site_brief: dict[str, Any],
    file_texts: list[tuple[str, str]],
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    seen: set[tuple[str, str]] = set()

    def _add(target: str, label: str, snippet: str) -> None:
        key = (target, label)
        if key in seen:
            return
        seen.add(key)
        issues.append(
            CriticIssue(
                severity="high",
                type="placeholder_leakage",
                target=target,
                message=(
                    f"Platshållarkontakt ({label}) läcker i {target}: "
                    f'"{snippet[:80]}".'
                ),
                repairHint=(
                    "Ta bort platshållarkontakten; använd en riktig uppgift "
                    "eller dölj kanalen (businessFacts.unknowns)."
                ),
            )
        )

    for address, text in _iter_block_texts(content_blocks):
        label = _scan_placeholder(text)
        if label is not None:
            _add(address, label, text)

    for field in ("contactPhone", "contactEmail", "contactAddress"):
        value = _clean_str(site_brief.get(field))
        if value is None:
            continue
        label = _scan_placeholder(value)
        if label is not None:
            _add(f"{_GLOBAL_ROUTE}.contact", label, value)

    for address, text in file_texts:
        label = _scan_placeholder(text)
        if label is not None:
            _add(address, label, text)

    return issues


def _primary_location_token(location_hint: str) -> str | None:
    """Return the leading place token from a free-form locationHint."""
    cleaned = re.split(r"[,/]", location_hint, maxsplit=1)[0].strip()
    if not cleaned:
        return None
    # First whitespace-delimited token covers "Malmö", and the multi-word case
    # ("Stockholm city") still matches via the full-token containment below.
    return cleaned


def _check_missing_local_context(
    content_blocks: dict[str, Any],
    site_brief: dict[str, Any],
    file_texts: list[tuple[str, str]],
) -> list[CriticIssue]:
    location_hint = _clean_str(site_brief.get("locationHint"))
    if location_hint is None:
        return []
    token = _primary_location_token(location_hint)
    if token is None:
        return []
    needle = _normalise(token)
    haystacks = [_normalise(text) for _, text in _iter_block_texts(content_blocks)]
    haystacks += [_normalise(text) for _, text in file_texts]
    if any(needle in hay for hay in haystacks):
        return []
    hero_addresses = _hero_addresses(content_blocks)
    target = hero_addresses[0] if hero_addresses else "home.hero"
    return [
        CriticIssue(
            severity="low",
            type="missing_local_context",
            target=target,
            message=(
                f'locationHint "{location_hint}" anges men orten "{token}" '
                "nämns inte i output."
            ),
            repairHint=(
                f"Nämn orten ({token}) i hero/positionering för lokal "
                "relevans och sökbarhet."
            ),
        )
    ]


def _hero_has_cta(content_blocks: dict[str, Any]) -> bool:
    for address in _hero_addresses(content_blocks):
        block = content_blocks.get(address)
        if isinstance(block, dict) and any(
            _clean_str(block.get(key)) for key in _HERO_CTA_KEYS
        ):
            return True
    return False


def _brief_has_cta(site_brief: dict[str, Any]) -> bool:
    conversion = site_brief.get("conversion")
    if isinstance(conversion, dict):
        if _clean_str(conversion.get("primaryCta")) or _clean_str(
            conversion.get("secondaryCta")
        ):
            return True
    return False


def _check_missing_cta(
    content_blocks: dict[str, Any], site_brief: dict[str, Any]
) -> list[CriticIssue]:
    if _hero_has_cta(content_blocks) or _brief_has_cta(site_brief):
        return []
    hero_addresses = _hero_addresses(content_blocks)
    target = hero_addresses[0] if hero_addresses else "home.hero"
    return [
        CriticIssue(
            severity="high",
            type="missing_cta",
            target=target,
            message="Ingen CTA i hero/contact - besökaren saknar nästa steg.",
            repairHint=(
                "Lägg en tydlig primär CTA i hero (conversion.primaryCta), "
                "t.ex. 'Be om offert' eller 'Boka tid'."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Generated-files scan (optional)
# ---------------------------------------------------------------------------


def _route_section_for_file(target_dir: Path, page: Path) -> str:
    """Derive a ``<route>.<section>`` target from a generated page path.

    Generated files do not carry section ids, so we report the route derived
    from the ``app/`` directory and a synthetic ``page`` section. ``app/page.tsx``
    -> ``home.page``; ``app/kontakt/page.tsx`` -> ``kontakt.page``.
    """
    try:
        relative = page.parent.relative_to(target_dir / "app")
    except ValueError:
        return f"{_GLOBAL_ROUTE}.page"
    parts = [part for part in relative.parts if part not in ("", ".")]
    route = "home" if not parts else "-".join(parts)
    return f"{route}.page"


def _read_generated_file_texts(target_dir: Path | None) -> list[tuple[str, str]]:
    """Return ``(target, text)`` for every line in the generated TSX/JSX files.

    Best-effort and bounded: skips build/dependency directories and silently
    drops unreadable files. Returns an empty list when ``target_dir`` is None or
    has no generated pages so the critic stays blueprint-only by default.
    """
    if target_dir is None:
        return []
    app_dir = target_dir / "app"
    if not app_dir.exists():
        return []
    texts: list[tuple[str, str]] = []
    for page in sorted(target_dir.rglob("*")):
        if page.suffix not in _TEXT_EXTENSIONS:
            continue
        if any(part in _SCAN_SKIP_DIRS for part in page.parts):
            continue
        try:
            content = page.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        target = _route_section_for_file(target_dir, page)
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                texts.append((target, stripped))
    return texts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _score_for(issues: list[CriticIssue]) -> int:
    penalty = sum(_SEVERITY_WEIGHT.get(issue.severity, 0) for issue in issues)
    return max(0, 100 - penalty)


def run_deterministic_critic(
    *,
    generation_package: dict[str, Any] | None = None,
    site_brief: dict[str, Any] | None = None,
    target_dir: Path | None = None,
) -> CriticResult:
    """Run the five deterministic heuristics and return a CriticResult.

    Reads the blueprint (``generation_package.contentBlocks`` + the Site Brief
    honesty/contact fields) and, when ``target_dir`` is given, the generated
    TSX/JSX output. No LLM, no model role, no OpenAI call. The result NEVER
    feeds ``QualityResult.status`` aggregation - it is a warning lane.
    """
    gp = generation_package if isinstance(generation_package, dict) else {}
    brief = site_brief if isinstance(site_brief, dict) else {}
    content_blocks = gp.get("contentBlocks")
    content_blocks = content_blocks if isinstance(content_blocks, dict) else {}

    file_texts = _read_generated_file_texts(target_dir)

    issues: list[CriticIssue] = []
    issues += _check_generic_copy(content_blocks)
    issues += _check_thin_offer(content_blocks)
    issues += _check_placeholder_leakage(content_blocks, brief, file_texts)
    issues += _check_missing_local_context(content_blocks, brief, file_texts)
    issues += _check_missing_cta(content_blocks, brief)

    return CriticResult(score=_score_for(issues), issues=issues)


def append_critic_trace_event(
    run_dir: Path,
    run_id: str,
    critic: CriticResult,
) -> None:
    """Append a non-blocking critic event to ``<run_dir>/trace.ndjson``.

    Mirrors the Engine Event record shape that ``scripts/build_site.py:Trace``
    writes (``runId``/``phase``/``event``/``status``/``message``/``timestamp``/
    ``payloadPath``) so the critic event is consistent with the rest of the
    trace. Status is always ``warning`` because the critic never blocks. The
    file is appended to (never truncated) so an existing trace is preserved;
    callers only invoke this when a run directory exists.
    """
    high = sum(1 for issue in critic.issues if issue.severity == "high")
    record = {
        "runId": run_id,
        "phase": "build",
        "event": "critic.evaluated",
        "status": "warning",
        "message": (
            f"Deterministic critic score={critic.score} "
            f"issues={len(critic.issues)} (high={high}) "
            f"source={critic.source}"
        ),
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "payloadPath": "quality-result.json",
    }
    trace_path = run_dir / "trace.ndjson"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
