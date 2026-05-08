#requires -Version 5
<#
.SYNOPSIS
  Start the Sajtbyggaren backoffice (Streamlit) on http://localhost:8501.

.DESCRIPTION
  Launches `streamlit run backend.py --server.headless true` from the repo
  root. The backoffice is the operator-only governance/scaffold/dossier
  editor; it is NOT in the user runtime.
#>

[CmdletBinding()]
param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Sajtbyggaren backoffice"
Write-Host "  cwd:  $repoRoot"
Write-Host "  url:  http://localhost:$Port"
Write-Host ""

streamlit run backend.py --server.headless true --server.port $Port
