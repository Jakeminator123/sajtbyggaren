"""Operator-upload-pipelinen.

Guards:

1. ``governance/schemas/project-input.schema.json`` accepterar ``brand``
   och ``gallery`` med AssetRef-form, men kräver dem inte
   (bakåtkompatibilitet med befintliga examples utan bilder).
2. ``$defs/assetRef`` failar closed på unkown enum-värden för
   ``role``/``placement``/``mimeType``.
3. ``iter_asset_refs`` plockar både brand.logo, brand.heroImage och
   gallery-items från en Project Input.
4. ``copy_operator_uploads`` returnerar 0 utan att krascha när
   uppladdningsmappen saknas.
5. ``_apply_discovery_overrides`` mappar discovery.assets → brand.logo /
   brand.heroImage / gallery i Project Input.

Ingen extern nätverks-I/O — vi mockar disk genom temporära mappar och
remote fetch genom monkeypatchad ``requests.get``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
EXAMPLE_PROJECT_INPUT = REPO_ROOT / "examples" / next(
    (
        p.name
        for p in (REPO_ROOT / "examples").glob("*.project-input.json")
    ),
    "",
)


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base_project_input() -> dict:
    assert EXAMPLE_PROJECT_INPUT.exists(), (
        "Hittade inget committat project-input-example att basera testerna på."
    )
    return json.loads(EXAMPLE_PROJECT_INPUT.read_text(encoding="utf-8"))


def _valid_asset_ref(**overrides) -> dict:
    base = {
        "assetId": "01HXYZ7Q3KEXABCDEFG1234567",
        "filename": "logo-01hxyz7q.webp",
        "mimeType": "image/webp",
        "sizeBytes": 18342,
        "width": 512,
        "height": 512,
        "alt": "Företagets logotyp",
        "role": "logo",
    }
    base.update(overrides)
    return base


class _FakeRemoteAssetResponse:
    def __init__(
        self,
        data: bytes = b"",
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.data = data
        self.status_code = status_code
        self.headers = headers or {}
        self.chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size: int) -> list[bytes]:
        if self.chunks is not None:
            return self.chunks
        return [
            self.data[index : index + chunk_size]
            for index in range(0, len(self.data), chunk_size)
        ]

    def close(self) -> None:
        self.closed = True


@pytest.mark.governance
def test_schema_accepts_brand_logo_hero_and_gallery(
    schema: dict, base_project_input: dict
) -> None:
    payload = copy.deepcopy(base_project_input)
    payload["brand"] = {
        "logo": _valid_asset_ref(),
        "heroImage": _valid_asset_ref(
            assetId="01HXYZ8R0XYZ0PQRSTUV9876543",
            filename="hero-01hxyz8r.webp",
            role="hero",
            alt="Bild av lokalen",
        ),
        "primaryColorHex": "#1A2B3C",
    }
    payload["gallery"] = [
        _valid_asset_ref(
            assetId="01HXYZ9S0AAAA1234567890ABCD",
            filename="gallery-01hxyz9s.webp",
            role="gallery",
            placement="about",
        )
    ]
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert not errors, [error.message for error in errors]


@pytest.mark.governance
def test_schema_declares_source_url_as_optional_uri(schema: dict) -> None:
    asset_ref_schema = schema["$defs"]["assetRef"]
    source_url_schema = asset_ref_schema["properties"]["sourceUrl"]

    assert source_url_schema["type"] == "string"
    assert source_url_schema["format"] == "uri"
    assert "sourceUrl" not in asset_ref_schema["required"]
    assert asset_ref_schema["additionalProperties"] is False


@pytest.mark.tooling
def test_copy_operator_uploads_handles_stream_interruption_gracefully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reviewer-fynd (Hög, 2026-05-24): ``_fetch_asset_bytes_from_url``
    fångade tidigare bara fel runt ``requests.get(...)``, inte fel som
    uppstår senare under ``response.iter_content(...)``. Om blob-svaret
    bröts mitt i streamen kunde en ``ChunkedEncodingError`` bubbla ut
    från ``copy_operator_uploads`` och krascha hela bygget — trots att
    funktionen uttryckligen lovar att tystlåtet hoppa över trasiga assets.

    Det här testet låser den inre ``try/except requests.RequestException``
    som nu omger ``iter_content``-loopen. Förlorar streamen efter första
    chunken: funktionen returnerar ``None`` (skippas) i stället för att
    kasta. Resten av bygget fortsätter.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    class _BrokenStreamResponse:
        status_code = 200
        headers: dict[str, str] = {}
        closed = False

        def iter_content(self, chunk_size: int):  # noqa: ARG002
            yield b"webp\x00first-chunk-ok"
            raise build_site.requests.exceptions.ChunkedEncodingError(
                "Connection broken: stream interrupted mid-read"
            )

        def close(self) -> None:
            self.closed = True

    response = _BrokenStreamResponse()
    monkeypatch.setattr(build_site.requests, "get", lambda *_a, **_kw: response)

    ref = _valid_asset_ref(
        assetId="01HSTREAM0000000000000000",
        filename="broken.webp",
        sourceUrl="https://abc.public.blob.vercel-storage.com/broken.webp",
    )
    target = tmp_path / "generated-site"
    target.mkdir()

    copied = build_site.copy_operator_uploads(
        "missing-on-disk", target, {"brand": {"logo": ref}}
    )

    captured = capsys.readouterr()
    assert copied == 0, "Broken stream ska skippas, inte krascha builden"
    assert "stream interrupted" in captured.out, (
        f"Expected stream-fel-log i stdout, fick: {captured.out!r}"
    )
    assert response.closed is True, "response.close() måste köras även på fel"
    assert not (target / "public" / "uploads" / "broken.webp").exists()


@pytest.mark.tooling
def test_runtime_gatekeeper_rejects_malformed_sourceurl_strings() -> None:
    """Reviewer-fynd (Låg, 2026-05-24): schema deklarerar ``format: "uri"``
    men JSON Schema gör format-enforcement opt-in (kräver rfc3987 e.dyl.) —
    värdena ALDRIG stoppas av schemat ensamt. Den faktiska gatekeepern är
    ``_is_allowed_asset_source_url`` i build_site.py som kallas innan
    ``_fetch_asset_bytes_from_url``. Detta test låser att gatekeepern
    avvisar alla rimliga "string men inte HTTPS-blob-URL"-fall, inte bara
    de uppenbara (HTTP, file:, okänd host) som redan testas i
    ``test_is_allowed_asset_source_url_allowlist``.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import _is_allowed_asset_source_url  # noqa: E402

    malformed = [
        "not a url at all",
        "   ",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//public.blob.vercel-storage.com/x.webp",
        "https://",
        "https:///x.webp",
        "blob:https://public.blob.vercel-storage.com/x.webp",
        "ftp://public.blob.vercel-storage.com/x.webp",
        "ssh://public.blob.vercel-storage.com/x.webp",
    ]
    for candidate in malformed:
        assert not _is_allowed_asset_source_url(candidate), (
            f"Gatekeepern måste avvisa malformed sourceUrl {candidate!r}"
        )


@pytest.mark.governance
def test_schema_still_validates_existing_examples_without_brand(
    schema: dict,
) -> None:
    """Bakåtkompat: alla committade examples måste validera mot det
    utökade schemat trots att de saknar brand/gallery-fälten."""
    validator = jsonschema.Draft202012Validator(schema)
    for path in (REPO_ROOT / "examples").glob("*.project-input.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(payload))
        assert not errors, f"{path.name}: {[e.message for e in errors]}"


@pytest.mark.governance
@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "footer"),
        ("placement", "everywhere"),
        ("mimeType", "image/gif"),
    ],
)
def test_asset_ref_rejects_unknown_enum_values(
    schema: dict, base_project_input: dict, field: str, value: str
) -> None:
    payload = copy.deepcopy(base_project_input)
    bad_ref = _valid_asset_ref()
    bad_ref[field] = value
    payload["brand"] = {"logo": bad_ref}
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert errors, f"Expected schema error when {field}={value!r}"


@pytest.mark.tooling
def test_iter_asset_refs_collects_brand_and_gallery() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import iter_asset_refs  # noqa: E402

    logo = _valid_asset_ref(role="logo")
    hero = _valid_asset_ref(
        assetId="01HXYZ8R0XYZ0PQRSTUV9876543",
        filename="hero.webp",
        role="hero",
    )
    gallery_item = _valid_asset_ref(
        assetId="01HXYZ9S0AAAA1234567890ABCD",
        filename="g.webp",
        role="gallery",
        placement="about",
    )
    pi = {
        "brand": {"logo": logo, "heroImage": hero},
        "gallery": [gallery_item],
    }
    refs = iter_asset_refs(pi)
    asset_ids = {ref["assetId"] for ref in refs}
    assert asset_ids == {
        logo["assetId"],
        hero["assetId"],
        gallery_item["assetId"],
    }


@pytest.mark.tooling
def test_copy_operator_uploads_returns_zero_when_uploads_missing(
    tmp_path: Path,
) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import copy_operator_uploads  # noqa: E402

    pi = {"brand": {"logo": _valid_asset_ref()}}
    target = tmp_path / "generated-site"
    target.mkdir()
    # Ingen data/uploads/<siteId>/ existerar → ska returnera 0 utan
    # att kasta. public/uploads/ skapas ändå (idempotent).
    copied = copy_operator_uploads("doesnotexist", target, pi)
    assert copied == 0


@pytest.mark.tooling
def test_copy_operator_uploads_fetches_from_source_url_when_disk_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote Vercel Blob bytes are fetched and copied without real network I/O."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    ref = _valid_asset_ref(
        assetId="01HBLOB000000000000000000",
        filename="hero-from-blob.webp",
        sourceUrl="https://abc123.public.blob.vercel-storage.com/uploads/01HBLOB.../optimized.webp",
    )
    pi = {"brand": {"heroImage": ref}}
    target = tmp_path / "generated-site"
    target.mkdir()

    fake_bytes = b"webp\x00bytes-from-blob"
    response = _FakeRemoteAssetResponse(fake_bytes)
    fetch_calls: list[tuple[str, dict]] = []

    def fake_get(url: str, **kwargs) -> _FakeRemoteAssetResponse:
        fetch_calls.append((url, kwargs))
        return response

    monkeypatch.setattr(build_site.requests, "get", fake_get)

    copied = build_site.copy_operator_uploads("missing-on-disk", target, pi)

    assert copied == 1
    dest = target / "public" / "uploads" / "hero-from-blob.webp"
    assert dest.exists()
    assert dest.read_bytes() == fake_bytes
    assert response.closed is True
    assert fetch_calls == [
        (
            ref["sourceUrl"],
            {
                "headers": {
                    "User-Agent": "sajtbyggaren-build/1.0",
                    "Accept": "*/*",
                },
                "timeout": 15,
                "stream": True,
                "allow_redirects": False,
            },
        )
    ]


@pytest.mark.tooling
def test_copy_operator_uploads_uses_local_disk_when_source_url_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LocalAssetStore disk lookup remains unchanged when sourceUrl is absent."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    uploads_root = tmp_path / "uploads"
    asset_id = "01HLOCAL000000000000000000"
    asset_dir = uploads_root / "__draft" / asset_id
    asset_dir.mkdir(parents=True)
    disk_bytes = b"local-optimized-webp"
    (asset_dir / "optimized.webp").write_bytes(disk_bytes)

    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    ref = _valid_asset_ref(assetId=asset_id, filename="local.webp")
    pi = {"brand": {"logo": ref}}
    target = tmp_path / "generated-site"
    target.mkdir()

    def fail_get(*_args, **_kwargs):
        raise AssertionError("No remote fetch should run when sourceUrl is absent")

    monkeypatch.setattr(build_site.requests, "get", fail_get)

    copied = build_site.copy_operator_uploads("anysite", target, pi)

    assert copied == 1
    assert (target / "public" / "uploads" / "local.webp").read_bytes() == disk_bytes


@pytest.mark.tooling
def test_copy_operator_uploads_rejects_disallowed_source_url_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSRF-skydd: en ``sourceUrl`` mot en okänd host ska tystlåtet
    hoppas över, INTE fetchas. Vi vill inte att build_site kan tvingas
    GET-a vilken URL som helst som råkar smitas in i en project-input."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    ref = _valid_asset_ref(
        assetId="01HEVIL00000000000000000",
        filename="evil.webp",
        sourceUrl="https://attacker.example.com/internal-metadata",
    )
    pi = {"brand": {"logo": ref}}
    target = tmp_path / "generated-site"
    target.mkdir()

    def fail_get(*_args, **_kwargs):
        raise AssertionError("Fetch ska aldrig anropas för en otillåten host")

    monkeypatch.setattr(build_site.requests, "get", fail_get)

    copied = build_site.copy_operator_uploads("doesnotexist", target, pi)
    assert copied == 0
    assert not (target / "public" / "uploads" / "evil.webp").exists()


@pytest.mark.tooling
def test_copy_operator_uploads_rejects_http_source_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTPS is required even for an otherwise allowed blob host."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    ref = _valid_asset_ref(
        assetId="01HHTTP000000000000000000",
        filename="http.webp",
        sourceUrl="http://abc.public.blob.vercel-storage.com/x.webp",
    )
    target = tmp_path / "generated-site"
    target.mkdir()

    def fail_get(*_args, **_kwargs):
        raise AssertionError("Fetch ska aldrig anropas för http:// sourceUrl")

    monkeypatch.setattr(build_site.requests, "get", fail_get)

    copied = build_site.copy_operator_uploads("doesnotexist", target, {"brand": {"logo": ref}})

    assert copied == 0
    assert not (target / "public" / "uploads" / "http.webp").exists()


@pytest.mark.tooling
def test_copy_operator_uploads_source_url_is_authoritative_over_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When sourceUrl exists it is authoritative, even if stale local bytes exist."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    uploads_root = tmp_path / "uploads"
    asset_id = "01HBOTH0000000000000000000"
    asset_dir = uploads_root / "__draft" / asset_id
    asset_dir.mkdir(parents=True)
    disk_bytes = b"disk-bytes-should-win"
    (asset_dir / "optimized.webp").write_bytes(disk_bytes)

    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    remote_bytes = b"remote-bytes-should-win"
    ref = _valid_asset_ref(
        assetId=asset_id,
        filename="both.webp",
        sourceUrl="https://abc.public.blob.vercel-storage.com/should-be-called",
    )
    pi = {"brand": {"logo": ref}}
    target = tmp_path / "generated-site"
    target.mkdir()

    def fake_get(_url: str, **_kwargs) -> _FakeRemoteAssetResponse:
        return _FakeRemoteAssetResponse(remote_bytes)

    monkeypatch.setattr(build_site.requests, "get", fake_get)

    copied = build_site.copy_operator_uploads("anysite", target, pi)
    assert copied == 1
    dest = target / "public" / "uploads" / "both.webp"
    assert dest.read_bytes() == remote_bytes


@pytest.mark.tooling
def test_copy_operator_uploads_skips_too_large_source_url_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    monkeypatch.setattr(build_site, "_REMOTE_ASSET_MAX_BYTES", 8)
    response = _FakeRemoteAssetResponse(
        b"",
        headers={"Content-Length": "9"},
    )

    def fake_get(_url: str, **_kwargs) -> _FakeRemoteAssetResponse:
        return response

    monkeypatch.setattr(build_site.requests, "get", fake_get)

    ref = _valid_asset_ref(
        assetId="01HLARGE00000000000000000",
        filename="large.webp",
        sourceUrl="https://abc.public.blob.vercel-storage.com/large.webp",
    )
    target = tmp_path / "generated-site"
    target.mkdir()

    copied = build_site.copy_operator_uploads("doesnotexist", target, {"brand": {"logo": ref}})

    captured = capsys.readouterr()
    assert copied == 0
    assert "payload larger than 8 bytes" in captured.out
    assert "Skipping asset" in captured.out
    assert response.closed is True
    assert not (target / "public" / "uploads" / "large.webp").exists()


@pytest.mark.tooling
def test_is_allowed_asset_source_url_allowlist() -> None:
    """Allowlist:en ska godkänna Vercel-Blob-subdomäner över HTTPS
    och avvisa allt annat (HTTP, file://, relativa pathar, okända
    hosts, IP-adresser)."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import _is_allowed_asset_source_url  # noqa: E402

    assert _is_allowed_asset_source_url(
        "https://abc.public.blob.vercel-storage.com/x/optimized.webp"
    )
    assert _is_allowed_asset_source_url(
        "https://nested.subdomain.public.blob.vercel-storage.com/y.webp"
    )
    # Fel scheme / okända hosts / lokala IP / file:
    assert not _is_allowed_asset_source_url(
        "http://abc.public.blob.vercel-storage.com/x.webp"
    )
    assert not _is_allowed_asset_source_url("https://attacker.example.com/x.webp")
    assert not _is_allowed_asset_source_url("https://169.254.169.254/metadata")
    assert not _is_allowed_asset_source_url("file:///etc/passwd")
    assert not _is_allowed_asset_source_url("/uploads/local.webp")
    assert not _is_allowed_asset_source_url("")


@pytest.mark.tooling
def test_apply_discovery_overrides_maps_assets_to_brand_and_gallery() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from prompt_to_project_input import _apply_discovery_overrides  # noqa: E402

    base_pi: dict = {}
    discovery = {
        "answers": {
            "assets": {
                "logo": _valid_asset_ref(),
                "heroImage": _valid_asset_ref(
                    assetId="01HXYZ8R0XYZ0PQRSTUV9876543",
                    filename="hero.webp",
                    role="hero",
                ),
                "gallery": [
                    _valid_asset_ref(
                        assetId="01HXYZ9S0AAAA1234567890ABCD",
                        filename="g.webp",
                        role="gallery",
                        placement="about",
                    )
                ],
            }
        }
    }
    out = _apply_discovery_overrides(base_pi, discovery)
    assert out["brand"]["logo"]["assetId"] == discovery["answers"]["assets"]["logo"]["assetId"]
    assert out["brand"]["heroImage"]["role"] == "hero"
    assert len(out["gallery"]) == 1
    assert out["gallery"][0]["placement"] == "about"
