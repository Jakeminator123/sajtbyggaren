# Builder-uppdrag: copyDirective-modulutbrytning (behavior-preserving)

> Klistra in detta i en isolerad builder-agent (Cursor Cloud Background Agent
> eller motsvarande). Prompten är self-contained. Det här är en **surgical
> refactor UTAN beteendeändring** — inga buggar fixas, inga regler ändras,
> ingen ny copyDirective-funktion byggs. Bara filflytt + import/re-export så att
> hela testsviten passerar oförändrad.

## Bakgrund (varför)

`scripts/prompt_to_project_input.py` har vuxit till ett nav: prompt-mapping,
follow-up-merge, semantic patch OCH hela copyDirective-delsystemet
(ADR 0034 väg A nivå 1–3a: deterministisk extraktor, editPlan-planerare,
validering, grundnings-guard, site-state-läsare, apply). Två externa reviewers
(2026-06-02) rekommenderade samma sak: **bryt ut copyDirective-delsystemet till
en egen modul med tydliga contracts innan fler targets (cta/all-copy) byggs**,
annars blir nästa slice svår att resonera om. Detta uppdrag gör exakt det —
och bara det.

## Roll

Du är en builder-agent på branch `jakob-be` (jobba direkt på `jakob-be`, öppna
ingen PR mot `main`). Du flyttar copyDirective-koden från
`scripts/prompt_to_project_input.py` till ett nytt paket
`packages/generation/followup/`, och låter `scripts/prompt_to_project_input.py`
behålla follow-up-orkestreringen (`merge_followup_project_input`) + re-exporta
de namn som tester och andra moduler importerar.

## Läs först (i denna ordning)

1. `AGENTS.md`
2. `docs/current-focus.md` (toppblocket "Nästa")
3. `governance/decisions/0034-followup-prompt-content-passthrough.md`
4. `governance/rules/branch-scope-ui-ux.md` — verifiera att du **inte** är en
   `christopher-ui`-agent (du rör inte `apps/viewser/**`).
5. `governance/rules/code-in-english.md`
6. `scripts/prompt_to_project_input.py` — hela copyDirective-sektionen:
   `_COPY_DIRECTIVE_*`-konstanter/regexar, `_classify_copy_target`,
   `_extract_replace_value`, `_extract_explicit_replace_value`,
   `_extract_service_target_ref`, `_match_service_by_ref`, `_safe_copy_payload`,
   `_extract_copy_directives`, `_validate_copy_directive_candidate`,
   `_extract_copy_directives_via_llm`, `_has_explicit_copy_value`,
   `_content_rewrite_target`, `_is_content_rewrite_request`,
   `_build_site_state_for_copy_planning`, `_site_state_grounding_text`,
   `_planned_payload_grounded`, `_plan_copy_directives_via_llm`,
   `_apply_copy_directives`, samt anropet i `merge_followup_project_input`.
7. `packages/generation/brief/extract.py` — `extract_copy_directives_llm` +
   `plan_copy_directives_llm` (LLM-plumbing; **lämnas kvar** här, importeras
   lazy av den nya modulen precis som idag).
8. `tests/test_followup_copy_directives.py` — testerna importerar
   copyDirective-namn FRÅN `scripts.prompt_to_project_input`. De ska passera
   **oförändrade** via re-exports.

## Mål

1. Skapa paketet `packages/generation/followup/`:
   - `__init__.py` (docstring + ev. re-exports).
   - `text.py` — de delade lågnivå-texthjälparna som BÅDE copyDirective-koden
     och intent-klassificeringen använder. Flytta hit:
     `_normalise_followup_text`, `_contains_any`, `_contains_word`,
     `_contains_any_word`, `_string_value`. (Identifiera exakt vilka som delas
     genom att söka anropare; om en helper bara används av copyDirective-koden
     hör den hemma i `copy_directives.py` istället.)
   - `copy_directives.py` — hela copyDirective-delsystemet (konstanter, regexar,
     alla `_*`-funktioner i punkt 6 ovan UTOM de som är genuint delade och
     flyttats till `text.py`). Modul-docstring som förklarar ursprung + ADR 0034.
2. I `scripts/prompt_to_project_input.py`:
   - Ta bort de flyttade definitionerna.
   - Importera från de nya modulerna.
   - **Re-exportera** alla namn som tester/andra moduler refererar via
     `scripts.prompt_to_project_input` (minst: `_extract_copy_directives`,
     `_extract_copy_directives_via_llm`, `_validate_copy_directive_candidate`,
     `_is_content_rewrite_request`, `_apply_copy_directives` — verifiera mot
     `tests/test_followup_copy_directives.py`-importerna och `grep` i repo:t).
   - Behåll `merge_followup_project_input` här; den ska anropa de importerade
     copyDirective-funktionerna (inkl. story-snapshot/restore-logiken som ÄR
     follow-up-orkestrering och stannar i denna fil).

## Vad du EJ ska göra

- **Refactora aldrig funktionsbody:s.** Kopiera ordagrant (inkl. kommentarer).
- Fixa aldrig buggar, ändra aldrig regler, lägg aldrig till targets.
- **Ändra aldrig `classify_followup_intent` eller `_apply_semantic_patch`.**
- **Bredda INTE grounding-guarden** (årtal → siffror/orter/namn) — det är ett
  SEPARAT, beteendeändrande uppdrag.
- **Rör aldrig `apps/viewser/**`, `packages/preview-runtime/**`, renderers,
  `build_site.py`, schema eller governance-policies.** (Schema/policy är redan
  i synk; den här refaktorn ändrar inget kontrakt.)
- **Rör aldrig testfiler.** De ska passera via re-exports. Om en testimport går
  sönder är det en re-export du missat — lägg till re-exporten, ändra inte testet.
- Flytta INTE `extract_copy_directives_llm`/`plan_copy_directives_llm` ur
  `packages/generation/brief/extract.py` (de importeras lazy idag — behåll det).

## Cirkulär-import (viktigast)

`scripts/prompt_to_project_input.py` kommer importera
`packages/generation/followup/copy_directives.py`. Om copy_directives då
importerar tillbaka från `prompt_to_project_input` uppstår en cykel. Bryt den
genom att lägga de **delade** lågnivåhjälparna i `followup/text.py` som båda
importerar. Verifiera att `copy_directives.py` INTE importerar från
`scripts.prompt_to_project_input`. Kontrollera även eventuella beroenden som
`_customer_safe_planner_note`, `_title_case_company_name`,
`_looks_like_trailing_instruction`/`_TRAILING_INSTRUCTION_LEADS`,
`resolve_copy_directive_model`:
- Om en helper bara används av copyDirective-koden → flytta med till
  `copy_directives.py`.
- Om den delas med semantic patch / annan follow-up-logik → lägg i `text.py`
  (eller importera från sin nuvarande ägare om den inte skapar en cykel).
- `resolve_copy_directive_model` bor i `packages/generation/brief/models.py` —
  importera därifrån (ingen cykel).

### Bekräftat designval (Scout 2026-06-02 — följ detta)

- **`_copy_directive_llm_eligible` STANNAR i `scripts/prompt_to_project_input.py`.**
  Flytta den INTE till `text.py` eller `copy_directives.py`. Den läser
  `intent: FollowupIntent` och `_FOLLOWUP_ADD_ONLY_KEYWORDS` — båda är
  intent-klassificeringsartefakter som hör hemma i PI — och anropar ingen
  copy-funktion. Att lämna den i PI håller `copy_directives.py` fri från
  intent-konstanter och undviker att dra `FollowupIntent` +
  `_FOLLOWUP_ADD_ONLY_KEYWORDS` till `text.py`. `merge_followup_project_input`
  anropar den lokalt. (Samma gäller `_content_rewrite_target`/
  `_is_content_rewrite_request`-anropen — själva funktionerna kan flytta med
  copy_directives eftersom de inte beror på intent, men eligibility-glömmet mot
  intent stannar i PI.)
- `FollowupIntent`, `classify_followup_intent`, `_apply_semantic_patch`,
  `_FOLLOWUP_ADD_ONLY_KEYWORDS` och `_FOLLOWUP_*`-intent-konstanterna stannar i
  PI — de är inte copyDirective-kod.

## Guards (alla måste vara gröna, jämför mot baseline `df99076`)

```powershell
cd apps/viewser; npx tsc --noEmit; cd ..\..
python -m pytest tests/ -q
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python -m ruff check .
```

- `tests/test_followup_copy_directives.py` ska ha **exakt samma antal pass** som
  före refaktorn. Kör baslinjen själv direkt efter att du startat (på synkad
  merge-base) och **lås det exakta antalet passerade tester** (`passed`-siffran
  från pytet) — det var 88 passed på `jakob-be` 2026-06-02 efter PR
  #149-review-fixarna, men bekräfta mot din faktiska merge-base. Kräv samma
  antal oförändrat efter-tal.
- Övriga baseline-tal (Scout 2026-06-02, ska vara identiska efter refaktorn):
  `ruff check .` = 0 findings; `governance_validate.py` = 18/18 policies OK;
  `rules_sync.py --check` = OK; `check_term_coverage.py --strict` = 0 okända.
- Full pytet grön (samma siffror som baseline; den enda kända flaken är
  `test_api_prompt_route_spawns_python_end_to_end` om en orphan dev-server
  blockerar porten — kör `python kill-dev-trees.py` först).
- ruff 0 findings, governance 18/18, rules-sync OK, term-coverage --strict 0.

## Verifiering av beteende-paritet

Utöver gröna tester: kör en faktisk follow-up genom CLI:t före och efter och
diffa att Project Input-outputen är byte-identisk för ett par prompter, t.ex.:

- en rename ("byt företagsnamnet till Volvo"),
- en about-replace ("ändra om oss-texten till 'Vi är ett familjeföretag'"),
- en services-replace ("ändra tjänsten 'X' till 'Y'").

(Deterministiska vägar; ingen API-nyckel behövs. editPlan-planeraren kräver
LLM och täcks av de mockade testerna.)

## Leverabel

Commit(s) på `jakob-be` (ingen main-PR utan operatörs-OK). Innehåll:

- `packages/generation/followup/__init__.py`
- `packages/generation/followup/text.py`
- `packages/generation/followup/copy_directives.py`
- `scripts/prompt_to_project_input.py` (slimmad: orkestrering + re-exports)
- Inga testfilsändringar.

Commit-titel: `refactor(followup): extract copyDirective subsystem to packages/generation/followup`

Commit-beskrivning ska innehålla:
- Före/efter line-count i `scripts/prompt_to_project_input.py`.
- Lista över flyttade funktioner/konstanter per ny fil.
- Bekräftelse att alla guards är gröna (kopiera siffrorna).
- Bekräftelse att copyDirective-testerna är oförändrade och gröna.
- Hänvisning till denna prompt + ADR 0034.

## Misslyckande-mod

Om cirkulär-import inte går att bryta rent, eller om en helper har starkare
delning än väntat, stanna och rapportera (öppna ingen halv-merge). Beskriv
beroende-grafen och föreslå en scope-justering (t.ex. fler helpers till
`text.py`) i stället för att gissa.

## Efter denna refaktor (separata, beteendeändrande uppdrag — INTE här)

- Bredda editPlan grounding-guard (årtal → siffror/priser/orter/namn/
  certifieringar).
- ADR 0034-städning (status + kontrakt matchar nivå 2/3a).
- Nivå 3-fortsättning (multi-target editPlan, verifierModel, väg B-UI).
- Slice 2d cta/hero (kräver kontraktsbeslut).

## Modellval för agent

Composer 2.5 eller GPT-5-codex — mekaniskt refactor-arbete där deterministisk
noggrannhet > kreativitet. Verifiera mot testerna efter varje flyttgrupp.
