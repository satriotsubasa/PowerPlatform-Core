# CODEX Handoff

Last updated: 2026-03-29

## Purpose

This file is the current continuity note for `PowerPlatform-Core`.

If work resumes in a new Codex thread:

1. read this file
2. read `README.md`
3. run `python .\verify_repo.py` if files changed

## Repo Role

This repo is the generic source of truth for the public Power Platform Codex skill runtime.

It owns:

- generic skill behavior
- generic references
- generic helper scripts
- generic tools
- generic regression tests
- generic packaging and install behavior

It does not own:

- overlay-specific conventions
- overlay-specific prompts or examples
- house-style reference files

Overlay repos (e.g. `PowerPlatform-Overlay`) layer on top of this runtime to add house-style conventions.

## Current State

Clean state after production-ready rename and scrub:

- Skill ID: `powerplatform-core`
- GitHub: `satriotsubasa/PowerPlatform-Core`
- All company-specific references removed from test fixtures, templates, and documentation
- Core overlay discovery supports any extension via `"extends": "powerplatform-core"` in overlay `skill-package.json`

## Architecture State

Important current decisions:

- Core is generic and should not assume one house structure.
- Core is explicitly code-first for executable logic and should not choose Dataverse Business Rules as an implementation surface.
- Layered `.sln + Business/Data/Plugins/WebResources` repos are supported as one archetype among several.
- Discovery handles layered, ambiguous, tool-only, and sparse repos.
- Surface selection routes through `references/execution-surface-guide.md`.
- Live-affecting work routes through `references/verification-and-recovery.md`.
- Core auto-discovers overlay extensions at runtime and suggests them when relevant.

## Overlay Relationship

Core supports a composition model for house-style extensions:

- Core installs directly as `powerplatform-core`
- Overlay extensions install separately and layer on top of this runtime
- Any overlay declaring `"extends": "powerplatform-core"` in its `skill-package.json` is discovered at runtime

## Resume Checklist

When resuming:

1. read this file
2. read `README.md`
3. run `python .\verify_repo.py`
4. inspect `git status`
5. if continuing the same batch, review the local uncommitted changes before starting new edits
