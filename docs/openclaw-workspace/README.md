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
