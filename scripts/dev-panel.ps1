#requires -Version 5
<#
.SYNOPSIS
  Open a small local launcher for Sajtbyggaren dev surfaces.

.DESCRIPTION
  Starts existing dev scripts from one Windows panel. Each long-running
  surface opens in its own PowerShell window so the launcher stays usable.
#>

[CmdletBinding()]
param(
    [int]$BackofficePort = 8501,
    [int]$BuilderPort = 3000,
    [int]$ExamplePort = 3100,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Quote-PowerShellLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

function Get-PowerShellHost {
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwsh) {
        return $pwsh.Source
    }

    $windowsPowerShell = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($windowsPowerShell) {
        return $windowsPowerShell.Source
    }

    throw "Could not find pwsh or powershell.exe."
}

function Start-PanelCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Command,
        [string]$Url = ""
    )

    $literalTitle = Quote-PowerShellLiteral $Title
    $literalRepoRoot = Quote-PowerShellLiteral $repoRoot
    $terminalCommand = @"
`$Host.UI.RawUI.WindowTitle = $literalTitle
Set-Location -LiteralPath $literalRepoRoot
$Command
Write-Host ""
Write-Host "Process ended. Press Enter to close this window."
[void](Read-Host)
"@

    $encodedCommand = [Convert]::ToBase64String(
        [System.Text.Encoding]::Unicode.GetBytes($terminalCommand)
    )

    Start-Process `
        -FilePath (Get-PowerShellHost) `
        -WorkingDirectory $repoRoot `
        -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encodedCommand)

    if ($Url -and -not $NoBrowser) {
        Start-Process $Url
    }
}

function Open-LocalFolder {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }

    Start-Process $Path
}

function Add-LauncherRow {
    param(
        [Parameter(Mandatory = $true)][System.Windows.Forms.Form]$Form,
        [Parameter(Mandatory = $true)][string]$ButtonText,
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][int]$Top,
        [Parameter(Mandatory = $true)][scriptblock]$OnClick
    )

    $button = New-Object System.Windows.Forms.Button
    $button.Text = $ButtonText
    $button.Location = New-Object System.Drawing.Point(20, $Top)
    $button.Size = New-Object System.Drawing.Size(175, 42)
    $button.Add_Click($OnClick)

    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Description
    $label.Location = New-Object System.Drawing.Point(215, ($Top + 3))
    $label.Size = New-Object System.Drawing.Size(265, 42)

    $Form.Controls.Add($button)
    $Form.Controls.Add($label)
}

$backofficeScript = Join-Path $PSScriptRoot "dev-backoffice.ps1"
$builderScript = Join-Path $PSScriptRoot "dev-viewser.ps1"
$exampleBuilderScript = Join-Path $PSScriptRoot "dev-builder.ps1"
$defaultProjectInput = Join-Path $repoRoot "examples/painter-palma.project-input.json"
$runsDir = Join-Path $repoRoot "data/runs"
$generatedSitesDir = Join-Path (Split-Path -Parent $repoRoot) "sajtbyggaren-output/.generated"

$form = New-Object System.Windows.Forms.Form
$form.Text = "Sajtbyggaren startpanel"
$form.Size = New-Object System.Drawing.Size(530, 430)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "Sajtbyggaren"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$titleLabel.Location = New-Object System.Drawing.Point(20, 18)
$titleLabel.Size = New-Object System.Drawing.Size(470, 30)
$form.Controls.Add($titleLabel)

$introLabel = New-Object System.Windows.Forms.Label
$introLabel.Text = "Starta de vanligaste lokala ytorna utan att komma ihag kommandon."
$introLabel.Location = New-Object System.Drawing.Point(22, 52)
$introLabel.Size = New-Object System.Drawing.Size(470, 24)
$form.Controls.Add($introLabel)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Klicka pa en knapp for att starta."
$statusLabel.Location = New-Object System.Drawing.Point(20, 342)
$statusLabel.Size = New-Object System.Drawing.Size(470, 22)
$form.Controls.Add($statusLabel)

Add-LauncherRow `
    -Form $form `
    -ButtonText "Backoffice" `
    -Description "Streamlit-yta for governance, scaffolds, runs och operatorvy. Oppnar localhost:$BackofficePort." `
    -Top 90 `
    -OnClick {
        $statusLabel.Text = "Startar Backoffice pa localhost:$BackofficePort..."
        $script = Quote-PowerShellLiteral $backofficeScript
        Start-PanelCommand `
            -Title "Sajtbyggaren - Backoffice" `
            -Command "& $script -Port $BackofficePort" `
            -Url "http://localhost:$BackofficePort"
    }

Add-LauncherRow `
    -Form $form `
    -ButtonText "Builder" `
    -Description "Viewser med promptfalt, run history och preview. Oppnar localhost:$BuilderPort." `
    -Top 150 `
    -OnClick {
        $statusLabel.Text = "Startar Builder/Viewser pa localhost:$BuilderPort..."
        $script = Quote-PowerShellLiteral $builderScript
        Start-PanelCommand `
            -Title "Sajtbyggaren - Builder" `
            -Command "& $script -Port $BuilderPort" `
            -Url "http://localhost:$BuilderPort"
    }

Add-LauncherRow `
    -Form $form `
    -ButtonText "Example Site" `
    -Description "Kor Builder MVP pa standardexemplet och serverar resultatet pa localhost:$ExamplePort." `
    -Top 210 `
    -OnClick {
        $statusLabel.Text = "Bygger exempel och startar preview pa localhost:$ExamplePort..."
        $script = Quote-PowerShellLiteral $exampleBuilderScript
        $projectInput = Quote-PowerShellLiteral $defaultProjectInput
        Start-PanelCommand `
            -Title "Sajtbyggaren - Example Site" `
            -Command "& $script -ProjectInput $projectInput -Port $ExamplePort" `
            -Url "http://localhost:$ExamplePort"
    }

Add-LauncherRow `
    -Form $form `
    -ButtonText "Quick Check" `
    -Description "Kor snabb review-kedja: governance, rules sync, termcheck och ruff." `
    -Top 270 `
    -OnClick {
        $statusLabel.Text = "Startar snabbcheck i nytt terminalfonster..."
        Start-PanelCommand `
            -Title "Sajtbyggaren - Quick Check" `
            -Command "python scripts/review_check.py --quick"
    }

$openRunsButton = New-Object System.Windows.Forms.Button
$openRunsButton.Text = "Open Runs"
$openRunsButton.Location = New-Object System.Drawing.Point(20, 315)
$openRunsButton.Size = New-Object System.Drawing.Size(110, 28)
$openRunsButton.Add_Click({
    $statusLabel.Text = "Oppnar data/runs..."
    Open-LocalFolder $runsDir
})
$form.Controls.Add($openRunsButton)

$openGeneratedButton = New-Object System.Windows.Forms.Button
$openGeneratedButton.Text = "Generated Sites"
$openGeneratedButton.Location = New-Object System.Drawing.Point(145, 315)
$openGeneratedButton.Size = New-Object System.Drawing.Size(130, 28)
$openGeneratedButton.Add_Click({
    $statusLabel.Text = "Oppnar generated sites..."
    Open-LocalFolder $generatedSitesDir
})
$form.Controls.Add($openGeneratedButton)

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = "Close"
$closeButton.Location = New-Object System.Drawing.Point(380, 315)
$closeButton.Size = New-Object System.Drawing.Size(100, 28)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

[void]$form.ShowDialog()
