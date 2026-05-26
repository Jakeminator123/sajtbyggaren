# Cloud-grind-prompt 2 — B147 host-whitelist (ersätt env-bypass)

> **Copy-paste hela detta block som första prompt i en ny Cursor Cloud Agent-session.**
> Agenten ska kunna jobba self-contained utan att läsa andra docs.

---

Du är Builder-agent som kör i en cloud-agent-VM (Ubuntu). Repo: `Jakeminator123/sajtbyggaren`. Arbets-branch: **`jakob-be`** (Jakob-lane, men prompten rör en UI-lib-fil — operatör har redan godkänt scope-leak via samma precedent som PR #68/#71). Du touchar bara GitHub-remoten.

## Mission

Stäng **B147** (Vercel preview wizard 403 via `assertLocalhost`) genom att lägga till en host-whitelist (`VIEWSER_ALLOWED_HOSTS`) istället för att tvinga operatören använda `VIEWSER_ALLOW_NON_LOCALHOST=true` (som öppnar 12 API:er för **alla** hostar utan auth).

Dagens läge (verifierat 2026-05-26): `apps/viewser/lib/localhost-guard.ts` har bara localhost-check + en boolean env-flagga. Om operatören sätter den env-flaggan blir hela API-ytan publik. Det är **väg (a)** i `docs/known-issues.md` B147-analysen — fungerar men accepterar "no auth, no rate limit, no public deploy"-modellen på en publik URL.

Den här prompten implementerar **väg (b)**: comma-separated host-lista som klarerar specifika Vercel preview-/production-domäner utan att helt öppna API:erna.

## Branch + förutsättningar

```bash
git fetch origin --prune
git switch jakob-be
git pull --ff-only origin jakob-be
git status                  # ska vara clean
git log --oneline -5
```

Stoppa om `git pull --ff-only` failar (annan cloud-agent har pushat under tiden — be operatören koordinera).

## Tillåtna paths (write-set)

- `apps/viewser/lib/localhost-guard.ts` — utöka `assertLocalhost` med whitelist-stöd.
- `apps/viewser/lib/localhost-guard.test.ts` (skapas om den inte finns) — vitest/jest-spec som låser whitelist-beteendet.
- `apps/viewser/vercel.json` — om miljövariabel måste deklareras där. Verifiera först om Vercel-projektets `vercel.json` redan stödjer custom env (idag handlar `vercel.json` om build-config — kolla innan ändring).
- `docs/known-issues.md` — flytta B147 till "Stängda"-sektionen med commit-SHA + test-referens.
- `docs/architecture/viewser.md` — om den finns, dokumentera env-knappen där.

## Off-limits paths (do not touch)

- `apps/viewser/components/**` (Christopher-lane).
- `apps/viewser/app/**/*.tsx` (Christopher-lane).
- `apps/viewser/app/api/**/*.ts` — alla API-routes använder `assertLocalhost` men ändras inte av denna prompt; den nya logiken landar bara i `localhost-guard.ts`.
- `governance/policies/**`.
- `packages/generation/**`.
- `scripts/**`.

## Acceptanskriterier

1. Ny env-variabel `VIEWSER_ALLOWED_HOSTS` läses i `assertLocalhost`. Den är en comma-separated lista av exakta hostar (utan port). Exempel: `VIEWSER_ALLOWED_HOSTS="sajtbyggaren-viewser.vercel.app,sajtbyggaren-viewser-jakob-be.vercel.app"`.
2. `assertLocalhost`-flödet blir: (a) om `VIEWSER_ALLOW_NON_LOCALHOST=true` → tillåt (bakåtkompatibel escape-hatch), (b) annars om host i `LOCAL_HOST_NAMES` → tillåt, (c) annars om host finns i `VIEWSER_ALLOWED_HOSTS`-listan → tillåt, (d) annars → 403.
3. `VIEWSER_ALLOWED_HOSTS` parsas en gång per request (eller cachas — det är OK eftersom Vercel-deploys är immutable). Tomma värden och whitespace trimmas. Case-insensitive jämförelse (samma som existerande `hostFromHeader`).
4. 403-felmeddelandet uppdateras så det nämner båda env-knapparna:  
   `"Viewser är localhost-only. Sätt VIEWSER_ALLOWED_HOSTS=<host> för specifika domäner eller VIEWSER_ALLOW_NON_LOCALHOST=true för full bypass."`
5. JSDoc-kommentaren på `assertLocalhost` förklarar nya knappen.
6. Nya tester (minst 5) i `localhost-guard.test.ts`: (a) localhost passerar, (b) icke-listad host får 403, (c) host i `VIEWSER_ALLOWED_HOSTS` passerar, (d) `VIEWSER_ALLOW_NON_LOCALHOST=true` passerar oavsett host, (e) tom `VIEWSER_ALLOWED_HOSTS` faller tillbaka till bara localhost.
7. `docs/known-issues.md` B147-entry flyttas från "Öppna" till "Stängda" med fix-commit-SHA + test-fil-referens. Inkludera kort note att `VIEWSER_ALLOW_NON_LOCALHOST=true`-vägen finns kvar som fallback.
8. `cd apps/viewser && npx tsc --noEmit` + `npm run lint` ska vara gröna.
9. Python-guards (sprintvakt, governance, term-coverage, ruff) ska vara gröna — denna prompt ska inte påverka dem, men kör för att verifiera ingen drift.

## Tekniska tips

- Lägg till en modul-scope `Set<string>` som cachas vid första anrop, eller läs `process.env` vid varje anrop. Vercel-deploys är immutable så env är konstant inom en deploy — caching är OK och billigare.
- Trim + lowercase host-listan så jämförelse är säker mot whitespace ("a.com, b.com").
- Existerande `isAllowedHost(hostHeader)`-helpern kan utökas eller en parallel `isWhitelistedHost(hostHeader)` läggs till — det är upp till agenten. Föredra minimal yta.

## Final guards (alla ska vara gröna före push)

```bash
( cd apps/viewser && npx tsc --noEmit && npm run lint )
python -m ruff check .
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python scripts/sprintvakt_check.py
python -m pytest tests/ -q
```

Pythontesterna ska passera oförändrade (inga av dem rör `localhost-guard.ts`).

## Stoppvillkor

Stoppa och rapportera om:

- TS-typecheck failar och du inte kan motivera fixet inom write-set.
- Du behöver röra någon API-route-fil (de använder bara `assertLocalhost` — om nytt API behövs är det egen sprint).
- `docs/known-issues.md` är så stort att flyttning blir riskfylld — i så fall lämna det till Steward via Prompt 3.

## Commit-format

En atomisk commit:

```
feat(viewser): close B147 — add VIEWSER_ALLOWED_HOSTS for Vercel preview without full bypass

- localhost-guard.ts now supports a comma-separated whitelist of public
  hosts (Vercel preview/production domains) without dropping the
  no-auth/no-rate-limit guarantee for unknown hosts.
- The legacy VIEWSER_ALLOW_NON_LOCALHOST=true escape hatch stays as a
  blunter fallback.
- Adds <N> vitest specs in localhost-guard.test.ts and moves B147 to
  Stängda in docs/known-issues.md.
```

## Push

```bash
git push origin jakob-be
```

Ingen PR. Operatören sätter `VIEWSER_ALLOWED_HOSTS` i Vercel-projektets env (Preview + Production) som separat steg.

## Rapport tillbaka till operatör

```
Pushed <SHA> till origin/jakob-be.
B147 stängd: VIEWSER_ALLOWED_HOSTS host-whitelist + bibehållen fallback.
<N> vitest-tester gröna. Alla python-guards gröna.
Bug-count: 14 -> 13 aktiva.

Operatör måste manuellt sätta i Vercel-projektets settings → Environment Variables:
  VIEWSER_ALLOWED_HOSTS = sajtbyggaren-viewser.vercel.app,<eventuella-preview-doman>

(Eller behåll VIEWSER_ALLOW_NON_LOCALHOST=true om du föredrar väg (a).)
```

## Parallellitet

- **OK att köra parallellt med:** Prompt 1 (Gap 6+7), Prompt 3 (doc-städ), Prompt 4 (Gap 9), Prompt 5 (Gap 10). Den här prompten rör bara `apps/viewser/lib/localhost-guard.ts` + docs, vilket är disjunkt från alla andra promptars write-set.
- **Inga dependencies.** Kan starta när som helst.
