r"""Hitta kandidat-domänbegrepp i repot som inte finns i naming-dictionary.

Skriptet är medvetet konservativt: det rapporterar **kandidatord**, inte sanning.
Operatören avgör om en kandidat är ett riktigt domänbegrepp som måste registreras
eller bara vanlig prosa/programmeringsord.

Heuristiker (alla kombineras till en lista per fil):

1. Citerade termer i markdown med versal: `\`Site Brief\``, `**Generation Package**`.
2. PascalCase-symboler i kod (StructuredSiteBrief, ScaffoldDefinition).
3. Strängar med suffix `*.scaffold.json`, `*.dossier.json`, `*.policy.json`.
4. Nya mapp-/filnamn under `packages/`, `governance/`, `apps/` som inte finns i ownerPackage.

Skriptet ignorerar:

- vanliga TypeScript-/JS-/Python-keywords och stdlib-namn,
- React-, Next-, Vite-, Streamlit-namn,
- referensmaterial (`utlåtande/`, `struktur/`, `scaffolds_dossiers/`, `stackblitz/`),
- genererade kataloger (`node_modules/`, `dist/`, `build/`, `.next/`, `.venv/`, `data/`).

Körs från repo-roten:

    python scripts/check_term_coverage.py            # rapportera kandidater
    python scripts/check_term_coverage.py --strict   # exit-kod 1 om kandidater hittas

Skriptet är ett diagnosverktyg, inte en hård gate. Hård gate kommer först när
ordlistan är stabilare.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
NAMING = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"

INCLUDE_SUFFIXES = {".md", ".mdc", ".py", ".ts", ".tsx", ".js", ".jsx", ".json"}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    "out",
    ".turbo",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "data",
    "referens",
    ".streamlit",
}

# Vanliga ord som inte ska räknas som domänbegrepp.
COMMON_WORDS = {
    # Programmeringsspråk
    "True", "False", "None", "Boolean", "String", "Number", "Object", "Array",
    "Promise", "Function", "Map", "Set", "Date", "Error", "JSON", "Buffer",
    "Path", "List", "Dict", "Tuple", "Optional", "Any", "Union", "Type",
    "TypeError", "ValueError", "RuntimeError", "Exception", "Iterator",
    "ArgumentParser", "ImportError", "UnicodeDecodeError", "Input", "Output",
    "Boolean", "Iterable", "Sequence", "Mapping", "Callable",
    # Framework / lib
    "React", "Next", "NextJs", "NextJS", "Vite", "Tailwind", "TypeScript",
    "Python", "Streamlit", "FastAPI", "Pydantic", "Flask", "Django",
    "JsonSchema", "Draft202012Validator",
    # Web standards / native browser APIs
    "HTML", "CSS", "URL", "URI", "DOM", "API", "HTTP", "HTTPS", "JSON",
    "REST", "GraphQL", "WebSocket", "OAuth", "CORS", "TLS", "SSL",
    "SharedArrayBuffer", "SharedArrayBuffer is not defined",
    # Sajtbyggaren-meta-nyckelord (egennamn för repon)
    "Sajtbyggaren", "Sajtmaskin", "Jakeminator123", "Jakemiantor123",
    "Lovable", "GitHub", "Cursor", "Vercel", "StackBlitz",
    "WebContainer", "WebContainers", "Fly", "Stripe", "OpenAI", "Anthropic",
    # Generic word fragments som dyker upp i text
    "ADR", "PR", "CI", "ID", "UUID", "MD", "LLM", "JSON",
    "PascalCase", "Backup",
    # Generiska prosa-fraser
    "Positiva signaler", "Negativa signaler",
    "Fas 1 runtime", "Fas 2 runtime", "Fas 3 runtime",
    "Fas 1", "Fas 2", "Fas 3",
    # Språknamn
    "Engelska", "Svenska", "English", "Swedish",
    # Interna kod-symboler / rubriker som inte är domänbegrepp
    "CheckResult", "SECTIONS",
    "Required files", "Optional files",
    "Source", "Mirror", "Validate", "Spara",
    # ADR-referenser och prosa-rubriker
    "ADR 0001", "ADR 0002", "ADR 0003", "ADR 0004", "ADR 0005",
    "ADR 0006", "ADR 0007", "ADR 0008", "ADR 0009",
    "Mappstruktur", "Tre faser", "Tre lager", "Tre nya",
    # Versaler i prosa (svenska och engelska)
    "INTE", "ALDRIG", "ENBART", "EN", "ALL",
    # Pluraler/kompositer av redan registrerade termer
    "Dossiers", "Reference Templates",
    "Scaffold Selector", "Dossier Selector",
    "Selected Scaffold", "Variant",
    "Globalt", "Skickas",
    "Embedding Domains", "FollowUp",
    "Mechanical Fixes", "LLM Fixes",
    # Python stdlib + interna kod-symboler
    "KeyError", "TimeoutExpired", "VIEWS", "Principer",
    "BaseModel", "Field", "FileNotFoundError", "BriefResult",
}

# Suffix för fil-namnsbaserade domänbegrepp.
DOMAIN_FILE_SUFFIXES = (
    "scaffold.json",
    "dossier.json",
    "policy.json",
    "schema.json",
    "selection-profile.json",
    "quality-contract.json",
    "code-contract.json",
    "env-contract.json",
)


def load_naming() -> dict:
    if not NAMING.exists():
        print(f"naming-dictionary saknas på {NAMING}", file=sys.stderr)
        sys.exit(2)
    return json.loads(NAMING.read_text(encoding="utf-8"))


def known_terms(naming: dict) -> set[str]:
    out: set[str] = set()
    for term in naming.get("terms", []):
        out.add(term.get("id", ""))
        out.add(term.get("canonical", ""))
        for alias in term.get("aliasesAllowed", []) or []:
            out.add(alias)
    out.discard("")
    return out


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in INCLUDE_SUFFIXES:
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        files.append(path)
    return files


# Bara strängar med inledande versal som inte är vanliga ord.
PASCAL_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)\b")
QUOTED_PHRASE_MD_RE = re.compile(r"`([A-Z][A-Za-z0-9 ]{2,}?)`")
BOLD_PHRASE_MD_RE = re.compile(r"\*\*([A-Z][A-Za-z0-9 ]{2,}?)\*\*")


# Svenska och engelska småord som signalerar prosa snarare än domänterm.
PROSE_STOPWORDS_PATTERN = re.compile(
    r"\b(och|eller|att|med|för|av|som|till|från|när|innan|efter|"
    r"the|and|or|to|from|with|when|before|after|of|in|on|at)\b",
    flags=re.IGNORECASE,
)


def looks_like_prose(phrase: str) -> bool:
    """Fraser med småord eller > 4 tokens behandlas som prosa, inte domänterm."""
    if PROSE_STOPWORDS_PATTERN.search(phrase):
        return True
    if len(phrase.split()) > 4:
        return True
    return False


def find_candidates(text: str, file_suffix_already_known: set[str]) -> set[str]:
    out: set[str] = set()

    for match in PASCAL_RE.finditer(text):
        token = match.group(1)
        if token in COMMON_WORDS:
            continue
        out.add(token)

    for match in QUOTED_PHRASE_MD_RE.finditer(text):
        phrase = match.group(1).strip()
        if phrase in COMMON_WORDS:
            continue
        if looks_like_prose(phrase):
            continue
        out.add(phrase)

    for match in BOLD_PHRASE_MD_RE.finditer(text):
        phrase = match.group(1).strip()
        if phrase in COMMON_WORDS:
            continue
        if looks_like_prose(phrase):
            continue
        out.add(phrase)

    for suffix in DOMAIN_FILE_SUFFIXES:
        if suffix in text and suffix not in file_suffix_already_known:
            out.add(f"*.{suffix}")

    return out


def normalize_for_match(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Exit-kod 1 om kandidater hittas.")
    parser.add_argument("--limit", type=int, default=50, help="Max antal unika kandidater att visa.")
    args = parser.parse_args()

    naming = load_naming()
    terms = known_terms(naming)
    forbidden = {w for w in naming.get("globallyForbidden", []) if w}
    known_normalized = {normalize_for_match(t) for t in terms}

    # Suffix som hör till redan registrerade termer (Scaffold, Dossier, Policy ...).
    # När de bara finns som derivat av en kanonisk term är det inte ett okänt begrepp.
    suffix_known = set()
    for suffix in DOMAIN_FILE_SUFFIXES:
        stem = suffix.split(".")[0]
        if normalize_for_match(stem) in known_normalized:
            suffix_known.add(suffix)

    findings: dict[str, list[str]] = {}

    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # Use POSIX-style relative path so prefix-matching works on Windows too.
        rel = path.relative_to(REPO_ROOT).as_posix()

        # Hoppa över själva naming-dictionary, schemas och rules; de listar termer.
        if rel.startswith("governance/policies/") or rel.startswith("governance/schemas/") or rel.startswith("governance/rules/"):
            continue
        if rel.startswith(".cursor/rules/"):
            continue
        if rel.startswith("docs/agent-handbook.md") or rel.startswith("docs/PROJECT_BRIEF.md"):
            continue

        candidates = find_candidates(text, suffix_known)
        for cand in candidates:
            if cand in forbidden:
                continue
            if normalize_for_match(cand) in known_normalized:
                continue
            findings.setdefault(cand, []).append(rel)

    if not findings:
        print("OK: Inga okända kandidatbegrepp hittades.")
        return 0

    print(f"Hittade {len(findings)} kandidater (visar upp till {args.limit}):\n")
    for cand, files in sorted(findings.items())[: args.limit]:
        sample = ", ".join(sorted(set(files))[:3])
        more = "" if len(set(files)) <= 3 else f" (+{len(set(files)) - 3} fler)"
        print(f"  {cand}")
        print(f"      i: {sample}{more}")

    print(
        "\nÅtgärd: lägg till de som är riktiga domänbegrepp i "
        "governance/policies/naming-dictionary.v1.json och kör om."
    )

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
