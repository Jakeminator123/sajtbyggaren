"""SNI-branschgoldens (ADR 0045, Fas 4) — sex representativa branscher.

Låser hela kedjan ``answers.sniCode`` → sni-discovery-map → branschprofil →
Discovery Resolver → Project Input → plan → genererade routes → quality gate
för en bransch per scaffold:

=============  =========  ===========  ========================  ==============
Bransch        SNI 2025   Kategori     Scaffold                  Profil
=============  =========  ===========  ========================  ==============
Frisör         96.210     salon        local-service-business    sni-96
Restaurang     56.110     restaurant   restaurant-hospitality    sni-56
Advokat        69.101     legal        professional-services     sni-69
Tandläkare     86.230     healthcare   clinic-healthcare         sni-86
E-handel       47.752     ecommerce    ecommerce-lite            sni-47
Byggfirma      43.341     construction local-service-business    sni-43
=============  =========  ===========  ========================  ==============

Två lager:

1. ``test_sni_golden_resolver_chain`` — snabb, ren resolver-golden:
   kategori-härledning ur sniCode (utan siteType), profil-gating,
   extraCapabilities-merge och planner-kontext i decision + Project Input.
2. ``test_sni_golden_mini_eval`` — mini-eval per plan-dokumentet: kör
   prompt → Project Input → build (``do_build=False``, Node-fritt) och
   verifierar att branschens scaffold/variant/starter pinnas, att
   branschsidorna (t.ex. restaurangens ``/meny`` + ``/bokning``) faktiskt
   emitteras, och att quality-gaten är exakt ``ok``.

Mock-safe: ``OPENAI_API_KEY`` tas bort så brief/plan går deterministiska
mock-vägar; alla artefakter landar under ``tmp_path``. Om en deterministisk
mappning medvetet ändras (ny profil-kurering, ny kategori-mappning) ska
``_CASES`` uppdateras — inte assertionerna försvagas.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.discovery import resolve_discovery  # noqa: E402
from scripts.build_site import build  # noqa: E402
from scripts.prompt_to_project_input import generate  # noqa: E402

pytestmark = pytest.mark.tooling


@dataclass(frozen=True)
class _SniGoldenCase:
    case_id: str
    prompt: str
    sni_code: str
    normalized_code: str
    profile_id: str
    category_id: str
    scaffold_id: str
    variant_id: str
    starter_id: str
    # Capabilities som BRANSCHPROFILEN garanterar (delmängd av
    # requestedCapabilities; taxonomin kan lägga till fler).
    profile_capabilities: tuple[str, ...]
    # Branschsidor som måste emitteras (delmängd av genererade routes).
    industry_routes: tuple[str, ...]


_CASES: tuple[_SniGoldenCase, ...] = (
    _SniGoldenCase(
        case_id="frisor",
        prompt="Skapa en hemsida för en frisörsalong i Göteborg.",
        sni_code="96.210",
        normalized_code="96210",
        profile_id="sni-96",
        category_id="salon",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        starter_id="marketing-base",
        profile_capabilities=("booking", "pricing", "gallery", "hours"),
        industry_routes=("/", "/tjanster", "/om-oss", "/kontakt"),
    ),
    _SniGoldenCase(
        case_id="restaurang",
        prompt="Skapa en hemsida för en restaurang i Stockholm.",
        sni_code="56.110",
        normalized_code="56110",
        profile_id="sni-56",
        category_id="restaurant",
        scaffold_id="restaurant-hospitality",
        variant_id="warm-bistro",
        starter_id="marketing-base",
        profile_capabilities=("menu", "booking", "hours", "location", "gallery"),
        industry_routes=("/", "/meny", "/bokning", "/hitta-hit", "/om-oss"),
    ),
    _SniGoldenCase(
        case_id="advokat",
        prompt="Skapa en hemsida för en advokatbyrå i Malmö.",
        sni_code="69.101",
        normalized_code="69101",
        profile_id="sni-69",
        category_id="legal",
        scaffold_id="professional-services",
        variant_id="legal-classic",
        starter_id="marketing-base",
        profile_capabilities=("contact-form", "team-section", "faq-section"),
        industry_routes=("/", "/expertis", "/om-oss", "/kontakta-oss"),
    ),
    _SniGoldenCase(
        case_id="tandlakare",
        prompt="Skapa en hemsida för en tandläkarmottagning i Uppsala.",
        sni_code="86.230",
        normalized_code="86230",
        profile_id="sni-86",
        category_id="healthcare",
        scaffold_id="clinic-healthcare",
        variant_id="clinic-calm",
        starter_id="marketing-base",
        profile_capabilities=(
            "booking",
            "contact-form",
            "hours",
            "location",
            "faq-section",
        ),
        industry_routes=("/", "/behandlingar", "/om-oss", "/kontakta-oss"),
    ),
    _SniGoldenCase(
        case_id="ehandel",
        prompt="Skapa en hemsida för en webbutik som säljer hudvård.",
        sni_code="47.752",
        normalized_code="47752",
        profile_id="sni-47",
        category_id="ecommerce",
        scaffold_id="ecommerce-lite",
        variant_id="clean-store",
        starter_id="commerce-base",
        profile_capabilities=("payments", "gallery", "reviews"),
        industry_routes=("/", "/produkter", "/om-oss", "/kontakt"),
    ),
    _SniGoldenCase(
        case_id="bygg",
        prompt="Skapa en hemsida för en byggfirma i Örebro.",
        sni_code="43.341",
        normalized_code="43341",
        profile_id="sni-43",
        category_id="construction",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        starter_id="marketing-base",
        profile_capabilities=("contact-form", "gallery", "guarantees"),
        industry_routes=("/", "/tjanster", "/om-oss", "/kontakt"),
    ),
)

_CASE_IDS = tuple(case.case_id for case in _CASES)


def _candidate_project_input(case: _SniGoldenCase) -> dict:
    """Minimal Site Brief-derived Project Input som resolvern startar från."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": f"sni-golden-{case.case_id}",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Golden AB",
            "businessType": "service-provider",
            "tagline": "Golden tagline",
            "story": "Golden story",
        },
        "location": {"city": "Malmö", "country": "Sverige", "serviceAreas": []},
        "services": [{"id": "svc", "label": "Tjänst", "summary": "Tjänst."}],
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "golden@example.se",
            "addressLines": ["Adress 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }


def _sni_payload(case: _SniGoldenCase) -> dict:
    """Wizard-payload med ENBART sniCode — ingen siteType.

    Det är det skarpaste golden-läget: kategorin måste härledas helt ur
    sni-discovery-map och profilen måste appliceras via gating-vägen.
    """
    return {
        "schemaVersion": 1,
        "rawPrompt": case.prompt,
        "answers": {"sniCode": case.sni_code},
    }


# ---------------------------------------------------------------------------
# Lager 1 — resolver-golden (profil → capabilities → decision)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", _CASES, ids=_CASE_IDS)
def test_sni_golden_resolver_chain(case: _SniGoldenCase) -> None:
    project_input, decision = resolve_discovery(
        raw_prompt=case.prompt,
        payload=_sni_payload(case),
        project_input_candidate=_candidate_project_input(case),
    )

    # Spårbarhet: decision bär normaliserad kod + profil-id.
    assert decision.sniCode == case.normalized_code, (
        f"{case.case_id}: decision.sniCode var {decision.sniCode!r}, "
        f"förväntade {case.normalized_code!r}."
    )
    assert decision.industryProfileId == case.profile_id, (
        f"{case.case_id}: industryProfileId var {decision.industryProfileId!r}, "
        f"förväntade {case.profile_id!r}. Om profil-id:t medvetet ändrats i "
        "industry-profiles.v1.json ska _CASES uppdateras."
    )

    # Kategori-härledning ur sniCode (utan siteType) → rätt scaffold/variant.
    assert decision.selectedScaffoldId == case.scaffold_id, (
        f"{case.case_id}: SNI {case.sni_code} ska härleda kategori "
        f"{case.category_id!r} → scaffold {case.scaffold_id!r}, fick "
        f"{decision.selectedScaffoldId!r}."
    )
    assert decision.selectedVariantId == case.variant_id
    assert project_input["scaffoldId"] == case.scaffold_id
    assert project_input["variantId"] == case.variant_id

    # Profil → capabilities: alla extraCapabilities ska finnas i Project Input.
    requested = set(project_input.get("requestedCapabilities", []))
    missing = set(case.profile_capabilities) - requested
    assert not missing, (
        f"{case.case_id}: profilens capabilities {sorted(missing)} saknas i "
        f"requestedCapabilities {sorted(requested)} — profil-mergen i "
        "_resolve_capabilities har regredierat."
    )

    # Profil → planner-kontext: copy-vinkeln når notesForPlanner med
    # SNI-prefixet (gör den lätt att hitta/strippa nedströms).
    notes = (project_input.get("directives") or {}).get("notesForPlanner", "")
    assert f"Bransch (SNI {case.normalized_code[:2]}" in notes, (
        f"{case.case_id}: branschkontext saknas i notesForPlanner: {notes!r}"
    )


def test_sni_golden_explicit_sitetype_still_wins() -> None:
    """Operatörens explicita siteType slår SNI-härledningen (mjuk signal).

    Byggfirme-SNI + explicit valt ``restaurant`` ska ge restaurang-scaffold;
    profilen appliceras INTE (gating: profilens kategori matchar inte) men
    koden behålls för spårbarhet.
    """
    case = next(c for c in _CASES if c.case_id == "bygg")
    payload = _sni_payload(case)
    payload["answers"]["siteType"] = ["restaurant"]

    project_input, decision = resolve_discovery(
        raw_prompt=case.prompt,
        payload=payload,
        project_input_candidate=_candidate_project_input(case),
    )

    assert project_input["scaffoldId"] == "restaurant-hospitality"
    assert decision.sniCode == case.normalized_code
    # Bygg-profilen (sni-43, construction) får inte läcka in i restaurant-valet.
    assert decision.industryProfileId is None
    assert "guarantees" not in set(project_input.get("requestedCapabilities", []))


# ---------------------------------------------------------------------------
# Lager 2 — mini-eval (prompt → bygge → routes → quality gate, Node-fritt)
# ---------------------------------------------------------------------------


def _list_generated_routes(run_dir: Path) -> set[str]:
    app_dir = run_dir / "generated-files" / "app"
    routes: set[str] = set()
    for page_file in sorted(app_dir.rglob("page.tsx")):
        if page_file.parent == app_dir:
            routes.add("/")
        else:
            rel = page_file.parent.relative_to(app_dir).parts
            routes.add("/" + "/".join(rel))
    return routes


@pytest.mark.parametrize("case", _CASES, ids=_CASE_IDS)
def test_sni_golden_mini_eval(
    case: _SniGoldenCase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    project_input, meta, project_input_path, _meta_path = generate(
        case.prompt,
        output_dir=tmp_path / "prompt-inputs",
        site_id=f"sni-golden-{case.case_id}",
        discovery=_sni_payload(case),
    )

    decision = meta.get("discoveryDecision", {})
    assert decision.get("sniCode") == case.normalized_code
    assert decision.get("industryProfileId") == case.profile_id

    _target, run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
        auto_prune=False,
    )

    site_plan = json.loads((run_dir / "site-plan.json").read_text(encoding="utf-8"))
    quality_result = json.loads(
        (run_dir / "quality-result.json").read_text(encoding="utf-8")
    )
    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )

    # Plan-kedjan pinnar branschens scaffold/variant/starter.
    assert site_plan.get("scaffoldId") == case.scaffold_id, (
        f"{case.case_id}: site-plan scaffoldId {site_plan.get('scaffoldId')!r} "
        f"≠ förväntat {case.scaffold_id!r}."
    )
    assert site_plan.get("variantId") == case.variant_id
    assert site_plan.get("starterId") == case.starter_id

    # Branschsidorna renderas faktiskt (delmängd — starters får skicka fler).
    generated_routes = _list_generated_routes(run_dir)
    missing_routes = set(case.industry_routes) - generated_routes
    assert not missing_routes, (
        f"{case.case_id}: branschroutes {sorted(missing_routes)} saknas bland "
        f"genererade routes {sorted(generated_routes)}."
    )

    # Quality gate exakt grön + ärligt skippat npm-bygge (do_build=False).
    assert quality_result.get("status") == "ok", (
        f"{case.case_id}: quality-result status "
        f"{quality_result.get('status')!r} ≠ 'ok'."
    )
    assert build_result.get("status") == "skipped"
