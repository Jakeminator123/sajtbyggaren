#!/usr/bin/env python3
"""Run the deterministic golden path scorecard.

The default mode is offline and deterministic: it temporarily removes
``OPENAI_API_KEY`` while generating the four baseline Project Inputs, then
runs ``scripts.build_site.build`` with ``do_build=False``. That gives each
case real run artifacts and generated files without a real LLM call and
without ``npm install`` / ``npm run build``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SUMMARIES_DIR = REPO_ROOT / "data" / "evals" / "summaries" / "golden-path"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "data" / "evals" / "artifacts" / "golden-path"
# Backwards-compatible alias kept so older imports/tests/scripts that
# pointed at the combined ``data/evals/golden-path/`` directory keep
# working until they are migrated to the explicit summaries/artifacts
# pair below.
DEFAULT_EVALS_DIR = DEFAULT_ARTIFACTS_DIR
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
MAX_GOLDEN_PATH_EVALS_ENV = "SAJTBYGGAREN_MAX_GOLDEN_PATH_EVALS"
PASS_AVERAGE_THRESHOLD = 7.0
PASS_CASE_THRESHOLD = 6.5


@dataclass(frozen=True)
class Case:
    """One baseline prompt and its expected deterministic routing signals."""

    case_id: str
    label: str
    prompt: str
    expected_scaffold_id: str
    expected_variant_id: str
    expected_starter_id: str
    expected_business_types: tuple[str, ...]
    expected_routes: tuple[str, ...]
    industry_terms: tuple[str, ...]
    locality_terms: tuple[str, ...] = ()
    ideal_note: str = ""


BASELINE_CASES: tuple[Case, ...] = (
    Case(
        case_id="electrician-malmo",
        label="Elektriker Malmö",
        prompt="Skapa en hemsida för en elektriker i Malmö.",
        expected_scaffold_id="local-service-business",
        expected_variant_id="nordic-trust",
        expected_starter_id="marketing-base",
        expected_business_types=("electrician", "electrical-services", "service-provider"),
        expected_routes=("/", "/tjanster", "/om-oss", "/kontakt"),
        industry_terms=("elektriker", "elservice", "elarbeten", "felsökning"),
        locality_terms=("malmö", "malmo"),
        ideal_note="Bra fit för lokal service; främst kontakt- och copy-bevis behöver hålla.",
    ),
    Case(
        case_id="salon-goteborg",
        label="Frisörsalong Göteborg",
        prompt="Skapa en hemsida för en frisörsalong i Göteborg.",
        expected_scaffold_id="local-service-business",
        expected_variant_id="nordic-trust",
        expected_starter_id="marketing-base",
        expected_business_types=("hairdresser", "hair-salon", "service-provider"),
        expected_routes=("/", "/tjanster", "/om-oss", "/kontakt"),
        industry_terms=("frisör", "klippning", "styling", "färg"),
        locality_terms=("göteborg", "goteborg"),
        ideal_note="Saknar dedikerad salon-scaffold; kvaliteten avgörs av copy och bokningsnära CTA.",
    ),
    Case(
        case_id="naprapat-stockholm",
        label="Naprapatklinik Stockholm",
        prompt="Skapa en hemsida för en naprapatklinik i Stockholm.",
        expected_scaffold_id="clinic-healthcare",
        expected_variant_id="clinic-calm",
        expected_starter_id="marketing-base",
        expected_business_types=(
            "naprapat",
            "naprapath",
            "naprapath-clinic",
            "naprapat-clinic",
            "service-provider",
        ),
        # ``/om-oss`` + ``/kontakta-oss`` är clinic-healthcare-scaffolds
        # konventioner (samma för professional-services och agency-studio).
        # Pre-fix listades aspirational ``/team`` + standard ``/kontakt``,
        # vilket är route-namn för local-service-business — inte för Path B
        # native dispatcher-scaffolds. Se
        # packages/generation/orchestration/scaffolds/clinic-healthcare/routes.json
        # för canonical-listan; tests/test_builder_route_emission.py B45+B101
        # garanterar att CTA-länkar respekterar scaffolds contact_path.
        expected_routes=("/", "/behandlingar", "/om-oss", "/kontakta-oss"),
        industry_terms=("naprapat", "behandling", "rådgivning", "smärta"),
        locality_terms=("stockholm",),
        ideal_note=(
            "Det finns redan en clinic-healthcare-scaffold på disk; om local-service-business "
            "väljs är problemet selection/signal, inte retrieval."
        ),
    ),
    Case(
        case_id="ceramics-shop",
        label="Keramik e-handel",
        prompt="Skapa en hemsida för en liten e-handel som säljer keramik.",
        expected_scaffold_id="ecommerce-lite",
        expected_variant_id="clean-store",
        expected_starter_id="commerce-base",
        expected_business_types=("shop", "online-shop", "ecommerce", "e-commerce", "ecommerce-shop"),
        expected_routes=("/", "/produkter", "/om-oss", "/kontakt"),
        industry_terms=("keramik", "sortiment", "produkt", "beställning"),
        ideal_note="Commerce-scaffold finns aktiv; nästa kvalitetshål är produktcopy och köpnära kontaktväg.",
    ),
)

TRAIT_DEFINITIONS: dict[str, str] = {
    "clarity": "Förstår man direkt vad företaget gör?",
    "cta": "Finns tydlig nästa handling?",
    "trust": "Känns företaget legitimt och trovärdigt?",
    "industryFit": "Passar struktur och route-val branschen?",
    "copySpecificity": "Undviker generisk AI-copy och placeholder-känsla?",
    "mobileFirstFirstImpression": "Finns rimligt hero/section-flöde för första skärm?",
    "contactPath": "Fungerar kontaktvägen och är den branschanpassad?",
    "scaffoldFit": "Är vald scaffold, variant och starter rimliga?",
}

GENERIC_COPY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"tydlig hjälp med .+ och enkel väg vidare", re.IGNORECASE),
    re.compile(r"clear help with .+ and a simple way forward", re.IGNORECASE),
    re.compile(r"adress lämnas på förfrågan", re.IGNORECASE),
    re.compile(r"kontakt@example\.se", re.IGNORECASE),
)


def utc_now_iso() -> str:
    """Return a compact UTC timestamp for output metadata."""

    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def make_eval_id() -> str:
    """Return the default eval id used for JSON and Markdown output."""

    return "golden-path-" + datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def read_env_file_value(env_file: Path, name: str) -> str | None:
    """Return a single key from a simple ``.env`` file without loading secrets."""

    if not env_file.is_file():
        return None
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return None


def read_positive_int_setting(name: str, *, env_file: Path = REPO_ROOT / ".env") -> int | None:
    """Return a positive integer cap from process env or local ``.env``."""

    raw = os.environ.get(name)
    if raw is None:
        raw = read_env_file_value(env_file, name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def prune_golden_path_evals(
    artifacts_dir: Path,
    max_evals: int,
    *,
    protected_eval_ids: set[str] | None = None,
    dry_run: bool = False,
    summaries_dir: Path | None = None,
) -> list[str]:
    """Prune golden-path eval work dirs and matching JSON/Markdown summaries.

    ``artifacts_dir`` holds the per-eval work directories. ``summaries_dir``
    holds the operator-facing ``<evalId>.json`` and ``<evalId>.md`` reports
    and defaults to ``artifacts_dir`` so legacy callers that kept both in
    the same folder still get the same behavior.
    """

    if max_evals <= 0 or not artifacts_dir.is_dir():
        return []
    summaries_root = summaries_dir if summaries_dir is not None else artifacts_dir
    protected = protected_eval_ids or set()
    entries: list[tuple[float, Path]] = []
    protected_count = 0
    for child in artifacts_dir.iterdir():
        if not child.is_dir():
            continue
        if child.name in protected:
            protected_count += 1
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        entries.append((mtime, child))
    keep_slots = max(max_evals - protected_count, 0)
    entries.sort(key=lambda item: item[0], reverse=True)
    to_remove = [path for _, path in entries[keep_slots:]]
    removed: list[str] = []
    for path in to_remove:
        removed.append(path.name)
        if dry_run:
            continue
        for summary_path in (
            summaries_root / f"{path.name}.json",
            summaries_root / f"{path.name}.md",
        ):
            summary_path.unlink(missing_ok=True)
        shutil.rmtree(path)
    return removed


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning an empty dict for missing or malformed files."""

    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def extract_selected_dossiers(plan: dict[str, Any]) -> list[str]:
    """Return required dossier ids from a Site Plan shape."""

    selected = plan.get("selectedDossiers")
    if isinstance(selected, list):
        return [item for item in selected if isinstance(item, str)]
    if isinstance(selected, dict):
        required = selected.get("required", [])
        if isinstance(required, list):
            return [item for item in required if isinstance(item, str)]
    return []


def normalise_text(value: str) -> str:
    """Normalise text for cheap deterministic substring checks."""

    return " ".join(value.casefold().split())


def generated_text(run_dir: Path) -> str:
    """Return concatenated generated TSX files from a run snapshot."""

    app_dir = run_dir / "generated-files" / "app"
    if not app_dir.is_dir():
        return ""
    chunks: list[str] = []
    for path in sorted(app_dir.rglob("*.tsx")):
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def list_generated_routes(run_dir: Path) -> list[str]:
    """List routes from generated ``app/**/page.tsx`` files."""

    app_dir = run_dir / "generated-files" / "app"
    if not app_dir.is_dir():
        return []
    routes: list[str] = []
    for page_file in sorted(app_dir.rglob("page.tsx")):
        if page_file.parent == app_dir:
            routes.append("/")
            continue
        route = "/" + "/".join(page_file.parent.relative_to(app_dir).parts)
        routes.append(route)
    return routes


def route_paths(site_plan: dict[str, Any]) -> list[str]:
    """Return route paths from ``site-plan.json``."""

    routes = site_plan.get("routePlan", [])
    if not isinstance(routes, list):
        return []
    paths: list[str] = []
    for route in routes:
        if isinstance(route, dict) and isinstance(route.get("path"), str):
            paths.append(route["path"])
    return paths


def score_from_checks(points: float, evidence: list[str]) -> dict[str, Any]:
    """Create a bounded trait score payload."""

    score = max(0.0, min(10.0, round(points, 1)))
    return {
        "score": score,
        "maxScore": 10,
        "evidence": evidence,
    }


def any_term(text: str, terms: tuple[str, ...]) -> bool:
    """Return true when any term appears in normalised text."""

    haystack = normalise_text(text)
    return any(normalise_text(term) in haystack for term in terms)


def text_hits(text: str, terms: tuple[str, ...]) -> list[str]:
    """Return matching terms in deterministic order."""

    haystack = normalise_text(text)
    return [term for term in terms if normalise_text(term) in haystack]


def raw_prompt_leaks(text: str, prompt: str) -> list[str]:
    """Return raw prompt snippets that leaked into generated copy."""

    leaks: list[str] = []
    cleaned_prompt = prompt.strip()
    if cleaned_prompt and normalise_text(cleaned_prompt) in normalise_text(text):
        leaks.append(cleaned_prompt)
    blocked_phrases = (
        "skapa en hemsida",
        "hemsida för",
        "hemsida som",
    )
    haystack = normalise_text(text)
    leaks.extend(phrase for phrase in blocked_phrases if phrase in haystack)
    return leaks


def generic_copy_hits(text: str) -> list[str]:
    """Return generic fallback snippets detected in generated copy."""

    hits: list[str] = []
    for pattern in GENERIC_COPY_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def assess_route_sanity(expected: tuple[str, ...], plan_routes: list[str], fs_routes: list[str]) -> dict[str, Any]:
    """Compare planned, expected and generated routes."""

    missing_expected = sorted(set(expected) - set(plan_routes))
    missing_generated = sorted(set(plan_routes) - set(fs_routes))
    extra_generated = sorted(set(fs_routes) - set(plan_routes))
    status = "pass" if not missing_expected and not missing_generated else "fail"
    if extra_generated and status == "pass":
        status = "warn"
    return {
        "status": status,
        "expectedRoutes": list(expected),
        "plannedRoutes": plan_routes,
        "generatedRoutes": fs_routes,
        "missingExpectedRoutes": missing_expected,
        "missingGeneratedRoutes": missing_generated,
        "extraGeneratedRoutes": extra_generated,
    }


def assess_contact_cta(case: Case, plan_routes: list[str], fs_routes: list[str], text: str, build_result: dict[str, Any]) -> dict[str, Any]:
    """Assess the contact or product CTA path for a generated case."""

    has_contact_route = "/kontakt" in plan_routes and "/kontakt" in fs_routes
    has_contact_href = bool(re.search(r"href=\{?['\"]\/kontakt['\"]\}?", text))
    has_products_route = "/produkter" in plan_routes and "/produkter" in fs_routes
    has_products_href = bool(re.search(r"href=\{?['\"]\/produkter['\"]\}?", text))
    placeholder_fields = build_result.get("placeholderContactFields", [])
    if not isinstance(placeholder_fields, list):
        placeholder_fields = []
    ecommerce = case.expected_scaffold_id == "ecommerce-lite"
    status = "pass"
    notes: list[str] = []
    if has_contact_route:
        notes.append("/kontakt exists in plan and generated files")
    else:
        notes.append("/kontakt is missing from plan or generated files")
        status = "fail"
    if has_contact_href:
        notes.append("generated copy links to /kontakt")
    else:
        notes.append("no generated href to /kontakt detected")
        status = "warn" if status == "pass" else status
    if ecommerce:
        if has_products_route and has_products_href:
            notes.append("commerce case has /produkter route and product CTA")
        else:
            notes.append("commerce case lacks product route or product CTA")
            status = "warn" if status == "pass" else status
    if placeholder_fields:
        notes.append("placeholder contact fields: " + ", ".join(str(item) for item in placeholder_fields))
        status = "warn" if status == "pass" else status
    return {
        "status": status,
        "hasContactRoute": has_contact_route,
        "hasContactHref": has_contact_href,
        "hasProductsRoute": has_products_route,
        "hasProductsHref": has_products_href,
        "placeholderContactFields": placeholder_fields,
        "notes": notes,
    }


def score_traits(
    case: Case,
    *,
    project_input: dict[str, Any],
    site_brief: dict[str, Any],
    site_plan: dict[str, Any],
    build_result: dict[str, Any],
    route_sanity: dict[str, Any],
    contact_cta: dict[str, Any],
    text: str,
) -> dict[str, dict[str, Any]]:
    """Score all golden path traits from deterministic artifacts."""

    company = project_input.get("company") if isinstance(project_input.get("company"), dict) else {}
    business_type = str(company.get("businessType") or "")
    business_guess = str(site_brief.get("businessTypeGuess") or "")
    tone = site_brief.get("tone") or project_input.get("tone") or []
    plan_routes = route_paths(site_plan)
    generated_routes = route_sanity.get("generatedRoutes", [])
    placeholder_fields = contact_cta.get("placeholderContactFields", [])
    industry_hits = text_hits(text, case.industry_terms)
    locality_hits = text_hits(text, case.locality_terms)
    generic_hits = generic_copy_hits(text)
    prompt_leaks = raw_prompt_leaks(text, case.prompt)
    section_count = len(re.findall(r"<section\b", text))

    scores: dict[str, dict[str, Any]] = {}

    clarity_points = 4.0
    clarity_evidence: list[str] = []
    if project_input.get("language") == "sv":
        clarity_points += 1.0
        clarity_evidence.append("language=sv")
    if business_type in case.expected_business_types or business_guess in case.expected_business_types:
        clarity_points += 2.0
        clarity_evidence.append(f"business signal={business_type or business_guess}")
    if industry_hits:
        clarity_points += 1.5
        clarity_evidence.append("industry terms in generated copy: " + ", ".join(industry_hits[:3]))
    if locality_hits:
        clarity_points += 1.0
        clarity_evidence.append("locality terms in generated copy: " + ", ".join(locality_hits[:2]))
    if prompt_leaks:
        clarity_points -= 2.0
        clarity_evidence.append("raw prompt leak: " + ", ".join(prompt_leaks[:2]))
    scores["clarity"] = score_from_checks(clarity_points, clarity_evidence)

    cta_points = 4.0
    cta_evidence = list(contact_cta.get("notes", []))
    if contact_cta.get("hasContactRoute"):
        cta_points += 1.5
    if contact_cta.get("hasContactHref"):
        cta_points += 1.5
    if case.expected_scaffold_id == "ecommerce-lite" and contact_cta.get("hasProductsHref"):
        cta_points += 1.5
    if any_term(text, ("boka", "ring", "kontakta", "shoppa", "beställ", "offert")):
        cta_points += 1.0
        cta_evidence.append("CTA verbs detected")
    if route_sanity["status"] == "fail":
        cta_points -= 1.5
    scores["cta"] = score_from_checks(cta_points, cta_evidence)

    trust_points = 4.0
    trust_evidence: list[str] = []
    if "/om-oss" in plan_routes or "/team" in plan_routes:
        trust_points += 1.5
        trust_evidence.append("about/team route present")
    if contact_cta.get("hasContactRoute"):
        trust_points += 1.5
        trust_evidence.append("contact route present")
    if isinstance(tone, list) and any("trust" in str(item) or "förtroende" in str(item) for item in tone):
        trust_points += 1.0
        trust_evidence.append("trust-oriented tone propagated")
    if placeholder_fields:
        trust_points -= 1.0
        trust_evidence.append("placeholder contact fields reduce trust")
    if any_term(text, ("trygg", "erfaren", "lokal", "certifier", "legitimerad", "förtroende")):
        trust_points += 1.0
        trust_evidence.append("trust words detected")
    scores["trust"] = score_from_checks(trust_points, trust_evidence)

    fit_points = 3.0
    fit_evidence: list[str] = []
    selected_scaffold = site_plan.get("scaffoldId")
    if selected_scaffold == case.expected_scaffold_id:
        fit_points += 3.0
        fit_evidence.append(f"selectedScaffoldId matches expected {case.expected_scaffold_id}")
    else:
        fit_evidence.append(
            f"selectedScaffoldId={selected_scaffold}, expected={case.expected_scaffold_id}"
        )
    if (
        route_sanity["status"] in {"pass", "warn"}
        and not route_sanity["missingExpectedRoutes"]
        and not route_sanity["missingGeneratedRoutes"]
    ):
        fit_points += 2.0
        fit_evidence.append("expected routes are planned and generated")
    elif not route_sanity["missingGeneratedRoutes"]:
        fit_points += 0.75
        fit_evidence.append("generated routes match plan, but expected industry routes differ")
    if site_plan.get("starterId") == case.expected_starter_id:
        fit_points += 1.0
        fit_evidence.append("starter matches expected")
    if site_plan.get("variantId") == case.expected_variant_id:
        fit_points += 1.0
        fit_evidence.append("variant matches expected")
    scores["industryFit"] = score_from_checks(fit_points, fit_evidence)

    copy_points = 4.5
    copy_evidence: list[str] = []
    if industry_hits:
        copy_points += 1.5
        copy_evidence.append("industry-specific terms: " + ", ".join(industry_hits[:3]))
    if locality_hits:
        copy_points += 1.0
        copy_evidence.append("locality terms: " + ", ".join(locality_hits[:2]))
    if prompt_leaks:
        copy_points -= 2.0
        copy_evidence.append("raw prompt leak detected")
    if generic_hits:
        copy_points -= min(2.0, 0.75 * len(generic_hits))
        copy_evidence.append("generic/placeholder copy patterns: " + str(len(generic_hits)))
    if selected_scaffold != case.expected_scaffold_id:
        copy_points -= 0.75
        copy_evidence.append("selected scaffold limits industry-specific copy")
    scores["copySpecificity"] = score_from_checks(copy_points, copy_evidence)

    mobile_points = 5.0
    mobile_evidence = [f"section count in generated TSX={section_count}"]
    if "/" in generated_routes:
        mobile_points += 1.0
        mobile_evidence.append("home route generated")
    if section_count >= 4:
        mobile_points += 2.0
        mobile_evidence.append("home/sections give a first-screen flow")
    elif section_count >= 2:
        mobile_points += 1.0
    if len(generated_routes) >= 4:
        mobile_points += 1.0
        mobile_evidence.append("route set supports mobile nav")
    if "main" in text and "section" in text:
        mobile_points += 0.5
    scores["mobileFirstFirstImpression"] = score_from_checks(mobile_points, mobile_evidence)

    contact_points = 3.0
    contact_evidence = list(contact_cta.get("notes", []))
    if contact_cta.get("hasContactRoute"):
        contact_points += 2.0
    if contact_cta.get("hasContactHref"):
        contact_points += 1.5
    if any_term(text, ("telefon", "e-post", "öppettider", "adress", "boka", "kontakt")):
        contact_points += 1.0
        contact_evidence.append("contact detail words detected")
    if case.case_id in {"salon-goteborg", "naprapat-stockholm"} and any_term(text, ("boka", "behandling", "klippning")):
        contact_points += 1.0
        contact_evidence.append("booking/service-adjacent contact wording detected")
    if placeholder_fields:
        contact_points -= min(2.0, 0.5 * len(placeholder_fields))
    scores["contactPath"] = score_from_checks(contact_points, contact_evidence)

    scaffold_points = 3.0
    scaffold_evidence: list[str] = []
    if selected_scaffold == case.expected_scaffold_id:
        scaffold_points += 3.0
        scaffold_evidence.append("scaffold matches expected")
    else:
        scaffold_evidence.append(f"scaffold mismatch: {selected_scaffold} vs {case.expected_scaffold_id}")
    if site_plan.get("variantId") == case.expected_variant_id:
        scaffold_points += 1.5
        scaffold_evidence.append("variant matches expected")
    else:
        scaffold_evidence.append(
            f"variant mismatch: {site_plan.get('variantId')} vs {case.expected_variant_id}"
        )
    if site_plan.get("starterId") == case.expected_starter_id:
        scaffold_points += 1.5
        scaffold_evidence.append("starter matches expected")
    else:
        scaffold_evidence.append(
            f"starter mismatch: {site_plan.get('starterId')} vs {case.expected_starter_id}"
        )
    scores["scaffoldFit"] = score_from_checks(scaffold_points, scaffold_evidence)

    return scores


def total_score(trait_scores: dict[str, dict[str, Any]]) -> float:
    """Return an equal-weight score across all traits."""

    if not trait_scores:
        return 0.0
    return round(
        sum(float(score["score"]) for score in trait_scores.values()) / len(trait_scores),
        2,
    )


@contextlib.contextmanager
def deterministic_llm_env(enabled: bool) -> Iterator[None]:
    """Disable LLM access while default deterministic mode is active."""

    if not enabled:
        yield
        return
    previous = os.environ.pop(OPENAI_API_KEY_ENV, None)
    try:
        yield
    finally:
        if previous is not None:
            os.environ[OPENAI_API_KEY_ENV] = previous


def run_case(case: Case, *, work_dir: Path, mode: str) -> dict[str, Any]:
    """Generate, build and score one golden path case."""

    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate

    prompt_inputs_dir = work_dir / "prompt-inputs"
    runs_dir = work_dir / "runs"
    generated_dir = work_dir / "generated"
    for directory in (prompt_inputs_dir, runs_dir, generated_dir):
        directory.mkdir(parents=True, exist_ok=True)

    deterministic = mode == "deterministic"
    started = time.monotonic()
    with deterministic_llm_env(deterministic):
        project_input, meta, project_input_path, _meta_path = generate(
            case.prompt,
            output_dir=prompt_inputs_dir,
            site_id=case.case_id,
        )

        _target, run_dir = build(
            project_input_path,
            do_build=False,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
            auto_prune=False,
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)

    site_brief = read_json(run_dir / "site-brief.json")
    site_plan = read_json(run_dir / "site-plan.json")
    build_result = read_json(run_dir / "build-result.json")
    quality_result = read_json(run_dir / "quality-result.json")
    text = generated_text(run_dir)
    plan_routes = route_paths(site_plan)
    fs_routes = list_generated_routes(run_dir)
    route_sanity = assess_route_sanity(case.expected_routes, plan_routes, fs_routes)
    contact_cta = assess_contact_cta(case, plan_routes, fs_routes, text, build_result)
    trait_scores = score_traits(
        case,
        project_input=project_input,
        site_brief=site_brief,
        site_plan=site_plan,
        build_result=build_result,
        route_sanity=route_sanity,
        contact_cta=contact_cta,
        text=text,
    )
    score = total_score(trait_scores)
    passed = score >= PASS_CASE_THRESHOLD
    signal_summary = {
        "language": project_input.get("language") or site_brief.get("language"),
        "businessType": (project_input.get("company") or {}).get("businessType")
        if isinstance(project_input.get("company"), dict)
        else None,
        "businessTypeGuess": site_brief.get("businessTypeGuess"),
        "tone": site_brief.get("tone") or project_input.get("tone"),
        "pageCount": site_brief.get("pageCount"),
        "brand.primaryColorHex": (project_input.get("brand") or {}).get("primaryColorHex")
        if isinstance(project_input.get("brand"), dict)
        else None,
        "selectedScaffoldId": site_plan.get("scaffoldId"),
        "selectedVariantId": site_plan.get("variantId"),
        "expectedStarterId": case.expected_starter_id,
        "selectedStarterId": site_plan.get("starterId"),
    }
    selection_problem = (
        "selection"
        if site_plan.get("scaffoldId") != case.expected_scaffold_id
        else "not-selection"
    )
    case_payload = {
        "caseId": case.case_id,
        "label": case.label,
        "prompt": case.prompt,
        "mode": mode,
        "runId": run_dir.name,
        "runDir": str(run_dir),
        "projectInputPath": str(project_input_path),
        "elapsedMs": elapsed_ms,
        "passed": passed,
        "passThreshold": PASS_CASE_THRESHOLD,
        "totalScore": score,
        "traitScores": trait_scores,
        "traitDefinitions": TRAIT_DEFINITIONS,
        "routeSanity": route_sanity,
        "contactCtaSanity": contact_cta,
        "scaffoldSelection": {
            "selectedScaffoldId": site_plan.get("scaffoldId"),
            "expectedScaffoldId": case.expected_scaffold_id,
            "selectedVariantId": site_plan.get("variantId"),
            "expectedVariantId": case.expected_variant_id,
            "selectedStarterId": site_plan.get("starterId"),
            "expectedStarterId": case.expected_starter_id,
            "selectedDossiers": extract_selected_dossiers(site_plan),
            "idealNote": case.ideal_note,
        },
        "signalPropagation": signal_summary,
        "qualityStatus": quality_result.get("status"),
        "buildStatus": build_result.get("status"),
        "briefSource": site_brief.get("briefSource"),
        "planSource": site_plan.get("planSource"),
        "dominantProblem": classify_case_problem(
            trait_scores,
            route_sanity=route_sanity,
            contact_cta=contact_cta,
            selection_problem=selection_problem,
        ),
    }
    return case_payload


def classify_case_problem(
    trait_scores: dict[str, dict[str, Any]],
    *,
    route_sanity: dict[str, Any],
    contact_cta: dict[str, Any],
    selection_problem: str,
) -> str:
    """Return the most useful coarse problem label for the operator."""

    if selection_problem == "selection":
        return "selection"
    if route_sanity["status"] == "fail":
        return "routes"
    if contact_cta["status"] in {"fail", "warn"} and trait_scores["contactPath"]["score"] < 7:
        return "contact"
    weakest = min(trait_scores.items(), key=lambda item: float(item[1]["score"]))[0]
    if weakest in {"copySpecificity", "clarity"}:
        return "copy"
    if weakest == "mobileFirstFirstImpression":
        return "render"
    if weakest == "industryFit":
        return "signal-propagation"
    return "preview"


def compute_gate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the explicit embeddings readiness gate from score thresholds."""

    total = round(sum(float(case["totalScore"]) for case in cases) / len(cases), 2) if cases else 0.0
    below_case_threshold = [
        case["caseId"]
        for case in cases
        if float(case["totalScore"]) < PASS_CASE_THRESHOLD
    ]
    reasons: list[str] = []
    if total < PASS_AVERAGE_THRESHOLD:
        reasons.append(
            f"average score {total} is below {PASS_AVERAGE_THRESHOLD}"
        )
    if below_case_threshold:
        reasons.append(
            "cases below "
            + str(PASS_CASE_THRESHOLD)
            + ": "
            + ", ".join(below_case_threshold)
        )
    if not reasons:
        reasons.append("four baseline cases meet ADR 0026 score thresholds")
    status = "go" if total >= PASS_AVERAGE_THRESHOLD and not below_case_threshold else "no-go"
    return {
        "embeddingsReadiness": status,
        "nextGate": status,
        "averageScore": total,
        "averagePassThreshold": PASS_AVERAGE_THRESHOLD,
        "casePassThreshold": PASS_CASE_THRESHOLD,
        "casesBelowThreshold": below_case_threshold,
        "reasons": reasons,
    }


def inventory_repo() -> dict[str, Any]:
    """Return read-only scaffold, starter and dossier inventory."""

    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER

    scaffolds_dir = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
    starters_dir = REPO_ROOT / "data" / "starters"
    dossiers_dir = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
    on_disk_scaffolds = sorted(
        path.parent.name
        for path in scaffolds_dir.glob("*/scaffold.json")
        if path.is_file()
    )
    on_disk_starters = sorted(
        path.parent.name
        for path in starters_dir.glob("*/package.json")
        if path.is_file()
    )
    active_scaffolds = sorted(
        scaffold_id
        for scaffold_id in on_disk_scaffolds
        if scaffold_id in SCAFFOLD_TO_STARTER
        and SCAFFOLD_TO_STARTER[scaffold_id] in on_disk_starters
    )
    mapped_starters = sorted(set(SCAFFOLD_TO_STARTER.values()))
    dossier_ids: list[str] = []
    for manifest in dossiers_dir.glob("**/manifest.json"):
        data = read_json(manifest)
        dossier_id = data.get("id")
        if isinstance(dossier_id, str):
            dossier_ids.append(dossier_id)
    return {
        "scaffoldsOnDisk": on_disk_scaffolds,
        "runtimeActiveScaffolds": active_scaffolds,
        "deadOnDiskOnlyScaffolds": sorted(set(on_disk_scaffolds) - set(active_scaffolds)),
        "startersOnDisk": on_disk_starters,
        "runtimeMappedStarters": mapped_starters,
        "deadOnDiskOnlyStarters": sorted(set(on_disk_starters) - set(mapped_starters)),
        "dossiersOnDisk": sorted(dossier_ids),
    }


def summarise_problem_mix(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Count dominant problem labels and return the strongest one."""

    counts: dict[str, int] = {}
    for case in cases:
        label = str(case.get("dominantProblem") or "unknown")
        counts[label] = counts.get(label, 0) + 1
    dominant = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if counts else "unknown"
    return {
        "dominantProblem": dominant,
        "counts": counts,
    }


def write_case_files(work_dir: Path, cases: list[dict[str, Any]]) -> None:
    """Write one JSON file per case inside the eval work directory."""

    case_dir = work_dir / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        path = case_dir / f"{case['caseId']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_summary(eval_id: str, mode: str, work_dir: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the machine-readable summary payload."""

    gate = compute_gate(cases)
    problem_mix = summarise_problem_mix(cases)
    return {
        "schemaVersion": 1,
        "evalId": eval_id,
        "createdAt": utc_now_iso(),
        "mode": mode,
        "deterministicOffline": mode == "deterministic",
        "llmKeyRequired": mode != "deterministic",
        "openaiKeyPresentAtStart": bool(os.environ.get(OPENAI_API_KEY_ENV, "").strip()),
        "workDir": str(work_dir),
        "thresholds": {
            "averageScoreGo": PASS_AVERAGE_THRESHOLD,
            "minimumCaseScoreGo": PASS_CASE_THRESHOLD,
        },
        "baselinePrompts": [
            {"caseId": case.case_id, "prompt": case.prompt}
            for case in BASELINE_CASES
        ],
        "totalScore": gate["averageScore"],
        "caseCount": len(cases),
        "embeddingsGate": gate,
        "embeddingsReadiness": gate["embeddingsReadiness"],
        "nextGate": gate["nextGate"],
        "problemMix": problem_mix,
        "inventory": inventory_repo(),
        "cases": cases,
    }


def markdown_report(summary: dict[str, Any]) -> str:
    """Render a Swedish operator-facing Markdown report."""

    lines: list[str] = [
        "# Golden path scorecard",
        "",
        f"- Eval-id: `{summary['evalId']}`",
        f"- Läge: `{summary['mode']}`",
        f"- Offline default: `{summary['deterministicOffline']}`",
        f"- Total score: `{summary['totalScore']}` / 10",
        f"- Embeddings gate: `{summary['embeddingsReadiness']}`",
        f"- Dominerande problemtyp: `{summary['problemMix']['dominantProblem']}`",
        "",
        "## Baseline-prompter",
        "",
    ]
    for item in summary["baselinePrompts"]:
        lines.append(f"- `{item['caseId']}`: {item['prompt']}")
    lines.extend(
        [
            "",
            "## Scorecard",
            "",
            "| Case | Total | Pass | Dominant problem | Scaffold | Variant | Starter |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for case in summary["cases"]:
        selection = case["scaffoldSelection"]
        lines.append(
            "| {case_id} | {score:.2f} | {passed} | {problem} | {scaffold} | {variant} | {starter} |".format(
                case_id=case["caseId"],
                score=float(case["totalScore"]),
                passed="ja" if case["passed"] else "nej",
                problem=case["dominantProblem"],
                scaffold=selection["selectedScaffoldId"],
                variant=selection["selectedVariantId"],
                starter=selection["selectedStarterId"],
            )
        )
    lines.extend(["", "## Per case", ""])
    for case in summary["cases"]:
        lines.extend(
            [
                f"### {case['label']}",
                "",
                f"- Prompt: {case['prompt']}",
                f"- Total: `{case['totalScore']}` / 10",
                f"- Run: `{case['runId']}`",
                f"- Route sanity: `{case['routeSanity']['status']}`",
                f"- Contact CTA sanity: `{case['contactCtaSanity']['status']}`",
                f"- Dominant problem: `{case['dominantProblem']}`",
                "",
                "Signal propagation:",
                "",
            ]
        )
        for key, value in case["signalPropagation"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.extend(["", "Trait scores:", ""])
        for trait_id, trait in case["traitScores"].items():
            evidence = "; ".join(trait["evidence"]) or "no evidence"
            lines.append(
                f"- `{trait_id}`: `{trait['score']}` / 10 — {evidence}"
            )
        lines.append("")
    inventory = summary["inventory"]
    lines.extend(
        [
            "## Embeddings status",
            "",
            f"Gate-resultat: `{summary['embeddingsReadiness']}`.",
            "",
            "### Why no implementation yet",
            "",
            (
                "ADR 0026 säger att befintliga brief/render-signaler ska bevisas först. "
                "Den här körningen bygger inga embeddings och introducerar ingen ny "
                "retrieval-källa."
            ),
            "",
            "### Go conditions",
            "",
            f"- Fyra baseline-case behöver snitta minst `{PASS_AVERAGE_THRESHOLD}` / 10.",
            f"- Inget enskilt case får ligga under `{PASS_CASE_THRESHOLD}` / 10.",
            "- Selection-problemet ska vara isolerat innan vector retrieval läggs till.",
            "",
            "### What this eval says",
            "",
        ]
    )
    for reason in summary["embeddingsGate"]["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "### Next minimum implementation slice once Go",
            "",
            (
                "När gate blir Go: lägg först en read-only selection trace runt befintligt "
                "scaffold-/dossier-val med mockad retrieval-score. Bygg därefter minsta "
                "indexeringshjälpern bakom flagga; aktivera inte nya starters i samma steg."
            ),
            "",
            "## Starter-/dossier-status",
            "",
            "- Scaffolds på disk: " + ", ".join(f"`{item}`" for item in inventory["scaffoldsOnDisk"]),
            "- Runtime-aktiva scaffolds: " + ", ".join(f"`{item}`" for item in inventory["runtimeActiveScaffolds"]),
            "- Dead/on-disk-only scaffolds: "
            + (", ".join(f"`{item}`" for item in inventory["deadOnDiskOnlyScaffolds"]) or "inga"),
            "- Starters på disk: " + ", ".join(f"`{item}`" for item in inventory["startersOnDisk"]),
            "- Runtime-mappade starters: " + ", ".join(f"`{item}`" for item in inventory["runtimeMappedStarters"]),
            "- Dead/on-disk-only starters: "
            + (", ".join(f"`{item}`" for item in inventory["deadOnDiskOnlyStarters"]) or "inga"),
            "- Dossiers på disk: " + ", ".join(f"`{item}`" for item in inventory["dossiersOnDisk"]),
            "",
            "### Vilka case skulle vinna på mer material?",
            "",
            (
                "- `salon-goteborg`: kan vinna på salon-/booking-copy och eventuellt dossier, "
                "men kräver inte embeddings först."
            ),
            (
                "- `naprapat-stockholm`: bör först välja befintlig `clinic-healthcare`; "
                "det är selection/signal-propagation före retrieval."
            ),
            (
                "- `ceramics-shop`: har commerce-scaffold och commerce-starter; nästa lucka "
                "är produktcopy/contact path, inte starter-importer."
            ),
            (
                "- `electrician-malmo`: local-service-business är rimlig; förbättringen ligger "
                "i kontaktbevis och mer specifik copy."
            ),
            "",
            "### Retrieval eller kvalitet/signal?",
            "",
            (
                f"Dominerande problemtyp i denna körning är `{summary['problemMix']['dominantProblem']}`. "
                "Det talar för att nästa grind ska fixa mätbar kvalitet/signal innan "
                "embeddings eller starter-importer byggs."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def run_golden_path_eval(
    *,
    mode: str = "deterministic",
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    summaries_dir: Path = DEFAULT_SUMMARIES_DIR,
    eval_id: str | None = None,
    cases: tuple[Case, ...] = BASELINE_CASES,
    evals_dir: Path | None = None,
) -> dict[str, Any]:
    """Run all cases and write JSON + Markdown outputs.

    ``artifacts_dir`` holds the per-eval work tree (``prompt-inputs/``,
    ``runs/``, ``generated/``, ``cases/``). ``summaries_dir`` holds the
    operator-facing ``<evalId>.json`` and ``<evalId>.md`` reports. The
    legacy ``evals_dir`` keyword is still accepted: when set, both
    artifacts and summaries are placed inside that single directory so
    older callers keep working without changes.
    """

    if mode not in {"deterministic", "real-llm"}:
        raise ValueError(f"unknown mode: {mode!r}")
    if mode == "real-llm" and not os.environ.get(OPENAI_API_KEY_ENV, "").strip():
        raise SystemExit("--mode real-llm kräver OPENAI_API_KEY. Default är --mode deterministic.")
    if evals_dir is not None:
        artifacts_dir = evals_dir
        summaries_dir = evals_dir
    eval_id = eval_id or make_eval_id()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    work_dir = artifacts_dir / eval_id
    work_dir.mkdir(parents=True, exist_ok=False)
    results = [run_case(case, work_dir=work_dir, mode=mode) for case in cases]
    write_case_files(work_dir, results)
    summary = build_summary(eval_id, mode, work_dir, results)
    removed_eval_ids = prune_golden_path_evals(
        artifacts_dir,
        read_positive_int_setting(MAX_GOLDEN_PATH_EVALS_ENV) or 0,
        protected_eval_ids={eval_id},
        summaries_dir=summaries_dir,
    )
    summary["retention"] = {
        "envVar": MAX_GOLDEN_PATH_EVALS_ENV,
        "maxEvals": read_positive_int_setting(MAX_GOLDEN_PATH_EVALS_ENV),
        "removedEvalIds": removed_eval_ids,
    }
    json_path = summaries_dir / f"{eval_id}.json"
    md_path = summaries_dir / f"{eval_id}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(summary), encoding="utf-8")
    summary["jsonPath"] = str(json_path)
    summary["markdownPath"] = str(md_path)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("deterministic", "real-llm"),
        default="deterministic",
        help="Default deterministic mode requires no LLM key and skips npm build.",
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Alias for --mode real-llm. Requires OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=None,
        help=(
            "Override per-eval work-tree root. "
            f"Default: {DEFAULT_ARTIFACTS_DIR}."
        ),
    )
    parser.add_argument(
        "--summaries-dir",
        default=None,
        help=(
            "Override JSON/MD summary root. "
            f"Default: {DEFAULT_SUMMARIES_DIR}."
        ),
    )
    parser.add_argument(
        "--evals-dir",
        default=None,
        help=(
            "Legacy single-root override that places both work tree and "
            "summaries inside the same directory. Prefer --artifacts-dir "
            "and --summaries-dir."
        ),
    )
    parser.add_argument(
        "--eval-id",
        default=None,
        help="Override timestamped eval id. Useful for tests and reruns.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print summary JSON to stdout after writing files.",
    )
    parser.add_argument(
        "--fail-on-no-go",
        action="store_true",
        help="Return exit code 1 when embeddings gate is no-go. Default writes report and exits 0.",
    )
    args = parser.parse_args(argv)
    mode = "real-llm" if args.real_llm else args.mode
    if args.evals_dir:
        legacy_dir = Path(args.evals_dir).resolve()
        summary = run_golden_path_eval(
            mode=mode,
            evals_dir=legacy_dir,
            eval_id=args.eval_id,
        )
    else:
        artifacts_dir = (
            Path(args.artifacts_dir).resolve() if args.artifacts_dir else DEFAULT_ARTIFACTS_DIR
        )
        summaries_dir = (
            Path(args.summaries_dir).resolve() if args.summaries_dir else DEFAULT_SUMMARIES_DIR
        )
        summary = run_golden_path_eval(
            mode=mode,
            artifacts_dir=artifacts_dir,
            summaries_dir=summaries_dir,
            eval_id=args.eval_id,
        )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            "Golden path eval klar: "
            f"{summary['caseCount']} cases, total {summary['totalScore']} / 10, "
            f"embeddings={summary['embeddingsReadiness']}"
        )
        print(f"JSON: {summary['jsonPath']}")
        print(f"Markdown: {summary['markdownPath']}")
    if args.fail_on_no_go and summary["embeddingsReadiness"] == "no-go":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
