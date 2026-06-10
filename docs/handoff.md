# Handoff – Sajtbyggaren

**Datum:** 2026-06-10 UTC, steward-auto efter PR #255 — docs(agents): dedupe Cloud VM preview-mode-gotchan i AGENTS.md. Verifierad `main` är `298aeed`.

Nya PRs sedan föregående checkpoint: PR #255 — docs(agents): dedupe Cloud VM
preview-mode-gotchan i AGENTS.md.

## CLOSING-ROUND HANDOFF 2026-06-10 (natt) — ÖVERLÄMNING TILL NÄSTA AGENT

> **Detta är det ENDA auktoritativa blocket. Allt äldre ligger i arkivet —
> verifiera alltid mot git/koden, aldrig mot äldre block.**
>
> **Git-läge:** `origin/jakob-be = 68bbde3`, rent träd, lokal = origin.
> `origin/main = 16278c1`. **Deltat jakob-be→main är MYCKET STORT (15 PRs) —
> main-sync är nästa naturliga leveransfönster, men det är operatörens beslut.
> Pusha aldrig main per slice.** Post-merge-sanity efter hela tåget: governance
> 19/19, rules_sync OK, ruff 0, term-coverage --strict OK, riktade sviter gröna.
> Encoding-skan repo-brett (995 textfiler): inga UTF-8-fel/BOM/mojibake.

### Vad som landade i natt (per tema)

**Synlig section_add (ADR 0038) — kärnloops-grinden STÄNGD:**
- **#240**: `directives.mountedSections` på Project Input + render-seam i
  `render_home`. Skiva 1: `hours` → `hours-summary` renderas INLINE på
  local-service-business-home, position top/bottom från routerns
  "överst"/"längst ner". faq/team behåller egen-route-vägen.
- **#248** (Codex-granskning): intent-gate (bara section_add SKAPAR
  inline-placering; component_add kan högst BEVARA via explicit carry-forward) +
  render-time-allowlist `_INLINE_SECTION_ALLOWLIST` (paritetslåst mot resolverns
  `INLINE_SECTION_*`) + `{company}`-false-positive borta ur placeholder-scan.
- **#245+#249** (UI-halvan + granskningsrunda 2): AddModuleDialog med ärliga
  synlighets-badges ("kan synas på startsidan"/"kan bli egen sida"), EMPIRISKT
  verifierat promptformat (en modul per bygge; "Lägg till <promptNoun>
  <överst|längst ner>." — alla 9 moduler × 2 positioner klassas korrekt som
  section_add; sid-omnämnande i prompten tippar pris/team/garantier till
  route_add och undviks), inaktiva sidzoner utom Startsida ("stöds inte än").
- Honesty-grindar hela vägen: registrerad renderare + grundat innehåll + ej
  dubblett + allowlist; `appliedVisibleEffect` = ärlig fil-diff.

**Refaktor/städ:** #238 (render_helpers — SISTA megafil-slicen på build_site),
#225 (test_viewser_files splittad i 7 temafiler + storleksvakt; test-namn-
paritet 186=186), #246 (`Golden Path` canonical, ADR 0039, naming-dict v28;
begreppskarta; backoffice Golden Path-statusvy).

**Skyddsnät:** #241 (contact-CTA-routes), #242 (followup-versionering, inkl.
"mounted = dossier i selectedDossiers.required"), #243 (golden-path-smoke med
RIKTIGA svenska prompts + exakta statusar build=skipped/quality=ok/route-scan=ok),
#244 (placeholder-scan härdad, multiline-empty-heading, smala engelska
template-mönster), #250 (**auto_prune default OFF i hela API-kedjan** —
#237-granskningens dataförlust-fälla stängd: build()/build_targeted_version/
run_followup_chain defaultar False; --followup trådar args.allow_prune).

**Christopher-lane (inbox helt ikapp):** #239 (branschanpassat sidrutnät),
#247 (canonical capability-sluggar + scaffold-nyans), #251 (`recommendedPages`
exponeras i `/api/discovery-options` — msg-0056 punkt 1 LEVERERAD, se
msg-0058; `recommendedCapabilities` finns INTE i taxonomin → eget
governance-fält om önskat, hör ihop med punkt 2 businessFamily-ankaret).
Resolver-alias för wizardens legacy-sluggar + kontraktstest
(`tests/test_wizard_capability_slugs.py`, `KNOWN_UNMAPPED` medvetet —
`user-auth` hålls ogated per ADR 0035).

**Docs-MCP (agent-uppslagsverk):** hostad MCP på `https://docs.openclaw.ai/mcp`
konfigurerad i `.cursor/mcp.json` (gitignorerad), dokumenterad i
`docs/openclaw-workspace/README.md` — UPPSLAGSVERK för repo-agenter,
**INTE** runtime-yta för produktens OpenClaw-dirigent.

### Lösa trådar (för dig, prioriterat)

1. **OpenClaw 2.0 / agentroller i llm-flödet — AVBLOCKAT.** F1-readiness var
   gated på synlig section_add (nu inne). Plan:
   `docs/heavy-llm-flow/openclaw-2.0-conductor.md` + `openclaw-f1-readiness.md`.
2. **Operatörens manuella klick-checkar** (täcks inte av tester):
   /studio "lägg till en öppettider-sektion överst" på LSB-sajt med riktiga
   öppettider → block efter hero; #228:s Ändra-knapp → steg-hopp;
   kontrastfärg "gör sajten mörkblå"; modul-dialogen (#245/#249) visuellt.
3. **Main-sync-beslut** (operatören) — 15 PR:ar verifierade, bra fönster.
4. **Punkt 2 till Christopher:** businessFamily-ankare (ADR + family-fält i
   discovery-taxonomy) + ev. recommendedCapabilities-fält i samma veva.
5. **section_add skiva 2+:** fler inline-typer/routes/scaffolds (seam +
   allowlists redo; varje ny route trår injektions-seamen själv).
6. **Två färdiga cloud-agent-prompter** (chatlogg 2026-06-09 sen kväll):
   backoffice-grind (governance-register + Idag-vy + playground) och
   Vercel-hosted sandbox-preview (med ärlig 501-gating av python-vägar).
7. **#156 hosted `/live`** — parkerad (säkerhet), arkitektur-referens; görs om
   på färsk bas med auth/rate-limit när runtime-spåret väljs aktivt.
8. **Branch-rester för operatörsbeslut:** `cursor/gap-3a-offer-service-guard`,
   `cursor/dossier-intake-v11-review-895d`, `feat/kor-5-repair-pass` (ingen
   PR, ej bevisat mergade), `cursor/preview-runtime-adapters` (avsiktlig
   snapshot), Christophers stängda `feat/viewser-ui-overhaul`/
   `feat/viewser-router-decision-readiness`.

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

### 2026-06-09 UTC — handoff.md före `79bedef`

**Datum:** 2026-06-10 strax efter midnatt (UTC+2). Verifierad `jakob-be` är `68bbde3`
(docs-bump ovanpå merge-HEAD `79bedef`); `main` är oförändrad `16278c1`.

Nya PRs sedan föregående checkpoint (ALLA mergade till `jakob-be`, ej `main`):
#238, #239, #240, #241, #242, #243, #244, #245, #246, #247, #248, #249, #250,
#251 samt #225 — femton stycken, ett i taget med alla guards + CI gröna per PR.

### 2026-06-10 UTC — handoff.md före `1cc8a92`

**Datum:** 2026-06-09 UTC, steward-auto efter PR #252 — sync(jakob-be->main): merge-taget 2026-06-09/10 - synlig section_add (ADR 0038), golden-path-smoke, auto_prune opt-in, recommendedPages-API m.m. (15 PRs). Verifierad `main` är `1cc8a92`.

Nya PRs sedan föregående checkpoint: PR #252 — sync(jakob-be->main): merge-taget
2026-06-09/10 - synlig section_add (ADR 0038), golden-path-smoke, auto_prune opt-in,
recommendedPages-API m.m. (15 PRs).
