"""Dirigentpult - överordnad styrsida som samlar dirigentens alla kontroller.

EN sammanhållen cockpit (flikar A-G) för det som tidigare låg utspritt:

  A) Modeller per roll  - redigera ``llm-models.v1.json`` (delad save-väg).
  B) Chatt-/sidomodeller - ENV-styrda modeller, read-only + vägledning.
  C) Persona (SOUL)      - den path-låsta SOUL-editorn (återanvänd).
  D) Sanktionerade actions - action-registry.json, status-redigering med
     ärlighetsbanner (status speglar kodstöd, togglar ingen förmåga).
  E) Skills              - förmågekort (text, inte behörighet).
  F) Konduktör-roller    - ROLE_CONTRACTS read-only.
  G) Priser & gränser    - pris-snapshot read-only + refresh-knapp.

Designprinciper (ADR 0002 + governance/rules/09):

- ÅTERANVÄND, duplicera inte: modell-save går via ``backoffice.model_roles``
  (samma väg som LLM Engine-vyn), SOUL-editorn via
  ``identity.render_soul_editor`` - logiken bor kvar i sina moduler.
- ÄRLIGHET: ingen kontroll låtsas aktivera något som koden inte stöder.
  Action-status är dokumentation av kodstöd; konduktör-rollerna är frysta
  dataclasses och visas read-only; priser visas bara när de faktiskt
  hämtats (needsRefresh-flaggan döljs aldrig).
- PATH-LÅS: de enda skrivmålen är policy-filen (via model_roles),
  SOUL_PATH (via identity), ACTION_REGISTRY_PATH och SKILL.md-filer
  upptäckta under SKILLS_DIR. Ingen fri path-input från UI:t.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from .. import health, loaders, model_roles, runtime_models
from ..env_panel import read_non_secret_env
from ..io import atomic_write_json, atomic_write_text
from ..paths import DATA_DIR
from ._helpers import render_check, safe_render
from .identity import (
    OPENCLAW_WORKSPACE_DIR,
    SOUL_MAX_CHARS,
    SOUL_PATH,
    SOUL_RUNTIME_MAX_CHARS,
    render_soul_editor,
)
from .llm_engine import render_model_roles_editor

# Path-lås: Dirigentpultens skrivbara ytor utanför governance-policyn.
ACTION_REGISTRY_PATH = OPENCLAW_WORKSPACE_DIR / "action-registry.json"
SKILLS_DIR = OPENCLAW_WORKSPACE_DIR / "skills"
PRICING_SNAPSHOT_PATH = DATA_DIR / "model-pricing.json"

# Giltiga action-statusar (samma enum som action-registry.json dokumenterar).
ACTION_STATUSES = ("supported", "partial", "planned")

# Cap för skill-text: ett förmågekort ska vara kort och läsbart (samma
# klistra-in-skydd som SOUL-editorns cap).
SKILL_MAX_CHARS = 12000

_STATUS_BADGES = {"supported": "✅", "partial": "🟡", "planned": "🧭"}


def _badge(status: str) -> str:
    return f"{_STATUS_BADGES.get(status, '❓')} {status}"


def _price_cell(value: object) -> str:
    """Enhetlig strängcell för priser: tal -> str, saknat -> em-dash.

    Strängar hela vägen så st.dataframe-kolumnen får EN typ (annars klagar
    Arrow-serialiseringen på blandade float/str-kolumner)."""
    if value is None:
        return "—"
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _load_json_file(path: Path) -> tuple[dict | None, str | None]:
    """Läs en JSON-fil defensivt: (data, fel). Aldrig exception till UI:t."""
    if not path.exists():
        return None, f"{path.name} saknas på {path}."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Kunde inte läsa {path.name}: {exc}"
    if not isinstance(data, dict):
        return None, f"{path.name} har oväntad form (förväntade objekt)."
    return data, None


def list_skills() -> list[str]:
    """Skill-namn = katalognamn under skills/ som innehåller SKILL.md."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        child.name
        for child in SKILLS_DIR.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )


def skill_path(skill_name: str) -> Path:
    """Path-låst uppslag: namnet MÅSTE komma från list_skills()-scannen."""
    if skill_name not in list_skills():
        raise ValueError(f"Okänd skill '{skill_name}' - finns inte under {SKILLS_DIR}.")
    return SKILLS_DIR / skill_name / "SKILL.md"


def _age_label(iso_timestamp: str | None) -> str:
    """Svensk ålders-etikett för en ISO-tidsstämpel ('3 timmar sedan')."""
    if not iso_timestamp:
        return "aldrig"
    try:
        then = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp
    delta = datetime.now(UTC) - then
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "nyss"
    if minutes < 60:
        return f"{minutes} min sedan"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} h sedan"
    return f"{hours // 24} dagar sedan"


# ----- flik A: modeller per roll ---------------------------------------------


def _render_tab_models(models: dict, pricing: dict | None) -> None:
    st.subheader("A · Modeller per roll (motorn)")
    st.caption(
        "Motorns 12 Model Roles ur `llm-models.v1.json`. Varje roll är den enda "
        "vägen till ett LLM-anrop i pipelinen - att byta modell/provider här "
        "ändrar motorns beteende för ALLA byggen. Byte är en policy-bump: höj "
        "`version` i policyn i samma ändring (redigeras under Governance / "
        "Policies). Spara-knappen validerar med governance-validate och rullar "
        "tillbaka vid fel - samma delade save-väg som LLM Engine / Model Roles."
    )

    price_by_model: dict[str, dict] = {}
    if pricing:
        price_by_model = {
            row.get("model"): row
            for row in pricing.get("models", [])
            if isinstance(row, dict)
        }

    role_to_group = model_roles.role_group_map(models)
    rows = []
    for role in models.get("roles", []):
        price = price_by_model.get(role.get("model"), {})
        rows.append(
            {
                "Roll": role.get("id"),
                "Modell": role.get("model"),
                "Provider": role.get("provider"),
                "Grupp": role_to_group.get(role.get("id"), "?"),
                "USD/1M in": _price_cell(price.get("inputPer1M")),
                "USD/1M ut": _price_cell(price.get("outputPer1M")),
                "Syfte": role.get("purpose"),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption(
        "Priser från pris-snapshotten (flik G). Grupperna i `sharedModelGroups` "
        "visar vilka roller som medvetet delar modell."
    )
    render_model_roles_editor(models, key_prefix="control-room")


# ----- flik B: chatt- & sidomodeller (ENV) -----------------------------------


def _render_tab_env_models() -> None:
    st.subheader("B · Chatt- & sidomodeller (ENV, read-only)")
    st.caption(
        "De här tre modellerna styrs av MILJÖVARIABLER - inte av "
        "`llm-models.v1.json`. Resolutionsordning: process-env vinner, sedan "
        "repo-rotens `.env` (och för Viewser även `apps/viewser/.env.local`, "
        "som Next-dev-servern läser men som inte syns här). Defaultvärdet "
        "parsas LIVE ur källfilen, så den här fliken kan inte driva när "
        "fallbacken byts i koden. Ändra genom att sätta env-variabeln + "
        "starta om dev-servern."
    )

    surfaces = (
        (
            "Viewser-chatt",
            runtime_models.CHAT_MODEL_ENV,
            runtime_models.chat_model_default(),
            "apps/viewser/lib/openai.ts",
        ),
        (
            "Vision (bildklassning)",
            runtime_models.VISION_MODEL_ENV,
            runtime_models.vision_model_default(),
            "apps/viewser/lib/asset-store/vision.ts",
        ),
        (
            "Discovery (URL-scrape)",
            runtime_models.DISCOVERY_MODEL_ENV,
            runtime_models.discovery_model_default(),
            "scripts/scrape_site.py",
        ),
    )

    rows = []
    for label, env_name, parsed_default, source in surfaces:
        env_value = read_non_secret_env(env_name)
        active = env_value or parsed_default or "okänd (kunde inte läsas ur källan)"
        rows.append(
            {
                "Yta": label,
                "Env-variabel": env_name,
                "Aktivt värde": active,
                "Källa": "env" if env_value else "default ur källkod",
                "Defaultens hem": source,
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    _render_router_fallback_toggle()

    st.markdown("**Chattens gränser** (`apps/viewser/lib/openai.ts`)")
    limits = runtime_models.chat_limits()
    chat_tokens_env = read_non_secret_env(runtime_models.CHAT_TOKENS_ENV)
    a, b, c = st.columns(3)
    a.metric(
        "Max svarstokens",
        chat_tokens_env or str(limits["maxOutputTokensDefault"] or "okänd"),
        help=(
            "Antal tokens modellen får generera per svar. Default "
            f"{limits['maxOutputTokensDefault']}; override via env "
            f"{runtime_models.CHAT_TOKENS_ENV}."
        ),
    )
    b.metric(
        "Max tecken/meddelande",
        str(limits["maxInputCharsPerMessage"] or "okänd"),
        help="Hård gräns per chattmeddelande - längre meddelanden avvisas.",
    )
    c.metric(
        "Max meddelanden/request",
        str(limits["maxMessagesPerRequest"] or "okänd"),
        help="Hård gräns för hur lång historik som skickas per anrop.",
    )
    if chat_tokens_env:
        st.caption(
            f"{runtime_models.CHAT_TOKENS_ENV} är satt i env och overridar defaulten."
        )


def _render_router_fallback_toggle() -> None:
    """Manövrera KÖR-6b-switchen (routerns LLM-fallback i OpenClaw-bryggan).

    Skrivmålet är path-låst till repo-rotens .env via env_panel.write_router_
    fallback (atomisk; rör aldrig andra rader/nycklar). Ärlighet: effekten
    gäller NÄSTA följdprompt-spawn, och en process-env-satt variabel (t.ex.
    satt i shellet före `npm run dev`) vinner alltid tills servern startas om.
    """
    from ..env_panel import router_fallback_state, write_router_fallback

    with st.container(border=True):
        st.markdown("**Router-LLM-fallback (KÖR-6b)** — OpenClaw-bryggans grind")
        enabled, source = router_fallback_state()
        st.caption(
            "Deterministisk KÖR-6a-heuristik först; tvetydiga/långa "
            "följdprompter eskaleras till routerModel när detta är PÅ "
            "(default). AV = ren regex-routing, inga LLM-anrop i grinden. "
            f"Effektivt läge just nu: **{'PÅ' if enabled else 'AV'}** "
            f"(källa: {source}). Ändringen skrivs till repo-rotens `.env` och "
            "gäller från NÄSTA följdprompt. OBS: är variabeln satt i process-"
            "env (shell/dev-serverstart) vinner den tills dev-servern startas "
            "om — källan ovan visar vilket."
        )
        desired = st.toggle(
            "LLM-fallback på (rekommenderad)",
            value=enabled,
            key="cr-router-fallback-toggle",
        )
        if st.button("Spara till .env", key="cr-router-fallback-save"):
            try:
                write_router_fallback(desired)
            except OSError as exc:
                st.error(f"Kunde inte skriva .env: {exc}. Inget har ändrats.")
            else:
                st.success(
                    f"Sparade OPENCLAW_ROUTER_LLM_FALLBACK={'1' if desired else '0'} "
                    "till repo-rotens .env. Gäller nästa följdprompt (process-env "
                    "vinner tills omstart om den är satt där). Ingen git-commit — "
                    ".env är gitignorad."
                )


# ----- flik C: persona (SOUL) -------------------------------------------------


def _render_tab_soul() -> None:
    st.subheader("C · Persona (SOUL)")
    st.caption(
        "Dirigentens konstitution - chatt-personans bas i ALLA sajter "
        "(ADR 0044). Styr TON och persona, ALDRIG byggbeteende (byggreglerna "
        "bor i kod + governance). Samma path-låsta editor som Identitet-vyn; "
        f"editor-cap {SOUL_MAX_CHARS} tecken, runtime trunkerar till "
        f"{SOUL_RUNTIME_MAX_CHARS} tecken (apps/viewser/lib/soul.ts)."
    )
    render_soul_editor(key_prefix="control-room")


# ----- flik D: sanktionerade actions (TOOLS) ----------------------------------


def _role_contract_status_by_edit_kind() -> dict[str, str]:
    """routerEditKind -> ROLE_CONTRACTS-status (för ärlighets-korskollen)."""
    from packages.generation.orchestration.openclaw.roles import (
        ROLE_CONTRACTS,
        role_for_edit_kind,
    )

    mapping: dict[str, str] = {}
    for contract in ROLE_CONTRACTS.values():
        for edit_kind in contract.acceptsEditKinds:
            role = role_for_edit_kind(edit_kind)
            if role is not None:
                mapping[edit_kind] = ROLE_CONTRACTS[role].status
    return mapping


def _save_action_status(registry: dict, action_id: str, new_status: str) -> None:
    """Skriv ny status för EN action, path-låst till ACTION_REGISTRY_PATH."""
    if new_status not in ACTION_STATUSES:
        st.error(f"Ogiltig status '{new_status}'. Tillåtna: {ACTION_STATUSES}.")
        return
    updated = json.loads(json.dumps(registry))  # deep copy utan extra imports
    action = next(
        (a for a in updated.get("actions", []) if a.get("id") == action_id), None
    )
    if action is None:
        st.error(f"Action '{action_id}' finns inte i registret.")
        return
    action["status"] = new_status
    try:
        atomic_write_json(ACTION_REGISTRY_PATH, updated)
    except OSError as exc:
        st.error(f"Kunde inte skriva action-registry.json: {exc}. Inget har ändrats.")
        return
    loaders.read_text.clear()
    loaders.load_json.clear()
    st.success(
        f"Sparade {action_id} -> {new_status}. Kom ihåg: detta dokumenterar "
        "kodstöd - det aktiverar ingen förmåga. Ingen git-commit har skett; "
        "committa som vanligt."
    )


def _render_tab_actions() -> None:
    st.subheader("D · Sanktionerade actions (TOOLS)")
    st.warning(
        "Status här SPEGLAR kodstöd - den togglar inte på faktisk förmåga. "
        "Att sätta en action till supported gör den INTE byggbar: en action "
        "körs bara om den har en riktig apply-väg i koden. Att flippa status "
        "utan kodstöd kräver kodstöd först (hård princip, governance/rules/09)."
    )
    st.caption(
        "Registret `docs/openclaw-workspace/action-registry.json` listar de "
        "sanktionerade actions dirigenten får köra och deras ärliga mognad. "
        "Behörigheten bor i KOD/governance; TOOLS.md nedan är read-only."
    )

    registry, err = _load_json_file(ACTION_REGISTRY_PATH)
    if err or registry is None:
        st.error(err)
        return

    contract_status = _role_contract_status_by_edit_kind()
    rows = []
    mismatches: list[str] = []
    for action in registry.get("actions", []):
        edit_kind = action.get("routerEditKind", "")
        role_status = contract_status.get(edit_kind)
        if role_status is not None and role_status != action.get("status"):
            mismatches.append(
                f"{action.get('id')}: registret säger '{action.get('status')}' men "
                f"konduktör-rollen för {edit_kind} säger '{role_status}'"
            )
        rows.append(
            {
                "Action": action.get("id"),
                "Status": _badge(action.get("status", "?")),
                "Router editKind": edit_kind,
                "Mount-only": "ja" if action.get("mountOnly") else "nej",
                "Roll-kontrakt": role_status or "—",
                "Skill": action.get("skill", ""),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption("Legend: ✅ supported · 🟡 partial · 🧭 planned · — ingen roll äger editKind.")

    for mismatch in mismatches:
        st.warning(
            f"Status-drift mot ROLE_CONTRACTS (kodet): {mismatch}. Registret "
            "ska spegla koden - rätta registret eller landa kodstödet."
        )

    with st.container(border=True):
        st.markdown("**Redigera action-status** (dokumentation av kodstöd, inget mer)")
        action_ids = [a.get("id") for a in registry.get("actions", []) if a.get("id")]
        if not action_ids:
            st.info("Inga actions i registret.")
        else:
            col_action, col_status = st.columns(2)
            selected_action = col_action.selectbox(
                "Action", action_ids, key="cr-action-select"
            )
            current = next(
                (
                    a.get("status")
                    for a in registry.get("actions", [])
                    if a.get("id") == selected_action
                ),
                "planned",
            )
            new_status = col_status.selectbox(
                "Status (speglar kodstöd)",
                ACTION_STATUSES,
                index=ACTION_STATUSES.index(current) if current in ACTION_STATUSES else 2,
                key="cr-action-status",
            )
            if new_status == "supported" and current != "supported":
                st.warning(
                    "Du är på väg att märka en action som supported. Det kräver "
                    "kodstöd (riktig apply-väg) - registret gör den inte byggbar."
                )
            if st.button("Spara action-status", key="cr-action-save"):
                _save_action_status(registry, selected_action, new_status)

    with st.expander("TOOLS.md (read-only)"):
        tools_path = OPENCLAW_WORKSPACE_DIR / "TOOLS.md"
        if tools_path.exists():
            st.markdown(tools_path.read_text(encoding="utf-8"))
        else:
            st.info(f"TOOLS.md saknas på {tools_path}.")


# ----- flik E: skills ----------------------------------------------------------


def _save_skill(skill_name: str, new_text: str) -> None:
    """Skriv EN skill-fil, path-låst via skill_path(); caps + tom-text-skydd."""
    if not new_text.strip():
        st.error("SKILL.md får inte vara tom. Inget sparat.")
        return
    if len(new_text) > SKILL_MAX_CHARS:
        st.error(
            f"SKILL.md är för lång ({len(new_text)} tecken). "
            f"Max {SKILL_MAX_CHARS} tecken. Inget sparat."
        )
        return
    try:
        target = skill_path(skill_name)
    except ValueError as exc:
        st.error(str(exc))
        return
    try:
        atomic_write_text(target, new_text)
    except OSError as exc:
        st.error(f"Kunde inte skriva SKILL.md: {exc}. Inget har ändrats.")
        return
    loaders.read_text.clear()
    st.success(
        f"Sparat till docs/openclaw-workspace/skills/{skill_name}/SKILL.md. "
        "Ingen git-commit har skett; committa som vanligt."
    )


def _render_tab_skills() -> None:
    st.subheader("E · Skills (förmågekort)")
    st.caption(
        "En skill är TEXT, inte behörighet: förmågekortet beskriver HUR en "
        "redan sanktionerad action ska utföras, men texten ändrar inte vad "
        "motorn kan göra. En action körs bara om den (1) är sanktionerad i "
        "TOOLS/registret, (2) har en apply-väg i kod och (3) klassas av "
        "routern - saknas något blir det en ärlig no-op."
    )

    skills = list_skills()
    if not skills:
        st.info(f"Inga skills hittade under {SKILLS_DIR}.")
        return

    selected_skill = st.selectbox("Välj skill", skills, key="cr-skill-select")
    current_text = skill_path(selected_skill).read_text(encoding="utf-8")

    tab_read, tab_edit = st.tabs(["Läs", "Redigera (text)"])
    with tab_read:
        st.markdown(current_text)
    with tab_edit:
        new_text = st.text_area(
            f"skills/{selected_skill}/SKILL.md",
            value=current_text,
            height=420,
            key=f"cr-skill-edit-{selected_skill}",
        )
        st.caption(
            f"{len(new_text)} / {SKILL_MAX_CHARS} tecken. Texten är vägledning "
            "för rollen som kör skillen - inte en behörighetsyta."
        )
        if st.button("Spara SKILL.md", key=f"cr-skill-save-{selected_skill}"):
            _save_skill(selected_skill, new_text)


# ----- flik F: konduktör-roller -------------------------------------------------


def _render_tab_roles() -> None:
    st.subheader("F · Konduktör-roller (read-only)")
    st.caption(
        "Rollkontrakten är FRYSTA dataclasses i "
        "`packages/generation/orchestration/openclaw/roles.py` - de visas "
        "read-only och kan aldrig redigeras härifrån. En kontraktsändring är "
        "en kod-PR, inte en UI-handling. Rollen FÖRSTÅR och föreslår; den "
        "deterministiska apply-kedjan validerar och applicerar."
    )

    from packages.generation.orchestration.openclaw.roles import ROLE_CONTRACTS

    rows = []
    for contract in ROLE_CONTRACTS.values():
        rows.append(
            {
                "Roll": contract.role,
                "Status": _badge(contract.status),
                "Tar emot editKinds": ", ".join(contract.acceptsEditKinds) or "—",
                "Producerar direktiv": ", ".join(contract.producesDirectives) or "—",
                "Kontextnivå": contract.contextLevel,
                "Mount-only": "ja" if contract.mountOnly else "nej",
                "Kör skill": contract.skill or "— (dispatcher)",
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    for contract in ROLE_CONTRACTS.values():
        with st.expander(f"{contract.role} - sammanfattning"):
            st.write(contract.summary)


# ----- flik G: priser & gränser -------------------------------------------------


def _render_tab_pricing(models: dict) -> None:
    st.subheader("G · Priser & gränser")
    st.caption(
        "Tokenpriser (USD per 1M tokens) ur snapshotten `data/model-pricing.json` "
        "- READ-ONLY här. Snapshotten skrivs ENBART av "
        "`scripts/fetch_model_prices.py`, som hämtar priserna från OpenAI:s "
        "officiella docs-MCP och aldrig hittar på siffror (saknat pris = null)."
    )

    pricing, err = _load_json_file(PRICING_SNAPSHOT_PATH)
    if err or pricing is None:
        st.error(err)
        pricing = {"models": [], "needsRefresh": True, "lastFetched": None}

    needs_refresh = bool(pricing.get("needsRefresh", True))
    last_fetched = pricing.get("lastFetched")

    badge_col, button_col = st.columns([3, 1])
    with badge_col:
        if needs_refresh:
            st.info(
                "Snapshotten är placeholder eller inaktuell (needsRefresh). "
                "Kör `python scripts/fetch_model_prices.py` - lokalt med nät/MCP "
                "eller via knappen - för riktiga priser."
            )
        else:
            st.success(
                f"Senast hämtad: {last_fetched} ({_age_label(last_fetched)}) "
                f"från {pricing.get('source', '—')}."
            )
    with button_col:
        if st.button("Uppdatera priser nu", key="cr-price-refresh", width="stretch"):
            with st.spinner("Kör scripts/fetch_model_prices.py ..."):
                st.session_state["cr-price-refresh-result"] = (
                    health.run_fetch_model_prices()
                )
            loaders.load_json.clear()
            loaders.read_text.clear()
            st.rerun()
    if "cr-price-refresh-result" in st.session_state:
        render_check(st.session_state["cr-price-refresh-result"])

    price_by_model = {
        row.get("model"): row
        for row in pricing.get("models", [])
        if isinstance(row, dict)
    }
    role_to_group = model_roles.role_group_map(models)
    rows = []
    for role in models.get("roles", []):
        price = price_by_model.get(role.get("model"), {})
        rows.append(
            {
                "Roll": role.get("id"),
                "Modell": role.get("model"),
                "Grupp": role_to_group.get(role.get("id"), "?"),
                "USD/1M in": _price_cell(price.get("inputPer1M")),
                "USD/1M ut": _price_cell(price.get("outputPer1M")),
                "Hämtad": _age_label(price.get("fetchedAt")),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    extra_models = [
        row
        for model_name, row in price_by_model.items()
        if model_name not in {r.get("model") for r in models.get("roles", [])}
    ]
    if extra_models:
        st.markdown("**Övriga prissatta modeller** (chatt-/sidomodeller m.m.)")
        st.dataframe(
            [
                {
                    "Modell": row.get("model"),
                    "USD/1M in": _price_cell(row.get("inputPer1M")),
                    "USD/1M ut": _price_cell(row.get("outputPer1M")),
                    "Hämtad": _age_label(row.get("fetchedAt")),
                }
                for row in extra_models
            ],
            width="stretch",
            hide_index=True,
        )

    st.markdown("**Gränser** (chatten, `apps/viewser/lib/openai.ts`)")
    limits = runtime_models.chat_limits()
    chat_tokens_env = read_non_secret_env(runtime_models.CHAT_TOKENS_ENV)
    a, b, c = st.columns(3)
    a.metric("Max svarstokens", chat_tokens_env or str(limits["maxOutputTokensDefault"] or "okänd"))
    b.metric("Max tecken/meddelande", str(limits["maxInputCharsPerMessage"] or "okänd"))
    c.metric("Max meddelanden/request", str(limits["maxMessagesPerRequest"] or "okänd"))


# ----- huvudvyn -----------------------------------------------------------------


def view_control_room() -> None:
    st.title("Dirigentpult")
    st.caption(
        "Överordnad styrsida för dirigenten: motorns modellroller, chatt-/"
        "sidomodeller, persona (SOUL), sanktionerade actions, skills, "
        "konduktör-roller och tokenpriser - samlade på en yta. Varje kontroll "
        "förklarar vad den styr; det som är read-only är read-only för att "
        "behörigheten bor i kod/governance, inte i UI:t (ADR 0002, "
        "governance/rules/09)."
    )

    models, models_err = loaders.safe_load_policy("llm-models.v1.json")
    registry, _registry_err = _load_json_file(ACTION_REGISTRY_PATH)
    pricing, _pricing_err = _load_json_file(PRICING_SNAPSHOT_PATH)

    # Statusrad: snabba nyckeltal över hela pulten.
    soul_chars = len(SOUL_PATH.read_text(encoding="utf-8")) if SOUL_PATH.exists() else 0
    actions = (registry or {}).get("actions", [])
    supported = sum(1 for a in actions if a.get("status") == "supported")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Modellroller", len((models or {}).get("roles", [])))
    m2.metric("Actions (supported)", f"{supported} / {len(actions)}")
    m3.metric(
        "SOUL-tecken",
        f"{soul_chars} / {SOUL_RUNTIME_MAX_CHARS}",
        help=(
            f"Editor-cap {SOUL_MAX_CHARS}; runtime läser bara de första "
            f"{SOUL_RUNTIME_MAX_CHARS} tecknen."
        ),
    )
    needs_refresh = bool((pricing or {}).get("needsRefresh", True))
    m4.metric(
        "Priser",
        "behöver hämtas" if needs_refresh else _age_label((pricing or {}).get("lastFetched")),
    )
    st.caption(
        "Legend: ✅ supported (kodstöd finns) · 🟡 partial (delvis) · "
        "🧭 planned (planerad, inget kodstöd) · 🔒 read-only (ägs av kod/governance)."
    )

    tab_a, tab_b, tab_c, tab_d, tab_e, tab_f, tab_g = st.tabs(
        [
            "A · Modeller per roll",
            "B · Chatt & sidor",
            "C · Persona (SOUL)",
            "D · Actions",
            "E · Skills",
            "F · Konduktör-roller 🔒",
            "G · Priser & gränser",
        ]
    )

    with tab_a:
        if models_err or models is None:
            st.error(models_err)
        else:
            _render_tab_models(models, pricing)
    with tab_b:
        _render_tab_env_models()
    with tab_c:
        _render_tab_soul()
    with tab_d:
        _render_tab_actions()
    with tab_e:
        _render_tab_skills()
    with tab_f:
        _render_tab_roles()
    with tab_g:
        if models_err or models is None:
            st.error(models_err)
        else:
            _render_tab_pricing(models)


VIEWS = {
    "Dirigentpult": lambda: safe_render(view_control_room),
}
