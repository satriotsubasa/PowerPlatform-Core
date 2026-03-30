[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Local', 'GitHub')]
    [string]$Source = 'Local',

    [string]$DestinationRoot = (Join-Path $HOME '.codex\skills'),

    [string]$Repo = 'satriotsubasa/PowerPlatform-Core',

    [string]$Ref = 'main',

    [ValidateSet('auto', 'download', 'git')]
    [string]$Method = 'git',

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packagingHelper = Join-Path $scriptRoot 'skill-packaging.ps1'
$skillName = 'powerplatform-core'
$legacySkillNames = @()
$localSkillRoot = $scriptRoot
$destinationPath = Join-Path $DestinationRoot $skillName

if (-not (Test-Path -LiteralPath $packagingHelper)) {
    throw "Packaging helper script was not found at '$packagingHelper'."
}

. $packagingHelper

function Remove-InstalledSkillIfRequested {
    param(
        [string]$PathToRemove,
        [switch]$RequireForce
    )

    if (-not (Test-Path -LiteralPath $PathToRemove)) {
        return
    }

    if ($RequireForce -and -not $Force) {
        throw "Skill already exists at '$PathToRemove'. Use -Force to replace it, or run .\update-skill.ps1 instead."
    }

    if ($PSCmdlet.ShouldProcess($PathToRemove, 'Remove existing installed skill')) {
        Remove-Item -LiteralPath $PathToRemove -Recurse -Force
    }
}

function Remove-LegacyInstalledSkills {
    foreach ($legacySkillName in $legacySkillNames) {
        $legacyPath = Join-Path $DestinationRoot $legacySkillName
        if (Test-Path -LiteralPath $legacyPath) {
            if ($PSCmdlet.ShouldProcess($legacyPath, "Remove legacy installed skill '$legacySkillName'")) {
                Remove-Item -LiteralPath $legacyPath -Recurse -Force
            }
        }
    }
}

function Copy-LocalSkillRoot {
    param(
        [string]$SourceRoot,
        [string]$DestinationPath
    )

    if ($PSCmdlet.ShouldProcess($DestinationPath, "Install $skillName runtime package from local repo")) {
        Copy-PackagedSkill -SourceRoot $SourceRoot -DestinationPath $DestinationPath
    }
}

if ($Source -eq 'Local') {
    Assert-SkillSourceRoot -SourceRoot $localSkillRoot

    if ($PSCmdlet.ShouldProcess($DestinationRoot, 'Ensure Codex skills directory exists')) {
        New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    }

    Remove-LegacyInstalledSkills
    Remove-InstalledSkillIfRequested -PathToRemove $destinationPath -RequireForce

    Copy-LocalSkillRoot -SourceRoot $localSkillRoot -DestinationPath $destinationPath
}
else {
    if ($PSCmdlet.ShouldProcess($DestinationRoot, 'Ensure Codex skills directory exists')) {
        New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    }

    Remove-LegacyInstalledSkills
    Remove-InstalledSkillIfRequested -PathToRemove $destinationPath -RequireForce

    if ($PSCmdlet.ShouldProcess($destinationPath, "Install $skillName runtime package from GitHub")) {
        $checkout = Get-GitHubSkillSource -Repo $Repo -Ref $Ref -Method $Method
        try {
            Copy-PackagedSkill -SourceRoot $checkout.SourceRoot -DestinationPath $destinationPath
        }
        finally {
            Remove-TemporarySkillWorktree -PathToRemove $checkout.TempRoot
        }
    }
}

if ($WhatIfPreference) {
    Write-Host "No changes were made because -WhatIf was used."
    Write-Host "Skill would be installed to $destinationPath"
}
else {
    Write-Host "Installed $skillName to $destinationPath"
    Write-Host 'Restart Codex to pick up new skills.'
}
