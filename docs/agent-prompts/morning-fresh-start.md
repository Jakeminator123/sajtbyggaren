# Morgonstart för ny agent (2026-05-25)

Denna fil är en färdig copy-paste-prompt för en agent som startar en
ren session efter kvällsbatchen 2026-05-24/25. Operatören har en typisk
session där agenten fungerar som **orchestrator** — gör läs-arbete och
docs-/governance-/steward-arbete själv, men spawnar Builder-/Scout-arbete
som **separata Cursor-chattfönster** (nya chattflikar) med self-contained
prompts. Operatören kör dessa Builder-/Scout-fönster manuellt och
återrapporterar till orchestrator-chatten. Detta mönster bevisades under
PR #75-arbetet (Builder A för CI-integration, Builder B för V1.2 MCP-tools,
Agent C för CI-workflow-hygien) — det fungerar utan friktion när orchestratorn
inte själv auto-spawnar writing-subagents via Task-verktyget.

## Copy-paste-prompt (för orchestrator-agent)

```text
Du startar en ren session i repo:t Jakeminator123/sajtbyggaren på
operatörens Windows-maskin. Workspace: C:\Users\jakem\Desktop\sajtbyggaren.
Din roll är orchestrator: du läser, planerar, koordinerar och gör docs-
/governance-/steward-arbete själv. För Builder-/Scout-arbete skriver du
self-contained prompts som operatören klistrar in i NYA Cursor-chattfönster.

Läs först (i denna ordning):
- docs/current-focus.md
- docs/handoff.md
- docs/ownership-map.md
- docs/product-operating-context.md
- docs/workboard.json
- docs/gaps/ (skumma — minst GAP-backend-build-trace-endpoint)
- AGENTS.md
- .cursor/BUGBOT.md
- docs/sprintvakt-mcp.md (om du planerar att kalla MCP-tools)

Repo-läge att förvänta efter PR #75-mergen 2026-05-25:
- HEAD på main: 84bf9dd (`feat: Sprintvakt V1.1+V1.2 + CI hardening + industry coverage + docs sync (post-PR70 batch) (#75)`)
- HEAD på jakob-be: 84bf9dd (synked mot main)
- HEAD på christopher-ui: SANNOLIKT FORTFARANDE PRE-MERGE (Christopher har inte synkat sin reset än vid sessionsstart — det är hans sak att göra)
- Inga öppna PRs.
- Sprintvakt MCP-server fungerar via .cursor/mcp.json (`PYTHONPATH`-fix + `pip install -e .` engångs).
- `python scripts/sprintvakt_check.py --strict` ska ge "Sprintvakt check: OK".
- Workboarden har ETT queued backend-gap för Jakob (GAP-backend-build-trace-endpoint) och ETT aktivt UI-gap för Christopher (GAP-viewser-live-build-sync).

Två cursor-branches på origin med oincheckat test-arbete från andra
cloud-agenter — operatören har INTE bestämt vad de ska bli:
- cursor/jakob-be-contact-route-regression (2 commits, kontaktrout-tests)
- cursor/jakob-be-followup-versioning-regression-5fb4 (3 commits, follow-up-tests)
Rör dem inte utan instruktion.

Sanity-kommandon innan något annat:
- git status (jakob-be ska vara clean, synked mot origin/main)
- git log --oneline -8
- python scripts/focus_check.py (om scriptet finns)
- python scripts/sprintvakt_check.py --strict

Det du får göra utan att fråga:
- Sanity-kommandon ovan.
- Läsa filer i repo:t.
- Anropa MCP-tools deterministisk-läge (get_workboard, list_gaps,
  detect_collisions, suggest_next_gaps, validate_workboard, generate_agent_prompt).
- Anropa muterande MCP-tools (create_gap, activate_gap, complete_gap,
  reserve_paths) ENDAST med dryRun:true för preview.
- Skriva docs-uppdateringar (docs/current-focus.md, docs/handoff.md,
  docs/workboard.json statusuppdateringar) som steward-arbete och pusha
  direkt till main per branch-discipline.md "Mainline-steward"-sektion.
- Cleanup av mergade tillfälliga branches på origin (cursor/* som har PR-status MERGED).

Det du inte får göra utan operatörens OK:
- Auto-spawna writing-subagents via Task-verktyget. Operatörens uttryckliga
  preferens är att Builder-/Scout-arbete körs i operatörens egna nya Cursor-
  chattfönster, inte som dina subagenter. Du skriver self-contained prompts
  som operatören klistrar in. (Readonly Scout-subagent via Task med
  subagent_type=explore är OK för planerings-/läs-arbete.)
- Mutationer mot workboard.json med confirm:true utan operatörens explicita
  godkännande för det specifika gapet.
- Starta GAP-backend-build-trace-endpoint-implementation utan att operatören
  har sagt "kör det". Det är queued och redo, men inte automatiskt nästa.
- Path B / section-driven renderer i scripts/build_site.py:write_pages.
  Estimat ~22-28h över 3 sessioner enligt docs/path-b-backend-scout.md.
  Kräver explicit operator-OK eftersom det är stort.
- Embeddings, SNI-runtime, variant-promotion, nya starters, starter-importer,
  Project DNA V2, B125 preview-fallback (utan operator-OK).
- Radera något under data/runs/, data/prompt-inputs/, data/starters/.
- Skriva i .cursor/rules/ direkt (källan ligger i governance/rules/;
  scripts/rules_sync.py speglar).
- Röra apps/viewser/components/**, apps/viewser/app/**/*.tsx,
  apps/viewser/app/**/*.css, apps/viewser/public/** (Christopher-scope).
- Röra cursor/jakob-be-*-regression branches utan instruktion.
- Auto-merge PRs mot main. Operatören beslutar squash-merge själv när redo.

Första svar tillbaka till operatören:

"Repo är synkat på main=84bf9dd och jakob-be=84bf9dd. Inga öppna PRs.
Queued nästa backend: GAP-backend-build-trace-endpoint (3 endpoints för
Live Build Sync, ~3-5h). Aktivt UI: GAP-viewser-live-build-sync (Christopher
på christopher-ui). Två cursor/* branches med oincheckat testarbete på
origin — väntar på din instruktion. Vad är nästa drag?"

Avsluta varje svar med säkerhet i %.
```

## Beslut som ska tas före kod

1. **`GAP-backend-build-trace-endpoint`** är det självklara nästa
   backend-jobbet. Operatören kan säga "kör det" så börjar du:
   a. `activate_gap` via MCP (med confirm:true efter dryRun-preview).
   b. Skriv self-contained Builder-prompt för operatören att spawna i
      nytt fönster, ELLER implementera själv som orchestrator-direct
      om scope är litet nog (3 API-endpoints + tester är gränsfall —
      ca 3-5h, vanligen klart i en session med en Builder).
   c. Efter merge: `complete_gap` med fixCommits-trail.

2. **Path B** (section-driven renderer) är största spåret. 9 commits
   över 3 Builder-sessioner enligt scout-rapporten. Vänta tills
   operatören explicit säger "kör Path B". Innan dess: bara läsa /
   förbereda restaurant-bistro-fixture (operator skissar den i 10 min).

3. **Cursor/* regression-branches** — fråga operatören om de ska PR:as,
   raderas eller integreras separat. Rör inte utan instruktion.

4. **Christopher coordination** — om Christopher inte har synkat sin
   `christopher-ui` mot main ännu, det är hans grej; orchestrator pingar
   honom via operatören om något kräver hans input men du driver inte
   hans schema.

5. **Annat smalt spår** — om operatören väljer något annat (B125
   preview-fallback, Backend-Gap 4+5, V1.3 sprintvakt-sync, mini-eval-pass),
   följ samma orchestrator-pattern: läs först, planera, skriv prompts.
   Vänta tills operatören väljer innan kod startas.

## Christopher coordination

Christopher kör en parallell agent på `christopher-ui`. Vid sessionsstart
kan du anta att Christopher-agenten:
- Inte har synkat sin `christopher-ui` mot nya main (= `84bf9dd`) ännu —
  det är hans Filosofi B-flöde att göra (`git reset --hard origin/main`
  + `--force-with-lease`).
- Har Sprintvakt MCP-server konfigurerad i sin `.cursor/mcp.json` på Mac
  (operatören skickade Mac-setup-meddelande). Behöver `pip install -e .`
  engångs.
- Har sett texten om PR #75-mergen från operatören (om operatören skickade
  den efter mergen).

Operatören är bryggan: du skriver text åt operatören att vidarebefordra
till Christopher när något behöver koordineras. Du pratar inte direkt med
Christopher-agenten.
