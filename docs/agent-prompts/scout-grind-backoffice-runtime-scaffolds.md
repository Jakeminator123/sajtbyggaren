# Scout-prompt: Backoffice runtime-scaffolds-diagnostik stale

## Roll och mål

Du är en **read-only Scout-agent**. Du gör inga kod- eller doc-ändringar. Ditt enda mål är att producera **EN gedigen Builder-prompt** som en cloud-agent (grind-mode) kan klistra in och köra autonomt mot en egen branch som PR:as till `jakob-be`.

## Bakgrund

Coachens analys 2026-05-28 ~01:00 hittade en stale-diagnostik i Backoffice. Backoffice säger att runtime-scaffolds bara är `local-service-business` + `ecommerce-lite` (2 stycken), men resolvern har **6** runtime-aktiva scaffolds: lägg till `restaurant-hospitality`, `clinic-healthcare`, `professional-services`, `agency-studio` (de tre senare landade efter Path B fas 1+2+3a som är klar enligt `docs/section-design-treatments-scout.md`).

Det är inte en runtime-bug — sajterna byggs korrekt — men det är en **operatörs-förvirrings-bug**. Backoffice-diagnostiken visar fel bild av vad som är aktivt. Risk: framtida agent ser "bara 2 scaffolds aktiva" och tror att Path B-arbetet är ogjort.

## Pre-flight (läs i denna ordning)

1. `AGENTS.md` — projekt-kontekst, env-setup, kommando-konventioner.
2. `docs/current-focus.md` — verifiera att uppgiften fortfarande är aktuell. Om någon har fixat den sedan denna prompt skrevs (kolla senaste commits + `docs/known-issues.md`), avbryt och rapportera "redan löst".
3. `docs/known-issues.md` — sök efter "Backoffice" och "runtime-scaffolds" för ev. bug-ID.
4. `packages/generation/discovery/resolve.py` — hitta `_RUNTIME_SCAFFOLD_HINTS`-konstanten. Detta är **den auktoritativa listan** över runtime-aktiva scaffolds. Räkna entries.
5. `backoffice.py` + `backoffice/`-mappen (Streamlit-modulen) — sök efter `local-service-business` eller `ecommerce-lite` i klartext. Det är där den hardcodade staletexten lever. Notera **exakt fil + radnummer**.
6. `governance/policies/` — kolla om någon policy listar runtime-scaffolds explicit (kan vara samma stale-data där också).
7. `tests/test_backoffice_*.py` — kolla om något test cementerar den stale-listan.

## Verifiera innan prompt skrivs

- Är felet fortfarande där? (Kanske fixat sedan coachens analys.) Kör `rg "local-service-business" backoffice/ backoffice.py` + `rg "_RUNTIME_SCAFFOLD_HINTS" packages/`. Om listan i Backoffice redan matchar resolvern → avbryt + rapportera "no-op".
- Vilka scaffolds finns i `_RUNTIME_SCAFFOLD_HINTS` JUST NU? Lista dem med radnummer.
- Vilka scaffolds finns i Backoffice-diagnostiken JUST NU? Lista dem med fil + radnummer.

## Vad cloud-agent-prompten ska innehålla

Produera EN markdown-formatterad prompt som täcker följande. Kalla resultat-filen `_CLOUD-AGENT-PROMPT-backoffice-scaffolds.md` i scout-rapportens slut (eller skriv direkt som chat-output).

### Cloud-agent-prompten ska säga

1. **Roll:** "Du är en Builder-agent i grind-mode på Cloud Agent VM."
2. **Branch-strategi:**
   - Skapa egen branch från `jakob-be`: `git fetch origin && git checkout -b cursor/grind-backoffice-runtime-scaffolds origin/jakob-be`.
   - PR:a mot `jakob-be` (INTE main). Operatör mergear vid uppvaknande.
3. **Off-limits-paths:**
   - `apps/viewser/components/**` (Christophers lane).
   - `packages/generation/discovery/resolve.py` om det inte är ren read-only verifiering.
   - `governance/decisions/**` (ingen ny ADR krävs för diagnostik-bump).
4. **Allowed paths:**
   - `backoffice.py` + relevant `backoffice/`-fil (specifik per scout-fynd).
   - Eventuell ny test-fil `tests/test_backoffice_runtime_scaffolds.py`.
   - `docs/known-issues.md` (lägg till bug-ID om scout föreslår det, eller stäng existerande).
5. **Acceptance criteria:**
   - Backoffice-diagnostiken läser dynamiskt från `_RUNTIME_SCAFFOLD_HINTS` i `resolve.py` (importera + iterera) ELLER har en lista som matchar resolverns 6 scaffolds exakt. Scout föreslår vilken approach som är bäst givet kod-strukturen.
   - Regression-test: assertion att `set(backoffice_scaffolds) == set(resolve._RUNTIME_SCAFFOLD_HINTS.keys())` så framtida drift fångas.
6. **Pre-push-guards (alla MÅSTE vara gröna):**
   - `python scripts/governance_validate.py`
   - `python scripts/rules_sync.py --check`
   - `python scripts/check_term_coverage.py --strict`
   - `python -m ruff check .`
   - `python -m pytest tests/test_backoffice_*.py -q` + det nya testet
   - `python scripts/sprintvakt_check.py`
7. **Commit-format:**
   - `fix(backoffice): close <bug-id> — runtime-scaffolds-diagnostik dynamisk från resolver`
   - Body: kort förklaring av staleness + vad som ändras + att Path B fas 1+2+3a är runtime-aktiv.
8. **PR-format mot `jakob-be`:**
   - Title: `fix(backoffice): close <bug-id> — runtime-scaffolds-diagnostik dynamisk från resolver`
   - Body: scope-rad ("rör BARA `backoffice/`-modulen + 1 ny test"), sammanfattning, BugBot-self-review checklist (5-6 punkter).
9. **Stop-villkor:**
   - Om grund-strukturen kräver mer än 1 ny fil ändras OCH 1 ny test → stoppa och rapportera (då kräver det operator-OK).
   - Om `_RUNTIME_SCAFFOLD_HINTS` är borta från `resolve.py` (refactor:ad) → stoppa, scout-rapport behöver uppdateras.
   - Om Cloud Agent VM saknar python3-venv → kör `sudo apt-get install -y python3-venv` per `AGENTS.md`-not.

## Scout-rapportens format

Skriv en kort rapport (max ~200 rader) i markdown. Sektioner:

1. **TL;DR** (3-5 rader)
2. **Verifiering** — vad du fann i resolvern + Backoffice + tester. Konkreta filsökvägar + radnummer.
3. **Cloud-agent-prompt** — den faktiska prompten cloud-agenten ska få. Klar att klistras in.
4. **Risker / öppna frågor** — om något är otydligt, flagga för operatör.

## Vad du INTE ska göra

- Inga kod-ändringar. Du är read-only.
- Ingen PR. Cloud-agent gör det själv.
- Ingen ADR. Detta är diagnostik-bump, inte canonical-namn-ändring.
- Inget extra scope. Om du upptäcker andra Backoffice-stale-data, skriv en SEPARAT scout-rapport — inte en blandad fix.
