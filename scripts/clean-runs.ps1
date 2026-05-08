#requires -Version 5
<#
.SYNOPSIS
  Remove old data/runs/<runId>/ directories.

.DESCRIPTION
  Each builder invocation writes canonical Engine Run artefakter to
  data/runs/<runId>/. The directory is gitignored but accumulates
  locally over time. This script keeps the most recent N runs and
  deletes the rest. Default keeps 5.

.EXAMPLE
  scripts/clean-runs.ps1
  scripts/clean-runs.ps1 -Keep 0      # nuke all
  scripts/clean-runs.ps1 -Keep 20     # keep the 20 newest
  scripts/clean-runs.ps1 -DryRun      # only print what would be removed
#>

[CmdletBinding()]
param(
    [int]$Keep = 5,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runsDir = Join-Path $repoRoot "data/runs"

if (-not (Test-Path $runsDir)) {
    Write-Host "No data/runs/ directory; nothing to clean."
    return
}

$entries = Get-ChildItem -Directory $runsDir | Sort-Object LastWriteTime -Descending
$total = $entries.Count

if ($total -le $Keep) {
    Write-Host "Found $total runs; keeping all (limit $Keep)."
    return
}

$toRemove = $entries | Select-Object -Skip $Keep
Write-Host "Found $total runs; keeping $Keep newest, removing $($toRemove.Count)."

foreach ($entry in $toRemove) {
    if ($DryRun) {
        Write-Host "  (dry-run) $($entry.Name)"
    } else {
        Remove-Item -Recurse -Force $entry.FullName
        Write-Host "  removed $($entry.Name)"
    }
}
