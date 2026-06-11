# Arkiv: current-focus kvällsblocket 2026-06-11 (~22:55, per `6d740fcc`)

> Arkiverat 2026-06-12 ~00:30 vid midnattsstängningen. Detta är historik —
> verifiera alltid mot git/koden. Aktuell köplan: `docs/current-focus.md`.

## Status (2026-06-11 ~22:55 — kvällspasset: OpenClaw-smartness mergad + /kort-regel + lokal städning)

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
- Versionsläge (då): llm-models **v11**, naming-dictionary **v37**,
  dossier-contract **v4**.

**Dåvarande prioriteringar:** (1) review-kedjan #292 → #304 (levererades
samma natt — se midnattsblocket), (2) main-sync-uppföljning (klar samma
natt), (3) B198 del b, (4) ADR 0052-städ, (5) Token Meter-priser.

Last verified state (då): `6d740fcc` (2026-06-11 ~22:55 UTC+2).
