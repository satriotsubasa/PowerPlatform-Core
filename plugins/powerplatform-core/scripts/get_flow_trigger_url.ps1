[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SpecFile,

    [Parameter(Mandatory = $false)]
    [string]$Username,

    [Parameter(Mandatory = $false)]
    [string]$TenantId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Import-Module Microsoft.PowerApps.Administration.PowerShell -ErrorAction Stop

function Get-RouteErrorMessage {
    param(
        [Parameter(Mandatory = $true)]
        [System.Management.Automation.ErrorRecord]$ErrorRecord
    )

    if ($ErrorRecord.Exception -and $ErrorRecord.Exception.Message) {
        return $ErrorRecord.Exception.Message
    }

    return $ErrorRecord.ToString()
}

function Get-DerivedCallbackUrl {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Response
    )

    if ($null -ne $Response.PSObject.Properties["value"] -and $Response.value) {
        return [string]$Response.value
    }

    if (
        $null -ne $Response.PSObject.Properties["basePath"] -and $Response.basePath -and
        $null -ne $Response.PSObject.Properties["relativePath"] -and $Response.relativePath
    ) {
        $builder = [System.UriBuilder]::new([string]$Response.basePath)
        $relativePath = [string]$Response.relativePath
        if ($builder.Path.EndsWith("/") -and $relativePath.StartsWith("/")) {
            $builder.Path = $builder.Path.TrimEnd("/") + $relativePath
        } else {
            $builder.Path = $builder.Path + $relativePath
        }

        if ($null -ne $Response.PSObject.Properties["queries"] -and $Response.queries) {
            $pairs = @()
            foreach ($property in $Response.queries.PSObject.Properties) {
                $pairs += "{0}={1}" -f [uri]::EscapeDataString($property.Name), [uri]::EscapeDataString([string]$property.Value)
            }
            $builder.Query = ($pairs -join "&")
        }

        return $builder.Uri.AbsoluteUri
    }

    return $null
}

function Connect-PowerAppsSession {
    param(
        [Parameter(Mandatory = $false)]
        [string]$Username,

        [Parameter(Mandatory = $false)]
        [string]$TenantId
    )

    $parameters = @{
        Endpoint = "prod"
        UseSystemBrowser = $true
    }

    if ($Username) {
        $parameters["Username"] = $Username
    }
    if ($TenantId) {
        $parameters["TenantID"] = $TenantId
    }

    Add-PowerAppsAccount @parameters | Out-Null
}

function Resolve-Environment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OrganizationId
    )

    $matching = @(Get-AdminPowerAppEnvironment -ReturnCdsDatabaseType $false | Where-Object {
        $_.OrganizationId -and $_.OrganizationId.ToString().Equals($OrganizationId, [System.StringComparison]::OrdinalIgnoreCase)
    })

    if ($matching.Count -eq 0) {
        throw "Could not resolve a Power Platform environment for Dataverse organizationId '$OrganizationId'."
    }
    if ($matching.Count -gt 1) {
        throw "More than one Power Platform environment matched Dataverse organizationId '$OrganizationId'."
    }

    return $matching[0]
}

function Resolve-AdminFlow {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EnvironmentName,

        [Parameter(Mandatory = $true)]
        [string]$WorkflowId
    )

    $matches = @(Get-AdminFlow -EnvironmentName $EnvironmentName | Where-Object {
        $_.WorkflowEntityId -and $_.WorkflowEntityId.ToString().Equals($WorkflowId, [System.StringComparison]::OrdinalIgnoreCase)
    })

    if ($matches.Count -eq 0) {
        throw "Could not resolve a Power Automate admin flow whose WorkflowEntityId matches '$WorkflowId'."
    }
    if ($matches.Count -gt 1) {
        throw "More than one Power Automate admin flow matched WorkflowEntityId '$WorkflowId'."
    }

    return $matches[0]
}

$spec = Get-Content -Raw $SpecFile | ConvertFrom-Json -Depth 20
Connect-PowerAppsSession -Username $Username -TenantId $TenantId

$environment = Resolve-Environment -OrganizationId $spec.organizationId
$adminFlow = Resolve-AdminFlow -EnvironmentName $environment.EnvironmentName -WorkflowId $spec.workflowId
$triggerName = [string]$spec.triggerName
$apiVersion = if ($spec.apiVersion) { [string]$spec.apiVersion } else { "2016-11-01" }

$routeCandidates = @(
    "https://{flowEndpoint}/providers/Microsoft.ProcessSimple/environments/{environment}/flows/{flowName}/triggers/{triggerName}/listCallbackUrl?api-version={apiVersion}",
    "https://{flowEndpoint}/providers/Microsoft.ProcessSimple/scopes/admin/environments/{environment}/flows/{flowName}/triggers/{triggerName}/listCallbackUrl?api-version={apiVersion}"
)

$errors = @()
foreach ($routeTemplate in $routeCandidates) {
    $route = $routeTemplate `
        -replace "\{environment\}", [string]$environment.EnvironmentName `
        -replace "\{flowName\}", [string]$adminFlow.FlowName `
        -replace "\{triggerName\}", $triggerName `
        -replace "\{apiVersion\}", $apiVersion

    try {
        $response = InvokeApi -Method POST -Route $route -Body @{} -ThrowOnFailure -ApiVersion $apiVersion
        $callbackUrl = Get-DerivedCallbackUrl -Response $response
        if (-not $callbackUrl) {
            throw "The callback response did not include a resolvable callback URL."
        }

        [pscustomobject]@{
            success = $true
            environmentName = $environment.EnvironmentName
            environmentDisplayName = $environment.DisplayName
            organizationId = $spec.organizationId
            workflowId = $spec.workflowId
            workflowName = $spec.workflowName
            flowName = $adminFlow.FlowName
            triggerName = $triggerName
            callbackUrl = $callbackUrl
            routeUsed = $route
            response = $response
        } | ConvertTo-Json -Depth 30
        exit 0
    }
    catch {
        $errors += [pscustomobject]@{
            route = $route
            message = Get-RouteErrorMessage -ErrorRecord $_
        }
    }
}

throw ("Unable to resolve a signed callback URL for flow '{0}' trigger '{1}'. Routes attempted: {2}" -f `
    $adminFlow.FlowName,
    $triggerName,
    (($errors | ConvertTo-Json -Depth 8 -Compress)))
