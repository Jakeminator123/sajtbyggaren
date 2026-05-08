"""Deterministic Builder MVP for Sajtbyggaren.

Reads a Project Input, a Scaffold and a Variant from the repository, writes
canonical Engine Run artifacts under `data/runs/<runId>/`, and produces a
runnable Next.js project under `.generated/<siteId>/` by copying the
`marketing-base` Starter and patching it with the project input's content and
the variant's tokens.

By default the builder also runs `npm install` (when `node_modules` is
missing) and `npm run build`. Pass `--skip-build` to skip those steps during
fast dev iteration.

This is the minimal happy path described in `docs/migration-plan.md` Sprint 2
and `docs/architecture/builder-mvp.md`. It deliberately does not call any
LLM, does not implement Repair Pipeline or Quality Gate, and does not do
follow-up.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTERS_DIR = REPO_ROOT / "data" / "starters"
SCAFFOLDS_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
)
DOSSIERS_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "dossiers"
)
GENERATED_DIR = REPO_ROOT / ".generated"
RUNS_DIR = REPO_ROOT / "data" / "runs"

# Files the builder must NEVER write under any siteId. Case-insensitive.
# `.env.example` is allowed (canonical placeholder).
_FORBIDDEN_ENV_PATTERN = re.compile(r"^\.env(\..+)?$", flags=re.IGNORECASE)
_ALLOWED_ENV_NAMES = {".env.example"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def make_run_id(site_id: str) -> str:
    """Sortable, readable run id with millisecond precision and a uuid suffix.

    Example: ``20260507T143000.123Z-ab12cd34-painter-palma``. The uuid suffix
    eliminates the race window where two regenerations within the same
    millisecond could reuse a run directory and truncate each other's
    ``trace.ndjson``.
    """
    now = utc_now()
    stamp = now.strftime("%Y%m%dT%H%M%S")
    millis = f"{now.microsecond // 1000:03d}"
    short = uuid.uuid4().hex[:8]
    return f"{stamp}.{millis}Z-{short}-{site_id}"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def assert_not_env_secret(path: Path) -> None:
    """Refuse to touch real .env files (case-insensitive). .env.example is OK."""
    name = path.name
    if name in _ALLOWED_ENV_NAMES:
        return
    if _FORBIDDEN_ENV_PATTERN.match(name):
        raise AssertionError(
            f"Builder must not write secret env files (attempted: {path}). "
            "Hard Dossiers handle their own env contracts via env-contract.json."
        )


def write(path: Path, contents: str) -> None:
    """Write text to disk through the central guard. Use for ALL file writes.

    This is the single chokepoint that enforces the env-secret block.
    Helpers that previously called ``Path.write_text`` directly must go via
    this function instead so the guard cannot be bypassed.
    """
    assert_not_env_secret(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(contents)


def write_json(path: Path, data: Any) -> None:
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Trace (append-only Engine Events)
# ---------------------------------------------------------------------------


class Trace:
    """Append-only Engine Event log per `engine-run.v1.json:trace`."""

    def __init__(self, run_id: str, run_dir: Path) -> None:
        self.run_id = run_id
        self.path = run_dir / "trace.ndjson"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Initialize empty file so the trace is canonical for this run.
        with self.path.open("w", encoding="utf-8", newline="\n"):
            pass

    def event(
        self,
        phase: str,
        event: str,
        status: str,
        message: str = "",
        payload_path: str | None = None,
    ) -> None:
        record = {
            "runId": self.run_id,
            "phase": phase,
            "event": event,
            "status": status,
            "message": message,
            "timestamp": utc_now().isoformat(),
            "payloadPath": payload_path,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Starter copy and patch helpers
# ---------------------------------------------------------------------------


def _ignore_secret_envs(_dir: str, names: list[str]) -> list[str]:
    """shutil.copytree ignore-callback that drops any real .env file.

    `.env.example` is preserved (canonical placeholder). Combined with the
    pattern-based ignore list this guarantees that a starter that accidentally
    contains a real `.env` or `.env.local` cannot leak into a generated site.
    """
    drop: list[str] = []
    for name in names:
        if name in _ALLOWED_ENV_NAMES:
            continue
        if _FORBIDDEN_ENV_PATTERN.match(name):
            drop.append(name)
    return drop


def _ignore_combined(dir_path: str, names: list[str]) -> set[str]:
    base_ignore = shutil.ignore_patterns(
        "node_modules",
        ".next",
        "out",
        "*.tsbuildinfo",
        "next-env.d.ts",
    )(dir_path, names)
    secret_ignore = set(_ignore_secret_envs(dir_path, names))
    return set(base_ignore) | secret_ignore


def copy_starter(starter_id: str, target: Path) -> None:
    source = STARTERS_DIR / starter_id
    if not source.exists():
        raise SystemExit(
            f"Starter '{starter_id}' missing at {source}. "
            "Run the starter setup before building."
        )
    # Preserve existing target's node_modules / .next so we do not force a
    # fresh `npm install` on every regeneration.
    preserved = {"node_modules", ".next"}
    if target.exists():
        for entry in target.iterdir():
            if entry.name in preserved:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        shutil.copytree(source, target, ignore=_ignore_combined, dirs_exist_ok=True)
    else:
        shutil.copytree(source, target, ignore=_ignore_combined)


def variant_css(variant: dict) -> str:
    tokens = variant["tokens"]
    color = tokens["color"]
    radius = tokens["radius"]
    spacing = tokens["spacing"]
    return (
        ":root {\n"
        f"  --background: {color['background']};\n"
        f"  --foreground: {color['foreground']};\n"
        f"  --muted: {color['muted']};\n"
        f"  --border: {color['border']};\n"
        f"  --primary: {color['primary']};\n"
        f"  --primary-foreground: {color['primaryForeground']};\n"
        f"  --accent: {color['accent']};\n"
        f"  --accent-foreground: {color['accentForeground']};\n"
        f"  --radius-sm: {radius['sm']};\n"
        f"  --radius-md: {radius['md']};\n"
        f"  --radius-lg: {radius['lg']};\n"
        f"  --section-spacing: {spacing['section']};\n"
        f"  --container-width: {spacing['container']};\n"
        "}\n"
    )


def patch_globals_css(target: Path, variant: dict) -> None:
    css = target / "app" / "globals.css"
    original = css.read_text(encoding="utf-8")
    block = variant_css(variant)
    marker = "/* sajtbyggaren-variant-tokens:start */"
    end = "/* sajtbyggaren-variant-tokens:end */"
    if marker in original:
        before, _, rest = original.partition(marker)
        _, _, after = rest.partition(end)
        new_contents = f"{before}{marker}\n{block}{end}{after}"
    else:
        new_contents = (
            f"{marker}\n{block}{end}\n\n{original}"
        )
    write(css, new_contents)


def patch_layout(
    target: Path,
    site_title: str,
    site_description: str,
) -> None:
    layout = target / "app" / "layout.tsx"
    text = layout.read_text(encoding="utf-8")
    title_escaped = site_title.replace('"', '\\"')
    desc_escaped = site_description.replace('"', '\\"')
    text = text.replace(
        'title: "",',
        f'title: "{title_escaped}",',
    )
    text = text.replace(
        'description: "",',
        f'description: "{desc_escaped}",',
    )
    text = text.replace('lang="en"', 'lang="sv"')
    write(layout, text)


def patch_package_json(target: Path, dossier: dict) -> None:
    pkg_path = target / "package.json"
    pkg = load_json(pkg_path)
    pkg["name"] = dossier["siteId"]
    write(pkg_path, json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Page renderers (kept identical to v1 - just JSX templates with dossier copy)
# ---------------------------------------------------------------------------


def render_home(dossier: dict) -> str:
    company = dossier["company"]
    location = dossier["location"]
    services = dossier["services"]
    trust = dossier["trustSignals"]
    contact = dossier["contact"]
    services_grid = "\n".join(
        f"            <li key=\"{svc['id']}\" className=\"rounded-md border p-5\">\n"
        f"              <h3 className=\"text-lg font-semibold\">{svc['label']}</h3>\n"
        f"              <p className=\"mt-2 text-sm text-[color:var(--muted)]\">{svc['summary']}</p>\n"
        f"            </li>"
        for svc in services
    )
    trust_items = "\n".join(
        f"            <li key=\"trust-{i}\" className=\"flex gap-3\">\n"
        f"              <span className=\"mt-1 inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--accent)]\" />\n"
        f"              <span>{item}</span>\n"
        f"            </li>"
        for i, item in enumerate(trust)
    )
    return (
        "export default function Home() {\n"
        "  return (\n"
        "    <main className=\"flex flex-1 flex-col\">\n"
        "      <section className=\"bg-[color:var(--background)] text-[color:var(--foreground)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]\">\n"
        f"          <p className=\"text-sm uppercase tracking-widest text-[color:var(--muted)]\">{location['city']}</p>\n"
        f"          <h1 className=\"max-w-2xl text-4xl font-semibold leading-tight md:text-5xl\">{company['name']}</h1>\n"
        f"          <p className=\"max-w-2xl text-lg text-[color:var(--muted)]\">{company['tagline']}</p>\n"
        "          <div className=\"flex flex-wrap gap-3\">\n"
        f"            <a href=\"/kontakt\" className=\"rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)]\">Begär offert</a>\n"
        f"            <a href=\"tel:{contact['phone'].replace(' ', '')}\" className=\"rounded-md border px-5 py-3 text-sm font-medium\">Ring {contact['phone']}</a>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
        "      <section className=\"border-t bg-[color:var(--background)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]\">\n"
        "          <div className=\"flex flex-col gap-2\">\n"
        "            <h2 className=\"text-2xl font-semibold\">Tjänster</h2>\n"
        "            <p className=\"max-w-2xl text-[color:var(--muted)]\">Vi tar oss tid med ytan och lämnar inget halvfärdigt.</p>\n"
        "          </div>\n"
        "          <ul className=\"grid gap-4 md:grid-cols-2\">\n"
        f"{services_grid}\n"
        "          </ul>\n"
        "          <a href=\"/tjanster\" className=\"text-sm font-medium underline\">Se alla tjänster</a>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
        "      <section className=\"border-t bg-[color:var(--background)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]\">\n"
        "          <h2 className=\"text-2xl font-semibold\">Varför oss</h2>\n"
        "          <ul className=\"flex flex-col gap-3 text-base\">\n"
        f"{trust_items}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
        "      <section className=\"border-t bg-[color:var(--primary)] text-[color:var(--primary-foreground)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]\">\n"
        "          <h2 className=\"text-2xl font-semibold\">Få en offert utan kostnad</h2>\n"
        "          <p className=\"max-w-2xl opacity-90\">Beskriv jobbet så hör vi av oss inom en arbetsdag.</p>\n"
        "          <a href=\"/kontakt\" className=\"w-fit rounded-md bg-[color:var(--primary-foreground)] px-5 py-3 text-sm font-medium text-[color:var(--primary)]\">Kontakta oss</a>\n"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_services(dossier: dict) -> str:
    services = dossier["services"]
    items = "\n".join(
        f"          <article key=\"{svc['id']}\" className=\"rounded-md border p-6\">\n"
        f"            <h2 className=\"text-xl font-semibold\">{svc['label']}</h2>\n"
        f"            <p className=\"mt-3 text-[color:var(--muted)]\">{svc['summary']}</p>\n"
        f"          </article>"
        for svc in services
    )
    return (
        "export default function ServicesPage() {\n"
        "  return (\n"
        "    <main className=\"flex flex-1 flex-col\">\n"
        "      <section className=\"bg-[color:var(--background)] text-[color:var(--foreground)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]\">\n"
        "          <header className=\"flex flex-col gap-3\">\n"
        "            <p className=\"text-sm uppercase tracking-widest text-[color:var(--muted)]\">Tjänster</p>\n"
        "            <h1 className=\"text-3xl font-semibold md:text-4xl\">Vad vi gör</h1>\n"
        "            <p className=\"max-w-2xl text-[color:var(--muted)]\">Vi arbetar med inomhus- och fasadmåleri samt färgsättning. Här är vad vi tar oss an.</p>\n"
        "          </header>\n"
        "          <div className=\"grid gap-4 md:grid-cols-2\">\n"
        f"{items}\n"
        "          </div>\n"
        "          <a href=\"/kontakt\" className=\"w-fit rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)]\">Begär offert</a>\n"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_about(dossier: dict) -> str:
    company = dossier["company"]
    team = company.get("team", [])
    location = dossier["location"]
    areas_html = ", ".join(location["serviceAreas"])
    team_items = "\n".join(
        f"            <li key=\"{member['name']}\" className=\"rounded-md border p-5\">\n"
        f"              <p className=\"text-base font-semibold\">{member['name']}</p>\n"
        f"              <p className=\"mt-1 text-sm text-[color:var(--muted)]\">{member['role']}</p>\n"
        f"            </li>"
        for member in team
    )
    return (
        "export default function AboutPage() {\n"
        "  return (\n"
        "    <main className=\"flex flex-1 flex-col\">\n"
        "      <section className=\"bg-[color:var(--background)] text-[color:var(--foreground)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]\">\n"
        "          <header className=\"flex flex-col gap-3\">\n"
        "            <p className=\"text-sm uppercase tracking-widest text-[color:var(--muted)]\">Om oss</p>\n"
        f"            <h1 className=\"text-3xl font-semibold md:text-4xl\">{company['name']}</h1>\n"
        "          </header>\n"
        f"          <p className=\"max-w-2xl text-base text-[color:var(--muted)]\">{company['story']}</p>\n"
        "          <div className=\"flex flex-col gap-4\">\n"
        "            <h2 className=\"text-xl font-semibold\">Teamet</h2>\n"
        "            <ul className=\"grid gap-3 md:grid-cols-2\">\n"
        f"{team_items}\n"
        "            </ul>\n"
        "          </div>\n"
        "          <div className=\"flex flex-col gap-2\">\n"
        "            <h2 className=\"text-xl font-semibold\">Områden vi arbetar i</h2>\n"
        f"            <p className=\"text-[color:var(--muted)]\">{areas_html}</p>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_contact(dossier: dict) -> str:
    contact = dossier["contact"]
    address_lines = "\n".join(
        f"                <span className=\"block\">{line}</span>"
        for line in contact["addressLines"]
    )
    return (
        "export default function ContactPage() {\n"
        "  return (\n"
        "    <main className=\"flex flex-1 flex-col\">\n"
        "      <section className=\"bg-[color:var(--background)] text-[color:var(--foreground)]\">\n"
        "        <div className=\"mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]\">\n"
        "          <header className=\"flex flex-col gap-3\">\n"
        "            <p className=\"text-sm uppercase tracking-widest text-[color:var(--muted)]\">Kontakt</p>\n"
        "            <h1 className=\"text-3xl font-semibold md:text-4xl\">Hör av dig</h1>\n"
        "            <p className=\"max-w-2xl text-[color:var(--muted)]\">Beskriv jobbet kort så återkommer vi inom en arbetsdag med tider och offert.</p>\n"
        "          </header>\n"
        "          <div className=\"grid gap-4 md:grid-cols-2\">\n"
        "            <article className=\"rounded-md border p-6\">\n"
        "              <h2 className=\"text-base font-semibold\">Telefon</h2>\n"
        f"              <a href=\"tel:{contact['phone'].replace(' ', '')}\" className=\"mt-2 block text-lg\">{contact['phone']}</a>\n"
        f"              <p className=\"mt-1 text-sm text-[color:var(--muted)]\">{contact['openingHours']}</p>\n"
        "            </article>\n"
        "            <article className=\"rounded-md border p-6\">\n"
        "              <h2 className=\"text-base font-semibold\">E-post</h2>\n"
        f"              <a href=\"mailto:{contact['email']}\" className=\"mt-2 block text-lg\">{contact['email']}</a>\n"
        "            </article>\n"
        "            <article className=\"rounded-md border p-6 md:col-span-2\">\n"
        "              <h2 className=\"text-base font-semibold\">Adress</h2>\n"
        "              <address className=\"mt-2 not-italic\">\n"
        f"{address_lines}\n"
        "              </address>\n"
        "            </article>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def write_pages(target: Path, dossier: dict) -> None:
    write(target / "app" / "page.tsx", render_home(dossier))
    write(target / "app" / "tjanster" / "page.tsx", render_services(dossier))
    write(target / "app" / "om-oss" / "page.tsx", render_about(dossier))
    write(target / "app" / "kontakt" / "page.tsx", render_contact(dossier))


def selected_required_dossiers(project_input: dict) -> list[str]:
    selected = project_input.get("selectedDossiers", {})
    required = selected.get("required", [])
    if not isinstance(required, list):
        return []
    return [item for item in required if isinstance(item, str) and item.strip()]


def resolve_dossier_dir(dossier_id: str) -> tuple[str, Path]:
    for dossier_class in ("soft", "hard"):
        path = DOSSIERS_DIR / dossier_class / dossier_id
        if path.exists():
            return dossier_class, path
    raise SystemExit(
        f"Selected dossier '{dossier_id}' not found under {DOSSIERS_DIR}/soft or /hard."
    )


def load_selected_dossier_manifests(project_input: dict) -> list[dict]:
    manifests: list[dict] = []
    for dossier_id in selected_required_dossiers(project_input):
        dossier_class, dossier_dir = resolve_dossier_dir(dossier_id)
        manifest_path = dossier_dir / "manifest.json"
        if not manifest_path.exists():
            raise SystemExit(f"Dossier '{dossier_id}' missing manifest.json at {manifest_path}")
        manifest = load_json(manifest_path)
        if manifest.get("id") != dossier_id:
            raise SystemExit(
                f"Dossier manifest id mismatch for {manifest_path}: expected '{dossier_id}', got '{manifest.get('id')}'"
            )
        if manifest.get("class") != dossier_class:
            raise SystemExit(
                f"Dossier manifest class mismatch for {manifest_path}: expected '{dossier_class}', got '{manifest.get('class')}'"
            )
        manifests.append(
            {
                "id": dossier_id,
                "class": dossier_class,
                "dir": dossier_dir,
                "manifest": manifest,
            }
        )
    return manifests


def mount_dossier_components(target: Path, selected_dossiers: list[dict]) -> list[str]:
    copied: list[str] = []
    components_target = target / "components"
    for info in selected_dossiers:
        components_dir = info["dir"] / "components"
        if not components_dir.exists():
            continue
        for source in sorted(components_dir.glob("*.tsx")):
            destination = components_target / source.name
            write(destination, source.read_text(encoding="utf-8"))
            copied.append(source.name)
    return copied


def write_dossier_routes(target: Path, selected_dossiers: list[dict]) -> list[str]:
    routes: list[str] = []
    selected_ids = {info["id"] for info in selected_dossiers}

    if "interactive-game-loop" in selected_ids:
        write(
            target / "app" / "spel" / "page.tsx",
            (
                'import { PacmanGame } from "@/components/pacman-game";\n\n'
                "export default function Page() {\n"
                "  return (\n"
                '    <main className="mx-auto w-[min(100%,72rem)] px-4 py-10">\n'
                '      <h1 className="mb-3 text-3xl font-semibold">Pacman-spel</h1>\n'
                '      <p className="mb-6 text-sm text-[color:var(--muted)]">Tryck pilarna for att styra och R for att starta om.</p>\n'
                "      <PacmanGame />\n"
                "    </main>\n"
                "  );\n"
                "}\n"
            ),
        )
        routes.append("/spel")

    return routes


# ---------------------------------------------------------------------------
# Route guards
# ---------------------------------------------------------------------------


def required_routes(scaffold_routes: dict) -> list[str]:
    return [
        r["path"]
        for r in scaffold_routes["defaultRoutes"]
        if r.get("required")
    ]


def all_default_routes(scaffold_routes: dict) -> list[str]:
    return [r["path"] for r in scaffold_routes["defaultRoutes"]]


def route_to_page_path(target: Path, route: str) -> Path:
    if route == "/":
        return target / "app" / "page.tsx"
    return target / "app" / route.lstrip("/") / "page.tsx"


# Detects "export default function|const|class ..." or "export { default }"
_DEFAULT_EXPORT_RE = re.compile(
    r"export\s+default\s+(?:async\s+)?(?:function|class|const|let|var|\w+)"
    r"|export\s*\{\s*default\b",
    flags=re.MULTILINE,
)


def assert_routes_present(target: Path, routes: list[str]) -> None:
    """Hard guard: every route must exist as a page.tsx with a default export.

    Checks both file existence AND that the file declares a default export so
    Next.js can mount the route. This catches the common error where a renderer
    template wrote an empty file or a file that was patched without exporting
    a component.
    """
    missing: list[str] = []
    no_export: list[str] = []
    for route in routes:
        path = route_to_page_path(target, route)
        if not path.exists():
            missing.append(f"{route} -> {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            missing.append(f"{route} -> unreadable ({exc})")
            continue
        if not _DEFAULT_EXPORT_RE.search(text):
            no_export.append(f"{route} -> {path} has no default export")

    problems: list[str] = []
    if missing:
        problems.append("missing route files:\n  " + "\n  ".join(missing))
    if no_export:
        problems.append("routes without default export:\n  " + "\n  ".join(no_export))
    if problems:
        raise SystemExit("Builder failed: " + "; ".join(problems))


# ---------------------------------------------------------------------------
# npm runner
# ---------------------------------------------------------------------------


def run_npm(command: list[str], cwd: Path) -> tuple[bool, float, str]:
    """Run an npm command and return (ok, seconds, last_lines).

    Uses shell=True on Windows so npm.cmd is found via PATHEXT.
    """
    start = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    elapsed = time.monotonic() - start
    output = (proc.stdout or "") + (proc.stderr or "")
    last_lines = "\n".join(output.splitlines()[-25:])
    return proc.returncode == 0, elapsed, last_lines


# ---------------------------------------------------------------------------
# Mock artefacts (no LLM yet)
# ---------------------------------------------------------------------------


def build_site_brief_mock(dossier: dict, scaffold: dict) -> dict:
    """Mock Site Brief derived from the dossier (no LLM)."""
    return {
        "briefSource": "mock-no-key",
        "modelUsed": "mock",
        "language": dossier["language"],
        "businessType": dossier["company"]["businessType"],
        "companyName": dossier["company"]["name"],
        "tagline": dossier["company"]["tagline"],
        "location": dossier["location"],
        "tone": dossier["tone"],
        "trustSignals": dossier["trustSignals"],
        "conversionGoals": dossier["conversionGoals"],
        "requestedCapabilities": dossier.get("requestedCapabilities")
        or [svc["id"] for svc in dossier["services"]],
        "scaffoldHint": scaffold["id"],
    }


def build_site_plan_mock(
    dossier: dict, scaffold: dict, scaffold_routes: dict, variant: dict
) -> dict:
    """Mock Site Plan derived from scaffold + variant + dossier (no LLM)."""
    return {
        "scaffoldId": scaffold["id"],
        "scaffoldVersion": scaffold["version"],
        "variantId": variant["id"],
        "starterId": "marketing-base",
        "routes": [
            {"path": r["path"], "id": r["id"], "purpose": r["purpose"]}
            for r in scaffold_routes["defaultRoutes"]
        ],
        "selectedDossiers": dossier.get("selectedDossiers", {}),
        "buildSpec": {
            "qualityTarget": 9.0,
            "verificationPolicy": "build-must-pass",
            "previewRuntime": "stackblitz",
        },
    }


def build_generation_package(
    dossier: dict,
    scaffold: dict,
    variant: dict,
) -> dict:
    """Generation Package - the only payload that would go to codegen-LLM."""
    return {
        "policyVersions": {
            "engineRun": "engine-run.v1",
            "namingDictionary": "naming-dictionary.v1",
            "scaffoldContract": "scaffold-contract.v1",
        },
        "siteBriefRef": "site-brief.json",
        "sitePlanRef": "site-plan.json",
        "scaffoldId": scaffold["id"],
        "variantId": variant["id"],
        "starterId": "marketing-base",
        "language": dossier["language"],
        "engineMode": "init",
    }


# ---------------------------------------------------------------------------
# Engine Run artefakts
# ---------------------------------------------------------------------------


def write_phase1_understand(
    run_dir: Path,
    trace: Trace,
    dossier_path: Path,
    dossier: dict,
    scaffold: dict,
) -> dict:
    """Phase 1 understand: input.json + site-brief.json."""
    trace.event("understand", "phase.started", "started", "Phase 1 understand starts")

    rel_dossier = (
        str(dossier_path.relative_to(REPO_ROOT)).replace("\\", "/")
    )
    input_data = {
        "runId": trace.run_id,
        "mode": "init",
        "rawPrompt": None,
        "dossierPath": rel_dossier,
        "detectedLanguage": dossier["language"],
        "timestamp": utc_now().isoformat(),
    }
    write_json(run_dir / "input.json", input_data)
    trace.event(
        "understand", "input.written", "done",
        "Captured dossier path and runId",
        payload_path="input.json",
    )

    brief = build_site_brief_mock(dossier, scaffold)
    write_json(run_dir / "site-brief.json", brief)
    trace.event(
        "understand", "site_brief.written", "done",
        "Mock Site Brief derived from dossier (briefSource=mock-no-key)",
        payload_path="site-brief.json",
    )
    trace.event("understand", "phase.completed", "done", "Phase 1 understand done")
    return brief


def write_phase2_plan(
    run_dir: Path,
    trace: Trace,
    dossier: dict,
    scaffold: dict,
    scaffold_routes: dict,
    variant: dict,
) -> tuple[dict, dict]:
    """Phase 2 plan: site-plan.json + generation-package.json."""
    trace.event("plan", "phase.started", "started", "Phase 2 plan starts")

    site_plan = build_site_plan_mock(
        dossier, scaffold, scaffold_routes, variant
    )
    write_json(run_dir / "site-plan.json", site_plan)
    trace.event(
        "plan", "site_plan.written", "done",
        f"Site Plan picked scaffold={scaffold['id']} variant={variant['id']}",
        payload_path="site-plan.json",
    )

    package = build_generation_package(dossier, scaffold, variant)
    write_json(run_dir / "generation-package.json", package)
    trace.event(
        "plan", "generation_package.written", "done",
        "Generation Package composed",
        payload_path="generation-package.json",
    )
    trace.event("plan", "phase.completed", "done", "Phase 2 plan done")
    return site_plan, package


def snapshot_generated_files(target_dir: Path, run_dir: Path) -> Path:
    """Snapshot generated files into ``data/runs/<runId>/generated-files/``.

    The dev preview at ``.generated/<siteId>/`` keeps mutating across runs
    (regenerations, npm install, build cache). The Engine Run contract in
    ``engine-run.v1.json`` says the canonical Generated Files belong under
    the run directory. We snapshot the source-relevant files only and skip
    ``node_modules`` and build output for size reasons.
    """
    snap_dir = run_dir / "generated-files"
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
    shutil.copytree(target_dir, snap_dir, ignore=_ignore_combined)
    return snap_dir


def write_repair_result_skeleton(run_dir: Path) -> dict:
    """Skeleton repair-result.json. Repair Pipeline is not implemented yet.

    Status ``not-run`` makes it impossible to confuse this with an actual
    repair attempt.
    """
    payload = {
        "status": "not-run",
        "reason": "Repair Pipeline is not implemented in Builder MVP yet.",
        "mechanicalFixesApplied": [],
        "llmFixesApplied": [],
        "remainingErrors": [],
    }
    write_json(run_dir / "repair-result.json", payload)
    return payload


def write_quality_result_skeleton(run_dir: Path) -> dict:
    """Skeleton quality-result.json. Quality Gate is not implemented yet."""
    payload = {
        "status": "not-run",
        "reason": "Quality Gate is not implemented in Builder MVP yet.",
        "checks": {
            "typecheck": "skipped",
            "build": "delegated-to-build-result",
            "route-scan": "delegated-to-build-result",
            "policy-compliance": "skipped",
        },
        "scorecard": None,
    }
    write_json(run_dir / "quality-result.json", payload)
    return payload


def empty_model_usage() -> dict:
    """Zeroed token / cost spend. Replace with real numbers when LLM is wired in."""
    return {
        "byRole": {},
        "totalInputTokens": 0,
        "totalOutputTokens": 0,
        "totalCostUsd": 0.0,
        "currency": "USD",
        "source": "mock-no-key",
    }


def write_build_result(
    run_dir: Path,
    trace: Trace,
    dossier: dict,
    scaffold: dict,
    variant: dict,
    routes: list[str],
    npm_steps: list[dict],
    overall_status: str,
    target_dir: Path,
    duration_ms: int,
) -> dict:
    """Write build-result.json. ``generatedFilesDir`` points at the canonical
    snapshot under the run directory, not at the dev preview, so downstream
    consumers (Backoffice, eval batch) can trust it across regenerations.
    """
    snap_dir = run_dir / "generated-files"
    rel_snapshot = str(snap_dir.relative_to(REPO_ROOT)).replace("\\", "/")
    rel_preview = str(target_dir.relative_to(REPO_ROOT)).replace("\\", "/")
    result = {
        "siteId": dossier["siteId"],
        "starterId": "marketing-base",
        "scaffoldId": scaffold["id"],
        "scaffoldVersion": scaffold["version"],
        "variantId": variant["id"],
        "language": dossier["language"],
        "engineMode": "init",
        "buildSource": "scripts/build_site.py",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "routes": routes,
        "generatedFilesDir": rel_snapshot,
        "devPreviewDir": rel_preview,
        "npmSteps": npm_steps,
        "modelUsage": empty_model_usage(),
        "finalize": {
            "snapshotDir": rel_snapshot,
            "snapshotedAt": utc_now().isoformat(),
        },
        "status": overall_status,
        "runDurationMs": duration_ms,
    }
    write_json(run_dir / "build-result.json", result)
    trace.event(
        "build", "build.result.written", "done",
        f"Build result status={overall_status}",
        payload_path="build-result.json",
    )
    return result


# ---------------------------------------------------------------------------
# Main build orchestration
# ---------------------------------------------------------------------------


def build(
    dossier_path: Path,
    do_build: bool = True,
) -> tuple[Path, Path]:
    """Generate a site and Engine Run artefakts. Returns (target, run_dir)."""
    started = time.monotonic()

    dossier = load_json(dossier_path)
    site_id = dossier["siteId"]
    scaffold_id = dossier["scaffoldId"]
    variant_id = dossier["variantId"]

    scaffold_dir = SCAFFOLDS_DIR / scaffold_id
    scaffold = load_json(scaffold_dir / "scaffold.json")
    scaffold_routes = load_json(scaffold_dir / "routes.json")
    variant = load_json(scaffold_dir / "variants" / f"{variant_id}.json")

    run_id = make_run_id(site_id)
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace(run_id, run_dir)

    print(f"runId: {run_id}")

    # Phase 1: understand
    write_phase1_understand(run_dir, trace, dossier_path, dossier, scaffold)

    # Phase 2: plan
    write_phase2_plan(
        run_dir, trace, dossier, scaffold, scaffold_routes, variant
    )

    # Phase 3: build
    target = GENERATED_DIR / site_id
    trace.event("build", "phase.started", "started", "Phase 3 build starts")

    print(f"Copying marketing-base -> {target}")
    copy_starter("marketing-base", target)

    print("Patching package.json")
    patch_package_json(target, dossier)

    print("Patching app/layout.tsx")
    patch_layout(
        target,
        site_title=dossier["company"]["name"],
        site_description=dossier["company"]["tagline"],
    )

    print("Injecting variant tokens into app/globals.css")
    patch_globals_css(target, variant)

    print("Writing pages: /, /tjanster, /om-oss, /kontakt")
    write_pages(target, dossier)

    selected_dossiers = load_selected_dossier_manifests(dossier)
    copied_components = mount_dossier_components(target, selected_dossiers)
    dossier_routes = write_dossier_routes(target, selected_dossiers)

    routes_required = required_routes(scaffold_routes)
    routes_all = all_default_routes(scaffold_routes)
    routes_required_with_dossiers = sorted(set(routes_required + dossier_routes))
    routes_all_with_dossiers = sorted(set(routes_all + dossier_routes))
    assert_routes_present(target, routes_required_with_dossiers)
    trace.event(
        "build", "files.written", "done",
        f"Wrote {len(routes_all_with_dossiers)} routes and copied {len(copied_components)} dossier components with default exports verified",
    )

    npm_steps: list[dict] = []
    overall_status = "ok"

    if do_build:
        if not (target / "node_modules").exists():
            print("Running npm install...")
            ok, secs, last = run_npm(["npm", "install"], target)
            npm_steps.append(
                {"name": "npm install", "ok": ok, "seconds": round(secs, 1)}
            )
            trace.event(
                "build", "npm.install", "done" if ok else "failed",
                f"npm install ok={ok} seconds={secs:.1f}",
            )
            if not ok:
                overall_status = "failed"
                print(last, file=sys.stderr)

        if overall_status == "ok":
            print("Running npm run build...")
            ok, secs, last = run_npm(
                ["npm", "run", "build"], target,
            )
            npm_steps.append(
                {"name": "npm run build", "ok": ok, "seconds": round(secs, 1)}
            )
            trace.event(
                "build", "npm.build", "done" if ok else "failed",
                f"next build ok={ok} seconds={secs:.1f}",
            )
            if not ok:
                overall_status = "failed"
                print(last, file=sys.stderr)
    else:
        overall_status = "skipped"
        trace.event(
            "build", "build.skipped", "degraded",
            "Build skipped via --skip-build",
        )

    # Snapshot generated files into the canonical run directory.
    print("Snapshotting generated files into run directory")
    snapshot_generated_files(target, run_dir)
    trace.event(
        "build", "generated_files.snapshotted", "done",
        "Snapshotted generated files into data/runs/<runId>/generated-files/",
        payload_path="generated-files/",
    )

    # Skeleton repair + quality artefacts so downstream consumers see all 8.
    write_repair_result_skeleton(run_dir)
    trace.event(
        "build", "repair_result.written", "done",
        "Repair Pipeline not implemented (skeleton status=not-run)",
        payload_path="repair-result.json",
    )
    write_quality_result_skeleton(run_dir)
    trace.event(
        "build", "quality_result.written", "done",
        "Quality Gate not implemented (skeleton status=not-run)",
        payload_path="quality-result.json",
    )

    duration_ms = int((time.monotonic() - started) * 1000)
    write_build_result(
        run_dir, trace, dossier, scaffold, variant,
        routes_all_with_dossiers, npm_steps, overall_status, target, duration_ms,
    )

    if overall_status == "failed":
        trace.event("build", "phase.completed", "failed", "Phase 3 build failed")
        raise SystemExit(1)

    trace.event("build", "phase.completed", "done", "Phase 3 build done")
    print(f"Generated site at {target}")
    print(f"Run artifacts at {run_dir}")
    return target, run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a generated site from a Project Input."
    )
    parser.add_argument(
        "--dossier",
        required=True,
        help="Path to the Project Input JSON file (examples/<siteId>.project-input.json).",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip npm install + npm run build (file generation only).",
    )
    args = parser.parse_args()

    dossier_path = Path(args.dossier).resolve()
    if not dossier_path.exists():
        print(f"Dossier not found: {dossier_path}", file=sys.stderr)
        return 1

    build(dossier_path, do_build=not args.skip_build)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
