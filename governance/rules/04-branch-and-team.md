---
description: Branchmodell (Jakob på jakob-be, Christopher på christopher, main canonical, christopher-ui fryst), team-/contract-first-workflow, de fyra guards före push, smidig lane-synk med delade löpnummer, och säker push/PR-disciplin.
alwaysApply: true
---

# Branch- och teamdisciplin

Konsoliderar branch-disciplin, Christophers aktiva branch, team-workflow och branch-delen av UI/backend-scope.

## Grundmodell

- **Jakob** jobbar default på `jakob-be` (backend, generation, governance, scripts, runtime, merge-review).
- **Christopher** jobbar default på `christopher` (UI/frontend i `apps/viewser/`, presentationslagret för genererade sajter), skapad med avstamp från `jakob-be`.
- **`main`** är canonical/sanningsbranch.
- `christopher-ui` (och `christopher-ui-backup-*`) är **fryst legacy** med parkerad auth/billing (`NEXT_PUBLIC_AUTH_ENABLED`, default AV) och får inte röras, mergas, rebasas eller raderas utan operatörens uttryckliga OK.
- PR mot `main` öppnas när en officiell version ska in (sprint/fas/fix-batch klar och granskad), inte för varje liten slice.
- Remote: `https://github.com/Jakeminator123/sajtbyggaren.git`.

## Tillfälliga branches

Använd `cursor/<kort-syfte-på-svenska-utan-åäö>` (git hanterar åäö inkonsekvent), t.ex. `cursor/openclaw-f1-readiness`. Aldrig `cursor/work`, `cursor/wip`, `cursor/test`, `cursor/temp`. Cleanup efter merge: `git push origin --delete <branch>`, `git branch -d <branch>`, `git fetch origin --prune`.

## De fyra guards före push

Kör i ordning; alla ska vara gröna. Aldrig commit + push på rött.

1. `git branch --show-current` — verifiera rätt branch.
2. `python scripts/governance_validate.py`
3. `python scripts/rules_sync.py --check`
4. `python scripts/check_term_coverage.py --strict`
5. Pytest (vid kod-/policy-ändring som kan påverka tester) — **riktade tester är default** (operatörsbeslut 2026-06-11): kör de sviter som rör ändrade filer/paket, t.ex. `python -m pytest tests/test_<berörd>*.py -q` eller kärnlanen `python -m pytest -m core -q`. Full svit körs av CI på PR:en (governance-workflowet) och är fortsatt kravet för merge. Full svit lokalt bara vid breda ändringar (flera paket) eller på explicit begäran — och då parallellt: `python -m pytest tests/ -q -n auto` (pytest-xdist, se `docs/testing.md`).

## Push och merge

- Pusha aldrig `main` med `--force`. Direkt-push till `main` är undantag (pure docs/governance-steward-bumpar, operatörens egna commits, steward-auto-bump-workflow).
- På `jakob-be`/`christopher`: pusha bara branchens egna ändringar.
- Om push nekas: stoppa, `git fetch origin && git status`, rapportera. Rebase/merge/force-push inte på impuls — fråga operatören.
- **Post-merge-sync** (efter att din PR mergats): `git fetch origin --prune`, sen på arbets-branchen `git reset --hard origin/<din-synk-bas>` och `git push --force-with-lease origin <branch>`. Din synk-bas är den branch du PR:ar in i: `main` för `jakob-be`, `jakob-be` för `christopher`. **Pulla aldrig** en redan squash-mergad branch. `--force-with-lease` är OK på de solo-ägda arbets-branchema, aldrig på `main`/delad branch. Tankemodell: arbets-branchen är en engångsstege — efter merge är det en `reset` mot synk-basen, inte en rebase-konflikt som ska "lösas". Detaljer: se avsnittet om smidig lane-synk nedan.

## Smidig lane-synk (mindre rebase-smärta)

Syftet är att `christopher`-lanen ska kunna hänga med `jakob-be` utan stora,
sällsynta och smärtsamma rebaser. Tre vanor:

- **Synka ofta, i början av varje pass.** Kör en ren synk mot din synk-bas
  (`origin/jakob-be` för `christopher`) vid passets start utan att vänta på
  klartecken. Klartecken behövs bara när motparten uttryckligen flaggat en
  pågående ändring i en delad fil du just nu redigerar — inte för en ren synk.
  Ju oftare du synkar, desto mindre divergens och desto färre konflikter.
- **Släpp i små, täta PR:ar.** PR:a varje klar slice i stället för att batcha
  en stor leverans. Bryt ut delgrunder till egna PR:ar (som #277/#285) så en
  delad grund landar en gång och inte ackumulerar konflikter i en jätte-PR.
- **Engångsstege.** Efter att din PR mergats är arbets-branchen färdiganvänd:
  `reset --hard` mot synk-basen och bygg vidare. Det är ingen rebase som ska
  "lösas", det är en återställning. Bär du oppushat arbete: rebasa det lilla
  ovanpå färsk synk-bas, inte tvärtom.

## Obligatorisk lane-grind för christopher-lanen (operatörsbeslut 2026-06-12)

Detta avsnitt är MÅSTE-krav (inte vanor) för alla agenter som arbetar på
`christopher`-lanen. Bakgrund: kvällen 2026-06-11 — en oregistrerad term
(`HostedRunStatePointer`) stoppade PR #304 i CI eftersom term-coverage inte
kördes lokalt, och varje merge på `jakob-be` ogiltigförklarade väntande
PR-rebaser. Reglerna stänger båda felklasserna:

1. **MÅSTE auto-synka vid varje passtart.** Kör `git fetch origin --prune`
   och `git reset --hard origin/jakob-be` (utan oppushat arbete) eller rebasa
   det lilla oppushade ovanpå färsk bas — UTAN att vänta på klartecken.
   Ett pass får aldrig börja på en gammal bas.
2. **MÅSTE köra hela grinden före VARJE push på en PR-branch** — inte ett
   urval: `governance_validate.py`, `rules_sync.py --check`,
   `check_term_coverage.py --strict`, ruff, riktade pytest-sviter för
   berörda filer, och `tsc --noEmit` vid viewser-ändringar. En push där
   term-coverage hoppats över räknas som regelbrott, inte som glömska.
3. **MÅSTE registrera nya identifierare i samma commit.** En commit som
   inför en ny canonical-kandidat (klass/typ/policy-begrepp) bär själv
   naming-dictionary-bumpen, med versionsnummer re-deriverat från färskt
   `origin/jakob-be` (aldrig från ett löfte i inbox/handoff).
4. **MÅSTE auto-rebasa öppna PR:ar när basen flyttar sig.** När
   `origin/jakob-be` får nya commits medan en lane-PR är öppen: rebasa/
   basmerga PR-branchen inom samma pass, eller flagga uttryckligen i inbox
   att PR:en är stale och överlämnas. En stackad PR retargetas till
   `jakob-be` OMEDELBART när dess bas-PR mergats.
5. **Fallback (jakob-be-lanens rätt):** en grön-men-stale lane-PR får
   slutföras av jakob-be-lanen via basmerge på PR-branchen (mönstret
   `9774b199`/`57ceec9c`) — enbart mekaniska konfliktlösningar och
   grind-fixar, alltid rapporterat i `docs/agent-inbox.jsonl`.

Motsvarande skyldighet på jakob-be-lanen: små gröna lane-PR:ar reviewas och
mergas SNABBT (kort review-SLA) — att låta dem ligga medan basen flyttar sig
är det som skapar rebase-loopar.

## Delade löpnummer (ADR-nummer och policy-versioner)

Vissa nummer är en delad seriell resurs över båda lanes och är den vanligaste
tysta krockytan: ADR-nummer i `governance/decisions/` och heltals-`version` i
`governance/policies/naming-dictionary.v1.json` och
`governance/policies/llm-models.v1.json`. Protokoll:

- **Lita aldrig på ett lovat nummer.** Ett nummer som utlovats i inbox eller
  handoff kan tas av motparten innan din PR landar (det har hänt: en utlovad
  `naming-dictionary`-version togs av andra lanen samma dag).
- **Re-derivera vid rebase/strax före PR.** Läs alltid nästa lediga nummer från
  färskt `origin/jakob-be` (integrationspunkten), aldrig från ett tidigare
  löfte. Nästa lediga = högsta befintliga + 1.
- **Bumpa sist.** Lägg version-/ADR-bumpen i sista committen före PR så
  race-fönstret blir så litet som möjligt.
- **Först till jakob-be vinner numret.** Den efterföljande lanen omnumrerar sitt
  eget bump mot faktisk HEAD vid sin rebase.

Läs de auktoritativa värdena direkt från integrationsbranchen:

```
git fetch origin --prune
git show origin/jakob-be:governance/policies/naming-dictionary.v1.json
git show origin/jakob-be:governance/policies/llm-models.v1.json
git ls-tree --name-only origin/jakob-be governance/decisions/
```

Läs `version`-fältet överst i policy-JSON:en och ta ADR-filen med högsta
nummer; ditt bump tar nästa heltal ovanför det.

## UI/backend-scope

- Backend/generation/governance/scripts hör normalt till `jakob-be`. Viewser/UI hör normalt till `christopher`.
- **Operatörsgrant (Jakob, 2026-06-08):** jakob-be FÅR fixa verkliga buggar i Christophers lane (`apps/viewser/**`) utan per-bugg-förhandsgodkännande — committat på `jakob-be`, taggat `[scope-leak] Approved by operator: <motivering>` och rapporterat i `docs/agent-inbox.jsonl`. Gäller buggfixar, inte nya features.
- Nya UI-features/UX-beteenden i Christophers lane kräver fortfarande riktat OK per ändring (kärnloops-relevant, liten diff, rapporterad, Christopher informerad). Detaljerad UI/UX-arbetsdisciplin: se [`11-ui-ux-scope.md`](11-ui-ux-scope.md).
- Off-limits backend-yta för UI-lanen (read OK, edit kräver OK): `apps/viewser/app/api/**`, `apps/viewser/lib/**`, `scripts/**`, `backoffice.py`/`backoffice/**`, `packages/generation/**` (utom design-bärande ytor), `governance/policies/*.v1.json` runtime-kontrakt, `governance/schemas/**`, `.github/**`, `.cursor/**`.

## Roller

- **Scout:** read-only audit/granskning av diffen på vilken arbets-branch som helst före push. Ändrar inget.
- **Builder:** implementerar tydligt avgränsad feature/fix.
- **Steward:** låg-risk docs/governance/sanity/status. Får jobba på sin arbets-branch eller direkt på `main` för pure docs/governance-bumpar. Rör inte filer i scope för en pågående Builder-sprint.

## Team- och contract-first-workflow

- Läs `docs/ownership-map.md` innan större ändringar som kan korsa frontend/backend/generation/governance/shared contract.
- Ändra inte shared contract tyst. Dokumentera nya frontend/backend-shapes i `docs/contracts/` innan båda sidor bygger mot dem. Saknas backend bygger frontend mot dokumenterade mockar, inte gissade API-shapes.
- Två agenter ska inte jobba i samma branch eller samma filer samtidigt. Vid fil-/branchkrock: stoppa och rapportera. Två agenter får aldrig pusha samtidigt till `main` (`git fetch --prune` + verifiera före push).
- Scope creep (auth, billing, runtime deploy, starter activation/import, B125) kräver explicit beslut.

## Commit-meddelanden

- Imperativ titel + 1-3 raders kropp som förklarar varför (inte vad). Titel/body på engelska enligt [`01-language-and-reply.md`](01-language-and-reply.md); ÅÄÖ skrivs korrekt om de förekommer (aldrig `\u00f6` eller ASCII-translit).
- **Multi-line på Windows/PowerShell** (ingen bash-heredoc). Primärt: here-string piped till `git commit -F -` (skapar inga disk-filer):

  ```powershell
  $OutputEncoding = [System.Text.Encoding]::UTF8
  @"
  chore: kort imperativ titel

  Body-rad 1 förklarar varför.
  "@ | git commit -F -
  ```

  Fallback om stdin-pipen failar: temp-fil under `$env:LOCALAPPDATA\Temp\sb-commit-msg-<timestamp>.txt` (aldrig `$env:TEMP`, som i agent-shell kan resolvera till `C:\WINDOWS\TEMP`). Skapa aldrig commit-message-filer i repo-roten i samma steg som `git add -A`.
