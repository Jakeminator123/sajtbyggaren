"""Run governance_validate.py as a subprocess and assert exit code 0.

This guarantees that every policy under governance/policies/ matches its
JSON Schema and that no globally-forbidden term is used outside its
allowed anti-pattern fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR


@pytest.mark.governance
@pytest.mark.tooling
def test_governance_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "governance_validate.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "governance_validate.py failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _dossier_contract_policy() -> dict:
    return {
        "dossierDirectoryLayout": {
            "additionalRequiredFilesByClass": {
                "hard": [
                    "env-contract.json",
                    "code-contract.json",
                    "integration-contract.json",
                ]
            }
        },
        "envContractRequiredFields": [
            "requires",
            "designModeBehavior",
            "integrationModeBehavior",
        ],
        "codeContractRequiredFields": ["must", "avoid"],
        "integrationContractRequiredFields": [
            "provider",
            "activation",
            "mockMode",
            "verification",
        ],
    }


@pytest.mark.governance
@pytest.mark.tooling
def test_cross_check_hard_dossier_contracts_flags_missing_required_contract_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import governance_validate as gv

    dossier_dir = (
        tmp_path
        / "hard"
        / "broken-hard-dossier"
    )
    dossier_dir.mkdir(parents=True)
    (dossier_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "broken-hard-dossier",
                "class": "hard",
                "envVars": ["RESEND_API_KEY"],
            }
        ),
        encoding="utf-8",
    )
    (dossier_dir / "env-contract.json").write_text(
        json.dumps(
            {
                "requires": [
                    {
                        "name": "RESEND_API_KEY",
                        "purpose": "Runtime provider auth",
                        "scope": "runtime",
                    }
                ],
                "designModeBehavior": "Honest design mode",
                "integrationModeBehavior": "Server-side provider call",
            }
        ),
        encoding="utf-8",
    )
    (dossier_dir / "code-contract.json").write_text(
        json.dumps(
            {
                "must": ["Submit must target /api/contact/resend."],
                "avoid": ["No client-side provider calls."],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(gv, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gv, "DOSSIERS_DIR", tmp_path)
    errors = gv.cross_check_hard_dossier_contracts(
        {"dossier-contract.v1.json": _dossier_contract_policy()}
    )

    assert any(
        "broken-hard-dossier" in err and "integration-contract.json" in err
        for err in errors
    ), errors


@pytest.mark.governance
@pytest.mark.tooling
def test_cross_check_hard_dossier_contracts_ignores_soft_only_trees(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import governance_validate as gv

    soft_dir = tmp_path / "soft" / "soft-only-dossier"
    soft_dir.mkdir(parents=True)
    (soft_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "soft-only-dossier",
                "class": "soft",
                "envVars": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(gv, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gv, "DOSSIERS_DIR", tmp_path)
    errors = gv.cross_check_hard_dossier_contracts(
        {"dossier-contract.v1.json": _dossier_contract_policy()}
    )
    assert errors == []
