---
description: Jakob arbetar på `jakob-be`, Christopher på `christopher-ui`, `main` är canonical. PR mot `main` när en ny officiell version ska in.
alwaysApply: true
---

# Branch-disciplin

## Grundregel

- **Jakob** jobbar default på arbets-branchen `jakob-be` (backend,
  generation, governance, scripts, runtime, merge-review).
- **Christopher** jobbar default på arbets-branchen `christopher-ui`
  (UI/frontend i `apps/viewser/`, presentationslagret för genererade
  sajter).
- **`main`** är projektets canonical / sanningsbranch. Pushas aldrig med
  `--force`. Direkt-pushes till `main` är undantag, inte standard.
- PR från `jakob-be` eller `christopher-ui` mot `main` öppnas när en ny
  officiell version ska in — typiskt när en sprint, ett fix-batch eller en
  fas är klar och granskad. Ingen schemalagd cadence; det är ett
  operatörs- eller agentbeslut per leveransfönster.
- Efter merge: arbets-branchen synkas till `origin/main` via
  `git fetch origin && git reset --hard origin/main && git push --force-
  with-lease origin <branch>` — inte via en separat sync-PR i motsatt
  riktning.

Remote är `https://github.com/Jakeminator123/sajtbyggaren.git`.

## Standardflöde: commit + push på arbets-branchen

1. Verifiera att aktuell branch är `jakob-be` (Jakob) eller
   `christopher-ui` (Christopher) — `git branch --show-current`.
2. Verifiera att branchen är synkad med sin egen origin
   (`git status` eller `python scripts/focus_check.py`).
3. Stage + commit med atomisk avgränsning (en commit per logiskt steg).
4. Kör de fyra guards (se nedan). Alla ska vara gröna.
5. Vid icke-trivial produkt- eller workflow-diff: låt Scout-agenten göra
   read-only bug review av diffen före push.
6. `git push origin jakob-be` (eller `christopher-ui`).

Detta gäller dokumentation, governance, kod, tester, scaffolds, dossiers
och refaktoriseringar. Om ändringen är stor eller riskabel ska agenten
stanna och be operatören bekräfta riktningen innan commit.

## När en PR mot `main` öppnas

PR från arbets-branchen mot `main` öppnas när:

- En sprint eller fas är klar och ska bli en officiell version.
- En batch fixar har samlats på arbets-branchen och operatören vill ha en
  granskad merge till `main`.
- Operatören uttryckligen ber om PR-flöde för en specifik ändring.

Standard-PR-flödet:

1. `git fetch origin && git status` — säkerställ att arbets-branchen är
   ren och pushad.
2. Verifiera de fyra guards lokalt (se nedan).
3. Öppna PR via GitHub-UI eller `gh pr create --base main --head <branch>`.
4. Vänta på Cursor Bugbot + CI-checks. Granska eventuella fynd; PR ska
   vara `mergeable`, `mergeStateStatus == "CLEAN"`, 0 aktiva
   review-trådar och inga oadresserade HIGH-severity fynd före merge.
5. Operatören eller agenten mergar via squash-merge (standardval).
6. Efter merge: synka arbets-branchen till nytt `origin/main` enligt
   "Post-merge-sync" nedan.

PR-loop-detaljer (Bugbot-iterationer, bekräftelser, nödläge-eskalering)
finns i [`governance/rules/bugbot-pr-loop.md`](bugbot-pr-loop.md).

## Direkt-push till `main`

Direkt-push till `main` är **undantag**, inte standard. Tillåtet bara för:

- Pure docs/governance-bumpar som steward-rollen gör (t.ex.
  `docs/current-focus.md`-bumpar efter merge när inget annat ändras).
- Operatörens egna manuella commits (operatören är alltid sista
  beslutsfattare).
- Steward-auto-bump-arbetsflödet i `.github/workflows/steward-auto-bump.yml`
  som kör post-merge.

För all produktkod, schemas, tester, scripts och packages gäller
PR-flödet ovan.

## Post-merge-sync

Efter en PR har mergats till `main`:

1. `git fetch origin --prune`.
2. På arbets-branchen: `git reset --hard origin/main`.
3. `git push --force-with-lease origin <branch>` — uppdaterar
   `origin/jakob-be` (eller `origin/christopher-ui`) till nya
   `origin/main`-spetsen.

**Pulla aldrig** en redan squash-mergad branch — det skapar dubbletter.
Använd `reset --hard origin/main` i stället. `--force-with-lease` är OK
på de permanenta arbets-branchema eftersom de är solo-ägda enligt
[`governance/rules/branch-scope-ui-ux.md`](branch-scope-ui-ux.md).

## Backup-branches (frivillig)

Backup-branches är ett operatörsverktyg, inte en agent-rutin. Operatören
skapar dem när hen vill ha extra säkerhet före en större operation
(t.ex. före en stor merge eller en riskabel refactor). Agenten skapar
inte backup-branches på eget initiativ — `jakob-be` och `christopher-ui`
är själva permanenta säkerhetsnät via Git-historiken.

Om operatören ber om en backup:

1. Lista befintliga backups: `git branch -a --list "*backup-*"`.
2. Välj nästa nummer: högsta `backup-N` + 1.
3. Skapa: `git branch backup-N <SHA>` (typiskt aktuell HEAD).
4. Pusha: `git push origin backup-N`.

Befintliga backup-branches på origin (idag `backup-11` t.o.m. höga
nummer + tre `*-BRA`/`*-VIKTIG`-suffix) ägs av operatören och ska aldrig
raderas utan explicit operatörsinstruktion.

## Tillfälliga feature-branches

Om en specifik uppgift kräver en tillfällig branch (Cloud-/Grind-agent-
arbete, experiment, dedikerad PR-spår), används namnmönstret:

- `cursor/<kort-syfte-på-svenska-utan-aaoo>` (git hanterar åäö
  inkonsekvent på olika plattformar)
- Exempel: `cursor/marketing-base`, `cursor/dossier-typer-v2`
- Aldrig: `cursor/work`, `cursor/wip`, `cursor/test`, `cursor/temp`

Cleanup efter merge:

1. `git push origin --delete <branchname>` (ta bort på GitHub).
2. `git branch -d <branchname>` (ta bort lokalt).
3. `git fetch origin --prune` (rensa stale referenser).

## Vad agenten aldrig gör utan tillstånd

- Skapar permanenta branches utöver `jakob-be` / `christopher-ui` /
  `backup-N`.
- Arbetar på backup-branches.
- Öppnar PR utan tydlig anledning (en sprint är klar, en officiell
  version ska in, eller operatören har bett om det).
- Tar bort backup-branches.
- Force-pushar till `main`.

## Push-fel

Om `git push origin <branch>` avvisas (non-fast-forward, hooks, eller
annat):

1. Stoppa direkt — ingen automatisk `--force` på `main`. På
   `jakob-be`/`christopher-ui` är `--force-with-lease` OK enligt
   "Post-merge-sync" ovan, men bara när det är post-merge-syncen som är
   anledningen.
2. Kör `git fetch origin && git status` för att förstå läget.
3. Fråga operatör innan rebase, merge eller force-push.

## Parallella agenter

När flera agenter jobbar samtidigt:

### Jakob-agent och Christopher-agent

- Jobbar på sin egen arbets-branch (`jakob-be` respektive
  `christopher-ui`) och rör inte motpartens branch.
- Off-limits-paths för Christopher-agenten är listade i
  [`governance/rules/branch-scope-ui-ux.md`](branch-scope-ui-ux.md).
- Jakob-agenten rör inte `apps/viewser/components/**`,
  `apps/viewser/app/**/*.tsx` eller andra UI-paths utan operatörens OK
  (se `docs/ownership-map.md`).
- Vid undantag: tagga commit-body med `[scope-leak] Approved by
  operator: <motivering>` enligt branch-scope-regeln. Detta är
  engångsundantag, inte permanent norm.

### Scout-agent

Är read-only i alla lägen. Kan granska diffen på vilken som helst
arbets-branch före push och leta efter buggar, scope-läckage, saknade
tester och stale docs. Ändrar inget.

### Steward-agent

Hanterar låg-risk docs/governance/sanity. Kan jobba på:

- Sin egen arbets-branch (`jakob-be` eller `christopher-ui` beroende på
  vem hen agerar åt) för docs som hör till pågående arbete.
- Direkt på `main` för pure docs/governance-bumpar som inte påverkar
  produktkod (se "Direkt-push till `main`" ovan).

Steward får inte röra filer som ligger i scope för en pågående Builder-
sprint. Aktiva scope listas i `docs/known-issues.md` eller
`docs/current-focus.md`.

### Push-race

Två agenter får aldrig pusha samtidigt till `main`. Den lokala agenten
kör `git fetch --prune` och verifierar att remote inte rört sig direkt
före sin push; om remote rörde sig avbryts pushen och operatör beslutar
nästa steg. Aldrig `--force` eller `--force-with-lease` på `main`.

Mellan `jakob-be` och `christopher-ui` finns ingen push-race eftersom
brancherna är solo-ägda.

## Före varje commit (de fyra guards)

Agenten kör i denna ordning:

1. `git branch --show-current` — verifiera rätt branch (`jakob-be`,
   `christopher-ui` eller `main` för Steward-undantag).
2. `python scripts/governance_validate.py`
3. `python scripts/rules_sync.py --check`
4. `python scripts/check_term_coverage.py --strict`
5. `python -m pytest -q`

Alla ska vara gröna. Om någon failar: stoppa, fixa, eller fråga operatören
om något är oklart. Aldrig commit + push på rött.

## Commit-meddelanden

- Commit-titlar på engelska enligt `code-in-english.md`.
- Body på engelska.
- ÅÄÖ skrivs korrekt om de förekommer (aldrig `\u00f6` eller ASCII-
  translit).
- Format: kort imperativ titel + 1-3 raders kropp som förklarar varför,
  inte vad.

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

Guards: governance_validate (18 OK), check_term_coverage --strict OK,
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
