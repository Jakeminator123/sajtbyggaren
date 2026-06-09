---
description: Sajtbyggaren är en kontrollerad ombyggnad av sajtmaskin som bygger bättre företagshemsidor; prioritera kärnloopen, undvik tidig scope creep och bygg OpenClaw kontrollerat.
alwaysApply: true
---

# Produktkärna och riktning

Sajtbyggaren är en kontrollerad ny version av gamla `Jakeminator123/sajtmaskin` (referensbranch `master`), inte en kopia. Målet är en mer strukturerad, styrbar och tydligt namngiven version.

## Nordstjärna

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

Allt arbete ska göra denna loop stabilare, tydligare eller mer kvalitativ.

## Produktprinciper

- Bygg bättre företagshemsidor för småföretagare, inte en bred Lovable/v0-kopia.
- Gamla `sajtmaskin` är referens/baslinje och reservdelslager, inte kodbas att återinföra rakt av. Plocka in goda idéer (glossary, scheman, quality gates, dossiers/capabilities, agent-router) men ta inte med legacy-komplexitet by default.
- Governance ska skydda riktningen, inte kväva bygget. Gör governance explicit: vad som får ändras, hur det valideras och vem som äger vad ska synas i `governance/`.
- Håll ägargränser tydliga enligt [`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json); sprid inte besläktad logik över orelaterade filer.
- Använd explicita domännamn enligt [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json).
- Föredra en liten sammanhängande kärna före UI, generatorer, integrationer och deploy-komplexitet.
- Undvik tidig scope creep: auth, billing, Stripe, Supabase, Shopify, custom domains, marketplace, avatar/media och för många initieringsvägar väntar.
- `backoffice.py` ligger i roten som backoffice (Streamlit), inte som del av användarens runtime.
- `PreviewRuntime` är en adapterstege: Vercel Sandbox är primärt användarnära förstahandsval (ADR 0033), `local-next` är faktisk default/fallback för dev, StackBlitz är pausad om inget annat beslutats.

## OpenClaw / Sajtagent

OpenClaw är strategiskt viktigt som framtida Sajtagent men ska byggas kontrollerat:

- dirigent/bridge ovanpå befintlig motor
- inte en parallell engine
- inte fri filpatch
- inte extern gateway/Docker i nuvarande fas, om inte uppgiften uttryckligen gäller Fas 2-planering (docs-only)

Detaljmodellen finns i [`09-openclaw-and-site-mutations.md`](09-openclaw-and-site-mutations.md).

## Arbetsordning (referens)

1. Governance först (policies, schemas, rules, decisions).
2. Backoffice-skelett (`backoffice.py`).
3. Migrationsrapport och baseline-eval.
4. Fas 1 runtime (Site Brief).
5. Fas 2 runtime (Orchestration).
6. Fas 3 runtime (Codegen, Finalize, Quality Gate).
7. PreviewRuntime (Vercel Sandbox primär per ADR 0033; `local-next` default/fallback; StackBlitz pausad).
8. apps/web sist; followup-flöde först när init är 9.0/10.
