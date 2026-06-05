"""Map a validated artefakt patch onto an existing Project Input field (KÖR-7c).

The KÖR-7b ``PatchPlan`` proposes patches against ``generation-package.json``
*blueprint* fields (``contentBlocks.<route>.<section>.<leaf>`` /
``visualDirection.*``). KÖR-7c does not create a new blueprint artefakt - it
creates the next **Project Input** version. So each validated patch must be
mapped onto an **existing** Project Input field via the directive mechanism the
follow-up loop already uses (builder-profil §3: reuse the field, never mint a
new canonical artefakt or runtime contract).

Exactly one kor-7b patch shape has such a home today:

- ``component_add`` referencing a **registered capability**: its value carries
  ``{"capability": "<slug>"}`` (the planner attaches it only when the
  componentIntent maps to a ``capability-map.v1.json`` capability). That maps to
  ``project_input.requestedCapabilities`` - the field the discovery wizard feeds
  (``directives.requestedCapabilities`` -> resolver -> ``requestedCapabilities``)
  and ``produce_site_plan`` / the build already consume.

Everything else the planner can emit has **no** Project Input home:

- an inline ``component_add`` (no registered capability, e.g. a clock widget):
  there is no Project Input field for "attach component C to section S"; adding
  one needs a new directive field + a build-side consumer = a new runtime
  contract (operator decision + ADR).
- a ``copy_change`` (``...<section>.headline``, value deferred to the copy model
  kor-1c): ``directives.copyDirectives`` only targets company-name / tagline /
  about-text / services, never an arbitrary section headline, and the new copy
  is produced at build time, not here.

``classify_patch`` is pure: it inspects a single :class:`ArtifactPatch` and
returns either a capability slug to add or a human-readable reason the patch has
no existing Project Input home. It reads and writes nothing.
"""

from __future__ import annotations

from typing import Any

from ..patch import ArtifactPatch

__all__ = ["classify_patch"]

_CONTENT_BLOCKS_ROOT = "contentBlocks"
_ACCESSORY_LEAF = "accessoryComponent"
_HEADLINE_LEAF = "headline"


def _capability_from_value(value: Any) -> str | None:
    """The registered capability slug a patch value references, if any.

    Mirrors the planner/validator contract: a ``component_add`` value is a small
    descriptor dict that carries ``{"capability": "<slug>"}`` only when the
    component maps to a registered capability. An inline component (a clock,
    a button) carries no capability key.
    """
    if isinstance(value, dict):
        capability = value.get("capability")
        if isinstance(capability, str) and capability:
            return capability
    return None


def classify_patch(patch: ArtifactPatch) -> tuple[str, None] | tuple[None, str]:
    """Classify one validated patch for apply.

    Returns ``(capability, None)`` when the patch maps onto the existing
    ``requestedCapabilities`` field, or ``(None, reason)`` when it has no
    existing Project Input home (so apply can report it instead of inventing a
    new field). The patch is assumed already rail-validated by kor-7b; this is
    only the blueprint-field -> Project Input-field mapping.
    """
    segments = patch.field.split(".") if patch.field else []
    root = segments[0] if segments else ""
    leaf = segments[3] if len(segments) >= 4 else ""

    if root == _CONTENT_BLOCKS_ROOT and leaf == _ACCESSORY_LEAF:
        capability = _capability_from_value(patch.value)
        if capability is not None:
            return capability, None
        return (
            None,
            (
                f"component_add {patch.field!r} är en inline-komponent utan "
                "registrerad capability; det finns inget befintligt Project "
                "Input-fält att lagra den i. En mappning kräver ett nytt "
                "directive-fält + build-konsument (nytt runtime-kontrakt, "
                "operatörsbeslut + ADR)."
            ),
        )

    if root == _CONTENT_BLOCKS_ROOT and leaf == _HEADLINE_LEAF:
        return (
            None,
            (
                f"copy_change {patch.field!r} träffar en sektionsrubrik; "
                "directives.copyDirectives stödjer bara company-name/tagline/"
                "about-text/services och den nya copyn produceras av "
                "copyModel (kor-1c) vid bygget. Ingen befintlig Project "
                "Input-mappning."
            ),
        )

    return (
        None,
        (
            f"patchfält {patch.field!r} har ingen befintlig Project "
            "Input-mappning; en mappning skulle kräva ett nytt directive-fält "
            "eller en ny canonical-typ (operatörsbeslut + ADR)."
        ),
    )
