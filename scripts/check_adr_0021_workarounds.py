"""Re-check status of upstream issues that ADR 0021 workarounds depend on.

ADR 0021 documents three temporary patches in
``apps/viewser/lib/stackblitz-files.ts`` that exist solely because
specific upstream Next.js / WebContainer bugs were unfixed at the time:

  1. ``next build --webpack`` flag injection
     (Turbopack incompat with WebContainer WASM environment)
  2. ``app/global-error.tsx`` override injection
     (Next 16 default ``/_global-error`` prerender crashes inside
     WebContainer with ``Invariant: Expected workStore to be initialized``)
  3. ``package-lock.json`` payload inclusion
     (Defensive against npm install resolving different deps in StackBlitz
     than locally)

The ADR's "Omprövning"-section explicitly says:

    När Next.js och WebContainer fungerar stabilt utan dessa workarounds
    ska patchPackageJsonForStackblitz och global-error-injektionen
    reduceras eller tas bort i en separat ändring med verifierad grön
    preview utan specialfall.

This script makes that reminder operational: it queries the GitHub API
for the three referenced upstream issues and prints their current state.
If any have been closed since ADR 0021 was authored (2026-05-15), the
operator should re-test the StackBlitz preview WITHOUT the corresponding
workaround and, if it still works, remove the patch in a dedicated PR.

Usage:

    python scripts/check_adr_0021_workarounds.py
    python scripts/check_adr_0021_workarounds.py --json

Exit codes:

    0 - all referenced issues are still open (workarounds remain
        justified; no action required)
    0 - one or more issues are closed (action recommended; we still
        exit 0 because this is an informational nudge, not a CI gate)
    1 - failed to fetch issue state (network error, GitHub rate-limit,
        or unrecognised reference format)

The script intentionally does NOT require auth or third-party deps; it
uses ``urllib`` against the public GitHub REST API. Unauthenticated
GitHub allows ~60 requests/hour per IP, which is far more than this
script needs (it makes 3 requests per invocation).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ADR_PATH = (
    REPO_ROOT
    / "governance"
    / "decisions"
    / "0021-stackblitz-preview-payload-workarounds.md"
)

# GitHub-issue-referens i ADR:n följer formen
# "[owner/repo#NNN](https://github.com/owner/repo/issues/NNN)" eller bara
# en blank URL i Referenser-sektionen. Vi parsar URL-formen eftersom
# den är entydig (ingen risk för t.ex. ``vercel/next.js#92656`` att
# tolkas som markdown-anchor).
_ISSUE_URL_RE = re.compile(
    r"https://github\.com/(?P<owner>[A-Za-z0-9._-]+)/"
    r"(?P<repo>[A-Za-z0-9._-]+)/issues/(?P<number>\d+)"
)
_ISSUE_API_TEMPLATE = "https://api.github.com/repos/{owner}/{repo}/issues/{number}"
_HTTP_TIMEOUT_SECONDS = 10


@dataclass
class IssueRef:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"

    @property
    def api_url(self) -> str:
        return _ISSUE_API_TEMPLATE.format(
            owner=self.owner, repo=self.repo, number=self.number
        )


@dataclass
class IssueStatus:
    ref: IssueRef
    state: str  # "open" / "closed" / "unknown"
    title: str
    closed_at: str | None
    error: str | None = None

    def to_serializable(self) -> dict[str, Any]:
        out = asdict(self)
        out["ref"] = self.ref.slug
        return out


def parse_issue_refs_from_adr() -> list[IssueRef]:
    """Plocka ut alla unika ``github.com/<owner>/<repo>/issues/<n>``-URL:er
    från ADR-filen i den ordning de förekommer. Duplicates filtreras bort
    så samma issue inte fetchas flera gånger även om ADR:n nämner den
    både i kontext-sektionen och i Referenser.
    """
    if not ADR_PATH.exists():
        raise SystemExit(
            f"ADR 0021-filen saknas: {ADR_PATH.relative_to(REPO_ROOT).as_posix()}.\n"
            "Skriptet förlitar sig på ADR-filen som källa-i-sanning för vilka "
            "issues som matchar workarounds. Återskapa ADR:n eller anpassa "
            "scriptet om filen flyttats."
        )
    text = ADR_PATH.read_text(encoding="utf-8")
    seen: set[tuple[str, str, int]] = set()
    refs: list[IssueRef] = []
    for match in _ISSUE_URL_RE.finditer(text):
        key = (
            match.group("owner"),
            match.group("repo"),
            int(match.group("number")),
        )
        if key in seen:
            continue
        seen.add(key)
        refs.append(IssueRef(owner=key[0], repo=key[1], number=key[2]))
    if not refs:
        raise SystemExit(
            "ADR 0021 innehåller inga github.com/.../issues/N-URL:er — antingen "
            "är ADR:n omskriven utan att uppdatera scriptet, eller så har "
            "Referenser-sektionen ändrat format. Inspektera ADR:n och uppdatera "
            "_ISSUE_URL_RE eller listan av refs manuellt."
        )
    return refs


def fetch_issue_status(ref: IssueRef) -> IssueStatus:
    """Hämta ett issue:s state + titel via public GitHub REST."""
    # api.github.com avvisar requests utan User-Agent. Accept-headern
    # följer rekommendationen från GitHub:s REST API-dokumentation.
    request = urllib.request.Request(
        ref.api_url,
        headers={
            "User-Agent": "sajtbyggaren-adr-0021-checker",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 403 är vanligast — rate-limit utan auth. 404 om issue:t flyttats.
        return IssueStatus(
            ref=ref,
            state="unknown",
            title="(could not fetch)",
            closed_at=None,
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except urllib.error.URLError as exc:
        return IssueStatus(
            ref=ref,
            state="unknown",
            title="(could not fetch)",
            closed_at=None,
            error=f"URLError: {exc.reason}",
        )
    except Exception as exc:  # noqa: BLE001 — fångar JSONDecodeError + okända
        return IssueStatus(
            ref=ref,
            state="unknown",
            title="(could not fetch)",
            closed_at=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    state = str(payload.get("state", "unknown")).lower()
    title = str(payload.get("title", "")).strip() or "(no title)"
    closed_at = payload.get("closed_at")
    if closed_at is not None and not isinstance(closed_at, str):
        closed_at = None
    return IssueStatus(
        ref=ref,
        state=state if state in ("open", "closed") else "unknown",
        title=title,
        closed_at=closed_at,
    )


def render_human(statuses: list[IssueStatus]) -> str:
    """Operatörsvänlig text-rapport. Markerar closed-issues så de syns
    direkt i terminalen. Inga ANSI-färger eftersom CI-loggar och
    Windows-terminal hanterar dem inkonsekvent.
    """
    lines: list[str] = []
    lines.append("ADR 0021 — Status på upstream-issues bakom workarounds")
    lines.append("=" * 60)
    for status in statuses:
        bullet = "[?]"
        if status.state == "open":
            bullet = "[ ]"
        elif status.state == "closed":
            bullet = "[X]"
        lines.append(f"{bullet} {status.ref.slug}  state={status.state}")
        lines.append(f"     {status.title}")
        if status.closed_at:
            lines.append(f"     stängd: {status.closed_at}")
        if status.error:
            lines.append(f"     fel: {status.error}")
        lines.append("")

    closed = [s for s in statuses if s.state == "closed"]
    unknown = [s for s in statuses if s.state == "unknown"]
    if closed:
        lines.append("ÅTGÄRD: ett eller flera issues är STÄNGDA.")
        lines.append(
            "Kör en preview WITHOUT motsvarande workaround i "
            "apps/viewser/lib/stackblitz-files.ts och, om embedding "
            "fortfarande funkar, ta bort patchen i en dedikerad PR per "
            "ADR 0021:s 'Omprövning'-sektion."
        )
    elif unknown:
        lines.append(
            "INFO: minst ett issue kunde inte hämtas (rate-limit eller "
            "nätverksfel). Kör om scriptet senare eller kolla manuellt."
        )
    else:
        lines.append(
            "Alla issues är fortfarande öppna — workarounds förblir "
            "berättigade. Inga åtgärder krävs."
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-check upstream-issue-status för ADR 0021-workarounds i "
            "apps/viewser/lib/stackblitz-files.ts. Kör manuellt periodiskt "
            "(t.ex. en gång i månaden) för att se om någon upstream-fix "
            "har landat så patcharna kan reduceras."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Skriv ut maskinläsbar JSON istället för human-readable text.",
    )
    args = parser.parse_args()

    try:
        refs = parse_issue_refs_from_adr()
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    statuses = [fetch_issue_status(ref) for ref in refs]

    if args.json:
        print(
            json.dumps(
                {"statuses": [s.to_serializable() for s in statuses]},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(render_human(statuses))

    # Returnera 1 BARA om vi inte kunde hämta något alls (annars är
    # closed/open ett informational-utfall, inte ett fel).
    if all(s.state == "unknown" for s in statuses):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
