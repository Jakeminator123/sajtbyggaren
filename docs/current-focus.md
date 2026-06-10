# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-10, natt — post-merge-tåg #254/#256/#257/#259/#260 + #258 + #261)

**Git:** `jakob-be = d6e7177` (#261 mergad ovanpå #258, därefter
cloud-grind-promptstädningen). `main = 7486145` (efter #255, docs-dedupe).
`jakob-be` ligger åter FÖRE `main` — ny main-sync är ett kommande
operatörsbeslut. Nattens mergade PRs på `jakob-be` (totalt **11 buggar
stängda** i natt):

- **#254** bug-sweep round 1: B163 stale preview, B165 www-crawl,
  B167 prune-portar, B168/B170/B171 OpenAI-env — 6 buggar stängda.
- **#256** `fix(wizard)`: B166 — wizardens Hämta-knapp gör nu nested merge
  (scrape-fält skrivs inte längre över).
- **#257** hostad Viewser: ärlig 2A-degradering (read-only utan Python-vägar)
  + gatad 2B sandbox-preview (blob-source). Sandbox-flaggan får ALDRIG
  sättas utan Deployment Protection (Vercels åtkomstskydd) på projektet.
- **#259** OpenClaw F1 slice 1: rollkontrakt + `ConversationKind`
  (conductor-klassning av småprat/omdöme vs edit), 58 tester.
- **#260** `fix(viewser)`: B164 dubbelbygge-recovery, B169 per-site-mutex,
  B172 siteId-filtrerad runId — följdprompt-loopens robusthet.
- **#258** `feat(backoffice)`: backoffice-grinden (cloud-lane) — governance-lås
  för vy-registret, Idag-landningsvy + färskhetsbrickor, Loop-bevis-vy.
  Mergad strax efter tåget (HEAD `3674475`).
- **#261** B155: okvoterad literal-ersättning ("ändra X till Y") i
  följdprompt. Mergad efter tåget (`f6ed39b`); rotorsak i
  docs/gaps/GAP-followup-prompt-content-passthrough.md.

**Eval-resultat:** real-LLM Golden Path 2026-06-10 = **8.2/10** totalt
(alla 4 case pass, gate go); deterministisk baseline 7.75. Dominant problem
var `contact` i alla fyra case — det styrde B166-prioriteringen i natt.

**Riktning (icke förhandlingsbar):** OpenClaw är en conductor/bridge på den
befintliga in-repo-motorn — inte en ny parallell motor, inte extern Docker/
Gateway i nuvarande fas, inte fri filpatch. In-repo-källan ENBART
(`packages/generation/orchestration/openclaw/`, `scripts/run_openclaw_followup.py`,
`scripts/verify_openclaw.py`, `apps/viewser/lib/openclaw-runner.ts`,
`apps/viewser/app/api/prompt/route.ts`). Plan:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](heavy-llm-flow/openclaw-2.0-conductor.md).
`sajtmaskin` + `C:\Users\jakem\Desktop\openclaw` = strikt read-only (AGENTS.md).

**Nästa prioriteringar (ny ordning efter nattens merge-tåg):**

1. **F1 slice 2 — wira rollvalet i conductor-flödet:** PR **#262** är
   öppen (conversation gate + role metadata; answer-only-vägen bevisad i
   operatörens klick-check 5 nedan) — granska + merga. Plan:
   `docs/heavy-llm-flow/openclaw-2.0-conductor.md`.
2. **Fix-slice: falsk QG-varning i FloatingChat** — "Quality Gate flaggade
   något" visades på alla tre versioner i nattens klick-checkar trots
   helgrön quality-result; spår: degraded-status i API-lagret, ej QG
   (klick-check 3 nedan). B155/#261 är mergad och ute ur listan.
3. **Vercel-deploy av 2A** (cloud-agent; Vercel-projektet
   sajtbyggaren-viewser finns; Deployment Protection måste vara aktiv FÖRE
   en eventuell sandbox-flagga). Backoffice-grinden #258 är INNE.

**Öppna blockers / att-göra:**

- **Manuella klick-checkar kvar (operatören):** #228 review-summary
  (Ändra→steg-hopp) + #240 öppettider-inline i /studio + #245/#249
  modul-dialogen (badges, en-modul-per-bygge, inaktiva sidzoner).
  Täcks inte av automatiska tester.
- **Main-sync-beslut:** `jakob-be` ligger nu före `main` igen efter nattens
  merge-tåg; ny sync-PR är ett operatörsbeslut.
- Branch-städning 2026-06-10: nattens mergade PR-brancher raderade
  (remote: fix/viewser-prompt-robustness-b164-b169-b172,
  feat/openclaw-f1-slice1-role-contracts, feat/viewser-hosted-vercel-sandbox
  + cursor-spegel; lokalt: samma två feature-brancher). Kvar för
  operatörsbeslut: `feat/viewser-ui-overhaul`/
  `feat/viewser-router-decision-readiness` (Christophers stängda, ej
  mergade), `cursor/gap-3a-offer-service-guard`,
  `cursor/dossier-intake-v11-review-895d`, `feat/kor-5-repair-pass` (ingen
  PR), `cursor/preview-runtime-adapters` (avsiktlig snapshot), samt lokala
  `rescue/openclaw-f1-d76ad9c` (innehållet bedöms ha landat via #259+#260
  men diffen mot PR-#259-HEAD var inte tom — behållen tills operatören
  bekräftar).

**Operatörens klick-checkar 2026-06-10 natt (/studio, sajt painter-palma,
sandbox-läge):**

1. "gör sajten mörkblå" → tema applicerat korrekt (`#1e3a8a`) men bara
   `--primary`/knappar — operatörsintentionen "hela sajten" träffas inte;
   stylist-scope-fråga för F1.
2. "lägg till en öppettider-sektion överst" → GODKÄND: synligt block efter
   hero — första mänskliga beviset av ADR 0038.
3. FALSK VARNING: FloatingChat sa "Quality Gate flaggade något" på alla
   tre versioner trots helgrön quality-result. Rotorsak utreds
   (degraded-status i API-lagret, ej QG) — fix-slice imorgon (prio 2).
4. Hero-H1 byter text vid VARJE ombygge (3 ggr bevisat) —
   heroHeadline-override saknas; kandidat: auto-pinna efter första bygget.
5. "kan du dra ett skämt?" → byggde v6 + "Klart!" — beviset för F1
   slice 2:s answer-only-väg (nu öppen som PR #262).

**Pågående:** PR **#262** (F1 slice 2, från worktree `sb-wt-f1s2`) är
öppen; sandbox Tier 1-smidighet pågår i worktree `sb-wt-sandbox-t1`
(PR väntas; plan i agent-rapport: pre-built `.next`-upload +
OIDC-autorefresh + timings).

**Operatörsbeslut taget:** Vercel Sandbox = primär preview-adapter lokalt.

Last verified state: `d6e7177` (2026-06-10 natt UTC+2; `jakob-be` HEAD efter
#261-mergen (B155) och cloud-grind-promptstädningen, ovanpå nattens
merge-tåg #254/#256/#257/#259/#260 + #258. `main = 7486145` efter #255 —
`jakob-be` före `main`, sync väntar operatörsbeslut).
Nya PRs sedan föregående checkpoint: #254, #256, #257, #259, #260, #258,
#261 (alla mergade till `jakob-be`), #255 (mergad till `main`), #253
(stängd), #262 (öppen, F1 slice 2).

## Öppna PR att känna till

- **#156** (`feat/live-preview → jakob-be`): hostad `/live`-loop. **Parkerad pga säkerhet**
  (publik POST utan auth/rate-limit kan starta sandboxar). Behålls som arkitektur-referens;
  görs om på färsk bas med auth/rate-limit designat från start när runtime-spåret väljs aktivt.
- **#262** (`feat/openclaw-f1-slice2-conductor-wiring`): F1 slice 2 —
  conductor wiring (conversation gate + role metadata). Öppnad av
  worktree-agenten (sb-wt-f1s2); granska + merga (prio 1 ovan).

Christophers UI-arbete sker på `christopher` (gamla `christopher-ui` är fryst legacy).

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Efter varje merge/sync som ändrar nästa agents
arbete: bumpa SHA:n på "Last verified state"-raden, uppdatera de tre
prioriteringarna + blockers, och flytta utgånget innehåll till arkivet (se hygien-regeln). Steward
post-push-verifierar `origin`-SHA, `git status` och `python scripts/focus_check.py`.
Uppdatera inte för ren mikrostatus som inte ändrar nästa agents arbete.

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`; Christopher på `christopher`. `main` är
  canonical/sanningsbranch.
- PR från arbets-branch → `main` när "en ny officiell version ska in" (beslut
  per leveransfönster, ingen cadence). Efter merge synkas arbets-branchen mot
  `origin/main`.
- Detaljer: [`governance/rules/04-branch-and-team.md`](../governance/rules/04-branch-and-team.md).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) ("Standard loop"). Kort: Scout
vid behov → arbete på arbets-branch → guards gröna → push → vid behov PR mot
`main` → post-merge-sync. Orkestrering över längre pass:
[`docs/orchestrator-playbook.md`](orchestrator-playbook.md).

Operatörspreferens: svenska, kort och koncist, gärna matris/tabell. Förklara
dev-uttryck med korta parenteser första gången per konversation. Mönstret i
[`governance/rules/01-language-and-reply.md`](../governance/rules/01-language-and-reply.md).

## Arkiv

Historiska statusblock + checkpoint-kedjan ligger i arkivet:

- [`docs/archive/current-focus-2026-06-08-pre-slim.md`](archive/current-focus-2026-06-08-pre-slim.md)
  (full snapshot precis före denna slimning).
- [`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md)
  (äldre checkpoint-kedja).

För commit-historik: `git log --oneline origin/main` eller
`git log --oneline origin/jakob-be`.

## Föregående checkpoint

Tidigare "Last verified state"-block och äldre "Current objective"-block är
flyttade till arkivet ovan (per `governance/rules/07-docs-focus-handoff.md`).
Auto-bump-verktyget lägger nya korta checkpoint-block här vid main-sync; håll
högst ett kvar och flytta resten till arkivet.

### 2026-06-10 UTC — current-focus.md före `3674475`

Last verified state: `e6a06a5` (2026-06-10 natt UTC+2; `main` = `jakob-be` =
`e6a06a5` efter PR #252-sync — merge-tåget med 15 PR:ar #238-#251 + #225
(synlig section_add ADR 0038, golden-path-smoke, auto_prune opt-in,
recommendedPages-API m.m.) togs över till `main` som ren övertagning, tom
diff main↔jakob-be verifierad, CI grönt). Därefter landade #255 på `main`
(docs-dedupe, `7486145`) och nattens fem PR:ar #254/#256/#257/#259/#260 på
`jakob-be`. Äldre checkpoint-kedja: arkivet ovan + `git log --follow`.
