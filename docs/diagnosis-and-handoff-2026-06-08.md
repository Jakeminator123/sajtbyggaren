---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

# Diagnos + Handoff — LLM-flödet & "Lovable-känslan" (2026-06-08)

> **Arkivnot (lane A, 2026-06):** Historisk diagnos — värdefull bakgrund men
> **inte** en aktiv diagnos (verifiera alltid mot koden). Behålls *på plats*
> (inte flyttat till `docs/archive/`) eftersom filtexten innehåller en
> branch-referens som blockeras av repo-secret-scannern vid filflytt.
> Sanningskälla för nuläget: `docs/current-focus.md` + `docs/handoff.md`.

> Skriven efter en live-demo där operatören testade följdprompter i Viewser
> och blev besviken: färg funkade, men "byt rubriken" redigerade fel fält och
> "lägg till en sida" hände inte. Detta dokument förklarar **exakt varför**,
> skiljer på två olika problemklasser, och ger en prioriterad väg framåt.
>
> Läs först: `docs/current-focus.md`, `docs/handoff.md`,
> `docs/heavy-llm-flow/post-build-plan.md`, `AGENTS.md`.

---

## 1. TL;DR — ärlig dom

Du har **inte** byggt en fri Lovable/v0-agent som skriver om valfri React/Next-kod.
Du har byggt en **kontrollerad, deterministisk byggare** med ett LLM-lager ovanpå,
där friheten sitter i **godkända mutationskontrakt** — inte i fri kodpatchning.

Den externa reviewern har rätt i huvudbilden. Men live-demon avslöjade att det
finns **två olika problem** som lätt blandas ihop:

| # | Problemklass | Exempel från demon | Natur | Storlek att fixa |
|---|---|---|---|---|
| A | **Precision/targeting-bugg** | "byt rubriken" → bytte *företagsnamnet* | Ett felklassat nyckelord | Liten (timmar) |
| B | **Saknad förmåga (capability gap)** | "lägg till en sida" → hände inget | Pipelinen har ingen väg | Stor (rör routing+nav+mall+schema+build) |

Det viktiga: **A är inte en LLM-svaghet — det är en kodbugg.** "Byt hero-rubriken"
*borde* fungera idag och gör det inte, p.g.a. en enda rad i en nyckelordslista.
Det är därför det känns trasigt på en "grundläggande" nivå.

---

## 2. Vad du faktiskt har (lager för lager)

| Lager | Finns? | Vad det gör |
|---|---|---|
| LLM för brief/struktur/copy | ✅ | Tolkar företaget, skriver copy, planerar sidstruktur |
| Router/intent-tolkning | ✅ | Klassar följdprompt: fråga / edit / review / oklart |
| LLM-fallback för svåra routerfall | ✅ | Hjälper tolka svårare promptar (kräver `OPENAI_API_KEY`) |
| OpenClaw Core V0 | ✅ | Ren **beslutsmotor** (dirigent): returnerar `answer_only` / `plan_only` / `clarification` / `patch_plan_request`. Ingen disk-I/O, ingen build, inget shell, inget nät |
| Patch/apply-kedja (KÖR-7) | ✅ | Skapar ny immutabel version för **stödda** ändringar (router→context→patch→apply→targeted render) |
| **Fri kodredigering av React/Next** | ❌ | LLM får **aldrig** skriva/patcha komponentkod |
| **"Ändra vad som helst"-agent** | ❌ | Finns inte |

"Heavy LLM-flow" i projektet betyder: **fler modellroller + mer strukturerad
pipeline + kvalitet/repair/verifiering** — INTE "LLM öppnar filerna och skriver
om koden". Det är skillnaden mellan din förväntan och nuläget.

---

## 3. Rotorsak till demo-felen (bevisat i kod)

### 3A. "Byt rubriken på startsidan till X" → bytte *företagsnamnet*

Detta är **bugg-klass A** och den är konkret. Följdprompten klassas av
`_classify_copy_target()` i
[`packages/generation/followup/copy_directives.py`](../packages/generation/followup/copy_directives.py).

Ordet **"rubrik"/"rubriken"** ligger i `_COPY_DIRECTIVE_NAME_KEYWORDS` (rad 63-64)
**och** i `_COPY_DIRECTIVE_EXPLICIT_NAME_KEYWORDS` (rad 258-261). Klassificeraren
kör i denna ordning:

1. tagline-nyckelord? (`tagline`, `underrubrik`, `hero-text`, `slogan`…) → "rubrik" finns INTE där → nej
2. about-nyckelord? → nej
3. services-nyckelord? → nej
4. **namn-nyckelord?** → **"rubriken" träffar** → returnerar `company-name`

Alltså: motorn antar att "rubrik/header" = företagsnamnet (för att namnet renderas
i nav-headern + hero-H1). Men när en användare säger *"byt rubriken på startsidan"*
menar hen **hero-rubriken (H1)**, inte företagsnamnet. **En semantisk miss inbakad
i en nyckelordslista.** Resultatet: namnet döptes om i stället för rubriken.

> Sekundärt: värdet blev "Jakobs" i stället för "Jakobs smålandshöns". Det är en
> separat värde-extraktions-/LLM-nyans (company-name behandlas annorlunda än
> citerad tagline). Primärfelet är target-klassificeringen ovan.

**Fixen (liten, klass A):** låt `rubrik/rubriken/huvudrubrik/huvudrubriken` mappa
till **`tagline`** (hero-H1), och behåll bara `företagsnamn/header/heter/rename`
som `company-name`. Flytta nyckelorden + uppdatera tester. Detta är reviewerns
prio 1 ("copy_change skarpare target").

### 3B. "Lägg till en ny sida" → hände inget (ärlig no-op)

Detta är **bugg-klass B (capability gap)**. Patch-plannern stödjer idag i praktiken
bara: `component_add` (capability), `copy_change` (named-field copy), och efter
**#207** `visual_style` (färg/typsnitt → `brand`/`tone`). Det finns **ingen**
`route_add`-väg: en ny sida kräver att flera delsystem rörs samtidigt —
**routePlan** (ny rutt), **navigation** (länkar i header/footer), en **sidmall +
sektionsrenderare**, **blueprint-schemat**, och **bygget**. Ingen följdprompt-väg
finns för det → avsikten har ingenstans att landa → ärlig no-op.

Viktigt och bra: **systemet ljög inte.** Det rapporterade bara namnändringen och
påstod aldrig att sidan lades till. Honesty-grinden håller.

---

## 4. Varför ett "bra LLM-flöde" ändå inte fixar grunderna

Flaskhalsen är **inte modellförståelse**. GPT förstår redan "byt hero-rubriken
till X" och "lägg till sida Y" perfekt. Problemet är att avsikten trattas genom
ett **smalt kontrakt** `{mål, värde}` med en fast meny av mål
(`company-name | tagline | about-text | services` + tema + några capabilities).
Allt som inte ryms i en lucka **kastas**:

- "byt rubriken" → fanns en lucka, men **fel lucka** valdes (klass A-bugg).
- "lägg till sida" → fanns **ingen lucka** (klass B-gap).

Detta är ett **medvetet** designval: deterministisk grund + LLM som dirigent ger
säkerhet, reproducerbarhet och inga trasiga/hallucinerade byggen — priset är
begränsad uttrycksförmåga. Du valde "kontrollerad Sajtbyggaren-agent", inte "fri
appbyggar-agent". Det är inte fel väg — men målbilden måste vara tydlig.

---

## 5. Målbild — två lägen (beslut krävs)

| Läge | Beskrivning | Status |
|---|---|---|
| **Safe Mode** | OpenClaw dirigerar via godkända mutationskontrakt (nuvarande väg) | byggs nu |
| **Agent Code Mode** | LLM får patcha filer i sandbox, med diff + build + rollback | framtida, premium |
| **Publish Mode** | Bara build-gröna/godkända ändringar kan publiceras | grind |

**Rekommendation (delad av extern reviewer):** fortsätt Safe Mode och **bredda de
5 vanligaste användarändringarna** innan ni ens överväger fri kodpatchning. Inför
Agent Code Mode för tidigt = tillbaka till gamla Sajtmaskin-kaoset (trasiga
byggen, hallucinerade komponenter, svår debug).

---

## 6. Prioriterad väg framåt (capability-breddning)

| Prio | Capability | Användarfras som då funkar | Lane |
|---|---|---|---|
| 0 ✅ | UI-wiring av OpenClaw `--apply` | (klart, PR #210) | — |
| **1** | **`copy_change` skarpare target** | "byt **hero-rubriken** till X" landar rätt | jakob-be |
| 2 | `section_add` | "lägg till sektion om team/FAQ/garantier/recensioner" | jakob-be |
| 3 | `route_add` | "lägg till en sida om X" | jakob-be |
| 4 | `layout_change` | "gör hero centrerad / mer luftig" | jakob-be |
| 5 | `visual_style` bredare router | "gör den rosa/modern/lyxigare" ("gör"-verb) | jakob-be |

Detta ger Lovable-känsla **utan** att gå full fri kodagent. Prio 1 är liten och
ger störst omedelbar "det funkar ju"-effekt (fixar exakt det som kändes trasigt).

---

## 7. Handoff — repo-status

- **`main` = `629a2d5`** (PR #210 mergad: OpenClaw `--apply` wirad i `/api/prompt`
  + FloatingChat; restyle materialiseras nu i UI:t — färg/typsnitt-följdprompt →
  ny version → preview ändras, live-bevisat).
- **`jakob-be` = `b3f9f5c`** (2 docs/städ-commits före main; rider nästa sync):
  - `562f35a` current-focus: UI-wiring landad, nästa hävstång = router/targeting.
  - `b3f9f5c` borttagen felstavad `.cursorindexignore` (canonical fil heter
    `.cursorindexingignore` och fanns redan).
- **`christopher`**: ska `git fetch && git reset --hard origin/main` (mycket
  landat). **`christopher-ui`**: parkerad/fryst — rör ALDRIG utan operatörs-OK.
- **Inbox**: `msg-0043` (relay) + `msg-0044` (orchestrator tog UI-slicen) skickade
  till `christopher`. **Inget svar/ack från Christopher ännu** — bollen ligger inte
  hos honom; nästa steg är backend-slices (prio 1-5 ovan) på `jakob-be`.

### Live-bevis denna runda (sajt `foretag-som-arbetar-med-61bd12`, getgård, riktig LLM)
- "ändra färgen till rosa" → **v4→v5**, sajten blev rosa, preview uppdaterad live. ✅
- "byt rubriken… + lägg till sida" → **v5→v6**, företagsnamn → "Jakobs"; ingen ny
  sida. ✅ text-väg fungerar / ❌ fel target (klass A) + ingen route_add (klass B).

### Nästa agent: börja här
1. **Prio 1 (rekommenderad första slice, jakob-be):** flytta `rubrik*` från
   company-name- till tagline-nyckelorden i `copy_directives.py`; lägg
   regression-test ("byt rubriken till X" → `tagline`, inte `company-name`);
   verifiera att "byt företagsnamnet till X" fortsatt → `company-name`. Kör
   `--real-llm`-repro för punkt C samtidigt (remap-signalen).
2. Därefter `section_add` (prio 2) enligt samma #207-mönster (`run_followup_chain`
   + `apply_patch_plan` + ny renderer-väg).
3. Uppdatera `docs/current-focus.md` + `docs/handoff.md` när nästa agents arbete
   ändras.

### Aldrig-rör
`backup-*`, `christopher`, `christopher-ui`, `main`, `feat/live-preview` (#156),
`hosted-sandbox-mvp`. Bygg inte hosting. Inför inte fri kodpatchning utan ADR +
operatörsbeslut.

---

## 8. Svar på din fråga, rakt

- **Editerades fel saker?** Ja — "byt rubriken" träffade fel fält. Det är en
  konkret, liten kodbugg (prio 1), inte en fundamental brist.
- **Har du ett Lovable-likt flöde?** Nej. Du har ett kontrollerat dirigent-flöde.
  Lovable-känslan kommer av att **bredda de 5 capabilities ovan**, inte av att
  släppa LLM:en lös på koden.
- **Är du på fel väg?** Nej — men målbilden måste vara explicit: kontrollerad
  OpenClaw-dirigent som breddas steg för steg (säkert), eller senare ett separat
  sandboxat Agent Code Mode (kraftfullt men riskabelt). Inte båda samtidigt.
