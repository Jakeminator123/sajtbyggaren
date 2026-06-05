# ADR 0004: Migration från sajtmaskin-baseline (kontrollerad rekonstruktion)

- Status: accepterat
- Datum: 2026-05-07

## Kontext

`Jakeminator123/sajtmaskin@master` har för bred yta, för många namnskuggor och för mycket parallellt arbete för att återanvändas wholesale. Två externa utlåtanden plus en review (`referens/utlatanden/utlatande-1-rebuild-vs-restore.txt` och `referens/utlatanden/utlatande-2-llm-flode.txt`, borttagna i #191, finns i git-historiken) pekar på samma slutsats: kontrollerad rekonstruktion, inte blank-slate.

Tre April-taggar i sajtmaskin är intressanta som generation-baskandidater:

- `ba33b28` - "baseline-before-design-priority". Liten build-fix-commit; explicit baseline innan Design Priority-lagret tillkom (commit `bbc0910f` ~10 minuter senare).
- `1f4e869` - "restore-milstolpe-4232ab3". Mer konkret commitmeddelande: återställning av LLM-kedjan till "milstolpe"-kvalitet, "simpler pipeline, richer prompts".
- `04b3215` - "milestone-best-version". Liten cleanup-commit men taggens namn antyder högsta kvalitet hittills; bevisas inte av commit-innehållet ensamt.

## Beslut

Sajtbyggaren bygger inte upp generation-kärnan från noll och ärver inte heller sajtmaskins master rakt av. Istället:

1. Vi börjar med governance + backoffice + preview-runtime-interface i Sajtbyggaren.
2. Innan generation-kärnan börjar implementeras kör vi en deterministisk eval-batch (5-10 företagshemside-prompts) mot kandidat-baserna `ba33b28`, `1f4e869` och `04b3215` lokalt och väljer den som ger högst poäng på `page-quality-traits.v1.json`.
3. Vald baseline blir referens för hur generation-prompten, scaffolds och dossiers tas in. Vi importerar inte koden som-är; vi förstår och återskapar i ny struktur.
4. Februari-commits `3e7ca17`, `a5b4fb2` (builder/auth) och `29971fb`, `9eccc75` (stream UX) plockas selektivt om motsvarande funktion behövs - inte hela Februari-trädet.
5. Sajtmaskins glossary och source-of-truth-policy (från `main`) inspireras till `naming-dictionary.v1.json` här, men förenklas radikalt.

## Konsekvenser

- Det går inte att "starta sajtbyggaren" i full mening innan baseline-evalen är gjord. Backoffice och governance kan dock byggas oberoende.
- Migrationsplanen i `docs/migration-plan.md` underhåller listan över vad som plockats från vilken sajtmaskin-commit.
- Referensmaterialet låg under `referens/` (se `referens/README.md` för indelning). Mappen raderades i #191 (operatörsbeslut: externt inspirationsmaterial, inte produktkod); innehållet finns kvar i git-historiken.
