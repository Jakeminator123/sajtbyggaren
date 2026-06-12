"""Merge operator-curated, pinned dependencies from mounted dossier manifests
into a generated site's ``package.json``.

ADR 0056 builds the *mechanism* only: a dossier manifest
(``governance/schemas/dossier.schema.json``) may declare ``dependencies`` as a
list of pinned npm specs (``"three@0.160.0"`` or ``"@scope/name@1.2.3"``). The
builder merges those into the generated ``package.json`` for the dossiers that
are actually mounted on a build. No language model selects dependencies — the
operator-curated, schema-validated dossier manifest is the sanctioned policy +
approval channel (see ``docs/openclaw-workspace/TOOLS.md``; LLM-chosen
dependencies stay a later Fas 3 decision in
``docs/heavy-llm-flow/openclaw-2.0-conductor.md``).

Pin policy (ADR 0056): only **exact** (``1.2.3``) and **tilde** (``~1.2.3``)
specs are accepted. Caret ranges, open ranges, ``*``, ``latest``/dist-tags,
git/url/workspace protocols and missing versions are rejected as a hard build
error.

Collision rule (no silent winner, ADR 0056): two mounted dossiers declaring the
same package with different pins, or a dossier pinning a package the starter
already depends on with a *different* spec, is a hard build error. An identical
re-declaration is a no-op.

Errors are raised as ``SystemExit`` with a ``Builder failed:`` prefix to match
the rest of ``scripts/build_site.py``'s hard build-failure messages.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Exact ``1.2.3`` or tilde ``~1.2.3``, with optional semver prerelease
# (``-rc.1``) and build metadata (``+build.5``). Deliberately NO caret,
# ranges, ``x`` wildcards, ``*``, dist-tags, or protocol specs.
_PIN_RE = re.compile(r"^~?\d+\.\d+\.\d+(-[0-9A-Za-z.\-]+)?(\+[0-9A-Za-z.\-]+)?$")


@dataclass(frozen=True)
class DependencyMerge:
    """Outcome of merging dossier dependencies into a base dependency map.

    ``dependencies`` is the final map to write into ``package.json``.
    ``changed`` is ``True`` iff at least one package was added relative to the
    base (the signal the builder uses to fall back from ``npm ci`` to
    ``npm install``). ``added`` maps the newly added package names to their
    pinned specs (used for the trace note).
    """

    dependencies: dict[str, str]
    changed: bool
    added: dict[str, str]


def parse_pinned_spec(spec: str, *, dossier_id: str | None = None) -> tuple[str, str]:
    """Parse ``"name@version"`` (incl. scoped ``"@scope/name@version"``).

    Returns ``(name, version)``. Raises ``SystemExit`` when the spec is missing
    a version or the version is not a pinned (exact/tilde) form.
    """
    where = f" (dossier '{dossier_id}')" if dossier_id else ""
    text = spec.strip()
    name, sep, version = text.rpartition("@")
    if sep == "" or name == "" or version == "":
        raise SystemExit(
            f"Builder failed: dossier dependency '{spec}'{where} must be a pinned "
            "'name@version' spec (e.g. 'three@0.160.0' or '~0.160.0')."
        )
    if not _PIN_RE.match(version):
        raise SystemExit(
            f"Builder failed: dossier dependency '{spec}'{where} is not pinned. "
            "Only exact ('1.2.3') or tilde ('~1.2.3') versions are allowed; "
            "caret ranges, open ranges, '*', dist-tags and git/url specs are rejected."
        )
    return name, version


def merge_dossier_dependencies(
    base: Mapping[str, str],
    selected_dossiers: Sequence[Mapping[str, object]],
) -> DependencyMerge:
    """Merge pinned deps from each mounted dossier's manifest into ``base``.

    ``base`` is the starter's ``package.json`` ``dependencies`` map.
    ``selected_dossiers`` is the list returned by
    ``load_selected_dossier_manifests`` (each item exposes ``id`` and
    ``manifest`` with a ``dependencies`` list). Raises ``SystemExit`` on a pin
    violation or a collision.
    """
    result: dict[str, str] = dict(base)
    added: dict[str, str] = {}
    # name -> (version, dossier_id) for cross-dossier collision detection.
    declared: dict[str, tuple[str, str]] = {}

    for info in selected_dossiers:
        dossier_id = str(info.get("id", "<unknown>"))
        manifest = info.get("manifest")
        if not isinstance(manifest, Mapping):
            continue
        raw_deps = manifest.get("dependencies", [])
        if not isinstance(raw_deps, Sequence) or isinstance(raw_deps, (str, bytes)):
            continue
        for raw_spec in raw_deps:
            if not isinstance(raw_spec, str):
                continue
            name, version = parse_pinned_spec(raw_spec, dossier_id=dossier_id)

            previous = declared.get(name)
            if previous is not None and previous[0] != version:
                prev_version, prev_dossier = previous
                raise SystemExit(
                    "Builder failed: dossier dependency collision -> "
                    f"'{dossier_id}' pins '{name}@{version}' but '{prev_dossier}' "
                    f"already pins '{name}@{prev_version}'. Two mounted dossiers "
                    "cannot declare the same package with different pins; reconcile "
                    "the dossier manifests before retrying."
                )
            declared[name] = (version, dossier_id)

            base_version = base.get(name)
            if base_version is not None and base_version != version:
                raise SystemExit(
                    "Builder failed: dossier dependency collision with starter -> "
                    f"dossier '{dossier_id}' pins '{name}@{version}' but the starter "
                    f"already depends on '{name}@{base_version}'. A dossier may not "
                    "silently override a starter dependency; remove the dossier pin "
                    "or align it with the starter before retrying."
                )

            if name not in result:
                result[name] = version
                added[name] = version
            # name already in base with an identical spec -> no-op.

    if added:
        # Keep the starter's original key order, then append added packages in a
        # deterministic (sorted) order so repeated builds emit byte-identical
        # package.json output.
        result = {**dict(base), **{name: added[name] for name in sorted(added)}}

    return DependencyMerge(dependencies=result, changed=bool(added), added=added)
