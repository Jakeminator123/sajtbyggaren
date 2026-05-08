#requires -Version 5
<#
.SYNOPSIS
  Start the Viewser localhost-only operator prototype on http://localhost:3000.

.DESCRIPTION
  Launches `apps/viewser` Next.js dev server. Viewser is the operator-only
  prototype with chat + manual build button + StackBlitz preview. NOT a
  canonical runtime; replaced by Sprint 4 LocalRuntime/StackBlitzRuntime.

  Requires `apps/viewser/.env.local` with `OPENAI_API_KEY`. Copy from
  `apps/viewser/.env.example`.
#>

[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$viewserDir = Join-Path $repoRoot "apps/viewser"

if (-not (Test-Path $viewserDir)) {
    throw "apps/viewser missing at $viewserDir"
}

Write-Host "Sajtbyggaren viewser prototype"
Write-Host "  cwd:  $viewserDir"
Write-Host "  url:  http://localhost:3000"

if (-not (Test-Path (Join-Path $viewserDir ".env.local"))) {
    Write-Warning "apps/viewser/.env.local missing. Copy .env.example and add OPENAI_API_KEY before chat works."
}

Push-Location $viewserDir
try {
    if (-not $SkipInstall -and -not (Test-Path "node_modules")) {
        Write-Host "  installing dependencies (first run)..."
        npm install
    }
    npm run dev
} finally {
    Pop-Location
}
