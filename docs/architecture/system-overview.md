# Systemöversikt

Sajtbyggaren bygger hemsidor och appar åt företag på en kvalitet som siktar på `~9.0/10` enligt [`page-quality-traits.v1.json`](../../governance/policies/page-quality-traits.v1.json).

## Tre lager

```text
governance/   <-- sanningskälla (JSON-policies + schemas + rules + decisions)
   ^
   | redigeras av
   |
backoffice.py <-- Streamlit-backoffice (operatören)
   |
   | speglar regler till
   v
.cursor/rules <-- Cursor-agent-regler (auto-genererade speglar)

governance/   <-- sanningskälla
   |
   | läses av
   v
packages/     <-- runtime: generation, builder, preview-runtime, policies, shared
apps/         <-- web/api som konsumerar packages
```

## Komponenter

| Mapp | Roll | Får importera |
|------|------|--------------|
| `governance/` | Policies, schemas, regler, beslut | (inget; rotsanning) |
| `backoffice.py` | Streamlit-backoffice | `governance/`, `scripts/`, `data/` |
| `scripts/` | Validering, sync, evals | `governance/`, `data/` |
| `packages/policies` | Typade laddare | `governance/` |
| `packages/generation` | LLM-flöde fas 1-3 | `packages/{policies,shared,builder}` |
| `packages/builder` | Version-livscykel | `packages/{policies,shared,generation}` |
| `packages/preview-runtime` | StackBlitz/Fly/Local-adaptrar | `packages/shared` |
| `packages/shared` | Primitives | (inget) |
| `apps/web` | UI | `packages/{policies,shared}`, `apps/api` |
| `apps/api` | HTTP-yta | alla `packages/` |
| `tests/evals` | Quality-gate-batch | `packages/`, `governance/` |
| `data/` | Lokal persistent state | (inget) |

Detaljer: se [`repo-boundaries.v1.json`](../../governance/policies/repo-boundaries.v1.json).

## Princip

LLM:en är inte arkitekt. Den är exekutor av en arkitektur som policies styr. Det betyder att:

- Kvalitet ändras genom att redigera `page-quality-traits.v1.json`, inte genom att fippla med prompts.
- Begrepp är låsta i `naming-dictionary.v1.json`. Inga synonymer.
- Mappägarskap är låst i `repo-boundaries.v1.json`. Brott blockerar review.
- Preview-strategi är låst i `preview-runtime-policy.v1.json`. StackBlitz först, EN quality gate.
