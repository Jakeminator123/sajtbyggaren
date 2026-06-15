"""Building Blocks: Scaffolds-vyn."""

from __future__ import annotations

import json

import streamlit as st

from ... import asset_graph, loaders
from ...paths import REPO_ROOT
from . import PLACEHOLDER_MARKER, SCAFFOLD_CANDIDATES_DIR, _list_scaffold_dirs


def view_scaffolds() -> None:
    st.title("Scaffolds")
    contract, err = loaders.safe_load_policy("scaffold-contract.v1.json")
    if err or contract is None:
        st.error(err)
        return

    st.caption(contract.get("purpose", ""))

    registry = contract.get("primaryScaffoldRegistry", [])
    required_files = asset_graph.scaffold_required_files(contract)
    real_scaffolds = {
        d.name for d in _list_scaffold_dirs() if asset_graph.scaffold_is_real(d, required_files)
    }
    placeholder_scaffolds = {
        d.name for d in _list_scaffold_dirs()
        if d.exists() and not asset_graph.scaffold_is_real(d, required_files)
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
            "requiredFiles": len(required_files),
            "rationale": s["rationale"],
        }
        for s in registry
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
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
    st.subheader("Skapa kandidat-skelett för en Scaffold")
    st.caption(
        "Skapar ett kandidat-skelett under `data/scaffold-candidates/<id>/` med de "
        "obligatoriska filerna enligt scaffold-contract (platshållarinnehåll). "
        "Backoffice skriver aldrig till canonical `packages/` (repo-boundaries); "
        "promotering till `packages/generation/orchestration/scaffolds/` sker via "
        "Builder-agent/PR. Samma kandidat-mönster som Variant Candidates och Dossier Candidates."
    )

    edit_mode = st.toggle("Aktivera kandidatskrivning", key="scaffold_edit_toggle")
    if not edit_mode:
        return

    candidate_ids = [
        s["id"] for s in registry if s["id"] not in real_scaffolds
    ]
    if not candidate_ids:
        st.info("Alla 14 Scaffolds är redan implementerade.")
        return
    selected = st.selectbox(
        "Välj Scaffold att skapa kandidat för", candidate_ids, key="scaffold_create_select"
    )
    if not isinstance(selected, str) or not selected:
        st.info("Välj en Scaffold innan du skapar kandidatfiler.")
        return
    pick = selected
    if st.button(f"Skapa kandidat för {pick}", key="scaffold_create"):
        target = SCAFFOLD_CANDIDATES_DIR / pick
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
            f"Skapade kandidat-skelett {target.relative_to(REPO_ROOT)} med platshållare. "
            "Det här promoterar aldrig till canonical `packages/` - en Builder-agent/PR "
            "flyttar skelettet till scaffolds/ när filerna fyllts enligt scaffold-contract."
        )

