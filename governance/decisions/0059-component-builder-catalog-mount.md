# ADR 0059 — component_builder katalog-mount (Steg 1: känd komponent → synlig montering)

**Status:** Proposed (utkast 2026-06-15; kräver operatörens OK + ett fokuserat
implementationspass med visuell verifiering, i #320-anda)
**Beroenden:** ADR 0057 (`component_builder`-rollkontrakt, partial/mount-only),
ADR 0040 (komponentkatalog), ADR 0038 (synlig inline-sektionsrender), ADR 0043
(`sectionContentOverrides`), ADR 0034 (följdprompt-väg A).
**Berörda filer (vid implementation):**
[`roles.py`](../../packages/generation/orchestration/openclaw/roles.py),
[`section_directives.py`](../../packages/generation/followup/section_directives.py),
[`classify.py`](../../packages/generation/orchestration/router/classify.py),
[`capability-map.v1.json`](../policies/capability-map.v1.json),
[`llm-models.v1.json`](../policies/llm-models.v1.json), renderarna i
`packages/generation/build/`, samt korsvalidering i
`tests/test_openclaw_registry_consistency.py`.

## Kontext

`component_builder` äger `component_add` men är `status="partial"`,
`mountOnly=True` (ADR 0057): en fri komponent-följdprompt får ett katalog-grundat
svar eller en ärlig no-op — den **monterar inget**. Samtidigt monterar
`section_add` redan kända sektionstyper (`faq`/`reviews`/`team`/`trust`/…) via
`section_directives.py` → capability → dossier, och `faq`/`team` renderas redan
**synligt** på `local-service-business`. Övriga (t.ex. `reviews` =
"testimonials", `trust`) monteras men renderas inte (mount-only).

Detta är två "dumma" specialfall som coachen 2026-06-15 pekade ut: (a)
`component_add` är en återvändsgränd vid sidan av `section_add`, och (b) den
synliga render-täckningen är smal (bara faq/team). Resultat: "lägg till
testimonials" känns trögt — antingen ärlig no-op eller mount-utan-synlighet.

Principen (oförändrad, ADR 0057 + målbild §5): **frihet i förståelsen, kontroll
i appliceringen.** Detta steg flyttar in mer beslutskraft i konduktorn **med
rails** — det inför INGEN fri generativ komponentkod (det är Steg 5, egen ADR).

## Beslut (Steg 1 — smalt, konsoliderande)

1. **`componentIntentModel` (ny roll, llm-models-bump).** Tolkar en fri
   följdprompt till ett strikt schema
   `{ kind, capability, targetRoute, sectionType, confidence, reason }`, där
   `capability`/`sectionType` RE-VALIDERAS mot capability-map-allowlisten i kod
   (samma guard-mönster som copyDirective/styleDirective). Låg `confidence` →
   no-op/förtydligande, aldrig falsk success. Modellen skriver aldrig ett fält
   direkt och gör aldrig fri filpatch. Körs bara när den deterministiska
   sektionstyp-detektionen i `classify.py` missar — den deterministiska vägen
   förblir primär (mock-paritet utan `OPENAI_API_KEY`).

2. **`component_builder` partial→supported för KÄNDA katalog-komponenter.** En
   igenkänd capability monteras via den BEFINTLIGA `section_add`-maskineriet
   (`requestedCapabilities` + `selectedDossiers.required`) — ingen ny mount-väg.
   Detta krymper `component_add`-specialfallet in i den redan testade
   sektionsvägen (konsolidering, inte en sidoväg till).

3. **Bredda den synliga render-vägen** till `reviews`/`trust` (och fler med
   home-kompatibel `<section>`-renderer) via `INLINE_SECTION_PLACEMENTS` /
   `VISIBLE_SECTION_ROUTES` + grundat-innehåll-grind, så "lägg till
   testimonials" ger en SYNLIG, ärlig ändring. Renderaren äger fortsatt
   `appliedVisibleEffect`; saknat grundat innehåll → ärlig mount-only (aldrig
   påhittad sektion).

4. **Okänd / ogrundad → ärlig plan eller no-op** via `unappliedFollowupIntents`
   (#313). En icke-katalog-komponent (t.ex. "roterande 3D-pizza") blir ett
   ärligt "stöds inte än som automatisk montering" — INTE en falsk success.
   (Det renodlade novel-intent-planeringssvaret kan tas som ett syskon-steg.)

## Vad ADR 0059 INTE beslutar

- Ingen fri generativ komponentkod / godtycklig filpatch (Steg 5, egen ADR).
- Inga nya katalog-komponenter (vendorering förblir en operatörs-PR via det
  kurerade intaget, ADR 0054).
- Ingen ändring av router-`EditKind`-enumet.

## Rails / ärlighet

Deterministisk apply + guards + immutabla versioner. `componentIntentModel`
föreslår; capability-map + renderaren validerar och materialiserar. Allt som
inte är en känd, grundad katalog-capability är en ärlig no-op/plan. Samma
honesty-genom-konstruktion som restyle (#316) och copyDirectives.

## Verifieringsplan (vid implementation)

- intent-schema-validering (allowlist; låg confidence → no-op);
- känd komponent monteras + renderas synligt (reviews/trust);
- okänd komponent → ärlig no-op/plan (ingen falsk success);
- model-routing-policytest för `componentIntentModel`;
- source-lock: ingen fri filpatch;
- befintliga följdprompt-ärlighetstester gröna;
- visuell verifiering i `/studio` (operatören, i #320-anda) innan merge.

## Nästa steg

Operatörens OK → ett fokuserat implementationspass (en slice i taget: intent +
mount-konsolidering först, synlig render sedan), var och en grön mot alla
guards innan push.
