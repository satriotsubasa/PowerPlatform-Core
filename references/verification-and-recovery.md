# Verification And Recovery

Use this reference when planning or closing out Dataverse-affecting work, and when a deployment, import, publish, or registration flow fails part-way.

## Completion Standard

Do not treat a Dataverse-affecting task as complete just because the repo changed locally, a helper finished, or an import command returned success.

State the outcome at the narrowest true level:

- repo change prepared
- build, pack, or validation completed
- target environment updated
- live behavior verified
- targeted regression checked when relevant

If the work only reached one of those levels, say that plainly instead of implying the later levels happened too.

## Minimum Evidence By Layer

Use the narrowest relevant set of layers for the task:

1. source or artifact evidence
2. build, pack, or validation evidence
3. live metadata, registration, publish, or import evidence
4. focused live behavior evidence
5. targeted regression evidence when an adjacent path could have been disturbed

If a layer did not happen, report that it did not happen. Do not fill the gap with optimistic wording.

## What Counts As Proof

### Source or artifact evidence

- inspect the unpacked diff, targeted XML change, generated asset, or helper payload
- confirm the exact files, schema names, logical names, versions, and solution surfaces that changed

### Build, pack, or validation evidence

- run the smallest relevant build, pack, sync, unpack, checker, or validation command
- confirm the command succeeded against the intended project or artifact

### Live metadata, registration, publish, or import evidence

- confirm the intended component landed in the approved target environment
- verify the target solution, registration, or binding instead of stopping at command success text

### Focused live behavior evidence

- run one realistic scenario that exercises the changed path
- prefer the smallest live check that proves the behavior, not a broad smoke test

### Targeted regression evidence

- check one nearby or previously working path that could have been disturbed by the change
- keep it narrow and relevant instead of turning every task into a full regression pass

## Verification Patterns By Surface

### Metadata, forms, views, app exposure, or solution XML

- inspect the unpacked diff or targeted XML change
- run the smallest relevant pack, sync, unpack, or checker command when appropriate
- if imported live, verify the target component exists in the intended solution and app surface
- if the change affects user interaction, perform one focused live check on the changed form, view, command, or navigation surface

### Plug-ins and Custom APIs

- restore and build the affected project
- confirm the intended assembly, package, step, image, filtering attributes, or API contract assumptions
- if registration or push happened, verify that the live component update actually landed
- run one narrow live scenario for the changed server-side path
- add one targeted regression check when the change could affect another message, step, or caller path

### PCF

- build the control
- verify manifest metadata and version surfaces
- verify the wrapper solution artifact when the repo uses a `Solutions` project
- if deployed live, confirm the control is available or bound in the intended surface
- perform one focused interaction check on the behavior that changed

### Client scripts and web resources

- verify handler names, logical names, dependencies, and emitted assets
- if the resource was pushed or imported, verify the intended registration or form usage
- when the change affects user-visible behavior, perform one focused live interaction check
- add one nearby event-path check if the change could affect load, save, on-change, or ribbon behavior outside the main path

### Data writes, seed scripts, and migrations

- confirm the target environment, table, and keying strategy
- record whether the action created, updated, or upserted data
- verify the smallest representative row or result set
- if a dry-run mode exists, say whether the run was dry-run only or applied live
- when repeatability matters, confirm whether the operation is idempotent or still requires cleanup before a rerun

## Failure Recovery Sequence

When a Dataverse-affecting flow fails part-way:

1. stop broad reruns and extra edits
2. inspect what actually landed
3. decide whether the repo or the live environment is currently authoritative
4. choose the smallest safe repair or reconciliation step
5. re-run the minimum relevant verification layers

Do not stack more local edits or retries on top of an unclear state.

## Choosing What Is Authoritative

Do not guess when repo and live Dataverse disagree.

Treat the repo as authoritative when:

- the repo contains the approved source-controlled change and live deployment is incomplete or failed
- the user explicitly wants the repo state to be pushed as the intended result
- the live environment appears partially updated or stale compared to the reviewed repo diff

Treat live Dataverse as authoritative when:

- the repo is missing recent approved environment work
- the user explicitly says the environment is the current source of truth
- the current task is reconciliation or reference hydration rather than deployment from repo source

Escalate and clarify instead of choosing a side when:

- both sides may contain valid new work
- the live environment was changed outside the repo and the intended winner is unclear
- the selected solution, patch target, or deployment boundary is ambiguous

## Failure Recovery Patterns

### If imports or publish operations collide

- do not skip the step immediately
- prefer an existing helper retry window first
- if the active path has no built-in retry window, confirm whether another import or publish is still running, wait for the environment to clear, and rerun one approved import or publish once
- if the second attempt still fails, stop and report the exact lock state instead of looping blindly

### If metadata or registration only partially lands

- inspect the target solution and component state before retrying
- prefer a narrow repair over replaying the whole deployment sequence
- verify that duplicate partial components were not created before rerunning create paths

### If source and live Dataverse drift apart

- stop further mutation
- identify whether the repo or live environment is meant to win using the authority rules above
- if that answer is still unclear, ask before reconciling

### If a plug-in or custom API deploys but behavior did not change

- verify the expected assembly or package actually updated
- verify the step, image, filtering attributes, and target message assumptions
- run one focused scenario that exercises the changed branch instead of assuming deployment equals behavior

## Closeout Checklist

Before reporting completion for Dataverse-affecting work, state:

- what changed in source
- what was built or validated
- whether the approved target environment was updated yet
- whether live behavior was verified
- what still requires import, publish, registration, approval, or follow-up
