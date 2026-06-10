# ADR 0044 — Koppla in agentkonstitutionen (SOUL) i runtime + Backoffice-identitetsvy

**Status:** Accepted
**Datum:** 2026-06-10 (operatörsbeslut, Jakob)
**Beroenden:** ADR 0002 (Backoffice i Python/Streamlit), ADR 0007 (språkpolicy),
B193 (roll-minnet i chatten). Referens:
[`docs/openclaw-workspace/SOUL.md`](../../docs/openclaw-workspace/SOUL.md),
[`docs/openclaw-workspace/TOOLS.md`](../../docs/openclaw-workspace/TOOLS.md),
[`docs/openclaw-workspace/README.md`](../../docs/openclaw-workspace/README.md),
[`apps/viewser/app/api/prompt/route.ts`](../../apps/viewser/app/api/prompt/route.ts),
vy-register-låset (#258).

## Kontext

`docs/openclaw-workspace/SOUL.md` finns i repot som dirigentens konstitution
(mål, får/får-inte, ärlighet, kontextnivåer) — men den är ren spec: ingen kod
läser den. Chatt-personan i `generateConversationAnswer`
(`apps/viewser/app/api/prompt/route.ts`) byggde sin systemprompt från hårdkodade
rader, så konstitutionen och den körande personan kunde driva isär.

Mönstret kommer från äkta OpenClaw, där en workspace har filer som soul/tools/
skills. Vi speglar redan SOUL + TOOLS + skills i `docs/openclaw-workspace/`. Den
här ADR:n gör workspacen *runtime-kopplad* för **chatt-personan** — som en
reguljär OpenClaw-workspace, men för vår in-process-dirigent. Den gör den INTE
till en ny motor: byggbeteendet styrs fortsatt av kod och governance.

## Beslut

Två additiva delar.

### Runtime-laddning av SOUL

`generateConversationAnswer` bygger sin systemprompt från
`docs/openclaw-workspace/SOUL.md`:

- En ny modul `apps/viewser/lib/soul.ts` (`loadSoulBaseLines`) läser SOUL.md
  server-side, **cacheas per process** (läsningen sker högst en gång), och
  **trunkeras** till en säker längd (`SOUL_MAX_CHARS`) så den sammansatta
  systemprompten aldrig närmar sig `lib/openai.ts`:s 8000-teckenstak per
  meddelande.
- **Defensiv fallback:** vid saknad/oläsbar fil returnerar laddaren null och
  `generateConversationAnswer` faller tillbaka på de hårdkodade persona-raderna
  (`CONVERSATION_SOUL_FALLBACK_LINES`) — exakt dagens beteende.
- De **dynamiska** raderna (B193-historiken, site_opinion-kontexten och
  ärlighetslinjen "inget ändrat i DENNA tur") behålls och läggs **EFTER**
  SOUL-basen i `systemLines`, så de alltid vinner.

### Backoffice-identitetsvy

En ny vy `Identitet (SOUL)` (ny sektion Identitet, modul
`backoffice/views/identity.py`) visar och låter operatören redigera SOUL.md med
förhandsvisning och spara till arbetsträdet, samt läsa TOOLS.md read-only. Vyn
registreras i vy-registret (`governance/policies/backoffice-views.v1.json` +
`backoffice/view_registry.py`) enligt det befintliga, dubbelriktat låsta
mönstret (#258).

## Säkerhetsräcken (hårda)

- **Ordningen är ett räcke:** SOUL-basen får aldrig övertrumfa de kodade
  ärlighetsraderna. `systemLines = [...soulBaseLines, ...dynamicLines]` låses med
  källås-test, och vid överlängd släpps SOUL-basen — aldrig de dynamiska
  raderna — så anropet aldrig kastar och ärligheten alltid finns kvar.
- **Path-lås i editorn:** vyn skriver ENDAST `docs/openclaw-workspace/SOUL.md`
  (konstant write-mål, ingen fri filskrivning, ingen path-input), har en
  max-längd och tom-text-spärr, och visar en varning om att ändringen gäller
  alla sajters chatt-persona. TOOLS.md är read-only.
- **Ingen git-commit från UI:t:** operatören committar som vanligt.
- **Inga nya canonical-termer:** PascalCase-träffar allowlistas vid behov; inga
  nya ord registreras i naming-dictionary utan denna ADR.

## Icke-scope

- `USER.md`/`IDENTITY.md` per kund (framtida), heartbeat/sessions, extern
  gateway.
- Att låta SOUL styra BYGG-beteende. SOUL styr bara chatt-personan + tonen;
  apply-kedjans regler bor i kod/governance, inte i prosa.

## Konsekvenser

Positiva:

- En sanningskälla för chatt-personan: konstitutionen och den körande personan
  kan inte längre driva isär.
- Operatören kan justera ton/persona utan att röra kod (men ärligheten är
  kodlåst).
- Workspace-mönstret blir konkret utan att bli en ny motor.

Negativa / risk:

- En redigerad SOUL gäller chatt-personan för alla sajter; varningen i vyn gör
  det tydligt.
- Källås, inte live-bevis: testerna bevisar källans form (ordning, path-lås,
  fallback, trunkering). Live-svar med riktig nyckel verifieras av operatören.

## Referenser

- [ADR 0002 — Backoffice i Python/Streamlit](0002-backoffice-in-python-streamlit.md)
- [`docs/backoffice/overview.md`](../../docs/backoffice/overview.md)
- [`docs/openclaw-workspace/README.md`](../../docs/openclaw-workspace/README.md)
