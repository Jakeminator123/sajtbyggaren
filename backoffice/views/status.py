"""Status-block: Översikt, Golden Path, System Health, Cross-Policy Status."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import streamlit as st

from .. import health, loaders
from ..freshness import compute_freshness
from ..paths import (
    EVALS_GOLDEN_PATH_SUMMARIES_DIR,
    LEGACY_GOLDEN_PATH_DIR,
    REPO_ROOT,
    RUNS_DIR,
)
from ._helpers import render_check, safe_render

BACKOFFICE_VIEWS_POLICY = "backoffice-views.v1.json"


def render_known_gaps() -> None:
    """Render the honest 'known gaps' note shared by Idag + Översikt.

    Surfaces gaps as gaps, not as features (ADR 0039 / docs/known-issues.md).
    """
    st.subheader("Kända brister")
    st.caption(
        "Synliggjorda som brister, inte som nya features. `section_add` monterar "
        "dossiers men renderar ännu inte alltid synligt på sidan/positionen "
        "(`applied=true`, `appliedVisibleEffect=false`). Följdprompt-copy gör "
        "ibland parafras i stället för literal replace. Spårning i "
        "`docs/known-issues.md` och "
        "`docs/gaps/GAP-followup-prompt-content-passthrough.md`."
    )


def _read_run_json(run_dir: Path, name: str) -> dict[str, Any] | None:
    """Read one run artefact as a dict, returning None for missing/broken JSON."""
    path = run_dir / name
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def latest_run_artifacts() -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Return ``(runId, build_result, quality_result)`` for the newest run.

    Pure read-only helper (no subprocess): picks the newest runId from
    ``data/runs/`` via ``loaders.list_run_ids`` and reads ``build-result.json``
    + ``quality-result.json``. Returns ``(None, None, None)`` when there is no
    run on disk.
    """
    run_ids = loaders.list_run_ids()
    if not run_ids:
        return None, None, None
    run_id = run_ids[0]
    run_dir = RUNS_DIR / run_id
    return run_id, _read_run_json(run_dir, "build-result.json"), _read_run_json(
        run_dir, "quality-result.json"
    )


def latest_golden_path_summary(
    summaries_dir: Path,
    legacy_dir: Path | None = None,
) -> tuple[dict[str, Any] | None, Path | None]:
    """Return the newest Golden Path eval summary as ``(data, path)``.

    Pure read-only helper (no Streamlit, no subprocess): scans the given
    summary directories for ``*.json`` files, picks the most recently
    modified, and parses it. Returns ``(None, None)`` when there is no
    readable summary. Broken JSON files are skipped so one corrupt report
    never hides a valid newer/older one.

    See ADR 0039 (Golden Path canonical) and ``docs/llm-golden-path-runbook.md``.
    """
    candidates: list[Path] = []
    for root in (summaries_dir, legacy_dir):
        if root is None or not root.exists():
            continue
        candidates.extend(p for p in root.glob("*.json") if p.is_file())

    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            return data, path
    return None, None


def _hard_reset_caches() -> None:
    loaders.load_json.clear()
    loaders.read_text.clear()


def _render_freshness_table() -> None:
    """Render one freshness badge per view, driven purely by the registry policy."""
    policy, err = loaders.safe_load_policy(BACKOFFICE_VIEWS_POLICY)
    if err or policy is None:
        st.warning(err or f"{BACKOFFICE_VIEWS_POLICY} saknas")
        return
    rows = []
    for entry in policy.get("views", []):
        fresh = compute_freshness(entry, REPO_ROOT)
        rows.append(
            {
                "Färskhet": fresh.badge,
                "Vy": entry.get("view", "—"),
                "Sektion": entry.get("section", "—"),
                "Status": entry.get("status", "—"),
                "Läser från": ", ".join(entry.get("readsFrom", []) or []),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption(
        "🟢 aktuell (data finns) · ⚪ tom datakälla · 🟡 driftar/legacy · "
        "🟢 live-diagnostik. Driven av `governance/policies/backoffice-views.v1.json` "
        "(låst av `tests/test_backoffice_registry.py`). Ingen vy får låtsas vara aktuell."
    )


def view_today() -> None:
    st.title("Idag")
    st.caption(
        "Read-only landningsvy: senaste `Golden Path`-eval, senaste körningen ur "
        "`data/runs/`, Quality Gate-sammandrag, kända brister och en färskhetsbricka "
        "per vy. Kör inget — läser bara disk. Begreppskarta: `docs/glossary.md`; "
        "vy-status: `docs/backoffice/overview.md`."
    )

    st.divider()
    st.subheader("Senaste Golden Path-eval")
    summary, summary_path = latest_golden_path_summary(
        EVALS_GOLDEN_PATH_SUMMARIES_DIR, LEGACY_GOLDEN_PATH_DIR
    )
    if summary is None:
        st.info(
            "Ingen golden-path-eval än. Kör `python scripts/run_golden_path_eval.py "
            "--mode deterministic` (offline, ingen API-nyckel)."
        )
    else:
        g1, g2, g3 = st.columns(3)
        g1.metric("Total score", f"{summary.get('totalScore', '—')} / 10")
        g2.metric("Embeddings gate", str(summary.get("embeddingsReadiness", "—")))
        g3.metric("Cases", summary.get("caseCount", "—"))
        st.caption(
            f"Eval `{summary.get('evalId', '—')}` ({summary.get('mode', '—')}, "
            f"{summary.get('createdAt', '—')}). Detaljer i fliken Golden Path."
        )

    st.divider()
    st.subheader("Senaste körning")
    run_id, build_result, quality_result = latest_run_artifacts()
    if run_id is None:
        st.info(
            "Inga körningar i `data/runs/` än. Skapa en via Playground eller "
            '`python scripts/dev_generate.py "Skapa hemsida för en elektriker i Malmö"`.'
        )
    else:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Run", run_id[:24])
        if build_result is not None:
            r2.metric("Build-status", str(build_result.get("status", "—")))
            r3.metric("siteId", str(build_result.get("siteId", "—")))
            r4.metric("Version", str(build_result.get("version", "—")))
        else:
            st.warning("build-result.json saknas eller är ogiltig för senaste run.")

        st.markdown("**Quality Gate-sammandrag**")
        if quality_result is None:
            st.info("quality-result.json saknas för senaste run.")
        else:
            st.caption(f"Aggregerad status: `{quality_result.get('status', '—')}`.")
            checks = quality_result.get("checks", [])
            if isinstance(checks, list) and checks:
                st.dataframe(
                    [
                        {
                            "Check": c.get("name", "—"),
                            "Status": c.get("status", "—"),
                            "Severitet": c.get("severity", "blocking"),
                            "Detalj": c.get("detail", ""),
                        }
                        for c in checks
                        if isinstance(c, dict)
                    ],
                    width="stretch",
                    hide_index=True,
                )

    st.divider()
    render_known_gaps()

    st.divider()
    st.subheader("Färskhet per vy")
    _render_freshness_table()


def view_overview() -> None:
    st.title("Översikt")
    st.caption(
        "Sajtbyggaren styrs av JSON-policies under `governance/policies/`. "
        "Detta är operatörens redigeringsyta. Användarens runtime ligger inte här. "
        "Dagens motor: `Golden Path` (huvudflödet) bygger via Site Brief -> Site Plan "
        "-> Generation Package -> Quality Gate, med `Project DNA` för "
        "follow-up-versionering. Begreppskarta: `docs/glossary.md`; vy-status: "
        "`docs/backoffice/overview.md`."
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Policies", len(loaders.list_policies()))
    col2.metric("Schemas", len(loaders.list_schemas()))
    col3.metric("Regler", len(loaders.list_rules()))
    col4.metric("ADR", len(loaders.list_decisions()))
    col5.metric("Cursor-speglar", len(list((REPO_ROOT / ".cursor" / "rules").glob("*.mdc"))))

    st.divider()
    st.subheader("Kvalitetsmål och gates")
    pq, err = loaders.safe_load_policy("page-quality-traits.v1.json")
    if err or pq is None:
        st.warning(err or "page-quality-traits saknas")
    else:
        qt = pq.get("qualityTarget", {})
        a, b, c, d = st.columns(4)
        a.metric("Target", qt.get("targetScore"))
        b.metric("Gate", qt.get("gateScore"))
        c.metric("Block under", qt.get("blockBelow"))
        d.metric("Skala", qt.get("scoreScale"))
        st.caption(qt.get("meaning", ""))

    st.divider()
    st.subheader("Golden Path")
    summary, summary_path = latest_golden_path_summary(
        EVALS_GOLDEN_PATH_SUMMARIES_DIR, LEGACY_GOLDEN_PATH_DIR
    )
    if summary is None:
        st.info(
            "Ingen golden-path-eval än. Kör `python scripts/run_golden_path_eval.py "
            "--mode deterministic` (offline, ingen API-nyckel). Detaljer i fliken "
            "**Golden Path** och i `docs/llm-golden-path-runbook.md`."
        )
    else:
        g1, g2, g3 = st.columns(3)
        g1.metric("Total score", f"{summary.get('totalScore', '—')} / 10")
        g2.metric("Embeddings gate", str(summary.get("embeddingsReadiness", "—")))
        g3.metric("Cases", summary.get("caseCount", "—"))
        st.caption(
            f"Senaste eval `{summary.get('evalId', '—')}` "
            f"({summary.get('mode', '—')}, {summary.get('createdAt', '—')}). "
            "Read-only — se fliken Golden Path för per-case-detaljer."
        )

    st.divider()
    st.subheader("Snabbåtgärder")
    a1, a2, a3 = st.columns(3)
    if a1.button("Kör governance-validering", width="stretch", key="ov_validate"):
        st.session_state["overview_check"] = health.run_governance_validate()
    if a2.button("Verifiera rules-sync", width="stretch", key="ov_sync"):
        st.session_state["overview_check"] = health.run_rules_sync_check()
    if a3.button("Term-coverage (strict)", width="stretch", key="ov_terms"):
        st.session_state["overview_check"] = health.run_term_coverage(strict=True)

    if "overview_check" in st.session_state:
        render_check(st.session_state["overview_check"])

    st.divider()
    render_known_gaps()


def view_golden_path_status() -> None:
    st.title("Golden Path")
    st.caption(
        "Read-only status för produktens kanoniska huvudflöde (ADR 0039). "
        "Speglar senaste `scripts/run_golden_path_eval.py`-summary under "
        "`data/evals/summaries/golden-path/`. Den här vyn kör inget — den läser "
        "bara. Flöde + entrypoint-yta i `docs/llm-golden-path-runbook.md`, "
        "begreppskarta i `docs/glossary.md`."
    )

    summary, summary_path = latest_golden_path_summary(
        EVALS_GOLDEN_PATH_SUMMARIES_DIR, LEGACY_GOLDEN_PATH_DIR
    )
    if summary is None:
        st.info(
            "Ingen golden-path-eval hittad. Kör från terminal:\n\n"
            "```\npython scripts/run_golden_path_eval.py --mode deterministic\n```\n\n"
            "Defaultläget är offline (ingen `OPENAI_API_KEY`, ingen npm-build)."
        )
        return

    thresholds = summary.get("thresholds", {}) or {}
    cols = st.columns(4)
    cols[0].metric("Total score", f"{summary.get('totalScore', '—')} / 10")
    cols[1].metric("Embeddings gate", str(summary.get("embeddingsReadiness", "—")))
    cols[2].metric("Cases", summary.get("caseCount", "—"))
    cols[3].metric("Go-snitt", thresholds.get("averageScoreGo", "—"))
    st.caption(
        f"Eval `{summary.get('evalId', '—')}` — läge `{summary.get('mode', '—')}`, "
        f"skapad {summary.get('createdAt', '—')}."
        + (f" Källa: `{summary_path.name}`." if summary_path is not None else "")
    )

    cases = summary.get("cases", [])
    if isinstance(cases, list) and cases:
        rows = [
            {
                "caseId": case.get("caseId", "—"),
                "totalScore": case.get("totalScore", "—"),
                "passThreshold": case.get("passThreshold", "—"),
                "passed": "ja" if case.get("passed") else "nej",
                "scaffoldId": (case.get("scaffoldSelection", {}) or {}).get(
                    "selectedScaffoldId", "—"
                ),
                "qualityStatus": case.get("qualityStatus", "—"),
                "buildStatus": case.get("buildStatus", "—"),
            }
            for case in cases
            if isinstance(case, dict)
        ]
        st.dataframe(rows, width="stretch", hide_index=True)

    problem_mix = summary.get("problemMix", {}) or {}
    if problem_mix.get("dominantProblem"):
        st.caption(f"Dominerande problemtyp: `{problem_mix['dominantProblem']}`.")


def view_system_health() -> None:
    st.title("System Health")
    st.caption(
        "Kör rimligt för scope: 'Snabb sanity' (focus_check + governance_validate) "
        "räcker för docs/policy-smala ändringar; 'Kör allt' är hela policy-sviten "
        "(governance_validate + rules-sync + term-coverage --strict + pytest -m "
        "governance). Plus en API-nyckel-kontroll för LLM-anrop."
    )

    c_quick, c_full = st.columns(2)
    if c_quick.button("Snabb sanity", key="sh_run_quick"):
        _hard_reset_caches()
        with st.spinner("Kör snabb sanity..."):
            st.session_state["health_results"] = [
                health.run_focus_check(),
                health.run_governance_validate(),
            ]
    if c_full.button("Kör allt", type="primary", key="sh_run_all"):
        _hard_reset_caches()
        with st.spinner("Kör hela policy-sviten..."):
            st.session_state["health_results"] = [
                health.run_governance_validate(),
                health.run_rules_sync_check(),
                health.run_term_coverage(strict=True),
                health.run_platform_baseline_check(),
                health.run_pytest_governance(),
            ]

    results: list[health.CheckResult] = st.session_state.get("health_results", [])
    if not results:
        st.info("Inga körningar än. Tryck 'Kör allt' för att börja.")
    else:
        cols = st.columns(len(results))
        for col, result in zip(cols, results, strict=True):
            col.metric(result.name, "OK" if result.ok else "FEL")
        st.divider()
        for result in results:
            render_check(result)
        st.divider()
        if any(not r.ok for r in results):
            if st.button("Försök fixa rules-sync (kör spegel-skript)", key="sh_apply_sync"):
                render_check(health.run_rules_sync_apply())

    st.divider()
    st.subheader("API-nycklar")
    from packages.generation.brief import has_openai_api_key

    openai_set = has_openai_api_key()
    anthropic_value = os.environ.get("ANTHROPIC_API_KEY")
    anthropic_set = bool(anthropic_value and anthropic_value.strip())
    a, b = st.columns(2)
    a.metric("OPENAI_API_KEY", "satt" if openai_set else "saknas")
    b.metric("ANTHROPIC_API_KEY", "satt" if anthropic_set else "saknas")
    st.caption(
        "Ingen nyckel echo-as. Saknad nyckel innebär att Playground och dev_generate.py "
        "faller tillbaka på mock-svar."
    )


def view_cross_policy() -> None:
    st.title("Cross-Policy Status")
    st.caption(
        "Realtidsstatus över konsistens mellan policies. Det här är vad "
        "pytest -m governance kontrollerar; samma logik visas här direkt."
    )

    needed = [
        "naming-dictionary.v1.json",
        "repo-boundaries.v1.json",
        "scaffold-contract.v1.json",
        "scaffold-selection.v1.json",
        "page-quality-traits.v1.json",
        "preview-runtime-policy.v1.json",
        "llm-flow-concepts.v1.json",
    ]
    bundle = {}
    missing = []
    for name in needed:
        p, err = loaders.safe_load_policy(name)
        if err or p is None:
            missing.append(f"{name}: {err}")
        else:
            bundle[name] = p
    if missing:
        for m in missing:
            st.error(m)
        return

    findings: list[tuple[bool, str]] = []

    nd = bundle["naming-dictionary.v1.json"]
    rb = bundle["repo-boundaries.v1.json"]
    sc = bundle["scaffold-contract.v1.json"]
    ss = bundle["scaffold-selection.v1.json"]
    pq = bundle["page-quality-traits.v1.json"]
    pr = bundle["preview-runtime-policy.v1.json"]
    flow = bundle["llm-flow-concepts.v1.json"]

    default_scaffold = ss["fallback"]["defaultScaffold"]
    registry_ids = {s["id"] for s in sc["primaryScaffoldRegistry"]}
    findings.append(
        (default_scaffold in registry_ids, f"defaultScaffold '{default_scaffold}' finns i registry")
    )

    qt = pq["qualityTarget"]
    findings.append(
        (
            qt["blockBelow"] <= qt["gateScore"] <= qt["targetScore"],
            f"qualityTarget thresholds: {qt['blockBelow']} <= {qt['gateScore']} <= {qt['targetScore']}",
        )
    )

    total_weight = sum(t["weight"] for t in pq["traits"])
    findings.append(
        (
            total_weight == pq["scoring"]["weightsTotal"],
            f"trait-vikter summerar till {total_weight} (förväntat {pq['scoring']['weightsTotal']})",
        )
    )

    phase_ids = [p["id"] for p in flow["phases"]]
    findings.append(
        (set(phase_ids) == set(flow["canonicalFlow"]), "canonicalFlow matchar phase ids")
    )

    pr_kinds = {r["kind"] for r in pr["runtimes"]}
    findings.append(
        (pr["default"] in pr_kinds, f"default Preview Runtime '{pr['default']}' finns i runtimes")
    )

    canonicals = [t["canonical"] for t in nd["terms"]]
    findings.append(
        (len(canonicals) == len(set(canonicals)), f"alla {len(canonicals)} kanoniska termer är unika")
    )

    boundary_paths = {o["path"].rstrip("/") for o in rb["ownership"]} | {"backoffice.py"}
    unknown_owners = [
        t["canonical"]
        for t in nd["terms"]
        if not any(t["ownerPackage"].startswith(p) for p in boundary_paths if p)
    ]
    findings.append(
        (
            not unknown_owners,
            "alla termer har ownerPackage i repo-boundaries"
            + (f" (avvikande: {unknown_owners})" if unknown_owners else ""),
        )
    )

    block_phase_ids: list[str] = []
    for block in flow.get("phaseBlocks", []):
        block_phase_ids.extend(block["phaseIds"])
    findings.append(
        (
            set(block_phase_ids) == set(phase_ids),
            "phaseBlocks täcker exakt alla phase ids",
        )
    )

    ok_count = sum(1 for ok, _ in findings if ok)
    st.metric("Status", f"{ok_count}/{len(findings)}")

    for ok, msg in findings:
        if ok:
            st.success(msg)
        else:
            st.error(msg)


VIEWS = {
    "Idag": lambda: safe_render(view_today),
    "Översikt": lambda: safe_render(view_overview),
    "Golden Path": lambda: safe_render(view_golden_path_status),
    "System Health": lambda: safe_render(view_system_health),
    "Cross-Policy Status": lambda: safe_render(view_cross_policy),
}
