---
title: Följdprompt-loopen — namn, flöde och begrepp
status: aktiv förklaring
owner: operator + backend
---

# Följdprompt-loopen

Detta dokument namnger och förklarar vad som händer när du skriver en prompt
eller en följdprompt i chatten och sajten byggs om. Det här är den kanoniska
källan; `FOLJDPROMPT-LOOPEN.md` i repo-roten är bara en pekare hit. Begreppen
nedan speglar `docs/glossary.md` (avsnittet "Följdprompt-loopen").

## Namnet

- **Följdprompt-loopen** = operatörens vardagsord för "skriv en ändring → ny version".
- Tekniskt körs den av **Hosted Build** (Vercel Sandbox) + **OpenClaw-dirigenten**.
- Kärnan i koden heter **OpenClaw action bridge → KÖR-7-kedjan**:
  `router → context → patch → apply → targeted render`.

## Flödet, steg för steg

```
1. Du skriver i chatten ──POST /api/prompt {mode:"followup", siteId}──► viewser (Next.js/TS = skalet)
2. /api/prompt: snabb förklassning — ren fråga? → svara direkt (ingen sandbox).
                                       annars ↓
3. startHostedBuild (apps/viewser/lib/hosted-build-runner.ts):
     - skapar en Vercel Sandbox FRÅN build-context-tarballen (= Python-motorn)
     - kör den detached; HTTP-svaret pollar bara KV-status (svarsbudget ~280s)
4. INNE i sandboxen (Python):
     pip install -r requirements.txt
       → run_openclaw_followup.py --apply         (dirigenten / apply-bryggan)
            └─ run_followup_chain (KÖR-7, i build_site.py):
                 router → context → patch → apply (ny immutabel version v+1)
                 → targeted render + next build
       → (om inget gick att applicera: legacy via prompt_to_project_input.py + build_site.py)
     → laddar upp filerna till blob: generated/<siteId>/...
     → skriver KV-pekare (current + run-state)
5. Klienten ser "done" (eller budget-meddelandet) → previewen laddar om → ny version syns
```

## De fyra skripten — och NÄR de körs

| Skript | Roll | När |
|---|---|---|
| `scripts/classify_message.py` | Router (deterministisk klassning) | Körs av viewser LOKALT (router-classify-runner.ts) för snabb "är detta en edit / ska preview startas". I det hostade tunga bygget klassas i stället INNE i run_openclaw_followup.py. |
| `scripts/run_openclaw_followup.py` | Dirigent / apply-brygga | FÖRST i en **följdprompt** (`--apply`). Klassar, beslutar, och kör KÖR-7-kedjan. Faller till legacy om inget kunde appliceras. |
| `scripts/prompt_to_project_input.py` | Prompt/wizard → Project Input | Vid **init-bygge** (ny sajt) och i legacy-följdvägen. Härleder företaget/strukturen och skriver Project Input. |
| `scripts/build_site.py` | Byggaren (+ KÖR-7-kedjan) | Bygger sajten (next build, Quality Gate, immutabel version). `run_followup_chain` (KÖR-7) bor här och importeras av dirigenten. |

`scripts/` har ~46 .py-filer totalt, men bara dessa är bygg-vägen; resten är
governance/eval/underhåll. Bakom dem ligger motor-biblioteket
`packages/generation/` (brief, planning, codegen, quality_gate, repair,
orchestration/{router,context,patch,apply,openclaw}, followup/ med ~13
directives-moduler, build/renderers).

## Varför körs Python-tarballen varje gång?

Motorn ÄR Python (`build_site.py` + `packages/generation/`). Viewser (Next.js/TS)
är bara skalet — UI + dirigering. På hostad Vercel finns ingen lokal Python eller
disk, så motorn körs i en Vercel Sandbox, och **build-context-tarballen ÄR den
Python-motorn** (uppladdad till blob). Varje bygge bootstrappar om motorn i en
färsk sandbox → därför pip-installeras allt på nytt varje gång.

### Arkitektur-trade-off (sandbox vs egen tjänst)

| Alternativ | Plus | Minus |
|---|---|---|
| Vercel Sandbox (nu) | serverlös, skala-till-noll, leverantörsneutral, ingen server att underhålla | kallstart + ominstallation per bygge (minuter) |
| Egen Python-tjänst (Render/Railway/Fly, Docker-image med deps förbakade) | varm, deps cachade → snabbt, ingen ominstallation | alltid-på-server (kostnad + drift + skalning) |
| "Lagringsställe" (blob) | tarballen LIGGER redan i blob | lagring ≠ compute — koden måste KÖRAS någonstans |

Sandbox valdes medvetet för serverlös/noll-underhåll. Mellanväg utan en
stående server: sandbox-reuse (`VIEWSER_SANDBOX_REUSE`, preview), slimmad pip
(bygg-only deps) och pip-cache → kapar ominstallationen.

## Begreppen — vad heter vad

| Begrepp | Vad det är | Exempel |
|---|---|---|
| Capability | Abstrakt slug — vad en sajt kan ha (kontraktet) | gallery, faq-section, contact-form |
| Dossier | Implementationen av en capability (förskrivna instruktioner som monteras) | image-gallery (→ gallery), faq-accordion (→ faq) |
| `editKind` (vardagsord: action) | Typen av följdprompt-ändring; kanoniskt routerfält i `router-decision.schema.json` | component_add, section_add, copy_change, route_remove, nav_hide |
| Generativt recept | Deterministisk tsx-mall som SKRIVER ny kod (undantaget) | image-placeholder-grid |

## "Action" — exempel och faktisk status

En **action** = edit-kind:en (typen av ändring). Status idag:

| Du skriver... | Action | Status |
|---|---|---|
| "Ändra färg på bakgrunden" | visual_style | live + syns |
| "Lägg in en platshållare/knapp" | component_add (ev. generativt recept) | live (placeholder-grid syns) |
| "Ta bort sidan Om oss" | route_remove / nav_hide | live (ADR 0060) |
| "Lägg till en sida som heter Om matmagasinet" | route_add | klassas men EJ inkopplad → ärlig no-op (planerad) |
| "Skapa en komponent som är guldig och rinner vatten" | fri codegen | EJ byggt — kräver Agent Code Mode (framtida) |

Det du gjorde ("lägg till 6 bildplatshållare") var alltså en **edit av typen
component_add → generativt recept (image-placeholder-grid)** — varken en dossier
eller en capability, utan kod-genererings-vägen. Det är frö nr 1 mot fria edits
(Agent Code Mode).

## Frontend ↔ backend: kontaktpunkterna (hur man "får kontakt")

Hela motorn är frontend-agnostisk. Vilken frontend som helst (dagens viewser,
en ny sida, en annan klient) behöver bara prata med **tre sömmar** — resten
(Python-motorn i sandbox + KV + blob) bryr sig inte om vem som ringer.

| Söm | Vad | Riktning |
|---|---|---|
| `POST /api/prompt` | Starta bygge/följdprompt. Body: `{prompt, mode:"init"\|"followup", siteId?, baseRunId?, toolIntent?, markedSections?}`. Svar: `{runId, siteId, version, buildStatus, buildResult, bridge, conversation, answerText, ...}` ELLER budget-meddelandet vid kallt bygge. | frontend → backend |
| `GET /api/hosted-build/<runId>?siteId=<siteId>` | Polla bygg-status (`phase`: queued→installing→project-input→building→uploading→done/failed; vid done även `result`). Site-bunden (B196). | frontend → backend |
| Preview | `POST /api/preview/<siteId>` startar/återanvänder en Vercel Sandbox; iframen visar resultatet. Filerna läses ur blob `generated/<siteId>/` (generated-blob-source) eller via preview-bundle-tarball. | frontend ↔ sandbox |

**Delad state (sanningen):** KV-pekare binder ihop allt —
`viewser:site:<siteId>:run-state` (PI/meta + artefakt-URL:er per version),
`viewser:site:<siteId>:current` (`{buildId, blobPrefix}` = aktiv build),
`viewser:hosted-run:<runId>` (status), `viewser:run:<runId>` (run-index).
Blob håller artefakterna: `generated/<siteId>/` (byggd sajt),
`run-artifacts/<siteId>/v<N>/` (kanoniska artefakter), `run-state/<siteId>/v<N>/`
(PI/meta-snapshots), `build-context/current.tar.gz` (själva Python-motorn).

**Bygga en NY frontend mot samma motor:** implementera bara (1) POST `/api/prompt`,
(2) poll `/api/hosted-build`, (3) bädda in preview-URL:en. Ingen kunskap om
Python, scaffolds eller capabilities behövs på frontend-sidan — kontraktet är
JSON in/ut + en preview-URL. Det är därför motorn kan flyttas (t.ex. till en egen
Render-tjänst) utan att frontend ändras: byt bara var `/api/prompt` kör motorn.

## route_add: så skulle jag lägga in "en ny sida"

`route_add` ("lägg till en sida som heter X") klassas redan av routern men är
**inte inkopplad** (ärlig no-op idag, listad bland ej-ägda edit-kinds i
`build_site.py`). Den symmetriska systern `route_remove`/`nav_hide` (ADR 0060)
visar exakt mönstret att spegla:

1. **router** (finns redan): `route_add` med en sid-etikett/`routeId`.
2. **resolver** — ny `resolve_added_routes(...)` i
   `packages/generation/followup/route_directives.py`: validera den nya
   `routeId`/etiketten (kollision mot befintliga routes, slug-säkerhet, max-antal),
   och välj ett sektions-set för sidan (t.ex. återanvänd scaffoldens
   `optionalSections` eller ett minimalt hero+contact-cta-set).
3. **apply** — skriv en **sticky** `directives.addedRoutes`-lista (spegel av
   `disabledRoutes`), så sidan överlever framtida byggen.
4. **build_site** — beräkna `activeRoutes = defaultRoutes − disabledRoutes +
   addedRoutes`, **rendera en `page.tsx`** för den nya routen (här ligger jobbet:
   en route-renderare som återanvänder befintliga `render_section_*`-helpers —
   samma renderer-lager som renderers-slice-arbetet rör), och **tråda in
   nav-länken** via `_nav_items_from_scaffold` (spegel av nav_hide, fast tvärtom).
5. **Honesty-grind** — okänd/dubblett/ogiltig → ärlig no-op (`route_add_unsupported`),
   aldrig en påhittad sida.

Tyngdpunkten är steg 4 (renderaren för den nya sidan), inte wiringen — exakt den
"synlig render per scaffold är den linjära kostnaden"-poäng som gäller alla
sektionstyper. Wiring ~50–80 rader (resolver + apply + chain-gren); renderaren
beror på hur rik sidan ska vara.
