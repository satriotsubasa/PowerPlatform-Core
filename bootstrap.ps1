#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Check (and optionally install) the PowerPlatform-Core prerequisite toolchain.

.DESCRIPTION
    The skills are code-first, so the live path needs a small local toolchain. This
    script verifies each prerequisite and reports a PASS/FAIL table:

      - Python 3.10+          (required - runs the helper scripts)
      - .NET 8 SDK            (required - builds/runs the DataverseOps tool + plug-ins)
      - Power Platform CLI    (required - auth, solution, and deployment operations)
      - Node.js 18+           (optional - only for PCF controls and Code Apps)

    Run with -Install to attempt installing anything missing that it can do safely:
    'pac' as a .NET global tool, and the rest via winget when winget is available.
    Without -Install it only checks and prints the exact command to fix each gap.

.EXAMPLE
    ./bootstrap.ps1

.EXAMPLE
    ./bootstrap.ps1 -Install
#>
[CmdletBinding()]
param(
    [switch]$Install
)

$ErrorActionPreference = 'Stop'

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonInfo {
    foreach ($candidate in @('python', 'python3')) {
        if (Test-CommandExists $candidate) {
            $raw = (& $candidate --version 2>&1 | Out-String).Trim()
            if ($raw -match '(\d+)\.(\d+)\.(\d+)') {
                $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                $ok = ($major -gt 3) -or ($major -eq 3 -and $minor -ge 10)
                return [pscustomobject]@{ Command = $candidate; Version = $raw; Ok = $ok }
            }
        }
    }
    # Windows launcher fallback.
    if (Test-CommandExists 'py') {
        $raw = (& py -3 --version 2>&1 | Out-String).Trim()
        if ($raw -match '(\d+)\.(\d+)\.(\d+)') {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            $ok = ($major -gt 3) -or ($major -eq 3 -and $minor -ge 10)
            return [pscustomobject]@{ Command = 'py -3'; Version = $raw; Ok = $ok }
        }
    }
    return $null
}

function Get-DotnetSdk8 {
    if (-not (Test-CommandExists 'dotnet')) { return $null }
    $sdks = (& dotnet --list-sdks 2>&1) -split "`n"
    $match = $sdks | Where-Object { $_.Trim() -match '^8\.' } | Select-Object -First 1
    if ($match) { return $match.Trim() }
    return $null
}

function Get-ToolVersion {
    param([string]$Name, [string]$Args = '--version')
    if (-not (Test-CommandExists $Name)) { return $null }
    return (& $Name $Args.Split(' ') 2>&1 | Out-String).Trim()
}

$results = New-Object System.Collections.Generic.List[object]
$missingRequired = New-Object System.Collections.Generic.List[string]

Write-Host ''
Write-Host 'PowerPlatform-Core prerequisite check' -ForegroundColor Cyan
Write-Host '======================================'

# --- Python -------------------------------------------------------------------
$py = Get-PythonInfo
if ($py -and $py.Ok) {
    $results.Add([pscustomobject]@{ Tool = 'Python 3.10+'; Status = 'PASS'; Detail = $py.Version })
} else {
    $detail = if ($py) { "$($py.Version) is too old" } else { 'not found' }
    $results.Add([pscustomobject]@{ Tool = 'Python 3.10+'; Status = 'FAIL'; Detail = $detail })
    $missingRequired.Add('python')
}

# --- .NET 8 SDK ---------------------------------------------------------------
$sdk = Get-DotnetSdk8
if ($sdk) {
    $results.Add([pscustomobject]@{ Tool = '.NET 8 SDK'; Status = 'PASS'; Detail = $sdk })
} else {
    $results.Add([pscustomobject]@{ Tool = '.NET 8 SDK'; Status = 'FAIL'; Detail = 'no 8.x SDK found' })
    $missingRequired.Add('dotnet')
}

# --- Power Platform CLI -------------------------------------------------------
$pac = Get-ToolVersion -Name 'pac'
if ($pac) {
    $results.Add([pscustomobject]@{ Tool = 'Power Platform CLI'; Status = 'PASS'; Detail = ($pac -split "`n")[0] })
} else {
    $results.Add([pscustomobject]@{ Tool = 'Power Platform CLI'; Status = 'FAIL'; Detail = 'not found' })
    $missingRequired.Add('pac')
}

# --- Node.js (optional) -------------------------------------------------------
$node = Get-ToolVersion -Name 'node'
if ($node) {
    $results.Add([pscustomobject]@{ Tool = 'Node.js (optional)'; Status = 'PASS'; Detail = $node })
} else {
    $results.Add([pscustomobject]@{ Tool = 'Node.js (optional)'; Status = 'WARN'; Detail = 'not found (only needed for PCF / Code Apps)' })
}

# Render manually (not Format-Table -AutoSize, which blocks probing console width
# when stdout is redirected, e.g. a background/CI run).
foreach ($r in $results) {
    $color = switch ($r.Status) { 'PASS' { 'Green' } 'WARN' { 'Yellow' } default { 'Red' } }
    Write-Host ("  {0,-20} {1,-6} {2}" -f $r.Tool, $r.Status, $r.Detail) -ForegroundColor $color
}
Write-Host ''

if ($missingRequired.Count -eq 0) {
    Write-Host 'All required tools are present. You are ready to go.' -ForegroundColor Green
    exit 0
}

# --- Remediation --------------------------------------------------------------
$hasWinget = Test-CommandExists 'winget'

function Install-Or-Advise {
    param([string]$Key)
    switch ($Key) {
        'python' {
            if ($Install -and $hasWinget) {
                Write-Host '-> Installing Python via winget...' -ForegroundColor Yellow
                winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
            } else {
                Write-Host '   Install Python 3.10+:  winget install Python.Python.3.12   (or https://www.python.org/downloads/)'
            }
        }
        'dotnet' {
            if ($Install -and $hasWinget) {
                Write-Host '-> Installing the .NET 8 SDK via winget...' -ForegroundColor Yellow
                winget install --id Microsoft.DotNet.SDK.8 -e --source winget --accept-package-agreements --accept-source-agreements
            } else {
                Write-Host '   Install the .NET 8 SDK:  winget install Microsoft.DotNet.SDK.8   (or https://dotnet.microsoft.com/download/dotnet/8.0)'
            }
        }
        'pac' {
            # pac installs cleanly as a .NET global tool once the SDK is present.
            if ($Install -and (Test-CommandExists 'dotnet')) {
                Write-Host '-> Installing the Power Platform CLI as a .NET global tool...' -ForegroundColor Yellow
                dotnet tool install --global Microsoft.PowerApps.CLI.Tool
                Write-Host '   Open a new shell (or add ~/.dotnet/tools to PATH) so pac is found.'
            } else {
                Write-Host '   Install pac:  dotnet tool install --global Microsoft.PowerApps.CLI.Tool   (needs the .NET SDK first)'
            }
        }
    }
}

Write-Host 'Missing required tools:' -ForegroundColor Yellow
foreach ($key in $missingRequired) { Install-Or-Advise -Key $key }

if (-not $Install) {
    Write-Host ''
    Write-Host 'Re-run with -Install to attempt the installs above automatically.' -ForegroundColor Cyan
}

exit 1
