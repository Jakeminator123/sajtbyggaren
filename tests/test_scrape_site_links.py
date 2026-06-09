"""Regressionstester för B165 — apex<->www host-normalisering i collect_links.

Operatörer anger ofta apex-domänen (``example.com``) medan sajten
redirectar till ``www.example.com`` och länkar internt med www-prefix.
``fetch_html`` följer redirecten för HTML:en, men ``collect_links``
jämförde host strikt mot ursprungs-URL:en — alla www-länkar
filtrerades bort som externa och bara startsidan crawlades (kontakt-/
om-sidor missades helt).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# scrape_site.py importerar requests + bs4 vid modul-load och avslutar
# processen om någon saknas. Samma guard som test_scrape_site_ssrf.py.
try:
    scrape_site = importlib.import_module("scripts.scrape_site")
except SystemExit:  # pragma: no cover - import guard surfaced
    pytest.skip(
        "scripts.scrape_site refused to import (missing requests/bs4); "
        "install requirements.txt to run these tests.",
        allow_module_level=True,
    )

from bs4 import BeautifulSoup  # noqa: E402


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


@pytest.mark.tooling
def test_collect_links_keeps_www_links_when_base_is_apex() -> None:
    """B165: www-länkar är interna när operatören angav apex-domänen."""
    html = (
        '<a href="https://www.example.com/kontakt">Kontakt</a>'
        '<a href="https://www.example.com/om-oss">Om oss</a>'
    )
    links = scrape_site.collect_links(_soup(html), "https://example.com")
    assert "https://www.example.com/kontakt" in links
    assert "https://www.example.com/om-oss" in links


@pytest.mark.tooling
def test_collect_links_keeps_apex_links_when_base_is_www() -> None:
    """B165 (spegeln): apex-länkar är interna när basen är www-varianten."""
    html = '<a href="https://example.com/tjanster">Tjänster</a>'
    links = scrape_site.collect_links(_soup(html), "https://www.example.com")
    assert "https://example.com/tjanster" in links


@pytest.mark.tooling
def test_collect_links_still_filters_foreign_hosts() -> None:
    """Normaliseringen får inte öppna för externa hosts."""
    html = (
        '<a href="https://facebook.com/example">FB</a>'
        '<a href="https://www.othersite.se/sida">Annan</a>'
        '<a href="/kontakt">Relativ</a>'
    )
    links = scrape_site.collect_links(_soup(html), "https://example.com")
    assert links == ["https://example.com/kontakt"]
