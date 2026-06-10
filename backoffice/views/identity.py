"""Identitet-block: dirigentens SOUL (redigerbar) + TOOLS (read-only).

ADR 0044. Operatörens redigeringsyta för dirigentens konstitution
(``docs/openclaw-workspace/SOUL.md``) — som en reguljär OpenClaw-workspace, men
för vår in-process-dirigent. Chatt-personan i
``apps/viewser/app/api/prompt/route.ts`` laddar SOUL server-side.

Säkerhetsräcken (hårda):
- Editorn skriver ENDAST ``SOUL.md`` via ett path-lås (``SOUL_PATH``). Ingen
  fri filskrivning, ingen path-input från UI:t.
- Max-längd (``SOUL_MAX_CHARS``) och tom-text avvisas innan write.
- ``TOOLS.md`` visas read-only (sanktionerade actions bor i kod/governance).
- Ingen git-commit sker härifrån; operatören committar som vanligt.
"""

from __future__ import annotations

import streamlit as st

from ..io import atomic_write_text
from ..paths import DOCS_DIR
from ._helpers import safe_render

# Path-lås: OpenClaw-workspacen är den enda ytan editorn får röra. SOUL_PATH är
# det enda write-målet; TOOLS_PATH läses read-only.
OPENCLAW_WORKSPACE_DIR = DOCS_DIR / "openclaw-workspace"
SOUL_PATH = OPENCLAW_WORKSPACE_DIR / "SOUL.md"
TOOLS_PATH = OPENCLAW_WORKSPACE_DIR / "TOOLS.md"

# Speglar takets-tanken på runtime-sidan (lib/soul.ts trunkerar basen): en
# konstitution ska vara kort och läsbar, inte en roman. Skydd mot oavsiktlig
# klistra-in-en-hel-fil.
SOUL_MAX_CHARS = 8000


def _save_soul(new_text: str) -> None:
    """Skriv SOUL.md path-låst, med max-längd och tom-text-skydd."""
    if not new_text.strip():
        st.error("SOUL.md får inte vara tom. Inget sparat.")
        return
    if len(new_text) > SOUL_MAX_CHARS:
        st.error(
            f"SOUL.md är för lång ({len(new_text)} tecken). "
            f"Max {SOUL_MAX_CHARS} tecken. Inget sparat."
        )
        return
    try:
        atomic_write_text(SOUL_PATH, new_text)
    except OSError as exc:
        st.error(f"Kunde inte skriva SOUL.md: {exc}. Inget har ändrats.")
        return

    # Backoffice-cachen läser via mtime, men chatt-personan cacheas per process
    # i Node — påminn operatören att starta om dev-servern.
    from .. import loaders

    loaders.read_text.clear()
    st.success(
        "Sparat till docs/openclaw-workspace/SOUL.md. Chatt-personan cacheas "
        "per process i Viewser — starta om dev-servern så den laddar om. "
        "Ingen git-commit har skett; committa ändringen som vanligt."
    )


def view_identity() -> None:
    st.title("Identitet (SOUL)")
    st.caption(
        "Dirigentens konstitution: mål, får/får-inte, ärlighet och "
        "kontextnivåer. Speglar en OpenClaw-workspace men för vår "
        "in-process-dirigent. Läses server-side av chatt-personan (ADR 0044)."
    )
    st.warning(
        "Den här texten är persona-bas för chatten i ALLA sajter. En ändring "
        "påverkar varje sajts dirigent-svar (ton + persona) — inte "
        "byggreglerna (de bor i kod och governance, inte i prosa). Ingen "
        "git-commit sker härifrån; committa som vanligt."
    )

    if not SOUL_PATH.exists():
        st.error(f"SOUL.md saknas på {SOUL_PATH}.")
        return

    current = SOUL_PATH.read_text(encoding="utf-8")

    tab_edit, tab_preview, tab_tools = st.tabs(
        ["Redigera SOUL", "Förhandsvisa", "TOOLS (read-only)"]
    )

    with tab_edit:
        new_text = st.text_area(
            "SOUL.md",
            value=current,
            height=560,
            key="identity-soul-edit",
        )
        st.caption(f"{len(new_text)} / {SOUL_MAX_CHARS} tecken.")
        if st.button("Spara SOUL.md", key="identity-soul-save"):
            _save_soul(new_text)
        st.session_state["identity-soul-preview"] = new_text

    with tab_preview:
        preview_text = st.session_state.get("identity-soul-preview", current)
        st.markdown(preview_text)

    with tab_tools:
        st.caption(
            "Sanktionerade actions (read-only). Redigeras i kod/governance, "
            "inte härifrån — TOOLS är behörighet, inte persona."
        )
        if TOOLS_PATH.exists():
            st.markdown(TOOLS_PATH.read_text(encoding="utf-8"))
        else:
            st.info(f"TOOLS.md saknas på {TOOLS_PATH}.")


VIEWS = {
    "Identitet (SOUL)": lambda: safe_render(view_identity),
}
