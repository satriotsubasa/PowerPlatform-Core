Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:DefaultExcludedDirectories = @(
    '.git',
    '.vs',
    '__pycache__',
    'bin',
    'coverage',
    'dist',
    'node_modules',
    'obj',
    'out'
)
$script:DefaultExcludedFiles = @('*.pyc', '*.pyo')

function Assert-SkillSourceRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot
    )

    $skillPath = Join-Path $SourceRoot 'SKILL.md'
    if (-not (Test-Path -LiteralPath $skillPath)) {
        throw "SKILL.md was not found at '$SourceRoot'. Run this script from the skill repo root."
    }
}

function Get-SkillPackageManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot
    )

    $manifestPath = Join-Path $SourceRoot 'skill-package.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Skill package manifest was not found at '$manifestPath'."
    }

    try {
        $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    }
    catch {
        throw "Could not parse skill package manifest at '$manifestPath'. $($_.Exception.Message)"
    }

    $runtimePaths = @($manifest.runtimePaths)
    if ($runtimePaths.Count -eq 0) {
        throw "Skill package manifest at '$manifestPath' does not define any runtime paths."
    }

    $sourceRootPath = [System.IO.Path]::GetFullPath($SourceRoot)
    $sourceRootPrefix = $sourceRootPath.TrimEnd('\') + '\'

    foreach ($relativePath in $runtimePaths) {
        if (-not ($relativePath -is [string]) -or [string]::IsNullOrWhiteSpace($relativePath)) {
            throw "Skill package manifest at '$manifestPath' contains an invalid runtime path entry."
        }

        if ([System.IO.Path]::IsPathRooted($relativePath)) {
            throw "Runtime path '$relativePath' in '$manifestPath' must be relative to the repo root."
        }

        $resolvedPath = [System.IO.Path]::GetFullPath((Join-Path $SourceRoot $relativePath))
        if ($resolvedPath -ne $sourceRootPath -and -not $resolvedPath.StartsWith($sourceRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Runtime path '$relativePath' in '$manifestPath' resolves outside the repo root."
        }

        if (-not (Test-Path -LiteralPath $resolvedPath)) {
            throw "Runtime path '$relativePath' listed in '$manifestPath' does not exist."
        }
    }

    $excludeDirectories = @($manifest.excludeDirectories)
    if ($excludeDirectories.Count -eq 0) {
        $excludeDirectories = $script:DefaultExcludedDirectories
    }

    $excludeFiles = @($manifest.excludeFiles)
    if ($excludeFiles.Count -eq 0) {
        $excludeFiles = $script:DefaultExcludedFiles
    }

    return [pscustomobject]@{
        ManifestPath = $manifestPath
        RuntimePaths = $runtimePaths
        ExcludeDirectories = $excludeDirectories
        ExcludeFiles = $excludeFiles
    }
}

function Copy-PackagedSkill {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    Assert-SkillSourceRoot -SourceRoot $SourceRoot
    $package = Get-SkillPackageManifest -SourceRoot $SourceRoot

    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null
    foreach ($relativePath in $package.RuntimePaths) {
        $sourcePath = Join-Path $SourceRoot $relativePath
        $destinationItemPath = Join-Path $DestinationPath (Split-Path -Leaf $sourcePath)
        Copy-PackagedItem `
            -SourcePath $sourcePath `
            -DestinationPath $destinationItemPath `
            -ExcludedDirectories $package.ExcludeDirectories `
            -ExcludedFiles $package.ExcludeFiles
    }
}

function Copy-PackagedItem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath,

        [Parameter(Mandatory = $true)]
        [string[]]$ExcludedDirectories,

        [Parameter(Mandatory = $true)]
        [string[]]$ExcludedFiles
    )

    $item = Get-Item -LiteralPath $SourcePath -Force
    if (-not $item.PSIsContainer) {
        if (-not (Test-IsExcludedFile -FileName $item.Name -ExcludedFiles $ExcludedFiles)) {
            $parentPath = Split-Path -Parent $DestinationPath
            if ($parentPath) {
                New-Item -ItemType Directory -Force -Path $parentPath | Out-Null
            }
            Copy-Item -LiteralPath $item.FullName -Destination $DestinationPath -Force
        }
        return
    }

    if (Test-IsExcludedDirectory -DirectoryName $item.Name -ExcludedDirectories $ExcludedDirectories) {
        return
    }

    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null
    foreach ($child in Get-ChildItem -LiteralPath $item.FullName -Force) {
        $childDestinationPath = Join-Path $DestinationPath $child.Name
        if ($child.PSIsContainer) {
            if (Test-IsExcludedDirectory -DirectoryName $child.Name -ExcludedDirectories $ExcludedDirectories) {
                continue
            }
        }
        elseif (Test-IsExcludedFile -FileName $child.Name -ExcludedFiles $ExcludedFiles) {
            continue
        }

        Copy-PackagedItem `
            -SourcePath $child.FullName `
            -DestinationPath $childDestinationPath `
            -ExcludedDirectories $ExcludedDirectories `
            -ExcludedFiles $ExcludedFiles
    }
}

function Copy-MergedSkillPackage {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$SourceRoots,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    foreach ($sourceRoot in $SourceRoots) {
        Copy-PackagedSkill -SourceRoot $sourceRoot -DestinationPath $DestinationPath
    }
}

function Test-IsExcludedDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DirectoryName,

        [Parameter(Mandatory = $true)]
        [string[]]$ExcludedDirectories
    )

    return $ExcludedDirectories -contains $DirectoryName
}

function Test-IsExcludedFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FileName,

        [Parameter(Mandatory = $true)]
        [string[]]$ExcludedFiles
    )

    foreach ($pattern in $ExcludedFiles) {
        if ($FileName -like $pattern) {
            return $true
        }
    }
    return $false
}

function Resolve-GitHubInstallMethod {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method
    )

    if ($Method -ne 'auto') {
        return $Method
    }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        return 'git'
    }

    return 'download'
}

function New-TemporarySkillWorktree {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-skill-stage-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    return $tempRoot
}

function Remove-TemporarySkillWorktree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathToRemove
    )

    if (Test-Path -LiteralPath $PathToRemove) {
        Remove-Item -LiteralPath $PathToRemove -Recurse -Force
    }
}

function Get-GitHubSkillSource {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Repo,

        [Parameter(Mandatory = $true)]
        [string]$Ref,

        [Parameter(Mandatory = $true)]
        [string]$Method
    )

    $resolvedMethod = Resolve-GitHubInstallMethod -Method $Method
    $tempRoot = New-TemporarySkillWorktree

    try {
        if ($resolvedMethod -eq 'git') {
            $cloneRoot = Join-Path $tempRoot 'repo'
            & git clone --depth 1 --branch $Ref "https://github.com/$Repo.git" $cloneRoot
            if ($LASTEXITCODE -ne 0) {
                throw "GitHub clone failed with exit code $LASTEXITCODE."
            }

            Assert-SkillSourceRoot -SourceRoot $cloneRoot
            return @{
                TempRoot = $tempRoot
                SourceRoot = $cloneRoot
            }
        }

        $archivePath = Join-Path $tempRoot 'repo.zip'
        $expandRoot = Join-Path $tempRoot 'archive'
        Invoke-WebRequest -Uri "https://codeload.github.com/$Repo/zip/$Ref" -OutFile $archivePath
        Expand-Archive -LiteralPath $archivePath -DestinationPath $expandRoot -Force

        $sourceRoot = Get-ChildItem -LiteralPath $expandRoot -Directory | Select-Object -First 1 -ExpandProperty FullName
        if (-not $sourceRoot) {
            throw "Expanded GitHub archive did not contain a repository root directory."
        }

        Assert-SkillSourceRoot -SourceRoot $sourceRoot
        return @{
            TempRoot = $tempRoot
            SourceRoot = $sourceRoot
        }
    }
    catch {
        Remove-TemporarySkillWorktree -PathToRemove $tempRoot
        throw
    }
}
