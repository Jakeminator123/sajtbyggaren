"""OpenClaw connection self-check (CLI).

Proves OpenClaw Core V0 is actually wired into the product WITHOUT having to
read terminal logs. There is nothing to install: OpenClaw Core V0 is plain
Python that ships inside this repo at
``packages/generation/orchestration/openclaw/`` and runs in the local
``.venv``. ``apps/viewser`` (``/api/prompt``) shells out to
``scripts/run_openclaw_followup.py`` which imports that package - no separate
service, no Docker.

This script verifies that wiring in layers and prints a clear PASS/FAIL lamp:

    1. Core import   - OpenClaw Core V0 is importable from packages/.
    2. CLI seam      - scripts/run_openclaw_followup.py exposes --apply.
    3. UI wiring     - apps/viewser route + runner call the apply bridge.
    4. Decision      - the deterministic decision classifies an edit vs a
                       question correctly (no build, no key, no disk).
    5. Apply (opt-in)- with --apply, run the real KÖR-7 chain (skip-build) on a
                       site and assert a follow-up materialises a NEW version.

Run:
    python scripts/verify_openclaw.py                 # safe, fast, no build, no key
    python scripts/verify_openclaw.py --apply         # + full chain on newest site (skip-build)
    python scripts/verify_openclaw.py --apply --site-id <siteId>

Exit code 0 = all PASS (green), 1 = at least one FAIL (red). The default mode
is deterministic: it touches no disk, runs no build and needs no
``OPENAI_API_KEY``. ``--apply`` writes one throwaway version on the chosen
site (the proof artefact) and is opt-in.

Conventions: code comments and identifiers in English
(governance/rules/code-in-english.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Make packages/ + scripts/ importable when running this file directly (mirrors
# scripts/run_openclaw_followup.py).
sys.path.insert(0, str(REPO_ROOT))


@dataclass
class Check:
    """One verification line: a name, a pass/fail boolean and a short detail."""

    name: str
    ok: bool
    detail: str = ""


def _check_core_import() -> Check:
    """OpenClaw Core V0 must be importable from the in-repo package."""
    try:
        from packages.generation.orchestration.openclaw import orchestrate
    except ImportError as exc:
        return Check("OpenClaw Core V0 importerbar", False, f"import-fel: {exc}")
    if not callable(orchestrate):
        return Check(
            "OpenClaw Core V0 importerbar", False, "orchestrate är inte anropbar"
        )
    return Check(
        "OpenClaw Core V0 importerbar",
        True,
        "packages/generation/orchestration/openclaw",
    )


def _check_cli_seam() -> Check:
    """The shell seam apps/viewser uses must exist and expose --apply."""
    script = REPO_ROOT / "scripts" / "run_openclaw_followup.py"
    if not script.exists():
        return Check("CLI-seam (run_openclaw_followup.py)", False, "filen saknas")
    try:
        text = script.read_text(encoding="utf-8")
    except OSError as exc:
        return Check("CLI-seam (run_openclaw_followup.py)", False, f"läsfel: {exc}")
    ok = "--apply" in text and "apply_followup_to_json" in text
    return Check(
        "CLI-seam (run_openclaw_followup.py --apply)",
        ok,
        "scripts/run_openclaw_followup.py",
    )


def _check_ui_wiring() -> Check:
    """The Viewser /api/prompt route must call the OpenClaw apply bridge."""
    runner = REPO_ROOT / "apps" / "viewser" / "lib" / "openclaw-runner.ts"
    route = REPO_ROOT / "apps" / "viewser" / "app" / "api" / "prompt" / "route.ts"
    problems: list[str] = []
    for path, needle, label in (
        (runner, "runOpenClawFollowupApply", "openclaw-runner.ts exporterar apply-bryggan"),
        (route, "runOpenClawFollowupApply", "route.ts anropar apply-bryggan"),
    ):
        if not path.exists():
            problems.append(f"{path.name} saknas")
            continue
        try:
            if needle not in path.read_text(encoding="utf-8"):
                problems.append(label + " (saknas)")
        except OSError as exc:
            problems.append(f"{path.name} läsfel: {exc}")
    return Check(
        "UI-wiring (/api/prompt -> apply bridge)",
        not problems,
        "; ".join(problems) or "wirad",
    )


def _check_decisions() -> list[Check]:
    """The deterministic decision must split an edit from a question correctly."""
    try:
        from scripts.run_openclaw_followup import decide_to_json
    except ImportError as exc:
        return [Check("Beslut (deterministiskt)", False, f"import-fel: {exc}")]

    checks: list[Check] = []

    edit = json.loads(decide_to_json("ändra färgen till rosa"))
    edit_ok = (
        edit.get("action") == "patch_plan_request"
        and edit.get("router", {}).get("editKind") == "visual_style"
    )
    checks.append(
        Check(
            "Beslut: 'ändra färgen till rosa' -> edit_instruction/visual_style",
            edit_ok,
            f"action={edit.get('action')} "
            f"editKind={edit.get('router', {}).get('editKind')}",
        )
    )

    question = json.loads(decide_to_json("vad tycker du om sidan?"))
    question_ok = (
        question.get("action") == "answer_only"
        and question.get("patchPlanRequest") is None
    )
    checks.append(
        Check(
            "Beslut: fråga -> answer_only (ingen build)",
            question_ok,
            f"action={question.get('action')}",
        )
    )

    section = json.loads(decide_to_json("lägg till en sektion om garantier"))
    section_ok = (
        section.get("action") == "patch_plan_request"
        and section.get("router", {}).get("editKind") == "section_add"
    )
    checks.append(
        Check(
            "Beslut: 'lägg till en sektion om garantier' -> edit_instruction/section_add",
            section_ok,
            f"action={section.get('action')} "
            f"editKind={section.get('router', {}).get('editKind')}",
        )
    )
    return checks


def _newest_site_id() -> str | None:
    """Best-effort: the siteId of the most recently modified run directory.

    Run dirs are named ``<timestamp>-<hash>-<siteId>``; timestamp and hash carry
    no internal hyphen, so the siteId is everything after the second hyphen.
    """
    runs = REPO_ROOT / "data" / "runs"
    if not runs.exists():
        return None
    run_dirs = sorted(
        (p for p in runs.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run_dir in run_dirs:
        parts = run_dir.name.split("-")
        if len(parts) >= 3:
            return "-".join(parts[2:])
    return None


def _check_apply(site_id: str) -> Check:
    """Run the real apply bridge (skip-build) and assert a version was minted."""
    try:
        from scripts.run_openclaw_followup import apply_followup_to_json

        payload = json.loads(
            apply_followup_to_json(
                "ändra färgen till rosa",
                site_id=site_id,
                do_build=False,
            )
        )
    except Exception as exc:  # broad on purpose: any failure is an honest FAIL
        return Check(f"Apply-bridge materialiserar version ('{site_id}')", False, f"fel: {exc}")

    bridge = payload.get("bridge") or {}
    chain = bridge.get("chain") or {}
    applied = bridge.get("applied") is True
    version = chain.get("version")
    previous = chain.get("previousVersion")
    bumped = (
        isinstance(version, int)
        and isinstance(previous, int)
        and version > previous
    )
    return Check(
        f"Apply-bridge materialiserar version ('{site_id}')",
        applied and bumped,
        f"status={bridge.get('status')} applied={applied} "
        f"v{previous}->v{version}",
    )


def run_checks(*, apply: bool, site_id: str | None) -> list[Check]:
    """Run all self-checks and return them in display order."""
    checks: list[Check] = [
        _check_core_import(),
        _check_cli_seam(),
        _check_ui_wiring(),
        *_check_decisions(),
    ]
    if apply:
        resolved = site_id or _newest_site_id()
        if not resolved:
            checks.append(
                Check(
                    "Apply-bridge",
                    False,
                    "ingen byggd sajt hittad - bygg en sajt först eller ange --site-id",
                )
            )
        else:
            checks.append(_check_apply(resolved))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "OpenClaw connection self-check. Proves OpenClaw Core V0 is wired "
            "into the product (import -> CLI seam -> UI route -> deterministic "
            "decision), optionally running the full apply chain on a site."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Also run the real KÖR-7 chain (skip-build) on a site and assert a "
            "follow-up materialises a new version. Writes one throwaway version."
        ),
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help="Site for --apply (default: the newest site with a run).",
    )
    args = parser.parse_args()

    checks = run_checks(apply=args.apply, site_id=args.site_id)

    print("OpenClaw connection self-check")
    print("=" * 64)
    for check in checks:
        lamp = "[ PASS ]" if check.ok else "[ FAIL ]"
        print(f"  {lamp}  {check.name}")
        if check.detail:
            print(f"            {check.detail}")
    print("=" * 64)

    passed = sum(1 for check in checks if check.ok)
    total = len(checks)
    all_ok = passed == total
    verdict = (
        "GRÖN — OpenClaw är inkopplad och svarar."
        if all_ok
        else "RÖD — minst en kontroll misslyckades (se raderna ovan)."
    )
    print(f"{passed}/{total} PASS — {verdict}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
