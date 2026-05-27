# Cloud-grind-promptar — avslutad backend-gap-batch

Den här mappen innehåller **fristående copy-paste-promptar** för Cursor Cloud Agents (eller motsvarande cloud-agent som har repo-write-access via GitHub). Varje cloud-agent klonar repot från `github.com/Jakeminator123/sajtbyggaren`, jobbar i sin Ubuntu-VM, pushar till `origin/jakob-be` och slutar. **Operatörens lokala maskin är inte i loopen alls** — det enda touchground är GitHub-remoten.

Operatören öppnar ett nytt cloud-agent-fönster, klistrar in en av prompterna som första meddelande, och låter agenten köra till push.

Varje prompt-fil är self-contained: agenten ska inte behöva läsa något annat docs/-material för att kunna jobba. Den deklarerar branch, scope, off-limits, acceptanskriterier, tester och commit-format — alla kommandon är bash/Linux (cloud-VM:n är Ubuntu, ingen venv-aktivering krävs eftersom systempython + `pip install -r requirements.txt` förutsätts redan ha körts som setup-steg).

## Läget nu

Prompterna 1-5 är körda och bortstädade ur denna mapp:

- Prompt 1 stängde Gap 6 + 7 i `c002aec` + `ea6e141`.
- Prompt 2 stängde B147 i `b3834b3`.
- Prompt 3 körde docs/workboard-sync i `cb07dbb` och efterföljande steward-commits.
- Prompt 4 stängde Gap 9 i `365c1d7`.
- Prompt 5 stängde Gap 10 i PR #122 / `3b61c73`.

Det finns ingen kvarvarande cloud-grind-prompt i denna batch. Nästa naturliga steg är sync-PR `jakob-be -> main`.

## Prompt-katalog

Inga aktiva promptfiler.

## Parallellitet-matris

Batchen var sekventiell eftersom Gap 6/7, Gap 9 och Gap 10 delade `scripts/build_site.py`-yta.

## Operatörens trigger-ordning (rekommenderad)

```
Alla fem klara. Sync-PR-fönster: gör nu (jakob-be → main).
```

Varje prompt går att stoppa när som helst — de är atomiska.

## Sync-PR-fönster

`jakob-be` är just nu över 30 commits framför `origin/main`. Bra läge för sync-PR är nu, så hela gap-batchen + B147 + doc-städet blir officiell `main`.

## Övergripande disciplin

Varje prompt slutar med samma rapport-rad:

```
Pushed <SHA> till origin/jakob-be. Guards alla gröna: ruff 0,
governance 18/18, rules_sync OK, term-coverage --strict OK,
sprintvakt OK, pytest grön. Klar — vänta operatörens nästa instruktion.
```

Cloud-agenten **öppnar ingen PR** själv — sync-PR `jakob-be -> main` är operatörens beslut.

Cloud-agenten **rör inte** `apps/viewser/components/**`, `apps/viewser/app/**/*.tsx`, `apps/viewser/public/**` om inte prompten uttryckligen säger det (Christopher-lane).

## Cloud-VM-förutsättningar

Innan en agent börjar, ska VM:n ha:

- Repot klonat till en arbets-katalog och `git switch jakob-be` körts.
- `pip install -r requirements.txt` körd (för python-guards + ev. nya deps som promptarna lägger till).
- `cd apps/viewser && npm install` körd om prompten ska köra UI-typecheck/lint.
- `git config user.name` + `git config user.email` satta så commits får rätt author.
- GitHub-push-token (Personal Access Token eller GitHub App-installation) konfigurerad så `git push origin jakob-be` lyckas.

Om något av detta saknas: cloud-agenten ska stoppa direkt med felmeddelande till operatören istället för att försöka workaround-fixa.
