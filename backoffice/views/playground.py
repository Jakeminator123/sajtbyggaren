"""Playground-vy: kör Engine Run från backoffice och se output live.

Spawnar `scripts/dev_generate.py` som subprocess - LLM-anrop sker INTE i
Streamlit-tråden. Pollar artefaktmappen.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any

import streamlit as st

from ..paths import REPO_ROOT, RUNS_DIR, SCRIPTS_DIR
from ._helpers import safe_render
from ._trace import load_trace_events, render_trace_viewer

PLAYGROUND_TIMEOUT_SECONDS = 180
LOG_EXCERPT_LINES = 80


def _extract_run_id(output: str) -> str | None:
    found_run_id: str | None = None
    for line in output.splitlines():
        if line.startswith("Run complete:"):
            run_path = line.replace("Run complete:", "").strip()
            normalized = run_path.replace("\\", "/").rstrip("/")
            found_run_id = normalized.rsplit("/", 1)[-1] or None
        elif "runId=" in line:
            for token in line.split():
                if token.startswith("runId="):
                    found_run_id = token.split("=", 1)[1]
                    break
    return found_run_id


def _format_log_excerpt(lines: list[str], *, limit: int = LOG_EXCERPT_LINES) -> str:
    excerpt = lines[-limit:]
    if not excerpt:
        return "Väntar på output från subprocess..."
    prefix = ""
    if len(lines) > limit:
        prefix = f"... visar senaste {limit} av {len(lines)} rader ...\n"
    return prefix + "".join(excerpt).rstrip()


def _render_process_status(
    status_slot: Any | None,
    *,
    phase: str,
    state: str,
    elapsed_seconds: float,
    exit_code: int | None,
    lines: list[str],
) -> None:
    if status_slot is None:
        return

    exit_text = "-" if exit_code is None else str(exit_code)
    status_slot.markdown(
        "\n".join(
            [
                f"**Status:** {state}",
                f"**Fas:** `{phase}`",
                f"**Tid:** {elapsed_seconds:.1f}s",
                f"**Exit code:** `{exit_text}`",
                "",
                "```text",
                _format_log_excerpt(lines),
                "```",
            ]
        )
    )


def _run_dev_generate(
    prompt: str,
    mode: str,
    phase: str,
    run_id: str | None = None,
    project_id: str | None = None,
    *,
    status_slot: Any | None = None,
    timeout_seconds: int = PLAYGROUND_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    args = [
        sys.executable,
        str(SCRIPTS_DIR / "dev_generate.py"),
        prompt,
        "--phase",
        phase,
        "--mode",
        mode,
    ]
    if mode == "followup" and project_id:
        args.extend(["--project-id", project_id])
    if run_id:
        args.extend(["--run-id", run_id])

    env = os.environ.copy()
    env["SAJTBYGGAREN_MODE"] = mode

    output_lines: list[str] = []
    output_queue: queue.Queue[str] = queue.Queue()
    started_at = time.monotonic()

    def _reader(stream: Any) -> None:
        for line in iter(stream.readline, ""):
            if not line:
                break
            output_queue.put(line)
        stream.close()

    def _drain_output() -> None:
        while True:
            try:
                output_lines.append(output_queue.get_nowait())
            except queue.Empty:
                break

    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
    except FileNotFoundError as exc:
        output = f"dev_generate.py kunde inte startas: {exc}"
        return {
            "exit_code": 1,
            "output": output,
            "run_id": None,
            "timed_out": False,
            "elapsed_seconds": 0.0,
        }

    if process.stdout is not None:
        reader = threading.Thread(target=_reader, args=(process.stdout,), daemon=True)
        reader.start()
    else:
        reader = None

    _render_process_status(
        status_slot,
        phase=phase,
        state="kör",
        elapsed_seconds=0.0,
        exit_code=None,
        lines=output_lines,
    )

    timed_out = False
    while process.poll() is None:
        elapsed = time.monotonic() - started_at
        _drain_output()
        _render_process_status(
            status_slot,
            phase=phase,
            state="kör",
            elapsed_seconds=elapsed,
            exit_code=None,
            lines=output_lines,
        )
        if elapsed > timeout_seconds:
            timed_out = True
            output_lines.append(f"\nTimeout efter {timeout_seconds}s\n")
            process.kill()
            break
        time.sleep(0.1)

    exit_code = process.wait()
    if reader is not None:
        reader.join(timeout=1)
    _drain_output()
    elapsed = time.monotonic() - started_at
    output = "".join(output_lines)
    if timed_out:
        exit_code = 1

    state = "timeout" if timed_out else ("klar" if exit_code == 0 else "fail")
    _render_process_status(
        status_slot,
        phase=phase,
        state=state,
        elapsed_seconds=elapsed,
        exit_code=exit_code,
        lines=output_lines,
    )
    return {
        "exit_code": exit_code,
        "output": output,
        "run_id": _extract_run_id(output),
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
    }


def view_playground() -> None:
    st.title("Playground")
    st.caption(
        "Kör en Engine Run direkt från backoffice. Spawnar `scripts/dev_generate.py` som "
        "subprocess. Anropar riktig LLM om `OPENAI_API_KEY` finns, annars mock."
    )

    from packages.generation.brief import has_openai_api_key

    api_key_set = has_openai_api_key()
    if api_key_set:
        st.success(
            "OPENAI_API_KEY är satt - **fas 1 (briefModel) och fas 2 (planningModel)** "
            "anropar riktig LLM. Fas 3 är fortfarande mock placeholder tills Sprint 3."
        )
    else:
        st.info(
            "Ingen OPENAI_API_KEY satt - fas 1 och fas 2 kör mock fallback "
            "(`mock-no-key`), fas 3 är mock placeholder."
        )

    prompt = st.text_area(
        "Prompt",
        value=st.session_state.get("playground_prompt", "Skapa hemsida för en elektriker i Malmö"),
        height=80,
        key="playground_prompt_input",
    )
    st.session_state["playground_prompt"] = prompt

    cols = st.columns([1, 1])
    mode = cols[0].radio(
        "Mode",
        ["init", "followup"],
        horizontal=True,
        key="playground_mode",
        help="Init skapar Project DNA. Follow-up läser DNA - inte implementerat än.",
    )
    project_id: str | None = None
    if mode == "followup":
        project_id = cols[1].text_input("Project ID", key="playground_project_id").strip() or None
        st.warning(
            "Follow-up-runtime är inte implementerad än. dev_generate.py kommer kräva "
            "--project-id och Project DNA-läsning. Avaktiverat för nu."
        )

    can_run = (mode == "init") or (mode == "followup" and project_id)
    if mode == "followup" and not project_id:
        st.error("Ange Project ID för att kunna köra follow-up.")

    st.subheader("Kör fas")
    a, b, c, d = st.columns(4)

    def _run(phase: str, requires_existing_run: bool) -> None:
        rid = st.session_state.get("playground_run_id") if requires_existing_run else None
        if requires_existing_run and not rid:
            st.warning("Kör fas 1 först (eller använd 'Kör allt').")
            return
        status_slot = st.empty()
        with st.spinner(f"Kör fas {phase}... loggar visas nedan."):
            result = _run_dev_generate(
                prompt,
                mode,
                phase,
                rid,
                project_id=project_id,
                status_slot=status_slot,
            )
            if not requires_existing_run and result["run_id"]:
                st.session_state["playground_run_id"] = result["run_id"]
            st.session_state["playground_output"] = result["output"]
            st.session_state["playground_phase"] = phase
            st.session_state["playground_exit_code"] = result["exit_code"]
            st.session_state["playground_timed_out"] = result["timed_out"]
            st.session_state["playground_elapsed_seconds"] = result["elapsed_seconds"]
            if result["exit_code"] == 0:
                st.success(f"Subprocess klar på {result['elapsed_seconds']:.1f}s.")
            elif result["timed_out"]:
                st.error(f"Timeout efter {PLAYGROUND_TIMEOUT_SECONDS}s.")
            else:
                st.error(f"Subprocess failade med exit code {result['exit_code']}.")

    if a.button("Fas 1: brief", use_container_width=True, key="pg_brief", disabled=not can_run):
        _run("brief", requires_existing_run=False)
    if b.button("Fas 2: plan", use_container_width=True, key="pg_plan", disabled=not can_run):
        _run("plan", requires_existing_run=True)
    if c.button("Fas 3: build", use_container_width=True, key="pg_build", disabled=not can_run):
        _run("build", requires_existing_run=True)
    if d.button("Kör allt", use_container_width=True, type="primary", key="pg_all", disabled=not can_run):
        _run("all", requires_existing_run=False)

    output = st.session_state.get("playground_output", "")
    if output:
        exit_code = st.session_state.get("playground_exit_code")
        elapsed = st.session_state.get("playground_elapsed_seconds")
        label = "Subprocess-logg"
        if exit_code is not None:
            label += f" (exit {exit_code}"
            if elapsed is not None:
                label += f", {elapsed:.1f}s"
            label += ")"
        with st.expander(label, expanded=True):
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
                events, skipped_lines = load_trace_events(trace)
                if events:
                    render_trace_viewer(
                        events,
                        key_prefix=f"playground-{run_id}",
                        skipped_lines=skipped_lines,
                    )
                else:
                    st.warning("Trace finns men inga giltiga rader än (möjligen halvskriven).")
            else:
                st.info("trace.ndjson skapas i fas 1.")


VIEWS = {
    "Playground": lambda: safe_render(view_playground),
}
