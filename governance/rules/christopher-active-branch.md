---
description: Christophers aktiva arbets-branch är `christopher` (avstamp från `jakob-be`). Gamla `christopher-ui` är fryst — rör den aldrig utan operatörens OK.
alwaysApply: true
---

# Christopher: aktiv branch är `christopher`

## Grundregel

- Christophers aktiva arbets-branch är **`christopher`**, skapad med avstamp
  från senaste `jakob-be`.
- `christopher-ui` (och `christopher-ui-backup-*`) är **fryst legacy**: de bär
  gammal historik plus parkerad auth/billing (`NEXT_PUBLIC_AUTH_ENABLED`) som
  medvetet inte ska tillbaka nu.
- Detta åsidosätter `christopher-ui`-namnet i
  [`branch-discipline.md`](branch-discipline.md) för Christopher-lanen tills
  operatören säger annat.

## Vad agenten alltid gör

1. Innan en edit eller commit: kör `git branch --show-current` och verifiera
   att den är `christopher`.
2. Om den i stället är `christopher-ui` eller en backup: stanna, byt till
   `christopher` (`git checkout christopher`), och fråga operatören om något
   är oklart.
3. Allt UI-arbete i `apps/viewser/` görs på `christopher`.

## Vad agenten aldrig gör utan operatörens uttryckliga OK

- Checkar ut, committar till, eller mergar in i `christopher-ui` eller dess
  backup.
- Mergar `christopher-ui` in i `christopher` (eller tvärtom).
- Ändrar, rebasar eller raderar `christopher-ui` / `christopher-ui-backup-*`.
- Pushar `christopher` till `jakob-be` eller `main` — det är en separat
  branch och push kräver explicit mål (`git push -u origin christopher`).

## Om operatören uttryckligen vill röra `christopher-ui`

Bekräfta målet i klartext först och tagga commit-body med en kort motivering
(t.ex. `[legacy-branch] Approved by operator: <varför>`). Annars gäller att
all aktiv utveckling sker på `christopher`.
