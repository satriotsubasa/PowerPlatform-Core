# Project Profile

Use this reference when a repo has a stable architecture that discovery should not have to guess every time.

## Purpose

Some repos have stable source areas that discovery should not have to guess every time. Common examples include:

- layered code areas such as `*.Business`, `*.Plugins`, and `*.Data`
- dedicated `WebResources`, `*.PCF`, or `Word Templates` folders
- repos where only part of the Dataverse solution source is stored locally
- repos where a local unpacked solution is only a supporting packaging solution such as a PCF wrapper, not the main business app solution

For those repos, add an optional project profile file so the skill can keep using the existing structure without guessing the wrong live solution.
If the repo is solution-only, very small, or still sparse, do not force a profile unnecessarily.

## Supported File Paths

The discovery script checks these locations in order:

- `.codex/power-platform.project-profile.json`
- `power-platform.project-profile.json`

Prefer the `.codex/` path when the profile is repo-local guidance rather than business-domain source.

Starter examples are included in this repo:

- `references/project-profile.template.json`
- `references/power-platform.flow-guards.template.json`

Overlay-specific project-profile examples should live in the overlay repo that owns those conventions, not in Core.

## Recommended Fields

```json
{
  "repoSolutionName": "Contoso.Sample",
  "mainSolutionUniqueName": "ContosoCore",
  "publisherPrefix": "cts",
  "managedStrategy": "both",
  "repoArchetype": "layered-dotnet-dataverse",
  "solutionSourceModel": "hybrid-code-and-supporting-solution-source",
  "namespaceRoot": "Contoso.Sample",
  "localSupportingSolutions": [
    "Contoso_PCF"
  ],
  "criticalPluginSteps": [
    "Account Create"
  ],
  "flowGuardSpecPath": ".codex/power-platform.flow-guards.json",
  "deploymentDefaults": {
    "environmentAliases": {
      "dev": "https://contoso-dev.crm.dynamics.com"
    },
    "defaultEnvironmentAlias": "dev",
    "manualOnlySurfaces": [
      "canvas-command-library",
      "maker-app-designer"
    ],
    "preferredDeploymentPaths": {
      "plugin": "push-plugin",
      "pcf": "deploy-pcf",
      "webresource": "sync-webresource",
      "metadata": "targeted-helper",
      "data": "upsert-data",
      "flow": "update-flow",
      "solution-import": "deploy-solution"
    },
    "timeouts": {
      "pluginPushSeconds": 300,
      "solutionImportSeconds": 900,
      "lockRetryCount": 10,
      "lockWaitSeconds": 30,
      "rowRetryCount": 2
    },
    "plugin": {
      "verifyStepStateByDefault": true,
      "autoReconcileStepStateByDefault": true,
      "pluginIds": {
        "primaryAssembly": "11111111-1111-1111-1111-111111111111"
      }
    },
    "dataWrites": {
      "typedColumns": {
        "account": {
          "statuscode": "choice"
        }
      }
    }
  },
  "intentionallyDisabledPluginSteps": [
    {
      "name": "Account Archive",
      "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
      "messageName": "Update",
      "primaryEntityLogicalName": "account",
      "stage": "PreOperation",
      "mode": "Synchronous"
    }
  ],
  "sourceAreas": {
    "business": "Contoso.Sample.Business",
    "data": "Contoso.Sample.Data",
    "supplementalData": "Data",
    "plugins": "Contoso.Sample.Plugins",
    "webResources": "WebResources",
    "pcf": "Contoso.Sample.PCF",
    "wordTemplates": "Word Templates",
    "dataverse": "Dataverse",
    "reference": "Reference"
  }
}
```

## Field Guidance

- `mainSolutionUniqueName`: the main live Dataverse solution the skill should target for app work.
- `localSupportingSolutions`: local solution sources that exist only for packaging or support work, such as a PCF wrapper solution.
- `sourceAreas.business`, `data`, `plugins`, `webResources`, `pcf`: the repo paths that are authoritative for those asset types.
- `sourceAreas.supplementalData`: use this for root `Data/` folders that hold JSON seed data, configuration snapshots, or migration content instead of early-bound code.
- `sourceAreas.wordTemplates`: use this for source-controlled `.docx` templates that drive plug-in or document-generation logic.
- `sourceAreas.dataverse`: the local metadata reference area, typically hydrated from the selected live solution when needed.
- `sourceAreas.reference`: docs, guides, or external references only. Do not treat this as a deployment source by default.
- `criticalPluginSteps`: optional step selectors that must stay enabled after plug-in push or registration work. A simple string matches by step `name`; an object can match by `name`, `pluginTypeName`, `messageName`, `primaryEntityLogicalName`, `stage`, or `mode`.
- `intentionallyDisabledPluginSteps`: optional step selectors that should remain disabled even after registration or push flows. Use the same selector shape as `criticalPluginSteps`.
- `flowGuardSpecPath`: optional relative path to a repo-owned flow-guard contract. If omitted, Core will look for `.codex/power-platform.flow-guards.json` and then `power-platform.flow-guards.json`.
- `deploymentDefaults`: optional deploy-orchestration hints used by Core helpers and `apply_requirement_spec.py` to classify live work earlier and stop faster when the preferred headless path is weak or blocked.
- `deploymentDefaults.environmentAliases`: optional alias-to-environment map for repo-owned deploy wrappers or project guidance.
- `deploymentDefaults.defaultEnvironmentAlias`: optional default alias to mention in repo guidance.
- `deploymentDefaults.manualOnlySurfaces`: optional list of surfaces that should fail fast to a manual fallback instead of spending time on headless retries. Match by asset type, primitive name, or repo vocabulary.
- `deploymentDefaults.preferredDeploymentPaths`: optional asset-type to primitive map that tells Core which path the repo prefers for `plugin`, `pcf`, `webresource`, `metadata`, `data`, `flow`, or `solution-import`.
- `deploymentDefaults.timeouts`: optional timeout defaults. Core currently reads `pluginPushSeconds` and `solutionImportSeconds` directly and preserves the other keys as repo guidance for wrapper scripts.
- `deploymentDefaults.plugin.verifyStepStateByDefault`: optional default that makes `push_plugin.py` verify plug-in step state even when the caller did not pass `--verify-step-state`.
- `deploymentDefaults.plugin.autoReconcileStepStateByDefault`: optional default that makes `push_plugin.py` reconcile drift automatically unless the caller opts out.
- `deploymentDefaults.plugin.pluginIds`: optional repo-owned identifiers for deploy wrappers or local conventions. Core keeps this generic and does not infer meaning beyond “repo-known IDs”.
- `deploymentDefaults.dataWrites.typedColumns`: optional table and column map for auto-coercing plain integer values into typed Dataverse payloads, such as `{ "type": "choice", "value": 1 }`, when the repo knows a column must be written as a typed choice.

## Operating Model

With a project profile in place:

- plug-in work still comes from `*.Business`, `*.Plugins`, and `*.Data`
- plug-in registration defaults can inherit expected enabled or disabled step state from `criticalPluginSteps` and `intentionallyDisabledPluginSteps`
- deployment orchestration can classify the asset type, preferred primitive, timeout budget, and fallback path before attempting live execution
- plug-in push can inherit default step-state verification and reconcile behavior from `deploymentDefaults.plugin`
- row-write helpers can coerce configured typed columns automatically from `deploymentDefaults.dataWrites.typedColumns`
- critical flows can inherit semantic deployment checks from `flowGuardSpecPath` or the default flow-guard file paths
- web resource work still comes from `WebResources`
- PCF work still comes from `*.PCF`
- document-template work comes from `Word Templates`
- metadata reference work can use `Dataverse/<solution-unique-name>/`
- the selected live solution remains the deployment target

The profile does not replace discovery. It narrows ambiguity and prevents the skill from confusing a supporting local solution with the main app solution.
If a repo uses different folder names, set those exact paths here instead of renaming the repo to fit an example.
