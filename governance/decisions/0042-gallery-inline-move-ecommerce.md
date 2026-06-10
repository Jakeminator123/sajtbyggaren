# ADR 0042 — section_add slice 4: galleri som flyttbar inline-sektion + ecommerce-lite

**Status:** Accepted
**Datum:** 2026-06-10
**Beroenden:** ADR 0038 (synlig section_add som `directives.mountedSections` —
grindarna och directive-formatet återanvänds oförändrade). Referens:
[`docs/agent-inbox.jsonl`](../../docs/agent-inbox.jsonl) (topics:
module-dragdrop-prep, placement-pick).

## Kontext

ADR 0038 slice 1 gjorde `hours` synlig som inline-block på
`local-service-business`-home och parkerade "fler scaffolds/typer" som slice 4.
Operatörsfynd 2026-06-10 (1753-skincare, `ecommerce-lite`): drag-and-drop
"lägg till en galleri-sektion överst" i buildern gav `applied=true` men ingen
synlig förändring — gallery var mount-only utanför local-service-business, och
gallerisektionen låg dessutom REDAN i `render_home`s default-ordning (mitt på
sidan, den renderas så fort galleri-bilder finns). Routerns positionsmål
("överst") kastades därmed bort två gånger: dels av scaffold-gaten, dels av
ADR 0038:s dubblettgrind (b) som droppar en post vars sektion redan finns i
route-ordningen.

`gallery` skiljer sig från `hours` på exakt en punkt: `hours-summary` finns
ALDRIG i default-ordningen (injektion = ny sektion), medan `gallery` ofta
redan finns där (placering = flytt av befintlig sektion).

## Beslut

1. **`gallery` blir en inline-placering** i `INLINE_SECTION_PLACEMENTS`
   (`packages/generation/followup/section_directives.py`):
   `gallery -> {sectionId: "gallery", routeId: "home"}`. Ingen ny renderare —
   `render_section_gallery` är redan registrerad och grundad på
   `dossier.gallery`.
2. **`ecommerce-lite` läggs till i `INLINE_SECTION_SCAFFOLDS`.** Dess home
   emitteras av SAMMA `render_home`-shim som local-service-business (den är
   inte i `_DISPATCHED_SCAFFOLDS`), så injektions-sömmen är redan trädd —
   inga nya render-vägar. Render-tidsallowlisten
   (`renderers._INLINE_SECTION_ALLOWLIST`) speglas till
   `{hours-summary, gallery}` för båda scaffolds (paritetslåst av
   `tests/test_section_directives.py`).
3. **Flytt-semantik för redan närvarande sektioner.** ADR 0038:s grind (b)
   ("ingen dubblett") förfinas: en `mountedSections`-post vars `sectionId`
   redan finns i routens default-ordning är en FLYTT när posten bär en
   explicit position (`top`/`bottom`/`before-contact`) — renderaren tar bort
   default-förekomsten och sätter in sektionen på operatörens slot, så den
   renderas exakt en gång. UTAN explicit position behålls dagens beteende
   (ärlig no-op, byte-identisk output) så befintliga directives aldrig
   skiftar layout retroaktivt.

## Ärlighetsgrindar (oförändrade utöver flytten)

Grindarna (a) registrerad renderare, (c) grundat innehåll och (d) scaffold-
allowlist från ADR 0038 gäller oförändrat. En galleri-flytt utan uppladdade
bilder förblir mount-only (renderaren returnerar tom sträng); en flytt på en
osanktionerad scaffold droppas av allowlisten. `appliedVisibleEffect` ägs
fortsatt av den deterministiska fil-diffen — en flytt blir synlig för att
`app/page.tsx`-bytes faktiskt ändras, aldrig genom att vi påstår det.

## Konsekvenser

- "Lägg till en galleri-sektion överst/längst ner" ger nu en synlig,
  positionstrogen förändring på både local-service-business och
  ecommerce-lite (`appliedVisibleEffect=true`, `affectedRoutes=["home"]`).
- Beteendebevarande: utan explicit position är output byte-identisk med idag
  (låst av `tests/test_home_section_inject.py`); `hours`-flödet rörs inte.
- Viewser-modulkatalogens galleri-kort uppgraderas från "syns inte än" till
  den ärliga inline-märkningen (gated på uppladdade bilder + scaffold).
- Schemat rörs inte (`mountedSections`-posterna är oförändrade).

## Utanför scope (kommande slices)

- Övriga mount-only-typer (pricing/map/contact-form/trust/reviews) — samma
  mönster kan följa när respektive sektion har en home-kompatibel renderare
  med grundat innehåll.
- Fler routes än `home`, finkornig ordinal-placering, och `sizePercent`
  (skickas redan strukturerat i UI:ts toolIntent men konsumeras inte av
  byggaren än).
