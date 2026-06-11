# Development & Maintainer Notes

This document holds the maintainer-oriented detail that used to live in the README: verification internals, capability boundaries, current limitations, and recommended follow-on work. The README itself stays focused on a new user evaluating, installing, and using the plugin.

For the full capability breakdown, see [`capability-matrix.md`](capability-matrix.md). For Core-vs-overlay ownership and the install model, see [`core-overlay-architecture.md`](core-overlay-architecture.md).

## Verification

The canonical local verification entry point is `verify_repo.py` at the repo root:

```bash
python verify_repo.py
```

It runs, in order:

- **Python syntax** — compiles `verify_repo.py` and every `*.py` under `scripts/` and `tests/`.
- **Skill structure** — confirms each `skills/<name>/SKILL.md` has valid YAML frontmatter whose `name` matches its folder, and that the plugin manifests (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`) are valid JSON when present.
- **Unit tests** — `python -m unittest discover -s tests -v`.
- **.NET build** — builds `CodexPowerPlatform.DataverseOps` (multi-targets `net8.0`, plus `net8.0-windows` on Windows). The WPF `CodexPowerPlatform.AuthDialog` is built only on Windows.
- **.NET tests** — runs `CodexPowerPlatform.DataverseOps.Tests` (targets `net8.0-windows`, so it runs on Windows only).
- **Skill quick validation** — runs the skill-creator `quick_validate.py` when the validator is found under the Codex or Claude skill home; otherwise it is skipped with a note.

Useful flags: `--skip-python`, `--skip-tests`, `--skip-dotnet`, `--skip-quick-validate`.

The unit suite includes lightweight acceptance scenarios (`tests/acceptance_scenarios.json`, `tests/test_skill_acceptance_scenarios.py`) covering representative repo shapes: layered hybrid, unpacked-solution-first, ambiguous mixed, tool-only, and sparse repos with no established structure.

## Design principles

- Keep the skill generic. Do not hardcode one tenant, publisher prefix, namespace pattern, or repo layout.
- Keep presentation and configuration work in metadata when possible.
- For executable logic, prefer code-managed surfaces — client script for form-scoped behavior, plug-ins or custom APIs for shared server-side behavior. Do not introduce Dataverse Business Rules as an implementation surface.
- Prefer repo-backed, headless-first execution over browser automation.
- Surface PAC-profile vs. requested-target mismatches before live work rather than silently assuming the active PAC environment is correct.
- Keep changes solution-scoped. Ask before delete, import, publish, register, push, or upgrade.
- Treat project context as runtime input, not fixed skill configuration.
- Optimize user waiting time, not just eventual completion. Fail fast when preflight says the surface is manual-only, unsupported, or timed out.

## Current boundaries

Core intentionally does **not**:

- assume one house repo structure or namespace style;
- ship overlay-owned house-style references;
- imply that `scripts/upsert_data.py` supports a generic dry-run mode (it does not — that phase stays in the workflow or repo tooling layer);
- default to browser automation when repo-backed or headless paths exist.

Some capabilities remain partly workflow-driven rather than fully helper-packaged, especially:

- bespoke XML surgery;
- highly repo-specific architecture decisions;
- environment-specific acceptance testing;
- document-template authoring that depends on one team's conventions.

## Known limitations today

- **Cross-surface auth unification is incomplete.** Dataverse SDK helpers, the PAC CLI, and Power Apps admin flows still use separate auth stacks, so one extra Power Apps sign-in can occur for helper paths such as flow trigger-URL retrieval.
- **First-time plug-in registration** is implemented for the two primary flows (assembly-based and package-based) and is primarily repo- and build-validated in this repo rather than broadly live-write regression-tested.
- **User/team role assignment is not packaged yet.** Core can inspect, create, and update roles, but assigning roles to users or teams is still workflow-driven.
- **Fully generic deployment/acceptance testing is not complete.** `scripts/validate_delivery.py` plus the repo-local regression suite cover safe validation well, but environment-specific acceptance helpers and broader live validation are still needed.
- **No exact context-pressure meter** — the skill uses heuristics, not a real percentage.

See [`capability-matrix.md`](capability-matrix.md) for the per-capability status, packaging category, and notes.

## Maintenance rules

- Make generic changes here first. Keep overlay-specific prompts, examples, and conventions out of Core.
- If a repo already has a safe deploy wrapper, Core may use it — but Core should not prescribe one project-specific wrapper shape as a default.
- Keep `README.md` focused on the new-user path (evaluate, install, use). Keep this file and `capability-matrix.md` for maintainer depth.
- Keep `CODEX_HANDOFF.md` focused on current repo state and in-flight work, not static capability manuals.

## Next recommended work

From the helper backlog (see [`capability-matrix.md`](capability-matrix.md) for the full list):

1. Live environment validation for the newest design and review helpers.
2. Direct patch, merge, and solution-upgrade execution helpers.
3. Richer Power Automate connector-specific authoring helpers.
4. Document-template authoring helpers for stable repo patterns.
5. Broader repo-profile adoption guidance across more repo archetypes.

The one explicitly tracked optional follow-on is issue `#19` (an optional Azure control-plane reference as a secondary path), deferred behind the generic Core acceptance and verification foundation.
