---
description: Verifiera filsystem-glob med rätt PowerShell-syntax och kompletera mot gitignored-filer. Tom output ska aldrig tolkas som "inga filer".
alwaysApply: true
---

# PowerShell-glob och gitignored-filer

## Två klassiska felfällor

### 1. `Get-ChildItem -Path . -Include` matchar inget utan wildcard

PowerShell tolkar `-Include` bara om `-Path` slutar på en wildcard (`\*`)
eller om `-Recurse` är satt. Utan det returnerar kommandot tom output
även om matchande filer finns.

```powershell
# BAD - returnerar inget även om filer finns
Get-ChildItem -Path . -Include "*.log" -Force

# GOOD - wildcard suffix på Path
Get-ChildItem -Path .\* -Include "*.log" -Force

# GOOD - explicit Filter på enskilt mönster
Get-ChildItem -Path . -Filter "*.log" -Force

# GOOD - rekursiv sökning
Get-ChildItem -Path . -Recurse -Include "*.log" -Force
```

### 2. `git status` döljer gitignored-filer

`git status` listar inte filer som matchar `.gitignore`. Att rapportera
"inga filer att rensa" baserat på `git status` är fel när uppgiften gäller
gitignored-artefakter (logs, build-output, scratch-filer).

```powershell
# BAD - missar viewser-dev.log, npm-build-*.log etc.
git status --short

# GOOD - kontrollera båda källor
Get-ChildItem -Path .\* -Include "*.log" -Force
git check-ignore -v .\viewser-dev.log
```

## Discipline för agenter

- När en uppgift säger "rensa lokala körloggar" eller liknande, lita
  inte enbart på `git status`. Lista filsystemet explicit med korrekt
  wildcard-syntax.
- Om ett glob-anrop returnerar tom output: kör en cross-check med en
  alternativ syntax (`-Filter`, `-Recurse`) innan du rapporterar
  "inga filer".
- Glob-kandidater i Cursor: `Glob`-verktyget söker bara trackade filer
  som standard. Använd PowerShell `Get-ChildItem -Force` för
  gitignored-artefakter.
