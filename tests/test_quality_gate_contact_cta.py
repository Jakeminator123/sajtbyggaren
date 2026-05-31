import json
from pathlib import Path

import pytest

from packages.generation.quality_gate import run_quality_gate
from packages.generation.quality_gate.checks import (
    _find_contact_page,
    run_contact_cta_presence_check,
)
from packages.generation.quality_gate.gate import _CHECKS_REGISTRY

SCAFFOLDS_DIR = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
)


def _site(root: Path, hero: str, contact: str, route: str = "kontakt") -> None:
    app = root / "app"
    (app / route).mkdir(parents=True, exist_ok=True)
    (app / "page.tsx").write_text(
        f"export default function Page() {{ return <section>{hero}</section>; }}",
        encoding="utf-8",
    )
    (app / route / "page.tsx").write_text(
        f"export default function Contact() {{ return <main>{contact}</main>; }}",
        encoding="utf-8",
    )
    (root / "routes.json").write_text(
        json.dumps(
            {
                "defaultRoutes": [
                    {"id": "home", "path": "/", "required": True, "purpose": "Home"},
                    {
                        "id": "contact",
                        "path": f"/{route}",
                        "required": True,
                        "purpose": "Contact",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def _load_scaffold_routes(scaffold_id: str) -> dict:
    return json.loads(
        (SCAFFOLDS_DIR / scaffold_id / "routes.json").read_text(encoding="utf-8")
    )


def _site_from_scaffold(root: Path, scaffold_id: str) -> str:
    routes_payload = _load_scaffold_routes(scaffold_id)
    default_routes = routes_payload["defaultRoutes"]
    contact_route = next(route for route in default_routes if route["id"] == "contact")
    contact_path = contact_route["path"]
    for route in default_routes:
        path = route["path"]
        page = (
            root / "app" / "page.tsx"
            if path == "/"
            else root / "app" / path.lstrip("/") / "page.tsx"
        )
        page.parent.mkdir(parents=True, exist_ok=True)
        if route["id"] == "home":
            body = f'<section><Link href="{contact_path}">Kontakta oss</Link></section>'
        elif route["id"] == "contact":
            body = '<main><a href="tel:+46">Ring oss</a></main>'
        else:
            body = "<main>Ok</main>"
        page.write_text(
            f"export default function Page() {{ return {body}; }}",
            encoding="utf-8",
        )
    return contact_path


def test_contact_cta_presence_flags_missing_hero_and_contact_ctas(tmp_path: Path) -> None:
    _site(tmp_path, "<p>Välkommen</p>", '<Link href="/kontakt">Kontakta oss</Link>')
    assert "hero" in run_contact_cta_presence_check(tmp_path).findings[0]
    _site(tmp_path, '<Link href="/kontakt">Boka rådgivning</Link>', "<p>Kontaktinfo</p>")
    result = run_contact_cta_presence_check(tmp_path)
    assert result.status == "failed"
    assert any("saknar kontakt-CTA" in finding for finding in result.findings)


def test_contact_cta_presence_accepts_sv_and_en_ctas(tmp_path: Path) -> None:
    _site(tmp_path, '<Link href="/kontakt">Kom igång</Link>', '<a href="tel:+46">Ring oss</a>')
    assert run_contact_cta_presence_check(tmp_path).status == "ok"
    _site(
        tmp_path,
        '<Link href="/contact">Get started</Link>',
        '<a href="mailto:hi@example.com">Contact us</a>',
        "contact",
    )
    assert run_contact_cta_presence_check(tmp_path).status == "ok"


def test_contact_cta_presence_rejects_cta_text_with_non_contact_href(tmp_path: Path) -> None:
    # Reviewer-fynd 2026-05-27: efter f446be1 OR-fixen kunde
    # <a href="/products">Ring oss</a> godkännas som contact-CTA bara för
    # att body matchar "ring". Fix: page-länkar kräver BÅDE contact-route-
    # href OCH CTA-text-mönster; bara tel:/mailto: får stå ensamma på href.
    _site(tmp_path, '<a href="/products">Ring oss</a>', '<a href="tel:+46">Ring oss</a>')
    result = run_contact_cta_presence_check(tmp_path)
    assert result.status == "failed"
    assert any("hero" in finding for finding in result.findings)


def test_contact_cta_presence_rejects_contact_href_with_non_cta_text(
    tmp_path: Path,
) -> None:
    _site(tmp_path, '<a href="/kontakt">Läs mer</a>', '<a href="tel:+46">Ring oss</a>')

    result = run_contact_cta_presence_check(tmp_path)

    assert result.status == "failed"
    assert any("hero" in finding for finding in result.findings)


def test_contact_cta_presence_accepts_scaffold_specific_routes(tmp_path: Path) -> None:
    _site(
        tmp_path,
        '<Link href="/kontakta-oss">Kontakta oss</Link>',
        '<a href="tel:+46">Ring oss</a>',
        "kontakta-oss",
    )
    assert run_contact_cta_presence_check(tmp_path).status == "ok"
    _site(
        tmp_path,
        '<Link href="/hitta-hit">Hitta hit</Link>',
        '<a href="mailto:info@example.com">Get in touch</a>',
        "hitta-hit",
    )
    assert run_contact_cta_presence_check(tmp_path).status == "ok"


@pytest.mark.parametrize(
    ("scaffold_id", "expected_contact_path"),
    [
        ("local-service-business", "/kontakt"),
        ("professional-services", "/kontakta-oss"),
        ("restaurant-hospitality", "/hitta-hit"),
    ],
)
def test_contact_cta_presence_resolves_contact_path_from_scaffold_routes(
    tmp_path: Path,
    scaffold_id: str,
    expected_contact_path: str,
) -> None:
    contact_path = _site_from_scaffold(tmp_path, scaffold_id)

    result = run_contact_cta_presence_check(tmp_path)

    assert contact_path == expected_contact_path
    assert result.status == "ok"
    assert expected_contact_path in result.detail
    assert _find_contact_page(tmp_path) == (
        tmp_path / "app" / expected_contact_path.lstrip("/") / "page.tsx"
    )


def test_contact_cta_presence_flags_unresolvable_contact_route(
    tmp_path: Path,
) -> None:
    # B-review 2026-05-31: a generated site whose contact route cannot be
    # resolved (no own routes.json, no scaffold match, and the linked
    # /hitta-hit page does not even exist) must NOT pass silently. The
    # warning-severity check now surfaces a finding so the operator sees that
    # the contact page went unvalidated. Gate status stays non-blocking.
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text(
        "export default function Page() { "
        'return <section><Link href="/hitta-hit">Hitta hit</Link></section>; }',
        encoding="utf-8",
    )

    result = run_contact_cta_presence_check(tmp_path)

    assert result.status == "failed"
    assert any("kunde inte resolvas" in finding for finding in result.findings)


def test_contact_cta_presence_flags_routes_json_without_contact_id(
    tmp_path: Path,
) -> None:
    # routes.json present but missing an id="contact" entry, and no generated
    # route matches a known scaffold contact path -> unresolvable -> flagged
    # rather than silently green.
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text(
        "export default function Page() { "
        'return <section><a href="tel:+46">Ring oss</a></section>; }',
        encoding="utf-8",
    )
    (tmp_path / "routes.json").write_text(
        json.dumps(
            {
                "defaultRoutes": [
                    {"id": "home", "path": "/", "required": True, "purpose": "Home"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_contact_cta_presence_check(tmp_path)

    assert result.status == "failed"
    assert any("kunde inte resolvas" in finding for finding in result.findings)


def test_contact_cta_presence_flags_contact_via_scaffold_fallback_without_routes_json(
    tmp_path: Path,
) -> None:
    # Robustness (B-review Medium): a partial tree without routes.json that
    # still has app/hitta-hit/page.tsx must resolve the contact route via the
    # known scaffold contact paths so the contact page IS validated. A missing
    # CTA on it must fail (the report's recommended regression case).
    app = tmp_path / "app"
    (app / "hitta-hit").mkdir(parents=True)
    (app / "page.tsx").write_text(
        "export default function Page() { "
        'return <section><Link href="/hitta-hit">Hitta hit</Link></section>; }',
        encoding="utf-8",
    )
    (app / "hitta-hit" / "page.tsx").write_text(
        "export default function Contact() { return <main>Ingen CTA har</main>; }",
        encoding="utf-8",
    )

    result = run_contact_cta_presence_check(tmp_path)

    assert result.status == "failed"
    assert any("hitta-hit" in finding for finding in result.findings)


def test_contact_cta_presence_passes_via_scaffold_fallback_without_routes_json(
    tmp_path: Path,
) -> None:
    # Same partial tree, but the resolved contact page carries a CTA -> ok.
    app = tmp_path / "app"
    (app / "hitta-hit").mkdir(parents=True)
    (app / "page.tsx").write_text(
        "export default function Page() { "
        'return <section><Link href="/hitta-hit">Hitta hit</Link></section>; }',
        encoding="utf-8",
    )
    (app / "hitta-hit" / "page.tsx").write_text(
        "export default function Contact() { "
        'return <main><a href="mailto:info@example.com">Kontakta oss</a></main>; }',
        encoding="utf-8",
    )

    result = run_contact_cta_presence_check(tmp_path)

    assert result.status == "ok"
    assert "/hitta-hit" in result.detail


def test_contact_cta_presence_registered_as_warning(tmp_path: Path) -> None:
    _site(tmp_path, "<p>Välkommen</p>", "<p>Kontaktinfo</p>")
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    by_name = {check.name: check for check in result.checks}
    assert by_name["contact-cta-presence"].severity == "warning"
    assert result.status == "ok"
    assert dict(_CHECKS_REGISTRY)["contact-cta-presence"] == "warning"
