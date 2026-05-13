<!--
Fyll i alla rubriker. Tomma sektioner blockar review. Skala kommentarer
efter PR-storlek - en doc-rad behöver inte halv-sida verifiering, men
fälten ska finnas så ro-review-agent och operatör vet vad de tittar på.
-->

## Scope

<!-- En mening: vad löser PR:en och vilket spår tillhör den (B-ID, ADR, etappnummer)? -->

## What changed

<!-- Punktlista över faktiskt ändrade filer + kort vad varje fil gör annorlunda. -->

## What did **not** change

<!-- Lika viktigt. Räkna upp filer/områden som ligger nära men medvetet är orörda. Hjälper ro-review-agent att avfärda scope-läckage snabbt. -->

## Verification

<!--
Kopiera kommandona du faktiskt körde + resultat. Standard-kedjan:

- python scripts/review_check.py
- (vid starter-ändring) cd data/starters/<starter>; npm ci; npm run build; npm run lint

Om verifieringen är hoppad - skriv varför.
-->

## Known risks / blockers

<!-- Lista eller "inga". Inkludera saker som "blockerar B-ID X" eller "kräver miljövariabel Y". -->

## Ready / merge recommendation

<!-- Ett av:
- Ready, kan squash-mergeas.
- Draft, väntar på <namn på beslut>.
- Behöver fix-runda först.
-->

## Post-merge sanity needed

<!-- Ja/nej. Ja om PR rör main-build, governance, eller schemas. -->
