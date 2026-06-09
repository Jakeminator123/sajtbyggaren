# Handoff – Sajtbyggaren

**Datum:** 2026-06-08 UTC, steward-auto efter PR #212 — sync(jakob-be->main): hero-fix + Bite C + section_add broadening + governance/cleanup batch. Verifierad `main` är `16278c1` (PR #212-squash `b49d1f7` + steward-auto-bump `16278c1` = nuvarande main-HEAD).

Nya PRs sedan föregående checkpoint: PR #195 — feat: gap 1 trust-proof USP seeding +
skiva 1c kor-5 rerender wiring; PR #196 — feat(openclaw): action-bridge --apply (skiva
1b action half); PR #198 — feat(builder): flat-layout-städning + POSIX-tree-kill (B157
nivå 4, kvarvarande städning); PR #199 — feat(viewser): skiva 1b UI half (OpenClaw
decision) + router/copy-honesty + build-orkestrering + scout/a11y; PR #202 —
feat(followup): visual_style restyle (colour + font) + nicer unnamed-business label; PR
#204 — docs(governance): site-mutation-layers rule + theme_directives reconciliation; PR
#200 — feat(planning): drop offer/tagline phrase from offer service cards (gap 3a); PR
#207 — feat(openclaw): materialise visual_style restyle through the apply chain; PR #210
— feat(viewser): wire OpenClaw --apply into /api/prompt follow-ups (skiva 1b action
half); PR #211 — feat(viewser): resizable FloatingChat + module drag-and-drop prep
dialog; PR #212 — sync(jakob-be->main): hero-fix + Bite C + section_add broadening +
governance/cleanup batch.

## CLOSING-ROUND HANDOFF 2026-06-08 (natt) — ÖVERLÄMNING TILL NY ORCHESTRATOR

> **Detta är det ENDA auktoritativa blocket. ALLT nedanför `---` är historik —
> verifiera alltid mot git/koden, aldrig mot äldre block (deras SHA är pre-sync
> och stale).**
>
> **Git-läge (POST-SYNC):** `origin/main = 16278c1` (PR #212 squash `b49d1f7` +
> steward-auto — hela förra batchen är officiell). `origin/jakob-be` ligger
> några commits FÖRE main med en andra-rundas batch (se nedan); rent arbetsträd.
> **Operatören synkar `jakob-be → main` medvetet — pusha aldrig main per slice.**
> Guards gröna (governance 19, rules_sync, term_coverage); full `pytest -q` grön
> (bara väntade skips — `test_api_prompt_smoke`-flaken är åtgärdad, `6c33798`).
>
> **Operatörsgrant (viktigt för dig som ny orchestrator):** jakob-be har stående
> tillstånd att FIXA BUGGAR det ser i Christophers UI-lane (`apps/viewser/**`) —
> committat på jakob-be, `[scope-leak]`-taggat, rapporterat i inboxen. Större
> icke-bugg-feature-/UX-ändringar kräver fortfarande per-ändrings-OK. Källa:
> `governance/rules/branch-discipline.md`.

### Runda 1 (i main via #212): hero-fix + Bite C + section_add + governance/cleanup
- **Hero-rotorsaksfix (`fb9692d`):** "ändra hero-texten" syntes inte — hero-H1
  renderas från blueprint (`positioning.oneLiner`, regenereras varje bygge), inte
  `company.tagline`. Ny `company.heroHeadline`-override (renderaren föredrar den,
  överlever ombygge). Fältkontrakt LÅST i copy-change-skill.
- **Bite C KLAR (`7984fc1`):** `viewer-panel.tsx` driver preview-flaggorna via
  `resolvePreviewRuntimeDescriptor` (`auto`≠`local-next` bevarat). Helt stängd.
- **section_add breddat (`4c6ba67`), MOUNT-ONLY:** nio typer (team/faq/trust/
  reviews + gallery/pricing/hours/map/contact-form). Monterar capability+dossier
  men renderar inte synligt än (`appliedVisibleEffect=false`).
- **preview-runtime descriptor + README, DEP0190 `next`-fix, env-matris, gpt-4o
  default, stale-doc-markeringar, backoffice-cleanup, .cursorignore-unlock.**

### Runda 2 (på jakob-be, ovanför main — väntar nästa sync): buggranskning + docs
- **FloatingChat honesty (`a98a46e`):** `summarizeOpenClawBridge` grindar synlig
  success på `previewShouldRefresh` — en mount-only-montering säger inte längre
  falskt "Jag genomförde ändringen".
- **dev.mjs DEP0190-rest (`35baddb`):** `vercel env pull` shell-fritt. Dispatchern
  helt ren.
- **Smal→stående buggfix-grant (`cccda391`):** se grant-rutan ovan.
- **AddModuleDialog falsk affordance (`dabd503`):** tog bort hero/services/
  cta-banner (omountbara) + ärlig copy om placering/mount-only.
- **Docs/governance-städning (denna commit):** section-add-skill + action-registry
  + current-focus-topp + openclaw-2.0-conductor + glossary alignade till
  mount-only + 9 typer + post-sync-git; Project Input runtime-path klargjord.

### Lösa trådar (för dig, prioriterat)
1. **Sync `jakob-be → main`** (runda-2-batchen) — operatörsbeslut.
2. **Synlig render av monterade section_add-sektioner + page/position-targeting**
   — den största produkthävstången nu (gör mount-only → faktiskt synligt). Hör
   till render-path/Sprint-3B-spåret.
3. **#4 dialog/toast-honesty:** `useFollowupBuild`→`onBuildDone`→studio-toast bär
   inte `appliedVisibleEffect` (FloatingChat gör nu). Signaturändring över 5
   dialoger + page — Christophers UX-slice. (inbox msg-0052)
4. **Remap-signalen** (requestedTarget/remapped) — väntar Christophers `--real-llm`-repro.
5. **#5 production COEP-split** + **#7 bridge-null-diagnostik** — små, noterade (msg-0052).
6. OpenClaw-conductor-slicen (roll-registry runtime, "F1") — scoped, ej startad.
7. **#156 hosted `/live`** — parkerad (säkerhet), rör inte.

## Historik

Allt äldre än toppblocket ovan är flyttat till
[`docs/archive/2026-06/handoff-history-2026-06-09.md`](archive/2026-06/handoff-history-2026-06-09.md)
(arkiv = historik, inte sanningskälla — verifiera mot git). Hela
versionshistoriken finns kvar via `git log --follow docs/handoff.md`.
