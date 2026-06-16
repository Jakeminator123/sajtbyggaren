---
status: active
owner: governance
truth_level: operational-contract
---

# Starter Contract

Det här är det hårda kontraktet för hur en ny Starter får bli användbar i
byggkedjan. Syftet är att hålla en Starter som ett neutralt basprojekt och
förhindra att varje ny bas blir en ny Python-operation.

Kontraktet är grundat i dagens källor:

- `data/starters/README.md` beskriver Starters som körbara Next.js-baser som
  scaffolds patchar med routes, sektioner, Variant-tokens och Project Input.
- `governance/policies/starter-registry.v1.json` är registret över giltiga
  Starter-id:n och deras status.
- `packages/policies/component_catalog.py:SCAFFOLD_STARTER_MAP` är den aktiva
  scaffold-till-Starter-mappningen som planering och build delar.
- `packages/generation/build/renderers.py:_DISPATCHED_SCAFFOLDS` är den smala
  allowlisten för scaffolds vars routes går via sektionsdispatchern.
- `scripts/build_site.py` säger i moduldocstringen att buildern kopierar
  `site_plan["starterId"]` och patchar den med Project Input-innehåll och
  Variant-tokens.

## Hårt kontrakt

En Starter:

1. får inte kräva ändringar i `scripts/build_site.py`
2. måste acceptera sidor via `write_pages` och sektionsdispatchern
3. måste använda samma Variant-token- och CSS-kontrakt som övriga Starters
4. får inte bära business logic
5. får aldrig producera fake content
6. är bara layout-, struktur- och visuell bas

Praktiskt betyder det att en Starter får bära neutral Next.js-struktur,
paketsetup, komponentbas, CSS-variabler och tomma ytor som buildern fyller.
Den får inte bära kundfakta, påhittade recensioner, hårdkodade CTA-länkar,
checkout-flöden, auth, databas, CMS-koppling eller en egen beslutsmotor.

## Enda legitima registreringspunkter

En Starter blir aktiv genom två explicita registreringspunkter, inte genom en
ny specialgren i buildern:

1. En rad i `SCAFFOLD_STARTER_MAP` i
   `packages/policies/component_catalog.py`.
2. En rad i `_DISPATCHED_SCAFFOLDS` i
   `packages/generation/build/renderers.py`, när scaffoldens routes behöver
   sektionsdispatch i stället för de äldre route-id-renderarna.

Det här dokumentet ändrar inte de raderna. Det låser bara regeln: en ny
Starter-aktivering ska vara mapping plus dispatch-registrering när den behövs,
inte starter-specifik scripting.

## Nya sektionstyper är build-förmågor

Om en scaffold behöver en genuint ny sektionstyp är det inte ett Starter-jobb.
Då behövs en återanvändbar renderer och dossier-/capability-grundning som en
ny build-förmåga. Den förmågan ska kunna delas av flera scaffolds och följa
samma ärlighetsregler som övrig rendering: inget rått följdprompt-innehåll,
inga påhittade fakta och ingen tom synlig modul som låtsas vara färdig.

En Starter får alltså inte innehålla egen Python-logik, egen route-skrivare
eller egna content-regler för att få en viss scaffold att fungera.

## Nuvarande status

Statusen nedan skiljer aktiv runtime från tillgängligt underlag:

| Starter | Status | Kommentar |
| --- | --- | --- |
| `marketing-base` | active-runtime | Aktiv för de mappade informationsscaffoldsen i `SCAFFOLD_STARTER_MAP`. |
| `commerce-base` | active-runtime | Aktiv för `ecommerce-lite`. |
| `portfolio-base` | available-not-mapped | Harmoniserad bas finns, men ingen aktiv runtime-mappning idag. |
| `docs-base` | available-not-mapped | Harmoniserad bas finns, men `course-education -> docs-base` är gated av B49 i `docs/known-issues.md`. |
| `saas-base` | placeholder | Registrerat mål för `saas-product`, men saknar körbar on-disk kod idag. |

`data/starters/README.md` innehåller målbilden för hur fem Starters kan täcka
fjorton scaffolds. Den målbilden är inte samma sak som aktiv runtime. Aktiv
runtime är den subset som finns i `SCAFFOLD_STARTER_MAP` och som har stöd i
route-/sektionsrenderingen.

## Review-check för Starter-PR

En PR som aktiverar eller ändrar en Starter ska kunna svara ja på detta:

- Har den undvikit ändringar i `scripts/build_site.py`?
- Är scaffold-till-Starter-valet en tydlig `SCAFFOLD_STARTER_MAP`-rad?
- Om routes inte passar äldre route-id-renderare: finns exakt den nödvändiga
  `_DISPATCHED_SCAFFOLDS`-raden?
- Är varje sektionstyp renderbar via sektionsdispatchern eller en återanvändbar
  ny build-förmåga?
- Kommer copy, bilder, kontaktvägar, CTA:er och företagsfakta från Project
  Input, Scaffold, Variant eller Dossier i stället för Startern?
- Är startern fortfarande neutral: ingen auth, databas, betalning, CMS,
  analytics, fake content eller business logic?

Om svaret kräver en ny specialgren för just en Starter är det inte en
Starter-aktivering. Då är det en ny build-förmåga eller ett nytt runtime-beslut
som behöver eget scope.
