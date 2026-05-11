# ADR 0019 - Exkludera apps/web från term-coverage (strict)

**Status:** accepted
**Datum:** 2026-05-11
**Beroenden:** ADR 0006 (term discipline), ADR 0012 (vocabulary
compression), ADR 0018 (apps/web import).

## Kontext

ADR 0018 dokumenterar importen av Christopher's UI till apps/web.
Importen drog in cirka femhundra nya identifierare i pascal-stil — i
huvudsak shadcn- och radix-primitiver, next-page-komponenter, layout-
komponenter och små lokala typ-aliaser.

Inget av detta är **domänbegrepp** i den mening termordlistan handlar
om. Domänspråket (Site Brief, Generation Package, Scaffold, Dossier,
Capability Map med flera) ägs av packages-generation och governance.
apps-web är en **konsument** av det språket via copy-strängar — den
introducerar inga nya canonical begrepp.

Strict-gaten i scripts-mappen blockerade därför PR
frontend-christopher-import med cirka femhundra falska positiva.
ADR 0018 angav att en uppföljnings-PR antingen ska:

1. Lägga in en common-words-utvidgning analog med viewser-blocket, eller
2. Exkludera apps-web-components-ui direkt i iter-files-funktionen.

## Beslut

Vi **exkluderar hela apps-web** i scripts-skannern, inte bara
underkatalogen för shadcn-primitiver. Skälet är att gränsen "vad är en
shadcn-primitiv" inte håller — flera UI-implementations-symboler
ligger utanför ui-mappen men är samma kategori av lokala
implementations-namn. En partiell exclusion skulle bara flytta bruset.

apps-web läggs in som ett path-skip på samma rad som existerande
skips för governance-policies och cursor-rules i skannerns main-funktion.

apps-viewser påverkas inte — dess implementation-symboler är redan
allowlistade i common-words och fortsätter scannas.

## Konsekvenser

### Vad detta löser

- Frontend-christopher-import-PR:n kan gå grönt och mergas till main.
- Apps-web kan utvecklas vidare utan att varje ny shadcn-rerender
  kräver naming-dictionary-uppdatering.
- Naming-dictionary förblir fokuserad på domänspråket.

### Vad detta inte löser

- Om apps-web i framtiden börjar introducera **äkta domänbegrepp**
  ska de registreras i naming-dictionary precis som vanligt —
  exclusion är en path-skip, inte en disciplineringsbefrielse.
- Shadcn-uppdateringar som introducerar nya primitiver i andra
  apps-componens-ui-mappar skulle behöva analog behandling. Vi
  hanterar det när det händer.

## Verifiering

Skannern strict-läge är grön på branchen frontend-christopher-import.

Skannern strict-läge är fortfarande grön på main (samma resultat
som innan ADR 0018-importen).

Apps-viewser fortsätter scannas oförändrat.
