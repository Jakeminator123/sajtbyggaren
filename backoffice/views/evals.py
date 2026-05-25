"""Evals och telemetri-vy — kör eval-suite och visa senaste smoke-resultat.

Två knappar spawnar `scripts/run_eval_suite.py` som subprocess och streamar
loggar live. Senaste suite-körningens summary (under
`data/evals/eval-runs/`) renderas som en tabell över de nio spårfälten
operatören tittar på. Ett manuellt 1-10 scorecard per case sparas
separat under `data/evals/manual-scorecards/`. Formatet är dokumenterat
i `docs/evals.md`.

Vyn ändrar inte `quality-result.json` eller någon `packages/generation/`-
modul — den är en read-only iakttagare ovanpå builderns artefakter.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st

from ..paths import EVAL_RUNS_DIR, MANUAL_SCORECARDS_DIR, REPO_ROOT, SCRIPTS_DIR
from ._helpers import safe_render

SCORE_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("clarity", "Tydlighet (är erbjudandet klart på första skärm?)"),
    ("trust", "Förtroende (sociala bevis, kontakt, profil)"),
    ("design", "Design (visuell helhet, typografi, hierarki)"),
    ("cta", "CTA (tydlig nästa-handling)"),
    ("copy", "Copy (naturlig text, inte AI-mall)"),
    ("overall", "Helhet"),
)

QUICK_TIMEOUT_SECONDS = 600
FULL_TIMEOUT_SECONDS = 1800
LOG_EXCERPT_LINES = 80


def _utc_iso() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _format_excerpt(lines: list[str]) -> str:
    excerpt = lines[-LOG_EXCERPT_LINES:]
    if not excerpt:
        return "Väntar på output från subprocess..."
    prefix = ""
    if len(lines) > LOG_EXCERPT_LINES:
        prefix = f"... visar senaste {LOG_EXCERPT_LINES} av {len(lines)} rader ...\n"
    return prefix + "".join(excerpt).rstrip()


def _render_status(slot: Any, *, mode: str, state: str, elapsed: float, lines: list[str]) -> None:
    if slot is None:
        return
    slot.markdown(
        "\n".join(
            [
                f"**Mode:** `{mode}`",
                f"**Status:** {state}",
                f"**Tid:** {elapsed:.1f}s",
                "",
                "```text",
                _format_excerpt(lines),
                "```",
            ]
        )
    )


def _spawn_subprocess_group(cmd: list[str], *, cwd: str, env: dict[str, str]) -> subprocess.Popen[str]:
    """Spawn ``cmd`` so the whole process tree can be terminated together.

    On Windows the child runs in a new process group via
    ``CREATE_NEW_PROCESS_GROUP`` so a later ``taskkill /T`` recursively
    reaches grandchildren (``build_site.py`` -> ``npm`` -> ``node``). On
    POSIX we use ``start_new_session=True`` so the same tree shares a
    process group we can signal with ``os.killpg``.
    """

    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "cwd": cwd,
        "env": env,
    }
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **popen_kwargs)


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    """Kill ``proc`` and every descendant.

    Without this, ``proc.kill()`` only signals the top-level Python
    process; spawned grandchildren (``build_site.py``, ``npm``, ``node``)
    keep running and consume resources while the UI already reports a
    timeout (Codex P2 review on PR #87).
    """

    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            import os as _os
            import signal as _signal

            try:
                _os.killpg(_os.getpgid(proc.pid), _signal.SIGTERM)
            except ProcessLookupError:
                pass
    except (OSError, subprocess.SubprocessError):
        proc.kill()


def _run_eval_suite(mode: str, status_slot: Any | None) -> dict[str, Any]:
    timeout = QUICK_TIMEOUT_SECONDS if mode == "quick" else FULL_TIMEOUT_SECONDS
    cmd = [sys.executable, str(SCRIPTS_DIR / "run_eval_suite.py"), mode]

    env = os.environ.copy()
    lines: list[str] = []
    q: queue.Queue[str] = queue.Queue()
    started = time.monotonic()

    def _reader(stream: Any) -> None:
        for line in iter(stream.readline, ""):
            if not line:
                break
            q.put(line)
        stream.close()

    def _drain() -> None:
        while True:
            try:
                lines.append(q.get_nowait())
            except queue.Empty:
                break

    try:
        proc = _spawn_subprocess_group(cmd, cwd=str(REPO_ROOT), env=env)
    except FileNotFoundError as exc:
        return {"exit_code": 1, "output": f"run_eval_suite.py kunde inte startas: {exc}", "timed_out": False, "elapsed": 0.0}

    reader_thread: threading.Thread | None = None
    if proc.stdout is not None:
        reader_thread = threading.Thread(target=_reader, args=(proc.stdout,), daemon=True)
        reader_thread.start()

    _render_status(status_slot, mode=mode, state="kör", elapsed=0.0, lines=lines)

    timed_out = False
    while proc.poll() is None:
        elapsed = time.monotonic() - started
        _drain()
        _render_status(status_slot, mode=mode, state="kör", elapsed=elapsed, lines=lines)
        if elapsed > timeout:
            timed_out = True
            lines.append(f"\nTimeout efter {timeout}s\n")
            _terminate_process_tree(proc)
            break
        time.sleep(0.2)

    exit_code = proc.wait()
    if reader_thread is not None:
        reader_thread.join(timeout=1)
    _drain()
    elapsed = time.monotonic() - started
    state = "timeout" if timed_out else ("klar" if exit_code == 0 else "fail")
    _render_status(status_slot, mode=mode, state=state, elapsed=elapsed, lines=lines)
    return {
        "exit_code": 1 if timed_out else exit_code,
        "output": "".join(lines),
        "timed_out": timed_out,
        "elapsed": elapsed,
    }


def _list_summaries() -> list[Path]:
    if not EVAL_RUNS_DIR.exists():
        return []
    files = [p for p in EVAL_RUNS_DIR.glob("*.json") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _load_scorecard(eval_run_id: str) -> dict[str, Any] | None:
    path = MANUAL_SCORECARDS_DIR / f"{eval_run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _save_scorecard(eval_run_id: str, items: list[dict[str, Any]]) -> Path:
    MANUAL_SCORECARDS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "evalRunId": eval_run_id,
        "createdAt": _utc_iso(),
        "items": items,
    }
    out_path = MANUAL_SCORECARDS_DIR / f"{eval_run_id}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)
    return out_path


def _format_dossiers(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "—"
    return str(value)


def _format_rejected(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, list):
        parts = []
        for entry in value:
            if isinstance(entry, dict) and "id" in entry:
                parts.append(str(entry["id"]))
            else:
                parts.append(str(entry))
        return ", ".join(parts) or "—"
    return str(value)


def _render_summary_table(summary: dict[str, Any]) -> None:
    cases = summary.get("cases", [])
    if not cases:
        st.info("Suite har inga cases.")
        return
    rows = []
    for case in cases:
        rows.append(
            {
                "siteId": case.get("siteId") or "—",
                "briefSource": case.get("briefSource") or "—",
                "planSource": case.get("planSource") or "—",
                "scaffoldId": case.get("scaffoldId") or "—",
                "variantId": case.get("variantId") or "—",
                "starterId": case.get("starterId") or "—",
                "selectedDossiers": _format_dossiers(case.get("selectedDossiers")),
                "rejectedCapabilities": _format_rejected(case.get("rejectedCapabilities")),
                "qualityStatus": case.get("qualityStatus") or "—",
                "buildStatus": case.get("buildStatus") or "—",
                "error": case.get("error") or "",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_scorecard_form(summary: dict[str, Any]) -> None:
    eval_run_id = summary.get("evalRunId")
    if not eval_run_id:
        return
    cases = summary.get("cases", [])
    if not cases:
        return

    existing = _load_scorecard(eval_run_id) or {}
    existing_items = {item.get("runId") or item.get("siteId"): item for item in existing.get("items", [])}

    st.subheader("Manuellt scorecard")
    st.caption(
        "1-10 per dimension är en operatörs-bedömning av faktisk hemsidekvalitet, "
        "inte ett automatiskt mått. Sparas separat — `quality-result.json` ändras inte."
    )

    with st.form(key=f"scorecard-{eval_run_id}"):
        new_items: list[dict[str, Any]] = []
        for idx, case in enumerate(cases):
            site_id = case.get("siteId") or f"case-{idx}"
            run_id = case.get("runId")
            key = run_id or site_id
            prev = existing_items.get(key, {})
            st.markdown(f"**{site_id}** — `{run_id or 'ingen runId'}`")
            cols = st.columns(3)
            scores: dict[str, int] = {}
            for i, (dim, label) in enumerate(SCORE_DIMENSIONS):
                col = cols[i % 3]
                default = int(prev.get(dim, 5))
                if default < 1:
                    default = 1
                if default > 10:
                    default = 10
                scores[dim] = col.slider(
                    label,
                    min_value=1,
                    max_value=10,
                    value=default,
                    key=f"score-{eval_run_id}-{site_id}-{dim}",
                )
            notes = st.text_area(
                "Anteckning",
                value=str(prev.get("notes", "")),
                key=f"notes-{eval_run_id}-{site_id}",
                height=68,
            )
            new_items.append(
                {
                    "siteId": site_id,
                    "runId": run_id,
                    **scores,
                    "notes": notes,
                }
            )
            st.divider()

        submitted = st.form_submit_button("Spara scorecard", type="primary", use_container_width=True)
        if submitted:
            out = _save_scorecard(eval_run_id, new_items)
            st.success(f"Scorecard sparat: `{out.relative_to(REPO_ROOT)}`")


def view_evals() -> None:
    st.title("Evals och telemetri")
    st.caption(
        "Smoke- och regressionssignal över examples-dossiers. Inte 1-10 kvalitetsbetyg "
        "— det lägger vi separat som manuellt scorecard. Detaljer i `docs/evals.md`."
    )

    try:
        from packages.generation.brief import has_openai_api_key

        api_key_set = has_openai_api_key()
    except ImportError:
        api_key_set = bool((os.environ.get("OPENAI_API_KEY") or "").strip())

    if api_key_set:
        st.success(
            "OPENAI_API_KEY är satt — `briefModel` anropar riktig LLM. "
            "`planSource` förblir `pinned` i `build_site.py` eftersom Project Input "
            "pinnar scaffold/variant; det är förväntat."
        )
    else:
        st.info(
            "Ingen OPENAI_API_KEY satt — `briefSource` blir `mock-no-key`. "
            "Suite kör fortfarande deterministisk codegen + Quality Gate."
        )

    st.subheader("Kör eval-suite")
    cols = st.columns(2)
    if cols[0].button(
        "Snabb regression (4x skip-build)",
        use_container_width=True,
        type="primary",
        key="eval-quick",
    ):
        status_slot = st.empty()
        with st.spinner("Kör quick-suite ..."):
            result = _run_eval_suite("quick", status_slot)
        st.session_state["eval_last_result"] = result
        if result["exit_code"] == 0:
            st.success(f"Quick-suite klar på {result['elapsed']:.1f}s.")
        elif result["timed_out"]:
            st.error(f"Timeout efter {QUICK_TIMEOUT_SECONDS}s.")
        else:
            st.error(f"Suite failade med exit code {result['exit_code']}.")

    if cols[1].button(
        "Full build (painter-palma + atelje-bird)",
        use_container_width=True,
        key="eval-full",
        help=(
            "Kör npm install + npm run build per case. Tar flera minuter; "
            "Streamlit-UI blockeras tills suite är klar."
        ),
    ):
        status_slot = st.empty()
        with st.spinner("Kör full-suite (npm install + npm run build per case) ..."):
            result = _run_eval_suite("full", status_slot)
        st.session_state["eval_last_result"] = result
        if result["exit_code"] == 0:
            st.success(f"Full-suite klar på {result['elapsed']:.1f}s.")
        elif result["timed_out"]:
            st.error(f"Timeout efter {FULL_TIMEOUT_SECONDS}s.")
        else:
            st.error(f"Suite failade med exit code {result['exit_code']}.")

    last_log = st.session_state.get("eval_last_result")
    if last_log and last_log.get("output"):
        with st.expander(
            f"Subprocess-logg (exit {last_log['exit_code']}, {last_log['elapsed']:.1f}s)",
            expanded=False,
        ):
            st.code(last_log["output"], language="text")

    summaries = _list_summaries()
    if not summaries:
        st.info(
            "Inga eval-runs ännu. Tryck på en av knapparna ovan, eller kör "
            "`python scripts/run_eval_suite.py quick` från terminal."
        )
        return

    st.subheader("Senaste eval-run")
    options = [p.stem for p in summaries]
    chosen_idx = st.selectbox(
        "Välj evalRunId",
        options=list(range(len(options))),
        format_func=lambda i: options[i],
        index=0,
        key="eval-history-select",
    )
    chosen_path = summaries[chosen_idx]
    try:
        summary = json.loads(chosen_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        st.error(f"Kunde inte läsa {chosen_path.name}: {exc}")
        return

    meta_cols = st.columns(4)
    meta_cols[0].metric("Mode", summary.get("mode", "—"))
    meta_cols[1].metric("Cases", len(summary.get("cases", [])))
    meta_cols[2].metric("OpenAI-key", "ja" if summary.get("openaiKeyPresent") else "nej")
    meta_cols[3].metric("Skapad", summary.get("createdAt", "—"))

    _render_summary_table(summary)
    st.divider()
    _render_scorecard_form(summary)


VIEWS = {
    "Evals och telemetri": lambda: safe_render(view_evals),
}
