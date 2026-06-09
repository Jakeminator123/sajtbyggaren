---
description: Dossier är en återanvändbar capability (Project Input är ett konkret kundprojekt) och formatet manifest.json + instructions.md + components/ är låst; klasser är bara soft eller hard.
globs: packages/generation/orchestration/dossiers/**,data/starters/**,docs/**/dossier*,governance/policies/*dossier*
alwaysApply: false
---

# Dossier-disciplin

Konsoliderar dossier-format och dossier-vs-project-input. Den regel som måste sitta i ryggmärgen: konkreta exempel som `painter-palma` är **Project Input**; återanvändbara legoklossar som `pacman-game` eller `stripe-checkout` är **Dossier**.

## Skillnad

- **Project Input** (alias: Deep Brief, Example Project): strukturerad tolkning av en operatörs init-prompt + konkret kund-/site-data. Filer: `examples/<siteId>.project-input.json`. Driver vad sajten ska handla om.
- **Dossier** (alias: Capability): återanvändbar legokloss som kan kopplas på vilken `Route`/section/slot som helst i en `Scaffold`. Drivs av en återanvändbar funktion/integration, inte av kundens namn. Default-kompatibel med alla Scaffolds.

Blanda dem aldrig.

## Format (låst)

Ett dossierpaket består av exakt:

```text
manifest.json
instructions.md
components/
```

Inga andra filer får läggas i en dossier-mapp utan ADR som uppdaterar kontraktet. En dossier deklarerar exakt **en** `capability` i `manifest.json`; capability-fältet är obligatoriskt.

## Klasser: bara soft eller hard

| Klass | Innebörd | Exempel |
|---|---|---|
| `soft` | Återanvändbar frontend/content-capability utan secrets/API. | `pacman-game`, `mouse-reactive-background`, `pricing-calculator`, `before-after-slider` |
| `hard` | Kräver env, secrets, backend, auth, databas, betalning eller extern API. | `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart` |

`hybrid` finns inte som klass. En dossier som behöver mock i designläge men integration i live-läge är `hard` med `mockMode`-konfiguration.

## Vad som inte är en Dossier

- Konkreta kundprojekt (`painter-palma`, `bakery-jansson`) — de är `Project Input`.
- En enkel animerad bakgrund som codegen kan skapa direkt från prompten. Det blir en Dossier först om den ska vara återanvändbar, testbar eller ha dependency-/slot-kontrakt.
- En `Route`/`Page` (ägs av `Scaffold`) eller en `Variant` (en visuell riktning är inte en capability).

## Praktisk regel

Kan svaras med "ja, vi kan ha det här på vilken sajt som helst" → Dossier. Är det "den här specifika kunden vill ha X" → Project Input. Osäker — stoppa, fråga, skapa inte en ny term.

## Förbjudna namn (ADR 0012)

`Site Dossier`, `Feature Dossier`, `Integration Dossier`, `Data Dossier` och `Hybrid Dossier` är borttagna och får inte återinföras. Listan är speglad i `naming-dictionary.v1.json:globallyForbidden` och bevakas av `tests/test_no_legacy_terms.py`. Ersättningar: använd `Project Input`, eller `Dossier` med klass `soft`/`hard` (och `mockMode` vid behov).
