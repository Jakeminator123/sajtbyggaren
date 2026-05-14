#requires -Version 5
<#
.SYNOPSIS
  Pretend to be an operator generating a site from a Project Input.

.DESCRIPTION
  Runs the deterministic Builder MVP for a chosen Project Input
  (default: `examples/painter-palma.project-input.json`), then starts the
  generated Next.js site on http://localhost:3000 so you can see the result
  in the browser. Pacman appears at /spel when the dossier is selected.

.EXAMPLE
  scripts/dev-builder.ps1
  scripts/dev-builder.ps1 -ProjectInput examples/painter-palma.project-input.json
  scripts/dev-builder.ps1 -SkipBuild
  scripts/dev-builder.ps1 -Port 3100
#>

[CmdletBinding()]
param(
    [string]$ProjectInput = "examples/painter-palma.project-input.json",
    [switch]$SkipBuild,
    [switch]$NoServe,
    [string]$GeneratedDir = $null,
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Sajtbyggaren builder run"
Write-Host "  project input: $ProjectInput"

if (-not (Test-Path $ProjectInput)) {
    throw "Project Input not found: $ProjectInput"
}

$buildArgs = @("scripts/build_site.py", "--dossier", $ProjectInput)
if ($SkipBuild) { $buildArgs += "--skip-build" }
if ($GeneratedDir) { $buildArgs += @("--generated-dir", $GeneratedDir) }

python @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "Builder failed with exit code $LASTEXITCODE"
}

if ($NoServe) {
    Write-Host ""
    Write-Host "Builder finished. -NoServe set; not starting Next.js dev server."
    return
}

$siteId = (Get-Content $ProjectInput | ConvertFrom-Json).siteId
if ($GeneratedDir) {
    $generatedRoot = $GeneratedDir
} elseif ($env:SAJTBYGGAREN_GENERATED_DIR) {
    $generatedRoot = $env:SAJTBYGGAREN_GENERATED_DIR
} else {
    $generatedRoot = Join-Path (Split-Path -Parent $repoRoot) "sajtbyggaren-output/.generated"
}
$siteDir = Join-Path $generatedRoot $siteId
if (-not (Test-Path $siteDir)) {
    throw "Generated site missing at $siteDir"
}

Write-Host ""
Write-Host "Starting Next.js dev server"
Write-Host "  cwd:  $siteDir"
Write-Host "  url:  http://localhost:$Port"

if (-not (Test-Path (Join-Path $siteDir "node_modules"))) {
    Write-Host "  installing dependencies (first run)..."
    Push-Location $siteDir
    try { npm install } finally { Pop-Location }
}

Push-Location $siteDir
try { npm run dev -- --port $Port } finally { Pop-Location }
