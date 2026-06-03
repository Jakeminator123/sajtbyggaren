# Orchestrerings-handoff — heavy-llm-flow

**Datum:** 2026-06-03 (uppdaterad) · **Bas:** `jakob-be` @ `1461945` · **Governance:** grön (18/18)

Överlämning så en ny orchestrator-agent kan fortsätta jobba med operatören (Jakob) utan
att läsa hela förra sessionens chatt. Läs även `README.md` + `00`–`04` i denna mapp.

## Vad som är mergat i `jakob-be`

| Commit | Vad |
|--------|-----|
| `1461945` | chore: ignorera lokala junk-filer (`*.code-workspace`, `*.lnk`) |
| `fa943ac` | denna handoff |
| `89530a1` | KÖR-6a — deterministisk router (#159) |
| `3f210f1` | KÖR-1a — blueprint schema skeleton + ADR 0036 (#157) |
| `4c469a3` | governance-unblock (#160) |
| `eb68028` | KÖR-0 state alignment / städning (#155) |
| `caf9a71`, `6a8e39b` | vercel-sandbox hosting-roadmap + preview-loop-kärna |

Grunden för det tunga LLM-flödet (blueprint-kontrakt + deterministisk router) är inne
och governance-grön.

## Orchestrerings-modellen (hur operatör + orchestrator-agent jobbar)

- Operatören godkänner merges och matar kör-prompter till builder-agenter.
  Orchestrator-agenten **babysittar** PR:erna (CI + review-trådar) till merge-redo och
  mergar **på operatörens OK** (`gh pr merge --squash`), aldrig self-merge.
- **Ett kör-kort = ett worktree** (`Desktop\sajtbyggaren-worktrees\<kort>`) +
  `feat/<kort>`-branch + PR mot `jakob-be`. Fil-disjunkta kort körs parallellt.
- **Checks är scope-baserade** (`04-builder-profil.md`). Governance-grindar:
  `check_term_coverage --strict` + `test_no_legacy_terms`. **Lägg docs via PR, eller kör
  båda grindarna lokalt före direkt-push** — en direkt-push av docs blockade term-coverage
  tidigare; #160 allowlistar nu heavy-llm-flow-vokabulären.
- **Bevakar-mönster:** bakgrunds-poller på `gh pr checks <n>` (governance-grön) + PR-head.
  Notiser kan lagga några sekunder — verifiera alltid med `gh pr checks` innan merge.
- **Review-bottar:** två bottar kommenterar PR-rader (codex-connector + Vercels review-bot).
  Validera fynden — agera på giltiga, ignorera false positives, jaga inte en oändlig
  P2-ström på deterministisk kod.

## Nästa kort (sekvens enligt README)

`kor-1b → 1c → 2 → 4a → 3a → 3b → 5 → 6b → 7a–d`.
**Rekommenderat nästa:** `kor-1b` (briefModel fyller brief-blueprintet).

## Uppskjutet — router v1 P2-luckor (→ `kor-6b` / v1.1)

Deterministiska routern (#159) passerade sin DoD + ai-bug-review, men review-bottarna
listade ~14 rådgivande P2-heuristikluckor (de blockerar inte merge). Jaga dem inte
deterministiskt — LLM-fallbacken (`kor-6b`) är byggd just för dem. Kvarvarande:
komponent-vs-route ("klocka på sidan"), create-verb→component_add, bar "ny/nytt",
preserve i samma klausul, koordinerade listor, bart remove utan mål, fråga-med-stilord,
multi-intent-referensskydd, referens+placering, "sista sektionen", nordiska TLD:er,
negerade stil-klausuler, frågeformulerad fix. (Ligger som olösta P2-trådar på #159.)

## Vercel Sandbox — tre spår, håll isär

1. **Runtime-adaptern** (`apps/viewser/lib/vercel-sandbox-runner.ts` + `PreviewRuntime`,
   redan på jakob-be): sund ~8/10, behåll. Kör en redan-byggd sajt; `@vercel/sandbox`
   bara i app-lagret (ADR 0030/0033). Känd P2-härdning: `resume:false` på stop/get.
2. **#156 hostad `/live`** (öppen PR, live-lane): bygg vidare — merga inte, radera inte.
   Bevisade hostad prompt→sandbox→preview (~75 s). Riktiga blockers = **säkerhet**
   (oautentiserad publik start, secrets som env in i VM:en, ingen rate-limit, 12h-token)
   + tracing-excludes-regressionsrisk på befintliga routes. Bot-fynd: Vercels review-bots
   5 förslag är giltiga härdningar (status-signatur, fel-state, `resume:false`, race);
   GPT:s "run-build.sh kan aldrig starta" är en **false positive** (sandbox-cwd är
   `/vercel/sandbox`, så relativ write == absolut exec; live-verifierat). "Följdprompt
   syns inte" = heavy-LLM:s copy-direktiv-gap (kor-1b→2 fixar det gratis), inte wiringen.
3. **hosted-sandbox-mvp** (worktree, 7 ocommittade filer): tredje konkurrerande WIP-spår
   mot #156 — konvergensbeslut behövs (live-lane). Force-radera worktreet förlorar arbetet.

## Lane-gränser

- **Vårt:** `packages/generation/**`, `governance/**`, `scripts/**`, `docs/heavy-llm-flow/**`.
- **Inte vårt — rör ej:** `apps/viewser/**` = live/Christopher-lane (#156 `/live`, #158
  UI-överhalning, hosted-sandbox-mvp). Säkerhet/hosted/auth väntar tills operatören
  uttryckligen väljer det som scope (produktkompassen).

## Branch/worktree-läge

- **Aktiva worktrees:** huvudträdet (`jakob-be`), `sajtbyggaren-live`
  (`feat/live-preview` #156), `sajtbyggaren-hosted-sandbox` (`hosted-sandbox-mvp`,
  7 ocommittade). Rör inte de två sista.
- **Raderade mergade branches:** `chore/termcov-heavy-llm-flow`, `feat/kor-1a`,
  `feat/kor-6a`, `cursor/kor-0-state-alignment-90e4` (#155),
  `cursor/preview-runtime-bite-b-di` (#140).
- **Att se över (EJ mergade — rör ej utan beslut):** `cursor/dev-env-setup-7245`
  (#154 closed, troligen ersatt av #151), `cursor/dossier-intake-v11-review-895d`
  (49 commits, ingen PR), `cursor/preview-runtime-adapters` (1 commit + 6-dagars tom
  stash). **Lämna alltid** `backup-*` (säkerhetskopior) och `christopher-ui`.
- **Sync `jakob-be → main`** = pending operatörsbeslut (så når arbetet canonical linje).

## Gör inte

- Merga inte till `main` utan operatörens OK; merga inte #156 (säkerhet kvar).
- Rör inte `apps/viewser/**`, #156/#158 eller hosted-sandbox-mvp (live/Christopher-lane).
- Bygg inte fri kodagent; inga nya canonical-typer utan ADR; inga påhittade claims.
- Committa aldrig `.env*`; skriv aldrig ut secrets.
- Force-radera inte hosted-sandbox-worktreet utan beslut (7 ocommittade filer).
