"""B198: named-dossier preference in apply (utbruten ur test_patch_apply.py).

Locks the named-Dossier switch a section_add follow-up can carry
(``apply_patch_plan(dossier_preferences=...)``, levererad i #301 + #303):

- a named preference mounts the named Dossier instead of the capability
  default (resend-contact-form i stället för mailto),
- the switch is EXCLUSIVE per capability EVEN SEQUENTIALLY (a v2-mounted
  mailto is displaced by a v3-chosen resend - no hybrid contact forms),
- an apply WITHOUT a preference never removes a mounted Dossier, and
- an unregistered preference falls back honestly to the default.

Egen ämnesfil per test-hygienens 1200-radstak (tests/test_test_hygiene.py);
delar helpers med tests/test_patch_apply.py i stället för att duplicera dem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.apply import apply_patch_plan  # noqa: E402
from packages.generation.orchestration.patch import PatchPlan  # noqa: E402
from tests.test_patch_apply import SITE_ID, _init_site  # noqa: E402

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core


def test_section_add_dossier_preference_mounts_named_dossier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B198: a follow-up that NAMED a specific implementing dossier ("resend")
    mounts it in ``selectedDossiers.required`` instead of the mailto default."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)

    result = apply_patch_plan(
        PatchPlan(patches=[], valid=True),
        site_id=SITE_ID,
        output_dir=tmp_path,
        added_capabilities=["contact-form"],
        dossier_preferences={"contact-form": "resend-contact-form"},
    )
    assert result.applied is True

    v2_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    required = v2_pi["selectedDossiers"]["required"]
    assert "resend-contact-form" in required
    assert "mailto-contact-form" not in required, (
        "the named preference must REPLACE the capability default, not mount "
        f"both contact forms; got {required!r}"
    )


def test_dossier_preference_displaces_previously_mounted_sibling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Extern granskning 2026-06-11 (fynd 3): en namngiven dossier-preferens
    är EXKLUSIV per capability även SEKVENTIELLT - en sajt som monterade
    mailto-defaulten i v2 och väljer resend i v3 får inte behålla båda
    kontaktformulären (ingen hybrid)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)

    # v2: vanlig section_add av contact-form -> mailto-defaulten monteras.
    first = apply_patch_plan(
        PatchPlan(patches=[], valid=True),
        site_id=SITE_ID,
        output_dir=tmp_path,
        added_capabilities=["contact-form"],
    )
    assert first.applied is True
    v2_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert "mailto-contact-form" in v2_pi["selectedDossiers"]["required"]

    # v3: namngiven preferens (resend) -> mailto-syskonet ska bort.
    second = apply_patch_plan(
        PatchPlan(patches=[], valid=True),
        site_id=SITE_ID,
        output_dir=tmp_path,
        added_capabilities=["contact-form"],
        dossier_preferences={"contact-form": "resend-contact-form"},
    )
    assert second.applied is True
    v3_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v3.project-input.json").read_text(encoding="utf-8")
    )
    required = v3_pi["selectedDossiers"]["required"]
    assert "resend-contact-form" in required
    assert "mailto-contact-form" not in required, (
        "den carry-forwardade mailto-monteringen måste ersättas av den "
        f"namngivna preferensen, inte samexistera; got {required!r}"
    )


def test_apply_without_preference_never_removes_mounted_dossiers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exklusivitets-fixens säkerhetsgräns: ett apply UTAN preferens får
    aldrig ta bort en redan monterad dossier (displacement sker ENBART vid
    en uttryckligen namngiven preferens)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)

    first = apply_patch_plan(
        PatchPlan(patches=[], valid=True),
        site_id=SITE_ID,
        output_dir=tmp_path,
        added_capabilities=["contact-form"],
        dossier_preferences={"contact-form": "resend-contact-form"},
    )
    assert first.applied is True

    # v3: orelaterad section_add (hours) utan preferens.
    second = apply_patch_plan(
        PatchPlan(patches=[], valid=True),
        site_id=SITE_ID,
        output_dir=tmp_path,
        added_capabilities=["hours"],
    )
    assert second.applied is True
    v3_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v3.project-input.json").read_text(encoding="utf-8")
    )
    required = v3_pi["selectedDossiers"]["required"]
    assert "resend-contact-form" in required, (
        "en monterad dossier får aldrig försvinna av ett senare apply utan "
        f"preferens; got {required!r}"
    )
    assert "opening-hours" in required


def test_section_add_invalid_dossier_preference_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B198 honesty: an unregistered preference is dropped and the capability
    default is mounted - chat can never mount an unknown dossier."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)

    result = apply_patch_plan(
        PatchPlan(patches=[], valid=True),
        site_id=SITE_ID,
        output_dir=tmp_path,
        added_capabilities=["contact-form"],
        dossier_preferences={"contact-form": "not-a-registered-dossier"},
    )
    assert result.applied is True

    v2_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    required = v2_pi["selectedDossiers"]["required"]
    assert "mailto-contact-form" in required
    assert "not-a-registered-dossier" not in required
