# Project Context Template

Use this checklist when the repository does not already make the project setup obvious. This is a per-task worksheet, not a permanent skill configuration. Run `python scripts/discover_context.py --path .` first, then ask only for the missing values that matter to the current task.

## Environment

- `DEV URL`:
- `TEST URL`:
- `Production allowed`: `no` unless the user explicitly overrides it.
- `Auth method`: `pac auth interactive` by default.
- `Dataverse MCP available`: yes or no.

## Solution

- `Main solution unique name`:
- `Solution display name`:
- `Publisher name`:
- `Publisher prefix`:
- `Managed strategy`: unmanaged source, managed release, or another stated approach.
- `Primary app(s)`:

## Repo Layout

- `Solution project path`:
- `Unpacked solution folder`:
- `Dataverse metadata reference path`:
- `Plug-in path`:
- `PCF path`:
- `Web resources path`:
- `Word Templates path`:
- `Reference path`:
- `Supplemental data path`:
- `Automation or flow assets path`:
- `Tests path`:
- `Project profile path`:

## Development Preferences

- `Plug-ins`: C#
- `Low-code plug-ins`: no
- `Custom APIs`: yes
- `Form scripts`: JS, TS, HTML, CSS
- `PCF`: yes
- `Early-bound generation`: yes or no

## Naming And Standards

- `Custom table pattern`:
- `Column pattern`:
- `Relationship pattern`:
- `Plug-in namespace`:
- `JavaScript or TypeScript namespace`:
- `PCF namespace`:
- `Preferred error message style`:

## Safety Gates

- Ask before delete: yes
- Ask before import: yes
- Ask before publish: yes
- Ask before register: yes
- Ask before push: yes
- Ask before upgrade: yes

## Validation

- Required build commands:
- Required lint commands:
- Required test commands:
- Manual validation expectations:

## Default Folder Layout When No Repo Convention Exists

```text
src/
  solution/
  plugins/
  pcf/
  webresources/
  automation/
tests/
artifacts/
```

## Discovery Order

Infer values before asking for them.

1. Read solution files such as `*.cdsproj`, `Other/Solution.xml`, `customizations.xml`, and deployment settings.
2. Read repo structure, solution references, plug-in projects, PCF manifests, and pipeline files.
3. Read an optional project profile such as `.codex/power-platform.project-profile.json` if it exists.
4. Read local auth or CLI context only if the task depends on the active environment.
5. Ask the user only for values that remain ambiguous or unavailable.
