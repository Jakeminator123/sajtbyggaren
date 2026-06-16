"""Prompt-input-meta-läsarfamiljen för den deterministiska byggaren.

Extraherat ordagrant ur ``scripts/build_site.py`` enligt
``docs/refactor/megafiles-plan.md`` (Del 2, slice 3), beteendebevarande.
Modulen läser den valfria sidecar-metadatan bredvid
``data/prompt-inputs/<siteId>.{project-input,meta}.json`` och normaliserar
init-/följdprompt-tillstånd för en Engine Run.

``load_json`` ligger nu i ``packages.generation.build.io_helpers``. Den
repo-relativa facade-hjälparen (``_to_repo_relative``) ligger kvar i
``scripts/build_site.py`` denna slice eftersom den beror på byggarens
``REPO_ROOT``-semantik. Funktioner här som behöver den gör därför fortsatt en
LAT import i funktionsbody (``from scripts.build_site import _to_repo_relative``)
för att undvika cirkulär import: ``scripts/build_site.py`` importerar den här
modulen ivrigt i sin header.
``_persist_init_project_input_sidecar`` behåller dessutom sin befintliga
lata import från ``scripts.prompt_to_project_input``.
"""

from __future__ import annotations

import copy
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.generation.build.io_helpers import load_json

_VERSIONED_PROMPT_INPUT_RE = re.compile(
    r"^(?P<site_id>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"
    r"\.v(?P<version>[1-9][0-9]*)\.project-input\.json$"
)
_CURRENT_PROMPT_INPUT_RE = re.compile(
    r"^(?P<site_id>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"
    r"\.project-input\.json$"
)


def _prompt_meta_path_for_dossier(dossier_path: Path) -> Path | None:
    """Return the adjacent prompt-input meta path for a Project Input file."""
    filename = dossier_path.name
    versioned = _VERSIONED_PROMPT_INPUT_RE.match(filename)
    if versioned:
        return dossier_path.with_name(
            f"{versioned.group('site_id')}.v{versioned.group('version')}.meta.json"
        )

    current = _CURRENT_PROMPT_INPUT_RE.match(filename)
    if current:
        return dossier_path.with_name(f"{current.group('site_id')}.meta.json")
    return None


def load_prompt_input_meta(
    dossier_path: Path,
    dossier: dict[str, Any],
) -> dict[str, Any]:
    """Load optional prompt metadata adjacent to data/prompt-inputs files.

    Curated examples do not have sidecar metadata and therefore keep the
    historical init-mode behaviour. Prompt-generated Project Inputs carry
    a sidecar with stable projectId/version so each Engine Run can record
    immutable version metadata instead of making Viewser read the mutable
    "latest" sidecar for every old run.
    """
    from scripts.build_site import _to_repo_relative

    meta_path = _prompt_meta_path_for_dossier(dossier_path)
    if meta_path is None:
        # Dossier filename does not match either prompt-input pattern
        # (no `<siteId>.project-input.json` and no `<siteId>.vN.*`).
        # Nothing in the prompt-input contract applies; keep init-mode.
        return {"mode": "init"}
    if not meta_path.exists():
        # B60 fynd 4: a missing sidecar can mean either
        #   (a) corrupt prompt-input state (interrupted run, partial copy,
        #       manual delete on a `data/prompt-inputs/` snapshot or on a
        #       versioned `<siteId>.vN.project-input.json` file) - must
        #       fail loudly so the operator restores the meta instead of
        #       silently emitting a follow-up build labelled as init with
        #       no projectId/version, OR
        #   (b) a curated example under `examples/` whose filename happens
        #       to match `_CURRENT_PROMPT_INPUT_RE` but never had a
        #       sidecar by design.
        # A versioned filename (`.vN.project-input.json`) is unambiguously
        # written by `prompt_to_project_input.py` and therefore must have
        # a sidecar; the current-pointer pattern only carries the same
        # contract when the file lives under `data/prompt-inputs/`.
        is_versioned = (
            _VERSIONED_PROMPT_INPUT_RE.match(dossier_path.name) is not None
        )
        is_under_prompt_inputs = dossier_path.parent.name == "prompt-inputs"
        if is_versioned or is_under_prompt_inputs:
            raise SystemExit(
                f"Builder failed: prompt meta sidecar missing at {meta_path}. "
                "Restore the meta or remove the orphaned project-input file."
            )
        return {"mode": "init"}

    meta = load_json(meta_path)
    site_id = meta.get("siteId")
    if site_id != dossier.get("siteId"):
        raise SystemExit(
            "Builder failed: prompt meta siteId mismatch "
            f"({meta_path} has {site_id!r}, Project Input has "
            f"{dossier.get('siteId')!r})."
        )

    version = meta.get("version")
    if version is not None and (not isinstance(version, int) or version < 1):
        raise SystemExit(
            f"Builder failed: prompt meta has invalid version at {meta_path}."
        )

    mode = meta.get("mode")
    if mode not in {"init", "followup"}:
        mode = "followup" if isinstance(version, int) and version > 1 else "init"

    project_id = meta.get("projectId")
    if project_id is not None and (
        not isinstance(project_id, str) or not project_id.strip()
    ):
        raise SystemExit(
            f"Builder failed: prompt meta has invalid projectId at {meta_path}."
        )
    if mode == "followup" and not project_id:
        raise SystemExit(
            f"Builder failed: follow-up prompt meta requires projectId at {meta_path}."
        )

    normalized = dict(meta)
    normalized["mode"] = mode
    normalized["metaPath"] = _to_repo_relative(meta_path)
    return normalized


def _prompt_meta_mode(prompt_meta: dict[str, Any] | None) -> str:
    if not prompt_meta:
        return "init"
    mode = prompt_meta.get("mode")
    return mode if mode in {"init", "followup"} else "init"


def _prompt_meta_project_id(prompt_meta: dict[str, Any] | None) -> str | None:
    if not prompt_meta:
        return None
    project_id = prompt_meta.get("projectId")
    return project_id if isinstance(project_id, str) and project_id else None


def _prompt_meta_version(prompt_meta: dict[str, Any] | None) -> int | None:
    if not prompt_meta:
        return None
    version = prompt_meta.get("version")
    return version if isinstance(version, int) and version >= 1 else None


def _prompt_meta_previous_version(prompt_meta: dict[str, Any] | None) -> int | None:
    """Return the previous Project Input version for follow-up builds.

    The prompt helper writes ``previousVersion`` on follow-up sidecars.
    If an older sidecar lacks that field, derive it from ``version - 1``
    so historical prompt-inputs still get best-effort snapshot lookup.
    """
    if not prompt_meta:
        return None
    previous_version = prompt_meta.get("previousVersion")
    if isinstance(previous_version, int) and previous_version >= 1:
        return previous_version
    version = _prompt_meta_version(prompt_meta)
    if version is not None and version > 1:
        return version - 1
    return None


def _prompt_meta_raw_prompt(prompt_meta: dict[str, Any] | None) -> str | None:
    if not prompt_meta:
        return None
    mode = _prompt_meta_mode(prompt_meta)
    key = "followUpPrompt" if mode == "followup" else "originalPrompt"
    value = prompt_meta.get(key)
    return value if isinstance(value, str) else None


def _persist_init_project_input_sidecar(
    dossier: dict[str, Any],
    prompt_meta: dict[str, Any] | None,
    prompt_inputs_dir: Path,
) -> dict[str, Any] | None:
    """Glue 1 (core loop): persist a discoverable Project Input sidecar for a
    fresh init build, so the next follow-up prompt can find it on disk.

    A follow-up resolves the Project Input from
    ``data/prompt-inputs/<siteId>.{project-input,meta}.json`` (``read_existing_meta``
    / ``read_base_run_snapshot`` in ``scripts/prompt_to_project_input.py``). A build
    driven straight from a curated example or any ad-hoc dossier path - the builder
    MVP path (``build_site.py --dossier examples/<slug>.project-input.json``) - never
    went through ``prompt_to_project_input.generate``, so no sidecar exists and the
    very next follow-up dies with "Follow-up meta sidecar saknas": the core loop
    (create -> preview -> follow-up) breaks on a freshly built site. The Viewser
    prompt path already writes the sidecar via ``generate`` before ``build`` runs, so
    that path is unaffected.

    This writes the v1 sidecar (immutable ``<siteId>.v1.*`` snapshots + the current
    pointers) the first time such a site is built, reusing the SAME
    ``write_project_input`` spine ``generate`` uses - no new format. Strictly additive
    and idempotent:

    - A build already backed by a sidecar (the prompt path / every follow-up
      version) carries ``projectId`` on ``prompt_meta`` and is left untouched.
    - A site whose sidecar already exists on disk is left untouched (never clobbers
      existing version truth).

    Returns the enriched init ``prompt_meta`` (``projectId`` + ``version=1``) so the
    run's ``input.json`` / ``build-result.json`` record the same identity the sidecar
    pins - exactly like a prompt-driven init build - keeping the run consistent with
    the persisted v1 snapshot for ``read_base_run_snapshot``. Returns ``None`` when
    nothing was persisted (the caller keeps the original ``prompt_meta``).

    Honest degrade: any failure (e.g. a dossier that does not validate against
    project-input.schema.json) is logged and skipped, never crashing a build that
    succeeds today.
    """
    from scripts.build_site import _to_repo_relative

    # Already backed by a prompt-inputs sidecar (prompt path / follow-up version).
    if _prompt_meta_project_id(prompt_meta) is not None:
        return None
    site_id = dossier.get("siteId")
    if not isinstance(site_id, str) or not site_id:
        return None
    try:
        from scripts.prompt_to_project_input import (
            _build_project_dna_snapshot,
            _current_meta_path,
            _validate_against_schema,
            write_project_input,
        )

        # Never clobber an existing version pointer (idempotent re-build).
        if _current_meta_path(prompt_inputs_dir, site_id).exists():
            return None

        project_input = copy.deepcopy(dossier)
        _validate_against_schema(project_input)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        meta: dict[str, Any] = {
            "projectId": uuid.uuid4().hex,
            "version": 1,
            "mode": "init",
            "siteId": site_id,
            "scaffoldId": project_input["scaffoldId"],
            "variantId": project_input["variantId"],
            "createdAt": now,
        }
        meta["projectDna"] = _build_project_dna_snapshot(
            project_input,
            previous_project_input=None,
            previous_project_dna=None,
            version=1,
            mode="init",
            follow_up_prompt=None,
        )
        _project_input_path, meta_path = write_project_input(
            project_input, meta, output_dir=prompt_inputs_dir
        )
    except Exception as exc:  # noqa: BLE001
        print(
            "Glue 1: kunde inte persistera Project Input-sidecar för "
            f"{dossier.get('siteId')!r}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None

    return {
        "mode": "init",
        "projectId": meta["projectId"],
        "version": 1,
        "scaffoldId": meta["scaffoldId"],
        "variantId": meta["variantId"],
        "metaPath": _to_repo_relative(meta_path),
    }


_PLACEHOLDER_CONTACT_VALID_FIELDS = (
    "phone",
    "email",
    "addressLines",
    # B133 Codex P2 follow-up: ``openingHours`` is also written from the
    # B88 fallback ("Mån-Fre 09:00-17:00" / "Mon-Fri 09:00-17:00") when
    # neither wizard nor scrape supplied a schedule, so it must be in
    # the operator-warning set too.
    "openingHours",
)


def _prompt_meta_placeholder_contact_fields(
    prompt_meta: dict[str, Any] | None,
) -> list[str]:
    """Return validated B133 placeholderContactFields from prompt meta.

    Filters to the known contact-block keys so a malformed sidecar
    cannot smuggle arbitrary strings into build-result.json — Viewser
    reads the list verbatim to render an operator warning.
    """
    if not prompt_meta:
        return []
    raw = prompt_meta.get("placeholderContactFields")
    if not isinstance(raw, list):
        return []
    fields: list[str] = []
    for value in raw:
        if (
            isinstance(value, str)
            and value in _PLACEHOLDER_CONTACT_VALID_FIELDS
            and value not in fields
        ):
            fields.append(value)
    return fields


def _prompt_meta_followup_intent_id(prompt_meta: dict[str, Any] | None) -> str | None:
    """Return ``projectDna.followUpIntent.id`` from the prompt sidecar."""
    if not prompt_meta:
        return None
    project_dna = prompt_meta.get("projectDna")
    if not isinstance(project_dna, dict):
        return None
    followup_intent = project_dna.get("followUpIntent")
    if not isinstance(followup_intent, dict):
        return None
    intent_id = followup_intent.get("id")
    return intent_id if isinstance(intent_id, str) and intent_id else None


def _has_copy_directives(payload: Any) -> bool:
    """Detect an applied copy edit (copyDirectives or sectionContentOverrides).

    Used by the follow-up honesty signal (ROW 3): when the operator asked to
    replace visible copy, a byte diff is only an honest "applied" effect if a
    real copy edit was actually recorded. ADR 0043 adds
    ``directives.sectionContentOverrides`` as a second applied-copy shape (a
    section text override), so an override-driven edit is recognised here too
    and never mis-reported as a phantom ``copy_directive_not_applied`` no-op.
    """
    if not isinstance(payload, dict):
        return False
    copy_directives = payload.get("copyDirectives")
    if isinstance(copy_directives, list) and bool(copy_directives):
        return True
    directives = payload.get("directives")
    if not isinstance(directives, dict):
        return False
    nested_copy_directives = directives.get("copyDirectives")
    if isinstance(nested_copy_directives, list) and bool(nested_copy_directives):
        return True
    section_overrides = directives.get("sectionContentOverrides")
    return isinstance(section_overrides, dict) and bool(section_overrides)


def _placeholder_contact_warning_message(fields: list[str]) -> str:
    """Human-readable warning string for build-result.json.

    Composes the canonical operator-facing line that Run Details mirrors
    via ``placeholderContactMessage`` so the warning text is consistent
    whether the operator reads the JSON artefakt or the Viewser badge.
    """
    joined = ", ".join(fields)
    return (
        f"Contact fields {joined} are placeholder values - operator "
        "must fill these before publishing."
    )


def _prompt_meta_wizard_must_have(
    prompt_meta: dict[str, Any] | None,
) -> list[str]:
    """Return validated B132 wizardMustHave list from prompt meta.

    Scout-orchestrator merge 2026-05-19: B132 (page intent warnings) and
    B133 (placeholder contact warnings) both add new helpers in this
    section. The two sets of helpers are orthogonal — one reads
    ``placeholderContactFields`` from the sidecar, the other reads
    ``wizardMustHave``. Kept side by side so build_result downstream can
    surface both warnings.
    """
    if not prompt_meta:
        return []
    raw_must_have = prompt_meta.get("wizardMustHave")
    if not isinstance(raw_must_have, list):
        return []

    labels: list[str] = []
    seen: set[str] = set()
    for item in raw_must_have:
        if not isinstance(item, str):
            continue
        label = item.strip()
        if not label or label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return labels
