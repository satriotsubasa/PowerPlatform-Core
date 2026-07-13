# Contributing to PowerPlatform-Core

Thanks for wanting to help. This is a young project and I am still shaping the process, so bear with me.

## Before you start

- For a bug or a concrete feature, open an issue first (there are templates) so we can agree on the shape before you spend time on it.
- For anything large, check in early rather than sending a big surprise PR.

## Local setup

The plugin is code-first, so it needs a small local toolchain:

- Python 3.10+
- .NET 8 SDK
- Microsoft Power Platform CLI (`pac`) — only for live operations, not for building or running the tests
- Node.js — only for PCF / Code Apps work

From a clone, the bootstrap script checks (and can install) the toolchain:

```bash
./bootstrap.sh            # macOS/Linux; add --install to install what is missing
```
```powershell
./bootstrap.ps1           # Windows; add -Install to install what is missing
```

## Verifying your change

One command runs the whole gate:

```bash
python verify_repo.py
```

It runs Python syntax checks, the `unittest` suite, the skill-structure and manifest checks, and the .NET build and tests for the `DataverseOps` tool. The Windows-only WPF auth dialog is skipped automatically on macOS/Linux. CI runs the same command on every pull request, so if it passes locally it should pass there.

## Pull requests

- Keep changes focused. Smaller PRs get reviewed faster.
- Make sure `python verify_repo.py` passes.
- Update the relevant skill text or docs if you change behavior.
- If your change alters shipped plugin content, bump the version in the manifests (hosts cache the plugin by version).
- Never include secrets, real environment or tenant URLs, or customer data in code, tests, or the PR description.

## Safety-sensitive areas

This tool performs live Dataverse mutations and handles authentication. Changes to the auth path, the live-mutation preflight, or anything that writes to an environment get extra scrutiny. If you are touching those, say so in the PR so I know to look closely.

## Reporting security issues

Please do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).
