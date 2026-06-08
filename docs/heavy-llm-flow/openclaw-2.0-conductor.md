# OpenClaw 2.0 — extern dirigent + roll-registry (plan)

> Status: plan (2026-06-08). Kontrollerad riktning, inte fri kod-agent.
> Läs först: `docs/diagnosis-and-handoff-2026-06-08.md`,
> `openclaw-mvp/docs/ARCHITECTURE.md`,
> `openclaw-mvp/docs/SAJTBYGGAREN_INTEGRATION.md`,
> `openclaw-mvp/docs/SAJTMASKIN_SOURCE_INDEX.md`.

## 1. Beslut (målbild)

OpenClaw ska vara en **dirigent**, inte en ny generator och inte en fri
kod-agent. Den ska:

- kunna köras **externt som en Docker-tjänst** (som sajtmaskins
  `infra/openclaw/` gateway), så den är deploybar och fristående,
- vara den **operatören chattar med** (Viewser FloatingChat → HTTP → tjänsten),
- **välja en agentroll** per följdprompt och låta rollen (modell-driven,
  gpt-5.4) producera en **strukturerad, validerad mutation**,
- routa mutationen genom Sajtbyggarens **deterministiska apply + guards**
  (KÖR-7). Aldrig fri filpatch, aldrig parallell engine, aldrig egen
  sanningskälla.

Princip: **frihet i förståelsen (LLM-roller), kontroll i appliceringen
(deterministisk apply + guards).**

## 2. Tre befintliga bitar som binds ihop

| Bit | Vad | Var | Roll i 2.0 |
|---|---|---|---|
| Core V0 (live) | router → context → decide, inkopplad i Viewser via `run_openclaw_followup.py` | `packages/generation/orchestration/openclaw/` | dirigentens beslutskärna |
| openclaw-mvp | FastAPI + Dockerfile + deploy/render+vercel; dry-run tool-calls | `openclaw-mvp/` | bas för den **externa Docker-tjänsten** |
| sajtmaskin (read-only ref) | Docker-gateway + sajtagenten (SOUL.md) + `src/lib/openclaw` kontextpolicy + `/api/openclaw/chat` | `C:\Users\jakem\dev\projects\sajtmaskin\infra/openclaw`, `src/lib/openclaw` | deploy/persona/kontext-blueprint |

## 3. Arkitektur

```text
Viewser FloatingChat
  -> HTTP -> OpenClaw conductor (Docker-tjänst, bas: openclaw-mvp)
       1. classify (router)               -> intent + editKind
       2. välj kontextnivå (context policy)
       3. välj AGENTROLL ur roll-registry
       4. rollen (gpt-5.4) -> strukturerad mutation {target, value | patch}
       5. mutationen -> Sajtbyggarens deterministiska apply + guards (KÖR-7)
       6. ny immutabel version -> preview refresh
```

Dirigenten bygger aldrig själv och patchar aldrig filer fritt. Rollerna
*förstår och föreslår*; den deterministiska kedjan *validerar och applicerar*.

## 4. Roll-registry (det nya, samlande lagret)

Varje roll = ett modell-drivet skript med fast kontrakt: in (fri text +
kontext) → ut (strukturerad mutation) → genom samma guards.

| Roll | Status | In → Ut | Guard |
|---|---|---|---|
| `copy_editor` | KLAR (A1, commit 109ba60) | fri text → copyDirective {company-name\|tagline\|about\|services, value} | leak/grounding/schema/honesty |
| `stylist` | nästa (prompt B) | fri text → tema/visual-directive (primär/accent-färg, font, ton) | tema-schema, honesty |
| `section_builder` | planerad (prompt C) | fri text → section_add (team/FAQ/garantier/recensioner) | sanktionerade typer |
| `reviewer` | planerad | läser artefakter → förbättringsförslag (read-only) | ingen mutation |
| `layout` / `route_builder` | senare | layout/route-mutation | apply-kapabilitet krävs |

Roller är återanvändbara oavsett om dirigenten körs in-process eller som
Docker-tjänst. De byggstenar som redan finns i `packages/generation/` (model
roles + apply-kedjan) återanvänds — registryt är "vilken roll för vilket
intent", inte ny motor.

## 5. Kontextnivå-policy (från sajtmaskins `chat-context-policy`)

Dirigenten väljer hur mycket sajt-kontext en roll får:
`none` → `project` → `artifacts` → `manifest` → `selected_files` →
`full_generated_files`. Skälet: en copy-edit behöver lite, en review behöver
mer. Token-budget per nivå.

## 6. Wiring + deploy

- **Tjänst:** promota `openclaw-mvp/` till den riktiga dirigenten (behåll
  dry-run-grinden tills apply-bryggan är verifierad).
- **Viewser:** FloatingChat → HTTP mot tjänsten (mönster: sajtmaskins
  `src/app/api/openclaw/chat` → gateway). Behåll dagens in-process Core V0 som
  fallback tills HTTP-vägen är grön.
- **Docker:** studera `sajtmaskin/infra/openclaw/{Dockerfile,render.yaml,railway.toml,docker-entrypoint.sh}`
  som blueprint; `openclaw-mvp/Dockerfile` + `deploy/` finns redan.
- **Persona (valfritt):** en Sajtbyggaren-egen `SOUL.md`/identitet för
  dirigenten OM vi vill ha avatar/personlighet — som konfig för VÅR tjänst,
  inte den fria gateway-modellen.

## 7. Guardrails (icke förhandlingsbart)

- Ingen fri Next.js-/fil-patch. Ingen parallell generator. OpenClaw är inte
  sanningskälla — Project Input / Site Brief / Site Plan / Generation Package är.
- `scripts/verify_openclaw.py` grön före varje merge.
- Allt arbete landar på `jakob-be`; ingen main-push utan operatörs-OK.
- `sajtmaskin` + `Desktop/openclaw` är strikt read-only referens (AGENTS.md).

## 8. Faser

- **Fas 0 (klar/pågår):** roll-lyft i befintlig pipeline — `copy_editor` (A1
  klar), `stylist` (B), `section_builder` (C). Höjer förståelse-taket utan ny
  infra.
- **Fas 1:** roll-registry som explicit modul + dirigent väljer roll.
- **Fas 2:** extern Docker-dirigent (promota openclaw-mvp) + Viewser HTTP-adapter.
- **Fas 3:** capabilities som recept (t.ex. `three_3d_scene`), layout/route_add
  — höjer apply-taket.

## 9. Nästa konkreta steg

1. `stylist`-rollen (prompt B): fri/sammansatt färg + tema (höjer samma
   förståelse-tak som A1, men för stil).
2. `section_builder` (prompt C): apply-kapabilitet för nya sektioner.
3. Roll-registry-modul (Fas 1) när 2-3 roller finns.
4. Extern Docker-dirigent (Fas 2) när registryt är stabilt.
