# PowerPlatform-Core

General-purpose Power Platform and Dataverse skill runtime for code-first, repo-backed execution in coding-agent workflows.

This skill is designed to maximize source-controlled, reviewable, testable, and maintainable execution. When a reliable code, metadata, or headless automation path exists, prefer it over portal-first or designer-first workflows.

This repository is the public, repo-agnostic base skill. It is meant to work across unfamiliar Power Platform and Dataverse repos, including:

- layered code-centric repos
- unpacked-solution repos
- mixed or ambiguous repos
- sparse repos with little or no existing structure

Opinionated house conventions belong in overlay repos, not here.

## What Core Owns

Core is the maintenance home for:

- generic skill contract in `SKILL.md`
- generic references in `references/`
- generic helper scripts in `scripts/`
- generic tools in `tools/`
- generic regression tests in `tests/`
- generic packaging and install behavior

Current overlay relationship:

- `powerplatform-core` installs directly from this repo
- Overlay extensions (e.g. `PowerPlatform-Overlay`) install as separate layers on top of this runtime
- House-style conventions are overlay-owned and are not shipped as Core references

That overlay note is informational only. Core remains a standalone, generic skill for broader Power Platform use.

## Current Capabilities

Core currently supports:

- repo discovery and context inference through `scripts/discover_context.py`
- auth gating and selected-solution confirmation through `scripts/auth_context.py`
- Dataverse row create, update, and upsert
- metadata creation and update helpers for tables, fields, lookups, forms, views, icons, and solution component placement
- security role inspect, create, and update helpers with solution-aware role privilege sync
- environment variable inspect and live value-set helpers
- client customization helpers for form-event registration, web resource sync, and PCF binding
- server-extension helpers for custom APIs, first-time plug-in registration, and repeatable plug-in push
- PCF scaffolding, versioning, packaging, and deployment
- solution-aware cloud flow inspect, lint, create, update, signed HTTP trigger URL retrieval, and hardening review
- document-generation inspection and planning
- solution deployment and delivery validation
- coordinated multi-step execution through `scripts/apply_requirement_spec.py`

For the fuller maintainer-oriented capability breakdown that used to live in the long README, see [docs/capability-matrix.md](docs/capability-matrix.md).

Core guidance now also explicitly covers:

- choosing the right implementation surface through [references/execution-surface-guide.md](references/execution-surface-guide.md)
- completion evidence and partial-failure recovery through [references/verification-and-recovery.md](references/verification-and-recovery.md)
- immutable stable keys, source-system-qualified provenance, and honest dry-run boundaries in data operations
- explicit deployment closeout that distinguishes repo-ready from environment-updated state

## Design Principles

- Keep the skill generic. Do not hardcode one tenant, one publisher prefix, one namespace pattern, or one repo layout.
- Keep presentation and configuration work in metadata when possible.
- For executable logic, prefer code-managed surfaces. Use client script for form-scoped behavior and plug-ins or custom APIs for shared server-side behavior.
- Do not choose Dataverse Business Rules as an implementation surface in this skill.
- Prefer repo-backed and headless-first execution over browser automation.
- Surface PAC-profile versus requested-target mismatches before live work instead of silently assuming the currently selected PAC environment is correct.
- Keep changes solution-scoped.
- Ask before delete, import, publish, register, push, or upgrade.
- Treat project context as runtime input, not fixed skill configuration.

## Repo Layout

Important top-level paths:

- `SKILL.md`: skill contract and workflow
- `agents/`: UI metadata
- `references/`: generic working guidance
- `scripts/`: Python helper entry points
- `tools/`: shared .NET tools
- `tests/`: repo-local regression coverage
- `docs/core-overlay-architecture.md`: Core vs overlay ownership
- `verify_repo.py`: canonical local verification entry point

## Verification

Canonical local verification:

```powershell
python .\verify_repo.py
```

That command currently runs:

- Python syntax checks across `scripts/`, `tests/`, and `verify_repo.py`
- `python -m unittest discover -s tests -v`
- `dotnet build` for both tool projects
- `quick_validate.py` when the local Codex `skill-creator` validator is available

Useful options:

```powershell
python .\verify_repo.py --skip-dotnet
python .\verify_repo.py --skip-quick-validate
```

The unit suite now includes lightweight acceptance scenarios for these representative repo shapes:

- layered hybrid repos
- unpacked-solution-first repos
- ambiguous mixed repos
- tool-only repos
- sparse repos with no established structure

## Installing The Skill

Local install:

```powershell
.\install-skill.ps1
```

Local update:

```powershell
.\update-skill.ps1
```

GitHub-based install:

```powershell
.\install-skill.ps1 -Source GitHub
.\update-skill.ps1 -Source GitHub
```

Installed runtime payload includes only:

- `SKILL.md`
- `agents/`
- `assets/`
- `references/`
- `scripts/`
- `tools/`

Repo-only files such as `README.md`, `CODEX_HANDOFF.md`, `tests/`, and repo maintenance scripts stay in the source repo and are not copied into the installed skill.

## Using The Skill

Example prompts:

```text
Use $powerplatform-core to inspect this repo and infer the likely Dataverse solution, source areas, and plug-in project.
Use $powerplatform-core to create a new Dataverse table and expose it in the target model-driven app.
Use $powerplatform-core to update a form script, sync the web resource, and register the handler.
Use $powerplatform-core to package and deploy a PCF control from this repo.
Use $powerplatform-core to execute this requirement spec end to end.
```

When the repo is unfamiliar, start by running:

```powershell
python .\scripts\discover_context.py --path .
```

For exact helper arguments, use each script's CLI help:

```powershell
python .\scripts\deploy_solution.py --help
python .\scripts\deploy_pcf.py --help
python .\scripts\upsert_data.py --help
python .\scripts\get_flow_trigger_url.py --help
```

## Current Boundaries

Core intentionally does not:

- assume one house repo structure
- assume one namespace style
- ship overlay-owned house-style references
- imply that `scripts/upsert_data.py` supports a generic dry-run mode when it does not
- default to browser automation when repo-backed or headless paths exist

Some capabilities still remain partly workflow-driven rather than fully helper-packaged, especially:

- bespoke XML surgery
- highly repo-specific architecture decisions
- environment-specific acceptance testing
- document-template authoring that depends on one team's conventions

## Maintainer Notes

- Make generic changes here first.
- Keep overlay-specific prompts, examples, and conventions out of Core.
- If a repo already has a safe deploy wrapper, Core may use it, but Core should not prescribe one project-specific wrapper shape as a default.
- Keep `README.md` focused on overview, install, verification, and maintenance boundaries.
- Keep `CODEX_HANDOFF.md` focused on current repo state and in-flight work, not static capability manuals.

## Next Recommended Work

The only current tracked follow-on is issue `#19`:

- optional Azure control-plane reference as a secondary path

That remains explicitly optional and deferred behind the generic Core acceptance and verification foundation.
