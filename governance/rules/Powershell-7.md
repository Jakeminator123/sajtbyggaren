---
description: Operatörens (Jakob) lokala miljö är Windows med PowerShell 7 — använd pwsh-syntax för shell-kommandon där. Christopher (macOS) och cloud-agenter (Linux/Unix) använder native POSIX-shell, inte pwsh.
alwaysApply: true
---

# Shell per miljö (operatör vs övriga)

Den här regeln säger vilken shell-syntax som gäller var. Den tvingar inte
PowerShell på alla — den binder bara operatörens lokala Windows-miljö. Välj
alltid shell-syntax efter miljön du faktiskt kör i.

## Operatören (Jakob), lokalt på Windows

- Standardskalet är PowerShell 7 (`pwsh`). Använd pwsh-syntax för
  shell-kommandon: `$env:NAMN` för miljövariabler, here-strings (`@"..."@`)
  i stället för bash-heredoc, och undvik att lita på `&&`-only-kedjor när en
  enklare sekvens räcker.
- Bash-konstruktioner (`cat <<'EOF'`, `export X=Y`) är inte garanterat
  tillgängliga i den miljön.

## Christopher (macOS) och cloud-agenter (Linux/Unix)

- Native POSIX-shell (`bash`/`zsh`) gäller. pwsh-specifik syntax ska inte
  användas där. Kedjor med `&&`, `export` och heredoc fungerar som vanligt.

## Varför regeln finns

Operatörens Windows-pwsh-miljö ska inte få bash-only-kommandon som tyst
failar. Regeln är informativ och miljöberoende — den gör inte pwsh till
default för agenter som kör på macOS eller Unix.
