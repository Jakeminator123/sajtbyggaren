# Lane C — Backend-megafil-refaktorPLAN (Scout/Steward, cloud)

> **FÖRBEREDD LANE — starta manuellt.** Detta är en **plan, ingen kod**.
> Backend-megafilerna är motorhjärtat och städas inte spontant. Klistra in hela
> meddelandet som första prompt i en Cursor Cloud Agent. Pushar till
> `origin/jakob-be`. Disjunkt write-set mot lane A (docs) och B (UI): denna lane
> rör BARA en ny `docs/`-planfil.

---

Du arbetar i `Jakeminator123/sajtbyggaren` på branch **`jakob-be`**.

Setup (Ubuntu cloud-VM) — **egen feature-branch så lanes kan köra parallellt**:
```bash
git switch jakob-be && git pull origin jakob-be
git switch -c cursor/lane-c-refactor-plan
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Roll:** Scout/Steward (read-only mot kod). **Scope:** skapa EN ny planfil
`docs/refactor/megafiles-plan.md`. **Ändra ingen kod, inga tester.**

Läs (read-only): `AGENTS.md`, `docs/current-focus.md`, `docs/handoff.md`,
`docs/ownership-map.md`, `docs/orchestrator-playbook.md`,
`packages/generation/build/renderers.py` (5003 rader),
`scripts/build_site.py` (4681 rader),
`scripts/prompt_to_project_input.py` (3385 rader), samt deras direkta
importörer/tester.

## Leverans: `docs/refactor/megafiles-plan.md`
Planen ska för var och en av de tre filerna innehålla:
1. Karta över ansvarsområden i filen (vilka grupper av funktioner/klasser hör
   ihop) och vilka som redan har naturliga sömmar.
2. **Beroenden ut/in** — vad importerar filen, vad importeras från den, och
   vilka repo-boundaries (`packages/generation/`-lager) som måste respekteras.
3. **Behavior-preserving slices** — en ordnad lista med mycket små,
   självständigt mergebara extraktioner. **`renderers.py` först**, i de minsta
   slices som går. Varje slice: vad flyttas, vart, vilka tester bevisar paritet.
4. **Testtäckning** — vilka befintliga tester skyddar beteendet idag, var det
   finns luckor som bör täppas FÖRE en slice.
5. **Stopp-/grind-regler** — refaktor får inte starta förrän synlig
   `section_add`-render / följdprompt-loopen är stabil (produktbevis först).
   Notera explicit den ordningsregeln.

Planen föreslår, den utför inte. Ingen slice får köras i denna lane.

## Off-limits
All kod (`packages/**`, `scripts/**`, `apps/**`), alla tester. Bara den nya
docs-filen. Öppna ingen PR.

## Verifiering (gröna före push)
```bash
python scripts/governance_validate.py
python scripts/check_term_coverage.py --strict
python -m pytest tests/test_docs_freshness.py tests/test_no_legacy_terms.py -q
```

## Stoppa om
Du frestas ändra kod, term-coverage flaggar nya begrepp i planen (skriv om utan
versaler-i-backticks då), eller `origin/jakob-be` har rört sig.

## Leverans (parallell-säker — egen branch + PR mot `jakob-be`)
```bash
git push -u origin cursor/lane-c-refactor-plan
gh pr create --base jakob-be --head cursor/lane-c-refactor-plan \
  --title "docs(refactor): megafil-refaktorplan (lane C, plan only)" \
  --body "<sammanfattning + 'ingen kod rörd, en ny docs-planfil'>"
```
PR-base är `jakob-be`. Operatören mergar.

## Slutrapport (exakt format)
```
PR öppnad: cursor/lane-c-refactor-plan -> jakob-be (#<nr>). Ny planfil:
docs/refactor/megafiles-plan.md. Ingen kod rörd. Guards gröna: governance 19/19,
term-coverage --strict OK, docs-tester gröna. Klar — vänta operatörens nästa instruktion.
```
