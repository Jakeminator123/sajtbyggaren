#!/usr/bin/env python3
"""Tree-kill orphan node-processer från Sajtbyggaren dev-servrar.

Användningsfall: efter en kraschad eller stängd Viewser-session kan
orphan-``next start``-processer leva kvar och hålla fil-lås på native
``.node``-binaries i ``node_modules/@next/swc-*-msvc/``. Det är samma
klass av problem som B157 round 3 fixade i Viewser, men för
processer som Viewser inte längre vet om (orphans från krasch).

Strategi:
- Lista alla ``node.exe``-processer via PowerShell + Win32_Process.
- Whitelist:a bara de vars ``CommandLine`` bär en Sajtbyggaren-scope-signal:
  antingen en path-token (``sajtbyggaren``, ``.generated\\`` eller
  dispatchern ``scripts\\dev.mjs``), ELLER ``next start``/``next dev`` på
  Viewsers preview-portintervall 4100-4199. Ett bart ``next start`` utan
  Viewser-port räknas INTE — det skulle annars träffa främmande Next.js-
  projekt som operatören kan ha igång (reviewer-fynd 2026-05-31).
- Tree-kill matchade PIDs med ``taskkill /T /F`` — samma teknik som
  ``apps/viewser/lib/local-preview-server.ts:killProcessTree`` använder.

Varför scopad whitelist: ``Stop-Process -Name node`` skulle döda ALLA
node.exe-processer på maskinen (VS Code language-servers, GitHub Desktop,
andra dev-servrar). En bred ``next``-match skulle döda andra Next-projekt.
Scopningen skyddar mot båda.

Användning:
- **Dubbelklicka** ``kill-dev-trees.bat`` i utforskaren (säkraste vägen).
- Eller direkt: ``python kill-dev-trees.py`` från PowerShell.
- Eller via venv: ``.\\.venv\\Scripts\\python.exe kill-dev-trees.py``.

Safe: ingen permanent state ändras, inga filer rörs. Säkert att köra
när som helst — om inga matchande processer finns gör scriptet inget.

Skapad i samband med B157 round 3-fixen 2026-05-28. Se
``B157-WINDOWS-PROCESS-TREE-FYND.md`` i repo-roten för full bakgrund.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Starka Sajtbyggaren-scope-signaler i CommandLine (case-insensitive). En
# process som bär NÅGON av dessa är repo-/output-scopad och säker att döda.
SAJT_PATH_TOKENS: tuple[str, ...] = (
    "sajtbyggaren",  # repo-roten + ../sajtbyggaren-output/.generated/
    r"scripts\dev.mjs",  # Viewser dev-dispatcher
    ".generated",  # genererade sajter (matchar både / och \ separator)
)

# ``next start``/``next dev`` ENSAMT är för brett — det matchar VILKET som
# helst Next.js-projekt på maskinen (operatören kan ha andra Next-appar
# igång). Vi kvalar bara en sådan process som Sajtbyggaren om den dessutom
# kör på Viewsers preview-portintervall (``PORT_BASE=4100``, ``PORT_RANGE=100``
# i ``apps/viewser/lib/local-preview-server.ts`` → 4100-4199). Reviewer-fynd
# 2026-05-31: utan portkravet kunde helpern tree-killa främmande Next-projekt.
NEXT_TOKENS: tuple[str, ...] = ("next start", "next dev")
PREVIEW_PORT_LO = 4100
PREVIEW_PORT_HI = 4199
# ``-p 4137`` / ``-p4137`` / ``--port=4137`` / ``--port 4137`` i en next-cmdline.
_PORT_FLAG_RE = re.compile(r"(?:-p|--port)[=\s]*(\d{2,5})")


def _has_preview_port(cmdline_lower: str) -> bool:
    """True om cmdline har en ``-p``/``--port`` i Viewsers preview-intervall."""
    return any(
        PREVIEW_PORT_LO <= int(match) <= PREVIEW_PORT_HI
        for match in _PORT_FLAG_RE.findall(cmdline_lower)
    )


def list_node_processes() -> list[dict]:
    """Lista alla node.exe-processer med PID + CommandLine.

    Använder PowerShell + ``Get-CimInstance Win32_Process``. Returnerar
    tom lista om inga node-processer kör eller om PowerShell saknas.
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                'Get-CimInstance Win32_Process -Filter "name='
                "'node.exe'\""
                " | Select-Object ProcessId, CommandLine"
                " | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"  ! Kunde inte lista node-processer: {exc}")
        return []

    if result.returncode != 0:
        print(f"  ! PowerShell fel: {result.stderr.strip()}")
        return []

    output = result.stdout.strip()
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        print(f"  ! Kunde inte parsa node-process-lista: {output[:200]}")
        return []

    if isinstance(data, dict):
        return [data]
    return data


def matches_sajtbyggaren(cmdline: str | None) -> bool:
    """Sant om ``cmdline`` är en Sajtbyggaren-scopad node-process.

    Två vägar att kvala (annars: matchar inte → dödas inte):
      1. En stark path-scope-signal (``SAJT_PATH_TOKENS``) — repo-roten,
         ``.generated\\`` eller dev-dispatchern. Räcker ensamt.
      2. ``next start``/``next dev`` PLUS en preview-port i 4100-4199.
         Ett bart ``next start`` utan Viewser-port är INTE nog — det skulle
         träffa främmande Next.js-projekt på maskinen.
    """
    if not cmdline:
        return False
    cmdline_lower = cmdline.lower()
    if any(token.lower() in cmdline_lower for token in SAJT_PATH_TOKENS):
        return True
    if any(token in cmdline_lower for token in NEXT_TOKENS):
        return _has_preview_port(cmdline_lower)
    return False


def tree_kill(pid: int) -> tuple[bool, str]:
    """Tree-kill ``pid`` + alla descendants med ``taskkill /T /F``.

    Returnerar ``(success, message)``. Räknar redan-död som success.
    """
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
    # Returncode 128 = process inte hittad (race — den dog precis innan).
    if result.returncode == 128:
        return True, "redan dead (race)"
    return False, f"taskkill exit {result.returncode}: {result.stderr.strip()[:80]}"


def main() -> int:
    print("Sajtbyggaren dev-tree killer")
    print("=" * 50)

    if sys.platform != "win32":
        print("  ! Detta script är Windows-only (använder taskkill /T /F).")
        print("    På POSIX (Linux/macOS) räcker normalt 'pkill -f next' eller")
        print("    'kill -- -<gpid>' eftersom process groups respekteras där.")
        return 1

    print("Letar efter Sajtbyggaren-relaterade node-processer...")
    processes = list_node_processes()

    if not processes:
        print("  -> Inga node.exe-processer aktiva. Inget att göra.")
        return 0

    targets = [p for p in processes if matches_sajtbyggaren(p.get("CommandLine"))]

    if not targets:
        print(
            f"  -> {len(processes)} node-processer aktiva men ingen matchar"
            " Sajtbyggaren."
        )
        print(
            "    Whitelisten skyddar mot att döda andra Node.js-verktyg"
            " (VS Code,"
        )
        print("    GitHub Desktop, andra dev-servrar etc.).")
        return 0

    print(f"Hittade {len(targets)} Sajtbyggaren-relaterade node-processer:")
    for p in targets:
        pid = p["ProcessId"]
        cmd = (p.get("CommandLine") or "").strip()
        if len(cmd) > 110:
            cmd = cmd[:107] + "..."
        print(f"  PID {pid:>6}: {cmd}")
    print()

    print("Tree-killar med taskkill /T /F...")
    success_count = 0
    for p in targets:
        pid = p["ProcessId"]
        success, message = tree_kill(int(pid))
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
