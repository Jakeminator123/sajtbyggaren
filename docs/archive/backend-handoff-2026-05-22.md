# Backend hand-off — 22 maj 2026

**Mottagare:** Jakob.
**Från:** Christopher (christopher-ui-branchen).
**Status:** Inga blockerande backend-tasks. Allt detta dokument beskriver är pushat och fungerar med din nuvarande backend.

---

## TL;DR

Sex nya commits på `christopher-ui` sedan din senaste push (`502b5c0`):

| Commit | Vad |
| --- | --- |
| `bbb4d52` | Sprint 0 (cleanup efter din M2-resolver) + Sprint 1 (LCP-optimering, 404/500-sidor, print-styles, OG-fallback) |
| `29d0927` | Sprint 2 (JSON-LD `LocalBusiness`, robots.txt, sitemap.xml, a11y skip-link) |
| `e0a44d…` | Bug-fixes + AI-bildgenerator via GPT Image 1.5 |
| `706a88a` | **Operator-uppladdade bilder fetchas från `sourceUrl` (Vercel Blob)** — fix för "uppladdade bilder visas inte" |
| `e4c179d` | Live-badge bekräftar token-postMessage end-to-end (Site Inspector → iframe → ack) |
| `d8d6209` | **Sprint A.1**: 10-stegs brand color scales `--primary-50..900` + `--accent-50..900` |
| `28f849f` | **Sprint A.2**: Tone-driven typography overlay (calm/bold/playful/premium) |

Alla ändringar är 100 % additiva. Pipeline, schema, resolver och planner är orörda. Du kan pulla utan att granska detaljerat — men om du vill säkra det finns checklistan i avsnitt 4 nedan.

### Sprint A — visuell variation (22 maj sent)

Två commits gör att olika sajter faktiskt SER olika ut beroende på brand/tone, istället för att alla landa på samma mid-tone-blå + Inter.

**`d8d6209` — 10-stegs brand color scales**

- Nya helpers `_hex_to_hsl` / `_hsl_to_hex` / `_build_color_scale` i `scripts/build_site.py` (efter `_foreground_for_background`).
- `variant_css` emitterar nu `--primary-50` .. `--primary-900` + `--accent-50` .. `--accent-900` som CSS-tokens. 50 = ljusast (97% L, för subtila bakgrundstinter), 900 = mörkast (18% L, för text-på-ljust).
- Saturation cap:as vid 85% så hög-mättade input som `#ff0000` inte ger neon-aktiga CTA-knappar.
- Skalan baseras på operatörens `brand.primaryColorHex` om det är satt, annars variant-defaulten. Helt deterministiskt.
- **Befintliga `--primary`/`--accent`-tokens ligger kvar exakt som idag** — additivt, byte-stable för existerande tester.
- **Render-funktionerna använder ännu inte tokens** — det är nästa naturliga steg (välj 2-3 platser där neutral-grå byts mot `var(--primary-50)`) men jag väntade med det för att inte spreda diff över hela `render_layout`/`render_home`. Du kan ta det när du är tillbaka, eller jag fortsätter i en separat commit imorgon.

**`28f849f` — tone-driven typography overlay**

- Ny dict `_TONE_TYPOGRAPHY` med fyra arketyper:
  - `calm` / `lugn` / `wellness` → Cormorant Garamond + Inter
  - `bold` / `modern` / `tech` → Space Grotesk + Inter
  - `playful` / `warm` / `friendly` → Quicksand + Nunito
  - `premium` / `editorial` / `luxury` → Playfair Display + Inter
- Nya helper `_typography_overlay_for_tone(project_input)` returnerar overlay-dict eller `None`.
- `variant_css` har ny kwarg `typography_overlay=` — om satt överrider den `_typography_for_variant`. Om `None` (default + alla befintliga tester) → identisk output.
- `patch_globals_css` wirar `project_input.tone.primary` → overlay → CSS.
- Generiska toner som `"professional"`, `"trustworthy"` mappas medvetet till `None` så variant-defaulten används. Vi vill bara override:a när vi har ett tydligt designval.

**Test-status (uppdaterat efter Sprint A):**
- Python: hela `pytest tests/ -q` grön (1244+ tests). +12 nya tester i `test_builder_smoke.py` (5 för palette, 7 för typografi).
- Ruff: 0 findings.
- `check_term_coverage.py --strict`: 0 findings (registrerade `TokenAckMessage`, `CircleCheck`, `MessageEvent` från tidigare commits).

**Vad du KAN testa snabbt** (efter `git pull origin christopher-ui`):

```bash
source .venv/bin/activate

# 1. Verifiera färgskala-emission
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build
grep -E "primary-(50|500|900)" /Users/<user>/Desktop/sajtbyggaren-output/.generated/painter-palma/app/globals.css

# 2. Verifiera tone-typography overlay end-to-end
# (Sätt tone.primary="playful" i en kopia av project-input och bygg)
jq '.tone.primary = "playful"' examples/painter-palma.project-input.json > /tmp/playful.json
python scripts/build_site.py --dossier /tmp/playful.json --skip-build
grep -E "Quicksand|Nunito" /Users/<user>/Desktop/sajtbyggaren-output/.generated/painter-palma/app/globals.css
```

Förväntat: `globals.css` innehåller alla 20 scale-tokens + Quicksand-importen.

**Vad jag medvetet INTE rörde** (väntar på din review):
- Schema (`project-input`, `site-plan`, `site-brief`) — inga ändringar.
- Plan-pipeline (`packages/generation/planning/plan.py`) — orörd.
- Brief-pipeline — orörd.
- Render-funktioner (`render_home`, `render_layout`) — orörda. Scale-tokens emitteras men konsumeras inte av render än.

---

## 1. Vad är klart och fungerar idag

### Genererade sajter får automatiskt:

- **LCP-prestanda**: `<link rel="preconnect">` mot Google Fonts, `fetchPriority="high"` + `decoding="async"` på hero-bilder, scroll-driven parallax.
- **Branded 404 + 500-sidor**: `app/not-found.tsx` + `app/error.tsx` med företagsnamn, telefonnr, reset-knapp.
- **Print-styles**: `@media print` nollar header/footer/animations.
- **Auto-OG-image**: 1200×630 brand-färgad SVG till `public/og-image-fallback.svg` om operator inte uppladdat — luma-säkrad text.
- **SEO-baseline**: JSON-LD `LocalBusiness` (med adress, telefon, områden, öppettider) inline i `<head>`, `robots.txt`, `sitemap.xml` med rätt priority per route.
- **A11y**: Skip-link ("Hoppa till innehållet") med WCAG 2.1 SC 2.4.1-pattern.

### Wizard:

- **AI-bildgenerator** via GPT Image 1.5. Operatör kan klicka "Generera med AI" bredvid varje upload-zone (logo, hero, gallery, favicon, ogImage) och få en AI-genererad bild via OpenAI Images API.
- Bilden sparas via samma `AssetStore.save()` som upload-flödet (alltså LocalAssetStore eller VercelBlobAssetStore). **Inga schema-ändringar.**

### Test-status:

- Python: 1244+ tests gröna (+ 37 nya `tests/test_build_media_rendering.py`).
- TypeScript: `tsc --noEmit` rent.
- ESLint: 0 findings.
- Ruff: 0 findings.

---

## 2. Vad du INTE behöver göra

Följande är NÄR-frågor från tidigare hand-offs som nu är icke-aktuella:

- ❌ **Lägga till AI-flagga i AssetRef-schema** — vi behöver inte särskilja AI-genererat från upload-genererat i `project-input.json`. Båda är giltiga `AssetRef` med `sourceUrl`/`filename`.
- ❌ **Pipeline-mappning för `directives.aiGenerated`** — har inte införts. AI-bilder ser ut som vanliga uploads för pipeline:n.
- ❌ **Nya `/api/*`-routes från Python-sidan** — `/api/generate-image` ligger i Next.js-appen (`apps/viewser/app/api/generate-image/route.ts`), inte i `scripts/*`.

---

## 3. Vad du KAN göra (frivilligt)

Inget av detta är blocking, men om du har bandbredd och vill polera ytterligare:

### 3.1 Verifiera Sprint 2:s SEO-output i en riktig build

```bash
# Säkerställ att din branch är synkad
git pull origin christopher-ui

# Kör en E2E-build mot en av examples-mappens dossiers
source .venv/bin/activate
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build

# Verifiera output
cat /Users/<user>/Desktop/sajtbyggaren-output/.generated/painter-palma/public/sitemap.xml
cat /Users/<user>/Desktop/sajtbyggaren-output/.generated/painter-palma/public/robots.txt
grep -A 1 "application/ld" /Users/<user>/Desktop/sajtbyggaren-output/.generated/painter-palma/app/layout.tsx
```

Förväntat: sitemap.xml listar alla 4 routes (`/`, `/tjanster`, `/om-oss`, `/kontakt`), robots.txt har `Sitemap: /sitemap.xml`, layout.tsx har giltig JSON-LD `LocalBusiness`.

### 3.2 Verifiera AI-bildgeneratorn lokalt (kräver `OPENAI_API_KEY`)

```bash
cd apps/viewser
npm run dev  # eller npm run dev:http om du inte har lokala HTTPS-certs

# Öppna http://localhost:3000, gå till wizardens steg 5 (Bilder & media).
# Klicka "Generera med AI" bredvid t.ex. Favicon-rutan.
# Skriv en prompt, välj stil, klicka "Generera".
# Förväntat: 8-30 sek loading, sedan preview. "Använd den här" sparar
# via befintlig AssetStore.
```

Kostnad: ~$0.04/bild vid default `quality=medium`. Defaultmodell `gpt-image-1.5` är ~20% billigare än `gpt-image-1`.

### 3.3 Lägg in `OPENAI_IMAGE_MODEL` + `OPENAI_IMAGE_QUALITY` i prod-secrets

När/om vi deployar till Vercel behöver dessa env-vars sättas där:

```
OPENAI_API_KEY=<samma som idag för briefModel/planningModel>
OPENAI_IMAGE_MODEL=gpt-image-1.5     # default — eller "gpt-image-1"
OPENAI_IMAGE_QUALITY=medium          # default — "low" för draft, "high" för final
```

Båda är optional med rimliga defaults; sätt dem bara om du vill kontrollera modellval/kostnad centralt.

### 3.4 Rate-limiting på `/api/generate-image` om vi går publik

Endpointen är idag `assertLocalhost`-skyddad så ingen externt anrop möjligt. När/om vi publicerar Sajtbyggaren bör vi lägga en rate-limit (typ 10 generationer/IP/timme) i en Vercel Edge Middleware. Det är en framtida task — inte aktuellt nu.

---

## 4. Granska-checklista (om du vill säkra dig)

```bash
git pull origin christopher-ui
git log --oneline 502b5c0..HEAD  # se mina 3 commits
git diff 502b5c0..HEAD -- scripts/build_site.py | head -100  # snabb-titt
git diff 502b5c0..HEAD -- packages/  # förväntat: tomt
git diff 502b5c0..HEAD -- governance/schemas/  # förväntat: tomt

# Kör hela python-suiten
source .venv/bin/activate
python -m pytest tests/ -q --deselect tests/test_docs_freshness.py --deselect tests/test_viewser_files.py --deselect tests/test_term_coverage.py

# Förväntat: alla tests passerar (1244+ st)
```

---

## 5. Frågor till mig om något inte stämmer

Skriv direkt i Cursor i din branch — jag ser pull-requesten när du pushar. Eller skicka WhatsApp.

— Christopher
