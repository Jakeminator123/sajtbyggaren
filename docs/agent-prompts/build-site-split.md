# Builder-uppdrag: B13a Step C — surgical split av page renderers

> Klistra in detta i en Cursor Cloud Background Agent eller annan
> isolerad builder-agent. Prompten är self-contained. Det här är en
> **surgical refactor utan beteendeändring** — inga buggar fixas, inga
> funktioner skrivs om. Bara filflytt + re-exports.

## Roll
Du är en builder-agent som ska flytta page-renderers från
`scripts/build_site.py` (6313 rader, 103 funktioner/klasser) till
nya filer under `packages/generation/build/`. Pathen är reserverad i
`.cursorignore` för exakt detta ändamål (se rad 26-32).

Det här är **steg C** av flytten enligt B13a-noten i `known-issues.md`
(se `docs/health-checks/2026-05-25-halvtid.md` §6.3 för fullständig
alternativbild). Steg D (full flytt) tas i en separat sprint senare.

## Förutsättningar (läs först, i denna ordning)
1. `AGENTS.md`
2. `governance/rules/branch-scope-ui-ux.md` — verifiera att denna agent
   INTE är en `christopher-ui`-agent (build_site.py är utanför hennes
   scope)
3. `governance/rules/code-in-english.md`
4. `docs/known-issues.md` — sök på "B13a" + relaterade buggar
   (B67, B86, B89, B90, B91, B92, B93, B110, B129) — **du ska inte
   fixa dessa, bara känna till dem**
5. `scripts/build_site.py` rader 2224-4850 (renderer-territoriet) + rad
   4845 (`write_pages`-dispatchern)
6. `tests/test_render_*.py`, `tests/test_builder_hardening.py`,
   `tests/test_naming_consistency.py` — alla tester som rör renderers

## Mål
Flytta följande från `scripts/build_site.py` till
`packages/generation/build/renderers.py` (eller flera filer om logiken
är cleaner):

### Page renderers (kärnan)
- `render_layout` (rad ~2224)
- `render_home` + alla `_render_home_*` helpers (rad ~2544-3982)
- `render_services` (rad ~2799)
- `render_about` (rad ~2844)
- `render_contact` (rad ~2936)
- `render_products` (rad ~2986)
- `render_faq` + helpers (rad ~3070-3204)
- `render_gallery` + helpers (rad ~3204-4029)
- `render_team` + helpers (rad ~4029-4082)
- `render_pricing` (rad ~4082)
- `render_portfolio` (rad ~4131)
- `render_map` (rad ~4192)
- `render_menu` + helpers (rad ~4316-4413)
- `render_booking` (rad ~4413)

### Static asset renderers
- `render_robots_txt`, `render_sitemap_xml`,
  `_render_structured_data_jsonld`, `render_og_fallback_svg`,
  `render_not_found`, `render_global_error` (rad ~4503-4845).
- Föreslagen placering: `packages/generation/build/static_assets.py`
  (separat fil eftersom de inte är page-renderers).

### Dispatcher
- `write_pages` (rad ~4845) — flytta till
  `packages/generation/build/renderers.py` eller en egen
  `packages/generation/build/dispatcher.py`.

## Vad du EJ ska göra
- **Refactora aldrig funktionsbody:s.** Kopiera ordagrant.
- Fixa aldrig buggar (B67, B86, B89, B90, B91, B92, B93, B110,
  B129). De är registrerade och ska tas i separata sprintar.
- **Konsolidera aldrig `_normalize_business_type` med
  `prompt_to_project_input.py`** — det är B110 och kräver egen ADR.
- **Rör aldrig `build()`, `main()`, eller pipeline-orkestreringen.**
- **Rör aldrig utility-helpers, asset/media-logik, color/typography,
  CSS-generatorer, business-type/CTA-logik eller route-pickers.** Dessa
  stannar i build_site.py för denna PR.
- **Rör aldrig testfiler.** De ska passera via re-exports.

## Konstruktion
1. Skapa `packages/generation/build/__init__.py` (tom eller med
   docstring + re-exports).
2. Skapa `packages/generation/build/renderers.py` med:
   - Modul-docstring som förklarar att filen är extraherad från
     `scripts/build_site.py` per B13a step C, ADR-länk om relevant.
   - Importer från `scripts/build_site.py` för helpers som
     renderers beror på (variant_css, _hero_cta_label,
     _nav_items_from_scaffold, etc. — gör inte cirkulär import:
     identifiera alla externa beroenden och importera dem från rätt
     plats).
   - Kopiera renderer-funktionerna ordagrant.
3. Skapa `packages/generation/build/static_assets.py` på samma sätt.
4. I `scripts/build_site.py`:
   - Ta bort de flyttade definitionerna.
   - Lägg till re-exports överst (efter befintliga imports):
     ```python
     from packages.generation.build.renderers import (
         render_layout, render_home, render_services, render_about,
         render_contact, render_products, render_faq, render_gallery,
         render_team, render_pricing, render_portfolio, render_map,
         render_menu, render_booking, write_pages,
     )
     from packages.generation.build.static_assets import (
         render_robots_txt, render_sitemap_xml,
         render_og_fallback_svg, render_not_found, render_global_error,
     )
     ```
   - Privata `_render_*` helpers re-exporteras inte (de är
     interna till renderers).
5. Hantera cirkulär-import-risken försiktigt: om renderer-koden
   anropar något från build_site.py som i sin tur anropar tillbaka,
   bryt cykeln genom att antingen (a) flytta helpern också, eller
   (b) använd lazy import inne i funktionsbody, eller (c) öppna en
   draft-PR och fråga operatören i Sprintvakt-inboxen.

## Begränsningar
- `python -m ruff check .` måste vara 0 findings.
- `python -m pytest tests/ -q` måste vara grön (1454 pass + 6
  förväntade skips, samma siffror som baseline 2026-05-25).
- `python scripts/governance_validate.py`, `python scripts/rules_sync.py
  --check`, `python scripts/check_term_coverage.py --strict`,
  `python scripts/sprintvakt_check.py` — alla måste fortsätta vara OK.
- `python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build`
  måste fortfarande producera en korrekt site under
  `../sajtbyggaren-output/.generated/painter-palma/` (verifiera att
  artefakterna ser identiska ut som innan flytten — diff:a en
  `generated-files/`-snapshot mellan före och efter).

## Leverabel
Draft PR mot `jakob-be`. Innehåll:
- `packages/generation/build/__init__.py`
- `packages/generation/build/renderers.py`
- `packages/generation/build/static_assets.py`
- `scripts/build_site.py` (slimmad med re-exports)
- Inga testfilsändringar (om någon krävs är det en regression du
  introducerat — fixa istället för att uppdatera testen).

PR-titel: `refactor(builder): extract page renderers from build_site.py
to packages/generation/build (B13a step C)`

PR-beskrivning ska innehålla:
- Före/efter line-count i `scripts/build_site.py` (förvänta
  ~6313 → ~3700, dvs ~40% mindre).
- Lista över flyttade funktioner per ny fil.
- Bekräftelse att alla tester passerar (kopiera siffrorna).
- Bekräftelse att `painter-palma`-build är artefakt-identisk
  före/efter (diff:a `data/runs/<runId>/generated-files/` mellan
  två körningar).
- Hänvisning till denna prompt + halvtidsrapporten.

## Misslyckande-mod
Om cirkulär-import är blockerande, eller om någon renderer har starkare
beroenden till build_site.py:s helpers än förväntat, öppna en draft-PR
med vad du har gjort + post Sprintvakt-inbox-meddelande via MCP-tool
`post_message`:

```
from: cursor-builder-b13a-step-c
to: jakob-orchestrator
subject: b13a-step-c-blocked
body: <kort beskrivning av cirkulär-import-graf, vilka helpers behöver
       flyttas tillsammans, och en föreslagen scope-justering>
```

Hellre stannad PR + signalering än korrupt half-merge.

## Modellval för agent
Composer 2.5 eller GPT-5-codex — det här är mekaniskt refactor-arbete
där deterministisk noggrannhet > kreativitet. Beräknad tid: 4-6 timmar
för försiktig agent som verifierar mot testerna efter varje grupp.
