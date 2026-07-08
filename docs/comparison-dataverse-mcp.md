# PowerPlatform-Core vs. the Microsoft Dataverse MCP server

People reasonably ask: *Microsoft ships a first-party [Dataverse MCP server](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/data-platform-mcp) — why would I install PowerPlatform-Core?*

**Short answer: they do different jobs, and they work well together.** The Dataverse MCP server lets agents **talk to your data**. PowerPlatform-Core lets agents **ship your solution** — flows, plug-ins, PCF, forms, security roles, solution ALM — from a Git repo, with deployment guardrails. We recommend running **both**.

*Last reviewed: July 2026, against PowerPlatform-Core v1.4.0 and the Dataverse MCP tool surface documented on Microsoft Learn (June 2026 restructure). Claims sourced from the community rather than official docs are marked ⚠.*

## What each one is

| | **Dataverse MCP server** | **PowerPlatform-Core** |
| --- | --- | --- |
| Form factor | Hosted MCP endpoint built into Dataverse (`https://{org}.crm.dynamics.com/api/mcp`) — nothing to install | Open-source coding-agent plugin (skills + Python/.NET toolchain) installed into Claude Code / OpenAI Codex |
| Made by | Microsoft (first-party, GA Dec 2025) | Community (Apache-2.0) |
| Serves | Copilot Studio agents, VS Code Copilot, Copilot CLI, Claude Desktop/Code — including **non-developer** conversational agents | Coding agents working in a **source-controlled repo** on a developer machine |
| Cost | Metered via Copilot Credits for agents outside Copilot Studio (since Dec 15, 2025) | Free; calls are ordinary Dataverse API traffic under your existing licenses |

## Capability comparison

| Capability | Dataverse MCP | PowerPlatform-Core |
| --- | --- | --- |
| Natural-language data exploration | ✅ `search` / `describe` / `read_query` — its core strength | ➖ Agent authors FetchXML/OData explicitly (design helpers included) |
| Row CRUD | ✅ create / update / delete (delete approval-gated) | ✅ create / read / update / upsert / **delete**, alternate keys, post-write `--verify` |
| Query at scale | ⚠ SQL `SELECT` subset (no JOIN/GROUP BY); ~20-row cap per call reported by community testing | ✅ FetchXML with bounded paging, paging cookies, match counts |
| Unstructured / Dataverse search | ✅ `search_data` (when Dataverse search is enabled) | ❌ |
| Table schema | ✅ create / update / delete table (⚠ community reports tables land in the Default Solution) | ✅ Tables, columns, lookups, choices, alternate keys, forms, views, ribbon, icons — **solution-aware** |
| Cloud flows | ❌ | ✅ Create, drift-guarded update, inspect, lint, hardening review, run history |
| Plug-ins & custom APIs | ❌ | ✅ Headless registration, build-and-push, step state |
| PCF / web resources / code apps | ❌ | ✅ |
| Solution ALM (pack / import / version / patch) | ❌ | ✅ With stale-artifact blocking and promotion audit |
| Security roles | ❌ (enforces the caller's roles; can't manage them) | ✅ Inspect / create / update as desired state |
| Tenant / environment admin | ❌ (governed *via* the admin center, doesn't administer) | ✅ Read-only inspection today (`pac admin`), writes planned behind an admin preflight |
| Source-control / repo awareness | ❌ No concept of a repo | ✅ Repo discovery is the entry point; changes are reviewable diffs |
| File transfer | ✅ SAS-URL upload/download | ➖ Word-template inspection/planning only |
| Central governance | ✅ Admin center kill switch, per-client allow-listing, DLP | ❌ No tenant-level governance surface |
| Safety on **deployments** | ➖ Delete approval only | ✅ Mandatory live-mutation preflight: blast radius, artifact provenance, rollback plan, no silent whole-solution escalation |

## When to use which

**Use the Dataverse MCP server when…**
- you want conversational, ad-hoc answers from live data ("which accounts changed this week?");
- the agent is a Copilot Studio / non-developer agent;
- you need zero-install access governed centrally by your admins.

**Use PowerPlatform-Core when…**
- you're building or changing *the solution itself* — schema, flows, plug-ins, PCF, forms, roles, packaging;
- the work must be source-controlled, reviewable, and delivered through a safe, targeted path;
- you need reads that scale (paging, counts, keyed verification) or write-back with evidence.

**Use both (recommended for developers):** register the Dataverse MCP alongside this plugin in the same agent —

```bash
claude mcp add dataverse -t stdio -- npx -y @microsoft/dataverse mcp https://yourorg.crm.dynamics.com
```

then let the MCP handle interactive data exploration while PowerPlatform-Core handles anything paged, keyed, verified, solution-aware, or deployed. Microsoft's own coding-agent tooling takes the same hybrid approach — MCP for conversational queries, SDK/Web API for bulk and schema work.

## Known caveats (both directions)

- Dataverse MCP: requires one-time tenant **admin consent** for non-Microsoft clients; tool names changed breakingly in the June 2026 restructure (`list_tables`/`describe_table`/`fetch` → `search`/`describe`); row caps and throttling limits are ⚠ community-observed, not officially documented.
- PowerPlatform-Core: requires a local toolchain (Python, .NET 8, `pac`); Claude Code and Codex are the fully tested hosts (Cursor/Copilot/Gemini manifests are experimental); some helpers are Windows-leaning (auth dialog, flow trigger-URL); safety preflights are enforced through the skills — hardening them into the tools themselves is on the [roadmap](roadmap.md).

*Sources: [Dataverse MCP docs](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/data-platform-mcp) · [connect other MCP clients](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/data-platform-mcp-other-clients) · [release plan (2025 wave 2)](https://learn.microsoft.com/en-us/power-platform/release-plan/2025wave2/data-platform/dataverse-mcp-server) · [tool-surface update (2026 wave 1)](https://learn.microsoft.com/en-us/power-platform/release-plan/2026wave1/data-platform/improve-dataverse-mcp-server-quality-updated-tools).*
