---
status: active
owner: backend
truth_level: summary
last_verified_commit: f56ac30
---

# Systemöversikt

Sajtbyggaren bygger företagshemsidor på en kvalitet som siktar mot `~9.0/10`
enligt [`page-quality-traits.v1.json`](../../governance/policies/page-quality-traits.v1.json).
Kärnloopen är `prompt -> företagshemsida -> preview -> följdprompt -> ny version`.

## EN repo — inga nästlade repon

Det här är **ett enda git-repo** (monorepo). Det finns inga sub-repon i repot.
Känslan av "repo-i-repo" kommer från att flera projekt bor i samma historik:

```text
sajtbyggaren/                 <- ETT git-repo (allt versionas härifrån)
├─ .vercel/                   <- länk: repot -> Vercel-projektet (deploy-rot = apps/viewser)
├─ governance/                <- sanningskälla: policies + schemas + rules + decisions
├─ packages/                  <- Python-runtime: generation, builder, preview-runtime, policies, shared
├─ scripts/                   <- build_site.py, dev_generate.py, validatorer
├─ backoffice.py              <- Streamlit-backoffice (operatören)
├─ apps/viewser/              <- Next.js operatörs-UI (= Vercels deploy-rot)
│   └─ .env.local / .env.vercel.local   <- lokala hemligheter (gitignored)
├─ data/                      <- runs, starters, lokal state (mest gitignored)
└─ ../sajtbyggaren-output/    <- GENERERADE kundsajter (UTANFÖR repot)
```

- `data/starters/<id>/` = färdiga Next.js-basprojekt vi vendorat in; deras egna
  `.git`-mappar är strippade, så det finns inga nästlade git-repon.
- `apps/viewser/` är en undermapp, inte ett eget repo. Vercel deployar bara den
  (deploy-rot = `apps/viewser`); därför ligger `.vercel/` i roten och pekar dit.
- De färdiga kundsajterna skrivs utanför repot (`../sajtbyggaren-output/`).

## Två lager

```text
Hjärnan (Python)      operatör / governance / builder — vad som ska byggas
   |   packages/generation/** · governance/** · scripts/ · backoffice.py
   v
Utdata (Next.js/TS)   den genererade kundsajten + apps/viewser operatörs-UI
```

Den deterministiska rälsen (scaffold/variant/dossier/starter/renderer) emitterar
**vanlig Next.js**. Det tunga LLM-flödet (se [`docs/heavy-llm-flow/`](../heavy-llm-flow/README.md))
är ett lager ovanpå som berikar samma artefaktkedja — det ersätter inte rälsen.

## Komponenter (mappägarskap)

| Mapp | Roll | Får importera |
|------|------|--------------|
| `governance/` | policies, schemas, regler, beslut | (inget; rotsanning) |
| `backoffice.py` | Streamlit-backoffice | `governance/`, `scripts/`, `data/` |
| `scripts/` | validering, sync, evals, `build_site.py` | `governance/`, `data/`, `packages/generation/*` |
| `packages/policies` | typade laddare | `governance/` |
| `packages/generation` | LLM-flöde fas 1-3 (brief/planning/orchestration/codegen/build/repair/quality_gate) | `packages/{policies,shared}` + interna fas-paket |
| `packages/builder` | version-livscykel | `packages/{policies,shared,generation}` |
| `packages/preview-runtime` | local/stackblitz/vercel-sandbox/fly-adaptrar | `packages/shared` |
| `packages/shared` | primitives | (inget) |
| `apps/viewser/` | localhost-operatörs-UI + API-routes som shellar ut till `build_site.py` | `packages/shared`, `data/runs/`, `examples/` |
| `data/` | lokal persistent state (runs, starters, versioner) | (inget) |

Komplett + auktoritativt: [`repo-boundaries.v1.json`](../../governance/policies/repo-boundaries.v1.json) (v10).

## Brancher (inte sub-repon)

- `jakob-be` — backend / heavy-LLM-lane (default för Python/generation/governance/scripts).
- `christopher-ui` — UI-lane (`apps/viewser/**`).
- `main` — canonical sanningsbranch. PR mot `main` per leveransfönster (operatörsbeslut).

## Princip

LLM:en är inte arkitekt — den är exekutor av en arkitektur som policies styr:

- Kvalitet ändras genom `page-quality-traits.v1.json`, inte genom att fippla med prompts.
- Begrepp är låsta i `naming-dictionary.v1.json`. Inga synonymer.
- Mappägarskap är låst i `repo-boundaries.v1.json`. Brott blockerar review.
- Preview körs via adaptrar; `vercel-sandbox` är primär/opt-in, `local` default
  (ADR 0030/0033). Genererad output förblir vanlig Next.js.
