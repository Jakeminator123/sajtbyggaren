"""Drift checker for the platform version baseline (ADR 0037).

The baseline in ``governance/policies/platform-baseline.v1.json`` is the single
source of truth for runtime and dependency versions. This script asserts that
``apps/viewser/package.json`` and every ``data/starters/*/package.json`` (the
codegen template) conform to it.

Run from the repo root:

    python scripts/check_platform_baseline.py            # same as --check
    python scripts/check_platform_baseline.py --check    # exit code 1 on drift
    python scripts/check_platform_baseline.py --fix      # write engines/volta + align pins

``--check`` (the default, wired into the guard suite) fails deterministically
when an ``enforced`` pin drifts from the baseline. Targets the baseline marks
``pendingPropagation`` (engines/volta, the @types/node bump, the npm
``packageManager`` pin, and the pins that vary today) are reported but do not
fail ``--check`` - they are propagated by a reviewed ``--fix`` in step 4
(operator OK + christopher-ui coordination, see ADR 0037).

``--fix`` writes ``engines.node`` + ``volta.node`` and sets every baseline-listed
pin present in a ``package.json`` to the baseline version (the same mechanical
pattern as ``rules_sync.py``). It touches ``apps/viewser/package.json``
(Christopher's lane) + ``data/starters/*`` and must therefore only run after
operator OK.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "governance" / "policies" / "platform-baseline.v1.json"

# package.json-fält som checkern läser pins ur (i denna prioritetsordning vid
# dubbletter, även om npm inte tillåter samma paket i flera).
_DEP_FIELDS = ("dependencies", "devDependencies")

# pendingPropagation tokens that are package.json fields, not package pins.
_ENGINES_NODE_TOKEN = "engines.node"
_VOLTA_NODE_TOKEN = "volta.node"
_PACKAGE_MANAGER_TOKEN = "packageManager"
_FIELD_TOKENS = (_ENGINES_NODE_TOKEN, _VOLTA_NODE_TOKEN, _PACKAGE_MANAGER_TOKEN)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    return load_json(path)


def baseline_pins(baseline: dict) -> dict[str, str]:
    """Platta ut framework/ui/styling/tooling till {paketnamn: version}."""
    pins: dict[str, str] = {}
    for group in ("framework", "ui", "styling", "tooling"):
        for name, version in baseline.get(group, {}).items():
            pins[name] = version
    return pins


def policy_consistency_errors(baseline: dict) -> list[str]:
    """Säkerställ att enforced/pendingPropagation pekar på riktiga pins.

    Fångar policy-författarmissar: varje baslinje-pin måste vara klassad som
    enforced eller pendingPropagation, och varje enforced/pending paketnamn
    (utöver fält-tokens) måste vara en riktig baslinje-pin.
    """
    errors: list[str] = []
    pins = baseline_pins(baseline)
    enforcement = baseline.get("enforcement", {})
    enforced = set(enforcement.get("enforced", []))
    pending = set(enforcement.get("pendingPropagation", []))

    overlap = enforced & pending
    if overlap:
        errors.append(
            "enforcement: paket både i enforced och pendingPropagation: "
            + ", ".join(sorted(overlap))
        )

    classified = enforced | pending
    for name in sorted(pins):
        if name not in classified:
            errors.append(
                f"enforcement: baslinje-pin '{name}' saknar klassning "
                "(måste vara enforced eller pendingPropagation)."
            )

    for name in sorted(enforced | (pending - set(_FIELD_TOKENS))):
        if name not in pins:
            errors.append(
                f"enforcement: '{name}' är klassad men finns inte som "
                "baslinje-pin under framework/ui/styling/tooling."
            )
    return errors


def collect_deps(pkg: dict) -> dict[str, str]:
    """Slå ihop dependencies + devDependencies till en uppslagstabell."""
    deps: dict[str, str] = {}
    for field in _DEP_FIELDS:
        section = pkg.get(field)
        if isinstance(section, dict):
            for name, version in section.items():
                deps.setdefault(name, version)
    return deps


def check_package(pkg: dict, baseline: dict) -> tuple[list[str], list[str]]:
    """Returnera (hard_errors, pending_notes) för en package.json mot baslinjen.

    Hard error: en ``enforced`` pin förekommer i package.json men driftar från
    baslinjen, ELLER ett ``engines.node``/``volta.node`` som är enforced
    driftar. Pending note: en ``pendingPropagation`` pin saknas/driftar, eller
    ``engines.node``/``volta.node`` saknas (steg 4-mål).
    """
    pins = baseline_pins(baseline)
    enforcement = baseline.get("enforcement", {})
    enforced = set(enforcement.get("enforced", []))
    pending = set(enforcement.get("pendingPropagation", []))
    runtime = baseline.get("runtime", {})

    deps = collect_deps(pkg)
    errors: list[str] = []
    notes: list[str] = []

    for name, expected in sorted(pins.items()):
        if name not in deps:
            # present-only: en starter måste inte använda varje paket.
            continue
        actual = deps[name]
        if actual == expected:
            continue
        msg = f"{name}: {actual!r} != baslinjens {expected!r}"
        if name in enforced:
            errors.append(msg)
        else:
            notes.append(msg + " (pendingPropagation)")

    # engines.node
    engines = pkg.get("engines")
    engines_node = engines.get("node") if isinstance(engines, dict) else None
    expected_node = runtime.get("node")
    if engines_node is None:
        target = _engine_bucket(_ENGINES_NODE_TOKEN, enforced, pending)
        msg = f"engines.node saknas (baslinje {expected_node!r})"
        (errors if target == "enforced" else notes).append(
            msg if target == "enforced" else msg + " (pendingPropagation)"
        )
    elif engines_node != expected_node:
        target = _engine_bucket(_ENGINES_NODE_TOKEN, enforced, pending)
        msg = f"engines.node: {engines_node!r} != baslinjens {expected_node!r}"
        (errors if target == "enforced" else notes).append(
            msg if target == "enforced" else msg + " (pendingPropagation)"
        )

    # volta.node
    volta = pkg.get("volta")
    volta_node = volta.get("node") if isinstance(volta, dict) else None
    expected_volta = runtime.get("voltaNode")
    if volta_node is None:
        target = _engine_bucket(_VOLTA_NODE_TOKEN, enforced, pending)
        msg = f"volta.node saknas (baslinje {expected_volta!r})"
        (errors if target == "enforced" else notes).append(
            msg if target == "enforced" else msg + " (pendingPropagation)"
        )
    elif volta_node != expected_volta:
        target = _engine_bucket(_VOLTA_NODE_TOKEN, enforced, pending)
        msg = f"volta.node: {volta_node!r} != baslinjens {expected_volta!r}"
        (errors if target == "enforced" else notes).append(
            msg if target == "enforced" else msg + " (pendingPropagation)"
        )

    # packageManager (npm pin). runtime.npm declares the npm major (e.g. "11.x");
    # the field, when present, is corepack-style "npm@<version>". It is a
    # pendingPropagation field-token (not enforced today), so a missing or
    # major-mismatched pin is a step-4 note, never a hard error - the exact
    # version is set by corepack / a reviewed --fix, not derived from an "x" range.
    expected_npm = runtime.get("npm")
    if expected_npm:
        npm_major = str(expected_npm).split(".")[0]
        package_manager = pkg.get("packageManager")
        target = _engine_bucket(_PACKAGE_MANAGER_TOKEN, enforced, pending)
        pm_msg: str | None = None
        if package_manager is None:
            pm_msg = f"packageManager saknas (baslinje npm {expected_npm!r})"
        elif not str(package_manager).startswith(f"npm@{npm_major}"):
            pm_msg = f"packageManager: {package_manager!r} != npm@{expected_npm}"
        if pm_msg is not None:
            (errors if target == "enforced" else notes).append(
                pm_msg if target == "enforced" else pm_msg + " (pendingPropagation)"
            )

    return errors, notes


def _engine_bucket(token: str, enforced: set[str], pending: set[str]) -> str:
    """Avgör om en engines/volta-token är enforced eller pending."""
    if token in enforced:
        return "enforced"
    return "pending"


def fix_package(pkg: dict, baseline: dict) -> tuple[dict, list[str]]:
    """Returnera (ny_pkg, ändringar): align pins + injicera engines/volta.

    Muterar en kopia av ``pkg``: sätter varje baslinje-pin som förekommer i
    dependencies/devDependencies till baslinjens version, och skriver
    ``engines.node`` + ``volta.node`` från ``runtime``. Skapar aldrig en pin
    som inte redan fanns (behåller present-only-semantiken).
    """
    pins = baseline_pins(baseline)
    runtime = baseline.get("runtime", {})
    changes: list[str] = []
    out = json.loads(json.dumps(pkg))  # djupkopia

    for field in _DEP_FIELDS:
        section = out.get(field)
        if not isinstance(section, dict):
            continue
        for name, expected in pins.items():
            if name in section and section[name] != expected:
                changes.append(f"{field}.{name}: {section[name]!r} -> {expected!r}")
                section[name] = expected

    expected_node = runtime.get("node")
    engines = out.get("engines")
    if not isinstance(engines, dict):
        engines = {}
    if engines.get("node") != expected_node:
        changes.append(f"engines.node: {engines.get('node')!r} -> {expected_node!r}")
        engines["node"] = expected_node
    out["engines"] = engines

    expected_volta = runtime.get("voltaNode")
    volta = out.get("volta")
    if not isinstance(volta, dict):
        volta = {}
    if volta.get("node") != expected_volta:
        changes.append(f"volta.node: {volta.get('node')!r} -> {expected_volta!r}")
        volta["node"] = expected_volta
    out["volta"] = volta

    return out, changes


def resolve_targets(baseline: dict, repo_root: Path = REPO_ROOT) -> tuple[list[Path], list[str]]:
    """Lös upp targets.include till konkreta package.json-paths.

    Returnerar (paths, errors). Ett literal-mönster (utan glob-tecken) som
    saknas är ett fel (förväntat target borta). Ett glob-mönster som inte
    matchar något (t.ex. saas-base utan package.json) hoppas tyst över.
    """
    include = baseline.get("targets", {}).get("include", [])
    paths: list[Path] = []
    errors: list[str] = []
    seen: set[Path] = set()
    for pattern in include:
        is_glob = any(ch in pattern for ch in "*?[")
        if is_glob:
            matches = sorted(repo_root.glob(pattern))
            for match in matches:
                if match not in seen:
                    seen.add(match)
                    paths.append(match)
        else:
            literal = repo_root / pattern
            if not literal.exists():
                errors.append(f"target saknas: {pattern}")
                continue
            if literal not in seen:
                seen.add(literal)
                paths.append(literal)
    return paths, errors


def run_check(baseline: dict, repo_root: Path = REPO_ROOT) -> int:
    consistency = policy_consistency_errors(baseline)
    targets, target_errors = resolve_targets(baseline, repo_root)

    had_error = bool(consistency) or bool(target_errors)
    for err in consistency:
        print(f"  policy: {err}")
    for err in target_errors:
        print(f"  {err}")

    any_pending = False
    for path in targets:
        rel = path.relative_to(repo_root).as_posix()
        try:
            pkg = load_json(path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"  {rel}: kunde inte läsas som JSON: {exc}")
            had_error = True
            continue
        errors, notes = check_package(pkg, baseline)
        if errors:
            had_error = True
            print(f"DRIFT {rel}:")
            for err in errors:
                print(f"  - {err}")
        if notes:
            any_pending = True
            print(f"pending {rel} (steg 4 --fix):")
            for note in notes:
                print(f"  - {note}")

    if had_error:
        print(
            "\nResultat: DRIFT mot platform-baseline.v1.json. "
            "Rätta package.json eller kör 'python scripts/check_platform_baseline.py --fix' "
            "(steg 4, kräver operatörs-OK)."
        )
        return 1

    if any_pending:
        print(
            "\nResultat: OK (enforced pins konformar). "
            "pendingPropagation-mål kvarstår för ett granskat --fix (ADR 0037 steg 4)."
        )
    else:
        print("\nResultat: OK - alla targets konformar mot platform-baseline.v1.json.")
    return 0


def run_fix(baseline: dict, repo_root: Path = REPO_ROOT) -> int:
    targets, target_errors = resolve_targets(baseline, repo_root)
    for err in target_errors:
        print(f"  {err}")
    if target_errors:
        return 1

    wrote_any = False
    for path in targets:
        rel = path.relative_to(repo_root).as_posix()
        try:
            pkg = load_json(path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"  {rel}: kunde inte läsas som JSON: {exc}")
            return 1
        new_pkg, changes = fix_package(pkg, baseline)
        if not changes:
            print(f"OK {rel}: redan i synk.")
            continue
        path.write_text(
            json.dumps(new_pkg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        wrote_any = True
        print(f"FIX {rel}:")
        for change in changes:
            print(f"  - {change}")

    if not wrote_any:
        print("\nResultat: allt redan i synk.")
    else:
        print(
            "\nResultat: skrev om package.json mot baslinjen. "
            "Granska diffen och koordinera med christopher-ui innan push (ADR 0037 steg 4)."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Validera utan att skriva (default).")
    group.add_argument(
        "--fix",
        action="store_true",
        help="Skriv engines/volta + align pins (steg 4, kräver operatörs-OK).",
    )
    args = parser.parse_args(argv)

    if not BASELINE_PATH.exists():
        print(f"Hittar inte baslinjen på {BASELINE_PATH}", file=sys.stderr)
        return 2
    baseline = load_baseline()

    if args.fix:
        return run_fix(baseline)
    return run_check(baseline)


if __name__ == "__main__":
    sys.exit(main())
