[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Local', 'GitHub')]
    [string]$Source = 'Local',

    [string]$DestinationRoot = (Join-Path $HOME '.codex\skills'),

    [string]$Repo = 'satriotsubasa/PowerPlatform-Core',

    [string]$Ref = 'main',

    [ValidateSet('auto', 'download', 'git')]
    [string]$Method = 'git',

    [switch]$Pull
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packagingHelper = Join-Path $scriptRoot 'skill-packaging.ps1'
$skillName = 'powerplatform-core'
$legacySkillNames = @()
$localSkillRoot = $scriptRoot
$destinationPath = Join-Path $DestinationRoot $skillName
$gitFolder = Join-Path $scriptRoot '.git'

if (-not (Test-Path -LiteralPath $packagingHelper)) {
    throw "Packaging helper script was not found at '$packagingHelper'."
}

. $packagingHelper

function Remove-InstalledSkill {
    param([string]$PathToRemove)

    if (-not (Test-Path -LiteralPath $PathToRemove)) {
        return $false
    }

    if ($PSCmdlet.ShouldProcess($PathToRemove, 'Remove existing installed skill before update')) {
        Remove-Item -LiteralPath $PathToRemove -Recurse -Force
    }
    return $true
}

function Remove-LegacyInstalledSkills {
    $removedLegacy = $false
    foreach ($legacySkillName in $legacySkillNames) {
        $legacyPath = Join-Path $DestinationRoot $legacySkillName
        if (-not (Test-Path -LiteralPath $legacyPath)) {
            continue
        }

        if ($PSCmdlet.ShouldProcess($legacyPath, "Remove legacy installed skill '$legacySkillName' before update")) {
            Remove-Item -LiteralPath $legacyPath -Recurse -Force
        }
        $removedLegacy = $true
    }
    return $removedLegacy
}

function Copy-LocalSkillRoot {
    param(
        [string]$SourceRoot,
        [string]$DestinationPath
    )

    if ($PSCmdlet.ShouldProcess($DestinationPath, "Update $skillName runtime package from local repo")) {
        Copy-PackagedSkill -SourceRoot $SourceRoot -DestinationPath $DestinationPath
    }
}

if ($Source -eq 'Local' -and $Pull) {
    if (-not (Test-Path -LiteralPath $gitFolder)) {
        throw "Cannot use -Pull because '$scriptRoot' is not a git working tree."
    }

    if ($PSCmdlet.ShouldProcess($scriptRoot, 'git pull --ff-only')) {
        & git -C $scriptRoot pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            throw "git pull failed with exit code $LASTEXITCODE."
        }
    }
}

if ($PSCmdlet.ShouldProcess($DestinationRoot, 'Ensure Codex skills directory exists')) {
    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
}

$removedLegacyInstall = Remove-LegacyInstalledSkills
$hadExistingInstall = (Remove-InstalledSkill -PathToRemove $destinationPath) -or $removedLegacyInstall

if ($Source -eq 'Local') {
    Assert-SkillSourceRoot -SourceRoot $localSkillRoot

    Copy-LocalSkillRoot -SourceRoot $localSkillRoot -DestinationPath $destinationPath
}
else {
    if ($PSCmdlet.ShouldProcess($destinationPath, "Update $skillName runtime package from GitHub")) {
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
    if ($hadExistingInstall) {
        Write-Host "Skill would be updated at $destinationPath"
    }
    else {
        Write-Host "Skill would be installed to $destinationPath"
    }
}
else {
    if ($hadExistingInstall) {
        Write-Host "Updated $skillName at $destinationPath"
    }
    else {
        Write-Host "Installed $skillName to $destinationPath"
    }
    Write-Host 'Restart Codex to pick up the updated skill.'
}
