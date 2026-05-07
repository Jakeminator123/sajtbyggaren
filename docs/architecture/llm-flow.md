# LLM-flöde

Sanningskälla: [`llm-flow-concepts.v1.json`](../../governance/policies/llm-flow-concepts.v1.json).

## Tre faser

### Fas 1 - Brief & Policy Resolution

Tar användarens prompt och producerar en kanonisk `Site Brief` plus en `Resolved Policy`. Här ska LLM:en bara strukturera och fylla i, inte uppfinna.

```mermaid
flowchart LR
    rawPrompt[Raw Prompt]
    siteBrief[Site Brief]
    intent[Intent Resolution]
    policy[Policy Resolution]

    rawPrompt --> siteBrief --> intent --> policy
```

| Steg | Kallar LLM? | Får inte göra |
|------|-------------|---------------|
| `raw_prompt` | nej | infer final design, choose scaffold, rewrite user intent |
| `site_brief` | ja | emit code, pick final preview runtime |
| `intent_resolution` | nej | duplicate brief schema, create new entry mode names |
| `policy_resolution` | nej | hard-code trait weights, invent quality dimensions |

### Fas 2 - Orchestration

Tar `Site Brief` + `Resolved Policy` och producerar `Generation Package` - den enda nyttolasten som får gå till codegen.

```mermaid
flowchart LR
    brief[Site Brief]
    scaffold[Scaffold Resolution]
    package[Generation Package]

    brief --> scaffold --> package
```

| Steg | Kallar LLM? | Får inte göra |
|------|-------------|---------------|
| `scaffold_resolution` | nej | route around policy, lock visual style before policy resolution |
| `generation_package` | nej | call codegen before package is complete |

### Fas 3 - Codegen, Finalize, Quality Gate

Tar `Generation Package` och producerar antingen `Promoted Site` eller `Repair Candidate`.

```mermaid
flowchart TD
    package[Generation Package]
    codegen[Codegen]
    autofix[Mechanical Autofix]
    repair[LLM Repair]
    preview[Preview Runtime]
    gate[Quality Evaluation]
    promo[Promotion]

    package --> codegen --> autofix
    autofix -- ok --> preview --> gate
    autofix -- fail --> repair --> autofix
    gate -- pass --> promo
    gate -- fail --> repair
```

| Steg | Kallar LLM? | Får inte göra |
|------|-------------|---------------|
| `codegen` | ja | mutate policy, silently skip requested pages |
| `mechanical_autofix` | nej | change design intent, invent features |
| `llm_repair` | ja | full rewrite, drop high-value sections, change policy |
| `preview_runtime` | nej | own generation logic, rename runtime-specific terms |
| `quality_evaluation` | ja | promote below gate, hide blocking failures |
| `promotion` | nej | promote draft files, skip audit trail |

## Init vs Followup

För nu fokuserar vi enbart på **init** (första generationen). Followup-flödet är medvetet utelämnat tills init är stabilt på `~9.0/10`. Se ADR [`0004`](../../governance/decisions/0004-migration-from-sajtmaskin-baseline.md).

## Anti-patterns

- Inga sekundära init-vägar förbi flödet ovan.
- Inga "magiska" prompts som lägger till kvalitetskrav utanför `page-quality-traits.v1.json`.
- Inget `Generation Package` som muteras efter att det skickats till codegen.
- Ingen tier-uppdelad quality gate. EN gate, eller nästa policy-version.
