"""LLM Engine-block: Mindmap, Init Flow, Follow-up Flow, Model Roles, Fix Types, Embeddings."""

from __future__ import annotations

import json

import streamlit as st

from .. import loaders
from ..mermaid import (
    build_engine_mindmap,
    build_followup_flow_diagram,
    build_init_flow_diagram,
    render_mermaid,
)
from ..paths import POLICIES_DIR
from ._helpers import safe_render


def _hard_reset_caches() -> None:
    loaders.load_json.clear()
    loaders.read_text.clear()


def view_mindmap() -> None:
    st.title("Mindmap - hela LLM-kedjan")
    st.caption(
        "Diagram genereras dynamiskt från `llm-flow-concepts`, `llm-models` och "
        "`engine-run`. Editera dessa policies så uppdateras diagrammet automatiskt."
    )

    flow, err = loaders.safe_load_policy("llm-flow-concepts.v1.json")
    if err or flow is None:
        st.error(err)
        return
    models, err = loaders.safe_load_policy("llm-models.v1.json")
    if err or models is None:
        st.error(err)
        return
    engine_run, err = loaders.safe_load_policy("engine-run.v1.json")
    if err or engine_run is None:
        st.error(err)
        return

    diagram = build_engine_mindmap(flow, models, engine_run)
    render_mermaid(diagram, height=900)

    with st.expander("Visa mermaid-källkod"):
        st.code(diagram, language="text")


def view_init_flow() -> None:
    st.title("Init Flow")
    st.caption(
        "init-mode skapar ett nytt projekt och lagrar Project DNA. Detta diagram "
        "visar alla phases plus Project DNA-skapandet i slutet."
    )
    flow, err = loaders.safe_load_policy("llm-flow-concepts.v1.json")
    if err or flow is None:
        st.error(err)
        return
    dna, err = loaders.safe_load_policy("project-dna.v1.json")
    if err or dna is None:
        st.error(err)
        return
    diagram = build_init_flow_diagram(flow, dna)
    render_mermaid(diagram, height=700)
    with st.expander("Visa mermaid-källkod"):
        st.code(diagram, language="text")


def view_followup_flow() -> None:
    st.title("Follow-up Flow")
    st.caption(
        "followup-mode läser befintlig Project DNA och klassificerar FollowUp Intent. "
        "Implementation kommer; nu visas planerad design."
    )
    dna, err = loaders.safe_load_policy("project-dna.v1.json")
    if err or dna is None:
        st.error(err)
        return
    diagram = build_followup_flow_diagram(dna)
    render_mermaid(diagram, height=700)
    with st.expander("Visa FollowUp Intents"):
        for intent in dna.get("followUpIntents", []):
            st.markdown(
                f"**{intent['id']}** - {intent['purpose']}  "
                f"\nscaffold: `{intent['scaffold']}` · variant: `{intent['variant']}` · "
                f"dossiers: `{intent['dossiers']}` · routes: `{intent['routes']}`"
            )
    with st.expander("Visa mermaid-källkod"):
        st.code(diagram, language="text")


def view_model_roles() -> None:
    st.title("Model Roles")
    models, err = loaders.safe_load_policy("llm-models.v1.json")
    if err or models is None:
        st.error(err)
        return

    st.caption(models.get("purpose", ""))

    role_to_group = {}
    for group in models.get("sharedModelGroups", []):
        for role_id in group["roles"]:
            role_to_group[role_id] = group["groupId"]

    rows = []
    for role in models.get("roles", []):
        rows.append(
            {
                "Roll": role.get("id"),
                "Modell": role.get("model"),
                "Provider": role.get("provider"),
                "Grupp": role_to_group.get(role.get("id"), "?"),
                "Syfte": role.get("purpose"),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Redigera modell per roll")
    st.caption(
        "Edit-mode skriver till `llm-models.v1.json` direkt. JSON valideras före spara."
    )

    edit_mode = st.toggle("Aktivera redigering", key="model_edit_toggle")
    if not edit_mode:
        return

    role_ids = [r["id"] for r in models.get("roles", [])]
    selected_role = st.selectbox("Välj roll", role_ids, key="model_role_select")
    role = next((r for r in models["roles"] if r["id"] == selected_role), None)
    if not role:
        return

    new_model = st.text_input("Modell", value=role.get("model", ""), key="model_input")
    new_provider = st.text_input("Provider", value=role.get("provider", "openai"), key="provider_input")

    if st.button("Spara ändringen", key="model_save"):
        for r in models["roles"]:
            if r["id"] == selected_role:
                r["model"] = new_model
                r["provider"] = new_provider
                break
        path = POLICIES_DIR / "llm-models.v1.json"
        backup = path.read_text(encoding="utf-8")
        try:
            path.write_text(
                json.dumps(models, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            _hard_reset_caches()
            st.success(f"Sparade {selected_role} -> {new_model} ({new_provider}).")
            st.info("Verifiera i System Health att governance_validate fortfarande passerar.")
        except Exception as exc:
            path.write_text(backup, encoding="utf-8")
            st.error(f"Misslyckades, rollback: {exc}")


def view_fix_types() -> None:
    st.title("Fix Types")
    fixes, err = loaders.safe_load_policy("fix-registry.v1.json")
    if err or fixes is None:
        st.error(err)
        return
    st.caption(fixes.get("purpose", ""))

    st.subheader("Mekaniska fixar (deterministiska, körs först)")
    mech_rows = [
        {
            "id": f.get("id"),
            "stage": f.get("stage"),
            "syfte": f.get("purpose"),
        }
        for f in fixes.get("mechanicalFixes", [])
    ]
    st.dataframe(mech_rows, use_container_width=True, hide_index=True)

    st.subheader("LLM-fixar (triggas vid specifika fel)")
    llm_rows = [
        {
            "id": f.get("id"),
            "trigger": f.get("trigger"),
            "modelRole": f.get("modelRole"),
            "syfte": f.get("purpose"),
        }
        for f in fixes.get("llmFixes", [])
    ]
    st.dataframe(llm_rows, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Principer**")
    for p in fixes.get("principles", []):
        st.write(f"- {p}")


def view_embeddings() -> None:
    st.title("Embeddings")
    emb, err = loaders.safe_load_policy("embedding-policy.v1.json")
    if err or emb is None:
        st.error(err)
        return
    models, err = loaders.safe_load_policy("llm-models.v1.json")
    if err or models is None:
        st.error(err)
        return

    st.caption(emb.get("purpose", ""))

    embedding_model = next(
        (r for r in models.get("roles", []) if r["id"] == emb.get("embeddingModelRole")),
        None,
    )
    if embedding_model:
        st.info(
            f"Embedding-modell (rollen `{embedding_model['id']}`): "
            f"`{embedding_model['model']}` via `{embedding_model['provider']}`"
        )

    rows = [
        {
            "Domän": d["id"],
            "Syfte": d["purpose"],
            "Indexed from": d["indexedFrom"],
            "Top-K": d["topKDefault"],
            "Min score": d["minScoreDefault"],
            "Konsumeras av roller": ", ".join(d["consumedByRoles"]),
            "Konsumeras i phases": ", ".join(d["consumedByPhases"]),
        }
        for d in emb.get("domains", [])
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Principer**")
    for p in emb.get("principles", []):
        st.write(f"- {p}")


VIEWS = {
    "Mindmap": lambda: safe_render(view_mindmap),
    "Init Flow": lambda: safe_render(view_init_flow),
    "Follow-up Flow": lambda: safe_render(view_followup_flow),
    "Model Roles": lambda: safe_render(view_model_roles),
    "Fix Types": lambda: safe_render(view_fix_types),
    "Embeddings": lambda: safe_render(view_embeddings),
}
