#!/usr/bin/env python3
"""Synka Vercel-länk + env och publicera Python-byggmotorn (LLM-kedjan) till blob.

Tre saker, i rätt ordning:
  1. Säkerställer att repot är länkat till Vercel-projektet (``vercel link``).
     Hoppas över om ``.vercel/`` redan finns (länkning är engångs + interaktiv).
  2. Pullar miljövariablerna till ``apps/viewser/.env.vercel.local``
     (``vercel env pull``) — filen som buildern/previewen läser BLOB/KV-token ur.
  3. Paketerar + laddar upp build-kontexten (``scripts/``, ``packages/``,
     ``governance/``, ``data/starters/``, ``requirements.txt``, ``pyproject.toml``)
     till blob och skriver URL/SHA till KV — exakt det
     ``apps/viewser/scripts/upload-build-context-to-blob.mjs`` gör.

Blob- och KV-storen DELAS av ALLA Vercel-miljöer (production/preview/development
+ ev. custom environments), så EN uppladdning gäller för alla samtidigt. Det är
alltså det enda som behövs för att de senaste Python-/OpenClaw-skripten ska
användas i den hostade runtimen.

Kör utan argument för en meny, eller icke-interaktivt:
    python scripts/sync_vercel_build_context.py --full --yes
    python scripts/sync_vercel_build_context.py --upload
    python scripts/sync_vercel_build_context.py --pull [--all-envs]
    python scripts/sync_vercel_build_context.py --check
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

CHECK_SCRIPT = "apps/viewser/scripts/check-build-context.mjs"
UPLOAD_SCRIPT = "apps/viewser/scripts/upload-build-context-to-blob.mjs"
ENV_FILE = "apps/viewser/.env.vercel.local"


def find_repo_root() -> Path:
    """Hitta mappen som har både ``apps/viewser`` och ``.git``."""
    starts = [Path(__file__).resolve(), Path.cwd().resolve()]
    for start in starts:
        for candidate in [start, *start.parents]:
            if (candidate / "apps" / "viewser").is_dir() and (candidate / ".git").exists():
                return candidate
    sys.exit("FEL: hittar inte repo-roten (mappen med apps/viewser och .git).")


ROOT = find_repo_root()


def _exec_prefix(tool_path: str) -> list[str]:
    """Wrappa Windows-batchshims (vercel.cmd/npm.cmd) i ``cmd /c``.

    ``node.exe`` och unix-shims körs direkt; en ``.cmd``/``.bat`` på Windows kan
    inte startas av CreateProcess utan ``cmd /c``.
    """
    if os.name == "nt" and tool_path.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", tool_path]
    return [tool_path]


def _resolve(tool: str) -> str | None:
    return shutil.which(tool)


def _run(cmd: list[str]) -> int:
    """Kör ett kommando med ärvd stdio (live-output) och returnera exit-koden."""
    print(f"\n$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def _require(tool: str) -> str:
    resolved = _resolve(tool)
    if resolved is None:
        sys.exit(f"FEL: {tool} hittades inte i PATH.")
    return resolved


def is_linked() -> bool:
    vercel_dir = ROOT / ".vercel"
    return (vercel_dir / "project.json").exists() or (vercel_dir / "repo.json").exists()


def ensure_link(auto_yes: bool) -> None:
    if is_linked():
        print("Vercel-länk finns redan (.vercel/).")
        return
    print("Ingen .vercel-länk hittad.")
    if not auto_yes and not ask("Länka projektet nu (vercel link)?", default=True):
        return
    print("  Svara: Link to existing project? = yes | namn = sajtbyggaren-viewser")
    vercel = _require("vercel")
    _run(_exec_prefix(vercel) + ["link"])


def do_pull(all_envs: bool = False) -> None:
    vercel = _require("vercel")
    _run(_exec_prefix(vercel) + ["env", "pull", ENV_FILE, "--yes"])
    if all_envs:
        # Värdena är "All Environments" idag => identiska, men framtidssäkert.
        for env_name, out in (
            ("production", "apps/viewser/.env.vercel.production.local"),
            ("preview", "apps/viewser/.env.vercel.preview.local"),
        ):
            _run(_exec_prefix(vercel) + ["env", "pull", out, f"--environment={env_name}", "--yes"])


def do_check() -> int:
    node = _require("node")
    return _run(_exec_prefix(node) + [CHECK_SCRIPT])


def do_upload() -> None:
    node = _require("node")
    code = _run(_exec_prefix(node) + [UPLOAD_SCRIPT])
    if code != 0:
        sys.exit(f"FEL: uppladdningen misslyckades (exit {code}).")
    do_check()
    print(
        "\nKLART: nyaste Python-motorn (LLM-kedjan) är publicerad och gäller för "
        "ALLA Vercel-miljöer (delad blob + delad KV)."
    )


def ask(question: str, *, default: bool = False) -> bool:
    suffix = "[J/n]" if default else "[j/N]"
    try:
        answer = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in ("j", "ja", "y", "yes")


def menu() -> None:
    while True:
        print("\n=== Sajtbyggaren: Vercel-sync ===")
        print("  1) Allt: länka + pulla env + ladda upp nyaste tarballen")
        print("  2) Ladda upp den nyaste versionen av tarballen (Python/LLM-kedjan)")
        print("  3) Pulla env (vercel env pull)")
        print("  4) Visa status (build-context:check — ändrar inget)")
        print("  5) Avsluta")
        try:
            choice = input("Val [1-5]: ").strip()
        except EOFError:
            return
        if choice == "1":
            ensure_link(auto_yes=False)
            if ask("Pulla senaste miljövariabler?", default=True):
                do_pull()
            stale = do_check() != 0
            if ask("Vill du ladda upp den nyaste versionen av tarballen?", default=stale):
                do_upload()
        elif choice == "2":
            stale = do_check() != 0
            if ask("Vill du ladda upp den nyaste versionen av tarballen?", default=stale):
                do_upload()
        elif choice == "3":
            do_pull(all_envs=ask("Även production + preview?", default=False))
        elif choice == "4":
            do_check()
        elif choice in ("5", "q", ""):
            return
        else:
            print("Okänt val.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vercel-sync för Sajtbyggaren build-context.")
    parser.add_argument("--full", action="store_true", help="länk + env-pull + ladda upp")
    parser.add_argument("--upload", action="store_true", help="ladda upp nyaste tarballen")
    parser.add_argument("--pull", action="store_true", help="vercel env pull")
    parser.add_argument("--check", action="store_true", help="bara status (ändrar inget)")
    parser.add_argument("--all-envs", action="store_true", help="pulla även production + preview")
    parser.add_argument("-y", "--yes", action="store_true", help="svara ja på allt (icke-interaktivt)")
    args = parser.parse_args()

    print(f"Repo-rot: {ROOT}")
    if not any([args.full, args.upload, args.pull, args.check]):
        menu()
        return
    if args.full:
        ensure_link(auto_yes=args.yes)
        do_pull(all_envs=args.all_envs)
        do_upload()
        return
    if args.pull:
        do_pull(all_envs=args.all_envs)
    if args.check and not args.upload:
        do_check()
    if args.upload:
        do_upload()


if __name__ == "__main__":
    main()
