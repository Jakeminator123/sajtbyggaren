# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-14 ~17:00 — takeover-prep: #316 noterad, dagens leveranser #310–#316, konduktör-roadmap)

**Git:** `main = jakob-be = origin/main = origin/jakob-be = 8005be92` (#316,
rent träd) vid rundans start; denna docs-commit ligger ovanpå på `jakob-be`
och `main` ff-synkas till samma tip. Production deployar från `main`.
Föregående focus-block (#314/#315, 2026-06-12 kväll) är arkiverat:
[`docs/archive/current-focus-2026-06-12-kvall.md`](archive/current-focus-2026-06-12-kvall.md).

**Nya PRs sedan föregående checkpoint:** #316 (mergad, `8005be92`) och #317
(öppen draft — se "Öppna PR att känna till"). Ingen PR mergades denna runda.

#316 ("Spår A", `8005be92`) är internt kallad färgfixen och är skilt från
uppgift A/#310 (dossier-deps). En restyle-följdprompt ("gör sajten blå",
"snyggare typsnitt") landar nu via tema-utföraren: `run_followup_chain` fick
en LLM-stylist-fallback bakom en delad eligibilitetsgrind
(`theme_directive_llm_eligible`, identisk för legacy-prompt-vägen och
OpenClaw-kedjan), ärlig `visual_style`-target-summary (inte contentBlocks-
mislabel), och "effekter" förblir ärligt oapplicerat. Rörde
`packages/generation/followup/` + `scripts/`, INTE `apps/viewser`-frontend.
Full dagsleverans #310–#316 + detaljer: [`docs/handoff.md`](handoff.md).

**Nästa 3 prioriteringar:**

1. **Operatörens produktions-E2E på `main`** (Jakobs nästa steg — agenter
   ska INTE förekomma testet): konkret restyle ("gör sajten blå") ska byta
   färg hostat; ren fråga svarar utan sandbox; andra previewn använder
   `source=preview-bundle` (lågt `sourceMs`); no-op ger ärlig rad (ingen
   falsk "Klart!"). #316 rörde inte frontend → ingen ny Vercel-frontend-
   deploy; produktändringen når hostade pipen via build-context-tarballen
   (bekräfta att den speglar `8005be92` — se handoff).
2. **Uppgift I — B197 discovery-paritet hostat** (HÅLLS tills prod-E2E
   grön): hostade byggvägen trådar bara prompttext, inte wizardens
   strukturerade discovery-payload. (Koordinera med Christophers spår,
   msg-0085.)
3. **Steg 1 mot konduktör-visionen (rekommenderad första byggskiva, M):**
   låt `component_builder` gå partial→supported mount för komponenter som
   redan finns i katalogen/capability-map (samma apply/mount-maskineri som
   FAQ/contact-form), ärligt mot #313. Kräver ADR-utökning av 0057. Underlag:
   [`docs/heavy-llm-flow/conductor-vision-roadmap.md`](heavy-llm-flow/conductor-vision-roadmap.md).

**Öppna blockers:** inga hårda.

Last verified state: `8005be92` (2026-06-14 ~17:00 UTC+2; #316 "Spår A"
mergad till `jakob-be` + `main`. Denna takeover-prep-runda: #316 noterad,
kvällsblocket arkiverat, B202/B203 bokförda i known-issues, konduktör-roadmap
tillagd. Ingen PR mergad — #317 är en draft som operatören beslutar om. Denna
docs-commit bumpar SHA:n och `main` ff-synkas till samma tip.)

## Öppna PR att känna till

- **#317 (draft, `cursor/setup-dev-environment-3a91` → `main`) — MERGAS EJ av
  agent, operatören beslutar.** Auto-genererad Cloud Agent env-setup-PR
  (Jakeminator123 + cursoragent). Enda kodändring: 6/3 rader i `AGENTS.md`
  som dokumenterar att `sudo apt-get update` måste köras före venv-paketet
  på en färsk VM. CI helt grön och mergeable, men den är (a) en draft,
  (b) siktar `main` direkt förbi `jakob-be`, och (c) hör inte till
  #310–#316-tåget — därför avstod takeover-prep-rundan. Operatören: markera
  ready + välj bas (sannolikt `jakob-be`) om innehållet ska in.

#306–#316 är squash-mergade till `jakob-be` och synkade till `main`
(#316 = "Spår A" färgfix, mergad 2026-06-14, tip `8005be92`). Äldre detaljer:
arkivet + `docs/handoff.md`.

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

- [`docs/archive/current-focus-2026-06-12-kvall.md`](archive/current-focus-2026-06-12-kvall.md)
  (kvällsblocket per `54de9b9c`: #314/#315-mergarna, slutlig main-sync för
  operatörens produktions-E2E).
- [`docs/archive/current-focus-2026-06-12-em.md`](archive/current-focus-2026-06-12-em.md)
  (eftermiddagsblocket per `56dc754f`: #310–#313-mergarna, branch-städning,
  första main-synken för produktionstest).
- [`docs/archive/current-focus-2026-06-12-middag.md`](archive/current-focus-2026-06-12-middag.md)
  (middagsblocket per `f642b1a5`: ADR 0055 preview-standardisering,
  hotfix-passet ~13:30, #308–#311).
- [`docs/archive/current-focus-2026-06-12-morgon.md`](archive/current-focus-2026-06-12-morgon.md)
  (morgonblocket per `261f0c63`: B199 v2 — hostad run-historik/artefakter
  live, omladdnings-återställning).
- [`docs/archive/current-focus-2026-06-12-gryning.md`](archive/current-focus-2026-06-12-gryning.md)
  (nattpassblocket per `575af63b`: hostad builder-paritet shippad, 404-tystnad,
  readiness-poll, canvas-rättningar, två cloud-prompter köade).
- [`docs/archive/current-focus-2026-06-12-natt.md`](archive/current-focus-2026-06-12-natt.md)
  (midnattsblocket per `5109cc1f`: B194 live/E2E-bevisad, main-sync klar,
  lane-grind i regel 04, CI-actions v6).
- [`docs/archive/current-focus-2026-06-11-kvall.md`](archive/current-focus-2026-06-11-kvall.md)
  (kvällsblocket per `6d740fcc`: OpenClaw-smartness #296–#303, #269, /kort-regeln).
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
