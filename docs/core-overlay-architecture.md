# Core And Overlay Architecture

This repository is the source of truth for the generic Power Platform skill. Overlay extensions (e.g. `PowerPlatform-Overlay`) layer on top of this generic base to add house-style conventions.

## Goal

Use one place for generic maintenance.

- Put broadly reusable Dataverse and Power Platform behavior in Core.
- Keep house-specific repo conventions in overlay repos.
- Avoid making the same generic code or documentation change in two repositories.

## Ownership

### Core owns

Keep these here and treat this repo as the primary maintenance location:

- generic helper scripts in `scripts/`
- generic execution tools in `tools/`
- generic tests in `tests/`
- generic visual assets in `assets/`
- generic packaging and installation behavior
- generic references such as:
  - `references/context-and-alm.md`
  - `references/execution-automation.md`
  - `references/helper-strategy.md`
  - `references/dataverse-design.md`
  - `references/dataverse-metadata.md`
  - `references/data-operations.md`
  - `references/client-customization.md`
  - `references/server-extensions.md`
  - `references/pcf-controls.md`
  - `references/power-automate-flows.md`
  - `references/solution-patches.md`
  - `references/solution-standards.md`
  - `references/power-fx.md`
  - `references/custom-connectors.md`
  - `references/document-generation.md`
  - `references/queries-and-xml.md`
  - `references/repo-archetypes.md`
  - `references/project-profile.md`
  - `references/project-profile.template.json`
  - `references/project-context-template.md`
  - `references/thread-continuity.md`

### Overlay extensions own

Keep these in the overlay repo and avoid turning them into Core defaults:

- overlay `SKILL.md`
- overlay `agents/openai.yaml`
- overlay-specific convention references (e.g. house-style naming guides)
- overlay-specific project-profile examples
- overlay-specific examples, prompts, and documentation that assume a particular namespace, naming, or folder convention

## Overlay Discovery

Core automatically discovers installed overlay extensions by scanning `~/.codex/skills/*/skill-package.json` for skills that declare `"extends": "powerplatform-core"`. When an overlay is found and the current repo matches its conventions, Core suggests using the overlay instead.

## Maintenance Rule

When you discover a new capability or fix:

1. If it is useful to a broad Power Platform developer, implement it in Core first.
2. If an overlay also needs it, flow that change into the overlay through the overlay's composed install or local sync workflow. Do not fork the same generic behavior into a separate overlay-owned implementation without a real convention reason.
3. If the change is only about house conventions, prompts, naming, or repo-shape rules, keep it in the overlay only.
4. If an overlay rule becomes broadly useful, promote it back into Core in a generic form.

## Trigger Separation

Use `powerplatform-core` when:

- the repo is unfamiliar or varied
- there is no special house convention to preserve
- the goal is broad public Power Platform support

Use an overlay skill (e.g. `powerplatform-overlay`) when:

- the repo follows a specific house convention or layered enterprise pattern
- preserving that structure is part of the task
- the overlay's `skill-package.json` declares `"extends": "powerplatform-core"`

## Current Install Model

Composed installation is the active model:

1. `powerplatform-core` installs directly from this repo's runtime package
2. Overlay skills install by copying this repo's runtime package first
3. The overlay package then replaces `SKILL.md`, `agents/openai.yaml`, and selected overlay references

The overlay repo keeps only overlay-owned files in source control. When a maintainer wants a local combined working tree, Core-owned runtime files can be materialized temporarily and kept ignored by git.
