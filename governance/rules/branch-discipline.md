---
description: Jobba på main med numrerad backup-branch före varje sprint. PR används inte som standard.
alwaysApply: true
---

# Branch-disciplin

## Grundregel

Agenten jobbar på `main` genom hela sprinten om operatören inte uttryckligen
säger något annat. **Standardflödet är backup-branch först, därefter commit +
push direkt mot `origin/main`**. Remote är
`https://github.com/Jakeminator123/sajtbyggaren.git`.

Backup-branchen är bara en återställningspunkt. Den är inte en arbetsbranch,
ska inte checkas ut för implementation och ska inte få en PR.

## Sprintstart: skapa backup-branch

Inför varje ny sprintrunda skapar agenten en numrerad backup-branch från ren
och synkad `main`:

1. Verifiera att aktuell branch är `main` (`git branch --show-current`).
2. Verifiera att `main` är synkad med `origin/main` (`git status` eller
   `python scripts/focus_check.py`).
3. Lista befintliga backups med `git branch -a --list "*backup-*"`.
4. Välj nästa nummer: högsta befintliga `backup-N` + 1.
5. Skapa backupen från nuvarande `main`: `git branch backup-N`.
6. Pusha backupen när operatören vill ha fjärrbackup:
   `git push origin backup-N`.
7. Stanna kvar på `main` och gör sprintarbetet där.

Exempel: om `backup-1` till `backup-5` finns blir nästa `backup-6`.

## Standardflöde: commit + push på main

För all vanlig agent-aktivitet pushas ändringen direkt till `main`:

1. Verifiera att aktuell branch är `main`.
2. Verifiera att sprintens backup-branch finns.
3. Stage + commit med atomisk avgränsning (en commit per logiskt steg).
4. Kör de fyra guards (se nedan). Alla ska vara gröna.
5. Vid icke-trivial produkt- eller workflow-diff: låt Scout-agenten göra
   read-only bug review av diffen före push.
6. `git push origin main`.

Detta gäller dokumentation, governance, kod, tester, scaffolds, dossiers och
refaktoriseringar. Om ändringen är stor eller riskabel ska agenten stanna och
be operatören bekräfta riktningen innan commit, men den skapar inte automatiskt
en feature-branch eller PR.

Scout-agenten ersätter Bugbot som pre-push-granskare i direkt-main-flödet.
Scout får inte fixa fynden själv, utan rapporterar blocker, risk,
nice-to-have eller falskt fynd. Builder- eller Steward-agenten gör sedan
eventuell fix inom samma scope.

## När agenten skapar annan branch eller PR

Endast när operatören uttryckligen säger något av:

- "öppna en PR för X"
- "gör detta på separat arbetsbranch"
- "byt till branch Y"

Om instruktionen är otydlig: fråga operatör innan branch eller PR skapas.

## Vad agenten aldrig gör utan tillstånd

- Skapar feature-branches "för säkerhets skull" eller "för att vara försiktig".
- Arbetar på backup-branches.
- Öppnar PR utan uttryckligt uppdrag.
- Tar bort backup-branches.
- Force-pushar till `main` (`git push --force` eller liknande).

## Push-fel

Om `git push origin main` avvisas (non-fast-forward, hooks, eller annat):

1. Stoppa direkt - ingen automatisk `--force` eller `--force-with-lease`.
2. Kör `git fetch origin && git status` för att förstå läget.
3. Fråga operatör innan rebase, merge eller force-push.

## Naming när arbetsbranch ändå behövs

- Format: `cursor/<kort-syfte-pa-svenska-utan-aaoo>` (git hanterar åäö inkonsekvent på olika plattformar)
- Exempel: `cursor/marketing-base`, `cursor/dossier-typer-v2`
- Aldrig: `cursor/work`, `cursor/wip`, `cursor/test`, `cursor/temp`

## Cleanup-rutin (när arbetsbranch ändå har använts)

Efter merge till `main`:

1. `git push origin --delete <branchname>` (ta bort på GitHub)
2. `git branch -d <branchname>` (ta bort lokalt)
3. `git fetch origin --prune` (rensa stale referenser)

Mål: `git branch -a` ska bara visa `main`, `origin/main` och bevarade
`backup-N`-branches när inget pågår.

## Parallella agenter

När flera agenter jobbar samtidigt mot samma repo (typiskt: en lokal agent på `main` plus en cloud-/feature-agent på en egen branch), gäller en strikt rollfördelning som hindrar att två agenter rör samma filer.

### Mainline-steward

Stannar på `main` och pushar direkt till `origin/main`, men bara för låg-risk-arbete:

- docs, governance-text och agent/reviewer-checklists
- lokal branch-cleanup (`git branch -d`, `git fetch --prune`)
- sanity-rapporter (kör de fyra guards + verifiera artefakter)
- små verifierade fixar där alla fyra guards är gröna före push

Mainline-steward får inte röra filer som ligger i scope för en pågående feature-/grind-agent.

### Scout-agent

Är read-only i alla lägen. När Builder- eller Steward-agenten jobbar direkt
på `main` kan Scout-agenten granska diffen före push och leta efter buggar,
scope-läckage, saknade tester och stale docs. Scout-agenten ändrar inget.

### Builder-agent

Jobbar normalt direkt på `main` efter att sprintens backup-branch har skapats.
Pushar till `origin/main` först efter gröna guards och operatörens godkännande
om arbetet är stort eller riskabelt. Skapar inte PR om operatören inte ber om
det uttryckligen.

### Scope-läckage förebyggs så här

1. Före varje main-commit läser mainline-steward `docs/known-issues.md` och senaste `docs/handoff.md` för att se vilka B-IDs eller sprint-spår som är aktiva. De filer som ett aktivt spår räknar upp som scope är off-limits för andra agenter tills Builder-agenten är klar.
2. Om mainline-steward upptäcker att en städning kräver att den rör en off-limits-fil: stoppa, rapportera till operatören, och låt Builder-agenten ta ändringen i samma sprint i stället.
3. Operatören kan när som helst nominera en specifik fil-lista som off-limits för en pågående uppgift; den listan har företräde över det här regelverket.

### Push-race

Två agenter får aldrig pusha samtidigt till `main`. Den lokala agenten kör `git fetch --prune` och verifierar `main == origin/main` direkt före sin push; om remote rörde sig mellan fetch och push avbryts pushen och operatör beslutar nästa steg. Aldrig `--force` eller `--force-with-lease` på `main`.

## Före varje commit (de fyra guards)

Agenten kör i denna ordning:

1. `git branch --show-current` - verifiera `main`
2. `python scripts/governance_validate.py`
3. `python scripts/rules_sync.py --check`
4. `python scripts/check_term_coverage.py --strict`
5. `python -m pytest -q`

Alla ska vara gröna. Om någon failar: stoppa, fixa, eller fråga operatören om något är oklart. Aldrig commit + push på rött.

## Commit-meddelanden

- Commit-titlar på engelska enligt `code-in-english.md`
- Body på engelska
- ÅÄÖ skrivs korrekt om de förekommer (aldrig `\u00f6` eller ASCII-translit)
- Format: kort imperativ titel + 1-3 raders kropp som förklarar varför, inte vad

### Multi-line commit-meddelanden på Windows/PowerShell

PowerShell saknar bash-style heredoc (`"$(cat <<'EOF' ... EOF)"`). Försök
att passa heredoc till `git commit -m` direkt på Windows ger
`Missing file specification after redirection operator`.

#### Primary: here-string piped till `git commit -F -` (rekommenderas)

Skapar **inga disk-filer**; commit-meddelandet existerar bara i shell-
pipen. Cursor- och Codex-IDE:s agent-aktivitetspanel börjar inte tracka
temporära artefakter, och repo-review-verktyg får inga false-positives:

```powershell
@"
chore: kort imperativ titel

Body-rad 1 förklarar varför.
Body-rad 2 listar ändrade filer eller kontext.

Guards: governance_validate (17 OK), check_term_coverage --strict OK,
pytest test_docs_freshness + test_no_legacy_terms (5 passed).
"@ | git commit -F -
```

Säkerställ UTF-8-encoding om commit-meddelandet innehåller `å`, `ä`, `ö`
(annars kan `git log` visa `\u00f6`):

```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
```

#### Fallback: temp-fil (om here-string failar i din shell-context)

Använd bara om stdin-pipen inte fungerar (t.ex. CI med restriktiv
PowerShell-profil eller wrapper-script som blockerar stdin).

1. Skriv meddelandet till `$env:LOCALAPPDATA\Temp\sb-commit-msg-<yyyyMMddHHmmss>.txt`
   (utanför repo, alltid user-temp). Använd unik tidsstämpel-suffix per commit.
2. `git commit -F $env:LOCALAPPDATA\Temp\sb-commit-msg-<yyyyMMddHHmmss>.txt`.
3. `Remove-Item $env:LOCALAPPDATA\Temp\sb-commit-msg-<yyyyMMddHHmmss>.txt`
   (städ; men även om du glömmer ligger filen utanför repo).

> **Gotcha:** Använd **inte** `$env:TEMP` i agent-shell. Cursor-/Codex-
> agenter kör ofta sin PowerShell i elevated/system-kontext där
> `$env:TEMP` resolveras till `C:\WINDOWS\TEMP` i stället för operatörens
> user-temp `C:\Users\<user>\AppData\Local\Temp`. Två separata problem:
> (a) en stale `sb-commit-msg.txt` i system-temp från tidigare cloud-agent
> kan plockas upp tyst och `git commit -F` använder *fel* meddelande,
> (b) agenten saknar i regel write-access till `C:\WINDOWS\TEMP` så städ
> failar. `$env:LOCALAPPDATA\Temp` är alltid user-temp oavsett shellets
> security-context. Verifierat fall: commit `840e73f` (2026-05-19) fick
> en helt orelaterad cached message — Steward-bumpens diff var korrekt
> men message-fältet visade `feat(discovery): align Viewser overlay
> with taxonomy`. Erratan landade i `ce1b137`.

Skapa **aldrig** commit-message-filer som `.commit-msg.tmp` i repo-roten
i samma steg som `git add -A`. Race-villkoret är: filen finns på disk när
`git add -A` körs, så den hamnar i index trots att du tänkt radera den
direkt efter commit. `.gitignore` fångar nya temporära mönster
(`.tmp-*`, `.tmp.*`, `.commit-msg.tmp`), men prevention via here-string
(eller `$env:LOCALAPPDATA\Temp` som fallback) är säkrare än att lita på
ignore-mönstret.
