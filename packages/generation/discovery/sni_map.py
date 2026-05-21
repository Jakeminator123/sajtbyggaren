"""Resolver helper för SNI 2025 → Discovery category candidate.

V1 är read-only diagnostik: ingen runtime-konsumtion av SNI sker än, och
helpern returnerar bara en kandidat ``wizardCategoryId`` (plus matchad
SNI-prefix, label och confidence). Den får aldrig returnera
``starterId``, ``scaffoldId``, ``variantId``, ``dossierId`` eller
``selectedDossiers`` — Discovery Resolver + Discovery Taxonomy avgör
fortsatt scaffold/variant/starter/capabilities efter kategori-valet.

API:
- :func:`normalize_sni_code` — strippa whitespace/dot/space och returnera
  en digit-only form (eller den ursprungliga section-bokstaven A-U).
- :func:`load_sni_discovery_map` — läs
  ``governance/policies/sni-discovery-map.v1.json`` och returnera ett
  in-memory uppslag.
- :func:`resolve_sni_discovery_category` — given en SNI-kod (i någon
  vanlig form) returnera ``SniMatch`` med kandidat-kategori eller
  ``None`` när policyn saknar matchning. Kastar inte exception för
  trasiga eller okända koder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "policies"
    / "sni-discovery-map.v1.json"
)
"""Canonical placering för SNI Discovery Map-policyn."""

_ALLOWED_LEVELS = ("group", "division")
"""Matchningsordning: mest specifik först."""


@dataclass(frozen=True, slots=True)
class SniMapping:
    """En enskild policyrad (huvudgrupp eller grupp-override)."""

    sniCode: str
    level: str
    wizardCategoryId: str
    confidence: str
    labelSv: str | None = None
    notesSv: str | None = None


@dataclass(frozen=True, slots=True)
class SniDiscoveryMap:
    """In-memory representation av ``sni-discovery-map.v1.json``."""

    policy_id: str
    version: int
    reference_taxonomy: str | None
    divisions: dict[str, SniMapping]
    groups: dict[str, SniMapping]

    def all_mappings(self) -> list[SniMapping]:
        """Returnerar alla policyrader, divisions först sorterade på sniCode."""
        return sorted(
            list(self.divisions.values()) + list(self.groups.values()),
            key=lambda m: (m.level != "division", m.sniCode),
        )


@dataclass(frozen=True, slots=True)
class SniMatch:
    """Resultat av :func:`resolve_sni_discovery_category`.

    ``input`` är det ursprungliga argumentet (oförändrat),
    ``normalizedCode`` är resultatet av :func:`normalize_sni_code`,
    ``matchedSniCode`` är policyradens prefix (eller ``None`` om ingen
    rad matchade), ``matchedLevel`` är ``"division"`` / ``"group"`` /
    ``"unknown"``. Resultatet får aldrig innehålla starter/scaffold/
    variant/Dossier-direktval.
    """

    input: str
    normalizedCode: str
    matchedLevel: str
    matchedSniCode: str | None
    wizardCategoryId: str | None
    labelSv: str | None
    confidence: str | None
    notesSv: str | None
    sourcePolicy: str


def normalize_sni_code(value: str | None) -> str:
    """Normalize en SNI-kod till digit-only form (eller behåll bokstaven).

    Hanterar de vanliga formerna operatören skickar:

    - ``"56"`` → ``"56"``
    - ``"56.1"`` → ``"561"``
    - ``"56.10"`` → ``"5610"``
    - ``"56.100"`` → ``"56100"``
    - ``"56100"`` → ``"56100"``
    - ``" 56 "`` → ``"56"``
    - ``"A"`` → ``"A"``  (section letter)
    - ``""`` / ``None`` → ``""``

    Funktionen kastar inte exception för trasiga värden. Tecken som inte
    är siffror eller A-Z-bokstäver droppas.
    """
    if not value:
        return ""
    text = str(value).strip().upper()
    if not text:
        return ""
    if text[0].isalpha() and len(text) == 1:
        return text
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits


def _empty_match(value: str, *, source_policy: str, level: str = "unknown") -> SniMatch:
    return SniMatch(
        input=value,
        normalizedCode=normalize_sni_code(value),
        matchedLevel=level,
        matchedSniCode=None,
        wizardCategoryId=None,
        labelSv=None,
        confidence=None,
        notesSv=None,
        sourcePolicy=source_policy,
    )


def load_sni_discovery_map(path: Path | None = None) -> SniDiscoveryMap:
    """Läs SNI Discovery Map-policyn från disk.

    ``path`` kan överskridas för tester. Helpern validerar inte mot
    schemat — det görs av ``scripts/governance_validate.py``. Vid trasig
    JSON propageras :class:`json.JSONDecodeError` så callern kan rapportera
    konfigurationsfelet.
    """
    actual = path if path is not None else DEFAULT_POLICY_PATH
    payload: dict[str, Any] = json.loads(actual.read_text(encoding="utf-8"))

    divisions: dict[str, SniMapping] = {}
    for raw in payload.get("divisionMappings", []) or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("sniCode", "")).strip()
        if not code:
            continue
        divisions[code] = SniMapping(
            sniCode=code,
            level="division",
            wizardCategoryId=str(raw.get("wizardCategoryId", "")),
            confidence=str(raw.get("confidence", "")),
            labelSv=raw.get("labelSv"),
            notesSv=raw.get("notesSv"),
        )

    groups: dict[str, SniMapping] = {}
    for raw in payload.get("groupOverrides", []) or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("sniCode", "")).strip()
        if not code:
            continue
        groups[code] = SniMapping(
            sniCode=code,
            level="group",
            wizardCategoryId=str(raw.get("wizardCategoryId", "")),
            confidence=str(raw.get("confidence", "")),
            labelSv=raw.get("labelSv"),
            notesSv=raw.get("notesSv"),
        )

    return SniDiscoveryMap(
        policy_id=str(payload.get("policyId", "")),
        version=int(payload.get("version", 0) or 0),
        reference_taxonomy=payload.get("referenceTaxonomy"),
        divisions=divisions,
        groups=groups,
    )


def resolve_sni_discovery_category(
    value: str | None,
    *,
    sni_map: SniDiscoveryMap | None = None,
    policy_path: Path | None = None,
) -> SniMatch:
    """Matcha en SNI-kod mot policyn och returnera kandidat-kategori.

    Algoritmen är mest specifik först:

    1. Normalisera input via :func:`normalize_sni_code`.
    2. Om normaliserad kod är tom eller en section-bokstav → ingen match.
    3. Försök matcha den 3-siffriga prefixen mot ``groupOverrides``.
    4. Annars försök matcha den 2-siffriga prefixen mot
       ``divisionMappings``.
    5. Annars returnera unknown.

    Helpern returnerar **aldrig** ``starterId``, ``scaffoldId``,
    ``variantId``, ``dossierId`` eller ``selectedDossiers``. Trasig
    input ger ``unknown`` utan exception.
    """
    resolved_map = sni_map if sni_map is not None else load_sni_discovery_map(policy_path)
    source_policy = resolved_map.policy_id or "sni-discovery-map.v1"
    original = "" if value is None else str(value)

    if not original.strip():
        return _empty_match(original, source_policy=source_policy)

    normalized = normalize_sni_code(original)
    if not normalized or not normalized.isdigit():
        return SniMatch(
            input=original,
            normalizedCode=normalized,
            matchedLevel="unknown",
            matchedSniCode=None,
            wizardCategoryId=None,
            labelSv=None,
            confidence=None,
            notesSv=None,
            sourcePolicy=source_policy,
        )

    for level in _ALLOWED_LEVELS:
        prefix_length = 3 if level == "group" else 2
        if len(normalized) < prefix_length:
            continue
        prefix = normalized[:prefix_length]
        registry = resolved_map.groups if level == "group" else resolved_map.divisions
        mapping = registry.get(prefix)
        if mapping is None:
            continue
        return SniMatch(
            input=original,
            normalizedCode=normalized,
            matchedLevel=level,
            matchedSniCode=mapping.sniCode,
            wizardCategoryId=mapping.wizardCategoryId or None,
            labelSv=mapping.labelSv,
            confidence=mapping.confidence or None,
            notesSv=mapping.notesSv,
            sourcePolicy=source_policy,
        )

    return SniMatch(
        input=original,
        normalizedCode=normalized,
        matchedLevel="unknown",
        matchedSniCode=None,
        wizardCategoryId=None,
        labelSv=None,
        confidence=None,
        notesSv=None,
        sourcePolicy=source_policy,
    )


def match_to_dict(match: SniMatch) -> dict[str, Any]:
    """Serialize a :class:`SniMatch` to plain dict (Backoffice helper)."""
    return {
        "input": match.input,
        "normalizedCode": match.normalizedCode,
        "matchedLevel": match.matchedLevel,
        "matchedSniCode": match.matchedSniCode,
        "wizardCategoryId": match.wizardCategoryId,
        "labelSv": match.labelSv,
        "confidence": match.confidence,
        "notesSv": match.notesSv,
        "sourcePolicy": match.sourcePolicy,
    }
