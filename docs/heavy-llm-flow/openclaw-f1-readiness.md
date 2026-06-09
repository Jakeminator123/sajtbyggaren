---
status: active-plan
owner: backend
truth_level: summary
last_verified_commit: 76b5ae4
---

# OpenClaw F1-readiness — install-grundning + registry-runtime-plan

> Status: plan/scout-only (2026-06-09). Detta dokument **minskar osäkerhet**
> inför nästa builder-lane (F1). Det är **inte** F1-implementationen och
> innehåller **ingen runtime-kod**. Allt nedan är antingen "finns idag"
> (verifierat mot git/koden) eller "föreslås (gated)". De två hålls isär med
> flit.
>
> Läs först: `docs/current-focus.md` (köplan), toppblocket i `docs/handoff.md`,
> `docs/openclaw-workspace/` (dirigent-konstitutionen) och
> [`openclaw-2.0-conductor.md`](openclaw-2.0-conductor.md) (fasplanen). Denna
> fil är readiness-spåret som conductor-planen pekar på under
> "OpenClaw F1-readiness (separat lokal lane)".

Placering: filen ligger i `docs/heavy-llm-flow/` bredvid
[`openclaw-2.0-conductor.md`](openclaw-2.0-conductor.md), eftersom F1 är nästa
steg i exakt den fasplanen (Fas 1 = roll-registry som explicit modul). Ingen
ny mappkonvention införs.

## 0. Stopp-före-kod-grind (sammanfattning)

Implementation av F1-runtime börjar FÖRST efter operatörens uttryckliga
go-ahead OCH när dessa tre prerequisites är klara:

| # | Prerequisite | Status idag (2026-06-09) |
|---|---|---|
| a | Synlig render-path för section_add (idag mount-only) | öppen — section_add är mount-only (`applied=true`, `appliedVisibleEffect=false`); synlig render återstår |
| b | Lane A docs/governance-cleanup landad på `jakob-be` | **klar** — mergad via `76b5ae4` (`merge(lane-a): docs honesty-cleanup + frontmatter + archive`) |
| c | Megafil-refaktorplanen (#215) beslutad | **klar som plan** — `2dadf09` ([`docs/refactor/megafiles-plan.md`](../refactor/megafiles-plan.md)); själva refaktor-koden väntar |

Tills allt tre + go-ahead är på plats: planera, vänta, stoppa. Skriv ingen
runtime-kod ens om vägen är tydlig. Denna fil flyttar inte gränsen — den
beskriver bara vad som ska göras när grinden öppnas.

## 1. Riktningen (icke förhandlingsbar)

OpenClaw i detta repo är en **dirigent/bridge ovanpå den befintliga,
kontrollerade motorn** — inte en parallell motor, inte fri filpatch, inte en
extern daemon i nuvarande fas. F1 ÅTERANVÄNDER in-repo-källan; den forkar eller
duplicerar den aldrig. Princip (från conductor-planen): *frihet i förståelsen
(LLM-roller), kontroll i appliceringen (deterministisk apply + guards)*.

In-repo-källan (enda ytan F1 rör):

- `packages/generation/orchestration/openclaw/` (`core.py`, `models.py`, `__init__.py`) — beslutskärnan (Core V0)
- `scripts/run_openclaw_followup.py` — CLI-seam som apps/viewser shellar till
- `scripts/verify_openclaw.py` — anslutnings-självkoll (PASS/FAIL-lampa)
- `apps/viewser/lib/openclaw-runner.ts` + `apps/viewser/app/api/prompt/route.ts` — UI-wiring
- `docs/openclaw-workspace/action-registry.json` + `skills/<namn>/SKILL.md` — spec/förmågekort

---

## 3.1 OpenClaw-installation för Sajtbyggaren

### In-process först — "inget att installera, ingen Docker"

Sajtbyggarens OpenClaw är **inte** en self-hosted gateway. Det är ren in-repo
Python i `packages/generation/orchestration/openclaw/` som körs i repots `.venv`.
apps/viewser (`/api/prompt`) shellar ut till `scripts/run_openclaw_followup.py`,
som importerar paketet via en deterministisk seam (repo-boundaries: viewser
importerar aldrig `packages/` direkt; skriptet i `scripts/` äger importen).

Detta är verifierat, inte planerat. `scripts/verify_openclaw.py` skriver i sin
docstring: "There is nothing to install: OpenClaw Core V0 is plain Python that
ships inside this repo … and runs in the local `.venv` … no separate service,
no Docker." Självkollen (`python scripts/verify_openclaw.py`) lyser grön på 6/6
idag: core-import, CLI-seam (`--apply`), UI-wiring, samt tre deterministiska
beslut (edit → `patch_plan_request`/`visual_style`; fråga → `answer_only`;
section → `patch_plan_request`/`section_add`).

Översättning extern OpenClaw → Sajtbyggaren (från `docs/openclaw-workspace/README.md`):

| Externa OpenClaw | I Sajtbyggaren (idag) |
|---|---|
| gateway / kanaler | Viewser-chatten + `/api/prompt` |
| agent runtime | `packages/generation/orchestration/openclaw/` (Core V0, in-repo) |
| tools | sanktionerade actions (`TOOLS.md`) |
| skills (`SKILL.md`) | `skills/<namn>/SKILL.md` |
| memory | per-sajt Project Input + run/version (ingen global minnesbank i git) |
| plugins / daemon / multi-channel | byggs INTE nu |

Slutsats: för F1 finns **ingen installationsfråga**. F1 lägger till en
registry-modul i samma `.venv`-paket. Ingen ny process, ingen Docker, ingen
gateway.

### Vad ett eventuellt externt Docker/Gateway-läge (Fas 2) skulle KRÄVA

Detta avsnitt **beskriver**, det **bygger inte**. Det är inte ett beslut att gå
till en gateway, och det scaffoldar ingenting. Alla provider-/hosting-val är
**öppna beslut** (se gate-noten sist i avsnittet).

Grundning A — den riktiga produktens docs (lokal spegel `openclaw-docs/`,
av-indexerad men läsbar; ändras aldrig av denna lane):

- Install (källa: `openclaw-docs/install.md`, härrör från
  `https://docs.openclaw.ai/install.md`): Node 24 (eller 22.19+); installer-
  script, npm/pnpm/bun, eller container (Docker/Podman). Cloud-mål som listas är
  bl.a. VPS, Render, Railway, Fly, GCP, Azure, Kubernetes, Northflank — alla
  som **alternativ**, inget utpekat. Verifiering: `openclaw --version`,
  `openclaw doctor`, `openclaw gateway status`.
- Gateway runbook (källa: `openclaw-docs/gateway.md`): en **alltid-på-process**
  för routing/control-plane/kanaler; en multiplexad port (default `18789`);
  WebSocket-control/RPC + OpenAI-kompatibla HTTP-endpoints
  (`/v1/models`, `/v1/chat/completions`, `/v1/responses`, m.fl.); default bind
  `loopback`; **auth krävs som standard** (delad hemlighet via
  `gateway.auth.token` / `OPENCLAW_GATEWAY_TOKEN`, eller `trusted-proxy` bakom
  reverse proxy); supervision via launchd/systemd/schtasks; fjärråtkomst helst
  via Tailscale/VPN, annars SSH-tunnel (auth kringgås aldrig av tunneln);
  hälsa via `openclaw gateway status` / `openclaw health`.

Grundning B — sajtmaskins `infra/openclaw/` som deploy-blueprint (read-only
referens enligt AGENTS.md; citeras som inspiration, kopieras/ändras ALDRIG):
en Docker-image (`node:22-slim`, `npm install -g openclaw …`,
`NODE_LLAMA_CPP_SKIP_DOWNLOAD=true`, exponerad port 18789, healthcheck mot
`/health`), en entrypoint som skriver `openclaw.json` vid uppstart
(`gateway.mode=local`, `bind`, `auth.mode=token`, controlUi allowedOrigins) och
faller tillbaka till `loopback` om token saknas, samt `render.yaml`/`railway.toml`
med persistent disk monterad på agentens state-katalog och hemligheter som
icke-synkade env-vars.

Prerequisites för ett externt läge (krav, inte val):

| Prerequisite | Vad det innebär | Belägg (referens) |
|---|---|---|
| Persistens | Beständig state-/config-katalog (annars tappas sessioner/konfig vid omstart) | sajtmaskin: monterad disk på agentens state-dir; gateway: `OPENCLAW_STATE_DIR` / `OPENCLAW_CONFIG_PATH` |
| HTTPS / exponering | Icke-loopback-bind kräver medveten exponering + tillåtna origins | gateway.md: `bind`, controlUi allowedOrigins; reverse proxy / Tailscale |
| Secrets | Token + modellnyckel injiceras som hemligheter, aldrig i image | `OPENCLAW_GATEWAY_TOKEN`, `OPENAI_API_KEY` (icke-synkade env-vars) |
| Auth | Påslagen som standard; icke-loopback utan auth vägras | gateway.md: "refusing to bind gateway … without auth" |
| Healthcheck | Liveness/readiness-prob för supervisor/plattform | `/health`; `openclaw gateway status` / `openclaw health` |
| Port / lock | Fast port + konflikthantering (en lyssnare per port) | default port 18789; portkonflikt-signatur "another gateway instance is already listening" |

> Provider-/hosting-val (Docker vs VPS vs Render vs Railway vs Fly vs gateway-
> exponering) är **ÖPPNA BESLUT**. Denna fil väljer ingen framtida väg; den
> redovisar bara krav, tradeoffs och prerequisites så operatören kan besluta
> senare. Beskrivs, byggs inte.

Not om in-repo-scaffold: `openclaw-mvp/` (FastAPI-spike som conductor-planen
pekar ut som möjlig bas för en framtida extern tjänst) och `openclaw-docs/`
ligger **gitignorerade** och är alltså inte del av `jakob-be`-trädet. De är
lokala referenser, inte auktoritativ repo-state — viktigt att inte beskriva
dem som "byggt".

---

## 3.2 F1-designen: gör action-registret körbart (SOM PLAN)

Mål: gör `docs/openclaw-workspace/action-registry.json` **körbar** — kod läser
registret och väljer roll — i stället för att vara enbart dokumentation. Detta
är Fas 1 i conductor-planen ("roll-registry som explicit modul + dirigent väljer
roll"). Inget byggs här; nedan är ritningen.

### Planerad modul: `registry.py`

En ny modul `packages/generation/orchestration/openclaw/registry.py` som:

- läser `docs/openclaw-workspace/action-registry.json` (fälten `id`, `skill`,
  `routerEditKind`, `status`, `mountOnly`),
- exponerar en mappning från routerns `editKind` → roll
  (`copy_change`→`copy_editor`, `visual_style`→`stylist`,
  `section_add`→`section_builder`, `site_review`→`site_review`/reviewer),
- är ren och deterministisk (ren JSON-läsning, ingen LLM, inget nätverk),
  samma anda som `core.py`.

### Hur `run_openclaw_followup.py` skulle läsa registret

`run_openclaw_followup.py` har redan två lägen: read-only beslut, och
`--apply`-bryggan som för ett `edit_instruction` kör den BEFINTLIGA apply-kedjan
`run_followup_chain` (router → context → patch → apply → targeted render). F1
lägger till ETT steg: när Core V0 returnerar `patch_plan_request` slår bryggan
upp rollen i `registry.py` (via routerns `editKind`) innan den ropar på
`run_followup_chain`. Ingen ny motor, ingen fri filpatch — rollen *förstår och
föreslår*, kedjan *validerar och applicerar*.

Kontraktet behålls oförändrat:

- `OpenClawDecision` muteras aldrig (dess V0-validator tvingar
  `appliedVisibleEffect=false`).
- `applied` / `appliedVisibleEffect` / `previewShouldRefresh` kommer ALLTID från
  `run_followup_chain` (det separata `bridge`-objektet), aldrig påhittat.
- Okänd/ostödd action → ärlig no-op med anledning (aldrig fejkad "klart").
- En monterad section_add förblir mount-only (`appliedVisibleEffect=false`) tills
  den separata render-path-uppgiften landar; F1 gör den inte synlig.

### Fil-touch-points (planerade, EJ rörda i denna lane)

| Fil | Planerad ändring | Rörd nu? |
|---|---|---|
| `packages/generation/orchestration/openclaw/registry.py` | ny modul (läser registret, mappar editKind→roll) | nej (ny) |
| `scripts/run_openclaw_followup.py` | läser registret för att välja roll före `run_followup_chain` | nej |
| `scripts/verify_openclaw.py` | ev. ny check: registret laddar + varje skill-path finns + status-värden giltiga | nej |
| `packages/generation/orchestration/openclaw/core.py` / `models.py` | oförändrat (kontraktet rörs inte) | nej |
| `docs/openclaw-workspace/action-registry.json` | oförändrat (läses, inte ändras) | nej |

### Tester att lägga till (beskrivs, skapas INTE här)

- registry-laddning: filen parsas, schemat (id/skill/routerEditKind/status) är giltigt.
- editKind→roll: varje stödd `editKind` mappar till förväntad roll; okänd editKind → ärlig no-op-väg.
- ogiltig/saknad skill-path → tydligt fel (inte tyst pass).
- status-enum-validering: bara `supported` | `partial` | `planned` accepteras.
- `verify_openclaw.py` förblir grön (oförändrad PASS-uppsättning + ev. en ny registry-check).

### Status-realism (överdriv inte mognaden)

Från `action-registry.json` + skills idag:

| Action | routerEditKind | Status | Not |
|---|---|---|---|
| restyle | `visual_style` | supported | färg/typsnitt/tema via theme_directives + stylist/color_lexicon |
| copy_change | `copy_change` | supported | namn/tagline/om/tjänster; LLM-förstådd, deterministisk validator |
| section_add | `section_add` | supported (mount-only) | monterar capability+dossier; renderas **ännu inte** synligt (`appliedVisibleEffect=false`) — synlig render återstår |
| layout_change | `layout_change` | planned | kräver apply-kapabilitet, inte fri CSS |
| site_review | `site_review` | partial | read-only svar/kritik; bygger aldrig |

### Ärlighet om #215 (megafil-refaktorn)

Megafil-refaktorn är **mergad som en docs-PLAN** (`2dadf09`,
[`docs/refactor/megafiles-plan.md`](../refactor/megafiles-plan.md)) — **inte**
som en kod-PR. Själva refaktorn (att flytta kod ur `renderers.py` /
`build_site.py` / `prompt_to_project_input.py`) är **inte gjord**. Formulering:
"beslutad/mergad refaktor-PLAN; kod väntar".

---

## 3.3 Risker & öppna frågor

### Lane A fas-nyans (nu landad)

Lane A (docs honesty-cleanup) är **mergad till `jakob-be`** via `76b5ae4`.
Prerequisite (b) i stopp-grinden är därmed uppfylld. Lane A:s arbete låg helt i
docs (frontmatter, arkivflytt, architecture/glossary-honesty) plus en ny opt-in
`scripts/docs_check.py` (ej inkopplad i CI). Den rörde **ingen** av F1-källfilerna
(openclaw-paketet, `run_openclaw_followup.py`, `verify_openclaw.py`,
`build_site.py`, `prompt_to_project_input.py`), så denna plans grundning står
kvar. Konsekvens för ordval: tidigare utkast skulle markerat Lane A som "öppen
gate" — det är nu en **stängd** gate. F1-honesty-språket (mount-only, ärlig
no-op, "syns inte än") ska följa Lane A:s checker-regler (se `docs_check.py`):
en rad som påstår synlig section_add måste bära en negation/mål-/mount-only-
markör.

### Megafil-refaktorn (#215) flyttar entrypoints F1 läser

`run_followup_chain` ligger **idag i `scripts/build_site.py`** (i grupperingen
"Version/följdprompt", ungefärligt radspann 4440–5172 enligt megafilplanen) —
mitt i refaktorns write-set. F1 importerar `run_followup_chain` därifrån. Om
refaktorn körs (när produktbeviset väl finns) kan apply-kedjans entrypoints
flytta. Detta är en **ordningsberoende risk**: megafil-refaktor-beslutet bör
vara klart (det är det, som plan) och helst koordineras så att F1-koden och en
ev. flytt av `run_followup_chain` inte krockar. Megafilplanens egen ordningsregel
säger dock att refaktorn inte startar förrän kärnloopen är produktbevisad — så i
praktiken landar F1-runtime troligen **före** själva refaktorkoden, och F1 bör
importera `run_followup_chain` via dess symbolnamn (inte via radnummer).

### Glue 1 + mount-only som gating för en meningsfull F1-demo

- Glue 1 (osäker på en färsk sajt): en följdprompt måste hitta Project Input på
  disk (`data/prompt-inputs/<siteId>.project-input.json`). Utan det kan
  section_add inte ens köra på en nybyggd sajt — dvs F1:s roll-val har inget att
  applicera på. Gating för en trovärdig demo.
- Mount-only: även när rollen väljs och kedjan kör, är section_add mount-only
  idag — resultatet skrivs som ny version men syns **inte** i preview ännu. En
  F1-demo som "lägg till en FAQ-sektion" blir därför ärligt "registrerad men syns
  inte än", inte "klart". Synlig render återstår (prerequisite a).

### Explicita öppna frågor till operatören

1. F1-scope: ska F1 enbart göra registret körbart för de roller som redan finns
   (copy_editor/stylist/section_builder + read-only site_review), och lämna
   layout_change/route_add till senare? (Förslag: ja.)
2. Ska `verify_openclaw.py` få en ny registry-check redan i F1, eller hålls den
   oförändrad tills registret bevisats? (Påverkar baslinjen för guarden.)
3. Demo-definition: räcker mount-only-demo (ärlig "registrerad, syns inte än")
   som F1-acceptans, eller kräver F1 att prerequisite (a) synlig render landat
   först? (Bestämmer om F1 och render-path-spåret måste sekvenseras.)
4. Provider-/hosting-väg för en eventuell Fas 2: ska den utredas separat, eller
   förblir den parkerad tills F1 + produktbevis är klara? (Alla provider-val är
   öppna; ingen väg vald här.)
5. Ordning F1 vs megafil-refaktor: ska F1-koden landa före refaktorn (som
   megafilplanens ordningsregel antyder), så att F1 importerar `run_followup_chain`
   via symbolnamn och refaktorn anpassar sig efter?

---

## Sammanfattning

- Installation för F1: **ingen** — in-process Python i `.venv`, ingen Docker,
  ingen gateway. Extern Fas 2 är **beskriven** (krav + prerequisites, grundat i
  `openclaw-docs/` och sajtmaskin-blueprinten) men **inte byggd**, och alla
  provider-val är öppna.
- F1-design: en ren `registry.py` som gör `action-registry.json` körbar +
  ett rollval i `run_openclaw_followup.py` före den befintliga `run_followup_chain`.
  Kontraktet (OpenClawDecision oförändrad; applied-signaler från kedjan; ärlig
  no-op; mount-only förblir osynlig) behålls. Fil-touch-points och tester är
  listade, **inte implementerade**.
- Risker: Lane A är nu landad (gate b klar); #215 är en beslutad plan men koden
  väntar och kan flytta `run_followup_chain`; Glue 1 + mount-only gatar en
  meningsfull demo.
- Grind: implementation väntar på (a) synlig render av section_add (mount-only
  idag, återstår), (b) Lane A (klar), (c) megafil-refaktor-beslut (klart som
  plan) + operatörens go-ahead.
