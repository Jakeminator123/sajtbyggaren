# SKILL: component_add

## Mål
Besvara en `component_add`-följdprompt ("lägg en klocka i andra sektionen", "lägg
till en accordion") grundat i **Component Catalog** (ADR 0040) — ELLER göra en
ÄRLIG no-op som pekar operatören mot det kurerade shadcn-intaget. Rollen som äger
kindet är `component_builder` (ADR 0057).

> **PARTIAL + MOUNT-ONLY i denna slice.** `component_add` MONTERAR ingen
> komponent och skriver INGA filer i den genererade sajten. En component_add-
> följdprompt resulterar i ett katalog-grundat svar (vilka komponenter som finns
> vendorerade enligt capability-map `components` + per-Starter
> `component-manifest.json`) eller en ärlig no-op. Den befintliga kedjan
> rapporterar no-op:en via `unappliedFollowupIntents` (ingen påhittad effekt).

## Roll-ägarskap (ADR 0057)
`role_for_edit_kind("component_add")` → `component_builder`;
`skill_for_edit_kind("component_add")` → denna fil
(`skills/component-add/SKILL.md`). Kontraktet är `status="partial"`,
`mountOnly=True`, `contextLevel="component_registry"`. Registryt
(`docs/openclaw-workspace/action-registry.json`) speglar samma fält och
korsvalideras mot rollkontraktet i
`tests/test_openclaw_registry_consistency.py`.

## Component Catalog (förhandsinfo)
Komponentmedvetenheten är låst i ADR 0040:

- **Lager 1** — per-Starter `component-manifest.json` (genererad inventering av
  `components/ui/`, `scripts/generate_component_manifests.py`).
- **Lager 2** — capability-map `components`-nyckel (vilken komponent en
  capability får använda), korskontrollerad mot starter-manifesten i
  `scripts/governance_validate.py`.
- **Lager 3** — denna roll-dispatch + den synliga render-vägen (faq-section →
  accordion-piloten) + intaget nedan.

## Intag av ny komponent (operatörsväg, aldrig runtime)
En komponent som INTE redan är vendorerad får ALDRIG monteras av kedjan. Vägen
in är det kurerade shadcn-intaget:

1. `python scripts/component_intake.py --prompt "<beskrivning>" --slug <slug>` —
   spawnar ett EGET `npx shadcn@latest mcp` (stdio), kör
   `search_items_in_registries → view_items_in_registries →
   get_item_examples_from_registries` och skriver en kandidat till
   `data/component-candidates/<slug>/` (`component.tsx`, `intake-info.json`,
   `README.md`). CLI:t läser ALDRIG `.cursor/mcp.json` och skriver ALDRIG i
   `data/starters/` eller `packages/generation/orchestration/`.
2. Operatören granskar kandidaten och kurerar in den i en Starter via en egen PR
   (component.tsx → `data/starters/<id>/components/ui/`, regenerera manifestet).
   Inga nya npm-beroenden i en Starter utan policy + operatörsgodkännande.

## Honesty
Okänd/icke-vendorerad komponent → ärlig no-op (inget mount, inga filer), med
hänvisning till intaget. `appliedVisibleEffect` är aldrig påhittad: en
component_add monterar inget i denna slice, så den rapporteras ärligt som
"registrerad men syns inte / förslag på intag", aldrig "genomförde ändringen".

## Status
partial — rollkontrakt + registry + denna skill landade med ADR 0057. Synlig
katalog-konsumtion finns för faq-section → accordion (lager 3-piloten); en
generell mount-väg för component_add är en senare slice med egen ADR.
