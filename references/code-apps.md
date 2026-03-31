# Power Apps Code Apps

Power Apps Code Apps is a code-first app-hosting feature in Power Platform that lets developers build full custom web applications locally using standard web frameworks (React, Vue, vanilla TypeScript/JavaScript) and deploy them directly into a Power Platform environment. The app is governed by the managed platform — authentication, DLP, sharing limits, Conditional Access — without any server infrastructure to manage.

This is distinct from PCF controls (which are components embedded inside model-driven forms) and from Canvas Apps (which are built in the Power Apps maker studio). A code app is a full single-page application.

> **Preview status**: Code Apps is currently in preview. Some capabilities listed below are subject to change.

## Architecture

Three layers collaborate at runtime:

| Layer | Role |
|-------|------|
| Your app code | React/Vue/TS/JS SPA built with Vite. Imports `@microsoft/power-apps` client library. |
| Power Apps client library (`@microsoft/power-apps`) | Provides APIs for connectors, Dataverse services, authentication, and context. Generates model/service files when data sources are added. |
| Power Apps host | Manages end-user Entra authentication, app loading, connector consent, and platform policy enforcement. |

`power.config.json` at the repo root is the metadata bridge between the local project and the Power Platform environment. Neither your app code nor the host reads it directly during development — only the CLI uses it during `push`.

### Generated file structure

When you add a data source, the client library generates files in `/generated/services/`:

```
src/
  generated/
    models/
      AccountsModel.ts      ← TypeScript type definitions for the table
    services/
      AccountsService.ts    ← CRUD methods (create, get, getAll, update, delete)
power.config.json           ← app metadata (displayName, environmentId, appId)
```

Do not hand-edit generated files. Re-run `pac code add-data-source` or the npm CLI equivalent to regenerate.

## Prerequisites

### Developer tools

- Node.js (LTS)
- npm
- Git
- VS Code (or any IDE)
- Power Platform CLI (`pac`) — for legacy workflow or non-npm scenarios

### Environment requirements

- Power Platform environment with Dataverse enabled
- Code Apps feature toggled on (admin required):
  1. Power Platform Admin Center → **Environments** → select environment
  2. **Settings** → **Product** → **Features**
  3. Toggle **Enable code apps** → **Save**

### Licensing

End-users who run code apps require a **Power Apps Premium** license.

## Tooling: npm CLI vs pac CLI

From `@microsoft/power-apps` v1.0.4+, a new npm-based CLI replaces the older `pac code` commands. The npm CLI is the recommended path going forward.

| Task | npm CLI (recommended) | pac CLI (legacy, being deprecated) |
|------|----------------------|------------------------------------|
| Init app | `npx power-apps init` | `pac code init` |
| Run locally | `npm run dev` | `pac code run` |
| Push to environment | `npx power-apps push` | `pac code push` |
| Add data source | `pac code add-data-source` | `pac code add-data-source` |

## End-to-End Development Workflow

### 1. Scaffold the project

```bash
# Use the official Vite template from Microsoft
npx degit github:microsoft/PowerAppsCodeApps/templates/vite my-app
cd my-app
npm install
```

### 2. Initialize as a code app

```bash
# Interactive (prompts for displayName and environmentId)
npx power-apps init

# Or pass options directly
npx power-apps init --displayName "My App" --environmentId <env-id>
```

This writes `power.config.json` and authenticates against your Power Platform environment.

### 3. Develop locally

```bash
npm run dev
```

Open the **Local Play** URL in the same browser profile as your Power Platform tenant.

> **Browser note**: Chrome and Edge block requests from public origins to localhost by default since December 2025. Grant browser permission when prompted, or configure `allow="local-network-access"` for iframe embeds.

### 4. Add Dataverse as a data source

```bash
pac code add-data-source -a dataverse -t <table-logical-name>
```

This generates `AccountsModel.ts` and `AccountsService.ts` (or equivalent) in `/generated/services/`. Import and use them:

```typescript
import { AccountsService } from './generated/services/AccountsService';
import type { Accounts } from './generated/models/AccountsModel';
```

### 5. Build and push to Power Platform

```bash
npm run build           # tsc -b && vite build
npx power-apps push     # publish compiled app to environment
```

The push command returns a Power Apps URL to run and share the app.

## Dataverse CRUD Patterns

### Create

```typescript
const newAccount = { name: "New Account", accountnumber: "ACC001" };
const result = await AccountsService.create(newAccount as Omit<Accounts, 'accountid'>);
```

Exclude system-managed fields (`accountid`, `ownerid`, etc.) from create payloads.

### Read (single)

```typescript
const result = await AccountsService.get(accountId);
```

### Read (multiple, with filtering)

```typescript
const result = await AccountsService.getAll({
  select: ['name', 'accountnumber', 'address1_city'],
  filter: "address1_country eq 'Australia'",
  orderBy: ['name asc'],
  top: 50,
});
```

Always use `select` to limit columns. Delegation is supported for `filter`, `sort`, and `top`.

### Update

```typescript
await AccountsService.update(accountId, { name: "Updated Name", telephone1: "555-0123" });
```

Only include fields you are changing. Sending unchanged fields risks false audit entries and unintended business logic triggers.

### Delete

```typescript
await AccountsService.delete(accountId);
```

## ALM: Dev → Test → Prod

Code apps follow standard Power Platform ALM via solutions and pipelines.

### Step 1: Push to dev environment

```bash
# Push to preferred solution (auto-detected)
npx power-apps push

# Or target a specific solution via pac CLI
pac code push --solutionName <solutionUniqueName>
```

### Step 2: Add to solution (if not already)

In Power Apps maker portal:
1. **Solutions** → select solution → **Add existing** → **App** → **Code app**

### Step 3: Deploy through pipelines

Use Power Platform Pipelines for environment promotion (Dev → Test → Prod):
- Preflight checks for dependencies and connection references
- Managed environment enforcement from February 2026

### Connection references

Use connection references instead of hardcoding connector credentials so the same solution promotes across environments without reconfiguration.

## Monitoring

### Azure Application Insights

Set up App Insights for production telemetry:
- Track user sessions, errors, and performance
- See `how-to/set-up-azure-app-insights` in official docs

### PAC CLI telemetry

Manage CLI telemetry opt-in/out with:
```bash
pac telemetry enable
pac telemetry disable
```

## Admin and Security

### Content Security Policy

Configure CSP headers for your code app in the Power Platform Admin Center to restrict which external origins the app can load resources from.

### Managed platform capabilities

Code apps inherit these platform protections automatically:

| Capability | Notes |
|-----------|-------|
| Entra authentication | Handled by the host — no custom auth code needed |
| DLP enforcement | Applied at app launch |
| Sharing limits | Follow canvas app sharing limits |
| Conditional Access | Per-app Conditional Access supported |
| App Quarantine | Admin can quarantine apps |
| Tenant isolation | Cross-tenant restrictions apply |
| Azure B2B | External user access via Azure B2B |
| Health metrics | Available in Admin Center and maker portal |

## Known Limitations

| Area | Limitation |
|------|-----------|
| Mobile | Not supported in Power Apps mobile or Power Apps for Windows |
| Git integration | Power Platform Git integration not supported |
| SAS IP restriction | Storage SAS IP restriction not supported |
| Power BI | PowerBIIntegration function not supported (can embed app in Power BI via Power Apps Visual) |
| SharePoint forms | SharePoint forms integration not supported |
| Solution packager | `pac solution pack/unpack` not supported for code apps |
| Dataverse actions | Dataverse actions and functions not yet supported via generated services |
| Polymorphic lookups | Not yet supported |
| FetchXML | Not supported via generated services |
| Alternate keys | Not supported via generated services |

## Detecting a Code App Repo

A repo contains a code app if `power.config.json` exists at the root or within a subdirectory. Run `discover_context.py` — the `code_apps` key in the output lists detected code app roots with their display names and environment IDs.

## Official References

- [Code Apps overview](https://learn.microsoft.com/en-us/power-apps/developer/code-apps/overview)
- [Code Apps architecture](https://learn.microsoft.com/en-us/power-apps/developer/code-apps/architecture)
- [npm CLI quickstart](https://learn.microsoft.com/en-us/power-apps/developer/code-apps/how-to/npm-quickstart)
- [Connect to Dataverse](https://learn.microsoft.com/en-us/power-apps/developer/code-apps/how-to/connect-to-dataverse)
- [ALM for code apps](https://learn.microsoft.com/en-us/power-apps/developer/code-apps/how-to/alm)
- [Sample apps and templates](https://github.com/microsoft/PowerAppsCodeApps)
