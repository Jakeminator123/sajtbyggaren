# ADR 0028 — runtime ladder för PreviewRuntime

**Status:** Accepted (ladder-idén lever; StackBlitz-nivån degraderad av 0033)
**Datum:** 2026-05-24
**Beroenden:** ADR 0003 (PreviewRuntime-abstraktion med StackBlitz först), `docs/product-operating-context.md`.

## Uppdatering (2026-06-15) — stege-idén gäller, men nivå-ordningen är omkörd

Själva idén — att `PreviewRuntime` är en abstraktion med flera nivåer för olika
ansvar — gäller fortfarande och bär 0030/0033. MEN den konkreta nivå 2 nedan
("`StackBlitzRuntime` är den användarnära och editbara previewnivån") är
**superseded/degraderad av ADR 0033**: `vercel-sandbox` är primär användarnära
preview, `local-next` är garanterad fallback, och `stackblitz` är **pausad**
(får finnas kvar men ska inte blockera, inte vara default, inte krävas i tester).
Läs alltså nivå-listan nedan som ursprunglig ansvarsmodell, inte som dagens
leverantörsval. De hårda portabilitetsreglerna (0030) bevaras av 0033.

Förfinas/degraderas av: ADR 0030 (providers är adapters), ADR 0033 (vercel-sandbox
primär, local-next fallback, stackblitz pausad).

## Kontext

Sajtbyggaren behöver preview-steg som hjälper kärnflödet utan att låsa
arkitekturen vid en leverantör för tidigt. Sprintvakt V1 byggs parallellt och
ska inte blockera ett smalt produktbeslut som hjälper agenter att hålla
riktning redan nu.

Det här beslutet är dokumentation och styrning. Det introducerar ingen
runtime-kod, ingen StackBlitz-implementation och ingen virtuell maskin.

## Beslut

`PreviewRuntime` är en abstraktion, inte en leverantör.

Runtime-nivåerna ordnas så här:

1. `LocalRuntime` är snabb intern/generated preview för utveckling,
   felsökning och operatornära iteration.
2. `StackBlitzRuntime` är den användarnära och editbara previewnivån när
   kärnflödet behöver en delbar browserupplevelse.
3. Production-/deploy-check är sista verifieringsnivå för att bevisa att en
   genererad sajt klarar produktionslika krav innan publicering.

Den här PR:en implementerar inte `StackBlitzRuntime`, production-/deploy-check
eller någon annan runtime. Om den sista nivån senare behöver kodnamn,
interface eller policyfält ska det låsas i en ny governance-ändring innan kod
skrivs.

## Konsekvenser

Positiva:

- Agenter kan prioritera preview-arbete utan att vänta på Sprintvakt V1.
- Leverantörsval hålls bakom `PreviewRuntime`.
- Snabb intern preview, användarnära preview och slutverifiering får olika
  ansvar.

Negativa:

- ADR 0003 nämner fortfarande `FlyRuntime` som tidigare kandidat för
  produktionslik verifiering. Den här ADR:n förtydligar nivån utan att byta
  implementation i kod.
- Det finns ännu ingen policy- eller kodmodell för production-/deploy-check.

## Utanför scope

- Ingen ändring i `packages/generation/`.
- Ingen ändring i `packages/preview-runtime/`.
- Ingen ändring i `apps/viewser/`.
- Ingen ändring i `scripts/build_site.py`.
- Ingen ändring i governance-policies.
- Ingen Sprintvakt-fil.
