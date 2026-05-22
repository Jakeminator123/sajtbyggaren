---
description: Contract-first team workflow for parallel frontend/backend work.
alwaysApply: true
---

# Team workflow

## Grundregel

Läs `docs/ownership-map.md` innan större ändringar som kan korsa frontend,
backend, generation, governance eller shared contract.

Följ alltid `governance/rules/branch-discipline.md` för branch- och PR-flöde.
Det betyder normalt direkt-main med backup först. PR/branch används när
operatören uttryckligen ber om det, vid Cloud/Grind-arbete, eller när en
större/riskfylld ändring väljs till PR-flöde. Hitta inte på egna branch-prefix.

## Contract-first

- Ändra inte shared contract tyst.
- Dokumentera nya frontend/backend-shapes i `docs/contracts/` innan båda sidor
  bygger mot dem.
- Om backend saknas ska frontend bygga mot dokumenterade mockar, inte gissade
  API-shapes.
- Om frontend saknas ska backend ändå beskriva output-shape och testidé.

## Frontend-agent

- Håll dig till `apps/viewser/**`, frontend-docs och mockar om inget annat är
  explicit valt.
- Ändra inte `packages/generation/**`, `governance/**`, `data/starters/**` eller
  runtime/deploy utan tydlig prompt.
- Om UI kräver ny backend-data: stoppa och föreslå contract-PR först.

## Backend-agent

- Ändra inte frontend-UX i `apps/viewser/**` utan tydlig prompt.
- Om generation/run-state ändrar vad Viewser konsumerar: uppdatera contract och
  be om frontend-review.
- Håll starter-import, registry activation, auth, billing, runtime deploy och
  B125 utanför scope om de inte uttryckligen är valda.

## Konflikt

- Två personer eller agenter ska inte jobba i samma branch eller samma filer
  samtidigt.
- Vid fil- eller branchkrock: stoppa och rapportera.
- Om båda behöver samma fil: gör en liten contract- eller docs-PR först.

## Scope creep

Auth, billing, runtime deploy, starter activation, starter import och B125
kräver explicit beslut. Dokumentation ska hjälpa bygget, inte bli ett
självändamål.
