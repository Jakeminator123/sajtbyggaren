# Cloud-grind-prompt 1 — Gap 6+7 paired (favicon + OG-image i build-pipeline)

> **Copy-paste hela detta block som första prompt i en ny Cursor Cloud Agent-session.**
> Agenten ska kunna jobba self-contained utan att läsa andra docs.

---

Du är Builder-agent som kör i en cloud-agent-VM (Ubuntu). Repo: `Jakeminator123/sajtbyggaren`. Arbets-branch: **`jakob-be`** (Jakob-lane). Du touchar bara GitHub-remoten — ingen operatörs-lokala maskin är i loopen.

## Mission

Stäng **backend-Gap 6 (favicon multi-size) + Gap 7 (OG-image 1200×630)** i build-pipelinen. Båda gapen är "delvis" idag: Next.js Metadata API rendrar redan `icons` och `openGraph.images` mot operatörens uppladdade filer, och `copy_operator_uploads` kopierar filerna rakt av till `public/uploads/`. Det som **saknas** är deterministisk bildkonvertering så att:

- `media.favicon` → multi-size `public/favicon.ico` (16/32/48/64 px ihop-packade i en .ico-fil).
- `media.ogImage` → center-cropped `public/og-image.png` på exakt 1200×630 px.

Båda kräver `pillow` i Python build-stacken (sharp finns redan på UI-sidan men är JS-only).

## Branch + förutsättningar

```bash
git fetch origin --prune
git switch jakob-be
git pull --ff-only origin jakob-be
git status                   # ska vara clean
git log --oneline -5         # senaste 5 commits
```

Om `git pull --ff-only` misslyckas (non-fast-forward): stoppa och rapportera. `jakob-be` är solo-ägd så det ska aldrig hända, men en annan cloud-agent kan ha pushat under tiden.

Lämna en kort jämförelse i din första rapport: vilken HEAD-SHA du startar från och vilka 3-5 senaste commits du ser. Operatören jämför mot `docs/current-focus.md` "Last verified state".

## Tillåtna paths (write-set)

- `requirements.txt` — lägg till `pillow>=10.0`.
- `scripts/build_site.py` — utöka `copy_operator_uploads()` så favicon + ogImage konverteras innan kopiering till public/. Helst via ny hjälpfunktion (`_convert_favicon_to_ico`, `_convert_og_image_to_1200x630_png`) som lever bredvid `copy_operator_uploads` i samma fil.
- `packages/generation/build/static_assets.py` — om du vill flytta konverteringen dit (renare arkitektur enligt B13a Step C-trenden), gör det. Annars håll den i `build_site.py` och inkludera shim-export här.
- `tests/test_builder_smoke.py` eller ny `tests/test_builder_favicon_ogimage.py` — regression-tester som låser konverteringen.

## Off-limits paths (do not touch)

- `apps/viewser/**` (Christopher-lane).
- `apps/viewser/lib/asset-store/sharp-pipeline.ts` (UI-side sharp, inte vår sak).
- `governance/policies/**` (ingen ny policy behövs — det här är ren build-pipeline-utvidgning).
- `governance/schemas/project-input.schema.json` (schemat har redan `media.favicon` och `media.ogImage` — verifiera men ändra inget).
- `packages/generation/orchestration/scaffolds/**`.
- `apps/viewser/components/**`, `apps/viewser/app/**/*.tsx`.

## Acceptanskriterier

1. `pillow>=10.0` finns i `requirements.txt`. Inget annat tillägg.
2. När `project_input.media.favicon` finns och dess fil-bytes är hittade (disk eller sourceUrl), konverteras innehållet till en multi-size `.ico` med storlekarna 16, 32, 48, 64 px. Filen skrivs till `<target>/public/favicon.ico` (en fil, inte under `/uploads/`). Operatörens orginalfil kopieras fortsatt till `public/uploads/<filename>` så Next.js Metadata API `icons`-blocket fortfarande pekar dit för apple-touch-icon.
3. När `project_input.media.ogImage` finns och bytes är tillgängliga, konverteras innehållet till en center-cropped 1200×630 PNG. Filen skrivs till `<target>/public/og-image.png`. Renderer-koden i `packages/generation/build/renderers.py:336-367` måste fortfarande peka på `/uploads/<filename>` för bakåtkompatibilitet (operatören kan ha redan-genererade sajter där). Lägg till en parallell `metadata.openGraph.images`-post som pekar på `/og-image.png` (1200×630, type `image/png`), och behåll den existerande `/uploads/<filename>`-posten som fallback.
4. SVG-fallback i `render_og_fallback_svg` (rad ~201 i `packages/generation/build/static_assets.py`) är oförändrad. Den används fortsatt när `project_input.media.ogImage` saknas.
5. Om pillow inte är installerad (`ImportError`) **eller** om en uppladdad bild är korrupt: logga en varning på stderr och hoppa över konverteringen utan att avbryta bygget. Operatörens orginalfiler ska fortsatt kopieras till `public/uploads/`.
6. SVG-favicons (`image/svg+xml`) konverteras inte (pillow stödjer inte SVG som input). I så fall: logga "favicon är SVG, hoppar över .ico-konvertering — Next.js Metadata API rendrar SVG direkt", och kopiera SVG:n rakt av till `public/favicon.svg` istället för `.ico`. Renderer-koden hittar redan rätt asset via filnamnet.
7. Inga nya prints i tysta success-paths. Bara prints vid fall-back/skip/error.
8. `python -m pytest tests/ -q` passerar fullt. Nya tester (minst 3): (a) ogImage konverteras till exakt 1200×630, (b) favicon.ico innehåller alla fyra storlekarna 16/32/48/64, (c) SVG-favicon hamnar som `public/favicon.svg` istället för `.ico`. Använd bildbibliotekets egna inspektions-helpers (`Image.open(...).size`, `Image.open(...).n_frames` för .ico).

## Tekniska tips

- pillow .ico-konvertering: `img.save(path, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64)])`. Bild-objektet får ha vilken storlek som helst — pillow skalar ner per size.
- Center-crop till 1200×630: ladda bild → skala så kortast sida matchar 1200/630-ratio (≈1.905) → crop center → resize till exakt 1200×630. Spara med `img.save(path, format="PNG", optimize=True)`.
- pillow installeras via `pip install pillow>=10.0` direkt i din VM (ingen venv-aktivering behövs). Efter raden är tillagd i `requirements.txt`, kör `pip install -r requirements.txt` igen så ny dep landar.
- Asset-bytes hittas redan idag i `copy_operator_uploads`-loopen (rad ~954-1011 i `scripts/build_site.py`). Lägg in konverteringssteget *efter* att bytes är lästa (disk eller sourceUrl) men *innan* `shutil.copy2(source_file, dest)`/`dest.write_bytes(data)`-anropet — eller, renare, gör en separat post-processing-pass över assets med roll favicon/ogImage.

## Final guards (alla ska vara gröna före push)

```bash
python -m ruff check .
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python scripts/sprintvakt_check.py
python -m pytest tests/ -q
```

## Stoppvillkor

Stoppa direkt och rapportera till operatören om:

- En guard failar och du inte kan fixa det med en enkel ändring inom write-set.
- `requirements.txt`-bumpen skapar nya ruff/pytest-failures du inte kan motivera.
- Du måste röra `apps/viewser/**` eller off-limits-paths för att lösa uppgiften.
- Konvertering kraschar på testfiler du inte kan dummy:a runt — behöver vi en ny test-fixture under `tests/fixtures/`?
- `git pull --ff-only` failar (en annan cloud-agent kan ha pushat under tiden).

## Commit-format

Två commits, atomiska:

```
1. chore(deps): add pillow>=10.0 for build-pipeline image conversion
2. feat(build): close Gap 6 + 7 — multi-size favicon.ico + 1200x630 og-image.png
```

Commit-body på engelska (per `governance/rules/branch-discipline.md`), med kort förklaring av varför + filer som rörts. Använd bash here-doc för multi-line message:

```bash
git commit -F - <<'EOF'
chore(deps): add pillow>=10.0 for build-pipeline image conversion

Body line 1
Body line 2
EOF
```

## Push

```bash
git push origin jakob-be
```

Ingen PR. Operatören öppnar sync-PR till `main` när hen bestämmer.

## Rapport tillbaka till operatör

```
Pushed <SHA> till origin/jakob-be.
Tillagt: pillow>=10.0, _convert_favicon_to_ico + _convert_og_image_to_1200x630_png.
Nya tester: <antal>.
Guards alla gröna: ruff 0, governance 18/18, rules_sync OK, term-coverage --strict OK, sprintvakt OK, pytest grön.
Backend-Gap 6 + 7 nu stängda. docs/backend-handoff.md status-tabellen behöver bumpas
(låt Steward göra det via Prompt 3 doc-städ, inte rör docs här).
```

## Parallellitet

- **OK att köra parallellt med:** Prompt 2 (B147), Prompt 3 (doc-städ). Inga gemensamma write-paths.
- **Måste klar innan:** Prompt 4 (Gap 9), Prompt 5 (Gap 10). Båda rör `scripts/build_site.py` så sekventiellt är säkrare.
