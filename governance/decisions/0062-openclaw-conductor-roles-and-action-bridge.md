# ADR 0062 — OpenClaw som dirigent: rollkontrakt, ConversationKind och action-bryggan

**Status:** Accepted
**Datum:** 2026-06-15
**Beroenden:** ADR 0036 (router-vokabulär), ADR 0034 (följdprompt-väg A), ADR 0044
(SOUL/chatt-persona), ADR 0057 (component_builder-rollkontrakt), ADR 0060
(route/nav-mutation + route_editor), ADR 0033 (preview-runtime). Relaterad
proposed: ADR 0059 (component_builder katalog-mount).
**Berörda filer (beskriver, ändrar inte):**
[`packages/generation/orchestration/openclaw/roles.py`](../../packages/generation/orchestration/openclaw/roles.py),
[`scripts/run_openclaw_followup.py`](../../scripts/run_openclaw_followup.py),
[`scripts/build_site.py`](../../scripts/build_site.py) (`run_followup_chain`),
[`apps/viewser/app/api/prompt/route.ts`](../../apps/viewser/app/api/prompt/route.ts),
[`docs/openclaw-workspace/action-registry.json`](../../docs/openclaw-workspace/action-registry.json),
korsvaliderade av
[`tests/test_openclaw_registry_consistency.py`](../../tests/test_openclaw_registry_consistency.py)
och [`tests/test_openclaw_roles.py`](../../tests/test_openclaw_roles.py).

## Numrering (notis)

0061 togs av Generative Component V1 (#341, Fas 4), som mergades till jakob-be
parallellt med detta pass. Denna foundational ADR får därför 0062.

## Syfte

Detta beslut gör den redan **landade** OpenClaw-arkitekturen till en explicit
sanningskälla i beslutsregistret. Den införs inte som en ny feature — den
beskriver nuläget så att en ny agent får rätt mental modell:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](../../docs/heavy-llm-flow/openclaw-2.0-conductor.md)
är **plan/roadmap** (med en framtida extern Docker-dirigent); DENNA ADR är
beslutsägaren för det som faktiskt körs in-process idag.

## Beslut

### 1. OpenClaw är en dirigent, inte en ny motor

OpenClaw är en **dirigent** ovanpå den befintliga in-repo-motorn — inte en ny
generator, inte en parallell motor och inte en fri kod-agent. Principen
(oförändrad): **frihet i förståelsen (LLM-roller), kontroll i appliceringen
(deterministisk apply + guards).** En roll *förstår och föreslår*; den
deterministiska kedjan *validerar och applicerar*.

### 2. Två flöden + en brygga

| Del | Vad | Var |
|---|---|---|
| KÖR-kedjan (grundflödet) | Deterministisk apply/build: `router → context → patch → apply → targeted render`. Ärlig (ingen falsk success), validerad, immutabla versioner. Det som faktiskt bygger och ändrar sajten. | `scripts/build_site.py:run_followup_chain` |
| Dirigenten (OpenClaw Core V0) | Den rena funktionen `decide()`: klassar konversationsart, väljer roll och `contextLevel`, ger grundade planeringssvar. Ingen disk, inget bygge, inget nätverk. | `packages/generation/orchestration/openclaw/` |
| Action-bryggan | `scripts/run_openclaw_followup.py --apply`: dirigenten beslutar, och för en edit DELEGERAR den till KÖR-kedjan och rapporterar det verkliga utfallet under `bridge`. En read-only-art bygger aldrig. Konsumeras av Viewser. | `apps/viewser/app/api/prompt/route.ts` (`runOpenClawFollowupApply`) |

### 3. Fas 1 — en beslutsyta (LANDAD, #338)

`run_followup_chain` har en valfri parameter `decision: RouterDecision | None`.
När dirigenten (`run_openclaw_followup`) redan klassat meddelandet injiceras dess
`RouterDecision` och kedjan KONSUMERAR den i stället för att klassa om. Följden:
en följdprompt klassas **EN gång** per `--apply`-anrop (en beslutsyta, max ett
modellanrop). Beteendebevarande: dirigentens `RouterContext` bär ingen
`routeSections`, så det injicerade beslutets ordinal-target (t.ex. "andra
sektionen") re-resolveras till ett konkret `sectionId` i kedjan
(`_resolve_injected_decision_sections`, samma regel som routerns interna
`_build_target`) innan resten av kedjan kör. Detta är **nuläge**, inte plan
(mergad i #338).

### 4. RoleContract-modellen (de roller som FAKTISKT finns)

`ROLE_CONTRACTS` i `roles.py` är frysta, typade dataclasses. Varje kontrakt låser
vilka router-`EditKind` rollen konsumerar (in) och vilka directive-kinds den får
emittera (ut), plus `contextLevel`, mognadsstatus och `mountOnly`. Detta är de
sex roller som finns i koden idag (gissa inte fler):

| Roll | Äger (editKind) | contextLevel | Status | Skill | Beslut |
|---|---|---|---|---|---|
| `router` | — (dispatcher) | none | supported | — | producerar ett routing-beslut, ALDRIG ett directive |
| `section_builder` | section_add | artifacts_plus_sections | supported | section-add | mount-only; `faq`/`team` renderas synligt på local-service-business |
| `stylist` | visual_style | artifacts | supported | restyle | tema/färg/font via theme_directives |
| `copy` | copy_change | artifacts | supported | copy-change | name/tagline/about/services-copy med grundnings-/leak-guards |
| `component_builder` | component_add | component_registry | **partial** | component-add | ADR 0057, mount-only: katalog-grundat svar eller ärlig no-op mot intaget |
| `route_editor` | route_remove, nav_hide | artifacts_plus_sections | supported | route-remove | ADR 0060, strukturerat direktiv (disabledRoutes / hiddenNavRoutes) |

`role_for_edit_kind` mappar editKind → ägande roll. De router-`EditKind` som
**ingen** roll äger i denna yta (`component_remove`, `layout_change`, `route_add`,
`none`) returnerar ärligt `None` — den herrelösa ytan döljs inte.

### 5. ConversationKind + answer-only-grenen

`classify_conversation` är en ADDITIV påbyggnad på routerns låsta `messageKind`
(rör aldrig dess åtta-kinds-enum eller `router-decision.schema.json`). De faktiska
`ConversationKind`-värdena i koden:

- `edit` — passthrough: varje router-edit bevaras ordagrant (med ägande roll).
- `small_talk` — småprat/skämt/hälsningar.
- `site_opinion` — omdöme om den aktuella sajten (svaras ur artefakter).
- `question` — ren fråga.
- `other` — `bug_report`/`reference_analysis`/oklart (egen downstream-hantering).

`ANSWER_ONLY_CONVERSATION_KINDS = (small_talk, site_opinion, question)` är den
ärliga answer-only-grinden: `expectsAnswer=True` ENBART för dessa, och då svarar
dirigenten i chatten UTAN bygge (ingen ny version, ingen render). Detta är enda
sanningskällan, speglad av `_ANSWER_ONLY_CONVERSATION_KINDS` i
`run_openclaw_followup.py` och `CONVERSATION_ANSWER_KINDS` i `route.ts`.
No-key-paritet: klassningen är deterministisk och identisk med/utan
`OPENAI_API_KEY` (`source=mock-no-key` utan nyckel).

### 6. Action-registry/skill-kopplingen

Kedjan: **roll → skill → strukturerad directive → deterministisk apply.**
`skill_for_edit_kind(edit_kind)` läser skill-sökvägen FRÅN det låsta
rollkontraktet (inte hårdkodad), så kedjans dispatch-nyckel aldrig kan driva isär
från `ROLE_CONTRACTS`. `docs/openclaw-workspace/action-registry.json` speglar varje
roll-action (skill, routerEditKind, status, mountOnly/visibleTypes) och
korsvalideras mot rollkontrakten av `tests/test_openclaw_registry_consistency.py`
så de två ytorna aldrig kan driva isär igen.

## Hårda gränser (rails — icke förhandlingsbart)

- **Ingen fri filpatch.** Rollerna emitterar strukturerade directives; KÖR-kedjan
  applicerar. Aldrig godtycklig Next.js-/fil-patch.
- **Ingen parallell motor.** Ny förmåga = en roll + skill + editKind som
  dispatchas genom EN kedja, aldrig en sidosilo.
- **Ingen egen sanningskälla.** Project Input / Site Brief / Site Plan /
  Generation Package + `data/runs/<runId>` äger sanningen; dirigenten gör det inte.
- **Ingen runtime-mount av okurerade komponenter.** Att vendorera in en komponent
  är en operatörs-PR via det kurerade intaget (ADR 0054), aldrig en runtime-mount.
- **Ingen påhittad success.** Saknas en capability blir det en ärlig no-op
  (`unappliedFollowupIntents` / `..._unsupported`-stage), och
  `appliedVisibleEffect`/`previewShouldRefresh` förblir kedjans auktoritativa
  utfall — aldrig en falsk "ändrade din sajt".

## Relation till andra beslut

- ADR 0044 — SOUL styr chatt-personan/tonen (inte byggbeteende); answer-only-
  svaret produceras av TS-halvan, inte påhittat i Python.
- ADR 0057 — `component_builder`-rollkontraktet (partial/mount-only) som denna
  ADR samlar in i rollmodellen.
- ADR 0059 (proposed) — eventuell katalog-mount (`component_builder`
  partial→supported för kända komponenter); ej beslutat.
- ADR 0060 — `route_editor` + `route_remove`/`nav_hide`; bevisade roll-driven
  exekvering genom EN kedja.
- ADR 0033 — preview-runtime (vercel-sandbox primär) som visar dirigentens
  resultat; oberoende av detta beslut men del av kärnloopen.
- `docs/heavy-llm-flow/openclaw-2.0-conductor.md` — plan/roadmap (extern
  Docker-dirigent m.m.); DENNA ADR är beslutsägaren för in-process-nuläget.

## Vad ADR 0062 INTE beslutar

- Ingen extern Docker-dirigent eller HTTP-yta (Fas 2 i planen, framtida).
- Ingen ny `EditKind` i routern eller ändring av router-decision-schemat.
- Ingen generativ/fri komponentkod (egen senare ADR).
- Ingen ändring av ROLE_CONTRACTS, action-registret eller någon körande kod —
  detta är ett docs/governance-beslut som beskriver befintlig kod.

## Verifiering (befintlig, oförändrad)

- `tests/test_openclaw_roles.py` (sex frysta rollkontrakt, immutabilitet),
  `tests/test_openclaw_registry_consistency.py` (roll ↔ action-registry),
  `scripts/verify_openclaw.py`.
- Fas 1: `run_followup_chain(..., decision=...)` konsumerar dirigentbeslutet
  (mergad #338).
