delivery-bias: läs docs/delivery-bias.md innan ändringar som kan växa i
docs/tester/scope; förmåga före dokumentation, smal testbudget och tydlig
feature-pr-redovisning gäller.

Det här är det aktiva driftkontraktet för repo-agenter. Håll det kort, strikt
och färskt. Långa förklaringar bor i `docs/` — se länkarna nedan.

## Regelprioritet

Följ regler i denna ordning:

1. Användarens uppgift i den aktuella tråden
2. Den här filen (`AGENTS.md`)
3. `.cursor/BUGBOT.md` och reglerna under `.cursor/rules/`
4. Repo-docs som länkas härifrån
5. Generella modell-/verktygsdefaults

Vid konflikt: välj det säkrare alternativet och förklara konflikten. Är rätt
åtgärd oklar — stoppa och fråga Jakob. Redigera aldrig `.cursor/rules/`
direkt; de är genererade speglar. Ändra källan under `governance/rules/` och
kör `python scripts/rules_sync.py --check`.

## Kärnarbetssätt

Agera som en Cursor-kompatibel repo-agent för det här repot — samma kontrakt
oavsett om du körs från Cursor eller Codex-IDE. Föredra små, direkta ändringar
i förgrunden; läs tillräckligt med kontext för att undvika misstag och gör
sedan minsta nyttiga ändring. Undvik breda refaktoreringar om operatören inte
uttryckligen ber om dem.

Produktmålet är bättre småföretagshemsidor genom kärnloopen
`prompt -> företagshemsida -> preview -> följdprompt -> ny version`. För
icke-triviala produkt-/builder-ändringar, håll `docs/product-operating-context.md`
i sikte och parkera ändringar som inte hjälper loopen om operatören inte
uttryckligen prioriterar dem.

Kontextdocs att läsa vid behov:

- `docs/agent-handbook.md` — onboarding, hårda regler, roller, standard-loop
- `docs/agent-setup.md` — miljö, tjänster, fulla lint-/test-kommandon
- `docs/agent-gotchas.md` — miljöfällor (portar, tmux, Vercel/Viewser, evals-dir)
- `docs/product-operating-context.md` — produktkompass och prioriteringsfilter
- `docs/delivery-bias.md` — scope/testbudget innan breddande ändringar
- `docs/orchestrator-playbook.md` — fleragentpass (arbetssätt, inte fjärde fast roll)
- `docs/testing.md`, `docs/known-issues.md`

## Notis om shell-kommandon på Windows (Jakob/jakob-be)
> ⚠️ **OBS! (Gäller endast för "jakob" och "jakob-be"):**  
> De agenter som körs av användaren "jakob" eller "jakob-be" (inklusive ALLA
> underagenter/subagenter de spawnar) kör nästan alltid i **PowerShell på
> Windows** — inte bash. Skriv kommandon i PowerShell-syntax från början.
>
> **Gör (PowerShell-säkert):**
> - Kedja sekventiellt med `;` — eller hellre flera separata shell-anrop.
>   (`&&`/`||` funkar först i PowerShell 7+; anta inte att de finns.)
> - Miljövariabler: `$env:NAMN` (sätt per-process), aldrig `export`/`VAR=x cmd`.
> - Sökvägar med mellanslag: dubbla citattecken; backslash är INTE escape-tecken.
> - Flerradigt innehåll till fil: skriv en tempfil med `Out-File`/`Set-Content`
>   (välj `-Encoding` medvetet) och peka på den (t.ex. `curl.exe --data-binary "@fil"`).
> - Native binärer: skriv `curl.exe` — blotta `curl` är i PowerShell ett alias
>   till en inbyggd webb-cmdlet, inte riktiga curl.
> - Tysta fel: `2>$null` eller `-ErrorAction SilentlyContinue`, inte `2>/dev/null`.
>
> **Gör INTE (bash-ismer som tyst går sönder):**
> - Heredocs (`<<EOF`), `$(...)`-subshells i bash-stil, `export`, `which`
>   (använd `Get-Command`), `head`/`tail`/`grep`/`sed`/`awk` som kommandon
>   (använd specialverktygen eller `Select-Object`/`Select-String`),
>   enkelfnuttar runt strängar som ska interpoleras.
> - Newline-separerade kommandon i ETT shell-anrop.
>
> **Särskilt viktigt:** Bash-skript/kommandon som genereras HÄR men ska köras
> i unix-miljö (GitHub Actions, moln-VM, Vercel sandbox) kan få fel radslut
> (CRLF) eller trasiga heredocs. Ange explicit Unix-EOL (LF) för sådana filer
> och testa i bash-miljö när de är pipeline-kritiska.  
> Detta gäller dock *enbart* sessioner/agentkörningar för "jakob" och "jakob-be".

## Underagenter — sparsamhet (operatörspreferens 2026-06-11)

Spawna underagenter sparsamt, inte som standard. Gör små och medelstora
uppgifter själv i förgrunden. Delegera bara när det ger verkligt värde: långa
körningar, äkta oberoende parallella spår, eller arbete som annars skulle
krocka i huvudcheckouten. När du ändå delegerar, föredra read-only rapport-
eller scout-agenter som tar fram underlag du läser och agerar på, framför
flera skrivande underagenter samtidigt. Detta är en mjuk standard, inte ett
förbud — fler agenter är okej när det tydligt hjälper. Samma anda finns i
`docs/orchestrator-playbook.md` (sektionerna om underagenter och parallelisering).

## READ-ONLY reference projects (NEVER modify)

These external folders are **strictly read-only reference material**: never
create, edit, delete, rename, move, format, lint, commit or write to them in
any way (agent, subagent, script or git). You MAY read and study them freely.

- `C:\Users\jakem\Desktop\openclaw\`
- `C:\Users\jakem\dev\projects\sajtmaskin\`
- any other folder named `sajtmaskin`, wherever it is on disk.

If a change there seems necessary, STOP and ask the operator first. The repo's
own OpenClaw work happens ONLY inside this repo
(`packages/generation/orchestration/openclaw/`, `openclaw-mvp/`, `apps/`,
`scripts/`). What each reference contains: see `docs/reference-projects.md`.

## Lint, test och validering (kort)

- Lint: `python -m ruff check .`. The ruff baseline is **0 findings** — every
  new finding is a real bug to fix, not a `noqa` candidate (a `noqa` must be
  backed by an ADR). Fix new findings in dedicated `chore: ruff auto-fixes`
  commits, never mixed with feature work. `tests/test_docs_freshness.py`
  enforces that this number matches reality.
- Tester: riktade sviter för ändrade filer/paket är lokal default före commit
  (`python -m pytest tests/test_<area>*.py -q` eller core-lane
  `python -m pytest -m core -q`). Full svit kör i CI på varje PR och är
  merge-gate; lokalt bara vid breda ändringar:
  `python -m pytest tests/ -q -n auto` (pytest-xdist; se `docs/testing.md`).
- Governance: `python scripts/governance_validate.py && python scripts/rules_sync.py --check && python scripts/check_term_coverage.py --strict`.
- Fler kommandon och tjänster (backoffice, engine run, builder, Viewser): se
  `docs/agent-setup.md`. Miljöfällor: se `docs/agent-gotchas.md`.

## Miljö och secrets

Operator-grant (Jakob, 2026-06-02; utökad 2026-06-03): agenten får läsa och
redigera ALLA `.env*`-filer var som helst i repot (repo-root, `apps/viewser/`
och valfri undermapp) plus `.cursorignore`, `.vercel/` och `.cursor/` som del
av builder-/preview-/orkestreringsarbete. Skriv aldrig ut riktiga
secret-värden i svar (använd redigerade former som "OPENAI_API_KEY är satt"),
och committa aldrig `.env*` eller `.cursor/mcp.json` (de förblir gitignorerade).

Vercel-sandbox-preview lokalt kräver en färsk `VERCEL_OIDC_TOKEN` (`vercel env
pull apps/viewser/.env.vercel.local`, ~12h TTL) i processens miljö plus
`VIEWSER_PREVIEW_MODE=vercel-sandbox`. Cloud Agent-secrets kan override:a
`apps/viewser/.env.local` — fulla detaljer i `docs/agent-gotchas.md`.

## Språk och namngivning

Kod-identifierare och JSON-fältnamn på engelska; operatör-vänd text (docs,
regler, UI-labels) på svenska med riktiga å/ä/ö. Undvik versala flerordsfraser
i backticks/fetstil i `.md` om de inte står i naming-dictionary —
`check_term_coverage.py --strict` flaggar dem.

## Stoppvillkor

Stoppa och fråga Jakob före: ändringar i read-only-referensprojekten ovan,
exponering av secrets, breda arkitekturomskrivningar som inte efterfrågats,
byte av governance-/regelsystem, radering av historiska docs, destruktiv
städning utanför repot, eller manuell ändring av `.cursor/rules/`. Är den säkra
vägen uppenbar — ta den och förklara kort.
