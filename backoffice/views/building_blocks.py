"""Building Blocks-block: Scaffolds, Variants, Dossiers, Reference Templates."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from .. import loaders
from ..paths import REPO_ROOT
from ._helpers import safe_render


SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
REFERENCE_TEMPLATES_DIR = REPO_ROOT / "data" / "reference-templates"

# Marker the building-blocks UI uses to tag files that were created as
# placeholders by the "Lägg till första filuppsättning"-button. Anything
# carrying this marker must NOT count as "Implementerad: ja".
PLACEHOLDER_MARKER = "placeholder, fill per scaffold-contract"


def is_placeholder_file(path: Path) -> bool:
    """Return True if file looks like a placeholder created by the builder.

    A scaffold counts as "Implementerad" only when none of its required
    JSON files contain the placeholder marker. Otherwise the table would
    silently report half-baked scaffolds as implemented.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if PLACEHOLDER_MARKER in text:
        return True
    if path.suffix == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False
        if isinstance(payload, dict) and "_status" in payload:
            return True
    return False


def scaffold_is_real(scaffold_dir: Path) -> bool:
    """Scaffold is real iff at least one required file exists and none are placeholders."""
    if not scaffold_dir.exists():
        return False
    required = ["scaffold.json", "routes.json", "sections.json"]
    real_files = 0
    for fname in required:
        fpath = scaffold_dir / fname
        if not fpath.exists():
            continue
        if is_placeholder_file(fpath):
            return False
        real_files += 1
    return real_files > 0


def _list_scaffold_dirs() -> list:
    if not SCAFFOLDS_DIR.exists():
        return []
    return [d for d in SCAFFOLDS_DIR.iterdir() if d.is_dir()]


def _list_dossier_dirs() -> list:
    if not DOSSIERS_DIR.exists():
        return []
    out = []
    for cls in ("soft", "hybrid", "hard"):
        cls_dir = DOSSIERS_DIR / cls
        if cls_dir.exists():
            for d in cls_dir.iterdir():
                if d.is_dir():
                    out.append((cls, d))
    return out


def view_scaffolds() -> None:
    st.title("Scaffolds")
    contract, err = loaders.safe_load_policy("scaffold-contract.v1.json")
    if err or contract is None:
        st.error(err)
        return

    st.caption(contract.get("purpose", ""))

    registry = contract.get("primaryScaffoldRegistry", [])
    real_scaffolds = {d.name for d in _list_scaffold_dirs() if scaffold_is_real(d)}
    placeholder_scaffolds = {
        d.name for d in _list_scaffold_dirs()
        if d.exists() and not scaffold_is_real(d)
    }

    def _status(scaffold_id: str) -> str:
        if scaffold_id in real_scaffolds:
            return "ja"
        if scaffold_id in placeholder_scaffolds:
            return "platshållare"
        return "nej"

    rows = [
        {
            "id": s["id"],
            "label": s["label"],
            "Implementerad": _status(s["id"]),
            "rationale": s["rationale"],
        }
        for s in registry
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if placeholder_scaffolds:
        st.warning(
            "Följande scaffolds har bara platshållarfiler och bör fyllas eller tas "
            f"bort: {', '.join(sorted(placeholder_scaffolds))}"
        )

    st.divider()
    st.subheader("Filer per Scaffold (kontrakt)")
    layout = contract["scaffoldDirectoryLayout"]
    st.write(f"**Owner package:** `{layout['ownerPackage']}`")
    st.write(f"**Per scaffold path:** `{layout['perScaffoldPath']}`")
    cols = st.columns(2)
    cols[0].markdown("**Required files**")
    for f in layout["requiredFiles"]:
        cols[0].write(f"- `{f}`")
    cols[1].markdown("**Optional files**")
    for f in layout.get("optionalFiles", []):
        cols[1].write(f"- `{f}`")

    st.divider()
    st.subheader("Lägg till första filuppsättning för en Scaffold")
    st.caption(
        "Skapar mappen `packages/generation/orchestration/scaffolds/<id>/` med minimala "
        "obligatoriska filer enligt scaffold-contract. Innehållet är platshållare; "
        "redigera per fil efter creation."
    )

    edit_mode = st.toggle("Aktivera filsystemskrivning", key="scaffold_edit_toggle")
    if not edit_mode:
        return

    candidate_ids = [
        s["id"] for s in registry if s["id"] not in real_scaffolds
    ]
    if not candidate_ids:
        st.info("Alla 14 Scaffolds är redan implementerade.")
        return
    pick = st.selectbox("Välj Scaffold att skapa", candidate_ids, key="scaffold_create_select")
    if st.button(f"Skapa mapp för {pick}", key="scaffold_create"):
        target = SCAFFOLDS_DIR / pick
        target.mkdir(parents=True, exist_ok=True)
        for required in layout["requiredFiles"]:
            path = target / required
            if not path.exists():
                if path.suffix == ".json":
                    path.write_text(
                        json.dumps({"_status": PLACEHOLDER_MARKER}, indent=2) + "\n",
                        encoding="utf-8",
                    )
                else:
                    path.write_text("# placeholder\n", encoding="utf-8")
        st.success(
            f"Skapade {target.relative_to(REPO_ROOT)} med platshållare. "
            "Tabellen ovan visar den nu som 'platshållare', inte 'ja' - "
            "fyll filerna enligt scaffold-contract innan den räknas som implementerad."
        )


def view_variants() -> None:
    st.title("Variants")
    st.caption(
        "Variants ligger under `packages/generation/orchestration/scaffolds/<id>/variants/`. "
        "Listar befintliga; redigering går via Policies-vyn på respektive variant.json."
    )
    scaffolds = _list_scaffold_dirs()
    if not scaffolds:
        st.info("Inga Scaffolds finns att äga Variants än. Skapa en Scaffold först.")
        return

    rows = []
    for s in scaffolds:
        variants_dir = s / "variants"
        if not variants_dir.exists():
            continue
        for v in variants_dir.glob("*.json"):
            rows.append({"Scaffold": s.name, "Variant": v.stem})
    if not rows:
        st.info("Inga variants finns än under befintliga Scaffolds.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)


def view_dossiers() -> None:
    st.title("Dossiers")
    contract, err = loaders.safe_load_policy("dossier-contract.v1.json")
    if err or contract is None:
        st.error(err)
        return

    st.caption(contract.get("purpose", ""))

    st.subheader("Klasser")
    for cls in contract["dossierClasses"]:
        with st.expander(cls["class"].upper()):
            st.write(cls["definition"])
            st.write("**Exempel:** " + ", ".join(cls["examples"]))

    st.subheader("Implementerade Dossiers")
    items = _list_dossier_dirs()
    if not items:
        st.info("Inga Dossiers implementerade än.")
        return
    rows = [{"Klass": cls, "id": d.name} for cls, d in items]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    layout = contract["dossierDirectoryLayout"]
    st.write(f"**Owner package:** `{layout['ownerPackage']}`")
    st.write(f"**Per dossier path:** `{layout['perDossierPath']}`")
    st.markdown("**Required files (alla klasser):**")
    for f in layout["requiredFilesAllClasses"]:
        st.write(f"- `{f}`")
    st.markdown("**Extra filer per klass:**")
    for cls, files in layout["additionalRequiredFilesByClass"].items():
        st.write(f"- `{cls}`: " + ", ".join(f"`{f}`" for f in files))


def view_reference_templates() -> None:
    st.title("Reference Templates")
    st.caption(
        "Externa templates som används som inspirations- och struktur-corpus, inte som "
        "produktens skelett. Sanningskälla: [`embedding-policy.v1.json`]."
    )
    if not REFERENCE_TEMPLATES_DIR.exists():
        st.info(
            "Ingen `data/reference-templates/`-mapp ännu. När du laddar ner Vercel-/egna "
            "templates till den mappen dyker de upp här."
        )
        return
    children = sorted([p.name for p in REFERENCE_TEMPLATES_DIR.iterdir() if p.is_dir()])
    if not children:
        st.info("`data/reference-templates/` är tom.")
        return
    st.write("Kataloger under `data/reference-templates/`:")
    for child in children:
        st.write(f"- `{child}`")


VIEWS = {
    "Scaffolds": lambda: safe_render(view_scaffolds),
    "Variants": lambda: safe_render(view_variants),
    "Dossiers": lambda: safe_render(view_dossiers),
    "Reference Templates": lambda: safe_render(view_reference_templates),
}
