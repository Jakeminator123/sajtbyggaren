# ADR 0047 — generativ sektionsomskrivning utan explicit värde (editPlan för `sectionContentOverrides`)

**Status:** Accepted
**Datum:** 2026-06-10
**Beroenden:** ADR 0034 (follow-up prompt content passthrough — `copyDirectives`
+ editPlan nivå 3a, prejudikat för generering-med-guards), ADR 0043 (ändringsbar
sektionstext via `directives.sectionContentOverrides`). Referens:
[`docs/gaps/GAP-followup-prompt-content-passthrough.md`](../../docs/gaps/GAP-followup-prompt-content-passthrough.md)
(B155-resten), `docs/known-issues.md` (ADR 0043-slicens uppföljning punkt (a)).

## Kontext

ADR 0043 (#278, mergad) gjorde sektionstext ändringsbar **när följdprompten bär
den nya texten** ("ändra texten i hero till X", "gör om om-oss-texten så den
nämner Y"). Apply härleder copyn deterministiskt ur prompten och skriver den till
det additiva fältet `directives.sectionContentOverrides` (en
`"<routeId>.<sectionId>.<field>" -> text`-map; field = `headline` |
`subheadline` | `body`); renderaren låter override:n vinna över blueprint-copyn.

En omskrivnings-instruktion **utan** explicit värde ("gör om-oss-texten varmare",
"skriv om heron så den låter mer premium") kan inte härledas deterministiskt.
ADR 0043 registrerade detta som uttalat utanför scope och `docs/known-issues.md`
bär det som B155-uppföljning, punkt (a): den deterministiska vägen förblir en
ärlig no-op tills ett copyModel-pass kopplas in i apply.

Prejudikatet finns redan: ADR 0034 nivå 3a gav `copyDirectiveModel` ett
**editPlan-läge** som läser sajtens aktuella redigerbara fält och GENERERAR ny
copy för about-text (`company.story`) och services (`services[].summary`) vid en
rewrite-instruktion utan angivet värde — alltid genom samma public-copy-guards +
grundnings-vakt, och `company-name`/`tagline` genereras aldrig.

## Beslut

Bredda `copyDirectiveModel`-rollens editPlan-läge till sektionsfälten i
`sectionContentOverrides`-vitlistan (`headline` | `subheadline` | `body` per
`<routeId>.<sectionId>`).

1. **Generering.** När apply (KÖR-7c) tar emot en `copy_change`-patch mot ett
   vitlistat sektionsfält och den deterministiska härledningen (ADR 0043
   `derive_section_edit`) inte hittar något explicit värde, OCH följdprompten är
   en omskrivnings-/förbättrings-instruktion (rewrite/improve-verb eller en
   "gör ... varmare/mer premium"-kvalitetsförskjutning, ej additiv), läser
   `copyDirectiveModel` sektionens **aktuella copy** (befintlig override för
   exakt det målet, annars den strukturerade blueprint-copyn) + instruktionen och
   genererar ny text för det **ena** fältet.

2. **Guards (oförändrade, återanvända).** Varje genererad payload går genom samma
   public-copy-validator som `copyDirectives` (`_safe_copy_payload`: rå
   instruktion kan aldrig bli kundcopy, change-verb-/blocklist-avvisning, cap per
   fält — headline/subheadline 200, body 600) PLUS samma grundnings-vakt
   (`_planned_payload_grounded`): en payload som inför ett flersiffrigt tal
   (årtal/pris/antal/procent) som inte finns i den aktuella sektionscopyn eller
   prompten dröppas. Icke-numeriska fakta hålls av systemprompten (samma
   dokumenterade begränsning som ADR 0034). `name`/`tagline` (globala
   copyDirective-targets) genereras aldrig av denna väg.

3. **Applicering — ingen ny skrivyta.** Ett genererat värde appliceras ENBART via
   ADR 0043:s befintliga `sectionContentOverrides`-väg i apply (samma
   leak-säkra, immutabla `v<N+1>`-skrivning). Ingen fri filpatch, ingen
   renderer-ändring (override:n läses redan byte-stabilt), ingen schema-ändring
   (värdet är en sträng i den befintliga map:en).

4. **Mock-paritet.** Utan `OPENAI_API_KEY` returnerar editPlan-passet inget; en
   värdelös omskrivnings-instruktion förblir då exakt dagens ärliga no-op (ingen
   ny version skrivs). Kodvägar utan nyckel är byte-identiska med före ADR 0047.

5. **All-or-nothing bevaras.** En rewrite-instruktion som inte kan genereras (ingen
   nyckel, modell-fel, eller payload dröppt av guard) faller till samma
   `unmapped`-no-op som idag — ingen tom version skrivs. Ett lyckat genererat
   värde mappas till en override och en ny version skrivs.

Lokationsval:

- **Valt — apply-sidans `sectionContentOverrides`-väg** (ADR 0043). Generering är
  ett valfritt förståelse-steg i apply-loopen; resultatet går genom den redan
  sanktionerade override-applicering. En liten lokal cachead läsning av
  föregående version ger sektionens base-text utan att flytta apply:s
  auktoritativa läs-steg eller röra `apply_patch_plan`-signaturen.
- Avvisat — egen ny skrivyta / fält: bryter ADR 0043:s slutna kontrakt i onödan.
- Avvisat — fri filpatch i `.generated/` (ADR 0034 väg C, fortsatt parkerad).

## Konsekvenser

- Kärnflödet (`prompt -> företagshemsida -> preview -> följdprompt -> ny
  version`) håller även för värdelösa omskrivnings-instruktioner mot en sektion:
  de ger nu en synlig, ärlig ändring (`appliedVisibleEffect=true` via den
  befintliga fil-diffen) i stället för en tyst no-op — när en nyckel finns.
- Rå följdprompt renderas aldrig okontrollerat som kundcopy; samma guards som
  `copyDirectives`. Ungrundade tal dröppas.
- Beteendebevarande utan nyckel (mock-paritet); inga befintliga PI-snapshots
  eller renderer-golden påverkas.
- `copyDirectiveModel`-rollens syfte breddas (llm-models policy-bump till
  version 10 — endast purpose-texten, inga parameter-fält).

## Utanför scope (kvarstår i `docs/known-issues.md`)

- Compound-prompter ("gör den coolare och lägg till ett skämt") rapporterar ännu
  inte otillämpade delar via `unappliedFollowupIntents` på apply-vägen.
- Icke-numeriska påhittade fakta (namn, orter, certifieringar) hålls bara av
  systemprompten, inte av en deterministisk vakt (samma begränsning som ADR 0034).
- Fler sektioner/routes än vad ADR 0043 + scaffold-rails redan tillåter.

## Referenser

- `packages/generation/brief/extract.py` (`plan_section_copy_rewrite_llm`)
- `packages/generation/followup/section_content_overrides.py`
  (`is_section_content_rewrite_request`, `current_section_text`,
  `plan_section_edit_via_llm`)
- `packages/generation/orchestration/apply/apply.py` (apply-loopens editPlan-hook)
- `governance/policies/llm-models.v1.json` (`copyDirectiveModel`, version 10)
- `tests/test_section_content_overrides.py`, `tests/test_followup_copy_directives.py`
