from pathlib import Path

from packages.generation.quality_gate import run_quality_gate
from packages.generation.quality_gate.checks import run_contact_cta_presence_check
from packages.generation.quality_gate.gate import _CHECKS_REGISTRY


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
