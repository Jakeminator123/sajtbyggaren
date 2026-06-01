# ADR 0034 - follow-up prompt content passthrough

**Status:** accepterad (väg A, first slice) / proposed (väg B UI + väg C)
**Datum:** 2026-05-27 (uppdaterad 2026-06-01)
**Beroenden:** ADR 0017 (minimal real codegenModel v1), ADR 0027
(semantic follow-up merge i Project DNA V1), ADR 0032 (section
treatments additive directive), GAP-followup-prompt-content-passthrough.

## Implementationsnot 2026-06-01 (väg A, first slice)

Väg A:s första slice är implementerad på `jakob-be` (ej i `main` än). Detta
är medvetet INTE "full LLM-flow" - det är "ADR 0034 Path A / copyDirectives
first slice":

- **Kontrakt:** `directives.copyDirectives[]` i `project-input.schema.json`
  (strikt: `target` enum `company-name | tagline`, `operation` enum
  `replace-text | include-token`, `payload` validerad/maxLength 200,
  `source` enum `prompt-rule | llm | explicit`). Naming-dictionary v18
  registrerar Copy Directive.
- Deterministiska regler (`scripts/prompt_to_project_input.py`):
  "byt/ändra/gör om \<namn|header|rubrik\> till '\<Y\>'" -> replace-text på
  company-name; "inkludera '\<TOKEN\>' i hero" -> include-token på tagline.
  Körs offline, fullt testbar.
- **LLM-extraktor:** dedikerad `copyDirectiveModel`-roll (llm-models.v1.json
  v5, EJ återanvänd briefModel). Fyrar bara i produktions-CLI (Viewser ->
  `--followup-site-id`), när deterministiska regler missar OCH följdprompten
  är genuint oklassad icke-additiv. All output går genom samma
  public-copy-validator som deterministiska direktiv.
- **Spårbarhet:** applicerade direktiv sparas i Project Input
  (`directives.copyDirectives`); `build-result.json:appliedVisibleEffect`
  (B155) blir `true` när page.tsx ändras.
- **Leak-säkerhet:** rå följdprompt renderas aldrig okontrollerat - bara en
  validerad payload till ett känt strukturerat fält.

Kvar (proposed): väg B FloatingChat-feedback (kräver Christopher/UI), bredare
targets (story/services/all-copy), och väg C (modell patchar `.generated/`
direkt - kräver sandbox/diff/rollback enligt nedan).

## Kontext

Sajtbyggarens kärnflöde är `prompt -> företagshemsida -> preview ->
följdprompt -> ny version`. Operatören verifierade 2026-05-27 två
följdpromptar som skapade ny version men inte synlig ändring:

1. "Allt sla vara mycket ljusare" gav fortsatt mörk/noir/editorial tone i
   `site-brief.json` och renderad sida.
2. "Kan du ändra den där texten vid hero och lite överallt till att
   inkludera 'TEST-JAKOB' i typ alla meninar?" gav ingen förekomst av
   `TEST-JAKOB` i `app/page.tsx`.

Audit i `docs/gaps/GAP-followup-prompt-content-passthrough.md` visar att
följdprompten sparas som metadata (`followUpPrompt`, `input.json`,
`build-result.json`) men inte översätts till ett renderer- eller
codegen-konsumerat fält.

Nuvarande pipeline har fyra spärrar:

- Site Brief-schemat har inget fält för fria copy-direktiv.
- Follow-up-merge klassar okända eller breda content-prompter konservativt
  som `no-semantic-change`.
- Buildern skickar pinnad scaffold/variant till planeringsfasen, så
  planningModel hoppar över omtolkning (`planSource="pinned"`).
- Renderers och codegen-manifest läser strukturerade dossierfält,
  variant/defaults och smala directives; real codegenModel får bara
  skriva `rationale` och `riskNotes`, inte filinnehåll.

## Beslut

Status är proposed. Rekommenderat beslut är en tvåstegslösning:

1. Lägg till ett strikt, validerat copy-direktivkontrakt i Site Brief och
   Project Input. Starta smalt med en lista som kan bära target,
   operation och payload, till exempel `copyDirectives[]`.
2. Lägg ärlig användarfeedback när en följdprompt inte gav ett synligt,
   applicerat direktiv. FloatingChat ska inte signalera lyckad ändring när
   pipeline bara skapade en ny version utan renderad effekt.

En separat modell som patchar `.generated/`-kod direkt ska inte byggas
förrän ett senare beslut har låst sandbox, diff-regler, Quality Gate och
rollback.

## Alternativ

### Alternativ A - strikt `copyDirectives[]`

Utöka Site Brief, Project Input och build-kontraktet med en strukturerad
lista av copy-direktiv. Varje direktiv ska vara validerbart, exempelvis:

- target: `hero`, `services`, `about`, `all-copy`
- operation: `include-token`, `rewrite-section`, `replace-text`
- payload: token, ny copy eller constraints

Fördelar:

- Gör följdpromptar spårbara genom hela pipeline.
- Passar governance-modellen: schema först, sedan implementation.
- Minskar risken för rå prompt-läckage eftersom renderern bara läser
  validerade direktiv.
- Går att regressionstesta med konkreta artefakter och generated files.

Nackdelar:

- Kräver ändringar i brief, Project Input, follow-up-merge, renderer och
  möjligen codegen-summary.
- Bred copy som "lite överallt" måste begränsas eller brytas ned.
- Kräver fallback när direktivet inte kan appliceras utan att ljuga.

### Alternativ B - ärlig FloatingChat-feedback

Behåll pipelinekontraktet smalt men svara användaren när följdprompten
inte resulterade i en synlig ändring. Exempel: "Jag kunde inte fånga en
synlig ändring. Ange exakt sektion eller text som ska ändras."

Fördelar:

- Snabbt sätt att minska tysta no-ops.
- Skyddar produktförtroendet bättre än en falskt lyckad version.
- Kräver ingen ny filpatchning eller bred schemaförändring.

Nackdelar:

- Löser inte kärnlöftet fullt ut; användaren ville få sajten ändrad.
- Riskerar att lägga ansvar på användaren i stället för att förbättra
  generatorn.
- Kan bli svårt att avgöra "ingen synlig ändring" utan robust diff eller
  output-verifiering.

### Alternativ C - real `copyEditModel` ovanpå `.generated/`

Efter ordinarie build kan en separat modell läsa aktuell generated-kod och
följdprompten, skapa en begränsad patch och låta Quality Gate och Repair
Pipeline verifiera resultatet.

Fördelar:

- Mest naturligt för fria copy-prompter.
- Kan hantera exakta texttokens och breda copy-edit-instruktioner utan att
  först modellera varje möjlig sektion.
- Kan ge snabb synlig effekt på befintlig Next.js-output.

Nackdelar:

- Störst säkerhets- och drift-risk eftersom modellen skriver i runtimekod.
- Krockar med ADR 0017-principen att real codegenModel ännu inte emitterar
  filinnehåll.
- Kräver sandbox, diff-policy, rollback, testning och tydlig ägarskap för
  post-build-patchar.

## Rekommendation

Välj alternativ A som produktgrund och komplettera med alternativ B som
ärligt säkerhetsnät. Det matchar produktkompassen: kärnflödets förtroende
är viktigare än teknisk elegans. En följdprompt ska antingen ge en synlig
ny version eller tydligt säga varför ingen synlig ändring fångades.

Alternativ C parkeras tills systemet har ett accepterat kontrakt för
modellskrivna filpatchar efter build.

## Konsekvenser

Positiva:

- Följdpromptar får en explicit, testbar väg från prompt till renderad
  output.
- Pinned scaffold/variant kan fortsätta vara auktoritativa utan att blockera
  copy-ändringar.
- Operatören får bättre artefakter för att förstå varför en version ändrades
  eller inte ändrades.

Negativa:

- Site Brief- och Project Input-kontrakten måste vidgas.
- Renderer-implementeringen behöver definiera vilka targets som kan ta emot
  direktiv i första slice.
- UI behöver visa ärlig no-op-feedback utan att skapa förvirring kring
  versionshistoriken.

## Utanför scope

- B125 preview-fallback.
- Sprint 3B codegenModel och generell LLM-baserad file-emission.
- Full Project DNA V2-lagring.
- Variant-promotion eller ny scaffold selection.
- Direkt patchning av `.generated/` utan separat ADR.

## Acceptanskriterier

Ett framtida accepterat beslut och implementation ska minst uppfylla:

- En följdprompt med exakt token, till exempel `TEST-JAKOB`, kan spåras
  från tolkad artefakt till renderad generated-fil.
- En följdprompt som inte kan mappas till ett synligt direktiv ger ärlig
  FloatingChat-feedback.
- Rå följdprompt renderas aldrig okontrollerat som kundcopy.
- `planSource="pinned"` fortsätter skydda scaffold/variant-val, men copy-
  direktiv blockeras inte av den pinnen.
- Quality Gate och relevanta regressionstester körs efter ändringen.

## Referenser

- `docs/gaps/GAP-followup-prompt-content-passthrough.md`
- `docs/product-operating-context.md`
- `scripts/prompt_to_project_input.py`
- `packages/generation/brief/extract.py`
- `packages/generation/planning/plan.py`
- `packages/generation/build/renderers.py`
- `packages/generation/codegen/codegen.py`
