# Handoff 2026-05-27 — gap-batch klar

## Verifierat läge

- `jakob-be` är på `91230b4` efter steward-städning ovanpå Gap 10-merge.
- PR #122 är squash-mergad till `jakob-be` som `3b61c73`.
- Backend-gap 1-11 från `docs/backend-handoff.md` är stängda.
- `origin/main` ligger kvar på `1004122`; `jakob-be` är 38 commits före
  `origin/main` efter gap-spec-städningen.

## Landat sedan senaste större sync

- Gap 6 + 7: favicon/OG-image-konvertering (`ea6e141`).
- B147: `VIEWSER_ALLOWED_HOSTS` för Viewser preview utan full bypass
  (`b3834b3`).
- Gap 9: `moodImages` isoleras till `data/uploads/<siteId>/__mood/`
  (`365c1d7`).
- Gap 10: `products[].productImage` går end-to-end via Project Input,
  `public/products/` och produktgrid (`3b61c73`).
- Steward-städning: avslutade cloud-grind-prompter och färdiga gap-specar
  bortstädade, workboard-reservationer rensade, eval-output-dokumentation
  justerad (`6222627`, `91230b4`).

## Nästa rekommenderade steg

1. Öppna sync-PR `jakob-be → main`.
2. När sync-PR är mergad: synka `jakob-be` till `origin/main` enligt
   branch-disciplinen.
3. När Christopher öppnar PR för `GAP-backend-build-trace-endpoint`: Jakob
   reviewar scope-leak-implementationen och kontrollerar workboard-owner.

## Kända saker att inte blanda in

- `B125` preview-fallback, B13a arkitekturflytt, embeddings, SNI-runtime,
  variant-promotion och nya starters är parkerade tills operatören väljer
  en ny sprint.
- Root- och app-kopior av `SM_hero.mp4`/`LOGO_SM2.0.png` finns fortfarande;
  B115 är inte stängd.
- Äldre stashar finns kvar för gamla preview-mode-branches. De är inte del
  av dagens `jakob-be`-läge.
