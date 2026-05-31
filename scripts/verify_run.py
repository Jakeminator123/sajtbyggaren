#!/usr/bin/env python3
"""Verifierar en sajtbyggaren-run mot LLM contract propagation-förväntningar.

Stand-alone post-run-checker som läser artefakter direkt från disk så
operatören slipper StackBlitz/preview för att verifiera ett bygg-resultat.
Designad för adversarial- och baseline-mini-eval där vi vill jämföra
före/efter snabbt utan att starta någon server.

Skriptet är medvetet stand-alone (inga externa dependencies, ingen
import från `packages/` eller `apps/`) så vilken agent som helst kan
köra den i en lokal IDE eller i en cloud-grind utan setup-overhead.

Kontrakt: text-output är operatör-läsbar; `--json` ger maskin-läsbar
output med samma data så agenter kan tolka utfallet utan regex-parsning.

Användningsexempel (PowerShell, från repo-rot):

    # Default - alla checks, text-output mot senaste matchande run
    python scripts/verify_run.py --site-id skoldpaddssoppa-karlsson-099d5c

    # Senaste run överhuvudtaget (för "vad just byggdes?")
    python scripts/verify_run.py --latest

    # Specifik run-ID (exakt match i data/runs/)
    python scripts/verify_run.py --run-id 20260519T190606.540Z-...

    # Maskin-läsbar JSON-output för agent-konsumtion
    python scripts/verify_run.py --site-id <id> --json

    # Bara specifika checks (kommaseparerat)
    python scripts/verify_run.py --site-id <id> --checks b137,b138

Exit-koder:
    0 - alla aktiverade checks passerade
    1 - minst en check failade
    2 - argument- eller path-fel (run/site-id ej funnen, etc)

Se ``docs/tools/verify_run.md`` för agent-integrationsguide.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


# UI-direktiv-fraser som B137 ska blockera från att läcka till tagline.
# Speglar BLOCKED_TAGLINE_PHRASES-fixturen i Builders regression-tester
# (tests/test_discovery_resolver.py).
BLOCKED_TAGLINE_PHRASES: tuple[str, ...] = (
    "Hemsida om",
    "hemsida om",
    "2 sidor",
    "3 sidor",
    "4 sidor",
    "gröna färger",
    "gröna färg",
    "röda färger",
    "röd färg",
    "blå färger",
    "blå färg",
    "mörkt tema",
    "ljust tema",
    "Bygg en",
    "bygg en",
    "Skapa en",
    "skapa en",
)


# Generic B107-fallback-summaries. Om en service-summary matchar någon av
# dessa är det troligen ren fallback (briefen var sparse), inte
# operatörsdriven copy. Vi flaggar det som NIT i service-check.
B107_FALLBACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^Tydlig hjälp med .+ och enkel väg vidare\.?$", re.IGNORECASE),
    re.compile(r"^Clear help with .+ and a simple way forward\.?$", re.IGNORECASE),
)


# Default-set av checks. --checks låter operatören välja specifika.
ALL_CHECKS: tuple[str, ...] = (
    "brief",
    "b137",
    "b138",
    "intent-guard",
    "routes",
    "services",
    "contact",
    "field-sources",
    "page-intent",
)


# ---------------------------------------------------------------------------
# Path-resolvers
# ---------------------------------------------------------------------------


def find_run_dir(
    *,
    run_id: str | None,
    site_id: str | None,
    latest: bool = False,
) -> Path:
    """Hitta run-katalogen för en given site- eller run-ID."""
    runs_dir = REPO_ROOT / "data" / "runs"
    if not runs_dir.is_dir():
        raise FileNotFoundError(f"data/runs/ saknas: {runs_dir}")

    if run_id:
        target = runs_dir / run_id
        if not target.is_dir():
            raise FileNotFoundError(f"Run-katalog saknas: {target}")
        return target

    candidates = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )

    if latest:
        if not candidates:
            raise FileNotFoundError(f"Inga runs hittade under {runs_dir}")
        return candidates[0]

    if site_id:
        matches = [d for d in candidates if d.name.endswith(f"-{site_id}")]
        if not matches:
            raise FileNotFoundError(
                f"Ingen run hittad för siteId={site_id!r} under {runs_dir}"
            )
        return matches[0]

    raise ValueError("Ge antingen --site-id, --run-id eller --latest")


# Build id YYYYMMDDTHHMMSSZ with optional -NN suffix. Mirrors
# packages/generation/build/immutable_builds.py; inlined because verify_run.py
# is deliberately dependency-free (no import from packages/ or apps/).
_BUILD_ID_RE = re.compile(r"^\d{8}T\d{6}Z(?:-\d{2,})?$")


def _read_active_build_dir(site_dir: Path) -> Path | None:
    """Returnera aktiv immutable build-dir om current.json pekar på en giltig.

    Speglar packages/generation/build/immutable_builds.py:read_active_build_dir
    men inlinad eftersom verify_run.py medvetet är dependency-fri.
    """
    pointer = site_dir / "current.json"
    if not pointer.is_file():
        return None
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    build_id = payload.get("activeBuildId")
    if not isinstance(build_id, str) or not _BUILD_ID_RE.match(build_id):
        return None
    build_dir = site_dir / "builds" / build_id
    return build_dir if build_dir.is_dir() else None


def find_generated_dir(site_id: str) -> Path:
    """Generated-output-katalogen för en given site-ID.

    Speglar scripts/build_site.py-konventionen:
    prioritet env SAJTBYGGAREN_GENERATED_DIR > default (../sajtbyggaren-output/.generated/).

    B157 nivå 4 Stage A: sajter byggs numera till <site>/builds/<buildId>/ och
    aktiv build pekas ut av <site>/current.json. Returnera den aktiva build-
    katalogen när pekaren är giltig, annars fall tillbaka till det flata
    site-root-layoutet (sajter byggda före nivå 4).
    """
    env = os.environ.get("SAJTBYGGAREN_GENERATED_DIR")
    if env:
        site_dir = Path(env) / site_id
    else:
        site_dir = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated" / site_id
    active = _read_active_build_dir(site_dir)
    return active if active is not None else site_dir


def find_meta_sidecar(site_id: str) -> Path | None:
    """Returnera path till sidecar-meta om den finns."""
    sidecar = (
        REPO_ROOT / "data" / "prompt-inputs" / f"{site_id}.meta.json"
    )
    return sidecar if sidecar.is_file() else None


# ---------------------------------------------------------------------------
# JSON-läsare + extraktorer
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict[str, Any]:
    """Läs JSON-fil; returnera tom dict på fel."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  [!] parse-fel {path.name}: {exc}", file=sys.stderr)
        return {}


def extract_hero_tagline(page_tsx: Path) -> str | None:
    """Plocka första {"..."}-strängen i en <p>-tag.

    Bygger på samma renderer-mönster som B137-fixen producerar:
    ``<p ...>{"<tagline>"}</p>`` i Hero-blocket på första sidan.
    """
    if not page_tsx.is_file():
        return None
    try:
        text = page_tsx.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'<p[^>]*>\{"([^"]+)"\}</p>', text)
    return match.group(1) if match else None


def list_app_routes(app_dir: Path) -> list[str]:
    """Routes via filsystemet (för cross-check mot site-plan.json)."""
    if not app_dir.is_dir():
        return []
    routes: list[str] = []
    if (app_dir / "page.tsx").is_file():
        routes.append("/")
    for entry in app_dir.iterdir():
        if (
            entry.is_dir()
            and not entry.name.startswith("_")
            and (entry / "page.tsx").is_file()
        ):
            routes.append("/" + entry.name)
    return sorted(routes)


# ---------------------------------------------------------------------------
# Checks (varje return:ar dict med {status, label, details})
# ---------------------------------------------------------------------------

CheckResult = dict[str, Any]


def check_brief(site_brief: dict[str, Any]) -> CheckResult:
    """Info-only: skriv ut briefens fångade signaler. Returnerar alltid OK."""
    return {
        "status": "OK",
        "label": "Site Brief (briefModel-signaler)",
        "details": {
            "businessTypeGuess": site_brief.get("businessTypeGuess"),
            "pageCount": site_brief.get("pageCount"),
            "tone": site_brief.get("tone"),
            "servicesMentioned": site_brief.get("servicesMentioned"),
            "briefSource": site_brief.get("briefSource"),
            "modelUsed": site_brief.get("modelUsed"),
        },
    }


def check_b137_tagline(generated_dir: Path) -> CheckResult:
    """B137: läcker rå UI-direktiv-text in i Hero-tagline?"""
    page_tsx = generated_dir / "app" / "page.tsx"
    tagline = extract_hero_tagline(page_tsx)
    if tagline is None:
        return {
            "status": "UNKNOWN",
            "label": "B137 - Hero tagline",
            "details": {
                "tagline": None,
                "page_tsx": str(page_tsx),
                "note": "kunde inte extrahera tagline (page.tsx saknas eller annat mönster)",
            },
        }
    leaks = [
        phrase
        for phrase in BLOCKED_TAGLINE_PHRASES
        if phrase.lower() in tagline.lower()
    ]
    return {
        "status": "FAIL" if leaks else "OK",
        "label": "B137 - Hero tagline",
        "details": {
            "tagline": tagline,
            "blocked_leaks": leaks,
        },
    }


def check_b138_pagecount(
    site_brief: dict[str, Any], site_plan: dict[str, Any]
) -> CheckResult:
    """B138: respekterar planning brief.pageCount + emitterar pageCountWarning?"""
    route_plan = site_plan.get("routePlan") or []
    route_paths = [r.get("path") for r in route_plan]
    page_count_warning = site_plan.get("pageCountWarning")
    page_count = site_brief.get("pageCount")
    details: dict[str, Any] = {
        "route_paths": route_paths,
        "route_count": len(route_paths),
        "brief_page_count": page_count,
        "pageCountWarning": page_count_warning,
    }

    if not isinstance(page_count, int) or not (1 <= page_count <= 10):
        details["note"] = "brief.pageCount inte satt eller utanför 1-10; ingen trim förväntad"
        return {"status": "SKIP", "label": "B138 - pageCount-trim", "details": details}

    if len(route_paths) > page_count:
        details["note"] = (
            f"brief.pageCount={page_count} men {len(route_paths)} routes "
            "emitterade utan trim"
        )
        return {"status": "FAIL", "label": "B138 - pageCount-trim", "details": details}

    if len(route_paths) <= page_count and page_count_warning:
        return {"status": "OK", "label": "B138 - pageCount-trim", "details": details}

    details["note"] = (
        "routes är inom pageCount men ingen pageCountWarning - "
        "kan vara av-design eller missad warning-emission"
    )
    return {"status": "WARN", "label": "B138 - pageCount-trim", "details": details}


def check_intent_guard(
    site_brief: dict[str, Any], site_plan: dict[str, Any]
) -> CheckResult:
    """Intent Guard: warnings emitterade när wizard-kategori vs brief-mat krockar?"""
    warnings = site_plan.get("intentGuardWarnings") or []
    services = site_brief.get("servicesMentioned") or []
    services_text = " ".join(str(s).lower() for s in services if isinstance(s, str))
    food_terms = ("mat", "restaurang", "café", "bageri", "soppa", "kök", "cafe")
    food_hit = any(term in services_text for term in food_terms)
    details: dict[str, Any] = {
        "warning_count": len(warnings),
        "warnings": warnings,
        "services_food_hit": food_hit,
    }
    if food_hit and not warnings:
        details["note"] = (
            "services innehåller mat-term men inga intentGuardWarnings - "
            "möjligt false-negative om wizard-kategori inte var food-relaterad"
        )
        return {"status": "WARN", "label": "Intent Guard", "details": details}
    return {"status": "OK", "label": "Intent Guard", "details": details}


def check_routes_filesystem(
    site_id: str, site_plan: dict[str, Any], generated_dir: Path
) -> CheckResult:
    """Filsystemet (generated-output) ska matcha site-plan.routePlan."""
    route_plan = site_plan.get("routePlan") or []
    plan_paths = sorted(r.get("path") for r in route_plan)
    fs_paths = list_app_routes(generated_dir / "app") if generated_dir.is_dir() else []
    details: dict[str, Any] = {
        "site_plan_paths": plan_paths,
        "filesystem_paths": fs_paths,
        "generated_dir": str(generated_dir),
    }
    if not generated_dir.is_dir():
        details["note"] = "generated-dir saknas (ev. annan SAJTBYGGAREN_GENERATED_DIR)"
        return {"status": "UNKNOWN", "label": "Routes filsystem vs site-plan", "details": details}
    if set(plan_paths) != set(fs_paths):
        details["note"] = "filsystem och site-plan.json stämmer inte överens"
        return {"status": "FAIL", "label": "Routes filsystem vs site-plan", "details": details}
    return {"status": "OK", "label": "Routes filsystem vs site-plan", "details": details}


def check_services(generated_dir: Path) -> CheckResult:
    """B107: detektera generic fallback-summaries i service-grid."""
    page_tsx = generated_dir / "app" / "page.tsx"
    services_tsx = generated_dir / "app" / "tjanster" / "page.tsx"
    sources: list[Path] = [p for p in (page_tsx, services_tsx) if p.is_file()]
    if not sources:
        return {
            "status": "UNKNOWN",
            "label": "Services B107 fallback",
            "details": {"note": "ingen page.tsx eller /tjanster/page.tsx hittad"},
        }
    fallback_hits: list[str] = []
    seen_summaries: list[str] = []
    for src in sources:
        text = src.read_text(encoding="utf-8")
        # <p>{"<summary>"}</p> i service-cards
        for match in re.finditer(r'<p[^>]*>\{"([^"]+)"\}</p>', text):
            summary = match.group(1)
            if summary in seen_summaries:
                continue
            seen_summaries.append(summary)
            for pattern in B107_FALLBACK_PATTERNS:
                if pattern.match(summary):
                    fallback_hits.append(summary)
                    break
    details: dict[str, Any] = {
        "unique_summaries_seen": len(seen_summaries),
        "fallback_hits": fallback_hits,
    }
    if fallback_hits:
        details["note"] = "B107-fallback-mönster aktiv (briefen sparse på service-detaljer)"
        return {"status": "WARN", "label": "Services B107 fallback", "details": details}
    return {"status": "OK", "label": "Services B107 fallback", "details": details}


def check_contact_placeholders(meta_sidecar: Path | None) -> CheckResult:
    """Placeholder-contact-fält: vilka kontaktfält var inte operatörsangivna?"""
    if meta_sidecar is None:
        return {
            "status": "UNKNOWN",
            "label": "Placeholder contact fields",
            "details": {"note": "ingen sidecar-meta hittad"},
        }
    meta = load_json(meta_sidecar)
    placeholders = meta.get("placeholderContactFields") or []
    return {
        "status": "OK",
        "label": "Placeholder contact fields",
        "details": {
            "placeholder_fields": placeholders,
            "count": len(placeholders),
            "sidecar": str(meta_sidecar),
        },
    }


def check_field_sources(meta_sidecar: Path | None) -> CheckResult:
    """Visar fieldSources-mappning så agenter kan se vad som kom varifrån."""
    if meta_sidecar is None:
        return {
            "status": "UNKNOWN",
            "label": "Field sources (wizard/brief/derived/default)",
            "details": {"note": "ingen sidecar-meta hittad"},
        }
    meta = load_json(meta_sidecar)
    discovery_decision = meta.get("discoveryDecision") or {}
    field_sources = discovery_decision.get("fieldSources") or {}
    return {
        "status": "OK",
        "label": "Field sources (wizard/brief/derived/default)",
        "details": {
            "fieldSources": field_sources,
        },
    }


def check_page_intent(site_plan: dict[str, Any]) -> CheckResult:
    """B132: info-only - lista wizard-must-have-warnings om de finns."""
    warnings = site_plan.get("pageIntentWarnings") or []
    return {
        "status": "OK",
        "label": "B132 - pageIntentWarnings (info)",
        "details": {
            "warning_count": len(warnings),
            "warnings": warnings,
        },
    }


# ---------------------------------------------------------------------------
# Output-renderare
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "OK": "\x1b[32m",
    "FAIL": "\x1b[31m",
    "WARN": "\x1b[33m",
    "UNKNOWN": "\x1b[33m",
    "SKIP": "\x1b[90m",
}
COLOR_RESET = "\x1b[0m"


def _colorize(status: str) -> str:
    """Lägg på ANSI-färg om stdout är TTY; annars rå-text."""
    if not sys.stdout.isatty():
        return f"[{status}]"
    color = STATUS_COLORS.get(status, "")
    return f"{color}[{status}]{COLOR_RESET}"


def render_text(
    run_dir: Path,
    site_id: str,
    build_status: str | None,
    results: list[CheckResult],
) -> None:
    """Operatör-vänlig text-output."""
    print(f"Run     : {run_dir.name}")
    print(f"Site-ID : {site_id}")
    print(f"Build   : status={build_status!r}")
    print()
    for result in results:
        print(f"{_colorize(result['status'])} {result['label']}")
        details = result.get("details") or {}
        for key, value in details.items():
            if key == "note":
                continue
            if isinstance(value, list) and value and isinstance(value[0], dict):
                print(f"    {key}:")
                for item in value:
                    print(f"      - {item}")
            else:
                print(f"    {key}: {value}")
        if "note" in details:
            print(f"    note: {details['note']}")
        print()


def render_json(
    run_dir: Path,
    site_id: str,
    build_status: str | None,
    results: list[CheckResult],
) -> None:
    """Maskin-läsbar JSON för agent-konsumtion."""
    payload = {
        "run": run_dir.name,
        "siteId": site_id,
        "buildStatus": build_status,
        "results": results,
        "summary": {
            "ok": sum(1 for r in results if r["status"] == "OK"),
            "fail": sum(1 for r in results if r["status"] == "FAIL"),
            "warn": sum(1 for r in results if r["status"] == "WARN"),
            "unknown": sum(1 for r in results if r["status"] == "UNKNOWN"),
            "skip": sum(1 for r in results if r["status"] == "SKIP"),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifiera sajtbyggaren-run mot LLM contract propagation.",
        epilog="Se docs/tools/verify_run.md för agent-integrationsguide.",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--site-id", help="Site-ID (senaste matchande run).")
    selector.add_argument("--run-id", help="Exakt run-ID från data/runs/.")
    selector.add_argument(
        "--latest",
        action="store_true",
        help="Senaste run överhuvudtaget (oavsett siteId).",
    )
    parser.add_argument(
        "--checks",
        type=str,
        default=None,
        help=(
            "Kommaseparerad lista av checks att köra. Default: alla. "
            f"Tillgängliga: {','.join(ALL_CHECKS)}"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Maskin-läsbar JSON-output (för agent-konsumtion).",
    )
    args = parser.parse_args(argv)

    try:
        run_dir = find_run_dir(
            run_id=args.run_id, site_id=args.site_id, latest=args.latest
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"FEL: {exc}", file=sys.stderr)
        return 2

    site_brief = load_json(run_dir / "site-brief.json")
    site_plan = load_json(run_dir / "site-plan.json")
    build_result = load_json(run_dir / "build-result.json")
    site_id = (
        build_result.get("siteId")
        or args.site_id
        or run_dir.name.split("-", 2)[-1]
    )
    generated_dir = find_generated_dir(site_id)
    meta_sidecar = find_meta_sidecar(site_id)

    if args.checks:
        wanted = {c.strip() for c in args.checks.split(",") if c.strip()}
        invalid = wanted - set(ALL_CHECKS)
        if invalid:
            print(
                f"FEL: okända checks: {sorted(invalid)}. "
                f"Tillgängliga: {','.join(ALL_CHECKS)}",
                file=sys.stderr,
            )
            return 2
    else:
        wanted = set(ALL_CHECKS)

    results: list[CheckResult] = []
    if "brief" in wanted:
        results.append(check_brief(site_brief))
    if "b137" in wanted:
        results.append(check_b137_tagline(generated_dir))
    if "b138" in wanted:
        results.append(check_b138_pagecount(site_brief, site_plan))
    if "intent-guard" in wanted:
        results.append(check_intent_guard(site_brief, site_plan))
    if "routes" in wanted:
        results.append(check_routes_filesystem(site_id, site_plan, generated_dir))
    if "services" in wanted:
        results.append(check_services(generated_dir))
    if "contact" in wanted:
        results.append(check_contact_placeholders(meta_sidecar))
    if "field-sources" in wanted:
        results.append(check_field_sources(meta_sidecar))
    if "page-intent" in wanted:
        results.append(check_page_intent(site_plan))

    if args.json:
        render_json(run_dir, site_id, build_result.get("status"), results)
    else:
        render_text(run_dir, site_id, build_result.get("status"), results)

    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
