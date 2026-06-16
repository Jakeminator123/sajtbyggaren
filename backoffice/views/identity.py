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
from ._editor import commit_edit, make_readback_verify, render_diff
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


def _soul_validation_errors(new_text: str) -> list[str]:
    """Tom-text- och max-längd-spärr för SOUL.md (samma regel före write och
    vid återläsnings-verifiering). Tom lista = får sparas."""
    errors: list[str] = []
    if not new_text.strip():
        errors.append("SOUL.md får inte vara tom. Inget sparat.")
    if len(new_text) > SOUL_MAX_CHARS:
        errors.append(
            f"SOUL.md är för lång ({len(new_text)} tecken). "
            f"Max {SOUL_MAX_CHARS} tecken. Inget sparat."
        )
    return errors


def _save_soul(new_text: str) -> None:
    """Skriv SOUL.md path-låst, med max-längd och tom-text-skydd.

    Går via den delade säkra spar-vägen (``_editor.commit_edit``): validera ->
    atomic write till den path-låsta ``SOUL_PATH`` -> återläsnings-verifiering
    -> rollback om filen blev tom/för lång på disk. Skrivmålet är ALLTID
    konstanten ``SOUL_PATH``; ingen fri path-input kan omdirigera skrivningen.
    """
    result = commit_edit(
        target=SOUL_PATH,
        validate=lambda: _soul_validation_errors(new_text),
        write=lambda: atomic_write_text(SOUL_PATH, new_text),
        verify=make_readback_verify(SOUL_PATH, _soul_validation_errors),
        success_message=(
            "Sparat till docs/openclaw-workspace/SOUL.md. Chatt-personan cacheas "
            "per process i Viewser — starta om dev-servern så den laddar om. "
            "Ingen git-commit har skett; committa ändringen som vanligt."
        ),
        write_error_message=lambda exc: (
            f"Kunde inte skriva SOUL.md: {exc}. Inget har ändrats."
        ),
        rollback_message=lambda output: (
            f"SOUL.md blev ogiltig på disk efter spara - rollback genomfört. {output}"
        ),
    )
    if result.ok:
        # Backoffice-cachen läser via mtime, men chatt-personan cacheas per
        # process i Node — påminn operatören att starta om dev-servern.
        from .. import loaders

        loaders.read_text.clear()
        st.success(result.message)
    else:
        st.error(result.message)


# Runtime-trunkeringen i apps/viewser/lib/soul.ts: allt över denna gräns når
# aldrig chatt-personan. Speglas här så editorerna kan varna ärligt.
SOUL_RUNTIME_MAX_CHARS = 3500


def render_soul_editor(*, key_prefix: str = "identity") -> None:
    """Delad SOUL-editor (redigera/förhandsvisa/TOOLS read-only).

    All skrivlogik (path-lås, caps, varningar) bor i den här modulen — andra
    vyer (Dirigentpulten) återanvänder renderaren med eget ``key_prefix`` i
    stället för att duplicera den. Skrivmålet är alltid den path-låsta
    ``SOUL_PATH``-konstanten via ``_save_soul``.
    """
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
            key=f"{key_prefix}-soul-edit",
        )
        st.caption(
            f"{len(new_text)} / {SOUL_MAX_CHARS} tecken (editor-cap). "
            f"Runtime trunkerar till {SOUL_RUNTIME_MAX_CHARS} tecken "
            "(apps/viewser/lib/soul.ts) — text därefter når aldrig chatten."
        )
        if len(new_text) > SOUL_RUNTIME_MAX_CHARS:
            st.warning(
                f"Texten är {len(new_text)} tecken — allt efter tecken "
                f"{SOUL_RUNTIME_MAX_CHARS} klipps bort av runtime innan "
                "chatt-personan ser den."
            )
        render_diff(current, new_text, key=f"{key_prefix}-soul-diff")
        if st.button("Spara SOUL.md", key=f"{key_prefix}-soul-save"):
            _save_soul(new_text)
        st.session_state[f"{key_prefix}-soul-preview"] = new_text

    with tab_preview:
        preview_text = st.session_state.get(f"{key_prefix}-soul-preview", current)
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


def view_identity() -> None:
    st.title("Identitet (SOUL)")
    st.caption(
        "Dirigentens konstitution: mål, får/får-inte, ärlighet och "
        "kontextnivåer. Speglar en OpenClaw-workspace men för vår "
        "in-process-dirigent. Läses server-side av chatt-personan (ADR 0044)."
    )
    render_soul_editor(key_prefix="identity")


VIEWS = {
    "Identitet (SOUL)": lambda: safe_render(view_identity),
}
