"""Regression tests for the SSRF guard in scripts/scrape_site.py.

The original implementation passed allow_redirects=True to requests.get,
which let a public URL silently redirect to an internal IP (AWS metadata,
loopback services, link-local) without re-running validate_ssrf. These
tests lock in the manual hop-by-hop validation introduced when that
hole was closed.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# scrape_site.py imports requests + bs4 at module load and exits the
# process if either is missing. The test environment always installs
# them via requirements.txt, but guard for the rare CI image where
# they slip through so the rest of the suite still runs.
try:
    scrape_site = importlib.import_module("scripts.scrape_site")
except SystemExit:  # pragma: no cover - import guard surfaced
    pytest.skip(
        "scripts.scrape_site refused to import (missing requests/bs4); "
        "install requirements.txt to run these tests.",
        allow_module_level=True,
    )


def _make_redirect_response(location: str, status: int = 302) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.is_redirect = True
    response.headers = {"Location": location}
    response.close = MagicMock()
    return response


def _make_ok_html_response(html: str = "<html><body>ok</body></html>") -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.is_redirect = False
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.encoding = "utf-8"
    response.raw = types.SimpleNamespace(read=lambda _n, decode_content=True: html.encode("utf-8"))
    response.close = MagicMock()
    return response


def test_fetch_html_blocks_redirect_to_loopback() -> None:
    """A 302 from a public host to http://127.0.0.1 must be rejected."""
    redirect = _make_redirect_response("http://127.0.0.1:8501/admin")
    with patch.object(scrape_site, "requests") as mock_requests:
        mock_requests.get.return_value = redirect
        mock_requests.RequestException = Exception
        html, error = scrape_site.fetch_html("https://example.com")
    assert html == ""
    assert error is not None
    assert "Redirect blockerad" in error


def test_fetch_html_blocks_redirect_to_link_local_metadata() -> None:
    """A 302 to the AWS/GCP/Azure metadata endpoint must be rejected."""
    redirect = _make_redirect_response("http://169.254.169.254/latest/meta-data/")
    with patch.object(scrape_site, "requests") as mock_requests:
        mock_requests.get.return_value = redirect
        mock_requests.RequestException = Exception
        html, error = scrape_site.fetch_html("https://example.com")
    assert html == ""
    assert error is not None
    assert "Redirect blockerad" in error


def test_fetch_html_blocks_redirect_to_file_scheme() -> None:
    """A 302 to file:///etc/passwd must be rejected even if the IP guard would not catch it."""
    redirect = _make_redirect_response("file:///etc/passwd")
    with patch.object(scrape_site, "requests") as mock_requests:
        mock_requests.get.return_value = redirect
        mock_requests.RequestException = Exception
        html, error = scrape_site.fetch_html("https://example.com")
    assert html == ""
    assert error is not None
    assert "icke-tillåtet schema" in error


def test_fetch_html_follows_public_redirect_chain() -> None:
    """Multiple hops between public hosts should still succeed."""
    hop1 = _make_redirect_response("https://www.example.com/landing")
    hop2 = _make_redirect_response("https://www.example.com/landing/v2")
    final = _make_ok_html_response("<html><body>landing v2</body></html>")
    with (
        patch.object(scrape_site, "requests") as mock_requests,
        patch.object(scrape_site, "validate_ssrf", return_value=None),
    ):
        mock_requests.get.side_effect = [hop1, hop2, final]
        mock_requests.RequestException = Exception
        html, error = scrape_site.fetch_html("https://example.com")
    assert error is None
    assert "landing v2" in html


def test_fetch_html_caps_redirect_loops() -> None:
    """An infinite redirect loop must be cut off at MAX_REDIRECTS."""
    loop_response = _make_redirect_response("https://example.com/loop")
    with (
        patch.object(scrape_site, "requests") as mock_requests,
        patch.object(scrape_site, "validate_ssrf", return_value=None),
    ):
        mock_requests.get.return_value = loop_response
        mock_requests.RequestException = Exception
        html, error = scrape_site.fetch_html("https://example.com")
    assert html == ""
    assert error is not None
    assert "redirects" in error


def test_fetch_html_does_not_set_allow_redirects_true() -> None:
    """Source-lock so a future refactor cannot quietly re-enable allow_redirects=True."""
    source = (REPO_ROOT / "scripts" / "scrape_site.py").read_text(encoding="utf-8")
    fetch_index = source.index("def fetch_html(")
    next_def = source.index("\ndef ", fetch_index + 1)
    body = source[fetch_index:next_def]
    # Strip docstring + comments before scanning so the SSRF rationale we
    # write in the docstring (which intentionally mentions the old
    # allow_redirects=True call) does not trip the source-lock.
    code_lines = []
    in_docstring = False
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            in_docstring = not in_docstring
            if stripped.count(quote) >= 2:
                in_docstring = False
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        code_lines.append(line)
    code_only = "\n".join(code_lines)
    assert "allow_redirects=False" in code_only, (
        "fetch_html must call requests.get with allow_redirects=False "
        "and validate every hop manually via validate_ssrf."
    )
    assert "allow_redirects=True" not in code_only, (
        "allow_redirects=True would re-open the SSRF hop-validation gap."
    )
