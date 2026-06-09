---
description: OpenClaw är dirigent/bridge genom sanktionerade actions (fri förståelse, kontrollerad applicering); ändra en användarsajt via per-sajt-lagret, aldrig via en delad mall.
globs: docs/openclaw-workspace/**,docs/heavy-llm-flow/**,packages/generation/orchestration/openclaw/**,packages/generation/followup/**,scripts/run_openclaw_followup.py,scripts/verify_openclaw.py,apps/viewser/lib/openclaw-runner.ts,apps/viewser/app/api/prompt/**
alwaysApply: false
---

# OpenClaw och runtime-sajtmutationer

Konsoliderar OpenClaw-modellen och sajt-mutationslagren. Finns för att ingen agent ska "ändra fel sak": en delad mall i stället för per-sajt-lagret, eller hand-redigerad genererad output.

## OpenClaw är en dirigent/bridge

OpenClaw är en router **ovanpå** init/follow-up som väljer answer/plan/site-change. Den står ovanför pipelinen och väljer hur den ska användas — den kapar den inte.

```text
FloatingChat / följdprompt -> OpenClaw router/rollval -> strukturerad mutation
  -> befintlig apply-kedja -> ny version + preview-refresh
```

**Tillåtet:** läsa site state, Project Input och run/version; välja sanktionerad action från `docs/openclaw-workspace/action-registry.json`; använda agentroller för bättre förståelse/copy/design/sektioner; köra ändringar genom befintlig apply-kedja.

**Inte tillåtet:** fri patch i generated files; ny parallell motor; extern OpenClaw daemon/gateway/Docker i nuvarande fas (om inte uppgiften uttryckligen är docs-only Fas 2-plan); påhittade fakta/recensioner/certifikat/telefonnummer/claims; fejkad success när `appliedVisibleEffect` är false.

**Nuvarande realism:** `restyle` och `copy_change` är supported; `section_add` kan vara supported men mount-only tills synlig render finns; `site_review` är read-only/partial; `layout_change` är planned. Signaler som `applied`, `appliedVisibleEffect` och `previewShouldRefresh` ska komma från kedjan, aldrig hittas på av UI/OpenClaw.

## Två helt olika sorters "ändring" — blanda aldrig ihop dem

| | Repo-redigering | Runtime-sajtmutation |
|---|---|---|
| **Vem** | Kodagent (Scout/Builder/Steward) som ändrar Sajtbyggaren-repot | Pipelinen + OpenClaw-orkestrerade agenter som ändrar EN användares sajt |
| **Vad** | Motor (`packages/generation/**`, `scripts/**`), delade mallar, governance, lanes | EN sajts `Project Input`/`Project DNA`/genererad output + versioner |
| **Bundet av** | `repo-boundaries.v1.json`, branch-scope, build-chain-låsen, naming-dictionary | Follow-up-intent-taxonomin (`project-dna.v1.json`) + honesty-reglerna |
| **Räckvidd** | En delad fil påverkar **ALLA** sajter | Bara mål-sajten |

Kärnregel: **för att ändra hur EN användares sajt ser ut/läser/beter sig — rör aldrig en delad mall.** Att ändra en delad `Variant` för att en kund vill ha rosa gör alla kunder på den varianten rosa.

## Vilket lager ändrar jag? (per-sajt vs delat)

| Vill åstadkomma | Lager | Räckvidd |
|---|---|---|
| Default-uttryck för en hel sajt-**typ** | `Variant` (delad) | ALLA sajter med varianten — bara om operatören medvetet ändrar default |
| EN sajts färg/font/uttryck (**restyle**) | per-sajt override → `themeTokens` (`Project Input` `brand`/`tone` idag) | bara den sajten |
| Byta hela uttrycket för EN sajt | `variantId` (mjukt lås, `restyle`-intent) i `Project DNA` | bara den sajten |
| Sajtens grammatik (routes/sektioner) | `Scaffold` (hårt lås, bara via `redesign` → `Project Fork`) | — |
| Copy/innehåll för EN sajt | `Project Input`/follow-up `copyDirective` | den sajten |
| Lägga på en capability | `Dossier` (delad) monteras per sajt via `selectedDossiers` | den sajten |

Hand-redigera **aldrig** genererad output (`.generated/**`, `data/runs/<runId>/generated-files/**`) — den skrivs om vid nästa build. Ändra källan i stället.

## Restyle är redan modellerad — hitta inte på en parallell

`project-dna.v1.json` follow-up-intent `restyle` (`variant: may-change`) + DNA-fält `themeTokens` är den kanoniska modellen för färg-/font-/uttrycks-ändring. Routerns `editKind` `visual_style` är samma begrepp som DNA-intenten `restyle` — behandla som synonymer, inför inte ett tredje ord (formell hopslagning = ADR). Tills `Project DNA`-runtime landar är `brand.primaryColorHex`/`brand.accentColorHex` + `tone.primary` den sanktionerade per-sajt-override-ytan (deterministisk seed: `packages/generation/followup/theme_directives.py`).

## Tunga LLM-flödet: fri tillgång till mål-sajten

Det tunga flödet har **fri tillgång att ändra mål-användarens sajt** genom de sanktionerade ytorna. Det begränsas INTE av repo-boundaries/branch-scope (de gäller repo-författande), utan av follow-up-intent-taxonomin + honesty.

- **Får fritt:** läsa sajtens state, välja intent/vinkel, skriva per-sajt `Project Input`/`themeTokens`, köra follow-up-kedjan (router → context → patch → apply → targeted render), reparera och regenerera output + versioner — för **mål-sajten**.
- **Får inte:** redigera delade mallar/motor/governance för att uppnå en enskild sajts effekt; hitta på claims/recensioner/placeholder-kontakt; skriva fria Next.js-filer utanför codegen; byta `Scaffold` utanför `redesign`/`Project Fork`; eller röra en **annan** användares sajt.

## 60-sekunders-check innan du rör sajt-utseende/innehåll/struktur

1. Är detta **repo-redigering** (delad effekt) eller **runtime-sajtmutation** (en sajt)?
2. Om en sajt: använder jag **per-sajt-lagret** (`Project Input`/`Project DNA`), inte en delad mall?
3. Finns intenten/fältet redan (`project-dna.v1.json`, `themeTokens`, `copyDirective`)? Återanvänd, dubbla inte.
4. Honesty: hittar jag på något (claim, kontakt, cert)? Stoppa.

Osäker på vilket lager? Stanna och fråga operatören.
