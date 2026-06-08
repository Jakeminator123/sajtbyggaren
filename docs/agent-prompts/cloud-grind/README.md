# Cloud-grind-promptar — avslutad backend-gap-batch

Den här mappen innehåller **fristående copy-paste-promptar** för Cursor Cloud Agents (eller motsvarande cloud-agent som har repo-write-access via GitHub). Varje cloud-agent klonar repot från `github.com/Jakeminator123/sajtbyggaren`, jobbar i sin Ubuntu-VM på en **egen feature-branch**, öppnar en **PR mot sin bas-branch** och slutar. **Operatörens lokala maskin är inte i loopen alls** — det enda touchground är GitHub-remoten. Den egna branchen per lane gör att alla tre kan köra **parallellt** utan att krocka på samma branch.

Operatören öppnar ett nytt cloud-agent-fönster, klistrar in en av prompterna som första meddelande, och låter agenten köra till push.

Varje prompt-fil är self-contained: agenten ska inte behöva läsa något annat docs/-material för att kunna jobba. Den deklarerar branch, scope, off-limits, acceptanskriterier, tester och commit-format — alla kommandon är bash/Linux (cloud-VM:n är Ubuntu, ingen venv-aktivering krävs eftersom systempython + `pip install -r requirements.txt` förutsätts redan ha körts som setup-steg).

## Läget nu

Tidigare batch (prompt 1-5) är körd och bortstädad: Gap 6/7 (`c002aec`/`ea6e141`),
B147 (`b3834b3`), docs/workboard-sync (`cb07dbb`), Gap 9 (`365c1d7`), Gap 10
(PR #122 / `3b61c73`).

**Aktuell batch (2026-06-08) — tre FÖRBEREDDA lanes, ej startade.** Operatören
startar dem manuellt en och en (eller parallellt) genom att klistra in
respektive fil som första prompt i en Cursor Cloud Agent. De har hårda,
disjunkta write-set så de kan köra samtidigt utan att krocka — och samtidigt med
det lokala backend-arbetet (`packages/generation/**` render-path).

## Prompt-katalog

| Fil | Lane | Roll | Branch | Write-set | Status |
| --- | --- | --- | --- | --- | --- |
| [`lane-a-docs-honesty-rest.md`](lane-a-docs-honesty-rest.md) | A | Steward | `jakob-be` | docs honesty-cleanup (glossary/architecture-fixar, arkivflytt → `docs/archive/2026-06/`, gaps, frontmatter) + ev. ny `scripts/docs_check.py` | förberedd (utökad med coach-review) |
| [`lane-b-floatingchat-split.md`](lane-b-floatingchat-split.md) | B | Builder (UI) | `christopher` | `floating-chat.tsx` + nya syskonfiler | förberedd (kräver operatörs-OK, refaktor i UI-lane) |
| [`lane-c-backend-refactor-plan.md`](lane-c-backend-refactor-plan.md) | C | Scout/Steward | `jakob-be` | en ny `docs/refactor/`-planfil | förberedd |

## Parallellitet-matris

Alla tre kan köra **helt parallellt** — var och en jobbar på sin egen
feature-branch och öppnar en PR, så ingen push-krock uppstår:

| Lane | Feature-branch | PR-bas | Parallell? |
| --- | --- | --- | --- |
| A | `cursor/lane-a-docs-cleanup` | `jakob-be` | ja |
| B | `frontend/floating-chat-split` | `christopher` | ja |
| C | `cursor/lane-c-refactor-plan` | `jakob-be` | ja |

A och C har båda PR-bas `jakob-be` men disjunkta filer → konfliktfri merge
(merga dem i valfri ordning). Det lokala backend-arbetet
(`packages/generation/**`) är off-limits för alla tre.

## Off-limits för ALLA lanes — OpenClaw-agentens yta

En separat agent äger OpenClaw-docs-spegeln och ev. en MCP-server. Ingen lane
rör: `scripts/fetch_openclaw_docs.py`, hela `openclaw-docs/` (gitignored
spegel av docs.openclaw.ai), eller `.cursor/mcp.json`. OpenClaw-*docs*-fixar
(workspace/conductor fas-nyans) koordineras med den agenten innan edit.

## Operatörens trigger-ordning (rekommenderad)

Öppna tre cloud-agent-fönster och klistra in en lane-prompt i varje — de kan
startas samtidigt. Review/merga PR:erna i valfri ordning när de är gröna.
Varje prompt går att stoppa när som helst — de är atomiska.

## Sync-PR-fönster

`jakob-be` ligger 7 commits före `origin/main` (runda-2-batch ovanpå PR #212).
Sync `jakob-be -> main` är operatörens beslut — verifiera alltid mot
`git log --oneline origin/main..origin/jakob-be` innan ett sync-fönster.

## Övergripande disciplin

Varje prompt slutar med en kort rapport-rad: vilken PR som öppnades, att guards
är gröna (ruff 0, governance 19/19, rules_sync OK, term-coverage --strict OK,
pytest grön) och vad som ändrades. Exakt format står i respektive prompt.

Cloud-agenten **öppnar en PR mot sin bas-branch** (A/C → `jakob-be`, B →
`christopher`) men **mergar den inte** — review + merge är operatörens beslut.
Sync `jakob-be -> main` är ett separat operatörsbeslut. PR-body måste lista alla
ändrade filer (BUGBOT-disciplin: olistade filer = scope-läckage).

Cloud-agenten **rör inte** `apps/viewser/components/**`, `apps/viewser/app/**/*.tsx`, `apps/viewser/public/**` om inte prompten uttryckligen säger det (Christopher-lane), och aldrig OpenClaw-agentens yta (se ovan).

## Cloud-VM-förutsättningar

Innan en agent börjar, ska VM:n ha:

- Repot klonat till en arbets-katalog och `git switch jakob-be` + `git pull origin jakob-be` körda så HEAD matchar `origin/jakob-be` (annars riskerar agenten merge-konflikter mot ändringar pushade strax innan).
- På Ubuntu Noble (default cloud-VM): `sudo apt-get install -y python3-venv` körd innan venv skapas. Det versionerade `python3.12-venv`-paketet kan saknas i sources; meta-paketet drar in det. (Empiriskt observerat i cloud-grind-pass 2026-05-27 — PR #128.)
- `pip install -r requirements.txt` körd (för python-guards + ev. nya deps som promptarna lägger till).
- `cd apps/viewser && npm install` körd om prompten ska köra UI-typecheck/lint.
- `git config user.name` + `git config user.email` satta så commits får rätt author.
- GitHub-push-token (Personal Access Token eller GitHub App-installation) konfigurerad så `git push origin <feature-branch>` lyckas.

Om något av detta saknas: cloud-agenten ska stoppa direkt med felmeddelande till operatören istället för att försöka workaround-fixa.
