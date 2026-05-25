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
- Aktiverar queued gaps och markerar gaps som completed.
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
  - `docs/agent-inbox.jsonl`

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

### `activate_gap`

Flyttar ett gap från `queuedGaps` till `activeGaps`, sätter `status:"active"`,
`activatedAt`, gapets `updatedAt` samt workboardens `updatedAt` och
`updatedBy`.

Input:

```json
{"gapId": "GAP-example", "dryRun": true}
```

Skrivning kräver:

```json
{"gapId": "GAP-example", "dryRun": false, "confirm": true}
```

### `complete_gap`

Flyttar ett gap från `activeGaps` till `completedGaps`. Om gapet fortfarande
ligger i `queuedGaps` kan toolen hoppa över aktivering och slutföra direkt.
Den sätter `status:"completed"`, `completedAt`, gapets `updatedAt`,
`fixCommits`, `notes` samt workboardens `updatedAt` och `updatedBy`.

Input:

```json
{
  "gapId": "GAP-example",
  "fixCommits": ["301ca99"],
  "notes": ["Verified locally."],
  "dryRun": true
}
```

`fixCommits` och `notes` är valfria listor och defaultar till tomma listor.
Skrivning kräver `dryRun:false` och `confirm:true`.

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

## Agent inbox

Sprintvakt-servern har ett enkelt **append-only meddelandeflöde** för
koordination mellan operatör, orchestrator-agenter (`jakob-orchestrator`,
`christopher-orchestrator`) och Builder/Scout/Steward-agenter. Det är inte
en realtidschatt — varje meddelande är en rad i `docs/agent-inbox.jsonl`,
så loggen är diff-vänlig och idempotent.

Filen versioneras i git och är samma för alla brancher som synkar mot
`main`. Det betyder att en cloud-agent på `cursor/foo` kan posta ett
meddelande, pusha sin branch, och en agent på `christopher-ui` kan läsa
det efter `git fetch origin` (eller efter att meddelandet mergats till
`main`).

Två event-typer ligger i loggen:

- `{"type": "message", "id": "msg-0001-a1b2c3", "from": "...", "to": [...], "subject": "...", "body": "...", "createdAt": "..."}`
- `{"type": "ack", "messageId": "msg-0001-a1b2c3", "by": "...", "at": "..."}`

`list_messages` läser hela filen, viker ihop messages med deras acks och
returnerar en flat lista med `acks` påhängd. Skrivning sker bara via
`post_message` och `ack_message` (båda gated av `dryRun`/`confirm`).
Filen skapas automatiskt första gången någon postar.

### `post_message`

Append ett koordinationsmeddelande.

Input:

```json
{
  "from": "jakob-orchestrator",
  "to": ["christopher-orchestrator"],
  "subject": "PR #76 mergad",
  "body": "Recovery-tests + catch-all-fix är inne på jakob-be.",
  "topic": "GAP-backend-build-trace-endpoint",
  "dryRun": true
}
```

`from`/`to`-värden saneras till `[a-z0-9][a-z0-9._-]{0,39}`. `topic` är
valfritt men följer `[A-Za-z0-9][A-Za-z0-9._/-]{0,79}`. `subject` får
max 140 tecken, `body` max 4000 tecken. Skrivning kräver `dryRun:false`
och `confirm:true`.

Message-id är deterministiskt: `msg-<ordinal>-<6-char-hash>`. Hashen
beräknas på `sender|subject|ordinal` utan klocktidsbidrag, så en
`dryRun:true`-preview och den efterföljande `dryRun:false`+`confirm:true`
ger samma id så länge inboxens state inte växt mellan anropen. Det
betyder att agenter tryggt kan cacha id:t från preview-svaret och
referera till det i en ack eller cross-agent-länk. Ordinalet är minst
fyra siffror men växer organiskt utan tak (`msg-9999-...` följs av
`msg-10000-...`), så `ack_message` accepterar `\d{4,}` i id-mönstret.

### `list_messages`

Returnerar messages folded med acks. Inga skrivningar.

Input:

```json
{"to": "christopher-orchestrator", "unreadFor": "christopher-orchestrator", "limit": 20}
```

Alla filter är valfria: `to`, `from`, `topic`, `since` (ISO-8601
timestamp som parsas till ett UTC-medvetet datetime-värde, så `Z` och
`+00:00` är ekvivalenta och offsets jämförs som instants i stället för
strängar), `unreadFor` (filtrera bort meddelanden den deltagaren redan
acked) och `limit` (1-500, default 50). Svar:

```json
{
  "messages": [
    {
      "type": "message",
      "id": "msg-0001-a1b2c3",
      "from": "jakob-orchestrator",
      "to": ["christopher-orchestrator"],
      "subject": "PR #76 mergad",
      "body": "...",
      "createdAt": "2026-05-25T04:05:00Z",
      "acks": [{"by": "christopher-orchestrator", "at": "2026-05-25T04:10:00Z"}]
    }
  ],
  "count": 1,
  "totalMatched": 1,
  "inboxFile": "docs/agent-inbox.jsonl"
}
```

### `ack_message`

Append en read/processed-ack. Bara mottagare som finns i `to`-listan får
acka. Skrivning kräver `dryRun:false` och `confirm:true`. Svaret
inkluderar `alreadyAcked: true/false` så agenter slipper logga
dubbla-acks även om de råkar köra två gånger. När `alreadyAcked` är
`true` skriver toolen ingen ny rad (acken är idempotent för samma
`(messageId, by)`-par) och svaret innehåller `written: false`.

Skrivvägen är dessutom symlink-resistent: `docs/agent-inbox.jsonl` får
inte vara en symlänk och `docs/`-katalogen får inte heller vara en
symlänk, så ingen kan omdirigera append-strömmen utanför
Sprintvakts write-whitelist. När inboxen ligger inuti repo-roten går
skrivvägen dessutom genom `core._assert_allowed_write`, samma
whitelist-check som workboard- och gap-skrivningar använder.

Input:

```json
{"messageId": "msg-0001-a1b2c3", "by": "christopher-orchestrator", "dryRun": false, "confirm": true}
```

## Källa till sanning: workboard vinner över gap-filer

`docs/workboard.json` är den **levande staten**. `docs/gaps/<id>.md` är
en **snapshot tagen vid `create_gap`**. När `activate_gap` eller
`complete_gap` flyttar ett gap mellan listor uppdateras bara workboarden;
gap-filens metadata-rader (`status`, `updatedAt`, etc.) blir då stale.

Det är medvetet:

- Gap-filen fungerar som ett ankare för file-only gaps (när någon skapar
  ett gap manuellt på disk innan workboarden uppdateras) och som en
  läsbar markdown-spec.
- `_find_gap` (anropad av `generate_agent_prompt`) prioriterar
  workboardens version och faller tillbaka till gap-filen bara när
  gapet inte finns i workboarden alls.
- `validate_workboard` kontrollerar bara workboarden; gap-filer
  kontrolleras inte schema-mässigt.

V1.3 kan lägga till tvåvägs-sync (workboard-state skrivs tillbaka till
gap-filens metadata-block efter varje transition) om operatörsfeedback
visar att stale gap-filer förvirrar i praktiken. Tills dess: **antag att
workboarden är sanningen** när status/timestamps inte stämmer mellan
filerna.

## Dagligt flöde

1. Läs workboarden.
2. Kör `detect_collisions` för tänkt gap.
3. Skapa gap med `dryRun:true`.
4. Bekräfta gap med `dryRun:false` och `confirm:true`.
5. Aktivera gapet med `activate_gap`.
6. Generera agentprompt.
7. Agenten jobbar i rätt lane.
8. Markera gapet klart med `complete_gap`.
9. Efter merge: kör `post_merge_sync_instructions`.

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
