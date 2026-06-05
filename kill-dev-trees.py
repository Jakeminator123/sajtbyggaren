#!/usr/bin/env python3
"""Tree-kill orphan node-processer från Sajtbyggaren dev-servrar.

Användningsfall: efter en kraschad eller stängd Viewser-session kan
orphan-``next start``-processer leva kvar och hålla fil-lås på native
``.node``-binaries i ``node_modules/@next/swc-*-msvc/``. Det är samma
klass av problem som B157 round 3 fixade i Viewser, men för
processer som Viewser inte längre vet om (orphans från krasch).

Strategi:
- Lista alla ``node.exe``-processer via PowerShell + Win32_Process.
- Whitelist:a bara Sajtbyggaren-scopade processer:
  1. Path-token (``sajtbyggaren``, ``apps/viewser``, ``.generated``,
     ``scripts\\dev.mjs``) i egen cmdline ELLER i ett föräldraträd
     (Windows lämnar ofta cmdline tom på barnprocesser).
  2. ``next start``/``next dev`` på preview-port 4100-4199 (Viewser
     local-preview; portintervallet används bara av Sajtbyggaren).
  3. ``node.exe`` som lyssnar på preview-port 4100-4199 (även tom cmdline).
  4. ``node.exe`` som lyssnar på Viewser dev-port 3000-3001 **och** har
     path-scope i trädet — så vi inte dödar främmande Next på 3000.
- Tree-kill matchade PIDs med ``taskkill /T /F``.

Varför scopad whitelist: ``Stop-Process -Name node`` skulle döda ALLA
node.exe-processer på maskinen (VS Code language-servers, GitHub Desktop,
andra dev-servrar). En bred ``next``-match på port 3000 skulle döda andra
Next-projekt. Scopningen skyddar mot båda.

Användning:
- **Dubbelklicka** ``kill-dev-trees.bat`` i utforskaren (säkraste vägen).
- ``python kill-dev-trees.py`` — dödar matchade processer.
- ``python kill-dev-trees.py --dry-run`` — visa vad som skulle dödas.
- ``python kill-dev-trees.py --verbose`` — visa även icke-matchade node.

Skapad i samband med B157 round 3-fixen 2026-05-28 (B157 stängd).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Starka Sajtbyggaren-scope-signaler (case-insensitive). Matchas mot
# sammanslagen cmdline i process + föräldrar (scope_text).
SAJT_PATH_TOKENS: tuple[str, ...] = (
    "sajtbyggaren",  # repo + ../sajtbyggaren-output/.generated/
    r"apps\viewser",
    "apps/viewser",
    r"scripts\dev.mjs",  # Viewser dev-dispatcher
    ".generated",  # genererade sajter (matchar både / och \ separator)
)

NEXT_TOKENS: tuple[str, ...] = ("next start", "next dev")
PREVIEW_PORT_LO = 4100
PREVIEW_PORT_HI = 4199
VIEWSER_DEV_PORT_LO = 3000
VIEWSER_DEV_PORT_HI = 3001
_PORT_FLAG_RE = re.compile(r"(?:-p|--port)[=\s]*(\d{2,5})")
_MAX_ANCESTRY_DEPTH = 30


def _has_port_in_range(cmdline_lower: str, lo: int, hi: int) -> bool:
    """True om cmdline har ``-p``/``--port`` inom [lo, hi]."""
    return any(lo <= int(match) <= hi for match in _PORT_FLAG_RE.findall(cmdline_lower))


def _has_preview_port(cmdline_lower: str) -> bool:
    return _has_port_in_range(cmdline_lower, PREVIEW_PORT_LO, PREVIEW_PORT_HI)


def _has_viewser_dev_port(cmdline_lower: str) -> bool:
    return _has_port_in_range(cmdline_lower, VIEWSER_DEV_PORT_LO, VIEWSER_DEV_PORT_HI)


def _run_powershell_json(command: str, *, timeout: int = 15) -> list[dict] | None:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"  ! PowerShell misslyckades: {exc}")
        return None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"  ! PowerShell fel: {stderr}")
        return None

    output = result.stdout.strip()
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        print(f"  ! Kunde inte parsa JSON: {output[:200]}")
        return None

    if isinstance(data, dict):
        return [data]
    return data


def list_node_processes() -> list[dict]:
    """Lista node.exe med PID, cmdline, förälder och ExecutablePath."""
    rows = _run_powershell_json(
        'Get-CimInstance Win32_Process -Filter "name=\'node.exe\'"'
        " | Select-Object ProcessId, ParentProcessId, CommandLine, ExecutablePath"
        " | ConvertTo-Json -Compress"
    )
    return rows if rows is not None else []


def list_processes_by_pid() -> dict[int, dict]:
    """Alla processer indexerade på PID (för föräldragång)."""
    rows = _run_powershell_json(
        "Get-CimInstance Win32_Process"
        " | Select-Object ProcessId, ParentProcessId, Name, CommandLine"
        " | ConvertTo-Json -Compress",
        timeout=20,
    )
    if rows is None:
        return {}
    by_pid: dict[int, dict] = {}
    for row in rows:
        pid = int(row["ProcessId"])
        by_pid[pid] = row
    return by_pid


def list_port_listener_pids(lo: int, hi: int) -> set[int]:
    """PIDs som lyssnar på TCP-portar i [lo, hi] (Windows)."""
    rows = _run_powershell_json(
        f"Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue"
        f" | Where-Object {{ $_.LocalPort -ge {lo} -and $_.LocalPort -le {hi} }}"
        " | Select-Object LocalPort, OwningProcess"
        " | ConvertTo-Json -Compress",
        timeout=15,
    )
    if rows is None:
        return set()
    pids: set[int] = set()
    for row in rows:
        try:
            pids.add(int(row["OwningProcess"]))
        except (KeyError, TypeError, ValueError):
            continue
    return pids


def collect_scope_text(pid: int, by_pid: dict[int, dict]) -> str:
    """Sammanslagen cmdline längs föräldraträdet (barn → rot)."""
    parts: list[str] = []
    seen: set[int] = set()
    current = pid
    depth = 0
    while current and current not in seen and depth < _MAX_ANCESTRY_DEPTH:
        seen.add(current)
        proc = by_pid.get(current)
        if not proc:
            break
        cmdline = proc.get("CommandLine")
        if cmdline:
            parts.append(str(cmdline))
        parent = proc.get("ParentProcessId")
        try:
            current = int(parent) if parent not in (None, 0) else 0
        except (TypeError, ValueError):
            break
        depth += 1
    return " ".join(parts)


def _has_path_scope(scope_text_lower: str) -> bool:
    return any(token.lower() in scope_text_lower for token in SAJT_PATH_TOKENS)


def matches_sajtbyggaren(cmdline: str | None, *, scope_text: str | None = None) -> bool:
    """Sant om processen är Sajtbyggaren-scopad (cmdline-only API för tester).

    Produktion använder ``is_target_node_process`` som även tar port-lyssnare
    och föräldraträd i beaktande.
    """
    # Fall back to cmdline on an empty scope_text too: a failed/timed-out
    # ancestry query yields "" (not None), and an empty string carries no
    # match signal. ``is not None`` would let that empty string mask a
    # cmdline that does carry a Sajtbyggaren scope token.
    combined = scope_text if scope_text else (cmdline or "")
    combined_lower = combined.lower()
    cmdline_lower = (cmdline or "").lower()

    if _has_path_scope(combined_lower):
        return True

    next_in_scope = any(token in combined_lower for token in NEXT_TOKENS)
    if next_in_scope and _has_preview_port(combined_lower):
        return True

    if any(token in cmdline_lower for token in NEXT_TOKENS):
        if _has_preview_port(cmdline_lower):
            return True
        if _has_viewser_dev_port(cmdline_lower) and _has_path_scope(combined_lower):
            return True

    return False


def is_target_node_process(
    proc: dict,
    *,
    by_pid: dict[int, dict],
    preview_listener_pids: set[int],
    dev_listener_pids: set[int],
) -> bool:
    """Avgör om en node.exe ska tree-killas."""
    pid = int(proc["ProcessId"])
    cmdline = proc.get("CommandLine")
    scope_text = collect_scope_text(pid, by_pid)

    if matches_sajtbyggaren(cmdline, scope_text=scope_text):
        return True

    if pid in preview_listener_pids:
        return True

    if pid in dev_listener_pids and _has_path_scope(scope_text.lower()):
        return True

    return False


def tree_kill(pid: int) -> tuple[bool, str]:
    """Tree-kill ``pid`` + alla descendants med ``taskkill /T /F``."""
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout (taskkill hängde)"

    if result.returncode == 0:
        return True, "dead"
    if result.returncode == 128:
        return True, "redan dead (race)"
    return False, f"taskkill exit {result.returncode}: {result.stderr.strip()[:80]}"


def _truncate(text: str, limit: int = 110) -> str:
    text = text.strip()
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tree-kill Sajtbyggaren node-processer.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Visa matchade processer utan att döda dem.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Visa även icke-matchade node-processer (felsökning).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print("Sajtbyggaren dev-tree killer")
    print("=" * 50)

    if sys.platform != "win32":
        print("  ! Detta script är Windows-only (använder taskkill /T /F).")
        print("    På POSIX (Linux/macOS) räcker normalt 'pkill -f next' eller")
        print("    'kill -- -<gpid>' eftersom process groups respekteras där.")
        return 1

    if args.dry_run:
        print("LÄGE: dry-run (inga processer dödas)")
        print()

    print("Letar efter Sajtbyggaren-relaterade node-processer...")
    processes = list_node_processes()

    if not processes:
        print("  -> Inga node.exe-processer aktiva. Inget att göra.")
        return 0

    by_pid = list_processes_by_pid()
    preview_listener_pids = list_port_listener_pids(PREVIEW_PORT_LO, PREVIEW_PORT_HI)
    dev_listener_pids = list_port_listener_pids(VIEWSER_DEV_PORT_LO, VIEWSER_DEV_PORT_HI)

    targets: list[dict] = []
    non_targets: list[dict] = []
    for proc in processes:
        if is_target_node_process(
            proc,
            by_pid=by_pid,
            preview_listener_pids=preview_listener_pids,
            dev_listener_pids=dev_listener_pids,
        ):
            targets.append(proc)
        else:
            non_targets.append(proc)

    if args.verbose and non_targets:
        print(f"\n{len(non_targets)} node-processer matchade INTE (skyddade):")
        for p in non_targets[:12]:
            pid = p["ProcessId"]
            cmd = _truncate(p.get("CommandLine") or "(tom cmdline)")
            scope = _truncate(collect_scope_text(int(pid), by_pid))
            print(f"  PID {pid:>6}: {cmd}")
            if scope and scope != cmd:
                print(f"           scope: {scope}")
        if len(non_targets) > 12:
            print(f"  ... och {len(non_targets) - 12} till")

    if preview_listener_pids or dev_listener_pids:
        print(
            f"  Port-lyssnare: preview {sorted(preview_listener_pids) or '—'}"
            f", viewser dev {sorted(dev_listener_pids) or '—'}"
        )

    if not targets:
        print(
            f"\n  -> {len(processes)} node-processer aktiva men ingen matchar"
            " Sajtbyggaren."
        )
        print(
            "    Whitelisten skyddar VS Code, Cursor, GitHub Desktop m.fl."
        )
        print("    Tips: kör med --verbose för att se varför inget matchade.")
        return 0

    print(f"\nHittade {len(targets)} Sajtbyggaren-relaterade node-processer:")
    for p in targets:
        pid = p["ProcessId"]
        cmd = _truncate(p.get("CommandLine") or "(tom cmdline)")
        print(f"  PID {pid:>6}: {cmd}")
    print()

    if args.dry_run:
        print("Dry-run klar — inga processer dödades.")
        return 0

    print("Tree-killar med taskkill /T /F...")
    success_count = 0
    for p in targets:
        pid = int(p["ProcessId"])
        success, message = tree_kill(pid)
        marker = "  +" if success else "  -"
        print(f"{marker} PID {pid:>6}: {message}")
        if success:
            success_count += 1

    print()
    print(f"{success_count}/{len(targets)} processträd avslutade.")
    if success_count == len(targets):
        print("Du kan nu köra `npm run dev` igen utan WinError 5.")
    else:
        print("OBS: vissa processer kunde inte dödas. Kör Task Manager")
        print("för att inspektera kvarvarande node.exe-instanser.")
    return 0 if success_count == len(targets) else 2


if __name__ == "__main__":
    sys.exit(main())
