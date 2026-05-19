#!/usr/bin/env python3
"""Tree-printer för LLM-context och operatör-snabb-orientering.

Successor till operator-lokala tree_v2.py. Ligger nu under scripts/ så
alla agenter (Scout, Builder, Steward, Cloud Agents) kan kalla den via
``python scripts/tree_view.py [path]`` utan att operatören manuellt
behöver dela med sig av sin lokala variant.

Standardläge är bakåtkompatibelt mot tree_v2.py: samma IGNORE-set,
samma ASCII-layout, samma output till stdout. CLI-flaggor lägger till
LLM-vänliga format, depth-cap, storlek, file-filter, clipboard-copy
och stub:ade kataloger så node_modules/.next/.venv inte sprängs ut i
hundratals rader.

Designprinciper:

- Inga externa dependencies. Funkar i alla repo-miljöer som har Python
  3.12+ (matchande projektets ruff/mypy/pytest-baseline).
- Defensiv mot permission-denied (Windows-rättigheter på vissa katalog-
  juntar) — skippa tyst med en `[denied]`-stub istället för crash.
- Default-IGNORE matchar projektets `.gitignore`-mönster för bygg-
  artefakter, dev-cacher och utility-mappar.

CLI-exempel:

    python scripts/tree_view.py                          # cwd, default
    python scripts/tree_view.py apps/viewser             # specifik path
    python scripts/tree_view.py --max-depth 3            # bara 3 nivåer
    python scripts/tree_view.py --llm                    # LLM-vänlig markdown
    python scripts/tree_view.py --copy                   # till clipboard (PowerShell)
    python scripts/tree_view.py --with-size              # storlek per katalog
    python scripts/tree_view.py --ext .py,.tsx           # bara filer av viss typ
    python scripts/tree_view.py --no-stub                # expandera node_modules etc.
    python scripts/tree_view.py packages --llm --copy --max-depth 4
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
from pathlib import Path

# Default-IGNORE: matchar repo:ts .gitignore + vanliga utility-mappar
# som typiskt inte är intressanta för LLM-context. Operatören kan
# extenderar via --extra-ignore.
_DEFAULT_IGNORE: frozenset[str] = frozenset(
    {
        # Git + Python-cache
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        # Python-virtualenv
        ".venv",
        "venv",
        # JS/TS-bygg
        "node_modules",
        ".next",
        "out",
        "dist",
        "build",
        ".turbo",
        # Editor/OS
        ".idea",
        ".vscode",
        ".DS_Store",
        "Thumbs.db",
        # Cursor
        ".cursor",
        # Repo-specifikt
        ".generated",
        # Egg-info
        "*.egg-info",
    }
)

# Mappar som typiskt sväller tusen filer; stub:as som "[N items]"
# istället för full expansion när --no-stub inte är satt. node_modules
# är redan i _DEFAULT_IGNORE men listas här ifall operatören klönar
# IGNORE bort men ändå vill ha stubbar.
_STUB_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".next",
        ".venv",
        "venv",
        ".generated",
        "dist",
        "build",
        ".turbo",
    }
)


def _format_size(byte_count: int) -> str:
    """Returnera människoläsbar storlek (B/KiB/MiB/GiB)."""
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(byte_count)
    unit_index = 0
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _directory_size(path: Path) -> int:
    """Best-effort byte-count för en katalog. Skippar permission-denied."""
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        return 0
    return total


def _count_entries(path: Path) -> int:
    """Antal direkta children — för stub-text [N items]."""
    try:
        return sum(1 for _ in path.iterdir())
    except (OSError, PermissionError):
        return 0


def _should_ignore(name: str, ignore: frozenset[str]) -> bool:
    """Stöd både exakta namn och *.suffix-pattern (`*.egg-info`)."""
    if name in ignore:
        return True
    for pattern in ignore:
        if pattern.startswith("*."):
            if name.endswith(pattern[1:]):
                return True
    return False


def _matches_ext_filter(name: str, ext_filter: list[str] | None) -> bool:
    """Returnera True om filen ska visas givet --ext-filter."""
    if ext_filter is None:
        return True
    lower = name.lower()
    return any(lower.endswith(ext.lower()) for ext in ext_filter)


def _format_dir_label(
    name: str,
    *,
    is_stub: bool,
    entry_count: int,
    size_bytes: int | None,
) -> str:
    """Bygg den slutliga node-etiketten med ev. stub-info + storlek."""
    parts = [name + "/"]
    if is_stub:
        parts.append(f"[{entry_count} items]")
    if size_bytes is not None:
        parts.append(f"({_format_size(size_bytes)})")
    return " ".join(parts)


def _format_file_label(name: str, *, size_bytes: int | None) -> str:
    """Bygg fil-etikett med ev. storlek."""
    if size_bytes is None:
        return name
    return f"{name} ({_format_size(size_bytes)})"


def tree(
    path: Path,
    *,
    prefix: str = "",
    out: io.StringIO,
    depth: int = 0,
    max_depth: int | None,
    ignore: frozenset[str],
    stub_dirs: frozenset[str],
    no_stub: bool,
    with_size: bool,
    ext_filter: list[str] | None,
    llm: bool,
) -> None:
    """Rekursiv tree-walk. Skriver till `out` (StringIO för senare format)."""
    if max_depth is not None and depth >= max_depth:
        return

    try:
        raw_contents = list(path.iterdir())
    except (OSError, PermissionError):
        out.write(f"{prefix}└── [denied]\n")
        return

    # Filtrera ignored + applicera ext-filter på filer
    contents = [
        c
        for c in raw_contents
        if not _should_ignore(c.name, ignore)
        and (c.is_dir() or _matches_ext_filter(c.name, ext_filter))
    ]
    # Sortera: kataloger först (alfabetiskt), sedan filer (alfabetiskt)
    contents = sorted(
        contents, key=lambda p: (0 if p.is_dir() else 1, p.name.lower())
    )

    pointers = (
        ["├── "] * (len(contents) - 1) + ["└── "] if contents else []
    )

    for pointer, child in zip(pointers, contents, strict=True):
        if child.is_dir():
            is_stub = (not no_stub) and child.name in stub_dirs
            entry_count = _count_entries(child) if is_stub else 0
            size_bytes = _directory_size(child) if with_size else None
            label = _format_dir_label(
                child.name,
                is_stub=is_stub,
                entry_count=entry_count,
                size_bytes=size_bytes,
            )
            out.write(f"{prefix}{pointer}{label}\n")
            if not is_stub:
                extension = "│   " if pointer == "├── " else "    "
                tree(
                    child,
                    prefix=prefix + extension,
                    out=out,
                    depth=depth + 1,
                    max_depth=max_depth,
                    ignore=ignore,
                    stub_dirs=stub_dirs,
                    no_stub=no_stub,
                    with_size=with_size,
                    ext_filter=ext_filter,
                    llm=llm,
                )
        else:
            try:
                size_bytes = child.stat().st_size if with_size else None
            except (OSError, PermissionError):
                size_bytes = None
            label = _format_file_label(child.name, size_bytes=size_bytes)
            out.write(f"{prefix}{pointer}{label}\n")


def _wrap_llm_markdown(root_label: str, body: str) -> str:
    """LLM-vänligt format: markdown-codeblock + path-prefix-rensning."""
    lines = [
        f"# Tree of `{root_label}`",
        "",
        "```text",
        root_label + "/",
        body.rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(lines)


def _copy_to_clipboard(text: str) -> bool:
    """PowerShell `Set-Clipboard` på Windows; xclip/pbcopy på POSIX."""
    if shutil.which("powershell"):
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Set-Clipboard"],
                input=text,
                text=True,
                check=True,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            return False
    for cmd in (("pbcopy",), ("xclip", "-selection", "clipboard")):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(
                    list(cmd), input=text, text=True, check=True
                )
                return True
            except (subprocess.SubprocessError, OSError):
                continue
    return False


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tree-printer för LLM-context och operatör.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Sökväg att skanna (default: cwd).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Max-djup. Inget = obegränsat.",
    )
    parser.add_argument(
        "--with-size",
        action="store_true",
        help="Visa storlek per katalog och fil.",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Markdown-codeblock-format för LLM-context.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Kopiera output till clipboard (PowerShell/pbcopy/xclip).",
    )
    parser.add_argument(
        "--ext",
        type=str,
        default=None,
        help="Komma-separerad lista av filändelser att visa, t.ex. '.py,.tsx'.",
    )
    parser.add_argument(
        "--no-stub",
        action="store_true",
        help="Expandera annars stub:ade kataloger (node_modules, .venv osv).",
    )
    parser.add_argument(
        "--extra-ignore",
        type=str,
        default=None,
        help="Komma-separerade extra namn att ignorera utöver default-listan.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Skriv också till denna fil (default: bara stdout).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"path saknas: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"path är inte katalog: {root}", file=sys.stderr)
        return 2

    ignore = set(_DEFAULT_IGNORE)
    if args.extra_ignore:
        ignore.update(
            item.strip() for item in args.extra_ignore.split(",") if item.strip()
        )
    ignore_frozen = frozenset(ignore)

    ext_filter: list[str] | None = None
    if args.ext:
        ext_filter = [
            ("." + e.strip().lstrip(".")).lower()
            for e in args.ext.split(",")
            if e.strip()
        ]

    body_buffer = io.StringIO()
    tree(
        root,
        prefix="",
        out=body_buffer,
        depth=0,
        max_depth=args.max_depth,
        ignore=ignore_frozen,
        stub_dirs=_STUB_DIRS,
        no_stub=args.no_stub,
        with_size=args.with_size,
        ext_filter=ext_filter,
        llm=args.llm,
    )
    body = body_buffer.getvalue()

    root_label = root.name or str(root)
    if args.llm:
        formatted = _wrap_llm_markdown(root_label, body)
    else:
        formatted = f"{root_label}/\n{body}"

    sys.stdout.write(formatted)

    if args.output_file:
        try:
            Path(args.output_file).write_text(formatted, encoding="utf-8")
        except OSError as exc:
            print(f"kunde inte skriva output-fil: {exc}", file=sys.stderr)
            return 1

    if args.copy:
        if _copy_to_clipboard(formatted):
            print("[copied to clipboard]", file=sys.stderr)
        else:
            print(
                "[clipboard inte tillgänglig — använd --output-file istället]",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
