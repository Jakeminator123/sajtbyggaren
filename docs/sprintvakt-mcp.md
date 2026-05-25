# Sprintvakt MCP V1

Sprintvakt V1 är en lokal koordineringsyta för Jakob och Christopher. Den ska
hjälpa agenter att välja smala gaps, reservera paths och upptäcka krockar innan
arbete startar.

Sprintvakt är inte en autonom projektledare. Den ändrar inte roadmap, produktkod
eller GitHub-state.

## Vad V1 gör

- Läser `docs/workboard.json`.
- Listar gaps från workboarden och `docs/gaps/`.
- Skapar gap-filer med `dryRun` som första steg.
- Reserverar path scopes.
- Upptäcker green/yellow/red collisions.
- Föreslår nästa säkra gaps med deterministiska heuristiker.
- Genererar agentprompter för Scout, Builder eller Steward.
- Returnerar post-merge sync-kommandon för `jakob-be` och `christopher-ui`.

## Vad V1 inte gör

- Inga GitHub writes.
- Inga PR-, merge- eller push-tools.
- Inga shell-kommandon från MCP-tools.
- Inga ändringar i produktkod.
- Inga ändringar i `scripts/build_site.py`, `packages/generation/**`,
  `apps/viewser/**` eller `governance/policies/**`.
- Ingen LLM-planering.

## Säkerhetsmodell

- Muterande tools har `dryRun:true` som default.
- Muterande tools kräver `confirm:true` när `dryRun:false`.
- Alla path-inputs saneras:
  - inga absoluta paths
  - inga `..`
  - inga tomma paths
  - inga paths utanför repo
- Skrivning är begränsad till:
  - `docs/workboard.json`
  - `docs/gaps/**`
  - `docs/agent-prompts/sprintvakt.md`
  - `docs/sprintvakt-log.md`

## CLI

Engångsregistrering av `tooling`-paketet i venv (annars `ModuleNotFoundError`):

```bash
pip install -e .
```

Kör workboard- och collision-check:

```bash
python3 scripts/sprintvakt_check.py
python3 scripts/sprintvakt_check.py --json
python3 scripts/sprintvakt_check.py --strict
```

Exit-koder:

- `0`: inga blockers.
- `1`: blockers, eller warnings med `--strict`.

## Lokal MCP-server

Starta servern lokalt via stdio:

```bash
python3 -m tooling.sprintvakt_mcp.server
```

V1 använder en dependency-free JSON-RPC stdio-server med MCP-kompatibla
metoder (`initialize`, `tools/list`, `tools/call`). Den är avsiktligt smal för
att undvika lockfile- och CI-risk. Nästa steg om teamet vill ha full SDK-wiring
är att lägga till official MCP Python SDK i ett separat dependency-PR och låta
servern återanvända samma `tooling/sprintvakt_mcp/core.py`.

## Tools

### `get_workboard`

Input:

```json
{}
```

Returnerar hela workboarden som JSON.

### `list_gaps`

Input:

```json
{"status": "active"}
```

`status` kan vara `active`, `queued`, `completed` eller `all`.

### `create_gap`

Skapar `docs/gaps/<id>.md` och lägger gapet i workboarden.

Skrivning kräver:

```json
{"dryRun": false, "confirm": true}
```

### `reserve_paths`

Reserverar paths för ett gap och returnerar collisionRisk. Skrivning kräver
`dryRun:false` och `confirm:true`.

### `detect_collisions`

Returnerar:

```json
{
  "collisionRisk": "green",
  "collisions": [],
  "recommendation": "...",
  "safeNextAction": "..."
}
```

### `suggest_next_gaps`

Föreslår upp till tre gaps utan LLM-anrop.

### `generate_agent_prompt`

Returnerar en färdig Cursor/Cloud-agentprompt med roll, branch, läsordning,
scope, doNotTouch, checks, acceptance, PR-regel och stoppregler.

### `validate_workboard`

Validerar workboarden, aktiva gaps, owner, paths, acceptance, checks och
collisions.

### `post_merge_sync_instructions`

Returnerar sync-kommandon för arbetsbranches efter merge till `main`.

## Dagligt flöde

1. Läs workboarden.
2. Kör `detect_collisions` för tänkt gap.
3. Skapa gap med `dryRun:true`.
4. Bekräfta gap med `dryRun:false` och `confirm:true`.
5. Generera agentprompt.
6. Agenten jobbar i rätt lane.
7. Efter merge: kör `post_merge_sync_instructions`.
8. Uppdatera workboarden.

## Varför PR går mot main

`main` är sanningen. Sprintvakt-infra ska byggas en gång och mergas till
`main`. Efter merge synkar Jakob och Christopher sina arbetsbranches från
`origin/main`; det ska inte öppnas separata PR:er mot `jakob-be` eller
`christopher-ui`.

## Post-merge branch sync

Efter att Sprintvakt-PR:n är squash-mergad till `main`:

```bash
git switch main
git fetch origin --prune
git pull --ff-only origin main

git switch jakob-be
git reset --hard origin/main
git push --force-with-lease origin jakob-be

git switch christopher-ui
git reset --hard origin/main
git push --force-with-lease origin christopher-ui
```

`--force-with-lease` är bara OK på solo-ägda arbetsbranches enligt repo-reglerna.
Använd aldrig force eller force-with-lease på `main`.
