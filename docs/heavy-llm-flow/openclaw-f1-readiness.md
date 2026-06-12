---
status: active-plan
owner: backend
truth_level: summary
last_verified_commit: d234941
---

# OpenClaw F1-readiness — install-grundning + registry-runtime-plan

> Status: historisk readiness med uppdaterad nulägesnot (verifierad mot
> `d234941`, 2026-06-12). Dokumentet skrevs 2026-06-09 inför F1; F1 slice
> 1–3 är nu levererade i annan form än planen antog: rollkontrakten bor i
> `packages/generation/orchestration/openclaw/roles.py`, registry-konsistensen
> låses av `tests/test_openclaw_registry_consistency.py`, och
> `scripts/build_site.py:run_followup_chain` dispatchar `section_add` via
> `skill_for_edit_kind`.
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

## 0. Historisk stopp-före-kod-grind (sammanfattning)

Det här var grinden innan F1-runtime. Mot dagens kod är den passerad för
rollkontrakt + dispatch, men synlig render är bara delvis breddad:

| # | Prerequisite | Status 2026-06-12 |
|---|---|---|
| a | Synlig render-path för section_add | delvis stängd — faq/team renderas synligt på `local-service-business`; contact-form renderas synligt på `ecommerce-lite` när `resend-contact-form` är monterad. Övriga section_add-typer är fortsatt mount-only eller inline-gated enligt `docs/openclaw-workspace/action-registry.json`. |
| b | Lane A docs/governance-cleanup landad på `jakob-be` | **klar** — mergad via `76b5ae4` (`merge(lane-a): docs honesty-cleanup + frontmatter + archive`) |
| c | Megafil-refaktorplanen (#215) beslutad | **klar som plan** — `2dadf09` ([`docs/refactor/megafiles-plan.md`](../refactor/megafiles-plan.md)); själva refaktor-koden väntar |

Den ursprungliga stoppregeln ska därför inte läsas som dagens byggkö. Den visar
vilka risker som fanns innan F1 landade.

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

Slutsats: för F1 fanns och finns **ingen installationsfråga**. Den levererade
lösningen lade inte till någon ny process, Docker eller gateway.

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

## 3.2 F1-designen: gör action-registret körbart (historisk plan, levererad form)

Målet var att göra `docs/openclaw-workspace/action-registry.json` körbar — kod
ska välja roll i stället för att bara dokumentera roller. Den levererade formen
blev smalare och mer driftlåst än skissen: `ROLE_CONTRACTS` i `roles.py` är
kodens frysta rollkontrakt, och testet `test_openclaw_registry_consistency.py`
korsvaliderar skill/status/mountOnly/visibleTypes mot action-registryt.

### Levererad modulform: `roles.py`

I stället för en separat `registry.py` finns nu
`packages/generation/orchestration/openclaw/roles.py`, som:

- exponerar `ROLE_CONTRACTS` med `router`, `section_builder`, `stylist` och
  `copy`,
- exponerar mappningen från routerns `editKind` → roll
  (`copy_change`→`copy`, `visual_style`→`stylist`,
  `section_add`→`section_builder`),
- exponerar `skill_for_edit_kind`, som läser `RoleContract.skill` och därmed
  gör den klassade rollen styrande för dispatch,
- är ren och deterministisk (ingen LLM, inget nätverk), samma anda som `core.py`.

### Hur kedjan läser rollen

`run_openclaw_followup.py` har redan två lägen: read-only beslut, och
`--apply`-bryggan som för ett `edit_instruction` kör den BEFINTLIGA apply-kedjan
`run_followup_chain` (router → context → patch → apply → targeted render).
Den rolldrivna dispatchen sker inne i `run_followup_chain`: runt raderna
4017–4036 jämför kedjan `skill_for_edit_kind(editKind)` med
`SECTION_ADD_SKILL`, i stället för att bara hårdkoda rått `editKind`.
Ingen ny motor, ingen fri filpatch — rollen väljer skill, kedjan validerar
och applicerar.

Kontraktet behålls oförändrat:

- `OpenClawDecision` muteras aldrig (dess V0-validator tvingar
  `appliedVisibleEffect=false`).
- `applied` / `appliedVisibleEffect` / `previewShouldRefresh` kommer ALLTID från
  `run_followup_chain` (det separata `bridge`-objektet), aldrig påhittat.
- Okänd/ostödd action → ärlig no-op med anledning (aldrig fejkad "klart").
- En monterad section_add kan vara synlig när en smal render-path finns:
  faq/team på `local-service-business`, contact-form på `ecommerce-lite` med
  `resend-contact-form`. I övriga fall stannar mount-only-ärligheten.

### Fil-touch-points (planerade då, leveransstatus nu)

| Fil | Planerad ändring | Leveransstatus |
|---|---|---|
| `packages/generation/orchestration/openclaw/registry.py` | ny modul (läser registret, mappar editKind→roll) | byggdes inte separat; motsvarande kontrakt finns i `roles.py` |
| `scripts/run_openclaw_followup.py` | läser registret för att välja roll före `run_followup_chain` | bridge-seam bär conversation/rollmetadata; själva section-dispatchen sker i `run_followup_chain` |
| `scripts/verify_openclaw.py` | ev. ny check: registret laddar + varje skill-path finns + status-värden giltiga | oförändrad huvudlampa; registry-drift låses i pytest |
| `packages/generation/orchestration/openclaw/core.py` / `models.py` | oförändrat (kontraktet rörs inte) | Core-kontraktet behölls |
| `docs/openclaw-workspace/action-registry.json` | oförändrat (läses, inte ändras) | blev driftlåst mot `ROLE_CONTRACTS` via test |

### Tester (levererade)

- `tests/test_openclaw_roles.py` låser `ROLE_CONTRACTS`, `role_for_edit_kind`,
  `skill_for_edit_kind` och answer-only-signalen.
- `tests/test_openclaw_registry_consistency.py` jämför action-registryt med
  rollkontrakten: skill, status, mountOnly och visibleTypes får inte drifta.
- `tests/test_run_openclaw_followup.py` låser bridge-seam, conversation gate och
  att edits fortsätter till kedjan.

### Status-realism (överdriv inte mognaden)

Från `action-registry.json` + skills idag:

| Action | routerEditKind | Status | Not |
|---|---|---|---|
| restyle | `visual_style` | supported | färg/typsnitt/tema via theme_directives + stylist/color_lexicon |
| copy_change | `copy_change` | supported | namn/tagline/om/tjänster; LLM-förstådd, deterministisk validator |
| section_add | `section_add` | supported (delvis synlig) | monterar capability+dossier; faq/team renderas synligt på `local-service-business`, contact-form på `ecommerce-lite` när `resend-contact-form` är monterad. Övriga typer är fortsatt mount-only eller inline-gated enligt action-registryt. |
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
`build_site.py`, `prompt_to_project_input.py`), så planens grundning stod kvar.
Konsekvens för ordval: tidigare utkast skulle markerat Lane A som "öppen gate"
— det är nu en **stängd** gate.

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

### Glue 1 + synlig render-bredd som gating för nästa demo

- Glue 1 är inte längre den generella blockeraren för F1: `/api/prompt` kör
  OpenClaw apply-bryggan och hostad follow-up hydreras från blob/KV.
- Synlig render är fortfarande selektiv. En demo med "lägg till FAQ" eller
  "lägg till team" kan vara synlig på `local-service-business` när content-gaten
  är uppfylld; contact-form kan vara synlig på `ecommerce-lite` med
  `resend-contact-form`. Andra typer ska fortfarande rapporteras ärligt som
  mount-only eller no-op.

### Explicita öppna frågor till operatören

1. F1-scope för rollerna är i praktiken valt: router, section_builder, stylist
   och copy är låsta i `ROLE_CONTRACTS`; layout/route ligger senare.
2. Registry-checken landade som pytest-konsistensguard snarare än som ny
   `verify_openclaw.py`-lampa.
3. Demo-definitionen bör nu skilja synliga typer från mount-only-typer i stället
   för att kalla hela `section_add` osynlig.
4. Provider-/hosting-väg för en eventuell Fas 2: ska den utredas separat, eller
   förblir den parkerad tills F1 + produktbevis är klara? (Alla provider-val är
   öppna; ingen väg vald här.)
5. Ordning F1 vs megafil-refaktor: F1 landade före refaktorkoden och läser
   `run_followup_chain` via symbolnamn.

---

## Sammanfattning

- Installation för F1: **ingen** — in-process Python i `.venv`, ingen Docker,
  ingen gateway. Extern Fas 2 är fortfarande bara beskriven; provider-val är
  öppna.
- F1-designen är levererad som `ROLE_CONTRACTS` + rolldriven skill-dispatch +
  registry-konsistensguard. Den separata `registry.py`-formen byggdes inte.
- Synlig render för section_add är delvis stängd, inte helt öppen: faq/team på
  `local-service-business`, contact-form på `ecommerce-lite`; andra typer kräver
  fortsatt render-breddning eller ska rapporteras mount-only.
- Kvar som framtida beslut: extern dirigent/HTTP-adapter och bredare
  layout-/route-mutationer.
