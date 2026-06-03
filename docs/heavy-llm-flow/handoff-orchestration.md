# Orchestrerings-handoff — heavy-llm-flow

**Datum:** 2026-06-03 (uppdaterad) · **Bas:** `jakob-be` @ `167ace5` · **Governance:** grön (18/18)

Överlämning så en ny orchestrator-agent kan fortsätta jobba med operatören (Jakob) utan
att läsa hela förra sessionens chatt. Läs även `README.md` + `00`–`04` i denna mapp samt
`docs/current-focus.md`.

## Vad som är mergat i `jakob-be` (heavy-LLM-kedjan)

| Commit | Vad |
|--------|-----|
| `167ace5` | KÖR-1c-copy — rik contentBlocks (story/faq/offer) → synlig branschcopy (#167) |
| `d86b151` | KÖR-7a — read-only Context Assembler (#166) |
| `d1541eb` | KÖR-2 — renderern konsumerar blueprint (#165) |
| `5546905` | KÖR-1c — planning fyller Generation Package-blueprint (#164) |
| `f0aa175` | guardrail: manual/wizard-vägen förstaklass + `heavy-llm-flow-layers`-regel (#163) |
| `fae98f3` | KÖR-1b — briefModel fyller brief-blueprintet (#162) |
| `8e4f7fe` | KÖR-0b state-realign + VercelSandboxRuntime boundary (#161) |
| `4c469a3` `3f210f1` `89530a1` | #160 governance-unblock · #157 KÖR-1a schema · #159 KÖR-6a router |
| `eb68028` · `caf9a71`/`6a8e39b` | #155 KÖR-0 · vercel-sandbox hosting-roadmap + preview-loop-kärna |

**Statusen nu:** Hela "gör-det-synligt"-kedjan är inne. Den deterministiska renderern läser
blueprint som innehållskälla (kor-2), och planning producerar nu rik branschcopy
(kor-1c-copy) som tänder hero/CTA/trust **och** story/faq/tjänster för de fyra baseline-
branscherna (elektriker/frisör/naprapat/keramik). Berikning är gated på svensk
kor-1b-positioning; utan den (legacy/mock) är output byte-identisk = noll regression.
Routern (kor-6a) + Context Assembler (kor-7a) finns som rails för follow-up/patch.

## Nästa kort

Sekvens: `1b ✓ 1c ✓ 2 ✓ 7a ✓ 1c-copy ✓ → 4a → 3a → 3b → 5 → 6b → 7b–d`.
**Rekommenderat nästa:** `kor-4a` (deterministisk Quality Critic, ingen LLM, beror på 1c+2 —
båda inne). Sedan `kor-3a/3b` (section-treatments → visualDirection), `kor-5` (repair),
`kor-6b` (router LLM-fallback), `kor-7b–d` (patch/apply/targeted rebuild).
**Coexistence-OBS:** dispatcha INTE en builder som kör full `pytest` medan operatören har en
Viewser dev-sajt igång — `test_api_prompt_smoke` startar en egen Next.js-dev-server och två
samtidiga floppar (Windows-orphan-issue, se AGENTS.md). Pausa builder-dispatch under preview.

## Orchestrerings-modellen (verifierad denna session)

- **Operatören** godkänner scope/merges; **orchestrator-agenten** (du) babysittar PR:er till
  merge-redo och mergar på operatörens stående OK. "Self-merga aldrig" är *builder*-regeln;
  orchestratorn mergar.
- Builder-agenter körs antingen som (a) Cursor cloud-agenter (operatören klistrar prompten)
  eller (b) bakgrunds-subagenter du startar själv (`Task`, `run_in_background`) som
  bygger → pushar → öppnar PR. Subagenter gör loopen självgående.
- **Cloud-agenter öppnar DRAFT-PR:er** → kör `gh pr ready <n>` innan merge.
- **Babysit-flöde:** verifiera scope (rätt filer, inga off-limits) → `gh pr checks` grön
  (governance ~3 min är sist klar) → validera review-bot-fynd → fixa giltiga i en **temporär
  worktree på PR-grenen** (`git fetch origin pull/<n>/head:pr-<n>` + `git worktree add`),
  pusha → re-CI → `gh pr merge --squash --delete-branch` → `git merge --ff-only
  origin/jakob-be` → städa worktree + lokal branch + `git fetch --prune`.
- **Bevakare (valfri):** bakgrunds-PowerShell som pollar `gh pr list/checks` och skriver
  `ACTIONABLE_GREEN/FAIL` (notify_on_output). Bra för passiv väntan; stäng den när operatören
  jobbar interaktivt. Den auto-mergar inte — den pingar bara.
- **Review-bottar:** codex-connector + Vercel review-bot gav denna session **giltiga** fynd
  (determinism-set, CTA-telefon-ärlighet, appliedVisibleEffect, restaurant-CTA, offer-block,
  runs-dir-cwd) — alla fixade med regressionstest. Validera varje; fixa giltiga, motivera
  false positives (en FAQ-tråd var FP).

## Visible-value-läget + öppen produktfråga

- hero/CTA/trust + story/faq/tjänster är nu branschnära för de fyra baselines (mät via
  dev-sajt: `cd apps/viewser && npm run dev`, svensk prompt per bransch, default `local-next`).
- **Öppen fråga (ej beslutad):** planningModel *författar* inte contentBlocks-copy som
  structured output — copy härleds deterministiskt ur briefen (det dokumenterade
  kor-1c-kontraktet, det som gör mock = real). Att låta modellen skriva copyn direkt =
  runtime-kontraktsbeslut + ny fabriceringsyta → kräver operatörs-OK + ev. ADR. Flaggat.

## Uppskjutet / parkerat

- **kor-6b** — router v1.1 LLM-fallback för ~14 rådgivande P2-heuristikluckor i `classify.py`.
  Jaga dem inte deterministiskt; fallbacken är byggd för dem.
- **KÖR-0G — renderer naming hygiene** (liten docs/namnstäd, INTE egen PR mitt i flödet):
  `renderers.py`/`blueprint_render.py` använder `dossier` som namn på render-input-dicten —
  INTE samma som orchestration-`Dossier` (capability under `packages/.../dossiers/`).
  Coach-bekräftat: namnskuld, ingen bugg, renderas aldrig som kundcopy. Dokumentera +
  döp lokalt till `render_input`/`render_context` senare. Batcha med nästa Steward-pass.
- **Vercel-adapter-härdning** (apps/viewser, live-lane): `resume:false` på `Sandbox.get`/stop
  i `vercel-sandbox-runner.ts`. P2, ej blocker.
- **#156 `/live`** — hostad publik loop, parkerad (P1: oautentiserad publik sandbox-start +
  secrets in i VM + ingen rate-limit). Live-lane, rör/merga ej. (Copy-direktiv-gapet som
  #156:s "följdprompt syns inte"-fynd nämnde är nu stängt av kor-1c-copy.)
- **`SAJTBYGGAREN_EVALS_DIR`** (operatörens lokala `.env`): satt till `data/output/.evals` →
  gör `test_default_evals_dir_is_inside_data_evals_artifacts_mini` röd i full-sviten. För
  helgrön svit: kommentera ut eller `=data/evals/artifacts/mini`. (Worktree-builders ärver
  inte root-`.env` → de var gröna.)
- **Sync `jakob-be → main`** = pending operatörsbeslut.

## Lane-gränser & gör-inte

- **Vårt:** `packages/generation/**`, `governance/**`, `scripts/**`, `docs/heavy-llm-flow/**`.
- **Inte vårt — rör ej:** `apps/viewser/**` (live/Christopher: #156, #158, hosted-sandbox-mvp).
- Merga inte till `main` utan OK; merga inte #156; ingen fri kodagent; inga nya
  canonical-typer utan ADR; inga påhittade claims; committa aldrig `.env*`; force-radera inte
  hosted-sandbox-worktreet.

## Branch/worktree-läge

- **Aktiva worktrees:** huvudträdet (`jakob-be` @ `167ace5`, rent), `sajtbyggaren-live`
  (`feat/live-preview` #156), `sajtbyggaren-hosted-sandbox` (`hosted-sandbox-mvp`,
  ocommittat). Rör inte de två sista.
- **Mergade + raderade denna session:** `feat/kor-1a`/`feat/kor-6a`, kor-0b-realign (#161),
  guardrail (#163), kor-1c (#164), kor-2 (#165), kor-7a (#166), kor-1c-copy (#167).
  (Cursor-footern kan visa stale spök-branches — ladda om fönstret rensar; `git branch` är
  sanningen.)
- **Att se över (EJ mergade — rör ej utan beslut):** `cursor/dossier-intake-v11-review-895d`
  (49 commits, ingen PR), `cursor/dev-env-setup-7245` (#154 closed),
  `cursor/preview-runtime-adapters`. **Lämna alltid** `backup-*` + `christopher-ui`.

## Canvas (operatörsreferens)

Arkitekturkartan ligger på
`~/.cursor/projects/<workspace>/canvases/heavy-llm-flow-arkitektur.canvas.tsx` (öppnas bredvid
chatten; ligger utanför repot, committas inte). Den speglar två-motor-modellen + kör-status.
**Uppdatera när kort mergas:** den ska nu visa kor-1b/1c/2/7a/1c-copy som "inne", `kor-4a`
som "huvudspår nu", och story/faq/tjänster som "branschnära (kor-1c-copy)" i stället för
"mall tills copy-gapet stängs".
