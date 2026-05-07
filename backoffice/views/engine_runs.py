"""Engine Runs-vy: lista körningar och inspektera artefakter + trace."""

from __future__ import annotations

import json

import streamlit as st

from .. import loaders
from ..paths import RUNS_DIR
from ._helpers import safe_render


def view_engine_runs() -> None:
    st.title("Engine Runs")
    st.caption(
        "Körningar under `data/runs/`. Varje runId har en mapp med 8 artefakter "
        "och en `trace.ndjson`. Se `engine-run.v1.json`."
    )

    run_ids = loaders.list_run_ids()
    if not run_ids:
        st.info(
            "Inga körningar än. Skapa en med:\n\n"
            '```\npython scripts/dev_generate.py "Skapa hemsida för en elektriker i Malmö"\n```'
        )
        return

    st.metric("Antal körningar", len(run_ids))
    selected = st.selectbox("Välj runId", run_ids, key="engine_run_select")
    if not selected:
        return

    run_dir = RUNS_DIR / selected
    expected = [
        "input.json",
        "site-brief.json",
        "site-plan.json",
        "generation-package.json",
        "repair-result.json",
        "quality-result.json",
        "build-result.json",
        "trace.ndjson",
    ]
    rows = []
    for name in expected:
        path = run_dir / name
        rows.append(
            {
                "Artefakt": name,
                "Status": "OK" if path.exists() else "saknas",
                "Bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    files_dir = run_dir / "generated-files"
    rows.append(
        {
            "Artefakt": "generated-files/",
            "Status": "OK" if files_dir.is_dir() else "saknas",
            "Bytes": (
                sum(p.stat().st_size for p in files_dir.rglob("*") if p.is_file())
                if files_dir.is_dir()
                else 0
            ),
        }
    )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    tab_trace, tab_brief, tab_plan, tab_build, tab_files = st.tabs(
        ["Trace", "Site Brief", "Site Plan + Package", "Build Result", "Generated Files"]
    )

    with tab_trace:
        trace_path = run_dir / "trace.ndjson"
        if trace_path.exists():
            events = []
            for line in trace_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if events:
                st.dataframe(events, use_container_width=True, hide_index=True)
            else:
                st.warning("Trace finns men kunde inte parsas.")
        else:
            st.warning("trace.ndjson saknas.")

    def _show(path_name: str):
        path = run_dir / path_name
        if path.exists():
            try:
                st.json(json.loads(path.read_text(encoding="utf-8")), expanded=False)
            except json.JSONDecodeError as exc:
                st.error(f"{path_name}: ogiltig JSON: {exc}")
        else:
            st.info(f"{path_name} saknas.")

    with tab_brief:
        _show("site-brief.json")
    with tab_plan:
        _show("site-plan.json")
        _show("generation-package.json")
    with tab_build:
        _show("build-result.json")
        _show("repair-result.json")
        _show("quality-result.json")
    with tab_files:
        if files_dir.is_dir():
            files = sorted(p for p in files_dir.rglob("*") if p.is_file())
            if not files:
                st.info("generated-files/ är tom.")
            else:
                names = [str(f.relative_to(files_dir)) for f in files]
                pick = st.selectbox("Fil", names, key=f"file-{selected}")
                if pick:
                    chosen = files_dir / pick
                    st.code(chosen.read_text(encoding="utf-8"), language=None)
        else:
            st.info("generated-files/ saknas.")


VIEWS = {
    "Engine Runs": lambda: safe_render(view_engine_runs),
}
