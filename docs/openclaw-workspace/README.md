# OpenClaw-workspace (Sajtbyggaren)

Detta är Sajtbyggarens egen OpenClaw-spec — inspirerad av externa OpenClaw
(docs.openclaw.ai: en self-hosted gateway + tools + skills + workspace-filer
som soul/tools/skills), men medvetet **smalare och kontrollerad**. Den externa
OpenClaw är referens, inte arkitektur att kopiera rakt av.

Syfte: ge varje agent EN sanningskälla för vad OpenClaw betyder i detta repo, så
ingen bygger egna "OpenClaw-varianter", en extern daemon eller en parallell
motor. OpenClaw är en **dirigent** på den kontrollerade motorn.

## Externa OpenClaw -> Sajtbyggaren (översättning)

| Externa OpenClaw | I Sajtbyggaren |
|---|---|
| gateway / kanaler (WhatsApp/Slack/Telegram) | Viewser-chatten + `/api/prompt` |
| agent runtime | `packages/generation/orchestration/openclaw/` (in-repo, Core V0) |
| tools | sanktionerade actions (se `TOOLS.md`) |
| skills (`SKILL.md`) | `skills/<namn>/SKILL.md` här |
| memory | per-sajt Project Input + run/version (ingen global minnesbank i git) |
| plugins / daemon / multi-channel | bygg INTE nu |

## Docs-MCP för agenter (uppslagsverk — INTE produkt-runtime)

Externa OpenClaw-dokumentationen har en **hostad MCP-server** direkt på
`https://docs.openclaw.ai/mcp` (verifierad med riktigt MCP-handshake:
`serverInfo: openclaw-docs 1.0.0`). Den är konfigurerad i `.cursor/mcp.json`
(gitignorerad — konfig per maskin) som server-id `openclaw-docs`:

- **ingen lokal server**: ersätter det gamla `localhost:6280`-upplägget som
  krävde `openclaw mcp serve` lokalt (CLI:t är inte installerat på
  operatörsmaskinen och behöver inte vara det).
- **Alltid färsk dokumentation** direkt från källan — används för uppslag om
  hur externa OpenClaw fungerar/installeras när agenter jobbar i detta repo.
- **Offline-backup**: den lokala Markdown-spegeln i `openclaw-docs/`
  (~686 filer) i repo-roten kräver ingen server alls.
- Om Cursor visar en röd/gammal anslutning: Cursor Settings → MCP → refresha
  eller toggla `openclaw-docs` av/på så den ansluter mot den nya URL:en.

**Avgränsning (viktig):** detta är ett uppslagsverk för agenter som arbetar i
repot — **inte** en runtime-yta för produktens OpenClaw-dirigent. Produktens
OpenClaw anropar aldrig denna MCP-server (eller någon annan extern tjänst);
den kör enbart de sanktionerade in-repo-actions som `TOOLS.md` och
`action-registry.json` definierar. Samma regel som ovan: extern OpenClaw är
referens, inte arkitektur.

## OpenAI docs-MCP för agenter (samma uppslagsverk-roll)

OpenAI hostar en **officiell publik docs-MCP** på
`https://developers.openai.com/mcp` (verifierad med riktigt MCP-handshake:
`serverInfo: openai-docs-mcp 1.0.0`, ingen auth). Konfigurerad i
`.cursor/mcp.json` (gitignorerad — konfig per maskin) som server-id
`openai-docs`. Använd den för **färsk** info när du jobbar mot OpenAI-API:t i
detta repo — t.ex. modellnamn/priser för `llm-models.v1.json`, Responses
API-parametrar/limits, eller OpenAPI-scheman:

- `search_openai_docs` — sök i `platform.openai.com` + `developers.openai.com`.
- `list_openai_docs` — bläddra/lista sidor när rätt sökfråga är okänd.
- `fetch_openai_doc` — hämta exakt markdown för en sida (scheman, exempel,
  limits) så svar går att citera till källan.
- `list_api_endpoints` — lista alla API-endpoints ur OpenAPI-specen.
- `get_openapi_spec` — OpenAPI-spec för en endpoint, valfritt filtrerad på
  kodexempel per språk.

Samma avgränsning som `openclaw-docs`: detta är ett **uppslagsverk för agenter**,
inte en produkt-runtime-yta. Motorns Model Roles (`llm-models.v1.json`) anropar
OpenAI via egna resolvers — aldrig via denna MCP-server.

## Vad som INTE ska byggas
- Ingen extern OpenClaw-daemon eller gateway-process.
- Inga plugins, ingen multi-channel.
- Ingen fri agent som skriver valfria filer.
- Ingen parallell motor bredvid Project Input / Site Brief / Site Plan /
  Generation Package.
- Ändra aldrig referensmaterialet (sajtmaskin, `C:\Users\jakem\Desktop\openclaw`)
  — det är read-only (AGENTS.md).

## Filer här
- `SOUL.md` — agentens identitet, mål och stoppregler.
- `TOOLS.md` — vilka actions OpenClaw får och inte får köra.
- `action-registry.json` — actions + status (supported / partial / planned).
- `skills/<namn>/SKILL.md` — förmågekort per action.
- Helhetsplan: `../heavy-llm-flow/openclaw-2.0-conductor.md`.

## Status
Detta är spec/referens-lagret (säkert, additivt). Att göra workspacen
runtime-kopplad (kod läser `action-registry.json` / `verify_openclaw.py`
verifierar att skills finns) är en senare, medveten slice — inte en ny motor.
