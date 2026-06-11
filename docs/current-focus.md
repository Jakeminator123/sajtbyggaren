# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-11 ~22:55 — kvällspasset: OpenClaw-smartness mergad + /kort-regel + lokal städning)

**Git:** `jakob-be = 6d740fcc` (rent träd, local == origin). Lokal `main`-pekare
fast-forwardad till `origin/main` (`cb0f6a5d`) — bara en bokmärkesflytt, inget
arbete rört. Lokala branches städade: `christopher`, `jakob-be`, `main` kvar;
de tre mergade `backup_*`/`backup-160-BRA` raderade lokalt (finns kvar på
origin). Inga extra worktrees. Main-sync (kvällens senare merges → `main`)
hanteras i parallellt operatörsspår. Prod (`sajtbyggaren-viewser.vercel.app`)
deployas från `main`.

**Kvällens facit (2026-06-11 kväll, fyra PR:ar mergade till jakob-be):**

- **#297** KÖR-6b i bryggan: `run_openclaw_followup.py` eskalerar nu
  tvetydiga/långa följdprompter till routerModel (samma väg som kedjan i
  `build_site.py` redan hade); EN router-klassificering per anrop via
  router-injektion i `orchestrate`/`classify_conversation`; kill-switch
  `OPENCLAW_ROUTER_LLM_FALLBACK=0`; TS-runner-timeout 15→45 s.
- **#298** Dirigent-bekräftelse: efter en SYNLIGT applicerad ändring
  (`previewShouldRefresh=true`) genererar dirigenten 1–2 meningars
  bekräftelse i chatten, grundad enbart i kedjans fakta; mount-only- och
  ärlighetsrader röjs aldrig; no-key → deterministisk rad som förut.
- **#301** B198 del a: prompt som NAMNGER en dossier ("resend") monterar
  `resend-contact-form` i stället för mailto-defaulten (nya router-cues för
  resend/mejlformulär → contact-form + validerad dossier-preferens i
  section_add→apply). Synlig render på ecommerce-lite kvarstår (B198 del b).
- **#296** B198 registrerad i known-issues (19 aktiva / 25 öppna).
- Operatörs-env: prune-taken höjda 6→12 (`SAJTBYGGAREN_MAX_RUNS/GENERATED/
  PROMPT_INPUTS` i lokala `.env`); operatörens manuella radering av
  `data/runs` bekräftad ofarlig (PI-snapshotkedjan intakt).
- **/kort-regel** (`6d740fcc`, direktcommit): ny `governance/rules/13-kort-svar.md`
  (+ `.cursor`-spegel) — operatören skriver `/kort` → ultrakort svar, matris vid
  strukturerat innehåll. `alwaysApply: true`.
- Verifiering: #299/#300 + Vercel-env (22 vars, identiska i Prod/Preview/Dev)
  bekräftade inne på `jakob-be`; `ignoreCommand` utökad med
  `docs/openclaw-workspace` (`2ef8f116`). Notisen om `fix/kvallsbatch-hardening`
  utredd: den branchen är borta, innehållet ligger i #303 — inget kvar att fixa.

**Stora bilden:** oförändrad sedan förmiddagen — P2 skeppad, hostad publik
drift PÅ med rate-limit/TTL/B195/B196 (fullt block i arkivet:
[`current-focus-2026-06-11-em.md`](archive/current-focus-2026-06-11-em.md)).

**Eftermiddagens facit (2026-06-11 em, sex PR:ar mergade till jakob-be +
direktcommits):**

- **#291** Dirigentpult (ADR 0051): överordnad styrsida i backoffice (flikar
  A–G) + ärlighets-audit av alla 32 vyer + tokenpris-snapshot
  (`scripts/fetch_model_prices.py`, `data/model-pricing.json`).
- Per-roll modellparametrar, ADR 0052 (`e55fc0ca`): llm-models v11 med
  reasoningEffort + maxOutputTokens per roll, delad defensiv läsare
  `packages/policies/llm_model_params.py`, åtta call-sites trådade,
  TS-plumbing i `apps/viewser/lib/openai.ts`.
- **#285** (ADR 0046): inspector-/markedSections-grunden mergad — grunden
  landade EN gång, Christophers v36-bump inne.
- **#293** (skördelista A3): committad golden-path-baseline
  (`tests/evals/golden-path-baseline.json`) + regressions-grind
  (`scripts/eval_gate.py`) + nytt Node-fritt CI-jobb `eval-baseline`.
- **#295** (ADR 0053): hard-dossier-kontrakten (env/code/integration +
  mockMode) + första hard-dossiern `resend-contact-form`; dossier-contract
  v4; mailto förblir soft default.
- **#294**: smidig lane-synk + delade löpnummer-protokoll i
  `governance/rules/04-branch-and-team.md` (lärdom av dagens v35/v36-
  ping-pong: re-derivera alltid nummer från färskt origin/jakob-be).
- Direktcommits: gpt-5.5-lyft i chatt/vision/discovery (`6015af17`),
  Vercel-OIDC-pull lagad för Windows/Node 24 (`0be31b3f`), sparsamhetsregel
  för underagenter i `AGENTS.md` (`372904b4`), PowerShell-regler
  (`8ae21fd0`), dossier-AGENT-GUIDE (`e58dcd77`), canvas-facts anti-stale
  (`e37b2a6c`). Inbox msg-0073–0077 till Christopher. **#156 stängd**
  (ersatt av P2-leveransen).
- Versionsläge: llm-models **v11**, naming-dictionary **v37**,
  dossier-contract **v4**.

**Nästa prioriteringar (i ordning):**

1. **Review-kedjan #292 → #304:** #269 är MERGAD (kvällsreview 2026-06-11,
   godkänd; konflikt mot färska basen löst via basmerge `9774b199`).
   Christophers action: rebasa #292 mot färska jakob-be + retargeta, sedan
   #304 (B194-stängningen — hostad run-state till blob + KV-pekare, dvs.
   gamla prio 3 levereras där). Besked skickat (msg-0079). Därefter B197.
2. **Main-sync-uppföljning:** main synkades i kväll i parallellt spår;
   kvällens senare merges (#296–#303 + #269) väntar på nästa sync-fönster.
3. **B198 del b — synlig contact-form-render:** dedikerad-route-mönstret
   (faq/team) för contact-form på ecommerce-lite, så resend-formuläret
   faktiskt syns (del a + hardening är inne).
4. **ADR 0052-uppföljning (litet städ):** ta bort död
   `model="gpt-5.4"`-default i `packages/generation/brief/extract.py` (~rad
   690), byt hårdkodad fallback i `scripts/prompt_to_project_input.py`
   (~rad 3343) mot policy-defaults, tråda design-tooling-skripten
   (variantModel/dossierModel/scaffoldModel — v12-värdena ligger vilande).
   Plus eslint-fyndet i `industry-search.tsx:298` (msg-c-0080).
5. **Token Meter-priser (operatören, valfritt):** USD-priserna i Vercel-env
   sattes till 0 vid konsolideringen — sätt riktiga värden om kostnadsvisning
   önskas hostat.

**Öppna blockers / att-göra:**

- B194/B197 — P3-spår (B194 är nu nästa stora utlösare, se prio 3).
- B155 hålls öppen (kvarvarande targets).
- B192 STÄNGD av Christopher (msg-c-0076) — answer-only renderas nu neutralt.
- `christopher`-lanen äger: `use-followup-build.ts`, dialogerna,
  viewser-frontend/inspector — rör ej.

Last verified state: `6d740fcc` (2026-06-11 ~22:55 UTC+2; `origin/jakob-be =
6d740fcc`, rent träd, local == origin. Kvällen: #296/#297/#298/#301
(OpenClaw-smartness + B198 del a), #302 (fallback-toggle i Dirigentpulten),
#303 (hardening efter extern riskmatris), #299/#300 (parallellspåret: env-dok +
ignoreCommand, kompletterad med docs/openclaw-workspace i `2ef8f116`), **#269
mergad efter godkänd review**, samt `/kort`-regeln (`6d740fcc`). Lokal `main`
fast-forwardad till `cb0f6a5d`; lokala backup-branches städade. ADR-liggare:
nästa lediga **0055**; 0054 är reserverad för MCP-intagsgrinden.)

## Öppna PR att känna till

- **#292** (`feat/hosted-asset-set-forwarding`): Christophers hostade
  asset_set-forwarding. **Hans action:** rebasa mot färska jakob-be +
  retargeta (basen `christopher` är mergad via #269). GO givet (msg-0073).
- **#304** (stackad på #292): **B194-stängningen** — hostad run-state
  persisteras till blob + KV-pekare så följdprompter funkar hostat.
  Reviewas efter #292 (kedjan i msg-c-0081).
- **#305** (`→ main`): Vercel Web Analytics-install (parallellspåret).

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
vid behov → arbete på arbets-branch → guards gröna (riktade tester lokalt,
full svit i CI per guard 5) → push → vid behov PR mot `main` → post-merge-sync.
Orkestrering över längre pass:
[`docs/orchestrator-playbook.md`](orchestrator-playbook.md).

Operatörspreferens: svenska, kort och koncist, gärna matris/tabell. Förklara
dev-uttryck med korta parenteser första gången per konversation. Mönstret i
[`governance/rules/01-language-and-reply.md`](../governance/rules/01-language-and-reply.md).

## Arkiv

Historiska statusblock + checkpoint-kedjan ligger i arkivet:

- [`docs/archive/current-focus-2026-06-11-em.md`](archive/current-focus-2026-06-11-em.md)
  (lunchblocket per `a314fe5a`: P2-skeppningen, #284–#290-kedjan, publik drift PÅ).
- [`docs/archive/current-focus-2026-06-11-fm.md`](archive/current-focus-2026-06-11-fm.md)
  (förmiddagens fulla block: nattpasset 2026-06-10, #270–#287-kedjan, eval-facit).
- [`docs/archive/current-focus-2026-06-08-pre-slim.md`](archive/current-focus-2026-06-08-pre-slim.md)
  (full snapshot precis före slimningen 2026-06-08).
- [`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md)
  (äldre checkpoint-kedja).

För commit-historik: `git log --oneline origin/main` eller
`git log --oneline origin/jakob-be`.

## Föregående checkpoint

Tidigare "Last verified state"-block och äldre "Current objective"-block är
flyttade till arkivet ovan (per `governance/rules/07-docs-focus-handoff.md`).
Auto-bump-verktyget lägger nya korta checkpoint-block här vid main-sync; håll
högst ett kvar och flytta resten till arkivet.

### 2026-06-11 UTC — current-focus.md före `ab8755a6`

Last verified state: `a314fe5a` (2026-06-11 ~13:30 UTC+2; #288/#289/#290
mergade + andra main-syncen, publik drift PÅ). Fulla blocket:
[`docs/archive/current-focus-2026-06-11-em.md`](archive/current-focus-2026-06-11-em.md).
