#!/usr/bin/env python3
"""
sync_and_publish.py — interaktiv hjälpare för Vercel-länk, env-pull och
publicering av Python-byggmotorn (LLM-kedjan) till Vercel Blob.

Kör utan argument för en meny. Eller icke-interaktivt:
    python sync_and_publish.py --full --yes    # länk + env-pull + ladda upp
    python sync_and_publish.py --upload --yes   # bara ladda upp nyaste tarballen
    python sync_and_publish.py --pull           # bara vercel env pull
    python sync_and_publish.py --check          # bara status (ändrar inget)

Blob + KV delas av ALLA Vercel-miljöer, så EN uppladdning gäller överallt.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_repo_root() -> Path:
    starts = []
    if "__file__" in globals():
        starts.append(Path(__file__).resolve())
    starts.append(Path.cwd().resolve())
    for start in starts:
        for d in [start, *start.parents]:
            if (d / "apps" / "viewser").is_dir() and (d / ".git").exists():
                return d
    sys.exit("FEL: hittar inte repo-roten (mappen med apps/viewser och .git).")


ROOT = find_repo_root()
VERCEL = shutil.which("vercel") or "vercel"
NODE = shutil.which("node") or "node"


def run(cmd: list[str], *, allow_fail: bool = False) -> int:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    code = subprocess.run(cmd, cwd=str(ROOT)).returncode
    if code != 0 and not allow_fail:
        sys.exit(f"\nFEL: kommandot misslyckades (exit {code}).")
    return code


def is_linked() -> bool:
    v = ROOT / ".vercel"
    return (v / "project.json").exists() or (v / "repo.json").exists()


def ensure_link(auto_yes: bool) -> None:
    if is_linked():
        print("Vercel-länk finns redan (.vercel/).")
        return
    print("Ingen .vercel-länk hittad.")
    if not auto_yes and not ask("Länka projektet nu (vercel link)?", default=True):
        return
    print("  Svara: Link to existing project? = yes | namn = sajtbyggaren-viewser")
    run([VERCEL, "link"])


def do_pull(all_envs: bool = False) -> None:
    run([VERCEL, "env", "pull", "apps/viewser/.env.vercel.local", "--yes"])
    if all_envs:
        # Värdena är "All Environments" idag => identiska, men framtidssäkert.
        run([VERCEL, "env", "pull", "apps/viewser/.env.vercel.production.local",
             "--environment=production", "--yes"])
        run([VERCEL, "env", "pull", "apps/viewser/.env.vercel.preview.local",
             "--environment=preview", "--yes"])


def do_check() -> int:
    return run([NODE, "apps/viewser/scripts/check-build-context.mjs"], allow_fail=True)


def do_upload() -> None:
    run([NODE, "apps/viewser/scripts/upload-build-context-to-blob.mjs"])
    do_check()
    print("\nKLART: nyaste Python-motorn (LLM-kedjan) är publicerad och gäller "
          "för ALLA Vercel-miljöer (delad blob + delad KV).")


def ask(question: str, *, default: bool = False) -> bool:
    suffix = "[J/n]" if default else "[j/N]"
    try:
        ans = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans in ("j", "ja", "y", "yes")


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="länk + env-pull + upload")
    ap.add_argument("--upload", action="store_true", help="ladda upp nyaste tarballen")
    ap.add_argument("--pull", action="store_true", help="vercel env pull")
    ap.add_argument("--check", action="store_true", help="bara status")
    ap.add_argument("--all-envs", action="store_true")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="svara ja på allt (icke-interaktivt)")
    args = ap.parse_args()

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
