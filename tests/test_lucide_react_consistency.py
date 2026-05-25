"""lucide-react cross-package version consistency.

`scripts/build_site.py:write_pages` (`render_home`, `render_about`,
`render_contact`, `render_layout`, `render_products`) emits
`import { ... } from "lucide-react"` into every generated customer
site. The version that ends up resolving in `node_modules/lucide-react`
is determined by the starter's `package.json` (since builder copies
the starter wholesale into `.generated/<siteId>/`). If the starters
drift to different lucide-react majors, the same generated code path
can produce different runtime behaviour per scaffold — and worse, if
one starter's version removes an icon that `write_pages` hardcodes
(brand icons like the github / slack / twitter exports were the
trigger in sajtmaskins fall), every site built on that starter
starts failing `next build` with `Module not found` or
`Cannot find name <Icon>`.

The predecessor app (`sajtmaskin`) hit exactly this on every dependabot
production-bump after lucide-react removed brand icons — see B145 in
docs/known-issues.md plus ADR 0020 ("commerce-base: lägg till
lucide-react som runtime-dep") which already flagged the underlying
debt: `scripts/build_site.py:write_pages` is icon-library-coupled and
the starters must therefore agree on the lucide version.

This test is the cross-policy guard that schema validation alone cannot
catch: it verifies all five `package.json` files (apps/viewser plus the
four starters) declare the same `lucide-react` version specifier. It
does NOT pin the version to an exact value — that requires an ADR per
the starter doctrine in `data/starters/README.md` ("nya deps i en
starter kräver operatörsgodkännande"). It only locks consistency.

When this test fails, the fix is one of:

  1. Bring all five `package.json` files back in sync at the same
     `lucide-react` version (preferred when the change was unintended
     drift from a single dependabot bump).
  2. If the divergence is intentional (e.g. one starter migrated to a
     dedicated brand-icon library), add an ADR that documents the
     reason and update this test to expect the documented split.
  3. If lucide-react is being removed entirely from a starter as part
     of the architectural debt cleanup (ADR 0020 "väg B"), update both
     this test and `scripts/build_site.py:write_pages` together so the
     icon emission is starter-aware.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Alla `package.json` som måste hålla samma `lucide-react`-version.
# Listan är hardcoded snarare än glob-baserad eftersom: (a) glob skulle
# råka inkludera framtida `package.json` som inte hör till detta
# konsistens-spår (t.ex. en framtida `apps/backoffice-web/`), och (b)
# en explicit lista signalerar att beslutet att inkludera en `package.json`
# är medvetet — om en ny starter eller app läggs till och den ska
# omfattas av samma kontrakt, lägg den i listan medvetet.
PACKAGE_JSONS_REQUIRING_LUCIDE_CONSISTENCY: list[Path] = [
    REPO_ROOT / "apps" / "viewser" / "package.json",
    REPO_ROOT / "data" / "starters" / "marketing-base" / "package.json",
    REPO_ROOT / "data" / "starters" / "commerce-base" / "package.json",
    REPO_ROOT / "data" / "starters" / "portfolio-base" / "package.json",
    REPO_ROOT / "data" / "starters" / "docs-base" / "package.json",
]


def _load_lucide_version(package_json_path: Path) -> str:
    """Returnera `dependencies.lucide-react`-strängen från en
    `package.json`. Failar testet med en tydlig assertion-rad om filen
    saknas eller om dep:en inte är deklarerad — den måste finnas i
    alla fem filer för att kontraktet ska vara meningsfullt.
    """
    assert package_json_path.exists(), (
        f"package.json saknas: {package_json_path.relative_to(REPO_ROOT).as_posix()}. "
        f"Antingen är listan PACKAGE_JSONS_REQUIRING_LUCIDE_CONSISTENCY i "
        f"tests/test_lucide_react_consistency.py föråldrad (filen flyttad/borttagen) "
        f"eller så är det en regression."
    )
    payload = json.loads(package_json_path.read_text(encoding="utf-8"))
    deps = payload.get("dependencies", {})
    assert isinstance(deps, dict), (
        f"{package_json_path.relative_to(REPO_ROOT).as_posix()} saknar "
        f"`dependencies`-block (eller har det som non-object)."
    )
    version = deps.get("lucide-react")
    assert version is not None, (
        f"{package_json_path.relative_to(REPO_ROOT).as_posix()} saknar "
        f"`dependencies.lucide-react`. Builder hardcodar lucide-imports i "
        f"genererade sajter, så denna dep krävs för att `next build` mot "
        f"den genererade sajten ska gå grön. Kontext: ADR 0020."
    )
    assert isinstance(version, str), (
        f"{package_json_path.relative_to(REPO_ROOT).as_posix()} har "
        f"`dependencies.lucide-react` som icke-sträng: {version!r}."
    )
    return version


@pytest.mark.governance
def test_lucide_react_version_consistent_across_packages() -> None:
    """Alla fem `package.json` (apps/viewser + 4 starters) MÅSTE deklarera
    samma `lucide-react`-version. Driftar skadar builder-genererade
    sajter genom att producera olika runtime-beteende per scaffold och
    riskerar `Module not found` / `Cannot find name <Icon>` om en starter
    råkar bumpa förbi den version som tar bort en hårdkodad ikon.
    """
    versions: dict[str, str] = {}
    for package_json in PACKAGE_JSONS_REQUIRING_LUCIDE_CONSISTENCY:
        rel = package_json.relative_to(REPO_ROOT).as_posix()
        versions[rel] = _load_lucide_version(package_json)

    distinct = set(versions.values())
    assert len(distinct) == 1, (
        "lucide-react-versionerna i kontrakts-package.json:erna driftar "
        "ifrån varandra. När builder genererar en kund-sajt kopieras "
        "starterns package.json wholesale, så olika starters → olika "
        "lucide-react-versioner → olika ikon-API:er = potentiellt "
        "trasig `next build` per scaffold.\n\n"
        "Aktuella versioner:\n"
        + "\n".join(f"  {path}: {ver}" for path, ver in sorted(versions.items()))
        + "\n\nFix: bring back to one version (preferred) eller ADR + "
        "uppdatera detta test om split:en är medveten. Se ADR 0020 + "
        "B145 i docs/known-issues.md för bakgrund."
    )


@pytest.mark.governance
def test_lucide_react_specifier_uses_caret_or_exact() -> None:
    """Defensiv guard: lucide-react-specifiern ska vara antingen exakt
    (`1.14.0`) eller caret-baserad (`^1.14.0`). Ingen tilde, ingen
    range, ingen `*`/`latest` — vi vill att npm install resolverar
    deterministiskt och att uppgraderingar kommer via en explicit
    edit av filerna (eller via dependabot, som bumpar caret-pinnar
    inom samma major). Range-specifiers skulle kunna lösa olika
    minor:s mellan operatörens lokala lockfile och CI:s lockfile,
    vilket är samma sorts split som test_lucide_react_version_
    consistent_across_packages skyddar mot.
    """
    import re

    pattern = re.compile(r"^(?:\^?\d+\.\d+\.\d+|\d+\.\d+\.\d+)$")
    failures: list[tuple[str, str]] = []
    for package_json in PACKAGE_JSONS_REQUIRING_LUCIDE_CONSISTENCY:
        rel = package_json.relative_to(REPO_ROOT).as_posix()
        version = _load_lucide_version(package_json)
        if not pattern.match(version):
            failures.append((rel, version))

    assert not failures, (
        "lucide-react-specifier matchar inte `^X.Y.Z` eller `X.Y.Z`:\n"
        + "\n".join(f"  {path}: {ver!r}" for path, ver in failures)
        + "\n\nUndvik tilde-, range- och tag-pinnar för denna dep eftersom "
        "builder kopierar starter wholesale till genererad sajt; vi vill "
        "att npm install resolverar samma version varje gång."
    )
