param(
    [string]$TargetUrl,
    [string]$Username,
    [string]$TenantId,
    [switch]$AutoValidate,
    [string]$RepoRoot = ".",
    [switch]$EnsureDataverseReference,
    [ValidateSet("Managed", "Unmanaged", "Both")]
    [string]$ReferencePackageType = "Unmanaged",
    [string]$Output
)

$scriptPath = Join-Path $PSScriptRoot "auth_context.py"
$arguments = @($scriptPath)

if ($TargetUrl) {
    $arguments += @("--target-url", $TargetUrl)
}

if ($Username) {
    $arguments += @("--username", $Username)
}

if ($TenantId) {
    $arguments += @("--tenant-id", $TenantId)
}

if ($AutoValidate) {
    $arguments += "--auto-validate"
}

if ($RepoRoot) {
    $arguments += @("--repo-root", $RepoRoot)
}

if ($EnsureDataverseReference) {
    $arguments += "--ensure-dataverse-reference"
}

if ($ReferencePackageType) {
    $arguments += @("--reference-package-type", $ReferencePackageType)
}

if ($Output) {
    $arguments += @("--output", $Output)
}

& python @arguments
exit $LASTEXITCODE
