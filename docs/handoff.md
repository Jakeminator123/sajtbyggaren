# Handoff – Sajtbyggaren

**Datum:** 2026-06-10 natt UTC+2, steward post-merge checkpoint efter nattens
merge-tåg #254/#256/#257/#259/#260 (10 buggar stängda) + branch-städning.
Verifierad `origin/jakob-be` är `3674475` (#258 mergad ovanpå tåg-HEAD
`5e6b008`); `main` är `7486145` (efter #255).

Nya PRs sedan föregående checkpoint: #254, #256, #257, #259, #260, #258
(alla mergade till `jakob-be`), #255 (docs-dedupe, mergad till `main`),
#253 (stängd), #261 (öppen draft, B155).

## CLOSING-ROUND HANDOFF 2026-06-10 (natt, runda 2) — ÖVERLÄMNING TILL NÄSTA AGENT

> **Detta är det ENDA auktoritativa blocket. Allt äldre ligger i arkivet —
> verifiera alltid mot git/koden, aldrig mot äldre block.**
>
> **Git-läge (uppdaterat 2026-06-10 natt, runda 2):**
> `origin/jakob-be = 3674475` efter nattens merge-tåg #254/#256/#257/#259/#260
> (tåg-HEAD `5e6b008`) + #258-mergen strax därefter (alla mergade, CI grönt
> per PR). `main = 7486145` (efter #255) —
> `jakob-be` ligger åter FÖRE `main`; ny main-sync är ett operatörsbeslut.
> Branch-städning gjord: nattens mergade PR-brancher raderade remote
> (fix/viewser-prompt-robustness-b164-b169-b172,
> feat/openclaw-f1-slice1-role-contracts, feat/viewser-hosted-vercel-sandbox
> + dess cursor-spegel, SHA-verifierad) och lokalt (samma två
> feature-brancher). Lokala `rescue/openclaw-f1-d76ad9c` BEHÅLLEN:
> innehållet bedöms ha landat via #259+#260 (kodfilerna är identiska med
> jakob-be) men diffen mot PR-#259-HEAD var inte tom — operatören bekräftar
> innan radering.

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

### Lösa trådar (för dig, prioriterat)

1. **F1 slice 2 — wira rollvalet i conductor-flödet:**
   `scripts/run_openclaw_followup.py` + `/api/prompt` answer-only för
   konversations-kinds (småprat/omdöme svaras direkt utan bygge).
   `route.ts` är ledig efter #260. Plan:
   `docs/heavy-llm-flow/openclaw-2.0-conductor.md`.
2. **B155-slicen (okvoterad literal replace):** PR **#261** (draft, cloud)
   öppnad mot `jakob-be` enligt godkänd plan — granska + merga när den
   lämnar draft.
3. **Vercel-deploy av 2A** (cloud-agent; Vercel-projektet
   sajtbyggaren-viewser finns; Deployment Protection FÖRE eventuell
   sandbox-flagga). Backoffice-grinden #258 är INNE.
4. **Operatörens manuella klick-checkar** (täcks inte av tester):
   /studio "lägg till en öppettider-sektion överst" på LSB-sajt med riktiga
   öppettider → block efter hero; #228:s Ändra-knapp → steg-hopp;
   kontrastfärg "gör sajten mörkblå"; modul-dialogen (#245/#249) visuellt.
5. **Main-sync-beslut:** `jakob-be` före `main` igen efter nattens tåg;
   ny sync-PR när operatören vill ha en officiell version.
6. **#156 hosted `/live`** — parkerad (säkerhet), arkitektur-referens; görs om
   på färsk bas med auth/rate-limit när runtime-spåret väljs aktivt.
7. **Branch-rester för operatörsbeslut:** `cursor/gap-3a-offer-service-guard`,
   `cursor/dossier-intake-v11-review-895d`, `feat/kor-5-repair-pass` (ingen
   PR, ej bevisat mergade), `cursor/preview-runtime-adapters` (avsiktlig
   snapshot), Christophers stängda `feat/viewser-ui-overhaul`/
   `feat/viewser-router-decision-readiness`, samt lokala
   `rescue/openclaw-f1-d76ad9c` (se git-läget ovan).

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
