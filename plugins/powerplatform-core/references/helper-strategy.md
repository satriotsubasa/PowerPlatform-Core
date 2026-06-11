# Helper Strategy

Use this reference when deciding whether a capability should become a dedicated helper script or remain partly workflow-driven.

## Core Rule

Prefer a dedicated helper when the operation is:

- deterministic
- repeatable across repos
- environment-safe with clear inputs
- easier to validate as a discrete unit than as freeform reasoning

Keep part of the work in the skill workflow when the operation depends heavily on repo-specific judgment, business architecture, or ambiguous design choices.

## Three Categories

### 1. Straightforward To Package As Dedicated Helpers

These are the kinds of operations that should become reusable scripts whenever practical. Several are already implemented in this repo:

- richer form mutation
- richer view mutation
- batch web resource sync and publish
- PCF binding and packaging helpers
- solution component placement helpers
- deployment and testing helpers
- document-template inspection helpers for `Word Templates`

These are usually deterministic enough for explicit inputs and stable outputs.

### 2. Possible, But Needs Careful Design

These are worth packaging, but only after the input model is clear:

- end-to-end requirement orchestration for larger multi-area changes
- complex form designer behavior replication
- patch, merge, and solution-upgrade workflows
- Power Automate Dataverse query or expression generation and validation
- document-template and content-control automation that depends on repo conventions

Several first-pass Category 2 helpers are now implemented in this repo:

- flow hardening review
- flow connector review
- Dataverse schema and query design
- solution standards review
- Power Fx debugging
- custom connector and integration-wrapper design
- document-generation planning
- patch and merge planning

These often need a strong spec format, repo profile, or staged validation flow before they are safe helpers.

### 3. Better Kept Partly Workflow-Driven

Do not force these into generic helpers unless a stable pattern emerges:

- bespoke XML surgery
- one-off business logic design
- architecture decisions that depend on the current app shape
- tasks where the "right" implementation depends on repo-specific conventions more than on mechanics

For these, keep the helper layer focused on deterministic sub-operations and let the skill workflow compose them.

## Target Operating Model

The intended split is:

- dedicated helpers for deterministic execution
- skill workflow for composition, interpretation, and repo-specific judgment

Examples:

- plug-in deployment helper: good helper
- web resource sync helper: good helper
- choose whether a document-generation change belongs in plug-in logic, placeholder config, or template structure: workflow judgment

## Next Helper Backlog

### Next helper batches

1. live environment validation for the newest design and review helpers
2. richer flow-connector authoring helpers that go beyond review into controlled generation
3. document-template authoring helpers when a stable repo pattern emerges

### After that

1. direct patch-execution helpers that move beyond planning into controlled environment operations
2. stronger repo-profile adoption guidance across more repo archetypes

### Keep workflow-driven for now

- freeform architectural refactors
- bespoke document-generation logic design
- unusual XML-only fixes with low reuse

## Practical Decision Test

Before adding a new helper, ask:

1. Can I define a stable input schema?
2. Can I validate the output mechanically?
3. Is this likely to be reused across repos?
4. Would the helper reduce risk compared with freeform execution?

If most answers are yes, package it as a helper.
If not, keep it as workflow guidance and use existing helpers for the deterministic parts.
