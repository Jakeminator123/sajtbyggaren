"""Discovery Resolver — canonical mapping från Viewser discovery-wizard till Project Input.

Stänger B121 backendsida: konsoliderar discovery-sanning som tidigare passerade
``WizardAnswers``-tempfilen, ``briefModel``/masterprompt och
``_apply_discovery_overrides`` utan en explicit konfliktlösare. Resolvern läser
``governance/policies/discovery-taxonomy.v1.json`` + Discovery Payload + Site
Brief-kandidat och producerar:

- ett resolverat Project Input dict (kompatibelt med
  ``governance/schemas/project-input.schema.json``)
- ett ``DiscoveryDecision`` dict (kompatibelt med
  ``governance/schemas/discovery-decision.schema.json``) som persisteras
  som extra fält ``discoveryDecision`` på prompt-input meta-sidecaren.

Public API:

- :func:`resolve_discovery` — main entry point, takes raw prompt, payload,
  candidate Project Input + optional scrape fields, returnerar
  ``(resolved_project_input, decision)``.
- :func:`load_discovery_taxonomy` — loader för policyfilen.
- :class:`DiscoveryDecision`, :class:`FallbackWarning`, :class:`FieldSource` —
  typade containers för decision-shape.

Planning är fortsatt canonical för faktisk starter-resolution
(``packages/generation/planning/plan.py:_resolve_starter_id``). Resolvern
returnerar bara ``expectedStarterId`` som *förväntat* värde härlett från
``selectedScaffoldId`` via ``SCAFFOLD_TO_STARTER``.
"""

from __future__ import annotations

from .models import (
    DEFAULT_TAXONOMY_CATEGORY_ID,
    DiscoveryDecision,
    DiscoveryPayload,
    FallbackWarning,
    FieldSource,
    FieldSourceLiteral,
    SelectionSource,
    SupportStatus,
)
from .resolve import (
    apply_discovery_overrides,
    resolve_discovery,
)
from .taxonomy import (
    DiscoveryTaxonomy,
    TaxonomyCategory,
    load_discovery_taxonomy,
)

__all__ = [
    "DEFAULT_TAXONOMY_CATEGORY_ID",
    "DiscoveryDecision",
    "DiscoveryPayload",
    "DiscoveryTaxonomy",
    "FallbackWarning",
    "FieldSource",
    "FieldSourceLiteral",
    "SelectionSource",
    "SupportStatus",
    "TaxonomyCategory",
    "apply_discovery_overrides",
    "load_discovery_taxonomy",
    "resolve_discovery",
]
