# Orchestrerings-handoff — heavy-llm-flow

**Datum:** 2026-06-03 · **Bas:** `jakob-be` @ `89530a1` · **Governance:** grön (18/18)

Överlämning så en ny orchestrator-agent kan fortsätta jobba med operatören (Jakob) utan
att läsa hela förra sessionens chatt. Läs även `README.md` + `00`–`04` i denna mapp.

## Vad som är mergat i `jakob-be`

| Commit | Vad |
|--------|-----|
| `89530a1` | KÖR-6a — deterministisk OpenClaw-router (#159) |
| `3f210f1` | KÖR-1a — blueprint schema skeleton + ADR 0036 (#157) |
| `4c469a3` | governance-unblock: allowlist + reword av heavy-llm-flow-docs (#160) |
| `eb68028` | KÖR-0 state alignment / städning (#155) |
| `caf9a71`, `6a8e39b` | vercel-sandbox hosting-roadmap + preview-loop-kärna |

Grunden för det tunga LLM-flödet (blueprint-kontrakt + deterministisk router) är alltså
inne och governance-grön.

## Orchestrerings-modellen (hur operatör + orchestrator-agent jobbar)

- Operatören godkänner merges och matar kör-prompter till builder-agenter.
  Orchestrator-agenten **babysittar** PR:erna (CI + review-trådar) till merge-redo och
  mergar **på operatörens OK** (`gh pr merge --squash`), aldrig self-merge.
- **Ett kör-kort = ett worktree** (`Desktop\sajtbyggaren-worktrees\<kort>`) +
  `feat/<kort>`-branch + PR mot `jakob-be`. Fil-disjunkta kort körs parallellt.
- **Checks är scope-baserade** (se `04-builder-profil.md`). Governance-grindar:
  `check_term_coverage --strict` + `test_no_legacy_terms`. **Lägg docs via PR, eller kör
  båda grindarna lokalt före direkt-push** — en direkt-push av docs blockade term-coverage
  tidigare; `#160` allowlistar nu heavy-llm-flow-vokabulären och rewordade legacy-exempel.
- **Bevakar-mönster:** bakgrunds-poller på `gh pr checks <n>` (governance-grön) + PR-head-OID
  (fixup landad). Notiser kan lagga några sekunder — verifiera alltid med `gh pr checks`
  innan merge.

## Lane-gränser (viktigt)

- **Vårt:** `packages/generation/**`, `governance/**`, `scripts/**`.
- **Inte vårt — rör ej:** `apps/viewser/**` = live/Christopher-lane. Öppna PR där:
  - **#156** hostad `/live`-loop — parkerad pga riktiga säkerhetsflaggor
    (oautentiserad publik sandbox-start utan rate-limit, secrets i sandbox-env,
    `run-build.sh`-path-bugg, next.config-tracing kan bryta `/api/prompt`). Fixas i
    live-agentens egen slice, inte av oss.
  - **#158** UI-överhalning. Christopher-lane.

## Nästa kort (sekvens enligt README)

`kor-1b → 1c → 2 → 4a → 3a → 3b → 5 → 6b → 7a–d`.
**Rekommenderat nästa:** `kor-1b` (briefModel fyller brief-blueprintet).

## Uppskjutet — router v1 P2-luckor (→ `kor-6b` / v1.1)

Deterministiska routern (#159) passerade sin DoD (klock-exempel A–E + ~45 prompter) och
ai-bug-review-grinden, men review-bottarna (codex + Vercel-VADE) listade ~14 rådgivande
P2-heuristikluckor (de blockerar inte merge). Jaga dem inte deterministiskt —
LLM-fallbacken (`kor-6b`) är byggd just för dem. Kvarvarande kategorier:

- komponent-placering vs route-skapande ("lägg en klocka på sidan")
- create-verb ("skapa en klocka") → component_add
- bar "ny/nytt" → copy-edit felklassad som ny route
- preserve-villkor i samma klausul ("...utan att ändra texten") tappar editen
- koordinerade listor ("karta och kontaktformulär") tappar andra objektet
- bart remove-verb utan mål → bör be om förtydligande
- ren fråga med stil-ord ("vad betyder premium?") → bör inte trigga build
- multi-intent med referens tappar referens-/plan-only-skydd
- referens + placering tappar parsat target
- "sista sektionen" (negativ ordinal) resolvas inte
- nordiska TLD:er (.dk/.no/.fi) känns inte igen som referens
- negerade stil-klausuler ("men inte mörk") tappar villkoret
- frågeformulerad fix ("kan du fixa det där?") → svaras som ren fråga

(De ligger även som olösta P2-trådar på #159.)

## Branch/worktree-läge

- **Aktiva worktrees:** huvudträdet (`jakob-be`), `sajtbyggaren-live`
  (`feat/live-preview`, annan agent), `sajtbyggaren-hosted-sandbox`
  (`hosted-sandbox-mvp`, annan agent). Rör inte de två sista.
- **Raderade (mergade):** `chore/termcov-heavy-llm-flow`, `feat/kor-1a`, `feat/kor-6a`.
- **Att se över (operatörsbeslut):** `cursor/kor-0-state-alignment-90e4` (#155 mergad),
  äldre `cursor/preview-runtime-*`, `cursor/dossier-intake-*`, `cursor/dev-env-setup-*`.
  **Rör aldrig** `backup-*` (säkerhetskopior) eller `christopher-ui`.
- **Sync `jakob-be → main`** = pending operatörsbeslut (så når arbetet canonical/publik linje).

## Gör inte

- Merga inte till `main` utan operatörens OK.
- Rör inte `apps/viewser/**`, #156 eller #158 (live/Christopher-lane).
- Bygg inte fri kodagent; inga nya canonical-typer utan ADR; inga påhittade claims.
- Committa aldrig `.env*`; skriv aldrig ut secrets.
