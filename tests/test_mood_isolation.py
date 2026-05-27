"""Regression tests for Gap 9 moodImages isolation.

Mood images are uploaded through the same AssetStore shape as gallery
images, but they are planning inspiration rather than public site assets.
They must therefore be preserved in Project Input, isolated under
``data/uploads/<siteId>/__mood/``, and excluded from ``public/uploads/``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.discovery import resolve_discovery  # noqa: E402


def _valid_asset_ref(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "assetId": "01JMOOD0000000000000000000",
        "filename": "mood-01jmood.webp",
        "mimeType": "image/webp",
        "sizeBytes": 4096,
        "width": 800,
        "height": 600,
        "alt": "Mood-referens",
        "role": "gallery",
    }
    base.update(overrides)
    return base


def _candidate_project_input() -> dict[str, Any]:
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "mood-isolation-site",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Mood Test AB",
            "businessType": "painter",
            "tagline": "Testar mood-bilder",
            "story": "En testfirma för mood-bilder.",
        },
        "location": {
            "city": "Stockholm",
            "country": "Sverige",
            "serviceAreas": ["Stockholm"],
        },
        "services": [
            {"id": "maleri", "label": "Måleri", "summary": "Måleri."}
        ],
        "tone": {"primary": "warm", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "hej@example.se",
            "addressLines": ["Exempelgatan 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }


class _FakeRemoteAssetResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.closed = False

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return [
            self.data[index : index + chunk_size]
            for index in range(0, len(self.data), chunk_size)
        ]

    def close(self) -> None:
        self.closed = True


@pytest.fixture(scope="module")
def project_input_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_iter_asset_refs_excludes_mood_images() -> None:
    from scripts.build_site import iter_asset_refs

    gallery_ref = _valid_asset_ref(
        assetId="01JGALLERY0000000000000000",
        filename="gallery.webp",
        alt="Publik galleribild",
    )
    mood_ref = _valid_asset_ref(
        assetId="01JMOODONLY00000000000000",
        filename="mood.webp",
        alt="Privat mood-bild",
    )

    refs = iter_asset_refs({"gallery": [gallery_ref], "moodImages": [mood_ref]})

    assert [ref["assetId"] for ref in refs] == [gallery_ref["assetId"]]


@pytest.mark.tooling
def test_copy_operator_uploads_does_not_publish_mood_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import build_site

    uploads_root = tmp_path / "uploads"
    site_id = "mood-site"
    mood_ref = _valid_asset_ref()
    mood_dir = uploads_root / site_id / mood_ref["assetId"]
    mood_dir.mkdir(parents=True)
    (mood_dir / "optimized.webp").write_bytes(b"private-mood-bytes")
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    target = tmp_path / "generated-site"
    target.mkdir()

    copied = build_site.copy_operator_uploads(
        site_id,
        target,
        {"moodImages": [mood_ref]},
    )

    assert copied == 0
    assert not (target / "public" / "uploads" / mood_ref["filename"]).exists()


@pytest.mark.tooling
def test_copy_mood_assets_copies_local_bytes_to_private_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import build_site

    uploads_root = tmp_path / "uploads"
    site_id = "mood-site"
    mood_ref = _valid_asset_ref()
    source_dir = uploads_root / site_id / mood_ref["assetId"]
    source_dir.mkdir(parents=True)
    (source_dir / "optimized.webp").write_bytes(b"private-mood-bytes")
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    copied = build_site.copy_mood_assets(site_id, {"moodImages": [mood_ref]})

    dest = uploads_root / site_id / "__mood" / f"{mood_ref['assetId']}.webp"
    assert copied == 1
    assert dest.read_bytes() == b"private-mood-bytes"


@pytest.mark.tooling
def test_copy_mood_assets_skips_missing_bytes_without_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import build_site

    uploads_root = tmp_path / "uploads"
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)
    mood_ref = _valid_asset_ref(assetId="01JMISSING000000000000000")

    copied = build_site.copy_mood_assets("mood-site", {"moodImages": [mood_ref]})

    captured = capsys.readouterr()
    assert copied == 0
    assert "saknas både på disk" in captured.out
    assert not list((uploads_root / "mood-site" / "__mood").glob("*"))


@pytest.mark.tooling
def test_copy_mood_assets_uses_source_url_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import build_site

    uploads_root = tmp_path / "uploads"
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)
    remote_bytes = b"remote-mood-bytes"
    response = _FakeRemoteAssetResponse(remote_bytes)

    def fake_get(_url: str, **_kwargs: Any) -> _FakeRemoteAssetResponse:
        return response

    monkeypatch.setattr(build_site.requests, "get", fake_get)
    mood_ref = _valid_asset_ref(
        assetId="01JREMOTE0000000000000000",
        filename="remote-mood.webp",
        sourceUrl="https://abc.public.blob.vercel-storage.com/remote-mood.webp",
    )

    copied = build_site.copy_mood_assets("mood-site", {"moodImages": [mood_ref]})

    dest = uploads_root / "mood-site" / "__mood" / f"{mood_ref['assetId']}.webp"
    assert copied == 1
    assert dest.read_bytes() == remote_bytes
    assert response.closed is True


@pytest.mark.tooling
def test_resolver_preserves_mood_images_in_project_input(
    project_input_schema: dict[str, Any],
) -> None:
    payload = {
        "schemaVersion": 2,
        "rawPrompt": "Måleri i Stockholm sedan 1998",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {
            "siteType": ["business"],
            "moodImages": [
                _valid_asset_ref(
                    visionSubject="warm earth-tone interior",
                    visionConfidence="high",
                )
            ],
        },
        "directives": {"language": "sv", "scaffoldHint": "local-service-business"},
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["moodImages"][0]["assetId"] == payload["answers"]["moodImages"][0]["assetId"]
    assert project_input["moodImages"][0]["visionSubject"] == "warm earth-tone interior"
    assert decision.fieldSources["moodImages"] == "wizard"


@pytest.mark.tooling
def test_build_site_brief_maps_mood_vision_to_notes_for_planner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = json.loads(
        (REPO_ROOT / "examples" / "painter-palma.project-input.json").read_text(
            encoding="utf-8"
        )
    )
    project_input["siteId"] = "mood-brief-site"
    project_input["moodImages"] = [
        _valid_asset_ref(
            assetId="01JBRIEFMOOD000000000000",
            filename="warm-mood.webp",
            alt="Varm färgpalett med trä och grönt",
            visionSubject="warm wood and green palette",
            visionConfidence="high",
        )
    ]
    project_input_path = tmp_path / "mood-brief-site.project-input.json"
    project_input_path.write_text(
        json.dumps(project_input, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _target, run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    notes = brief["notesForPlanner"]
    assert "Visual mood: Varm färgpalett med trä och grönt" in notes
    assert "subject: warm wood and green palette" in notes
    assert "confidence: high" in notes
