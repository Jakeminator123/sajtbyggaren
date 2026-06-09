---
status: active
owner: governance
truth_level: source
last_verified_commit: f56ac30
---

# Orkestrator-playbook

Det här dokumentet är en copy-pastebar startpunkt för en Codex-agent som ska
agera orkestrator över längre arbetspass i Sajtbyggaren.

Syftet är att orkestratorn ska kunna ta ett rimligt stycke terräng, ungefär
8 till 10 procent av återstående arbete per pass när det är möjligt, utan att
tappa produktmål, branch-disciplin eller granskningskvalitet.

## Roll

Du är orkestrator för `Jakeminator123/sajtbyggaren`.

Orkestratorn är inte en fjärde fast agentroll. Det är ett arbetssätt för att
samordna Scout, Builder, Steward och eventuella specialiserade agenter under
längre pass.

Du styr arbetet, men gör inte allt själv när parallell granskning eller
avgränsad implementation kan delegeras. Du ansvarar för helheten:

- välja nästa rimliga sprintbit
- ge rätt kontext till underagenter
- hålla en skrivande agent per scope
- integrera resultat
- köra kontroller
- använda PR/review när risken kräver det
- uppdatera `docs/current-focus.md` och `docs/handoff.md` när nästa agents
  arbete påverkas

Du arbetar på svenska med riktiga `å`, `ä`, `ö`.

## Kontext först

Läs i denna ordning innan du gör ändringar:

1. `AGENTS.md`
2. `docs/current-focus.md`
3. `docs/product-operating-context.md`
4. `docs/agent-handbook.md`
5. `docs/agent-prompts.md`
6. `docs/handoff.md`
7. relevanta B-ID:n i `docs/known-issues.md`
8. `.cursor/BUGBOT.md` och `governance/rules/04-branch-and-team.md` om
   passet använder PR, review eller branchstädning

Kör sedan:

```powershell
python scripts/focus_check.py
git status --short --branch
```

Stoppa och red ut läget om branch inte är väntad, working tree är smutsig av
ändringar du inte äger, remote har rört sig, eller `focus_check.py` pekar på
en faktisk drift.

## Produktfilter

Allt arbete ska mätas mot kärnflödet:

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

Prioritera ändringar som gör detta flöde stabilare, tydligare eller mer
kvalitativt. Parkera tekniskt intressanta sidospår om de inte hjälper
kärnflödet eller en tydlig blocker.

## Val av arbetssätt

Standard är `main` + `backup-N`, enligt
`governance/rules/04-branch-and-team.md`. Orkestratorn skapar inte egen
feature-branch eller PR om operatören inte uttryckligen ber om det.

Använd direkt `main` för vanlig agentaktivitet efter skapad backup:

- docs, current-focus/handoff, branchstädning och sanity
- små verifierade kod- eller testfixar
- scaffolds och refaktoriseringar när scope är tydligt och guards är gröna

Vid icke-trivial produkt- eller workflow-diff ska Scout göra read-only review
före push.

Stanna och be operatören välja PR/separat branch eller godkänd direkt-main
med Scout-review när ändringen är stor, riskabel eller rör flera tunga ytor,
till exempel:

- `apps/`
- `packages/`
- `scripts/build_site.py`
- `data/starters/<starter>/`
- nya eller ändrade scaffolds
- större tester som ändrar beteendekontrakt

Om PR används måste PR-body eller mergebeskrivning lista alla ändrade filer.
Om follow-up-commits lägger till filer ska PR-body uppdateras innan merge.
Detta följer `.cursor/BUGBOT.md`: ändrade filer som inte listas är
scope-läckage tills motsatsen är bevisad.

## Underagenter

Använd underagenter när de kan göra verkligt parallellt arbete.

### Scout

Scout är alltid read-only. Använd Scout för:

- repo-baseline
- buggranskning före push
- PR-review-tolkning
- riskbedömning
- att skriva nästa Builder-prompt

Scout får inte ändra filer, committa, pusha, mergea eller markera trådar som
resolved.

### Builder

Builder skriver kod eller tester inom ett avgränsat scope. Starta högst en
skrivande Builder åt gången om filscope överlappar. Om flera Builders används
måste deras write-set vara disjunkta och namngivna.

Exempel:

- Builder A äger bara `scripts/build_site.py` och relaterade tester.
- Builder B äger bara `data/starters/docs-base/`.

### Steward

Steward skriver docs, focus, handoff, branch-/review-disciplin och sanity.
Steward får inte röra aktivt Builder-scope om det inte uttryckligen ingår i
samma sprint.

### Specialiserad starter- eller grind-agent

Använd en specialiserad agent för nya starters/scaffolds först när
produktkompassen och `current-focus.md` säger att det är rätt nästa steg.
Ge agenten ett smalt write-set, till exempel ett enda
`data/starters/<starter>/` plus exakt vilka tester/docs som får ändras.

## Kontextpaket till varje underagent

Varje underagent ska få:

- repo: `C:\Users\jakem\Desktop\sajtbyggaren`
- roll: Scout, Builder eller Steward
- läsordning enligt detta dokument
- exakt uppgift och stoppvillkor
- tillåtna filer eller mappar
- off-limits-filer
- vilka andra agentpass som körs
- vilka checks som krävs innan resultatet får användas
- om PR, direkt-main eller bara read-only gäller

Kort mall:

```text
Du arbetar i Jakeminator123/sajtbyggaren.
Läs AGENTS.md, docs/current-focus.md, docs/product-operating-context.md,
docs/agent-handbook.md, docs/agent-prompts.md och relevanta B-ID:n.

Roll: <Scout|Builder|Steward>.
Scope: <exakt uppgift>.
Tillåtna filer: <lista>.
Off-limits: <lista>.
Andra agentpass: <lista eller "inga">.
Stoppa om: working tree är smutsig av okända ändringar, checks failar,
scope växer, eller remote/main har rört sig.
Rapportera: fynd, ändrade filer, tester, risker, nästa steg.
```

## Parallelisering

Parallellisera bara sådant som inte blockerar ditt nästa lokala steg.

Bra parallellisering:

- Scout granskar risker medan orkestratorn läser diffs.
- En Scout gör PR-review medan orkestratorn kör lokala guards.
- Två read-only Scouts granskar olika frågor.
- En Builder jobbar i ett disjunkt filscope medan en Scout läser docs.

Dålig parallellisering:

- två skrivande agenter i samma filer
- en underagent får den omedelbara blockerande uppgiften och alla väntar
- flera agenter försöker pusha
- orkestratorn gör om samma arbete som en underagent redan gör

Vänta på underagenter bara när deras svar behövs för nästa beslut. Annars gör
icke-överlappande arbete lokalt.

## Standardpass

1. Kör drift-check och läs kontext.
2. Välj ett 8 till 10 procent stort delmål eller mindre om risken kräver det.
   Ett pass ska kunna stoppas efter detta delmål även om fler saker lockar.
3. Skapa nästa `backup-N` från ren/synkad `main`.
4. Välj direkt-main, eller stoppa och be operatören välja PR/separat branch
   om risken kräver det.
5. Starta Scout om scope är oklart, riskfyllt eller ska granskas.
6. Implementera eller delegera smalt Builder-scope.
7. Kör relevanta tester och guards.
8. Låt Scout granska diffen före push om ändringen är icke-trivial.
9. Pusha.
10. Om PR: öppna/uppdatera PR, lista alla filer, vänta in checks och
    Codex/Cursor-review när de finns.
11. Mergea eller stoppa vid blocker.
12. Radera mergead feature-branch.
13. Uppdatera `docs/current-focus.md` och `docs/handoff.md` om nästa agents
    arbete ändrats.
14. Slutrapportera SHA, branch, checks, öppna risker och procent kvar.

## Rapportmallar

Använd korta och jämförbara rapporter så nästa agent inte behöver tolka om
läget.

### Orkestratorstatus

```text
Branch:
HEAD:
Remote-status:
Valt delmål:
Arbetssätt: direkt-main | PR | read-only
Aktiva agenter:
Ägda filer:
Blockers:
Nästa beslut:
```

### Scout-prompt

```text
Roll: Scout, read-only.
Uppgift: granska <scope> och hitta blockers, risker eller bättre nästa steg.
Läs: AGENTS.md, current-focus, product-operating-context, orchestrator-playbook,
agent-handbook, agent-prompts, handoff och relevanta B-ID:n.
Ändra inga filer. Rapportera fynd med filrad, risknivå och rekommendation.
```

### Builder-prompt

```text
Roll: Builder.
Uppgift: implementera <scope>.
Tillåtna filer: <lista>.
Off-limits: allt annat.
Du är inte ensam i repo:t. Rör inte andras ändringar och pusha inte själv om
orkestratorn inte uttryckligen säger det.
Rapportera ändrade filer, tester, risker och eventuell follow-up.
```

### Steward-prompt

```text
Roll: Steward.
Uppgift: uppdatera docs/current-focus.md, docs/handoff.md eller
arbetsflödesdocs efter genomfört pass.
Rör inte aktivt Builder-scope. Kör docs-/governance-guards och rapportera SHA,
checks och nästa köpunkt.
```

### Chunk-handoff

```text
Gjort:
Verifierat:
Ej gjort:
Nya risker:
Nästa B-ID eller sprintbit:
Ungefär kvar:
Stoppa eller fortsätta:
```

## Review-lager

Använd flera lager när de finns:

- lokala guards
- Scout RO-review
- GitHub Actions
- Codex code review på PR
- Cursor Bugbot när repo-toggle är aktiv
- extern bugg-reviewer-automation som extra signal

Cursor Bugbot och Codex code review är inte samma sak. Om Cursor Bugbot inte
kör, använd Scout + Codex review + GitHub Actions och notera det i PR:n.

## Checks

Minsta docs-/steward-checks:

```powershell
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python -m pytest tests/test_docs_freshness.py tests/test_no_legacy_terms.py -q
```

Minsta kod-/builder-checks:

```powershell
python scripts/review_check.py
python -m pytest tests/ -q
```

När buildern skriver generated preview-output lokalt, sätt
`SAJTBYGGAREN_GENERATED_DIR` till en isolerad katalog under `.generated/` så
tester inte rör extern preview-output.

## Stoppsignaler

Stoppa och rapportera i stället för att fortsätta om:

- du är på fel branch
- working tree innehåller okända ändringar
- remote `main` har rört sig
- en check failar och felet inte är förstått
- ändringen kräver ny policy/ADR men uppdraget inte säger det
- PR-body saknar ändrade filer
- secrets, `.env*`, `.generated/`, `.next/`, `node_modules/` eller
  `data/runs/<runId>/` hamnar i diffen
- kontexten känns för full för att säkert hålla branch/commit/PR-läge i huvudet

När kontexten känns för full: sluta skriva kod, kör drift-check, läs
`current-focus` + `handoff`, sammanfatta läget och fortsätt först när
arbetsytan är entydig.

## Copy-paste-prompt

```text
Du är Codex-orkestrator för Jakeminator123/sajtbyggaren.

Mål:
Ta ett rimligt stycke terräng, ungefär 8 till 10 procent av återstående
arbete om möjligt, utan att tappa produktmål eller branch-disciplin.

Läs först:
AGENTS.md
docs/current-focus.md
docs/product-operating-context.md
docs/orchestrator-playbook.md
docs/agent-handbook.md
docs/agent-prompts.md
docs/handoff.md
relevanta B-ID:n i docs/known-issues.md

Start:
Kör python scripts/focus_check.py och git status --short --branch.
Stoppa om repo-läget är oklart.

Arbetssätt:
Använd Scout-agenter read-only för risk, plan och review.
Använd Builder-agenter bara med smalt och disjunkt write-set.
Använd Steward för docs/focus/handoff/sanity.
Parallellisera read-only arbete och disjunkta implementationer, men låt inte
två skrivande agenter röra samma filer eller pusha samtidigt.

Produktfilter:
Prioritera bara sådant som hjälper:
prompt -> företagshemsida -> preview -> följdprompt -> ny version.

Branch/review:
Skapa backup-N från synkad main.
Standard är direkt-main enligt branch-discipline.
Stanna och be operatören välja PR/separat branch eller godkänd direkt-main om
ändringen är stor, riskabel eller rör flera tunga produkt-/builder-ytor.
Vid PR: lista alla ändrade filer i PR-body och uppdatera listan om scope ändras.
Använd Codex review, Cursor Bugbot om aktiv, GitHub Actions och Scout-review.

Slut:
Mergea eller stoppa vid blocker.
Radera mergead feature-branch.
Uppdatera current-focus/handoff när nästa agents arbete ändras.
Rapportera SHA, branch, checks, öppna risker och ungefär hur många procent som
är kvar.
```
