# Delade canvases

Den här mappen är den kanoniska, git-spårade källan för projektets delade
Cursor-canvases (interaktiva visuella översikter). De delas mellan Jakob och
Christopher via `main` — precis som all annan dokumentation.

## Canvases

| Fil | Innehåll |
| --- | --- |
| `begreppskarta-sajtbyggaren.canvas.tsx` | Interaktiv begreppskarta: bibliotek (scaffold/variant/dossier/starter), körningsartefakter (project input → site brief → site plan → generation package → byggd sajt), projektminne (project DNA), blueprint-fältgrupperna, faser mot 9/10 samt vad som finns/fattas på `main`. |
| `openclaw-floden.canvas.tsx` | Interaktivt OpenClaw-flöde: Viewser-chatten → samtalsgrinden → konduktörens beslut → KÖR-kedjan (6a/7a–7d) → ny version + preview, plus roller, action-registry och hårda regler. |
| `roller-vs-agenter-modeller.canvas.tsx` | Begreppsklargörande: skillnaden mellan Model Roles (var en LLM anropas), konduktör-roller (vem som förstår en ändring), SOUL-persona (hur chatten låter) och att fristående "agenter"/daemon inte finns här — plus var `gpt-4o` faktiskt körs, motorns 12 Model Roles, gränser och aktuell OpenAI-lineup (live via docs-MCP). |

## Så visas en canvas

Cursor renderar bara canvas-filer från den hanterade mappen
`~/.cursor/projects/<workspace-slug>/canvases/`. Repo-kopian här är källan;
spegla den dit med:

```powershell
python scripts/sync_canvases.py
```

Kör kommandot efter varje `git pull` som rör den här mappen (eller lägg det i
din vanliga uppdateringsrutin). Skriptet hittar rätt Cursor-mapp automatiskt;
om det inte lyckas, peka ut den med `--target`.

Har du i stället förbättrat en canvas lokalt i Cursor-mappen (t.ex. via en
agent-chatt) och vill dela den, dra tillbaka ändringen till repot:

```powershell
python scripts/sync_canvases.py --pull
```

`--pull` hämtar bara filer som redan finns här i mappen, så personliga
canvases följer inte med av misstag.

## Ägarskap och uppdatering (Steward)

Steward äger de delade canvaserna, på samma sätt som `docs/current-focus.md`
och `docs/handoff.md`:

- Fakta-blocket i begreppskartan (antal scaffolds/dossiers på disk,
  kvalitetsmålen från `page-quality-traits.v1.json`) räknas fram från repot:

  ```powershell
  python scripts/update_canvas_facts.py          # uppdatera blocket
  python scripts/update_canvas_facts.py --check  # verifiera utan att skriva
  ```

  `--check` ingår i stewards docs-checks (se `docs/orchestrator-playbook.md`)
  och körs dessutom automatiskt efter merge till `main` av workflowet
  steward-auto-bump, som committar en uppdatering vid drift.

- Handsiffrorna (kvalitetstelemetri i `QUALITY_TELEMETRY`, fasstatusarna i
  `PHASES`, OpenClaw-stegens status) kan inte räknas fram automatiskt — de
  uppdateras av Steward vid varje pass där `docs/current-focus.md` ändrar
  läget.

## Regler för innehållet

- Operatörstext i canvaserna är svenska; kodidentifierare engelska.
- Canvas-filerna importerar bara från `cursor/canvas` och bär inline-data —
  inga nätverksanrop, inga andra beroenden.
- Mappen är undantagen från term-coverage-skanning (samma behandling som den
  äldre, numera oanvända spegeln under `docs/heavy-llm-flow/canvases/`),
  eftersom filerna medvetet katalogiserar även förbjudna alias i pedagogiskt
  syfte.
