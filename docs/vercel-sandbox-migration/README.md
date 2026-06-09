# vercel-sandbox-migration — körschema

Den här mappen är en planeringsyta (inte kod). Den beskriver hur Sajtbyggaren går
från dagens lokala operatörsverktyg till en hostad produkt där användarens sajter
byggs och förhandsvisas i sandboxar — i stil med v0 eller Lovable, via en iframe
(eller en modernare motsvarighet) med en chatt för följdfrågor.

Innehållet är skrivet för att arbetas igenom steg för steg med agenter: varje fas i
`02-korschema.md` har en färdig prompt du kan klistra in till en ny agent. Kör en
fas i taget, läs av resultatet, gå vidare.

## Filer
- `00-nulage-och-mal.md` — var vi är idag, vart vi ska, och gap-listan.
- `01-arkitekturval.md` — besluten som måste fattas per gap (med alternativ).
- `02-korschema.md` — de sekvenserade agent-prompterna (huvudleveransen).
- `03-risker-kostnad-oppna-fragor.md` — risker, kostnad och öppna frågor.

## Hostad deploy idag

Hur den hostade Viewser-deployen ser ut just nu — vad som fungerar och vad som är
ärligt gatat — beskrivs i [`docs/hosted-viewser-deploy.md`](../hosted-viewser-deploy.md).
Det är en auth-gatad skiva av P1 (deploy-skalet) nedan.

## Snabbsvar på två frågor

Funkar allt på Vercel nu? Nej. Idag funkar loopen bara lokalt: `/api/prompt` och
`/api/preview/[siteId]` är localhost-låsta, och bygget shellar ut till Python
(`scripts/build_site.py`). En hostad deploy saknar både Python och localhost, och
koden degraderar själv där (`isHostedVercelRuntime` -> `hostedPythonRuntimeUnavailable`).
Det enda som redan kör i Vercel-molnet är själva sandbox-previewen. Den här mappen
är planen för att stänga gapet.

Kan plugin-skillen för vercel-sandbox användas? Delvis. Skill-filen handlar om att
köra agent-browser (headless webbläsare) i en sandbox, inte om att hosta
användarsajter. Men dess SDK-mönster — skapa sandbox, köra kommandon,
`sandbox.domain(port)`, auth via OIDC eller token, och framför allt snapshots för
snabb uppstart — är exakt det som `apps/viewser/lib/vercel-sandbox-runner.ts` redan
använder. Största direktvinsten därifrån: snapshots som pre-installerar beroenden en
gång, så previewen bootar på under en sekund i stället för dagens ~30 s kallstart.
Se `01-arkitekturval.md` (G5).

## Spelregler för agenter (gäller alla prompter)
- Kodidentifierare och JSON-fält på engelska; operatörstext (docs och UI) på svenska.
- Rör INTE `docs/heavy-llm-flow/` (en annan agent äger den mappen).
- Redigera ALDRIG `.cursor/rules/` direkt — källan ligger i `governance/rules/`.
- Skriv nya arkitekturbeslut som ADR under `governance/decisions/` (nästa lediga nummer).
- Jobba på egen branch, committa, öppna PR — merga ALDRIG till `main` själv.
- Kör guards före commit: `python -m ruff check .`, `python -m pytest tests/ -q`,
  `python scripts/governance_validate.py`, `python scripts/rules_sync.py --check`,
  `python scripts/check_term_coverage.py --strict`.
- term-coverage flaggar versaliserade ord och fraser i backticks eller fetstil i
  `.md`. Undvik dem (skriv hyphenated-lowercase, eller registrera via ADR plus
  naming-dictionary).
