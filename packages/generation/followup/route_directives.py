"""Follow-up route directives: resolve a route_remove to disabled scaffold routes.

A ``route_remove`` follow-up ("ta bort sidan Om oss", "radera kontaktsidan") is
the route_editor concern (Route/Nav Mutation V1, ADR 0060). It disables ONE
scaffold route by recording its routeId in ``directives.disabledRoutes`` so the
deterministic build drops the page from ``activeRoutes`` (page.tsx, header/footer
nav, route guards) - no new Dossier, no new render path, no free file patch. The
router resolved a best-effort routeId from the prompt label; this resolver is the
deterministic gate that validates it against the site's ACTUAL scaffold routes.

Scaffold-agnostic by construction: it reads the site's own ``routes.json``
``defaultRoutes`` (id + required), so it works for every starter, not one. The
``required`` guard keeps a scaffold's mandatory pages (home/services/contact on
local-service-business; the contact page everywhere, whose CTAs the whole site
links to) intact in Slice A - removing contact + retargeting its CTAs is Slice B
(``allow_required``).

Honest by construction: a routeId the scaffold does not declare, or a required
route kept in this slice, is reported as ``refused`` so the chain can do an
HONEST no-op with a reason (it never disables a page it cannot safely remove, and
never invents a route). Deterministic, offline, no LLM.

Slice B (ADR 0060): ``contact`` becomes removable too via ``allow_required_ids``
(the caller passes ``frozenset({"contact"})``), while ``home``/``services`` stay
protected (never in the allow-list, and ``home`` is refused unconditionally).
Removing contact retargets its site-wide CTAs to ``mailto:``/``tel:`` or omits
them - that materialisation lives in the build/render seam, not here.

Conventions: identifiers + comments in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

from typing import Any

__all__ = ["resolve_disabled_routes"]

# The landing page is always kept: even a scaffold that forgot the ``required``
# flag must never lose its root route. Guarded explicitly below, before the
# ``required`` check, so it cannot be opted into via ``allow_required_ids``.
_ALWAYS_REQUIRED_ROUTE_IDS = frozenset({"home"})


def resolve_disabled_routes(
    route_ids: list[str | None],
    scaffold_routes: dict[str, Any],
    *,
    allow_required: bool = False,
    allow_required_ids: frozenset[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Resolve route_remove targets to disable-able scaffold routeIds.

    Returns ``(disabled, refused)`` where:

    - ``disabled`` is the de-duplicated list of routeIds that BOTH exist in the
      scaffold's ``defaultRoutes`` AND are safe to remove (never ``home``; a
      ``required`` page only when ``allow_required`` is set OR its id is listed
      in ``allow_required_ids``). Recording one disables the page.
    - ``refused`` is ``[{"routeId", "reason"}]`` for every target that is
      unknown (no label resolved), not a scaffold route, or a required page kept
      in this slice - the honest no-op signal.

    ``route_ids`` are the best-effort routeIds the router resolved from the prompt
    (``decision.target.routeId`` + subtask targets); a ``None`` entry means the
    router saw a page removal but could not name the page.

    ``scaffold_routes`` is the loaded ``routes.json`` (``defaultRoutes`` with
    id/required). ``allow_required`` opens every required page except ``home``
    (kept for the resolver's direct unit-test seam). ``allow_required_ids`` is
    the Slice B path: the caller passes ``frozenset({"contact"})`` so contact -
    and only contact - becomes removable while ``services`` (and any other
    required page) stays protected. Deterministic, offline, no LLM.
    """
    allowed_required = allow_required_ids or frozenset()
    default_routes = (
        scaffold_routes.get("defaultRoutes") if isinstance(scaffold_routes, dict) else None
    )
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(default_routes, list):
        for route in default_routes:
            if isinstance(route, dict) and isinstance(route.get("id"), str):
                by_id[route["id"]] = route

    disabled: list[str] = []
    refused: list[dict[str, str]] = []
    seen: set[str] = set()
    for route_id in route_ids:
        if not route_id or not isinstance(route_id, str):
            refused.append(
                {
                    "routeId": "(okänd)",
                    "reason": (
                        "Ingen igenkänd sida i prompten; ange vilken sida som ska "
                        "tas bort (t.ex. 'ta bort sidan Om oss')."
                    ),
                }
            )
            continue
        if route_id in seen:
            continue
        seen.add(route_id)
        route = by_id.get(route_id)
        if route is None:
            refused.append(
                {
                    "routeId": route_id,
                    "reason": (
                        f"Sidan {route_id!r} finns inte bland scaffoldens sidor; "
                        "ingen sida tas bort (aldrig en påhittad route)."
                    ),
                }
            )
            continue
        if route_id in _ALWAYS_REQUIRED_ROUTE_IDS:
            refused.append(
                {
                    "routeId": route_id,
                    "reason": "Startsidan kan inte tas bort.",
                }
            )
            continue
        if (
            route.get("required")
            and not allow_required
            and route_id not in allowed_required
        ):
            refused.append(
                {
                    "routeId": route_id,
                    "reason": (
                        f"Sidan {route_id!r} är obligatorisk i scaffolden (t.ex. "
                        "tjänster) och kan inte tas bort; obligatoriska sidor "
                        "behålls (endast kontaktsidan kan tas bort, med säker "
                        "CTA-fallback)."
                    ),
                }
            )
            continue
        if route_id not in disabled:
            disabled.append(route_id)
    return disabled, refused
