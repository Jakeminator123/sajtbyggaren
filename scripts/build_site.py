"""Deterministic Builder MVP for Sajtbyggaren.

Reads a Site Dossier, a Scaffold and a Variant from the repository and writes
a runnable Next.js project under `.generated/<siteId>/` by copying the
`marketing-base` Starter and patching it with the dossier's content and the
variant's tokens.

This is the minimal happy path described in `docs/migration-plan.md` Sprint 2
and the Builder MVP plan. It deliberately does not call any LLM, does not
implement Repair Pipeline or Quality Gate, and does not do follow-up.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTERS_DIR = REPO_ROOT / "data" / "starters"
SCAFFOLDS_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
)
GENERATED_DIR = REPO_ROOT / ".generated"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def copy_starter(starter_id: str, target: Path) -> None:
    source = STARTERS_DIR / starter_id
    if not source.exists():
        raise SystemExit(
            f"Starter '{starter_id}' missing at {source}. "
            "Run the starter setup before building."
        )
    ignore = shutil.ignore_patterns(
        "node_modules",
        ".next",
        "out",
        "*.tsbuildinfo",
        "next-env.d.ts",
    )
    # Preserve existing target's node_modules / lockfile if present so we do
    # not force a fresh `npm install` on every regeneration.
    preserved = {"node_modules", ".next"}
    if target.exists():
        for entry in target.iterdir():
            if entry.name in preserved:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        # Copy contents of source over the cleaned target.
        shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)
    else:
        shutil.copytree(source, target, ignore=ignore)


def write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(contents)


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
    css.write_text(new_contents, encoding="utf-8", newline="\n")


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
    layout.write_text(text, encoding="utf-8", newline="\n")


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


def write_manifest(
    target: Path,
    dossier: dict,
    scaffold: dict,
    variant: dict,
) -> None:
    manifest = {
        "siteId": dossier["siteId"],
        "starterId": "marketing-base",
        "scaffoldId": scaffold["id"],
        "scaffoldVersion": scaffold["version"],
        "variantId": variant["id"],
        "language": dossier["language"],
        "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
        "routes": [r["path"] for r in load_json(
            SCAFFOLDS_DIR / scaffold["id"] / "routes.json"
        )["defaultRoutes"]],
        "engineMode": "init",
        "buildSource": "scripts/build_site.py",
    }
    write(
        target / "generation.manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def patch_package_json(target: Path, dossier: dict) -> None:
    pkg_path = target / "package.json"
    pkg = load_json(pkg_path)
    pkg["name"] = dossier["siteId"]
    write(pkg_path, json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")


def build(dossier_path: Path) -> Path:
    dossier = load_json(dossier_path)
    scaffold_id = dossier["scaffoldId"]
    variant_id = dossier["variantId"]

    scaffold_dir = SCAFFOLDS_DIR / scaffold_id
    scaffold = load_json(scaffold_dir / "scaffold.json")
    variant = load_json(scaffold_dir / "variants" / f"{variant_id}.json")

    target = GENERATED_DIR / dossier["siteId"]
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

    print("Writing generation.manifest.json")
    write_manifest(target, dossier, scaffold, variant)

    print(f"Generated site at {target}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a generated site from a Site Dossier."
    )
    parser.add_argument(
        "--dossier",
        required=True,
        help="Path to the Site Dossier JSON file.",
    )
    args = parser.parse_args()

    dossier_path = Path(args.dossier).resolve()
    if not dossier_path.exists():
        print(f"Dossier not found: {dossier_path}", file=sys.stderr)
        return 1

    build(dossier_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
