# Solution-Aware Cloud Flows

Use this reference when the task is about Power Automate cloud flows that live inside a Dataverse solution.

## Scope

- Prefer solution-aware cloud flows only.
- Treat the live flow as a Dataverse `workflow` record with `category = 5`.
- Use Dataverse SDK or Web API for inspect, create, update, and lint preflight work.
- Use solution ALM for cross-environment deployment.

## Working Model

- `workflow` is the Dataverse table that stores the cloud flow definition.
- `clientdata` is the important payload. It contains:
  - `properties.connectionReferences`
  - `properties.definition`
  - `schemaVersion`
- New flows created by code start as draft or off unless they are explicitly activated afterward.
- Connection references and environment variables belong in the same solution strategy as the flow.

## Preferred Execution Path

1. Inspect the existing flow first with `scripts/inspect_flow.py` when the user asks to analyze, troubleshoot, or enhance a flow.
2. Lint the flow with `scripts/lint_flow.py` before large edits or deployment.
3. Run `scripts/review_flow_hardening.py` when retry, concurrency, pagination, idempotency, or error-handling quality matters.
4. Run `scripts/review_flow_connectors.py` when Dataverse, SharePoint, Outlook, or other connector-specific read or write patterns need review.
5. Create or update the flow with `scripts/create_flow.py` or `scripts/update_flow.py`.
   - `scripts/update_flow.py` now performs semantic preflight and post-deploy checks when the update spec includes `clientData`.
   - By default it blocks updates that empty a previously non-empty switch case, remove previously existing branch actions, or violate a repo-owned flow guard contract.
   - Use `--allow-semantic-drift` only when the branch or action removal is intentional.
6. When the flow uses an HTTP trigger and the task needs its signed callback URL, resolve it with `scripts/get_flow_trigger_url.py`.
7. When the callback URL needs to be stored in Dataverse, prefer `scripts/set_environment_variable_value.py` over manual portal edits.
8. Keep the flow inside the selected unmanaged solution.
9. Promote the flow through solution deployment, not by recreating it ad hoc in each environment.

## Helper Intent

- `scripts/inspect_flow.py`
  - Inspect one flow or list solution-scoped flows.
  - Return identifiers, state, connection-reference summary, and definition summary.
- `scripts/lint_flow.py`
  - Detect missing connection references, missing triggers or actions, broken `runAfter`, hardcoded GUIDs, and hardcoded Dataverse URLs.
  - It can lint from live Dataverse or from a local `clientData`, `definition`, or JSON file.
- `scripts/review_flow_hardening.py`
  - Builds on the lint helper and returns a hardening checklist for retry policy, concurrency, pagination, idempotency, error handling, and maintainability.
  - It supports the same live or local sources as the lint helper.
- `scripts/review_flow_connectors.py`
  - Reviews connector-specific patterns in the flow definition.
  - Current connector packs focus on Dataverse, SharePoint, and Outlook action shapes.
  - It supports the same live or local sources as the lint helper.
- `scripts/create_flow.py`
  - Create a new solution-aware flow from `clientData`, or from `definition` plus `connectionReferences`.
  - Add it to the selected solution when `solutionUniqueName` is present or injected by the auth dialog.
- `scripts/update_flow.py`
  - Update an existing flow by `workflowId`, `workflowUniqueId`, `uniqueName`, or `name`.
  - Patch `clientData`, name, description, owner, and activation state.
  - When `clientData` is supplied, it inspects the live baseline first, runs semantic regression checks, updates the flow, then inspects the live result again.
  - It automatically loads an optional repo guard contract from `.codex/power-platform.flow-guards.json`, `power-platform.flow-guards.json`, or the project-profile `flowGuardSpecPath`.
- `scripts/get_flow_trigger_url.py`
  - Resolve a signed callback URL for an HTTP-trigger flow by inspecting the Dataverse `workflow` first, then mapping it to the Power Automate admin flow identity.
  - Prefer this helper when the task needs the live callback URL for an environment variable, external system, or smoke test.
- `scripts/inspect_environment_variable.py`
  - Inspect a Dataverse environment variable definition or read the current value that applies in the target environment.
- `scripts/set_environment_variable_value.py`
  - Create or update the live `environmentvariablevalue` record for an existing definition.
  - Prefer this helper instead of manual maker-portal edits when the skill needs to wire a flow endpoint or another environment-specific value.

## Spec Patterns

### Inspect

```json
{
  "name": "My Flow",
  "solutionUniqueName": "MySolution",
  "includeClientData": true
}
```

### Lint From Live Flow

```json
{
  "name": "My Flow",
  "solutionUniqueName": "MySolution"
}
```

### Lint From Local Definition

```json
{
  "definitionPath": "Dataverse/MySolution/Workflows/MyFlow.definition.json",
  "connectionReferencesPath": "Dataverse/MySolution/Workflows/MyFlow.connectionReferences.json"
}
```

### Connector Review

```json
{
  "name": "Notification Flow",
  "solutionUniqueName": "MySolution"
}
```

### Create

```json
{
  "name": "Sample Flow",
  "description": "Creates a Dataverse record from a manual trigger.",
  "solutionUniqueName": "MySolution",
  "definitionPath": "Dataverse/MySolution/Workflows/SampleFlow.definition.json",
  "connectionReferencesPath": "Dataverse/MySolution/Workflows/SampleFlow.connectionReferences.json",
  "activate": true
}
```

### Update

```json
{
  "name": "Sample Flow",
  "solutionUniqueName": "MySolution",
  "definitionPath": "Dataverse/MySolution/Workflows/SampleFlow.definition.json",
  "connectionReferencesPath": "Dataverse/MySolution/Workflows/SampleFlow.connectionReferences.json"
}
```

### Flow Guard Contract

Store repo-specific critical-branch rules in `.codex/power-platform.flow-guards.json` or point the project profile at another file.

```json
{
  "flows": [
    {
      "match": {
        "displayName": "[Example] When Document Signed"
      },
      "requiredSwitchCases": [
        {
          "switchName": "Determine_document_type",
          "caseName": "Case A",
          "requiredActionNames": [
            "List_rows_contoso_contacts",
            "List_rows_contoso_authorisedcontacts"
          ]
        }
      ]
    }
  ]
}
```

Use [references/power-platform.flow-guards.template.json](references/power-platform.flow-guards.template.json) as the starting point when the repo has critical switch branches that must not go empty.
Do not leave this as a hypothetical safeguard only in chat history. Add a real `.codex/power-platform.flow-guards.json` in the repo for critical flows such as `[Example] When Document Signed`.

### Resolve Trigger URL

```json
{
  "name": "Inbound HTTP Flow",
  "solutionUniqueName": "MySolution"
}
```

### Set Environment Variable Value

```json
{
  "schemaName": "contoso_InboundCallbackUrl",
  "value": "https://prod-00.westeurope.logic.azure.com/..."
}
```

## Common Delivery Chain

For the common code-first delivery pattern:

1. create or update the solution-aware flow
2. resolve the signed trigger URL
3. set the environment variable value
4. smoke test the endpoint only if the user asked for it

`scripts/apply_requirement_spec.py` can now orchestrate that chain with flow and environment-variable steps in one requirement spec.

## ALM Guidance

- Do not treat raw live flow edits as the deployment story.
- Keep flow promotion inside solution export or import, the same as the rest of the Dataverse solution.
- When a solution contains many things beyond the flow, that is still normal. The selected working solution remains the target container.
- If the user wants a flow-only promotion model, that is a solution-structure question:
  - use a patch
  - use a child solution
  - or use a dedicated flow solution

## Safety

- Do not delete flows unless the user explicitly requests it.
- Prefer lint plus inspect before major changes.
- For critical flows, keep a repo-owned flow guard contract so `scripts/update_flow.py` can block accidental branch loss before deployment.
- Ask before publish or import steps that affect the environment.
- Keep connection references and environment variables explicit rather than hardcoding environment-specific values in the definition.
- The Dataverse and Power Apps admin surfaces still use separate auth stacks. One extra Power Apps login prompt can still be expected for trigger-URL retrieval until those surfaces are unified.
