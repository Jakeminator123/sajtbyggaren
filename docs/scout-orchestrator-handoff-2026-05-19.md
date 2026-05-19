# Scout-orchestrator-handoff — 2026-05-19

För nästa Cursor-agent (eller annan IDE-agent) som tar över rollen
**Scout-orkestrator** för Viewser-overlay-E2E-Scout-spåret 2026-05-19.

Detta är en agent-handoff, inte en operator-handoff. Det är ett tillägg
ovanpå standard-rollerna i [`docs/agent-prompts.md`](agent-prompts.md);
det ersätter inte Scout/Builder/Steward-disciplinen utan beskriver hur
en Scout också kan orkestrera Cloud Agents + RO-reviews + auto-merge
under en längre arbetscykel.

## Roll-definition

**Scout-orkestrator** = en Scout-agent som dessutom:

- Spawnar **Cloud Agents** med Builder-prompts (operatören startar dem
  via cursor.com / Cursor Cloud).
- Babysittar PRs via [`babysit`-skill](../.cursor/skills-cursor/babysit/SKILL.md)
  loopen: pollar CI, triagerar Bugbot/Codex-kommentarer, flaggar
  merge-redo eller fixar konflikter.
- Spawnar **RO-review-subagents** (`Task` med `readonly=true`) som
  granskar PR-diffs mot Scout-rapportens fynd och Builder-promptens
  scope-disciplin.
- Vid operatörs-OK: **auto-mergar** PRs via `gh pr merge --squash --delete-branch`
  i sekventiell ordning (lättast → mest konflikt-prone).
- Löser merge-konflikter additivt (B-IDs är typiskt ortogonala mot
  varandra; konflikter på `docs/known-issues.md` lågprio).
- Bumpar `docs/known-issues.md`-summary-line per merge (92 → 93 → 94 → 95
  osv.) så `tests/test_known_issues_summary_line_matches_script` passerar.

Roll-rena Scout (read-only mot kod, write mot rapport) gäller fortfarande.
Cloud Agents fixar produktkod. Operatören mergar (eller delegerar till
Scout-orkestrator via "merga PR #X" eller "kör Cloud Agents auto-pilot").

## Pågående tillstånd vid handoff (2026-05-19, sent eftermiddag)

### Vad är klart

- **Viewser-overlay-E2E-Scout** rapport på `docs/reports/viewser-overlay-e2e-scout-2026-05-19.md`.
  - Case 1 (keramik): snitt 7.3/10. Verifierade B101 + B102 + B128 live.
  - Case 2 (frisörsalong): snitt 7.4/10. Verifierade B120 live + Page Intent-gap (Obs 3).
  - Case 3a (1753skincare utan scrape): snitt 6.6/10. Verifierade B95/B98 country-only-suppress + 4 nya fynd.
  - Snitt över 3 case: ~7.1/10 (över beslutsregelns 7-tröskel).
  - Case 4 / 5 / 6 / Spår B / 3b: ej körda. Markerade som "kvar för senare".
- **Auto-merge-pipeline** (under operatörens 1-h-paus): 4 PRs mergade i ordning #39 → #40 → #41 → #42 + en cleanup-commit. Plus PR #43 (B133-hardening efter Codex review).
- **Cleanup**: 3 stale `cursor/*`-branches på origin raderade. 3 worktrees borttagna. 3 lokala feature-branches städade. backup-30 + backup-31 finns kvar.
- **`scripts/tree_view.py`** (denna commit): committad utility för LLM-context. Ersätter operatörs-lokala `tree_v2.py`-arbetsflöde med en delad version som alla agenter kan köra.

### Vad pågår (när handoff skrivs)

**Tre Cloud Agents kör parallellt på cursor.com Grind-mode:**

1. **B134** — wizardMustHave-arv i `generate_followup` orsakar stale
   `pageIntentWarnings` i v2. Branch: framtida `cursor/...`. Förväntad
   PR-titel: `fix(prompt-helper): close B134 — reset wizardMustHave when followup has new discovery`.
2. **B135** — `fieldSources["contact.phone"]="brief"` är osant när placeholder
   används. Förväntad PR-titel: `fix(discovery): close B135 — fieldSources distinguish placeholder from brief`.
3. **F2 + Steward-bump** — fix stale `Fix: 56272c7` i B131-entry + bumpa
   `current-focus.md` + `handoff.md` + Scout-rapport-status. Förväntad
   PR-titel: `docs(steward): close F2 fix-SHA + bump verified state`.

Builder-prompterna för alla tre finns i Scout-rapporten under
"Builder-prompts" eller i föregående chatt-historik. Spara som referens.

### Vad är kvar att göra

| Item | Spår | Vem | Prio |
| --- | --- | --- | --- |
| Babysitt B134 + B135 + F2/Steward PRs när de skapas | Scout-orkestrator | Du som ny agent | Hög |
| Sekventiell auto-merge när alla 3 är gröna + RO-reviewade | Scout-orkestrator | Du | Hög |
| Slutlig Steward-bump efter alla mergar | Steward (separat) eller automerged via F2/Steward-PR | Operatör eller Steward | Medel |
| Scout fortsättning: Case 4 (sköldpaddssoppa) | Operatör i wizard + jag tolkar output | Operatör | Medel |
| Scout fortsättning: Case 6 (follow-up) | Operatör i wizard + B71-byte-stabilitet | Operatör | Medel |
| Scout fortsättning: Case 3b (scrape) | Operatör klickar Hämta-knappen | Operatör | Låg |
| Spår B variant-experiment (B1 keramik+earth-wellness, B2 frisör+warm-craft) | Operatör + Scout-tolkning | Operatör | Låg |
| Tree-script-förbättring (`scripts/tree_view.py`) | Klar i denna commit | Klar | — |

### Aktivt bug-scope vid handoff

- 25 aktiva
- 0 misplaced
- 5 unknown
- 95 stängda (efter PR #43-merge); kommer öka med 1-2 efter B134/B135-merger

**Öppna B-IDs som är direkt i scope för pågående arbete:**

- B134 — wizardMustHave-arv (Cloud Agent 1).
- B135 — fieldSources placeholder-vs-brief semantik (Cloud Agent 2).
- B129 — `_DEFAULT_VARIANT_BY_SCAFFOLD` hardcoded (väntar på variant-promotion-sprint, ingen direkt fix).
- B125 — browser-preview-fallback (egen ADR krävs).
- B59 — StackBlitz embed parkerad efter 2026-05-15.

**Öppna B-IDs som är out-of-scope för denna runda:**

- B47, B49, B53, B67, B80-B87, B97, B98 m.fl. Se `docs/known-issues.md`.

## Verktyg och rutiner

### Polla PR-status

```powershell
gh pr list --state open --json number,title,headRefName,mergeable,mergeStateStatus,statusCheckRollup -L 10
```

### Detaljerad CI-status per PR

```powershell
gh pr checks <num>
gh pr view <num> --json mergeable,mergeStateStatus,statusCheckRollup
```

### Spawna RO-review-subagent

Använd `Task`-tool med `subagent_type=generalPurpose` + `readonly=true`
+ `run_in_background=true`. Prompt-mall:

```text
Du är read-only review-agent (Scout RO-review). Granska PR #<N> i
Jakeminator123/sajtbyggaren mot Builder-promptens scope och Scout-
rapportens fynd. Rör inte git, posta inga PR-comments. Returnera
JSON-output med verdict + findings + checklist + sammanfattning på
svenska.
```

Subagent kör i bakgrunden + skickar slut-svar via system-notifikation.

### Lös rebase-konflikter additivt

Vid konflikt på `docs/known-issues.md`: behåll båda B-IDs i Stängda-sektionen,
ta bort `<<<<<<<`/`=======`/`>>>>>>>`-markörer, säkerställ kronologisk
ordning (mergad först överst).

Vid konflikt på `scripts/build_site.py` eller `scripts/prompt_to_project_input.py`:
båda PRs lägger typiskt till nya helpers. Behåll båda. Lägg de extra
helpers i samma sektion. Markera med kommentarer om scout-orchestrator-merge.

### Auto-merge

```powershell
gh pr merge <num> --squash --delete-branch
git switch main
git pull --ff-only origin main
python scripts/check_term_coverage.py --strict   # verifiera EXIT 0
python -m pytest tests/test_bug_scope_discipline.py tests/test_docs_freshness.py -q
```

### Tree-view för LLM-context

```powershell
python scripts/tree_view.py --llm --max-depth 3 --copy
python scripts/tree_view.py apps/viewser --max-depth 2 --with-size
python scripts/tree_view.py packages --ext .py
```

Operatören kan fortsätta använda lokal `tree_v2.py` om hon vill —
`tree_v*.py`-mönstret är fortfarande i `.gitignore`. Skillnaden är att
agenter nu har en delad utility att referera till.

### Backup-hygien

Före varje sprintrunda eller merge-burst: skapa nästa `backup-N` från
synkad main:

```powershell
$next = (git for-each-ref --format='%(refname:short)' refs/heads refs/remotes |
  Where-Object { $_ -match '(?:^|/)backup-(\d+)' } |
  ForEach-Object { [int]([regex]::Match($_, 'backup-(\d+)').Groups[1].Value) } |
  Measure-Object -Maximum).Maximum + 1
git branch "backup-$next"
git push origin "backup-$next"
```

Senast skapad: `backup-31` (från `7ac14c4` innan auto-pilot-mergerna).

## Utestående beslut för operatören

1. **Hur många Scout-case till?** Snitt 7.1/10 ligger redan över beslutsregelns
   7-tröskel. Om alla 6 case + Spår B levererar kan vi ge slutverdict; om
   operatören är tröttnad kan vi stänga rapporten med "3 case + sammanfattning"
   och spara resten som follow-up.
2. **Project DNA-sprint?** Beslutsregeln säger ≥7/10 OCH inget case <6.5
   → Project DNA-sprint. Case 3a fick 6.6/10, dvs marginalen är liten.
   Beslut bör fattas efter B134/B135-merger eftersom de förbättrar
   provenance + follow-up-stabiliteten.
3. **B125 browser-fallback ADR.** Krävs innan extern kundyta. Ej Scout-
   orchestrator-arbete; egen sprint.
4. **B129 variant-promotion-sprint.** Köpunkt #6 i `docs/current-focus.md`.
   Kräver variant-selection-logik (taxonomy-edit, dossier-rationale,
   wizard-val, eller operator-pin) + ADR för governance-flytt av
   `_DEFAULT_VARIANT_BY_SCAFFOLD`.

## Mot 9/10 i `docs/product-operating-context.md`

Produktmål: 9/10 kvalitet på företagshemsidor. Scout-snitt 7.1/10 nu.
Skillnaden mellan 7 och 9 ligger i (subjektivt rangordnat):

| Gap | Nuläge | Vad krävs |
| --- | --- | --- |
| **Visuell renderingsverifiering** | Bara TSX-källkod granskad. mobileFirst + visualPolish är 0/10 | Localhost-rendering + screenshots, eller server-byggd preview (B125-fallback). Eller Spår B variant-experiment för visuell jämförelse. |
| **Page Intent som bygger routes** | B132 = warning-only. Operatör som väljer "Bildgalleri" får INTE faktisk `/galleri` | Variant B/C av B132: extra-routes från `_PAGE_TO_ROUTE_HINT`. Egen sprint, kräver scaffold-template-utvidgning. |
| **Browser-fallback för preview** | B125 öppen | Egen ADR + en av: server-byggd statisk preview, lokal `next dev`-park, "Öppna i StackBlitz"-fallback, Vercel preview-deployments. |
| **Project DNA / semantic follow-up** | B71 markerad unverified | Semantic merge i `merge_followup_project_input` så story/tagline/tone uppdateras vid follow-up. Egen sprint. |
| **Capability/Dossier gaps** | booking, contact-form, payments, faq → varningar men ingen Dossier-implementation | Dossier-importer för minst contact-form (resend), booking (TBD), payments (stripe-checkout). Egen sprint. |
| **Variant-selection** | 8 nya variants är dead-on-arrival per B129 | Variant-promotion-sprint (Queue #6). Kräver discovery-taxonomy-edit eller Backoffice-pin. |
| **Konkret content** | service-descriptions är generic-fallback ("Tydlig hjälp med X och enkel väg vidare") | briefModel/codegenModel-prompt-tuning för rik service-summary. Eller wizard-fält för description default-text. |

**Ordning jag rekommenderar för att nå 9/10 utan att överbygga:**

1. Slutför B134 + B135 (pågår i Cloud Agents) — fixar follow-up-stabilitet och provenance.
2. **Spår B variant-experiment** — bekräfta visuellt att 8 nya variants gör skillnad. Ger underlag till B129-sprint.
3. **B125 browser-fallback ADR** — produktblockare innan extern kund.
4. **Page Intent Variant B** (extra routes) — krävs för seriös företagshemsida.
5. **Project DNA semantic merge** — follow-up-kvalitet.
6. Capability/Dossier-gaps + variant-promotion-sprint som parallellspår.

## Vad nästa Cursor-agent säger till operatören först

Föreslagen första-svar-prompt när nästa agent öppnar denna chat:

```text
Tar över Scout-orkestrator-rollen. Läst `docs/scout-orchestrator-handoff-2026-05-19.md`.

Status:
- Main = <kör `git rev-parse origin/main` för aktuell SHA>
- Cloud Agents B134/B135/F2 pågår — pollar status nu.
- Backup-31 är säkerhetsnät.

Säg "fortsätt" så pollar jag PRs varje 5 min och flaggar när merge-redo.
Säg "ny riktning" om du vill byta spår.
```

## Tack

Tack för förtroendet att köra autopilot under 1-h-pausen. Auto-pilot
slutfördes utan operator-intervention. backup-31 finns som rollback om
något i de 5 commits behöver återställas. RO-review-subagents bekräftade
retroaktivt att alla 3 mergar var merge-ready.
