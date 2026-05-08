---
description: Dossier är återanvändbar capability. Project Input är ett konkret kundprojekt. De är inte samma sak.
alwaysApply: true
---

# Dossier vs Project Input

Den enda regel som måste sitta i ryggmärgen: konkreta exempel som
`painter-palma` är **Project Input**. Återanvändbara legoklossar som
`pacman-game` eller `stripe-checkout` är **Dossier**.

## Definitioner

- **Project Input** (alias: Deep Brief, Example Project): strukturerad tolkning
  av en operatörs init-prompt och konkret kund-/site-data. Filer:
  `examples/<siteId>.project-input.json`. Driver vad sajten ska handla om.
- **Dossier** (alias: Capability): återanvändbar legokloss som kan kopplas på
  vilken `Route`/section/slot som helst i en `Scaffold`. Drivs av en
  återanvändbar funktion eller integration, inte av kundens namn.

En Dossier ska vara default-kompatibel med alla Scaffolds. En Scaffold är
sajtens grammatik (route + sektioner), inte en sida. En Variant är hela
sajtens visuella uttryck.

## Klasser

| Klass | Innebörd | Exempel |
|---|---|---|
| `soft` | Återanvändbar frontend/content capability utan secrets/API. | `pacman-game`, `mouse-reactive-background`, `pricing-calculator`, `before-after-slider`. |
| `hard` | Kräver env, secrets, backend, auth, databas, betalning eller extern API. | `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart`. |

`hybrid` finns inte som klass. En dossier som behöver mock i designläge men
integration i live-läge är `hard` med `mockMode`-konfiguration.

## Vad är inte en Dossier

- Konkreta kundprojekt (`painter-palma`, `bakery-jansson`) - de är `Project Input`.
- En enkel animerad bakgrund som LLM/codegen kan skapa direkt från
  promptens text. Det blir en Dossier först om den ska vara återanvändbar,
  testbar, ha dependency-kontrakt eller slot-kontrakt.
- En `Route` eller `Page` - en sida ägs av `Scaffold`, inte av en Dossier.
- En `Variant` - en visuell riktning är inte en capability.

## Praktisk regel för agenten

Om något kan svaras med "ja, vi kan ha det här på vilken sajt som helst" → Dossier.
Om det är "den här specifika kunden vill ha X" → Project Input.

Om du är osäker, stoppa. Fråga operatören. Skapa inte en ny term.

## Förbjudna namn

Följande termer är borttagna i ADR 0012 och får inte återinföras:

- `Site Dossier` (använd `Project Input`)
- `Feature Dossier` (använd `Dossier` med klass `soft`)
- `Integration Dossier` (använd `Dossier` med klass `hard`)
- `Data Dossier` (använd `Dossier` med klass `soft` eller flytta till `Project Input` om det är site-specifikt)
- `Hybrid Dossier` (använd `Dossier` med klass `hard` och `mockMode`)

Listan är speglad i `naming-dictionary.v1.json:globallyForbidden` och bevakas
av `tests/test_no_legacy_terms.py`.
