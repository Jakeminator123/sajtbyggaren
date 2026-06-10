"""Loader + resolver för branschprofiler per SNI-huvudgrupp (ADR 0045).

Profilen (``governance/policies/industry-profiles.v1.json``) är en mjuk
berikning ovanpå Discovery Taxonomy-kategorins defaults: extra
capabilities, rekommenderade sidor, copy-vinkel, trust-signaler, primär
CTA och bildspråk. Den väljer ALDRIG scaffold/variant/starter/Dossier —
det avgör Discovery Taxonomy efter kategorivalet, precis som idag.

API:
- :func:`load_industry_profiles` — läs policyn till ett in-memory
  uppslag (huvudgrupp -> :class:`IndustryProfile`).
- :func:`resolve_industry_profile` — given en SNI-kod i någon vanlig
  form, returnera profilen för kodens huvudgrupp eller ``None``.
  Kastar aldrig exception för trasig input (samma kontrakt som
  :func:`packages.generation.discovery.sni_map.resolve_sni_discovery_category`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .sni_map import normalize_sni_code

DEFAULT_PROFILES_PATH = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "policies"
    / "industry-profiles.v1.json"
)
"""Canonical placering för Industry Profiles-policyn."""


@dataclass(frozen=True, slots=True)
class IndustryProfile:
    """En branschprofil för en SNI-huvudgrupp."""

    profileId: str
    sniCode: str
    labelSv: str
    wizardCategoryId: str
    curated: bool
    copyAngle: str
    primaryCta: str
    toneHints: tuple[str, ...] = ()
    trustSignals: tuple[str, ...] = ()
    extraCapabilities: tuple[str, ...] = ()
    recommendedPages: tuple[str, ...] = ()
    imageryHints: tuple[str, ...] = ()
    notesSv: str | None = None


@dataclass(frozen=True, slots=True)
class IndustryProfilesPolicy:
    """In-memory representation av ``industry-profiles.v1.json``."""

    policy_id: str
    version: int
    profiles: dict[str, IndustryProfile] = field(default_factory=dict)

    def get(self, division_code: str) -> IndustryProfile | None:
        return self.profiles.get(division_code)


def _string_tuple(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(
        item.strip()
        for item in raw
        if isinstance(item, str) and item.strip()
    )


def load_industry_profiles(path: Path | None = None) -> IndustryProfilesPolicy:
    """Läs Industry Profiles-policyn från disk.

    ``path`` kan överskridas för tester. Schemavalidering görs av
    ``scripts/governance_validate.py``; trasig JSON propageras som
    :class:`json.JSONDecodeError` så callern ser konfigurationsfelet.
    """
    actual = path if path is not None else DEFAULT_PROFILES_PATH
    payload: dict[str, Any] = json.loads(actual.read_text(encoding="utf-8"))

    profiles: dict[str, IndustryProfile] = {}
    for raw in payload.get("divisionProfiles", []) or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("sniCode", "")).strip()
        if not code:
            continue
        profiles[code] = IndustryProfile(
            profileId=str(raw.get("profileId", "")),
            sniCode=code,
            labelSv=str(raw.get("labelSv", "")),
            wizardCategoryId=str(raw.get("wizardCategoryId", "")),
            curated=bool(raw.get("curated", False)),
            copyAngle=str(raw.get("copyAngle", "")),
            primaryCta=str(raw.get("primaryCta", "")),
            toneHints=_string_tuple(raw.get("toneHints")),
            trustSignals=_string_tuple(raw.get("trustSignals")),
            extraCapabilities=_string_tuple(raw.get("extraCapabilities")),
            recommendedPages=_string_tuple(raw.get("recommendedPages")),
            imageryHints=_string_tuple(raw.get("imageryHints")),
            notesSv=raw.get("notesSv") if isinstance(raw.get("notesSv"), str) else None,
        )

    return IndustryProfilesPolicy(
        policy_id=str(payload.get("policyId", "")),
        version=int(payload.get("version", 0) or 0),
        profiles=profiles,
    )


def resolve_industry_profile(
    value: str | None,
    *,
    profiles: IndustryProfilesPolicy | None = None,
    policy_path: Path | None = None,
) -> IndustryProfile | None:
    """Matcha en SNI-kod (valfri nivå) mot huvudgruppens profil.

    Normaliserar input via :func:`normalize_sni_code` och slår upp de
    två första siffrorna (huvudgruppen). Trasig/tom/för kort input ger
    ``None`` utan exception.
    """
    normalized = normalize_sni_code(value)
    if not normalized or not normalized.isdigit() or len(normalized) < 2:
        return None
    resolved = (
        profiles
        if profiles is not None
        else load_industry_profiles(policy_path)
    )
    return resolved.get(normalized[:2])


def profile_to_dict(profile: IndustryProfile) -> dict[str, Any]:
    """Serialize en :class:`IndustryProfile` till plain dict (UI/diagnostik)."""
    return {
        "profileId": profile.profileId,
        "sniCode": profile.sniCode,
        "labelSv": profile.labelSv,
        "wizardCategoryId": profile.wizardCategoryId,
        "curated": profile.curated,
        "copyAngle": profile.copyAngle,
        "primaryCta": profile.primaryCta,
        "toneHints": list(profile.toneHints),
        "trustSignals": list(profile.trustSignals),
        "extraCapabilities": list(profile.extraCapabilities),
        "recommendedPages": list(profile.recommendedPages),
        "imageryHints": list(profile.imageryHints),
        "notesSv": profile.notesSv,
    }


__all__ = [
    "DEFAULT_PROFILES_PATH",
    "IndustryProfile",
    "IndustryProfilesPolicy",
    "load_industry_profiles",
    "resolve_industry_profile",
    "profile_to_dict",
]
