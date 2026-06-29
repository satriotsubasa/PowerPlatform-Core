---
name: platform-administration
description: >
  Use for Power Platform TENANT and ENVIRONMENT administration - the tasks normally done in the
  Power Platform Admin Center, driven headlessly via the `pac admin` CLI and the Power Platform
  API. Covers listing environments, creating / resetting / backing-up / restoring / deleting
  environments, reading and writing tenant settings, data loss prevention (DLP) policies, managed
  environments, environment groups, application users / admin service principals, and capacity
  reporting. Trigger on "list the environments", "create / reset / delete / backup / restore an
  environment", "tenant settings", "DLP" / "data policy", "managed environment", "environment
  group", "Power Platform admin", "admin center", or "what environments are in this tenant", even
  when no helper is named. Admin-tier: it needs a Power Platform Administrator profile, distinct
  from the maker/developer Dataverse auth the other skills use. NOT for Dataverse data or solution
  ALM inside a single environment - use data-operations or solution-alm-delivery. Run the admin
  preflight before any environment or tenant write.
---

# Platform Administration — Tenant & Environment Admin

This skill owns Power Platform **tenant and environment administration**: the operations normally performed in the Power Platform Admin Center, done headlessly and code-first via the **`pac admin`** CLI and the **Power Platform API** (`Microsoft.PowerPlatform.Management` .NET SDK / `powerplatform-management` Python SDK). It is the administration branch of the `powerplatform-core` orchestrator.

It is **not** for working inside a single environment's data or solutions — row data is `data-operations`, solution packaging/delivery is `solution-alm-delivery`, security roles are `security-roles`. This skill operates one level up: the tenant and its environments.

## Admin-tier auth (read this first)

Administration uses a **different identity tier** than the rest of the plugin. The maker/developer Dataverse auth (the auth dialog, a System Customizer/Administrator security role in one environment) is **not** enough.

- Admin commands need the active **`pac auth`** profile to hold the **Power Platform Administrator** (or Microsoft 365 Global Administrator) role. Check with `pac auth who` / `pac auth list`; create an admin profile with `pac auth create` using an admin account.
- For unattended automation you can use an **admin service principal**, but an SPN **can't register itself** as a tenant admin — a human admin registers it once (Power Platform API / `New-PowerAppManagementApp`), after which it runs headless. An admin SPN is treated as a full Power Platform Administrator (no granular scoping), so guard its credentials accordingly.
- If an admin command fails with an authorization error, the cause is almost always a non-admin profile — surface that, don't retry blindly.

## When to use this

- List the environments in the tenant, or inspect one environment's settings/capacity.
- Read or change **tenant settings** (governance, environment-creation, default-environment routing, licensing flags).
- Inspect or manage **DLP / data policies** (`pac admin` can only *read* DLP — create/edit/delete go through the Power Platform API / SDK / admin connector).
- Enable/configure **managed environments** or **environment groups**.
- Create, reset, back up, restore, or delete an **environment**.
- Set up an **application user** or **admin service principal**.

## Helpers

The helpers live in the plugin's `scripts/` directory at the plugin root. Resolve the plugin root and invoke them with `$CLAUDE_PLUGIN_ROOT` / `$CODEX_PLUGIN_ROOT` (also `$PLUGIN_ROOT`), or by their path within the install.

| Helper | Purpose |
| --- | --- |
| `admin_inspect.py` | **Read-only.** Inspect tenant/environment administration via `pac admin`: `--mode environments` (list environments), `--mode tenant-settings`, `--mode dlp-policies` (list), `--mode groups` (environment groups). Returns the `pac admin` output in a JSON envelope; on an auth failure it returns a hint about needing an admin profile. No preflight (non-mutating). |

> **Capability status (phased).** Read-only inspection (`admin_inspect.py`) is implemented now. **Writes and deletes do not yet have dedicated helpers** — until they land, perform a specific admin write by running the exact `pac admin` command (or the Power Platform API) **only after the admin preflight below and explicit user approval**. Do not invent a helper that doesn't exist.

## Mandatory admin preflight (before ANY environment or tenant write/delete)

Administration changes have a far higher blast radius than a single data write — an environment delete or reset is **irreversible** and a tenant setting affects everyone. Before any create / update / delete / reset / restore / DLP-write / tenant-setting-write, print or capture an **admin preflight** and stop if any required field is missing:

- **Tenant + target:** tenant, and the target environment name + ID + URL (or "tenant-wide" for tenant settings / DLP).
- **Admin identity:** which `pac auth` profile / service principal is being used, and confirmation it holds the Power Platform Administrator role.
- **Operation:** the exact operation and the precise `pac admin` command (or API call) that will run.
- **Blast radius:** who/what is affected — one environment, all makers in the tenant, specific connectors (for DLP), etc.
- **Reversibility:** whether it can be undone. **Environment delete, reset, and restore are irreversible / destructive** — require a fresh **backup first** and an explicit, typed user confirmation naming the environment.
- **Recovery plan:** backup taken (id/time) and how to roll back if it goes wrong.

Hard rules:
- **Never** delete, reset, or restore an environment, or change a tenant-wide setting/DLP policy, without the preflight and explicit approval. Treat production environments as off-limits unless the user explicitly and separately approves.
- Reads (`admin_inspect.py` and other list/show operations) are non-mutating and **skip** the preflight.
- Prefer the cross-platform paths: `pac admin` and the Power Platform API / .NET+Python SDKs. **Avoid** the `Microsoft.PowerApps.Administration.PowerShell` module — it is Windows-PowerShell-5.x only and breaks cross-platform use; use the API/SDK for what `pac admin` can't do (notably DLP create/edit/delete).

## Boundaries

- Dataverse row data, queries, seeding → `data-operations`.
- Solution pack/import/deploy/versioning inside an environment → `solution-alm-delivery`.
- Security roles and privileges inside an environment → `security-roles`.
- This skill is the tenant/environment layer above all of those.
