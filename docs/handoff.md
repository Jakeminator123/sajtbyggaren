# Handoff – Sajtbyggaren

**Datum:** 2026-06-10 natt UTC+2, steward post-merge checkpoint efter nattens
merge-tåg #254/#256/#257/#259/#260 (10 buggar stängda) + branch-städning.
Verifierad `origin/jakob-be` är `3674475` (#258 mergad ovanpå tåg-HEAD
`5e6b008`); `main` är `7486145` (efter #255).

Nya PRs sedan föregående checkpoint: #254, #256, #257, #259, #260, #258
(alla mergade till `jakob-be`), #255 (docs-dedupe, mergad till `main`),
#253 (stängd), #261 (öppen draft, B155).

## SLUTLIG CLOSING-ROUND 2026-06-10 ~06:00 — ÖVERLÄMNING TILL NÄSTA ORCHESTRATOR

> **Detta är det ENDA auktoritativa blocket. Allt äldre ligger i arkivet —
> verifiera alltid mot git/koden, aldrig mot äldre block.**
>
> **Git-läge:** `origin/jakob-be = 9a7c9f6`, rent träd, lokal = origin.
> `main = 7486145`. `jakob-be` ligger 16 PRs före `main` — **main-sync är
> nästa naturliga leveransfönster (operatörsbeslut; efter sync sätter
> Vercel-agenten prod-env med Deployment Protection-villkoret)**.
> Enda öppna PR: **#156** (parkerad arkitektur-referens; Vercel-botens
> accepterade fixar ligger ofarligt på branchen — lärdomen
> `Sandbox.get({resume:false})` är värdefull för Tier 2).
> ALLA mergade PR-brancher städade lokalt+remote (inkl. cursor-speglar och
> docs-dedupe-branchen). `rescue/openclaw-f1-d76ad9c` RADERAD efter
> verifiering (innehållet landade via #259+#260). Kvarvarande lokala
> brancher: `jakob-be`, `main`, `backup_100_BRA`, `feat/live-preview`.
> Inga aktiva worktrees. Operatörens otrackade `.cursor/rules`-fil lämnad
> (personlig regel; flytta till governance/rules om den ska bli permanent).
>
> **Nattens slutfacit: 16 PRs mergade (#252, #254–#267 utom stängda #253),
> 13 buggar stängda (B163–B175).** Sen runda 2-blocket skrevs landade
> dessutom: #261 (B155-slice okvoterad literal replace), #262 (F1 slice 2 —
> SMARTA CHATTEN LIVE: skämt/omdöme/fråga → ärligt svar utan bygge),
> #263 (sandbox Tier 1: pre-built .next ~20 s/preview + OIDC-autorefresh +
> timings; + Scout-R1 trace-katalog-härdning `472e150` direkt på jakob-be),
> #264 (B173 hero-H1-pinning i BÅDA seams — Scout fångade apply-gapet),
> #265 (B174 falska QG-varningen: sentinel-kontrakt för bridge-JSON),
> #266 (prune-on-dev-start: npm run dev städar gamla byggen säkert),
> #267 (B175 first-run-recovery med mtime-färskhet).
>
> **Arbetssätt som fungerade i natt (rekommenderas):** Builder-agenter i
> EGNA git-worktrees (aldrig branch-byte i delade huvudträdet) → PR mot
> jakob-be → READ-ONLY Scout-granskning per PR → merge vid go + grön CI.
> Scout-grinden fångade skarpa fel i 4 av 9 granskningar — behåll den.

### Vad som landade i natt (per tema)

**Bug-sweep round 1 (#254, 6 buggar):** B163 stale preview efter ny version,
B165 apex↔www-crawl, B167 prune-guardens portar, B168/B170/B171
OpenAI-env-kedjan (nyckelhantering/Token Meter/cache).

**Wizard (#256):** B166 — Hämta-knappen gör nested merge så scrape-fält inte
skriver över operatörens ifyllda fält. Prioriterad direkt av eval-rundans
dominanta `contact`-problem.

**Hostad Viewser (#257, FAS 2A+2B):** ärlig 2A-degradering (hostad läge utan
Python-vägar svarar ärligt i stället för att låtsas), gatad 2B
sandbox-preview med blob-source (`generated-blob-source.ts`,
snapshot-CLI). VIKTIGT: sandbox-flaggan får ALDRIG sättas i Vercel-projektet
utan Deployment Protection (Vercels åtkomstskydd) aktiv.

**OpenClaw F1 slice 1 (#259):** rollkontrakt i
`packages/generation/orchestration/openclaw/roles.py` + `ConversationKind`
(conductor-klassning småprat/omdöme/edit; messageKind-låsningen på 8 intakt),
58 tester.

**Följdprompt-robusthet (#260):** B164 dubbelbygge-recovery (ingen tyst
legacy-fallback ovanpå redan skriven chain-version), B169 per-site-mutex i
`/api/prompt` (site A blockerar inte site B), B172 siteId-filtrerad
runId-detektion i `build-runner.ts`.

**Backoffice-grinden (#258, cloud-lane):** governance-lås för vy-registret
(`governance/policies/backoffice-views.v1.json` + schema), Idag-landningsvy
med färskhetsbrickor, Loop-bevis-vy som bygger sajt deterministiskt.
Mergad strax efter tåget (HEAD `3674475`).

**Eval (styrde prioriteringen):** real-LLM Golden Path 2026-06-10 = 8.2/10
totalt, alla 4 case pass, gate go; deterministisk baseline 7.75. Dominant
problem `contact` i alla case → B166 togs först.

### Lösa trådar (för nästa orchestrator, prioriterat)

1. **Main-sync-beslut (operatören):** 16 PRs verifierade och gröna —
   bra fönster. Efter sync: be Vercel-agenten sätta prod-env
   (`VIEWSER_ALLOWED_HOSTS` = `sajtbyggaren-viewser.vercel.app`;
   `VIEWSER_ENABLE_HOSTED_SANDBOX` ENDAST bakom Deployment Protection).
   Hosted preview är redan live på jakob-be-previewen bakom SSO
   (dokumenterat i #257-tråden).
2. **F1 slice 3 — section_builder-dispatch:** rollvalet styr skill/prompt
   i kedjan (idag bara metadata), ärlig roll-rad i FloatingChat,
   dialog-vägens konversationshantering (use-followup-build),
   `expectsAnswer`-signal (Scout-fynd #262). Plan + stylist-scope-
   beslutsunderlag: `docs/heavy-llm-flow/openclaw-2.0-conductor.md`.
3. **Sandbox-mätning + Tier 2:** mät #263:s verkliga vinst (`timings`
   med/utan `VIEWSER_SANDBOX_UPLOAD_BUILT=0` på painter-palma); därefter
   bas-snapshot (P3) + sandbox-återanvändning (liten ADR; kom ihåg
   `Sandbox.get({resume:false})`-lärdomen från #156-boten).
4. **Operatörens kvarvarande klick-checkar:** #228 Ändra→steg-hopp,
   modul-dialogen (#245/#249) visuellt, manuell 1–10-score i Backoffice
   (Idag-vyn). Öppettider-checken GODKÄND i natt; mörkblå-checken gav
   stylist-scope-frågan (punkt 2). OBS: operatören bör STARTA OM sin
   dev-server så nattens fixar (B163/B164/B174 + prune-on-dev-start) gäller.
5. **Starter-hygien-slice (kräver operatörs-OK, plattform-pins):**
   `engines`-fält i starters, `allowScripts` för sharp, transitiv
   msw-spårning, beslut om docs-base/portfolio-base ska runtime-mappas
   (idag medvetet omappade — aktivering = governance-slice i
   scaffold-kontraktet, inte bara filer på disk).
6. **#156 hosted `/live`** — parkerad (säkerhet), arkitektur-referens; görs om
   på färsk bas med auth/rate-limit när runtime-spåret väljs aktivt.
7. **Branch-rester för operatörsbeslut:** `cursor/gap-3a-offer-service-guard`,
   `cursor/dossier-intake-v11-review-895d`, `feat/kor-5-repair-pass` (ingen
   PR, ej bevisat mergade), `cursor/preview-runtime-adapters` (avsiktlig
   snapshot), Christophers stängda `feat/viewser-ui-overhaul`/
   `feat/viewser-router-decision-readiness`. (`rescue/openclaw-f1-d76ad9c`
   är raderad efter verifiering.)
8. **Christopher-koordinering:** msg-0060 (B166) + msg-0061 (#262 rörde
   FloatingChat, heads-up B173/Tier 1, sandbox-primär, main-sync-avisering
   kommer) väntar på kvittens. B169-uppföljning i hans lane noterad.
9. **Delade canvases (nytt, Steward-ägt):** `docs/canvases/` innehåller
   begreppskartan + openclaw-flödet som interaktiva canvases, delade via
   git. Spegla lokalt med `python scripts/sync_canvases.py`; fakta-blocket
   hålls i synk med `python scripts/update_canvas_facts.py --check` (körs
   även automatiskt post-merge på `main` via steward-auto-bump). Rutin och
   ägarskap: `docs/canvases/README.md` + orchestrator-playbookens
   Steward-avsnitt.

### Kända småsaker (inte buggar)

- `C:\Users\jakem\Desktop\sb-wt-hygiene` — tom kvarlåst worktree-katalog
  (fil-lås av process); git-registret är prunat. Försvinner vid omstart eller
  manuell radering. Ofarlig.
- Döda regel-länkar efter regelkonsolideringen 29→12 (#218) är fixade i alla
  AKTIVA docs 2026-06-10 (`branch-discipline.md` → `04-branch-and-team.md`,
  `reply-style.md` → `01-language-and-reply.md`). Arkiv + ADR:er behåller
  medvetet sina historiska stavningar — markdown-varningar därifrån kan
  ignoreras.
- Två gamla filer med blandade radslut (CRLF+LF): `docs/archive/current-focus-
  history-2026-05-26.md`, `governance/policies/scaffold-contract.v1.json` —
  harmlöst, medvetet orört.

## Historik

Allt äldre än toppblocket ovan är flyttat till
[`docs/archive/2026-06/handoff-history-2026-06-09.md`](archive/2026-06/handoff-history-2026-06-09.md)
(arkiv = historik, inte sanningskälla — verifiera mot git). Hela
versionshistoriken finns kvar via `git log --follow docs/handoff.md`.

## Föregående checkpoint

### 2026-06-10 UTC — handoff.md före `3674475`

**Datum:** 2026-06-10 natt (UTC+2), efter PR #252-main-syncen. Verifierad
`main` = `jakob-be` = `e6a06a5` (ren övertagning av merge-tåget #238-#251 +
#225, tom diff verifierad, CI grönt). Post-merge-sanity: governance 19/19,
rules_sync OK, ruff 0, term-coverage --strict OK, riktade sviter gröna.

Nya PRs sedan dess checkpoint: PR #252 (sync jakob-be→main). Därefter kom
nattens runda 2 (#254/#256/#257/#259/#260 på `jakob-be`, #255 på `main`) —
se toppblocket.
