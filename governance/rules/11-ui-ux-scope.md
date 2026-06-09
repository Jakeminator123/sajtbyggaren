---
description: UI/UX-arbete i Viewser och presentationslagret ska respektera backendkontrakt och branchägande; ändra inte backend tyst från UI-lanen och var ärlig i FloatingChat.
globs: apps/viewser/**,packages/generation/build/**
alwaysApply: false
---

# UI/UX-scope

Gäller främst `apps/viewser/**` och genererad presentationsyta. Branch-/push-disciplinen finns i [`04-branch-and-team.md`](04-branch-and-team.md); den här regeln är arbetsdisciplinen inom UI-lanen.

## Regler

- Ändra inte backendkontrakt tyst från UI-lanen. `/api/prompt`, OpenClaw-runner, data/run-kontrakt och Python-kedjan är backendnära; rör bara med rätt scope eller operatörs-OK.
- `FloatingChat` ska vara ärlig: visa inte "klart" när kedjan säger no-op eller mount-only. Signaler (`applied`, `appliedVisibleEffect`, `previewShouldRefresh`) kommer från kedjan, hittas aldrig på i UI.
- UI-copy ska göra användarens nästa steg tydligt, särskilt efter build och vid följdprompt.
- Är en refaktor behavior-preserving: håll diffen mekanisk och verifiera med TypeScript/lint/relevanta tester.

## Off-limits backend-yta (read OK, edit kräver OK)

Backend-motorn ägs separat. Off-limits från UI-lanen utan operatörens OK: `apps/viewser/app/api/**`, `apps/viewser/lib/**` (server-runners, asset-store, openai-klient, scrape/build/prompt-runner, runs, localhost-guard), `apps/viewser/middleware.ts`, `apps/viewser/next.config.ts`, `scripts/**`, `backoffice.py`/`backoffice/**`, `packages/generation/**` (utom design-bärande ytor), runtime-kontrakt-policies i `governance/policies/*.v1.json`, `governance/schemas/**`, `.github/**`, `.cursor/**`, `data/runs/**`, `data/uploads/**`.

## Inte off-limits (design för genererade sajter ÄR jobbet)

För att slutkundens sajter ska bli snygga, interaktiva och personaliserade får UI-lanen arbeta fritt här: `data/starters/**`, `packages/generation/orchestration/scaffolds/**/variants/*.json`, design-bärande policies (`scaffold-contract`, `scaffold-selection`, `discovery-taxonomy`, `dossier-selection`, `page-quality-traits`, `starter-registry`, `project-dna`), och hela viewser-appens presentationslager (`apps/viewser/app/**/*.tsx` och `*.css` utanför `app/api/`, `apps/viewser/components/**`, `apps/viewser/public/**`, tailwind-/postcss-/eslint-config).

Om en design-policy-ändring kräver schema-ändring i `governance/schemas/`: stoppa och fråga — det är gränssnitt mellan zonerna.

## Vid off-limits-behov

Stoppa innan edit, skriv kort förslag (vilken fil, varför, minimal backend-ändring), vänta på grönt ljus. Om svaret är "gör det själv ändå": tagga commit-body `[scope-leak] Approved by operator: <kort motivering>`. Före commit på `christopher`: `git diff --cached --name-only` och dubbelkolla att inga off-limits-paths är med.
