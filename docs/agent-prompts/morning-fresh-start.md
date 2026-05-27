# Morgonstart för ny agent (2026-05-25 sen natt / morgon)

> **Historisk prompt.** Denna prompt innehåller gamla HEAD-/PR-uppgifter
> från 2026-05-25. Nya agenter ska läsa
> `docs/current-focus.md` och `docs/handoff.md` för aktuellt läge innan de
> återanvänder något från detta dokument.

Denna fil är en färdig copy-paste-prompt för en agent som startar en ren
session efter nattens städ-runda 2026-05-25. Operatören har en typisk
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
- docs/sprintvakt-mcp.md (om du planerar att kalla MCP-tools — agent
  inbox-tools (post_message/list_messages/ack_message) är i PR #77 just
  nu, så de är på origin/jakob-be först när #77 mergats)

Repo-läge att förvänta efter recovery #76 + agent-inbox-PR #77:
- HEAD på main: 6649b51 (closing-round docs-sync efter PR #75; main ligger
  1-2 commits efter jakob-be).
- HEAD på jakob-be: 92df12c (`fix(backoffice): recover regression coverage (#76)`).
  Plus eventuellt agent-inbox-mergecommit ovanpå om PR #77 hunnit mergas
  under natten.
- HEAD på christopher-ui: 74a355b (`feat(viewser): GAP-backend-build-trace-endpoint
  — full Live Build Sync`). Christophers scope-leak-implementation av
  backend-gapet, ej PR:ad än vid skrivande stund. Jakob är reviewer.
- Öppna PRs: möjligen #77 (agent inbox) om Cursor Bugbot inte var grön i
  natt, plus eventuell PR från christopher-ui mot main.
- Sprintvakt MCP-server fungerar via .cursor/mcp.json (`PYTHONPATH`-fix
  + `pip install -e .` engångs).
- `python scripts/sprintvakt_check.py --strict` ska ge "Sprintvakt check: OK".
- Workboarden har ETT queued gap (GAP-backend-build-trace-endpoint, owner=jakob
  i workboarden — implementerat av Christopher på christopher-ui under
  operator-OK scope-leak), inga aktiva gaps.

Två gamla cursor-branches kvarstår på origin men är TEKNISKT REDUNDANTA
efter recovery #76 (deras testfiler ligger nu i jakob-be):
- cursor/jakob-be-contact-route-regression (2 commits)
- cursor/jakob-be-followup-versioning-regression-5fb4 (3 commits)
Operatören kan välja att radera dem (`git push origin --delete <name>`).
Rör dem inte utan instruktion.

Sanity-kommandon innan något annat:
- git status (jakob-be ska vara clean — data/dossier-candidates/ är
  gitignored sedan natten 25/5; om något annat är untracked: fråga
  operatören).
- git log --oneline -8
- gh pr list --state open --json number,title,headRefName,baseRefName
- python scripts/sprintvakt_check.py --strict

Det du får göra utan att fråga:
- Sanity-kommandon ovan.
- Läsa filer i repo:t.
- Anropa MCP-tools i deterministisk läge (get_workboard, list_gaps,
  detect_collisions, suggest_next_gaps, validate_workboard,
  generate_agent_prompt, list_messages, post_merge_sync_instructions).
- Anropa muterande MCP-tools (create_gap, activate_gap, complete_gap,
  reserve_paths, post_message, ack_message) ENDAST med dryRun:true för
  preview.
- Skriva docs-uppdateringar (docs/current-focus.md, docs/handoff.md,
  docs/workboard.json statusuppdateringar) som steward-arbete och pusha
  direkt till jakob-be per branch-discipline.md "Mainline-steward"-sektion.
- Cleanup av mergade tillfälliga branches på origin (cursor/* som har
  PR-status MERGED) efter operator-bekräftelse.

Det du inte får göra utan operatörens OK:
- Auto-spawna writing-subagents via Task-verktyget. Operatörens uttryckliga
  preferens är att Builder-/Scout-arbete körs i operatörens egna nya Cursor-
  chattfönster, inte som dina subagenter. Du skriver self-contained prompts
  som operatören klistrar in. (Readonly Scout-subagent via Task med
  subagent_type=explore är OK för planerings-/läs-arbete.)
- Mutationer mot workboard.json med confirm:true utan operatörens explicita
  godkännande för det specifika gapet.
- Mergea PR #77 eller Christophers kommande backend-trace-PR utan att
  operatören sagt "merge".
- Starta Path B / section-driven renderer utan operator-OK (estimat
  ~22-28h över 3 sessioner enligt docs/path-b-backend-scout.md).
- Embeddings, SNI-runtime, variant-promotion, nya starters, starter-importer,
  Project DNA V2, B125 preview-fallback (utan operator-OK).
- Radera något under data/runs/, data/prompt-inputs/, data/starters/.
- Skriva i .cursor/rules/ direkt (källan ligger i governance/rules/;
  scripts/rules_sync.py speglar).
- Röra apps/viewser/components/**, apps/viewser/app/**/*.tsx,
  apps/viewser/app/**/*.css, apps/viewser/public/** (Christopher-scope).
- Röra cursor/jakob-be-*-regression-brancherna utan instruktion.
- Auto-merge PRs mot main. Operatören beslutar squash-merge själv när redo.

Första svar tillbaka till operatören:

"Repo synkat. jakob-be=<SHA> (recovery #76 inne). main=6649b51 (1-2
commits efter jakob-be — sync-PR kvar att göra). christopher-ui=74a355b
med Christophers scope-leak-implementation av GAP-backend-build-trace-endpoint
(ej PR:ad än, jag är reviewer). PR #77 (agent inbox) <status>. Vad är
nästa drag?"

Avsluta varje svar med säkerhet i %.
```

## Beslut som ska tas före kod

1. **PR #77 (agent inbox)** — om Cursor Bugbot blev grön under natten
   och operatören vill ha inboxen i jakob-be: squash-merge nu. Annars
   vänta och eventuellt poke Bugbot.

2. **Christophers `GAP-backend-build-trace-endpoint`-PR** — så fort
   Christopher öppnar PR från `christopher-ui` mot `main` ska Jakob
   agera reviewer. Granska scope-leaken (medvetet brutet jakob-lane),
   kontrollera att workboard.json `owner` är kvar på `jakob` (precedent
   från PR #68), kör guards/pytest om något känns osäkert, sedan
   rekommendation till operatören om merge.

3. **Sync `jakob-be → main`** — `main` ligger nu 1-2 commits efter
   `jakob-be` (#76 + ev #77). En liten PR från `jakob-be` mot `main`
   lyfter hela batchen in i `main` och låter `christopher-ui` reseta
   sin branch. Gör efter att Christopher-PR:n och #77 är hanterade.

4. **Cursor/* regression-branches** — fråga operatören om de ska raderas
   nu när innehållet är inne via #76. De är tekniskt redundanta.

5. **Path B** (section-driven renderer) är största spåret. 9 commits
   över 3 Builder-sessioner enligt scout-rapporten. Vänta tills
   operatören explicit säger "kör Path B".

6. **Annat smalt spår** — om operatören väljer något annat (B125
   preview-fallback, Backend-Gap 4+5, V1.3 sprintvakt-sync, mini-eval-pass,
   nya dossiers/scaffolds), följ samma orchestrator-pattern: läs först,
   planera, skriv prompts. Vänta tills operatören väljer innan kod startas.

## Christopher coordination

Christopher kör en parallell agent på `christopher-ui`. Vid sessionsstart
2026-05-25 morgon:

- Christopher har just postat commit `74a355b` med
  `GAP-backend-build-trace-endpoint`-implementation under scope-leak.
  Hans agent har inte PR:at det än vid stängningstid; det förväntas tidigt
  på morgonen.
- När Christopher synkar sin `christopher-ui` mot uppdaterat `main` ska
  det ske via Filosofi B-flödet (`git reset --hard origin/main`
  + `--force-with-lease`). Han bör vänta tills `jakob-be → main`-syncen
  är gjord så han inte tappar sin scope-leak-commit. Operatören är
  bryggan här.
- Han har Sprintvakt MCP-server konfigurerad i sin `.cursor/mcp.json` på
  Mac. Agent-inbox-tools (`post_message`/`list_messages`/`ack_message`)
  blir tillgängliga för honom när PR #77 är mergad och han pullat.

Operatören är bryggan: du skriver text åt operatören att vidarebefordra
till Christopher när något behöver koordineras. Du pratar inte direkt
med Christopher-agenten.
