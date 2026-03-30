# PCF Controls

Use this reference for Power Apps component framework controls.

## When To Use PCF

Choose PCF when the requirement needs:

- richer field visualization
- reusable custom input behavior
- dataset rendering
- a supported alternative to heavy HTML web resources

If a simple form script or lightweight HTML web resource is enough, prefer the simpler option.

## Scaffolding

When creating a new control from scratch, prefer:

`pac pcf init --namespace <Namespace> --name <ControlName> --template field`

Reusable helper:

- use `scripts/scaffold_pcf_control.py` to create a new control inside the inferred or explicit PCF area

Use:

- `--template field` for single-field controls
- `--template dataset` for grid-like experiences
- `--framework react` only when the repo or requirement justifies it

Keep namespaces aligned with the publisher prefix or repo convention.

## Implementation Rules

- Keep dependencies lean.
- Design for empty, loading, error, and disabled states.
- Preserve accessibility and keyboard behavior.
- Keep manifest names, inputs, outputs, and resources consistent with the repo naming pattern.
- Avoid introducing a new frontend toolchain if the repo already standardizes one.

## Solution Integration

Tie the control back to the solution and target environment explicitly.

- keep the control in source control
- add the project to the solution project when the repo uses solution references
- build locally before any push
- ask before `pac pcf push`
- if the repo has a wrapper `Solutions` project, treat that wrapper as the normal deployable package path

For wrapper-solution repos, the common pattern is:

- development validation builds land in `Solutions\bin\Debug`
- deployable artifacts land in `Solutions\bin\Release`
- `Release` often produces both managed and unmanaged zips; prefer the managed artifact unless the user asks for unmanaged import

PCF versioning usually has two surfaces in those repos:

- the 3-part `version` attribute in `ControlManifest.Input.xml`
- the 4-part version in `Solutions\src\Other\Solution.xml`

Prefer updating both together through `scripts/version_pcf_solution.py`.

If push is approved and the target values are known, the common pattern is:

`pac pcf push --publisher-prefix <prefix> --solution-unique-name <solution>`

Reusable helper:

- use `scripts/deploy_pcf.py` in `auto` mode to install dependencies, build, and either package-import the wrapper solution or fall back to direct `pac pcf push`
- use `scripts/version_pcf_solution.py` when the package version needs to change before deployment
- use `scripts/bind_pcf_control.py` to attach the deployed control to an existing form control through headless `systemform.formxml` updates when the binding is deterministic
- use `scripts/add_solution_components.py` if the control or related form metadata still needs explicit solution placement

## Validation

Before finishing:

- install dependencies if needed
- run the repo's build command
- verify the control manifest
- verify the wrapper solution version and packaged artifact when the repo uses `Solutions`
- bind the control with `scripts/bind_pcf_control.py` when the requirement includes the target form control details
- report only the remaining environment steps that still cannot be executed headlessly
