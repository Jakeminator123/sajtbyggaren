"""Playground-vy: kör Engine Run från backoffice och se output live.

Spawnar `scripts/dev_generate.py` som subprocess - LLM-anrop sker INTE i
Streamlit-tråden. Pollar artefaktmappen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import streamlit as st

from ..paths import REPO_ROOT, RUNS_DIR, SCRIPTS_DIR
from ._helpers import safe_render


def _run_dev_generate(prompt: str, mode: str, phase: str, run_id: str | None = None) -> tuple[int, str, str | None]:
    args = [
        sys.executable,
        str(SCRIPTS_DIR / "dev_generate.py"),
        prompt,
        "--phase",
        phase,
    ]
    if run_id:
        args.extend(["--run-id", run_id])

    env = os.environ.copy()
    env["SAJTBYGGAREN_MODE"] = mode

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return 1, "", "Timeout efter 120s"

    output = (result.stdout or "") + (result.stderr or "")

    found_run_id: str | None = None
    for line in output.splitlines():
        if line.startswith("Run complete:"):
            run_path = line.replace("Run complete:", "").strip()
            try:
                found_run_id = run_path.rsplit(os.sep, 1)[-1]
            except Exception:
                found_run_id = None
        elif "runId=" in line and "engine.run.started" in line:
            for token in line.split():
                if token.startswith("runId="):
                    found_run_id = token.split("=", 1)[1]
                    break

    return result.returncode, output, found_run_id


def view_playground() -> None:
    st.title("Playground")
    st.caption(
        "Kör en Engine Run direkt från backoffice. Spawnar `scripts/dev_generate.py` som "
        "subprocess. Anropar riktig LLM om `OPENAI_API_KEY` finns, annars mock."
    )

    api_key_set = bool(os.environ.get("OPENAI_API_KEY"))
    if api_key_set:
        st.success("OPENAI_API_KEY är satt - briefModel kan göra riktiga anrop när Sprint C är aktiv.")
    else:
        st.info("Ingen OPENAI_API_KEY satt - alla phases är mockade.")

    prompt = st.text_area(
        "Prompt",
        value=st.session_state.get("playground_prompt", "Skapa hemsida för en elektriker i Malmö"),
        height=80,
        key="playground_prompt_input",
    )
    st.session_state["playground_prompt"] = prompt

    cols = st.columns([1, 1])
    mode = cols[0].radio("Mode", ["init", "followup"], horizontal=True, key="playground_mode")
    if mode == "followup":
        st.warning("Follow-up runtime är inte implementerad än. Body-vyn körs som init under huven.")

    project_id = None
    if mode == "followup":
        project_id = cols[1].text_input("Project ID", key="playground_project_id")

    st.subheader("Kör fas")
    a, b, c, d = st.columns(4)
    if a.button("Fas 1: brief", use_container_width=True, key="pg_brief"):
        with st.spinner("Kör fas 1..."):
            code, output, run_id = _run_dev_generate(prompt, mode, "brief")
            st.session_state["playground_run_id"] = run_id
            st.session_state["playground_output"] = output
            st.session_state["playground_phase"] = "brief"
            if code != 0:
                st.error(f"Exit code {code}")
    if b.button("Fas 2: plan", use_container_width=True, key="pg_plan"):
        rid = st.session_state.get("playground_run_id")
        if not rid:
            st.warning("Kör fas 1 först.")
        else:
            with st.spinner("Kör fas 2..."):
                code, output, _ = _run_dev_generate(prompt, mode, "plan", rid)
                st.session_state["playground_output"] = output
                st.session_state["playground_phase"] = "plan"
                if code != 0:
                    st.error(f"Exit code {code}")
    if c.button("Fas 3: build", use_container_width=True, key="pg_build"):
        rid = st.session_state.get("playground_run_id")
        if not rid:
            st.warning("Kör fas 1 och 2 först.")
        else:
            with st.spinner("Kör fas 3..."):
                code, output, _ = _run_dev_generate(prompt, mode, "build", rid)
                st.session_state["playground_output"] = output
                st.session_state["playground_phase"] = "build"
                if code != 0:
                    st.error(f"Exit code {code}")
    if d.button("Kör allt", use_container_width=True, type="primary", key="pg_all"):
        with st.spinner("Kör hela kedjan..."):
            code, output, run_id = _run_dev_generate(prompt, mode, "all")
            st.session_state["playground_run_id"] = run_id
            st.session_state["playground_output"] = output
            st.session_state["playground_phase"] = "all"
            if code != 0:
                st.error(f"Exit code {code}")

    output = st.session_state.get("playground_output", "")
    if output:
        with st.expander("Engine Events (output från subprocess)", expanded=True):
            st.code(output, language="text")

    run_id = st.session_state.get("playground_run_id")
    if run_id:
        run_dir = RUNS_DIR / run_id
        st.divider()
        st.subheader(f"Artefakter för {run_id}")

        tab_brief, tab_plan, tab_build, tab_trace = st.tabs(
            ["Site Brief", "Site Plan + Package", "Build Result", "Trace"]
        )

        def _show(path_name: str):
            path = run_dir / path_name
            if not path.exists():
                st.info(f"{path_name} skapas inte än i denna fas.")
                return
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                st.json(data, expanded=False)
            except json.JSONDecodeError as exc:
                st.error(f"Ogiltig JSON: {exc}")

        with tab_brief:
            _show("site-brief.json")
        with tab_plan:
            _show("site-plan.json")
            _show("generation-package.json")
        with tab_build:
            _show("build-result.json")
            _show("repair-result.json")
            _show("quality-result.json")
        with tab_trace:
            trace = run_dir / "trace.ndjson"
            if trace.exists():
                events = [
                    json.loads(line)
                    for line in trace.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                st.dataframe(events, use_container_width=True, hide_index=True)
            else:
                st.info("trace.ndjson skapas i fas 1.")


VIEWS = {
    "Playground": lambda: safe_render(view_playground),
}
