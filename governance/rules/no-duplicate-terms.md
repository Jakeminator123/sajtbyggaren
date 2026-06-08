---
description: Ett begrepp får ha exakt ett kanoniskt namn och bo i exakt en huvudmapp.
alwaysApply: true
---

# Inga dubbla begrepp

## Regel

- Varje koncept i Sajtbyggaren får ha exakt **ett** kanoniskt namn enligt [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json).
- Varje koncept har exakt **en** ägarmapp enligt `ownerPackage` i samma policy.
- Inga "namnskuggor" tillåts: ord som betyder olika saker i olika kontexter ska byta till olika kanoniska termer.

## Vad som ledde till röran i sajtmaskin

I gamla repot blev orden `brief`, `scaffold`, `context`, `contracts`, `quality gate`, `preflight`, `autofix`, `template-library`, `shadcn`, `3D` och `game` namnskuggor som betydde olika saker i olika filer. Det vi gör annorlunda:

- `brief` är aldrig en lös sammanfattning. Det är `Site Brief` enligt naming-dictionary, alltid.
- `autofix` är aldrig generiskt. Skriv **mekanisk autofix** eller **LLM-fix** explicit.
- `quality gate` är inte F2 eller F3. Det finns EN gate. Tier-uppdelning får uppstå först om eval visar att det behövs.
- `preview` är `Preview Runtime`, inte VM, preview-host eller webcontainer. `sandbox` är bara tillåtet som registrerat alias under Preview Runtime (Vercel Sandbox), inte som fri catch-all-term.

## Hur det upprätthålls

- `scripts/governance-validate.py` kontrollerar att policy-filer matchar sina schemas och att inga `globallyForbidden`-termer dyker upp.
- Code review på pull requests ska aktivt avvisa nya synonymer som inte står i `aliasesAllowed`.
